"""
ERPNext 人力资源管理模块
提供员工、假期、考勤等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class EmployeeManager:
    """员工管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_employee(self, first_name: str, company: str,
                       department: Optional[str] = None, designation: Optional[str] = None, **kwargs) -> Dict:
        """创建员工"""
        data = {
            "doctype": "Employee",
            "first_name": first_name,
            "company": company,
            "department": department or "",
            "designation": designation or ""
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_employees(self, company: Optional[str] = None, status: str = "Active") -> List[Dict]:
        """获取员工列表"""
        filters = {"status": status}
        if company:
            filters["company"] = company
        return self.client.get_list("Employee", filters=filters)


class LeaveManager:
    """假期管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_leave_application(self, employee: str, leave_type: str,
                               from_date: str, to_date: str, **kwargs) -> Dict:
        """创建请假申请"""
        data = {
            "doctype": "Leave Application",
            "employee": employee,
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_leave_balance(self, employee: str) -> List[Dict]:
        """获取员工假期余额"""
        return self.client.get_list("Leave Balance", {"employee": employee})


class AttendanceManager:
    """考勤管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def mark_attendance(self, employee: str, attendance_date: str,
                      status: str, **kwargs) -> Dict:
        """签到考勤"""
        data = {
            "doctype": "Attendance",
            "employee": employee,
            "attendance_date": attendance_date,
            "status": status
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_attendance_records(self, employee: Optional[str] = None,
                             from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict]:
        """获取考勤记录"""
        filters = {}
        if employee:
            filters["employee"] = employee
        if from_date:
            filters["attendance_date"] = [">=", from_date]
        if to_date:
            filters["attendance_date"] = ["<=", to_date]
        return self.client.get_list("Attendance", filters=filters)


class PayrollManager:
    """薪酬管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_salary_slip(self, employee: str, start_date: str, end_date: str, **kwargs) -> Dict:
        """创建工资单"""
        data = {
            "doctype": "Salary Slip",
            "employee": employee,
            "start_date": start_date,
            "end_date": end_date
        }
        data.update(kwargs)
        return self.client.insert(data)


class DepartmentManager:
    """部门管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_department(self, department_name: str, company: str,
                        parent_department: Optional[str] = None, **kwargs) -> Dict:
        """创建部门"""
        data = {
            "doctype": "Department",
            "department_name": department_name,
            "company": company,
            "parent_department": parent_department or ""
        }
        data.update(kwargs)
        return self.client.insert(data)
