# 销售管理 Skill

本 Skill 提供 ERPNext 销售管理业务能力。

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client
from sales.scripts.manager import SalesManager, CustomerManager

# 初始化（必须提供 tenant_id）
client = create_client({
    "url": "https://your-site.com",
    "api_key": "xxx",
    "api_secret": "xxx",
    "tenant_id": "tenant_123"
})

sales_mgr = SalesManager(client)
cust_mgr = CustomerManager(client)
```

## 业务功能

### 报价单管理

| 方法 | 说明 |
|------|------|
| `create_quotation()` | 创建报价单 |
| `convert_quotation_to_sales_order()` | 转为销售订单 |

### 销售订单管理

| 方法 | 说明 |
|------|------|
| `create_sales_order()` | 创建销售订单 |
| `create_delivery_note_from_sales_order()` | 创建送货单 |
| `create_sales_invoice_from_sales_order()` | 创建发票 |
| `get_pending_sales_orders()` | 待完成订单 |
| `hold_sales_order()` | 暂停订单 |
| `unhold_sales_order()` | 取消暂停 |
| `close_sales_order()` | 关闭订单 |

### 客户管理

| 方法 | 说明 |
|------|------|
| `create_customer()` | 创建客户 |
| `get_customer_balance()` | 获取客户余额 |
| `get_customer_credit_limit()` | 信用额度 |
| `update_customer_credit_limit()` | 更新信用额度 |
| `get_customer_sales_stats()` | 销售统计 |

## 示例

### 创建报价单并转为订单

```python
# 创建报价单
quotation = sales_mgr.create_quotation(
    customer="CUST-001",
    company="My Company",
    items=[{"item_code": "ITEM-001", "qty": 10, "rate": 100}],
    valid_till="2024-12-31"
)

# 转为销售订单
sales_order = sales_mgr.convert_quotation_to_sales_order(quotation["name"])
```

### 创建销售订单并生成发票

```python
# 创建销售订单
order = sales_mgr.create_sales_order(
    customer="CUST-001",
    company="My Company",
    items=[{"item_code": "ITEM-001", "qty": 10, "rate": 100}]
)

# 提交订单
client.submit("Sales Order", order["name"])

# 生成发票
invoice = sales_mgr.create_sales_invoice_from_sales_order(order["name"])
```
