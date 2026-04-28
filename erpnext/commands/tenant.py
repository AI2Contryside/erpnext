"""Bench commands for provisioning multi-tenant row-level-security.

These commands are **offline, operator-driven** one-shot actions. They are
intentionally kept out of runtime hooks so that a misconfigured site cannot
silently alter table DDL on every request.

Typical rollout sequence
------------------------
1. ``bench --site <site> add-tenant-id --all``
      Adds a ``tenant_id`` Custom Field (hidden, indexed) to every
      tenant-scoped DocType. Does NOT enable RLS yet; existing rows have a
      NULL tenant_id so all callers continue to work.

2. ``bench --site <site> backfill-tenant-id --tenant <default_tenant>``
      Populates NULL ``tenant_id`` on existing rows. Safe to re-run.

3. ``bench --site <site> rewrite-tenant-unique-keys --all``
      Drops every non-partial UNIQUE index/constraint on tables that carry
      ``tenant_id`` and recreates it with ``tenant_id`` prepended, so two
      tenants can share otherwise-unique values (Item.item_code,
      Customer.tax_id, the ``name`` PK, etc.) without colliding at the
      database layer. Original definitions are stashed in
      ``_tenant_unique_index_backup`` so the change is reversible.

4. ``bench --site <site> enable-tenant-rls --all``
      Enables Row Level Security and creates the isolation policy on every
      table that has a ``tenant_id`` column. After this point, any query
      that runs without ``app.current_tenant`` set sees zero rows from
      tenant-scoped tables — including background jobs. Be prepared.

5. ``bench --site <site> disable-tenant-rls --all`` (emergency only).
6. ``bench --site <site> revert-tenant-unique-keys --all`` (emergency only).
"""

from __future__ import annotations

import json
from typing import Iterable

import click

import frappe
from frappe.commands import get_site, pass_context

# Frappe/system modules whose DocTypes must NOT be tenant-scoped. Anything
# outside this list becomes a tenant-scoped target for ``--all``.
SYSTEM_MODULES = frozenset(
	{
		"Core",
		"Desk",
		"Integrations",
		"Workflow",
		"Website",
		"Printing",
		"Email",
		"Custom",
		"Geo",
		"Contacts",
		"Automation",
		"Social",
		"Bulk Transaction",
		"Data Migration",
	}
)

# Individually excluded DocTypes (in non-system modules) that store
# cross-tenant reference data and therefore must stay global.
EXPLICIT_EXCLUDES = frozenset(
	{
		"Country",
		"Currency",
		"Currency Exchange",
		"UOM",
		"UOM Category",
		"UOM Conversion Factor",
		"Language",
		"Time Zone",
	}
)


def _require_postgres() -> None:
	if frappe.db.db_type != "postgres":
		raise click.ClickException(
			f"Tenant isolation requires PostgreSQL; this site uses {frappe.db.db_type}."
		)


def _target_doctypes(explicit: tuple[str, ...], all_flag: bool) -> list[str]:
	if explicit and all_flag:
		raise click.ClickException("--all and explicit doctype arguments are mutually exclusive.")
	if explicit:
		return list(explicit)
	if not all_flag:
		raise click.ClickException("Pass DocType names or --all.")
	rows = frappe.db.sql(
		"""SELECT name FROM "tabDocType"
		   WHERE istable = 0 AND issingle = 0 AND is_virtual = 0
		     AND module NOT IN %(skip)s
		     AND name NOT IN %(explicit_excludes)s
		   ORDER BY name""",
		{"skip": tuple(SYSTEM_MODULES), "explicit_excludes": tuple(EXPLICIT_EXCLUDES)},
		as_dict=False,
	)
	return [r[0] for r in rows]


def _add_tenant_field(doctype: str) -> str:
	"""Return one of: 'added', 'skipped-existing', 'skipped-no-table'."""
	if not frappe.db.table_exists(doctype):
		return "skipped-no-table"
	if frappe.db.has_column(doctype, "tenant_id"):
		return "skipped-existing"
	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": "tenant_id",
			"fieldtype": "Data",
			"label": "Tenant ID",
			"hidden": 1,
			"read_only": 1,
			"no_copy": 1,
			"allow_on_submit": 1,
			"report_hide": 1,
			"search_index": 1,
			"in_standard_filter": 0,
			"in_list_view": 0,
			"in_global_search": 0,
		}
	)
	custom_field.insert(ignore_permissions=True)
	frappe.db.commit()
	return "added"


def _policy_name(doctype: str) -> str:
	# Policy names must be valid SQL identifiers. DocType names may contain
	# spaces/punctuation; hash them into a stable short suffix instead.
	import hashlib

	digest = hashlib.sha1(doctype.encode("utf-8")).hexdigest()[:12]
	return f"tenant_isolation_{digest}"


def _table_ident(doctype: str) -> str:
	# Table names are ``tab<DocType>``; quote with doubled double-quotes if
	# the name itself contains one (defensive — Frappe forbids it in
	# practice). Returning a pre-quoted identifier lets us safely inline it
	# into DDL, which PostgreSQL does not parameterise.
	safe = doctype.replace('"', '""')
	return f'"tab{safe}"'


def _enable_rls(doctype: str) -> str:
	if not frappe.db.has_column(doctype, "tenant_id"):
		return "skipped-no-column"
	ident = _table_ident(doctype)
	policy = _policy_name(doctype)
	frappe.db.sql(f"ALTER TABLE {ident} ENABLE ROW LEVEL SECURITY")
	frappe.db.sql(f"ALTER TABLE {ident} FORCE ROW LEVEL SECURITY")
	frappe.db.sql(f"DROP POLICY IF EXISTS {policy} ON {ident}")
	# USING filters reads; WITH CHECK restricts inserts/updates. Both
	# anchor to the session variable set by
	# erpnext.tenant_isolation.apply_tenant_context.
	frappe.db.sql(
		f"""CREATE POLICY {policy} ON {ident}
		    USING (tenant_id = current_setting('app.current_tenant', true))
		    WITH CHECK (tenant_id = current_setting('app.current_tenant', true))"""
	)
	frappe.db.commit()
	return "enabled"


def _disable_rls(doctype: str) -> str:
	ident = _table_ident(doctype)
	policy = _policy_name(doctype)
	frappe.db.sql(f"DROP POLICY IF EXISTS {policy} ON {ident}")
	frappe.db.sql(f"ALTER TABLE {ident} DISABLE ROW LEVEL SECURITY")
	frappe.db.commit()
	return "disabled"


def _iter_targets(targets: Iterable[str], op_label: str):
	for doctype in targets:
		try:
			yield doctype, None
		except Exception as exc:  # pragma: no cover — defensive
			click.secho(f"  [{op_label}] {doctype}: {exc}", fg="red")


@click.command("add-tenant-id")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Apply to every tenant-scoped DocType.")
@pass_context
def add_tenant_id(context, doctypes: tuple[str, ...], all_flag: bool):
	"""Add a hidden, indexed ``tenant_id`` Custom Field to the given DocTypes."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		targets = _target_doctypes(doctypes, all_flag)
		counts = {"added": 0, "skipped-existing": 0, "skipped-no-table": 0, "error": 0}
		for dt in targets:
			try:
				result = _add_tenant_field(dt)
				counts[result] += 1
				click.echo(f"  {result:<22} {dt}")
			except Exception as exc:
				counts["error"] += 1
				frappe.db.rollback()
				click.secho(f"  error                  {dt}: {exc}", fg="red")
		click.echo("")
		for key, n in counts.items():
			click.echo(f"{key}: {n}")
	finally:
		frappe.destroy()


@click.command("enable-tenant-rls")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Apply to every DocType that has tenant_id.")
@pass_context
def enable_tenant_rls(context, doctypes: tuple[str, ...], all_flag: bool):
	"""Enable Row Level Security and install the tenant isolation policy."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		targets = _target_doctypes(doctypes, all_flag)
		counts = {"enabled": 0, "skipped-no-column": 0, "error": 0}
		for dt in targets:
			try:
				result = _enable_rls(dt)
				counts[result] += 1
				click.echo(f"  {result:<18} {dt}")
			except Exception as exc:
				counts["error"] += 1
				frappe.db.rollback()
				click.secho(f"  error              {dt}: {exc}", fg="red")
		click.echo("")
		for key, n in counts.items():
			click.echo(f"{key}: {n}")
	finally:
		frappe.destroy()


@click.command("disable-tenant-rls")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Apply to every DocType that has tenant_id.")
@pass_context
def disable_tenant_rls(context, doctypes: tuple[str, ...], all_flag: bool):
	"""Drop the tenant isolation policy and turn RLS off. Emergency use."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		targets = _target_doctypes(doctypes, all_flag)
		for dt in targets:
			try:
				_disable_rls(dt)
				click.echo(f"  disabled  {dt}")
			except Exception as exc:
				frappe.db.rollback()
				click.secho(f"  error     {dt}: {exc}", fg="red")
	finally:
		frappe.destroy()


@click.command("backfill-tenant-id")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Apply to every DocType that has tenant_id.")
@click.option("--tenant", "tenant", required=True, help="Tenant id to assign to existing rows.")
@click.option("--dry-run", is_flag=True, help="Show row counts without writing.")
@pass_context
def backfill_tenant_id(
	context, doctypes: tuple[str, ...], all_flag: bool, tenant: str, dry_run: bool
):
	"""Set ``tenant_id = <tenant>`` on rows where it is NULL or empty."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		targets = _target_doctypes(doctypes, all_flag)
		total = 0
		for dt in targets:
			if not frappe.db.has_column(dt, "tenant_id"):
				click.echo(f"  skip (no column)  {dt}")
				continue
			ident = _table_ident(dt)
			if dry_run:
				count = frappe.db.sql(
					f"SELECT COUNT(*) FROM {ident} WHERE tenant_id IS NULL OR tenant_id = ''"
				)[0][0]
				click.echo(f"  would update  {count:>8}  {dt}")
				total += count
				continue
			frappe.db.sql(
				f"UPDATE {ident} SET tenant_id = %s WHERE tenant_id IS NULL OR tenant_id = ''",
				(tenant,),
			)
			affected = frappe.db.sql("SELECT 1")  # force flush; row count below
			click.echo(f"  backfilled    {dt}")
		frappe.db.commit()
		if dry_run:
			click.echo(f"\ntotal rows that would be updated: {total}")
	finally:
		frappe.destroy()


_BACKUP_TABLE = "_tenant_unique_index_backup"
_PG_IDENT_MAX = 63
_TENANT_SUFFIX = "_tenant"


def _ensure_backup_table() -> None:
	"""Create the backup table and commit immediately so it survives any
	per-DocType ``rollback()`` later in the run. Postgres DDL is
	transactional, so without this commit a single failed DocType wipes
	the table and cascades into ``relation does not exist`` for every
	subsequent DocType."""
	# ``columns`` is JSONB rather than TEXT[] because Frappe's parameter
	# binding renders a Python list as a tuple literal (e.g. ``('name')``),
	# which Postgres parses as a record/composite — not a text array — and
	# the insert fails with ``malformed array literal``. JSON sidesteps that
	# by sending a string we control.
	frappe.db.sql(
		f"""
		CREATE TABLE IF NOT EXISTS {_BACKUP_TABLE} (
			id BIGSERIAL PRIMARY KEY,
			table_name TEXT NOT NULL,
			original_index_name TEXT NOT NULL,
			constraint_name TEXT,
			is_primary BOOLEAN NOT NULL,
			columns JSONB NOT NULL,
			original_definition TEXT NOT NULL,
			new_object_name TEXT NOT NULL,
			created_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)
		"""
	)
	frappe.db.sql(
		f"""CREATE INDEX IF NOT EXISTS {_BACKUP_TABLE}_table_idx
		    ON {_BACKUP_TABLE} (table_name)"""
	)
	# Self-heal an older schema (the first revision used TEXT[] for ``columns``,
	# which Frappe's parameter binding could not populate). If the table is
	# empty we silently upgrade in place; if it has rows we refuse rather than
	# silently discarding operator-visible backup metadata.
	col_type = frappe.db.sql(
		f"""SELECT udt_name FROM information_schema.columns
		    WHERE table_name = '{_BACKUP_TABLE}' AND column_name = 'columns'""",
	)
	if col_type and col_type[0][0] != "jsonb":
		row_count = frappe.db.sql(f"SELECT COUNT(*) FROM {_BACKUP_TABLE}")[0][0]
		if row_count:
			raise click.ClickException(
				f"{_BACKUP_TABLE}.columns is {col_type[0][0]} but holds {row_count} row(s); "
				"manual migration required — convert to JSONB or drop after verifying."
			)
		frappe.db.sql(
			f"ALTER TABLE {_BACKUP_TABLE} ALTER COLUMN columns TYPE JSONB USING '[]'::jsonb"
		)
	frappe.db.commit()


def _suffix_tenant(name: str) -> str:
	"""Append ``_tenant`` to ``name``, truncating to PG's 63-byte identifier
	limit. Idempotent: a name that already ends with the suffix is returned
	unchanged so re-runs do not double-suffix."""
	if name.endswith(_TENANT_SUFFIX):
		return name
	available = _PG_IDENT_MAX - len(_TENANT_SUFFIX)
	base = name if len(name) <= available else name[:available]
	return base + _TENANT_SUFFIX


def _list_unique_indexes(table: str) -> list[dict]:
	"""Return every UNIQUE index on ``table`` together with metadata needed to
	decide whether (and how) to rewrite it. ``columns`` is ordered by index
	column position; system columns (attnum <= 0) are filtered out."""
	return frappe.db.sql(
		"""
		SELECT
			i.indexrelid AS oid,
			c2.relname AS index_name,
			i.indisprimary AS is_primary,
			i.indpred IS NOT NULL AS is_partial,
			(
				SELECT array_agg(a.attname ORDER BY ord)
				FROM unnest(i.indkey::int[]) WITH ORDINALITY AS k(attnum, ord)
				JOIN pg_attribute a
				  ON a.attrelid = c.oid AND a.attnum = k.attnum
				WHERE k.attnum > 0
			) AS columns,
			pg_get_indexdef(i.indexrelid) AS definition,
			(
				SELECT con.conname FROM pg_constraint con
				WHERE con.conindid = i.indexrelid
				LIMIT 1
			) AS constraint_name
		FROM pg_index i
		JOIN pg_class c  ON c.oid  = i.indrelid
		JOIN pg_class c2 ON c2.oid = i.indexrelid
		JOIN pg_namespace n ON n.oid = c.relnamespace
		WHERE c.relname = %s
		  AND n.nspname = current_schema()
		  AND i.indisunique
		""",
		(table,),
		as_dict=True,
	)


def _quote_ident(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def _column_list(cols: list[str]) -> str:
	return ", ".join(_quote_ident(c) for c in cols)


def _load_backup_columns(backup_id: int) -> list[str]:
	"""Read the JSON-encoded column list back out of the backup table.
	Postgres returns JSONB to psycopg2 as already-decoded Python objects, so
	this also tolerates the case where the driver hands back a list directly."""
	row = frappe.db.sql(
		f"SELECT columns FROM {_BACKUP_TABLE} WHERE id = %s",
		(backup_id,),
		as_dict=True,
	)
	if not row:
		return []
	value = row[0]["columns"]
	if isinstance(value, list):
		return list(value)
	if isinstance(value, str):
		return list(json.loads(value))
	return []


def _record_backup(
	table: str,
	idx: dict,
	new_object_name: str,
) -> None:
	frappe.db.sql(
		f"""
		INSERT INTO {_BACKUP_TABLE}
			(table_name, original_index_name, constraint_name, is_primary,
			 columns, original_definition, new_object_name)
		VALUES (%s, %s, %s, %s::boolean, %s::jsonb, %s, %s)
		""",
		(
			table,
			idx["index_name"],
			idx["constraint_name"],
			"true" if idx["is_primary"] else "false",
			json.dumps(list(idx["columns"] or [])),
			idx["definition"],
			new_object_name,
		),
	)


def _rewrite_unique_index(table: str, idx: dict) -> str:
	"""Drop ``idx`` and recreate it with ``tenant_id`` prepended. Returns the
	name of the new index/constraint so it can be reported and stored."""
	cols = list(idx["columns"] or [])
	new_cols = ["tenant_id", *cols]
	col_sql = _column_list(new_cols)
	table_ident = _quote_ident(table)

	if idx["is_primary"]:
		# Recreate as composite PRIMARY KEY. We keep the same constraint name
		# so anything that pins it (rare in Frappe) keeps working.
		pk_name = idx["constraint_name"] or f"{table}_pkey"
		new_name = pk_name  # reuse name; the *shape* is what changed
		_record_backup(table, idx, new_name)
		frappe.db.sql(f'ALTER TABLE {table_ident} DROP CONSTRAINT {_quote_ident(pk_name)}')
		frappe.db.sql(
			f'ALTER TABLE {table_ident} ADD CONSTRAINT {_quote_ident(new_name)} PRIMARY KEY ({col_sql})'
		)
		return new_name

	if idx["constraint_name"]:
		# Constraint-backed UNIQUE — must drop the constraint (which drops the
		# index) and recreate as a constraint so pg_constraint stays in sync.
		old_con = idx["constraint_name"]
		new_name = _suffix_tenant(old_con)
		_record_backup(table, idx, new_name)
		frappe.db.sql(f'ALTER TABLE {table_ident} DROP CONSTRAINT {_quote_ident(old_con)}')
		frappe.db.sql(
			f'ALTER TABLE {table_ident} ADD CONSTRAINT {_quote_ident(new_name)} UNIQUE ({col_sql})'
		)
		return new_name

	# Plain unique index, not constraint-backed.
	old_name = idx["index_name"]
	new_name = _suffix_tenant(old_name)
	_record_backup(table, idx, new_name)
	frappe.db.sql(f'DROP INDEX {_quote_ident(old_name)}')
	frappe.db.sql(
		f'CREATE UNIQUE INDEX {_quote_ident(new_name)} ON {table_ident} ({col_sql})'
	)
	return new_name


def _rewrite_doctype_unique_keys(
	doctype: str, include_primary: bool, dry_run: bool
) -> dict:
	counts = {
		"rewritten": 0,
		"already_tenant_scoped": 0,
		"skipped_partial": 0,
		"skipped_primary": 0,
		"skipped_no_column": 0,
		"skipped_no_table": 0,
	}
	if not frappe.db.table_exists(doctype):
		counts["skipped_no_table"] = 1
		return counts
	if not frappe.db.has_column(doctype, "tenant_id"):
		counts["skipped_no_column"] = 1
		return counts
	table = f"tab{doctype}"
	for idx in _list_unique_indexes(table):
		cols = list(idx["columns"] or [])
		if "tenant_id" in cols:
			counts["already_tenant_scoped"] += 1
			continue
		if idx["is_partial"]:
			# Partial uniques carry a WHERE predicate that may interact with
			# tenant_id semantics in non-obvious ways — surface them instead
			# of silently rewriting.
			counts["skipped_partial"] += 1
			continue
		if idx["is_primary"] and not include_primary:
			counts["skipped_primary"] += 1
			continue
		if dry_run:
			counts["rewritten"] += 1
			continue
		_rewrite_unique_index(table, idx)
		counts["rewritten"] += 1
	return counts


def _revert_doctype_unique_keys(doctype: str, dry_run: bool) -> dict:
	counts = {"reverted": 0, "skipped_no_backup": 0, "error": 0}
	if not frappe.db.table_exists(doctype):
		return counts
	table = f"tab{doctype}"
	rows = frappe.db.sql(
		f"""SELECT id, original_index_name, constraint_name, is_primary,
		           original_definition, new_object_name
		    FROM {_BACKUP_TABLE}
		    WHERE table_name = %s
		    ORDER BY id DESC""",
		(table,),
		as_dict=True,
	)
	if not rows:
		counts["skipped_no_backup"] = 1
		return counts
	table_ident = _table_ident(doctype)
	for r in rows:
		try:
			if dry_run:
				counts["reverted"] += 1
				continue
			# Drop the rewritten object first.
			if r["is_primary"]:
				frappe.db.sql(
					f'ALTER TABLE {table_ident} DROP CONSTRAINT {_quote_ident(r["new_object_name"])}'
				)
			elif r["constraint_name"]:
				frappe.db.sql(
					f'ALTER TABLE {table_ident} DROP CONSTRAINT {_quote_ident(r["new_object_name"])}'
				)
			else:
				frappe.db.sql(f'DROP INDEX IF EXISTS {_quote_ident(r["new_object_name"])}')
			# Re-execute the captured CREATE INDEX / pg_get_indexdef output.
			# For PK and constraint-backed uniques the captured text is the
			# index definition — we still need an ALTER TABLE … ADD CONSTRAINT
			# for those. pg_get_indexdef returns the index DDL even when the
			# index backs a constraint, so we rebuild the constraint by name
			# rather than executing the raw text.
			if r["is_primary"]:
				# Reconstruct PK from backup metadata (columns array).
				cols = _load_backup_columns(r["id"])
				frappe.db.sql(
					f'ALTER TABLE {table_ident} ADD CONSTRAINT {_quote_ident(r["original_index_name"] or table + "_pkey")} '
					f'PRIMARY KEY ({_column_list(cols)})'
				)
			elif r["constraint_name"]:
				cols = _load_backup_columns(r["id"])
				frappe.db.sql(
					f'ALTER TABLE {table_ident} ADD CONSTRAINT {_quote_ident(r["constraint_name"])} '
					f'UNIQUE ({_column_list(cols)})'
				)
			else:
				# Plain unique index — replay the saved CREATE INDEX text.
				frappe.db.sql(r["original_definition"])
			frappe.db.sql(
				f"DELETE FROM {_BACKUP_TABLE} WHERE id = %s",
				(r["id"],),
			)
			counts["reverted"] += 1
		except Exception as exc:
			counts["error"] += 1
			frappe.db.rollback()
			click.secho(f"  error      {doctype} ({r['original_index_name']}): {exc}", fg="red")
	return counts


@click.command("rewrite-tenant-unique-keys")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Apply to every DocType that has tenant_id.")
@click.option(
	"--include-primary/--no-include-primary",
	default=True,
	show_default=True,
	help="Also rewrite the PRIMARY KEY on `name` so two tenants can share a `name` value.",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without altering DDL.")
@pass_context
def rewrite_tenant_unique_keys(
	context, doctypes: tuple[str, ...], all_flag: bool, include_primary: bool, dry_run: bool
):
	"""Rewrite UNIQUE indexes/constraints on tenant-scoped tables to include
	``tenant_id``. Run after ``add-tenant-id`` + ``backfill-tenant-id`` and
	before ``enable-tenant-rls``."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		_ensure_backup_table()
		targets = _target_doctypes(doctypes, all_flag)
		totals = {
			"rewritten": 0,
			"already_tenant_scoped": 0,
			"skipped_partial": 0,
			"skipped_primary": 0,
			"skipped_no_column": 0,
			"skipped_no_table": 0,
			"error": 0,
		}
		for dt in targets:
			try:
				result = _rewrite_doctype_unique_keys(dt, include_primary, dry_run)
				for k, v in result.items():
					totals[k] += v
				if result["rewritten"]:
					click.echo(f"  rewrote {result['rewritten']:>3}  {dt}")
				elif result["already_tenant_scoped"] or result["skipped_partial"]:
					click.echo(
						f"  noop          {dt}  "
						f"(already={result['already_tenant_scoped']}, "
						f"partial={result['skipped_partial']}, "
						f"primary={result['skipped_primary']})"
					)
				# Commit per-DocType so a later failure cannot roll back
				# successful rewrites for earlier DocTypes.
				if not dry_run:
					frappe.db.commit()
			except Exception as exc:
				totals["error"] += 1
				frappe.db.rollback()
				click.secho(f"  error      {dt}: {exc}", fg="red")
				continue
		click.echo("")
		for key, n in totals.items():
			click.echo(f"{key}: {n}")
		if dry_run:
			click.echo("\n(dry-run — no DDL executed)")
	finally:
		frappe.destroy()


@click.command("revert-tenant-unique-keys")
@click.argument("doctypes", nargs=-1)
@click.option("--all", "all_flag", is_flag=True, help="Revert every DocType that has a backup row.")
@click.option("--dry-run", is_flag=True, help="Show what would be reverted without altering DDL.")
@pass_context
def revert_tenant_unique_keys(
	context, doctypes: tuple[str, ...], all_flag: bool, dry_run: bool
):
	"""Reverse a prior ``rewrite-tenant-unique-keys`` run by replaying the
	original index/constraint definitions saved in the backup table.
	Emergency-only — RLS will not protect against cross-tenant value
	collisions once the tenant-scoped uniques are gone."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		_require_postgres()
		_ensure_backup_table()
		if all_flag and not doctypes:
			rows = frappe.db.sql(
				f"SELECT DISTINCT table_name FROM {_BACKUP_TABLE} ORDER BY table_name"
			)
			targets = [r[0][len("tab"):] for r in rows if r[0].startswith("tab")]
		else:
			targets = _target_doctypes(doctypes, all_flag)
		totals = {"reverted": 0, "skipped_no_backup": 0, "error": 0}
		for dt in targets:
			try:
				result = _revert_doctype_unique_keys(dt, dry_run)
				for k, v in result.items():
					totals[k] += v
				if result["reverted"]:
					click.echo(f"  reverted {result['reverted']:>3}  {dt}")
				if not dry_run:
					frappe.db.commit()
			except Exception as exc:
				totals["error"] += 1
				frappe.db.rollback()
				click.secho(f"  error      {dt}: {exc}", fg="red")
				continue
		click.echo("")
		for key, n in totals.items():
			click.echo(f"{key}: {n}")
		if dry_run:
			click.echo("\n(dry-run — no DDL executed)")
	finally:
		frappe.destroy()


commands = [
	add_tenant_id,
	enable_tenant_rls,
	disable_tenant_rls,
	backfill_tenant_id,
	rewrite_tenant_unique_keys,
	revert_tenant_unique_keys,
]
