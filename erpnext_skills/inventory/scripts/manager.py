"""
ERPNext 库存管理模块
提供库存、仓库、物料移动等业务操作
"""

from typing import Dict, List, Optional
from base.scripts.client import ERPNextClient


class InventoryManager:
    """库存管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def get_item_stock(self, item_code: str, warehouse: Optional[str] = None) -> Dict:
        """获取物料库存"""
        filters = {"item_code": item_code}
        if warehouse:
            filters["warehouse"] = warehouse

        bins = self.client.get_list("Bin", filters=filters)
        total_qty = sum(b.get("actual_qty", 0) for b in bins)
        total_val = sum(b.get("stock_value", 0) for b in bins)

        return {
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": total_qty,
            "stock_value": total_val,
            "bins": bins
        }

    def get_warehouse_items(self, warehouse: str, limit: int = 50) -> List[Dict]:
        """获取仓库中的物料"""
        bins = self.client.get_list("Bin", {"warehouse": warehouse, "actual_qty": [">", 0]}, limit=limit)
        return bins

    def create_stock_entry(self, company: str, stock_entry_type: str,
                          items: List[Dict], **kwargs) -> Dict:
        """创建库存过账"""
        data = {
            "doctype": "Stock Entry",
            "company": company,
            "stock_entry_type": stock_entry_type,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def material_receipt(self, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建材料入库"""
        return self.create_stock_entry(company, "Material Receipt", items, **kwargs)

    def material_issue(self, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建材料出库"""
        return self.create_stock_entry(company, "Material Issue", items, **kwargs)

    def material_transfer(self, company: str, items: List[Dict],
                        source_warehouse: str, target_warehouse: str, **kwargs) -> Dict:
        """创建调拨"""
        for item in items:
            item["s_warehouse"] = source_warehouse
            item["t_warehouse"] = target_warehouse
        return self.create_stock_entry(company, "Material Transfer", items, **kwargs)

    def create_stock_reconciliation(self, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建库存调节"""
        data = {
            "doctype": "Stock Reconciliation",
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_stock_ledger(self, item_code: str, from_date: Optional[str] = None,
                        to_date: Optional[str] = None) -> List[Dict]:
        """获取库存台账"""
        filters = {"item_code": item_code}
        if from_date:
            filters["posting_date"] = [">=", from_date]
        if to_date:
            filters["posting_date"] = ["<=", to_date]
        return self.client.get_list("Stock Ledger Entry", filters=filters, limit=100)

    def create_delivery_note(self, customer: str, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建送货单"""
        data = {
            "doctype": "Delivery Note",
            "customer": customer,
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)

    def create_purchase_receipt(self, supplier: str, company: str, items: List[Dict], **kwargs) -> Dict:
        """创建采购收货"""
        data = {
            "doctype": "Purchase Receipt",
            "supplier": supplier,
            "company": company,
            "items": items
        }
        data.update(kwargs)
        return self.client.insert(data)


class WarehouseManager:
    """仓库管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def get_warehouses(self, company: Optional[str] = None) -> List[Dict]:
        """获取仓库列表"""
        filters = {}
        if company:
            filters["company"] = company
        return self.client.get_list("Warehouse", filters=filters)

    def create_warehouse(self, warehouse_name: str, company: str,
                        parent_warehouse: Optional[str] = None, **kwargs) -> Dict:
        """创建仓库"""
        data = {
            "doctype": "Warehouse",
            "warehouse_name": warehouse_name,
            "company": company,
            "parent_warehouse": parent_warehouse or ""
        }
        data.update(kwargs)
        return self.client.insert(data)


class ItemManager:
    """物料管理"""

    def __init__(self, client: ERPNextClient):
        self.client = client

    def create_item(self, item_code: str, item_name: str,
                   item_group: str = "All Item Groups",
                   stock_uom: str = "Nos", **kwargs) -> Dict:
        """创建物料"""
        data = {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": item_group,
            "stock_uom": stock_uom,
            "is_stock_item": 1
        }
        data.update(kwargs)
        return self.client.insert(data)

    def get_item_price(self, item_code: str, price_list: str = "Standard Selling") -> Optional[Dict]:
        """获取物料价格"""
        items = self.client.get_list("Item Price", {
            "item_code": item_code,
            "price_list": price_list
        }, limit=1)
        return items[0] if items else None

    def set_item_price(self, item_code: str, price_list: str, price: float) -> Dict:
        """设置物料价格"""
        existing = self.get_item_price(item_code, price_list)
        if existing:
            return self.client.update("Item Price", existing["name"], {"price_list_rate": price})
        else:
            return self.client.insert({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list,
                "price_list_rate": price
            })

    def disable_item(self, item_code: str) -> Dict:
        """禁用物料"""
        return self.client.update("Item", item_code, {"disabled": 1})

    def enable_item(self, item_code: str) -> Dict:
        """启用物料"""
        return self.client.update("Item", item_code, {"disabled": 0})
