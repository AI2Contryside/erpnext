# 库存管理 Skill

本 Skill 提供 ERPNext 库存管理业务能力。

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client
from inventory.scripts.manager import InventoryManager, WarehouseManager, ItemManager

client = create_client({
    "url": "https://your-site.com",
    "api_key": "xxx",
    "api_secret": "xxx",
    "tenant_id": "tenant_123"
})

inv_mgr = InventoryManager(client)
wh_mgr = WarehouseManager(client)
item_mgr = ItemManager(client)
```

## 业务功能

### 库存操作

| 方法 | 说明 |
|------|------|
| `get_item_stock()` | 获取物料库存 |
| `get_warehouse_items()` | 仓库物料列表 |
| `create_stock_entry()` | 创建库存过账 |
| `material_receipt()` | 材料入库 |
| `material_issue()` | 材料出库 |
| `material_transfer()` | 调拨 |
| `create_stock_reconciliation()` | 库存调节 |
| `get_stock_ledger()` | 库存台账 |

### 仓库管理

| 方法 | 说明 |
|------|------|
| `get_warehouses()` | 获取仓库列表 |
| `create_warehouse()` | 创建仓库 |

### 物料管理

| 方法 |说明 |
|------|------|
| `create_item()` | 创建物料 |
| `get_item_price()` | 获取价格 |
| `set_item_price()` | 设置价格 |
| `disable_item()` | 禁用物料 |
| `enable_item()` | 启用物料 |

## 示例

### 材料入库

```python
inv_mgr.material_receipt(
    company="My Company",
    items=[{"item_code": "ITEM-001", "qty": 100, "t_warehouse": "Main Warehouse - MC"}]
)
```

### 库存调拨

```python
inv_mgr.material_transfer(
    company="My Company",
    items=[{"item_code": "ITEM-001", "qty": 50}],
    source_warehouse="Warehouse A - MC",
    target_warehouse="Warehouse B - MC"
)
```

### 设置物料价格

```python
item_mgr.set_item_price("ITEM-001", "Standard Selling", 150.00)
```
