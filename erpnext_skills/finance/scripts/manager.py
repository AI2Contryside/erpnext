"""
ERPNext 财务管理模块
提供发票、付款、应收账款、应付账款等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class InvoiceManager:
    """发票管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_sales_invoice(self, customer: str, company: str, items: List[Dict],
                           posting_date: Optional[str] = None, **kwargs) -> Dict:
        """创建销售发票"""
        data = {
            "doctype": "Sales Invoice",
            "customer": customer,
            "company": company,
            "posting_date": posting_date or "",
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_purchase_invoice(self, supplier: str, company: str, items: List[Dict],
                               posting_date: Optional[str] = None, **kwargs) -> Dict:
        """创建采购发票"""
        data = {
            "doctype": "Purchase Invoice",
            "supplier": supplier,
            "company": company,
            "posting_date": posting_date or "",
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_invoice_from_sales_order(self, sales_order: str) -> Dict:
        """从销售订单创建发票"""
        return self.client.call_method("Sales Order", sales_order, "make_sales_invoice")

    def create_invoice_from_delivery_note(self, delivery_note: str) -> Dict:
        """从送货单创建发票"""
        return self.client.call_method("Delivery Note", delivery_note, "make_sales_invoice")

    def get_outstanding_invoices(self, doctype: str = "Sales Invoice",
                               customer: Optional[str] = None) -> List[Dict]:
        """获取未结清发票"""
        filters = {
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        }
        if customer:
            filters["customer"] = customer
        return self.client.get_list(doctype, filters=filters)

    def get_customer_outstanding(self, customer: str, company: Optional[str] = None) -> float:
        """获取客户应收账款"""
        filters = {
            "customer": customer,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        }
        if company:
            filters["company"] = company
        invoices = self.client.get_list("Sales Invoice", filters=filters)
        return sum(inv.get("outstanding_amount", 0) for inv in invoices)

    def get_supplier_outstanding(self, supplier: str, company: Optional[str] = None) -> float:
        """获取供应商应付账款"""
        filters = {
            "supplier": supplier,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        }
        if company:
            filters["company"] = company
        invoices = self.client.get_list("Purchase Invoice", filters=filters)
        return sum(inv.get("outstanding_amount", 0) for inv in invoices)


class PaymentManager:
    """付款管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_payment_entry(self, company: str, payment_type: str, amount: float,
                          account_paid: str, account_received: str,
                          party_type: Optional[str] = None, party: Optional[str] = None,
                          **kwargs) -> Dict:
        """创建付款凭证"""
        data = {
            "doctype": "Payment Entry",
            "company": company,
            "payment_type": payment_type,
            "amount": amount,
            "paid_account": account_paid,
            "received_account": account_received,
            "party_type": party_type or "",
            "party": party or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def receive_payment(self, company: str, amount: float, customer: str,
                      account_received: str, paid_account: str, **kwargs) -> Dict:
        """收款"""
        return self.create_payment_entry(
            company, "Receive", amount, account_received, paid_account,
            "Customer", customer, **kwargs
        )

    def make_payment(self, company: str, amount: float, supplier: str,
                    account_paid: str, received_account: str, **kwargs) -> Dict:
        """付款"""
        return self.create_payment_entry(
            company, "Pay", amount, account_paid, received_account,
            "Supplier", supplier, **kwargs
        )

    def create_payment_from_invoice(self, invoice: str, payment_amount: float) -> Dict:
        """从发票创建付款"""
        return self.client.call_method("Sales Invoice", invoice, "make_payment_entry")


class JournalManager:
    """日记账管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_journal_entry(self, company: str, accounts: List[Dict],
                          posting_date: Optional[str] = None, **kwargs) -> Dict:
        """创建日记账"""
        data = {
            "doctype": "Journal Entry",
            "company": company,
            "posting_date": posting_date or "",
            "accounts": accounts
        }
        data.update(kwargs)
        return self.client.insert(data)


class AccountingReport:
    """会计报表"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def get_trial_balance(self, company: str, from_date: str, to_date: str) -> List[Dict]:
        """获取试算平衡表"""
        return self.client.call_method(
            "erpnext.accounts.report.trial_balance.trial_balance.execute_report",
            filters={"company": company, "from_date": from_date, "to_date": to_date}
        )

    def get_balance_sheet(self, company: str, as_on_date: str) -> Dict:
        """获取资产负债表"""
        return self.client.call_method(
            "erpnext.accounts.report.balance_sheet.balance_sheet.execute_report",
            filters={"company": company, "as_on_date": as_on_date}
        )

    def get_profit_and_loss(self, company: str, from_date: str, to_date: str) -> Dict:
        """获取利润表"""
        return self.client.call_method(
            "erpnext.accounts.report.profit_and_loss.profit_and_loss.execute_report",
            filters={"company": company, "from_date": from_date, "to_date": to_date}
        )

    def get_general_ledger(self, account: str, from_date: str, to_date: str) -> List[Dict]:
        """获取总账"""
        filters = {"account": account, "from_date": from_date, "to_date": to_date}
        return self.client.get_list("GL Entry", filters=filters, limit=100)
