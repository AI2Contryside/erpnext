"""
ERPNext 资产管理模块
提供资产购置、折旧、维护等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class AssetManager:
    """资产管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_asset(self, asset_name: str, asset_category: str, company: str,
                   purchase_date: str, gross_weight: float, **kwargs) -> Dict:
        """创建资产"""
        data = {
            "doctype": "Asset",
            "asset_name": asset_name,
            "asset_category": asset_category,
            "company": company,
            "purchase_date": purchase_date,
            "gross_weight": gross_weight
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_asset_from_purchase(self, purchase_receipt: str) -> Dict:
        """从采购收货创建资产"""
        return self.client.call_method("Purchase Receipt", purchase_receipt, "make_asset")

    def get_assets(self, category: Optional[str] = None, company: Optional[str] = None,
                  status: Optional[str] = None) -> List[Dict]:
        """获取资产列表"""
        filters = {}
        if category:
            filters["asset_category"] = category
        if company:
            filters["company"] = company
        if status:
            filters["status"] = status
        return self.client.get_list("Asset", filters=filters)

    def get_asset_value(self, asset: str) -> Dict:
        """获取资产价值"""
        return self.client.get_doc("Asset", asset)

    def calculate_depreciation(self, asset: str) -> Dict:
        """计算折旧"""
        return self.client.call_method("Asset", asset, "calculate_depreciation")

    def post_depreciation(self, asset: str) -> Dict:
        """过账折旧"""
        return self.client.call_method("Asset", asset, "post_depreciation_entries")

    def transfer_asset(self, asset: str, target_warehouse: str, **kwargs) -> Dict:
        """转移资产"""
        data = {
            "doctype": "Asset Movement",
            "asset": asset,
            "target_warehouse": target_warehouse,
            "company": kwargs.get("company")
        }
        data.update(kwargs)
        return self.client.insert(data)

    def scrap_asset(self, asset: str, scrap_date: str, **kwargs) -> Dict:
        """报废资产"""
        data = {
            "doctype": "Asset Repair",
            "asset": asset,
            "repair_status": "Scrapped",
            "completion_date": scrap_date
        }
        data.update(kwargs)
        return self.client.insert(data)

    def sell_asset(self, asset: str, customer: str, selling_price: float) -> Dict:
        """出售资产"""
        return self.client.call_method("Asset", asset, "sell_asset",
                                     customer=customer, selling_price=selling_price)


class AssetCategoryManager:
    """资产类别管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_asset_category(self, category_name: str, company: str,
                            depreciation_method: str = "Straight Line",
                            total_number_of_depreciations: int = 5,
                            frequency_of_depreciation: int = 12, **kwargs) -> Dict:
        """创建资产类别"""
        data = {
            "doctype": "Asset Category",
            "asset_category_name": category_name,
            "company": company,
            "depreciation_method": depreciation_method,
            "total_number_of_depreciations": total_number_of_depreciations,
            "frequency_of_depreciation": frequency_of_depreciation
        }
        data.update(kwargs)
        return self.client.insert(data)


class AssetMaintenanceManager:
    """资产维护管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_maintenance_schedule(self, asset: str, company: str,
                                  maintenance_type: str, periodicity: str,
                                  start_date: str, **kwargs) -> Dict:
        """创建维护计划"""
        data = {
            "doctype": "Maintenance Schedule",
            "asset": asset,
            "company": company,
            "maintenance_type": maintenance_type,
            "periodicity": periodicity,
            "start_date": start_date
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_maintenance_visit(self, asset: str, company: str,
                                maintenance_type: str, **kwargs) -> Dict:
        """创建维护访问"""
        data = {
            "doctype": "Maintenance Visit",
            "asset": asset,
            "company": company,
            "maintenance_type": maintenance_type
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_pending_maintenance(self, asset: Optional[str] = None) -> List[Dict]:
        """获取待维护资产"""
        filters = {"docstatus": 1, "maintenance_status": "Pending"}
        if asset:
            filters["asset"] = asset
        return self.client.get_list("Maintenance Schedule", filters=filters)


class AssetValueAdjustment:
    """资产价值调整"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_value_adjustment(self, asset: str, company: str,
                              current_value: float, new_value: float,
                              **kwargs) -> Dict:
        """创建资产价值调整"""
        data = {
            "doctype": "Asset Value Adjustment",
            "asset": asset,
            "company": company,
            "current_asset_value": current_value,
            "new_asset_value": new_value,
            "adjustment_type": "Residual Value"
        }
        data.update(kwargs)
        return self.client.insert(data)


class AssetCapitalization:
    """资产资本化"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_capitalization(self, company: str, entry_type: str,
                            target_asset: str, **kwargs) -> Dict:
        """创建资产资本化"""
        data = {
            "doctype": "Asset Capitalization",
            "company": company,
            "entry_type": entry_type,
            "target_asset": target_asset
        }
        data.update(kwargs)
        return self.client.insert(data)
