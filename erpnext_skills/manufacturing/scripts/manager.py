"""
ERPNext 生产管理模块
提供物料清单、工艺路线、工单等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class BOMManager:
    """物料清单管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_bom(self, item: str, company: str, items: List[Dict],
                  operation_cost: Optional[float] = None, **kwargs) -> Dict:
        """创建物料清单"""
        data = {
            "doctype": "BOM",
            "item": item,
            "company": company,
            "items": items
        }
        if operation_cost:
            data["total_operation_cost"] = operation_cost
        data.update(kwargs)
        return self.client.insert(data)

    def get_active_bom(self, item: str) -> Optional[Dict]:
        """获取物料的激活BOM"""
        boms = self.client.get_list("BOM", {
            "item": item,
            "is_active": 1,
            "is_default": 1
        }, limit=1)
        return boms[0] if boms else None

    def get_bom_components(self, bom: str) -> List[Dict]:
        """获取BOM组件"""
        bom_doc = self.client.get_doc("BOM", bom)
        return bom_doc.get("items", [])

    def get_bom_cost(self, item: str) -> float:
        """获取物料的BOM成本"""
        bom = self.get_active_bom(item)
        if bom:
            bom_doc = self.client.get_doc("BOM", bom["name"])
            return bom_doc.get("total_cost", 0)
        return 0


class WorkOrderManager:
    """工单管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_work_order(self, item: str, company: str, qty: float,
                         bom: Optional[str] = None, **kwargs) -> Dict:
        """创建工单"""
        if not bom:
            from inventory.scripts.manager import ItemManager
            item_mgr = ItemManager(self.client)
            bom_obj = item_mgr.client.get_list("BOM", {
                "item": item,
                "is_active": 1,
                "is_default": 1
            }, limit=1)
            if bom_obj:
                bom = bom_obj[0]["name"]

        data = {
            "doctype": "Work Order",
            "item_code": item,
            "company": company,
            "qty": qty,
            "bom_no": bom or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def start_work_order(self, work_order: str) -> Dict:
        """开始工单"""
        return self.client.call_method("Work Order", work_order, "start_production")

    def complete_work_order(self, work_order: str, qty: float = 0) -> Dict:
        """完成工单"""
        if qty > 0:
            return self.client.call_method("Work Order", work_order, "make_stock_entry",
                                         qty=qty, stock_entry_type="Manufacture")
        return self.client.call_method("Work Order", work_order, "submit")

    def get_pending_work_orders(self, item_code: Optional[str] = None) -> List[Dict]:
        """获取待生产工单"""
        filters = {"docstatus": 1, "status": ["not in", ["Completed", "Closed", "Cancelled"]]}
        if item_code:
            filters["item_code"] = item_code
        return self.client.get_list("Work Order", filters=filters)

    def get_work_order_status(self, work_order: str) -> Dict:
        """获取工单状态"""
        return self.client.get_doc("Work Order", work_order)


class RoutingManager:
    """工艺路线管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_routing(self, name: str, company: str, operations: List[Dict], **kwargs) -> Dict:
        """创建工艺路线"""
        data = {
            "doctype": "Routing",
            "name": name,
            "company": company,
            "operations": operations
        }
        data.update(kwargs)
        return self.client.insert(data)

    def add_operation(self, routing: str, operation: str, time_in_mins: float) -> Dict:
        """添加工序"""
        return self.client.update("Routing", routing, {
            "operations": [{"operation": operation, "time_in_mins": time_in_mins}]
        })


class ProductionPlanManager:
    """生产计划管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_production_plan(self, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建生产计划"""
        data = {
            "doctype": "Production Plan",
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_production_plan_status(self, plan: str) -> Dict:
        """获取生产计划状态"""
        return self.client.get_doc("Production Plan", plan)

    def create_work_orders_from_plan(self, plan: str) -> Dict:
        """从生产计划创建工单"""
        return self.client.call_method("Production Plan", plan, "make_work_order")


class JobCardManager:
    """工序卡管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def get_job_cards(self, work_order: str) -> List[Dict]:
        """获取工单的工序卡"""
        return self.client.get_list("Job Card", {"work_order": work_order})

    def start_job_card(self, job_card: str) -> Dict:
        """开始工序卡"""
        return self.client.call_method("Job Card", job_card, "start_job")

    def complete_job_card(self, job_card: str, time_in_mins: float) -> Dict:
        """完成工序卡"""
        return self.client.call_method("Job Card", job_card, "complete_job", time_in_mins=time_in_mins)
