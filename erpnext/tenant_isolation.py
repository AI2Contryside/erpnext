"""Multi-tenant row-level-security support for ERPNext (PostgreSQL only).

Design
------
* Every tenant-scoped table carries a ``tenant_id`` column (added offline via
  ``bench add-tenant-id``; not at runtime).
* PostgreSQL Row-Level Security policies restrict queries to rows where
  ``tenant_id = current_setting('app.current_tenant')``. Policies are applied
  offline via ``bench enable-tenant-rls``.
* At the start of every HTTP request, :func:`apply_tenant_context` reads the
  trusted ``X-Tenant-ID`` header forwarded by the upstream gateway and sets
  the ``app.current_tenant`` session variable. We use session scope (not
  ``SET LOCAL``) so the value survives across the nested transactions that
  Frappe opens during a single request; we also re-set on every request so
  pooled connections cannot leak tenant state between users.
* :func:`stamp_tenant_on_insert` is wired via ``doc_events["*"]["before_insert"]``
  so new rows always receive the current session tenant; this keeps RLS
  ``WITH CHECK`` clauses satisfied without callers having to remember.
* :func:`stamp_tenant_on_bulk_insert` covers the same ground for
  ``frappe.db.bulk_insert`` (and, transitively, ``frappe.model.document.bulk_insert``
  which delegates to it). Frappe's bulk path deliberately bypasses ``doc_events``
  for speed, so the ``before_insert`` hook never fires there; the wrapper is
  installed at module import time via :func:`_install_bulk_insert_hook` so the
  fast path stamps ``tenant_id`` the same way the slow path does.

Trust model
-----------
``X-Tenant-ID`` is produced by the Go gateway from the authenticated JWT and
re-emitted by DeerFlow. ERPNext is never reachable directly from untrusted
clients — all ingress is via those services, which are treated as the
authorization boundary. The optional membership check (enabled by setting
``tenant_isolation.verify_membership`` to ``True`` in site config) provides
defense in depth once the ``Tenant Membership`` DocType lands.
"""

from __future__ import annotations

from typing import Any, Optional

import frappe
from frappe import _

TENANT_HEADER = "X-Tenant-ID"
SESSION_VAR = "app.current_tenant"


def _is_postgres() -> bool:
	return frappe.db is not None and getattr(frappe.db, "db_type", None) == "postgres"


def _read_header_tenant() -> Optional[str]:
	"""Return the X-Tenant-ID header value, or None if the request is
	non-HTTP (e.g. bench command, background job, migration)."""
	# frappe.request is None outside request context. Accessing
	# frappe.get_request_header() without a request raises.
	if getattr(frappe, "request", None) is None:
		return None
	value = frappe.get_request_header(TENANT_HEADER)
	if not value:
		return None
	return value.strip() or None


def _verify_membership_enabled() -> bool:
	return bool(frappe.local.conf.get("tenant_isolation_verify_membership"))


def _assert_tenant_membership(tenant_id: str) -> None:
	"""Optional defense-in-depth check. Disabled until the Tenant Membership
	DocType is introduced; enable by setting
	``tenant_isolation_verify_membership: 1`` in ``site_config.json``."""
	if not _verify_membership_enabled():
		return
	user = frappe.session.user if getattr(frappe, "session", None) else None
	if not user or user == "Guest":
		frappe.throw(_("Tenant access denied for unauthenticated session"), frappe.AuthenticationError)
	# Membership lookup uses a non-tenant-scoped table so it is not subject
	# to RLS. The table is created by the tenant-isolation bench command;
	# if it does not exist yet, treat as a configuration error rather than
	# silently accepting.
	allowed = frappe.db.sql(
		"""SELECT 1 FROM "tabTenant Membership"
		   WHERE user = %s AND tenant_id = %s AND disabled = 0
		   LIMIT 1""",
		(user, tenant_id),
	)
	if not allowed:
		frappe.throw(
			_("User {0} is not a member of tenant {1}").format(user, tenant_id),
			frappe.PermissionError,
		)


def _set_session_tenant(tenant_id: str) -> None:
	"""Set ``app.current_tenant`` at SESSION scope using a parameterized
	query. ``set_config(name, value, false)`` is the function form of
	``SET SESSION`` and — unlike ``SET`` — accepts bound parameters, so the
	tenant id cannot be SQL-injected even when it originates from an HTTP
	header."""
	frappe.db.sql("SELECT set_config(%s, %s, false)", (SESSION_VAR, tenant_id))


def current_session_tenant() -> Optional[str]:
	"""Return the tenant id currently active on this PG connection, or
	None if unset. Prefer this over re-reading the header so callers stay
	consistent with what RLS will actually see."""
	if not _is_postgres():
		return None
	row = frappe.db.sql("SELECT current_setting(%s, true)", (SESSION_VAR,))
	if not row:
		return None
	value = row[0][0]
	return value or None


def apply_tenant_context() -> None:
	"""Frappe ``before_request`` hook. Re-establishes the tenant session
	variable on every request so a pooled PG connection cannot leak state
	between requests. Missing header resolves to an empty tenant, which
	causes RLS to filter every tenant-scoped table to zero rows — the safe
	default."""
	if not _is_postgres():
		return
	tenant_id = _read_header_tenant() or ""
	if tenant_id:
		_assert_tenant_membership(tenant_id)
	_set_session_tenant(tenant_id)


def stamp_tenant_on_insert(doc: Any, method: Optional[str] = None) -> None:
	"""Frappe ``doc_events["*"]["before_insert"]`` hook. Populates
	``tenant_id`` on new docs that carry the column so the RLS ``WITH CHECK``
	policy admits the row. Explicit incoming values are permitted only when
	they match the session tenant; mismatched values are rejected rather
	than silently overwritten."""
	if not hasattr(doc, "tenant_id"):
		return
	session_tenant = current_session_tenant()
	if not session_tenant:
		# No tenant context — let RLS reject the insert instead of stamping
		# a blank value that would silently pass.
		return
	incoming = getattr(doc, "tenant_id", None)
	if incoming and incoming != session_tenant:
		frappe.throw(
			_("Cannot insert document with tenant_id {0} under session tenant {1}").format(
				incoming, session_tenant
			),
			frappe.PermissionError,
		)
	doc.tenant_id = session_tenant


def stamp_tenant_on_bulk_insert(
	doctype: str,
	fields: list[str],
	values: Any,
) -> tuple[list[str], Any]:
	"""Counterpart to :func:`stamp_tenant_on_insert` for the
	``frappe.db.bulk_insert`` fast path. The bulk path deliberately bypasses
	``doc_events`` for speed, so the ``before_insert`` hook never fires there;
	without this, every caller would have to remember to populate
	``tenant_id`` on each row, which is exactly the fragile pattern the
	doc-event hook was designed to prevent.

	Returns the (possibly-rewritten) ``(fields, values)`` to forward to the
	original ``bulk_insert``. ``values`` is wrapped lazily so generators are
	not materialised. No-ops outside Postgres or when no tenant context is
	set on the session — both cases preserve the original arguments
	unchanged so non-tenant callers (migrations, bench commands) are
	unaffected.
	"""
	if not _is_postgres():
		return fields, values

	session_tenant = current_session_tenant()
	if not session_tenant:
		# Mirrors the no-op branch in stamp_tenant_on_insert: when there is
		# no tenant on the session, leave the rows alone and let RLS reject
		# them rather than silently stamping a blank value.
		return fields, values

	# Use raw column existence rather than DocField meta. The offline
	# ``bench add-tenant-id`` adds a Custom Field whose meta lookup itself
	# touches tenant-scoped tables (tabCustomField); ``has_column`` reads
	# information_schema and is safe regardless of the current tenant.
	try:
		if not frappe.db.has_column(doctype, "tenant_id"):
			return fields, values
	except Exception:
		# DocType not yet migrated, or transient DB error — fall through
		# to the original call so the caller sees the real error rather
		# than a confusing one from our wrapper.
		return fields, values

	fields = list(fields)
	if "tenant_id" in fields:
		idx = fields.index("tenant_id")

		def _stamped_existing() -> Any:
			for row in values:
				row = list(row)
				incoming = row[idx]
				if not incoming:
					row[idx] = session_tenant
				elif incoming != session_tenant:
					frappe.throw(
						_("Cannot bulk_insert row with tenant_id {0} under session tenant {1}").format(
							incoming, session_tenant
						),
						frappe.PermissionError,
					)
				yield tuple(row)

		return fields, _stamped_existing()

	fields.append("tenant_id")

	def _stamped_appended() -> Any:
		for row in values:
			yield tuple(list(row) + [session_tenant])

	return fields, _stamped_appended()


def _install_bulk_insert_hook() -> None:
	"""Wrap :meth:`frappe.database.database.Database.bulk_insert` once at
	module import time so the fast path stamps ``tenant_id`` the same way
	``doc_events`` does on the slow path. Idempotent — safe across reloads
	and against repeated imports.

	``frappe.model.document.bulk_insert`` ultimately delegates to
	``frappe.db.bulk_insert`` (see ``frappe/model/document.py`` —
	``frappe.db.bulk_insert(dt, valid_column_map[dt], docs, ...)``), so a
	single wrapper at the database level covers both public APIs without
	having to monkey-patch two functions in lock-step.
	"""
	from frappe.database.database import Database

	original = Database.bulk_insert
	if getattr(original, "_tenant_isolation_wrapped", False):
		return

	def _wrapped(self, doctype, fields, values, ignore_duplicates=False, *, chunk_size=1000):
		new_fields, new_values = stamp_tenant_on_bulk_insert(doctype, fields, values)
		return original(
			self,
			doctype,
			new_fields,
			new_values,
			ignore_duplicates=ignore_duplicates,
			chunk_size=chunk_size,
		)

	_wrapped._tenant_isolation_wrapped = True  # type: ignore[attr-defined]
	Database.bulk_insert = _wrapped


# Install on import. The module is loaded the first time the
# ``before_request`` hook fires (or any other code references it), which
# happens before any tenant-scoped bulk_insert can run inside an HTTP
# request lifecycle.
_install_bulk_insert_hook()
