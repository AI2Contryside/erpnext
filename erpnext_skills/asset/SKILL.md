# 资产管理 Skill

本 Skill 提供 ERPNext 资产管理业务能力。

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client
from asset.scripts.manager import (
    AssetManager, AssetCategoryManager, AssetMaintenanceManager,
    AssetValueAdjustment, AssetCapitalization
)

client = create_client({
    "url": "https://your-site.com",
    "api_key": "xxx",
    "api_secret": "xxx",
    "tenant_id": "tenant_123"
})

asset_mgr = AssetManager(client)
cat_mgr = AssetCategoryManager(client)
maint_mgr = AssetMaintenanceManager(client)
```

## 业务功能

### 资产管理

| 方法 | 说明 |
|------|------|
| `create_asset()` | 创建资产 |
| `create_asset_from_purchase()` | 从采购创建 |
| `get_assets()` | 获取资产列表 |
| `get_asset_value()` | 获取资产价值 |
| `calculate_depreciation()` | 计算折旧 |
| `post_depreciation()` | 过账折旧 |
| `transfer_asset()` | 转移资产 |
| `scrap_asset()` | 报废资产 |
| `sell_asset()` | 出售资产 |

### 资产类别

| 方法 | 说明 |
|------|------|
| `create_asset_category()` | 创建资产类别 |

### 维护管理

| 方法 | 说明 |
|------|------|
| `create_maintenance_schedule()` | 创建维护计划 |
| `create_maintenance_visit()` | 创建维护访问 |
| `get_pending_maintenance()` | 待维护资产 |

### 价值调整

| 方法 | 说明 |
|------|------|
| `create_value_adjustment()` | 价值调整 |
| `create_capitalization()` | 资本化 |

## 示例

### 创建资产

```python
asset_mgr.create_asset(
    asset_name="Laptop Dell XPS",
    asset_category="Electronics",
    company="My Company",
    purchase_date="2024-01-01",
    gross_weight=15000
)
```

### 计提折旧

```python
asset_mgr.calculate_depreciation("ASSET-001")
asset_mgr.post_depreciation("ASSET-001")
```
