"""
ERPNext 采购管理模块
提供供应商、采购订单、采购发票等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class SupplierManager:
    """供应商管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_supplier(self, supplier_name: str, supplier_group: str = "All Supplier Groups",
                      country: Optional[str] = None, **kwargs) -> Dict:
        """创建供应商"""
        data = {
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_group": supplier_group,
            "country": country or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_supplier_balance(self, supplier: str) -> float:
        """获取供应商应付账款"""
        invoices = self.client.get_list("Purchase Invoice", {
            "supplier": supplier,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        })
        return sum(inv.get("outstanding_amount", 0) for inv in invoices)

    def get_supplier_purchase_stats(self, supplier: str) -> Dict:
        """获取供应商采购统计"""
        orders = self.client.get_list("Purchase Order", {
            "supplier": supplier,
            "docstatus": ["!=", 2]
        })
        total = sum(o.get("grand_total", 0) for o in orders)
        return {"total_orders": len(orders), "total_amount": total}


class PurchaseManager:
    """采购管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_supplier_quotation(self, supplier: str, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建供应商报价"""
        data = {
            "doctype": "Supplier Quotation",
            "supplier": supplier,
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_request_for_quotation(self, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建询价单"""
        data = {
            "doctype": "Request for Quotation",
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_purchase_order(self, supplier: str, company: str, items: List[Dict],
                            transaction_date: Optional[str] = None, **kwargs) -> Dict:
        """创建采购订单"""
        data = {
            "doctype": "Purchase Order",
            "supplier": supplier,
            "company": company,
            "transaction_date": transaction_date or "",
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_purchase_invoice_from_po(self, purchase_order: str) -> Dict:
        """从采购订单创建发票"""
        return self.client.call_method("Purchase Order", purchase_order, "make_purchase_invoice")

    def create_purchase_receipt_from_po(self, purchase_order: str) -> Dict:
        """从采购订单创建收货单"""
        return self.client.call_method("Purchase Order", purchase_order, "make_purchase_receipt")

    def get_pending_purchase_orders(self, supplier: Optional[str] = None) -> List[Dict]:
        """获取待完成采购订单"""
        filters = {"docstatus": 1, "status": ["not in", ["Completed", "Closed"]]}
        if supplier:
            filters["supplier"] = supplier
        return self.client.get_list("Purchase Order", filters=filters)

    def receive_purchase_order(self, purchase_order: str) -> Dict:
        """采购订单收货"""
        return self.client.call_method("Purchase Order", purchase_order, "make_purchase_receipt")

    def create_material_request(self, company: str, items: List[Dict],
                              material_request_type: str = "Purchase", **kwargs) -> Dict:
        """创建物料需求"""
        data = {
            "doctype": "Material Request",
            "company": company,
            "material_request_type": material_request_type,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def make_supplier_scorecard(self, supplier: str, company: str, **kwargs) -> Dict:
        """创建供应商评分卡"""
        data = {
            "doctype": "Supplier Scorecard",
            "supplier": supplier,
            "company": company
        }
        data.update(kwargs)
        return self.client.insert(data)
