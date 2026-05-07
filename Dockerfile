# syntax=docker/dockerfile:1.7
#
# ERPNext + Frappe production image for the trademind workspace.
#
# Build context MUST be the workspace root (the directory containing both
# `frappe/` and `erpnext/` sibling checkouts). The build COPY's both into
# the builder stage so bench can be initialised against our local forks
# instead of the upstream frappe/erpnext that bench would otherwise clone.
#
# Invocation (handled by scripts/build/build-images.sh --only erpnext):
#
#   docker buildx build \
#     --platform linux/amd64 \
#     -f erpnext/Dockerfile \
#     -t <repo>/trademind-erpnext:<sha> \
#     -t <repo>/trademind-erpnext:prod \
#     --push \
#     <workspace-root>
#
# Notes:
#   * Postgres + Redis are external (Aliyun RDS / Aliyun Redis). The image
#     does NOT bundle either — common_site_config.json is generated at
#     container start from env vars (see docker/entrypoint.sh).
#   * Site data lives in /home/frappe/frappe-bench/sites which the prod
#     compose mounts as a host volume so private files survive restarts.
#   * Web (gunicorn), scheduler, workers, and socketio run as a single
#     supervisord process group inside one container — fine for one-VM
#     deployments. Split into separate containers later if you need to
#     scale workers independently.

ARG PYTHON_VERSION=3.14
ARG NODE_MAJOR=24
ARG WKHTMLTOPDF_RELEASE=0.12.6.1-3

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder — install bench, materialise the bench tree, build assets
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG NODE_MAJOR

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Swap Debian apt repos to a China mirror so apt-get update doesn't hang
# on deb.debian.org (bookworm-slim uses the deb822 .sources format).
RUN sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g; s|security.debian.org|mirrors.ustc.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g; s|security.debian.org|mirrors.ustc.edu.cn|g' \
        /etc/apt/sources.list

# System deps + Node.js (for `bench build`'s asset compilation).
# build-essential and the *-dev packages are needed because frappe pulls
# native Python wheels (psycopg2-binary works, but lxml / xmlsec / pillow
# / cryptography may need to compile depending on platform).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git gnupg \
        build-essential pkg-config \
        libpq-dev libffi-dev libssl-dev \
        default-libmysqlclient-dev \
        libjpeg-dev zlib1g-dev libtiff-dev \
        libxml2-dev libxslt1-dev libxmlsec1-dev libxmlsec1-openssl \
        libsasl2-dev libldap2-dev \
        cron \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g yarn \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash frappe
USER frappe
WORKDIR /home/frappe

# Install bench CLI (frappe-bench is the orchestrator) into ~/.local
RUN pip install --user --no-cache-dir frappe-bench

ENV PATH="/home/frappe/.local/bin:${PATH}"

# Bring in the local fork checkouts. Both directories include their .git
# folders so bench can run a local `git clone` against them. Build context
# = workspace root, so paths are relative to that.
COPY --chown=frappe:frappe frappe  /home/frappe/_src/frappe
COPY --chown=frappe:frappe erpnext /home/frappe/_src/erpnext

# `bench init` clones frappe-path into apps/frappe. Pointing at a local
# directory makes bench do `git clone /local/path` — committed state only,
# not working-tree edits, so the build script enforces a clean tree.
RUN bench init \
        --frappe-path=/home/frappe/_src/frappe \
        --skip-redis-config-generation \
        --skip-assets \
        --no-procfile \
        --python python${PYTHON_VERSION} \
        --verbose \
        frappe-bench

WORKDIR /home/frappe/frappe-bench

# Pull in our erpnext fork the same way. Newer bench CLI defaults to
# not resolving deps (the old `--no-resolve-deps` flag was removed and
# replaced by an opt-in `--resolve-deps`), so a bare `get-app` keeps
# bench from re-fetching frappe — it's already wired up by `bench init`.
RUN bench get-app /home/frappe/_src/erpnext

# Build production-mode JS/CSS assets. This is the slowest step (~10 min
# on first build); buildx layer caching keeps subsequent builds fast.
RUN bench build --production --app frappe --app erpnext

# Snapshot the built sites/ tree (assets, apps.txt, common templates)
# into a path that won't be shadowed by the runtime volume mount. On
# container start the entrypoint rsyncs this template back into the
# volume, so a fresh ECS host's empty volume gets populated and an
# image upgrade refreshes the JS/CSS bundles automatically.
RUN mkdir -p /home/frappe/sites-template \
    && cp -a sites/. /home/frappe/sites-template/

# Strip dev-only artifacts to shrink the runtime layer.
# Keep apps/frappe/node_modules — frappe's realtime server
# (apps/frappe/socketio.js) requires `socket.io` and friends at
# runtime. apps/erpnext/node_modules is build-time only (used by
# `bench build --production` to compile assets) and can go.
# Top-level node_modules is bench tooling, also build-time only.
RUN find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find . -name "*.pyc" -delete \
    && rm -rf node_modules apps/erpnext/node_modules apps/*/.git \
    && rm -rf /home/frappe/_src

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime — minimal image with the built bench tree
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG NODE_MAJOR
ARG WKHTMLTOPDF_RELEASE

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/home/frappe/.local/bin:/home/frappe/frappe-bench/env/bin:${PATH}"

# Same China mirror swap as the builder stage — runtime is a fresh
# python:slim-bookworm so it ships the upstream sources.
RUN sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g; s|security.debian.org|mirrors.ustc.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g; s|security.debian.org|mirrors.ustc.edu.cn|g' \
        /etc/apt/sources.list

# Runtime-only system deps (no compilers, no -dev headers).
# wkhtmltopdf MUST be the patched-Qt 0.12.6+ build for frappe's PDF render
# to work; the apt version on bookworm doesn't include the qt patches.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg git \
        libpq5 libffi8 libssl3 \
        libmariadb3 \
        libxml2 libxslt1.1 libxmlsec1 libxmlsec1-openssl \
        libjpeg62-turbo zlib1g libtiff6 \
        libsasl2-2 libldap-2.5-0 libxrender1 libxext6 \
        redis-tools postgresql-client \
        fonts-cantarell fonts-noto-cjk fonts-noto-color-emoji fontconfig \
        xfonts-75dpi xfonts-base \
        supervisor rsync cron \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && curl -fsSL "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_RELEASE}/wkhtmltox_${WKHTMLTOPDF_RELEASE}.bookworm_amd64.deb" \
        -o /tmp/wkhtml.deb \
    && apt-get install -y --no-install-recommends /tmp/wkhtml.deb \
    && rm /tmp/wkhtml.deb \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash frappe \
    && mkdir -p /var/log/supervisor /var/run/supervisor \
    && chown -R frappe:frappe /var/log/supervisor /var/run/supervisor

# Bring over the bench tree + bench CLI from the builder. The bench env's
# Python venv has frappe/erpnext installed in editable mode at exactly the
# same path, so the COPY preserves the install layout.
COPY --from=builder --chown=frappe:frappe /home/frappe/.local           /home/frappe/.local
COPY --from=builder --chown=frappe:frappe /home/frappe/frappe-bench     /home/frappe/frappe-bench
# sites-template is the snapshot of sites/ (assets, apps.txt, ...) that
# entrypoint rsyncs into the runtime volume on every start.
COPY --from=builder --chown=frappe:frappe /home/frappe/sites-template   /home/frappe/sites-template

# Runtime config files (entrypoint generates common_site_config from env
# on first start; supervisord runs the four-process group).
COPY --chown=frappe:frappe erpnext/docker/entrypoint.sh    /entrypoint.sh
COPY --chown=frappe:frappe erpnext/docker/supervisord.conf /etc/supervisor/conf.d/erpnext.conf
RUN chmod +x /entrypoint.sh

USER frappe
WORKDIR /home/frappe/frappe-bench

# 8000 = gunicorn web; 9000 = node socketio.
# An external nginx (sidecar or Aliyun SLB) usually fronts both.
EXPOSE 8000 9000

ENTRYPOINT ["/entrypoint.sh"]
# Default role: run the full process group via supervisord. Override the
# command with `bench` for one-shot admin tasks (migrate, new-site, etc.).
CMD ["all"]
