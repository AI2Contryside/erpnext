"""
ERPNext 销售管理模块
提供销售订单、报价单、客户等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class SalesManager:
    """销售管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_quotation(self, customer: str, company: str, items: List[Dict],
                        valid_till: Optional[str] = None, **kwargs) -> Dict:
        """
        创建报价单
        """
        data = {
            "doctype": "Quotation",
            "customer": customer,
            "company": company,
            "valid_till": valid_till or "",
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def convert_quotation_to_sales_order(self, quotation: str) -> Dict:
        """将报价单转换为销售订单"""
        return self.client.call_method("Quotation", quotation, "make_sales_order")

    def create_sales_order(self, customer: str, company: str, items: List[Dict],
                          transaction_date: Optional[str] = None, **kwargs) -> Dict:
        """
        创建销售订单
        """
        data = {
            "doctype": "Sales Order",
            "customer": customer,
            "company": company,
            "transaction_date": transaction_date or "",
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_delivery_note_from_sales_order(self, sales_order: str) -> Dict:
        """从销售订单创建送货单"""
        return self.client.call_method("Sales Order", sales_order, "make_delivery_note")

    def create_sales_invoice_from_sales_order(self, sales_order: str) -> Dict:
        """从销售订单创建销售发票"""
        return self.client.call_method("Sales Order", sales_order, "make_sales_invoice")

    def get_pending_sales_orders(self, customer: Optional[str] = None) -> List[Dict]:
        """获取待完成销售订单"""
        filters = {"docstatus": 1, "status": ["not in", ["Completed", "Closed"]]}
        if customer:
            filters["customer"] = customer
        return self.client.get_list("Sales Order", filters=filters)

    def get_sales_order_items(self, sales_order: str) -> List[Dict]:
        """获取销售订单明细"""
        order = self.client.get_doc("Sales Order", sales_order)
        return order.get("items", [])

    def update_sales_order_status(self, sales_order: str, status: str) -> Dict:
        """更新销售订单状态"""
        return self.client.update("Sales Order", sales_order, {"status": status})

    def hold_sales_order(self, sales_order: str, reason: str) -> Dict:
        """暂停销售订单"""
        return self.client.call_method("Sales Order", sales_order, "hold", reason=reason)

    def unhold_sales_order(self, sales_order: str) -> Dict:
        """取消暂停销售订单"""
        return self.client.call_method("Sales Order", sales_order, "unhold")

    def close_sales_order(self, sales_order: str) -> Dict:
        """关闭销售订单"""
        return self.client.call_method("Sales Order", sales_order, "close_sales_order")

    def cancel_sales_order(self, sales_order: str) -> Dict:
        """取消销售订单"""
        return self.client.cancel("Sales Order", sales_order)


class CustomerManager:
    """客户管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_customer(self, customer_name: str, customer_group: str = "All Customer Groups",
                      territory: str = "All Territories", **kwargs) -> Dict:
        """创建客户"""
        data = {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_group": customer_group,
            "territory": territory
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_customer_balance(self, customer: str) -> float:
        """获取客户应收账款余额"""
        invoices = self.client.get_list("Sales Invoice", {
            "customer": customer,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        })
        return sum(inv.get("outstanding_amount", 0) for inv in invoices)

    def get_customer_credit_limit(self, customer: str) -> Dict:
        """获取客户信用额度"""
        return self.client.get_doc("Customer", customer)

    def update_customer_credit_limit(self, customer: str, credit_limit: float,
                                    company: str) -> Dict:
        """更新客户信用额度"""
        return self.client.update("Customer", customer, {
            "credit_limits": [{"company": company, "credit_limit": credit_limit}]
        })

    def get_customer_sales_stats(self, customer: str) -> Dict:
        """获取客户销售统计"""
        orders = self.client.get_list("Sales Order", {
            "customer": customer,
            "docstatus": ["!=", 2]
        })
        total = sum(o.get("grand_total", 0) for o in orders)
        return {
            "total_orders": len(orders),
            "total_amount": total
        }
