# 生产管理 Skill

本 Skill 提供 ERPNext 生产管理业务能力。

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client
from manufacturing.scripts.manager import (
    BOMManager, WorkOrderManager, RoutingManager,
    ProductionPlanManager, JobCardManager
)

client = create_client({
    "url": "https://your-site.com",
    "api_key": "xxx",
    "api_secret": "xxx",
    "tenant_id": "tenant_123"
})

bom_mgr = BOMManager(client)
wo_mgr = WorkOrderManager(client)
routing_mgr = RoutingManager(client)
plan_mgr = ProductionPlanManager(client)
job_mgr = JobCardManager(client)
```

## 业务功能

### 物料清单 (BOM)

| 方法 | 说明 |
|------|------|
| `create_bom()` | 创建 BOM |
| `get_active_bom()` | 获取激活的 BOM |
| `get_bom_components()` | 获取 BOM 组件 |
| `get_bom_cost()` | 获取 BOM 成本 |

### 工单

| 方法 | 说明 |
|------|------|
| `create_work_order()` | 创建工单 |
| `start_work_order()` | 开始工单 |
| `complete_work_order()` | 完成工单 |
| `get_pending_work_orders()` | 待生产工单 |
| `get_work_order_status()` | 工单状态 |

### 工艺路线

| 方法 | 说明 |
|------|------|
| `create_routing()` | 创建工艺路线 |
| `add_operation()` | 添加工序 |

### 生产计划

| 方法 | 说明 |
|------|------|
| `create_production_plan()` | 创建生产计划 |
| `get_production_plan_status()` | 计划状态 |
| `create_work_orders_from_plan()` | 从计划创建工单 |

### 工序卡

| 方法 | 说明 |
|------|------|
| `get_job_cards()` | 获取工序卡 |
| `start_job_card()` | 开始工序 |
| `complete_job_card()` | 完成工序 |

## 示例

### 创建 BOM

```python
bom_mgr.create_bom(
    item="FINISHED-001",
    company="My Company",
    items=[
        {"item_code": "RAW-001", "qty": 2},
        {"item_code": "RAW-002", "qty": 1}
    ]
)
```

### 创建工单并完成

```python
# 创建工单
wo = wo_mgr.create_work_order(
    item="FINISHED-001",
    company="My Company",
    qty=100
)

# 开始生产
wo_mgr.start_work_order(wo["name"])

# 完成工单并生成入库
wo_mgr.complete_work_order(wo["name"], qty=100)
```
