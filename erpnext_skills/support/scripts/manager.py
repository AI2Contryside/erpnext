"""
ERPNext 服务支持管理模块
提供工单、服务水平协议等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class IssueManager:
    """问题/工单管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_issue(self, subject: str, customer: Optional[str] = None,
                   priority: str = "Medium", **kwargs) -> Dict:
        """创建问题/工单"""
        data = {
            "doctype": "Issue",
            "subject": subject,
            "customer": customer or "",
            "priority": priority
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_issues(self, status: Optional[str] = None, customer: Optional[str] = None) -> List[Dict]:
        """获取问题列表"""
        filters = {}
        if status:
            filters["status"] = status
        if customer:
            filters["customer"] = customer
        return self.client.get_list("Issue", filters=filters)

    def close_issue(self, issue: str) -> Dict:
        """关闭问题"""
        return self.client.call_method("Issue", issue, "close")


class WarrantyClaimManager:
    """保修索赔管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_warranty_claim(self, customer: str, asset: str,
                            complaint: str, **kwargs) -> Dict:
        """创建保修索赔"""
        data = {
            "doctype": "Warranty Claim",
            "customer": customer,
            "asset": asset,
            "complaint": complaint
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_warranty_claims(self, customer: Optional[str] = None) -> List[Dict]:
        """获取保修索赔列表"""
        filters = {}
        if customer:
            filters["customer"] = customer
        return self.client.get_list("Warranty Claim", filters=filters)


class MaintenanceManager:
    """维护管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_maintenance_schedule(self, customer: str, item_code: str,
                                 maintenance_type: str, periodicity: str,
                                 start_date: str, **kwargs) -> Dict:
        """创建维护计划"""
        data = {
            "doctype": "Maintenance Schedule",
            "customer": customer,
            "item_code": item_code,
            "maintenance_type": maintenance_type,
            "periodicity": periodicity,
            "start_date": start_date
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_maintenance_visit(self, customer: str, maintenance_type: str, **kwargs) -> Dict:
        """创建维护访问"""
        data = {
            "doctype": "Maintenance Visit",
            "customer": customer,
            "maintenance_type": maintenance_type
        }
        data.update(kwargs)
        return self.client.insert(data)


class ServiceLevelManager:
    """服务水平协议管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_service_level_agreement(self, customer: str, service_level: str, **kwargs) -> Dict:
        """创建服务水平协议"""
        data = {
            "doctype": "Service Level Agreement",
            "customer": customer,
            "service_level": service_level
        }
        data.update(kwargs)
        return self.client.insert(data)
