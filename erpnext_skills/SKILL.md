---
name: erpnext-business-skills
description: 用于访问 ERPNext 系统的业务 Skill，支持销售、采购、库存、财务、生产、资产、项目、HR、服务支持等模块。所有 API 请求自动添加 X-Tenant-ID Header 实现多租户数据隔离。
---

# ERPNext 业务 Skill

本 Skill 提供访问 ERPNext 系统的业务能力，按业务板块组织。

## 核心原则

1. **所有 API 请求必须携带 `X-Tenant-ID` Header**
2. **按业务板块加载**：根据任务类型加载相应 Skill
3. **业务逻辑封装**：每个板块独立模块

## 业务板块

| Skill | 说明 | 路径 |
|-------|------|------|
| 销售 | 报价单、销售订单、客户 | [sales/SKILL.md](./sales/SKILL.md) |
| 采购 | 供应商、采购订单、询价 | [buying/SKILL.md](./buying/SKILL.md) |
| 库存 | 库存、仓库、物料 | [inventory/SKILL.md](./inventory/SKILL.md) |
| 财务 | 发票、付款、报表 | [finance/SKILL.md](./finance/SKILL.md) |
| 生产 | BOM、工单、工艺 | [manufacturing/SKILL.md](./manufacturing/SKILL.md) |
| 资产 | 资产、折旧、维护 | [asset/SKILL.md](./asset/SKILL.md) |
| 项目/CRM | 线索、机会、项目 | [crm/SKILL.md](./crm/SKILL.md) |
| HR | 员工、假期、考勤 | [hr/SKILL.md](./hr/SKILL.md) |
| 服务支持 | 工单、保修 | [support/SKILL.md](./support/SKILL.md) |

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client

# 配置（tenant_id 必填）
config = {
    "url": "https://your-erpnext-site.com",
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "tenant_id": "your_tenant_id"
}

client = create_client(config)

# 加载业务模块
from sales.scripts.manager import SalesManager
from buying.scripts.manager import PurchaseManager
from inventory.scripts.manager import InventoryManager
from finance.scripts.manager import InvoiceManager
from manufacturing.scripts.manager import WorkOrderManager
from asset.scripts.manager import AssetManager
from crm.scripts.manager import LeadManager
from hr.scripts.manager import EmployeeManager
from support.scripts.manager import IssueManager
```

## X-Tenant-ID 说明

所有 API 请求都会自动添加 `X-Tenant-ID` Header：

```python
# 内部实现
headers = {
    "Authorization": f"token {api_key}:{api_secret}",
    "X-Tenant-ID": tenant_id,  # 自动添加
}
```

## 目录结构

```
erpnext_skills/
├── SKILL.md                    # 本文件
├── base/
│   └── scripts/
│       └── client.py           # API 客户端
├── sales/
│   ├── SKILL.md
│   └── scripts/manager.py
├── buying/
│   ├── SKILL.md
│   └── scripts/manager.py
├── inventory/
│   ├── SKILL.md
│   └── scripts/manager.py
├── finance/
│   ├── SKILL.md
│   └── scripts/manager.py
├── manufacturing/
│   ├── SKILL.md
│   └── scripts/manager.py
├── asset/
│   ├── SKILL.md
│   └── scripts/manager.py
├── crm/
│   ├── SKILL.md
│   └── scripts/manager.py
├── hr/
│   ├── SKILL.md
│   └── scripts/manager.py
└── support/
    ├── SKILL.md
    └── scripts/manager.py
```
