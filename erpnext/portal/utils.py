import frappe
import os


def get_all_doctypes():
    """Get all DocTypes that need tenant_id field."""
    core_tables = [
        "DocType", "DocField", "DocPerm", "Custom Field", "Custom Script",
        "User", "Role", "Role Profile", "Page", "Report", "Print Format",
        "Workflow", "Workflow State", "Workflow Action", "Email Template",
        "Email Account", "Communication", "File", "Version", "Error Log",
        "Scheduled Job Log", "Transaction Log", "Session Default", "DefaultValue",
        "Custom DocPerm", "Module Def", "Package", "Application Export",
        "Data Import", "Data Import Legacy", "Batch", "Serial No",
        "Item Attribute", "Item Attribute Value", "Item Tax Template",
        "Item Tax", "Price List", "Price List Country", "Item Price",
        "UOM", "UOM Conversion Factor", "Brand", "Item Group",
        "Customer Group", "Supplier Group", "Territory", "Department",
        "Warehouse Type", "Warehouse", "Stock Level", "Inventory Dimension",
        "Inventory Dimension Detail", "Bin", "Stock Reconciliation Item",
        "Stock Ledger Entry", "GL Entry", "Payment Ledger Entry",
        "Advance Payment Ledger Entry", "Account", "Account Currency",
        "Budget", "Cost Center", "Company", "Fiscal Year", "Fiscal Year Company",
        "Period Closing Voucher", "Payment Term", "Payment Terms Template",
        "Customer Credit Limit", "Supplier Credit Limit", "Sales Partner",
        "Sales Person", "Territory", "Tax Category", "Tax Rule",
    ]

    all_doctypes = frappe.get_all("DocType", pluck="name")

    return [dt for dt in all_doctypes if dt not in core_tables]


def add_tenant_id_field(doctype):
    """Add tenant_id field to a DocType if it doesn't exist."""
    if frappe.db.has_column(doctype, "tenant_id"):
        return False

    try:
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": doctype,
            "fieldname": "tenant_id",
            "fieldtype": "Data",
            "label": "Tenant ID",
            "hidden": 1,
            "allow_on_submit": 0,
            "report_hide": 1,
            "reqd": 0,
            "unique": 0,
            "search_index": 0,
            "show_in_global_search": 0,
            "allow_in_quick_entry": 0,
        })
        custom_field.insert(ignore_permissions=True)
        frappe.db.commit()

        add_rls_policy(doctype)
        return True
    except Exception:
        frappe.db.rollback()
        return False


def add_rls_policy(doctype):
    """Add Row Level Security policy for a table."""
    if frappe.db.db_type != "postgres":
        return

    table_name = frappe.db.escape(f"tab{doctype}")

    try:
        frappe.db.sql(f"""
            DROP POLICY IF EXISTS tenant_isolation_{doctype} ON {table_name}
        """)

        frappe.db.sql(f"""
            CREATE POLICY tenant_isolation_{doctype}
            ON {table_name}
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true))
        """)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()


def setup_tenant_rls(doc, method):
    """Setup tenant_id field and RLS policy for new DocType.
    Called via doc_events when a new DocType is created.
    """
    if frappe.db.db_type != "postgres":
        return

    if doc.is_virtual:
        return

    try:
        add_tenant_id_field(doc.name)
    except Exception:
        pass


def enable_rls_for_all_tables():
    """Enable RLS and create policies for all tables with tenant_id."""
    doctypes = get_all_doctypes()

    for doctype in doctypes:
        if frappe.db.has_column(doctype, "tenant_id"):
            add_rls_policy(doctype)


def add_tenant_id_to_all_tables():
    """Add tenant_id field and RLS policy to all DocTypes."""
    doctypes = get_all_doctypes()
    added = []
    failed = []

    for doctype in doctypes:
        try:
            if add_tenant_id_field(doctype):
                added.append(doctype)
        except Exception:
            failed.append(doctype)

    return {
        "added": added,
        "failed": failed,
        "total": len(doctypes)
    }


def get_tenant_id():
    """Get tenant_id from HTTP header."""
    try:
        return frappe.local.request_headers.get("X-Tenant-ID")
    except Exception:
        return None


def set_tenant_id():
    """Set PostgreSQL tenant_id for RLS (Row Level Security) based on company field.
    Called on_session_creation hook to enable multi-tenant data isolation.
    Uses ERPNext's company field for tenant isolation.
    """
    tenant_id = get_tenant_id()

    if not tenant_id:
        return

    try:
        if hasattr(frappe, 'db') and frappe.db:
            with frappe.db.cursor() as cursor:
                cursor.execute(f"SET app.tenant_id = '{tenant_id}'")
    except Exception:
        pass


@frappe.whitelist()
def set_tenant_id_api(tenant_id):
    """API endpoint to set tenant_id for current session.
    Usage:
        frappe.call({
            method: 'erpnext.portal.utils.set_tenant_id_api',
            args: { tenant_id: 'your_tenant_id' }
        })
    Or via REST API:
        POST /api/method/erpnext.portal.utils.set_tenant_id_api
        Headers: X-Tenant-ID: your_tenant_id
    """
    if not tenant_id:
        return {"success": False, "message": "tenant_id is required"}

    try:
        if hasattr(frappe, 'db') and frappe.db:
            with frappe.db.cursor() as cursor:
                cursor.execute(f"SET app.tenant_id = '{tenant_id}'")
        return {"success": True, "tenant_id": tenant_id}
    except Exception as e:
        return {"success": False, "message": str(e)}


def auto_set_tenant_id(doc, method):
    """Auto set tenant_id field on document validate.
    Called via doc_events to automatically populate tenant_id field.
    """
    tenant_id = get_tenant_id()

    if not tenant_id:
        return

    if hasattr(doc, "tenant_id"):
        if not doc.tenant_id:
            doc.tenant_id = tenant_id


def set_default_role(doc, method):
	"""Set customer, supplier, student, guardian based on email"""
	if frappe.flags.setting_role or frappe.flags.in_migrate:
		return

	roles = frappe.get_roles(doc.name)

	contact_name = frappe.get_value("Contact", dict(email_id=doc.email))
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			frappe.flags.setting_role = True
			if link.link_doctype == "Customer" and "Customer" not in roles:
				doc.add_roles("Customer")
			elif link.link_doctype == "Supplier" and "Supplier" not in roles:
				doc.add_roles("Supplier")


def create_customer_or_supplier():
	"""Based on the default Role (Customer, Supplier), create a Customer / Supplier.
	Called on_session_creation hook.
	"""
	user = frappe.session.user

	if frappe.db.get_value("User", user, "user_type") != "Website User":
		return

	user_roles = frappe.get_roles()
	portal_settings = frappe.get_single("Portal Settings")
	default_role = portal_settings.default_role

	if default_role not in ["Customer", "Supplier"]:
		return

	# create customer / supplier if the user has that role
	if portal_settings.default_role and portal_settings.default_role in user_roles:
		doctype = portal_settings.default_role
	else:
		doctype = None

	if not doctype:
		return

	if party_exists(doctype, user):
		return

	party = frappe.new_doc(doctype)
	fullname = frappe.utils.get_fullname(user)

	if doctype != "Customer":
		party.update(
			{
				"supplier_name": fullname,
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Individual",
			}
		)

	party.flags.ignore_mandatory = True
	party.insert(ignore_permissions=True)

	alternate_doctype = "Customer" if doctype == "Supplier" else "Supplier"

	if party_exists(alternate_doctype, user):
		# if user is both customer and supplier, alter fullname to avoid contact name duplication
		fullname += "-" + doctype

	create_party_contact(doctype, fullname, user, party.name)

	return party


def create_party_contact(doctype, fullname, user, party_name):
	contact = frappe.new_doc("Contact")
	contact.update({"first_name": fullname, "email_id": user})
	contact.append("links", dict(link_doctype=doctype, link_name=party_name))
	contact.append("email_ids", dict(email_id=user, is_primary=True))
	contact.flags.ignore_mandatory = True
	contact.insert(ignore_permissions=True)


def party_exists(doctype, user):
	# check if contact exists against party and if it is linked to the doctype
	contact_name = frappe.db.get_value("Contact", {"email_id": user})
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		doctypes = [d.link_doctype for d in contact.links]
		return doctype in doctypes

	return False
