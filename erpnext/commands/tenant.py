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

3. ``bench --site <site> enable-tenant-rls --all``
      Enables Row Level Security and creates the isolation policy on every
      table that has a ``tenant_id`` column. After this point, any query
      that runs without ``app.current_tenant`` set sees zero rows from
      tenant-scoped tables — including background jobs. Be prepared.

4. ``bench --site <site> disable-tenant-rls --all`` (emergency only).
"""

from __future__ import annotations

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


commands = [add_tenant_id, enable_tenant_rls, disable_tenant_rls, backfill_tenant_id]
