#!/usr/bin/env python3
"""
ERPNext 功能覆盖度分析脚本
对比 ERPNext DocType 和 Skill 中实现的功能
"""

import os
import json

ERP_NEXT_DOCTYPES = {
    "销售": [
        "Quotation", "Sales Order", "Sales Invoice", "Delivery Note",
        "Customer", "Customer Group", "Customer Credit Limit",
        "Sales Partner", "Sales Person", "Sales Team",
        "Installation Note", "Product Bundle", "Quotation Lost Reason"
    ],
    "采购": [
        "Supplier", "Supplier Group", "Purchase Order", "Purchase Invoice",
        "Purchase Receipt", "Supplier Quotation", "Request for Quotation",
        "Material Request", "Supplier Scorecard"
    ],
    "库存": [
        "Item", "Item Group", "Item Price", "Item Tax",
        "Warehouse", "Bin", "Stock Entry", "Stock Reconciliation",
        "Stock Ledger Entry", "Delivery Note", "Purchase Receipt",
        "Pick List", "Shipment", "Material Request",
        "Batch", "Serial No", "Quality Inspection",
        "Landed Cost Voucher", "Putaway Rule", "Stock Reservation Entry"
    ],
    "财务": [
        "Payment Entry", "Journal Entry", "Payment Ledger Entry",
        "GL Entry", "Account", "Cost Center", "Budget",
        "Fiscal Year", "Payment Term", "Payment Terms Template",
        "Tax Rule", "Tax Category", "Currency", "Exchange Rate"
    ],
    "生产": [
        "BOM", "Work Order", "Job Card", "Routing",
        "Operation", "Workstation", "Production Plan",
        "Subcontracting Order", "Subcontracting Receipt",
        "Job Card Time Log", "BOM Operation", "BOM Item"
    ],
    "资产": [
        "Asset", "Asset Category", "Asset Movement",
        "Asset Depreciation Schedule", "Asset Capitalization",
        "Asset Repair", "Asset Maintenance", "Asset Value Adjustment"
    ],
    "项目": [
        "Project", "Task", "Timesheet", "Activity Cost",
        "Grant", "Campaign", "Lead", "Opportunity",
        "Contract"
    ],
    "HR": [
        "Employee", "Department", "Branch", "Designation",
        "Employee Grade", "Holiday List", "Leave Application",
        "Attendance", "Payroll", "Salary Slip"
    ],
    "支持": [
        "Issue", "Warranty Claim", "Maintenance Visit",
        "Maintenance Schedule", "Service Level Agreement"
    ],
    "系统": [
        "User", "Role", "Role Profile", "DocType",
        "Custom Field", "Custom Script", "Print Format",
        "Workflow", "Email Template", "Notification",
        "System Settings", "Website Settings"
    ]
}

SKILL_COVERAGE = {
    "销售": {
        "Quotation": ["create_quotation", "convert_quotation_to_sales_order"],
        "Sales Order": ["create_sales_order", "create_delivery_note_from_sales_order",
                        "create_sales_invoice_from_sales_order", "get_pending_sales_orders",
                        "hold_sales_order", "unhold_sales_order", "close_sales_order"],
        "Customer": ["create_customer", "get_customer_balance", "get_customer_credit_limit",
                    "update_customer_credit_limit", "get_customer_sales_stats"]
    },
    "采购": {
        "Supplier": ["create_supplier", "get_supplier_balance", "get_supplier_purchase_stats"],
        "Supplier Quotation": ["create_supplier_quotation"],
        "Request for Quotation": ["create_request_for_quotation"],
        "Purchase Order": ["create_purchase_order", "create_purchase_invoice_from_po",
                         "create_purchase_receipt_from_po", "get_pending_purchase_orders",
                         "receive_purchase_order"],
        "Material Request": ["create_material_request"],
        "Supplier Scorecard": ["make_supplier_scorecard"]
    },
    "库存": {
        "Bin": ["get_item_stock", "get_warehouse_items"],
        "Stock Entry": ["create_stock_entry", "material_receipt", "material_issue", "material_transfer"],
        "Stock Reconciliation": ["create_stock_reconciliation"],
        "Stock Ledger Entry": ["get_stock_ledger"],
        "Delivery Note": ["create_delivery_note"],
        "Purchase Receipt": ["create_purchase_receipt"],
        "Warehouse": ["get_warehouses", "create_warehouse"],
        "Item": ["create_item", "get_item_price", "set_item_price", "disable_item", "enable_item"]
    },
    "财务": {
        "Sales Invoice": ["create_sales_invoice", "get_outstanding_invoices", "get_customer_outstanding"],
        "Purchase Invoice": ["create_purchase_invoice", "get_supplier_outstanding"],
        "Payment Entry": ["create_payment_entry", "receive_payment", "make_payment"],
        "Journal Entry": ["create_journal_entry"]
    },
    "生产": {
        "BOM": ["create_bom", "get_active_bom", "get_bom_components", "get_bom_cost"],
        "Work Order": ["create_work_order", "start_work_order", "complete_work_order",
                      "get_pending_work_orders", "get_work_order_status"],
        "Routing": ["create_routing", "add_operation"],
        "Production Plan": ["create_production_plan", "get_production_plan_status",
                           "create_work_orders_from_plan"],
        "Job Card": ["get_job_cards", "start_job_card", "complete_job_card"]
    },
    "资产": {
        "Asset": ["create_asset", "create_asset_from_purchase", "get_assets",
                 "get_asset_value", "calculate_depreciation", "post_depreciation",
                 "transfer_asset", "scrap_asset", "sell_asset"],
        "Asset Category": ["create_asset_category"],
        "Maintenance Schedule": ["create_maintenance_schedule", "get_pending_maintenance"],
        "Maintenance Visit": ["create_maintenance_visit"],
        "Asset Value Adjustment": ["create_value_adjustment"],
        "Asset Capitalization": ["create_capitalization"]
    },
    "项目": {
        "Lead": ["create_lead", "convert_lead_to_customer", "convert_lead_to_opportunity"],
        "Opportunity": ["create_opportunity", "create_quotation_from_opportunity"],
        "Project": ["create_project", "get_project_tasks", "create_task",
                   "create_timesheet", "get_project_status"],
        "Task": ["create_task"],
        "Timesheet": ["create_timesheet"],
        "Contract": ["create_contract"]
    },
    "HR": {
        "Employee": ["create_employee", "get_employees"],
        "Department": ["create_department"],
        "Leave Application": ["create_leave_application", "get_leave_balance"],
        "Attendance": ["mark_attendance", "get_attendance_records"],
        "Salary Slip": ["create_salary_slip"]
    },
    "支持": {
        "Issue": ["create_issue", "get_issues", "close_issue"],
        "Warranty Claim": ["create_warranty_claim", "get_warranty_claims"],
        "Maintenance Schedule": ["create_maintenance_schedule"],
        "Maintenance Visit": ["create_maintenance_visit"],
        "Service Level Agreement": ["create_service_level_agreement"]
    }
}


def analyze_coverage():
    """分析功能覆盖度"""

    results = {}

    for module, doctypes in ERP_NEXT_DOCTYPES.items():
        covered = []
        not_covered = []

        for doctype in doctypes:
            if module in SKILL_COVERAGE and doctype in SKILL_COVERAGE[module]:
                covered.append(doctype)
            else:
                not_covered.append(doctype)

        results[module] = {
            "covered": covered,
            "not_covered": not_covered,
            "total": len(doctypes),
            "covered_count": len(covered),
            "coverage_rate": f"{len(covered) / len(doctypes) * 100:.1f}%"
        }

    return results


def print_report():
    """打印覆盖度报告"""

    results = analyze_coverage()

    print("=" * 60)
    print("ERPNext Skill 功能覆盖度报告")
    print("=" * 60)

    total_covered = 0
    total_not_covered = 0

    for module, data in results.items():
        print(f"\n【{module}】")
        print(f"  覆盖率: {data['coverage_rate']} ({data['covered_count']}/{data['total']})")

        if data["covered"]:
            print(f"  ✅ 已实现: {', '.join(data['covered'])}")

        if data["not_covered"]:
            print(f"  ❌ 未实现: {', '.join(data['not_covered'])}")

        total_covered += data["covered_count"]
        total_not_covered += len(data["not_covered"])

    print("\n" + "=" * 60)
    print(f"总计: {total_covered}/{total_covered + total_not_covered} "
          f"({total_covered / (total_covered + total_not_covered) * 100:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    print_report()
