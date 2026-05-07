#!/usr/bin/env bash
# entrypoint.sh — runtime initialiser for the trademind ERPNext image.
#
# Responsibilities, in order:
#   1. Generate sites/common_site_config.json from env vars (every start).
#   2. If SITE_NAME's directory doesn't exist yet, run `bench new-site` to
#      create the database + first admin user. Idempotent: skipped on every
#      subsequent boot.
#   3. Always run `bench migrate` so app upgrades roll forward
#      automatically. (Cheap no-op when the schema is current.)
#   4. exec the requested role:
#        all        → supervisord drives gunicorn + scheduler + worker(s) + socketio
#        web        → gunicorn only (single-process container)
#        worker     → bench worker only
#        scheduler  → bench schedule only
#        socketio   → node socketio.js only
#        bench …    → passthrough to bench CLI (admin one-shots)
#
# Required env vars (entrypoint exits 1 if any are unset):
#   SITE_NAME              the bench site to use as default
#   ERPNEXT_DB_HOST        Postgres host (Aliyun RDS endpoint)
#   ERPNEXT_DB_PORT        Postgres port (default 5432)
#   ERPNEXT_DB_PASSWORD    pg superuser password (used by bench new-site)
#   ERPNEXT_REDIS_HOST     Redis host
#   ERPNEXT_REDIS_PORT     Redis port (default 6379)
#
# Optional:
#   ERPNEXT_DB_ROOT_LOGIN  pg superuser name (default: postgres)
#   ERPNEXT_DB_NAME        Postgres database name to create + use for this
#                          site. Default: derived by Frappe from SITE_NAME
#                          via a 16-char hash (`_a1b2c3d4e5f6g7h8`). Set
#                          this to a readable name (e.g. `erpnext`) when
#                          sharing one RDS instance with other services.
#                          Frappe also creates a same-named DB user with
#                          `db_password` (auto-generated random) and
#                          stores it in sites/<site>/site_config.json on
#                          first run, so don't pre-create the user.
#   ERPNEXT_REDIS_PASSWORD Redis auth (omit if Redis has no requirepass)
#   ERPNEXT_ADMIN_PASSWORD admin password seeded into the new site
#                          (default: random-then-printed; check container logs)
#   GUNICORN_WORKERS       gunicorn worker count (default: 4)
#   BACKGROUND_WORKERS     bench background worker count (default: 1)

set -euo pipefail

BENCH_DIR="/home/frappe/frappe-bench"
SITES_DIR="$BENCH_DIR/sites"
SITES_TEMPLATE="/home/frappe/sites-template"

cd "$BENCH_DIR"

err() { printf "[entrypoint] ERROR: %s\n" "$*" >&2; }
log() { printf "[entrypoint] %s\n" "$*"; }

# ── Required env validation ──────────────────────────────────────────────────
require() {
    local name="$1"
    if [ -z "${!name:-}" ]; then
        err "$name is required but unset"
        exit 1
    fi
}

require SITE_NAME
require ERPNEXT_DB_HOST
require ERPNEXT_DB_PASSWORD
require ERPNEXT_REDIS_HOST

DB_PORT="${ERPNEXT_DB_PORT:-5432}"
DB_ROOT_LOGIN="${ERPNEXT_DB_ROOT_LOGIN:-postgres}"
REDIS_PORT="${ERPNEXT_REDIS_PORT:-6379}"
REDIS_PASSWORD="${ERPNEXT_REDIS_PASSWORD:-}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
BACKGROUND_WORKERS="${BACKGROUND_WORKERS:-1}"

# Build redis URLs with optional auth. Aliyun Cloud Redis usually requires
# `requirepass`; URL form is redis://:<password>@host:port/<db>.
redis_url() {
    local db="$1"
    if [ -n "$REDIS_PASSWORD" ]; then
        echo "redis://:${REDIS_PASSWORD}@${ERPNEXT_REDIS_HOST}:${REDIS_PORT}/${db}"
    else
        echo "redis://${ERPNEXT_REDIS_HOST}:${REDIS_PORT}/${db}"
    fi
}

# ── Hydrate sites/ from the image template ───────────────────────────────────
# The runtime volume mount at /home/frappe/frappe-bench/sites shadows the
# image's built-in assets/ directory, so on first start (empty volume) and
# after image upgrades (newer asset bundle) we sync the bake-time template
# into the live tree. rsync's --update is conservative: it never overwrites
# a newer file in the target, so per-site uploads (sites/<site>/{public,
# private}/files/) are safe.
if [ -d "$SITES_TEMPLATE" ]; then
    log "syncing image asset template → $SITES_DIR"
    rsync -a --update "$SITES_TEMPLATE/" "$SITES_DIR/"
fi

# ── Generate common_site_config.json ─────────────────────────────────────────
# Regenerated on every container start so config drift always converges to
# the env vars. site_config.json (per-site db credentials) is preserved
# because it lives in sites/$SITE_NAME/ and is volume-mounted.
log "writing $SITES_DIR/common_site_config.json"
cat > "$SITES_DIR/common_site_config.json" <<EOF
{
  "db_type": "postgres",
  "db_host": "${ERPNEXT_DB_HOST}",
  "db_port": "${DB_PORT}",
  "redis_cache":    "$(redis_url 0)",
  "redis_queue":    "$(redis_url 1)",
  "redis_socketio": "$(redis_url 2)",
  "root_login":    "${DB_ROOT_LOGIN}",
  "root_password": "${ERPNEXT_DB_PASSWORD}",
  "background_workers": ${BACKGROUND_WORKERS},
  "gunicorn_workers":   ${GUNICORN_WORKERS},
  "webserver_port": 8000,
  "socketio_port":  9000,
  "serve_default_site": true,
  "use_redis_auth": $([ -n "$REDIS_PASSWORD" ] && echo true || echo false),
  "restart_supervisor_on_update": false,
  "restart_systemd_on_update": false,
  "shallow_clone": true,
  "live_reload": false
}
EOF

# Mark default site so `bench --site $SITE_NAME` is implicit.
echo "$SITE_NAME" > "$SITES_DIR/currentsite.txt"

# ── First-run: create the site if its directory is missing ───────────────────
if [ ! -d "$SITES_DIR/$SITE_NAME" ]; then
    log "site '$SITE_NAME' does not exist — running bench new-site"
    ADMIN_PASS="${ERPNEXT_ADMIN_PASSWORD:-$(openssl rand -hex 12)}"
    if [ -z "${ERPNEXT_ADMIN_PASSWORD:-}" ]; then
        log "ERPNEXT_ADMIN_PASSWORD not set — generated: $ADMIN_PASS  (save this!)"
    fi

    db_name_args=()
    if [ -n "${ERPNEXT_DB_NAME:-}" ]; then
        log "using explicit ERPNEXT_DB_NAME=$ERPNEXT_DB_NAME"
        db_name_args=(--db-name "$ERPNEXT_DB_NAME")
    fi

    bench new-site \
        --db-type postgres \
        --db-host "$ERPNEXT_DB_HOST" \
        --db-port "$DB_PORT" \
        --db-root-username "$DB_ROOT_LOGIN" \
        --db-root-password "$ERPNEXT_DB_PASSWORD" \
        "${db_name_args[@]}" \
        --admin-password "$ADMIN_PASS" \
        --install-app erpnext \
        --no-mariadb-socket \
        "$SITE_NAME"

    log "site '$SITE_NAME' created"

    # ── First-run: enable multi-tenant row-level-security ───────────────────
    # ERPNext's tenant model requires four offline DDL steps after install
    # (see erpnext/erpnext/commands/tenant.py). They MUST run after the seed
    # data has landed, because CREATE/ALTER policies on tenant-scoped tables
    # would block the install-time inserts from `bench install-app erpnext`
    # if RLS were on already. Doing them here folds the human "run these
    # four commands" step into the same lifecycle as new-site.
    #
    # Idempotent within a fresh DB: add-tenant-id skips columns that
    # already exist; backfill UPDATE 0 rows when nothing is NULL;
    # rewrite-tenant-unique-keys uses a backup table and skips already-
    # rewritten constraints; enable-tenant-rls re-applies its policy.
    DEFAULT_TENANT="${ERPNEXT_DEFAULT_TENANT_ID:-__system__}"
    log "enabling tenant RLS (default tenant for backfill: $DEFAULT_TENANT)"
    bench --site "$SITE_NAME" add-tenant-id --all
    bench --site "$SITE_NAME" backfill-tenant-id --all --tenant "$DEFAULT_TENANT"
    bench --site "$SITE_NAME" rewrite-tenant-unique-keys --all
    bench --site "$SITE_NAME" enable-tenant-rls --all
    log "tenant RLS enabled"
else
    log "site '$SITE_NAME' already exists — skipping new-site"

    # On every restart, replay add-tenant-id so newly-installed apps (or
    # newly-added DocTypes from `bench migrate`) get the column. Idempotent
    # — skips DocTypes that already have it. The other three steps
    # (backfill / rewrite-keys / enable-rls) are NOT replayed because
    # rewrite-keys is destructive on already-rewritten indexes if the
    # backup table got truncated, and re-enabling RLS is a no-op for
    # tables already covered.
    log "ensuring new DocTypes have tenant_id column (idempotent)"
    bench --site "$SITE_NAME" add-tenant-id --all \
        || log "WARN: add-tenant-id failed (non-fatal — see traceback above)"
fi

# ── Roll migrations forward ──────────────────────────────────────────────────
log "running bench migrate"
bench --site "$SITE_NAME" migrate

# ── Dispatch ─────────────────────────────────────────────────────────────────
ROLE="${1:-all}"
shift || true

case "$ROLE" in
    all)
        log "starting full process group via supervisord"
        exec supervisord -c /etc/supervisor/conf.d/erpnext.conf -n
        ;;
    web)
        log "starting gunicorn (web) only"
        exec gunicorn \
            --bind 0.0.0.0:8000 \
            --workers "$GUNICORN_WORKERS" \
            --timeout 120 \
            --access-logfile - \
            --error-logfile - \
            frappe.app:application
        ;;
    worker)
        QUEUE="${WORKER_QUEUE:-default}"
        log "starting bench worker (queue=$QUEUE)"
        exec bench worker --queue "$QUEUE"
        ;;
    scheduler)
        log "starting bench schedule"
        exec bench schedule
        ;;
    socketio)
        log "starting node socketio"
        exec node "$BENCH_DIR/apps/frappe/socketio.js"
        ;;
    bench)
        # Passthrough: docker run ... bench migrate / list-apps / new-site / etc.
        log "passthrough: bench $*"
        exec bench "$@"
        ;;
    *)
        err "unknown role: $ROLE (valid: all, web, worker, scheduler, socketio, bench)"
        exit 2
        ;;
esac
