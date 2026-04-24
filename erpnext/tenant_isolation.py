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
