"""
ERPNext 项目与CRM管理模块
提供线索、机会、项目等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class LeadManager:
    """线索管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_lead(self, lead_name: str, company_name: Optional[str] = None,
                  territory: Optional[str] = None, **kwargs) -> Dict:
        """创建线索"""
        data = {
            "doctype": "Lead",
            "lead_name": lead_name,
            "company_name": company_name or "",
            "territory": territory or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def convert_lead_to_customer(self, lead: str) -> Dict:
        """将线索转换为客户"""
        return self.client.call_method("Lead", lead, "make_customer")

    def convert_lead_to_opportunity(self, lead: str) -> Dict:
        """将线索转换为机会"""
        return self.client.call_method("Lead", lead, "make_opportunity")


class OpportunityManager:
    """机会管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_opportunity(self, customer: str, opportunity_from: str,
                          title: str, currency: str = "CNY", **kwargs) -> Dict:
        """创建销售机会"""
        data = {
            "doctype": "Opportunity",
            "customer": customer,
            "opportunity_from": opportunity_from,
            "title": title,
            "currency": currency
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_quotation_from_opportunity(self, opportunity: str) -> Dict:
        """从机会创建报价单"""
        return self.client.call_method("Opportunity", opportunity, "make_quotation")


class ProjectManager:
    """项目管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_project(self, project_name: str, company: str,
                      start_date: Optional[str] = None, **kwargs) -> Dict:
        """创建项目"""
        data = {
            "doctype": "Project",
            "project_name": project_name,
            "company": company,
            "start_date": start_date or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_project_tasks(self, project: str) -> List[Dict]:
        """获取项目任务"""
        return self.client.get_list("Task", {"project": project})

    def create_task(self, subject: str, project: str, **kwargs) -> Dict:
        """创建任务"""
        data = {
            "doctype": "Task",
            "subject": subject,
            "project": project
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_timesheet(self, project: str, employee: str, **kwargs) -> Dict:
        """创建工时表"""
        data = {
            "doctype": "Timesheet",
            "project": project,
            "employee": employee
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_project_status(self, project: str) -> Dict:
        """获取项目状态"""
        return self.client.get_doc("Project", project)


class ContractManager:
    """合同管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_contract(self, contract_name: str, contract_type: str,
                      customer: Optional[str] = None, supplier: Optional[str] = None, **kwargs) -> Dict:
        """创建合同"""
        data = {
            "doctype": "Contract",
            "contract_name": contract_name,
            "contract_type": contract_type,
            "customer": customer or "",
            "supplier": supplier or ""
        }
        data.update(kwargs)
        return self.client.insert(data)
