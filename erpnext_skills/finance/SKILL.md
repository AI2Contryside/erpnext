# 财务管理 Skill

本 Skill 提供 ERPNext 财务管理业务能力。

## 快速开始

```python
import sys
sys.path.insert(0, '/path/to/erpnext_skills')

from base.scripts.client import create_client
from finance.scripts.manager import InvoiceManager, PaymentManager, JournalManager, AccountingReport

client = create_client({
    "url": "https://your-site.com",
    "api_key": "xxx",
    "api_secret": "xxx",
    "tenant_id": "tenant_123"
})

inv_mgr = InvoiceManager(client)
pay_mgr = PaymentManager(client)
journal_mgr = JournalManager(client)
report_mgr = AccountingReport(client)
```

## 业务功能

### 发票管理

| 方法 | 说明 |
|------|------|
| `create_sales_invoice()` | 创建销售发票 |
| `create_purchase_invoice()` | 创建采购发票 |
| `create_invoice_from_sales_order()` | 从订单创建发票 |
| `get_outstanding_invoices()` | 未结发票 |
| `get_customer_outstanding()` | 客户应收账款 |
| `get_supplier_outstanding()` | 供应商应付账款 |

### 付款管理

| 方法 | 说明 |
|------|------|
| `create_payment_entry()` | 创建付款凭证 |
| `receive_payment()` | 收款 |
| `make_payment()` | 付款 |

### 日记账

| 方法 | 说明 |
|------|------|
| `create_journal_entry()` | 创建日记账 |

### 报表

| 方法 | 说明 |
|------|------|
| `get_trial_balance()` | 试算平衡表 |
| `get_balance_sheet()` | 资产负债表 |
| `get_profit_and_loss()` | 利润表 |
| `get_general_ledger()` | 总账 |

## 示例

### 创建销售发票

```python
inv_mgr.create_sales_invoice(
    customer="CUST-001",
    company="My Company",
    items=[{"item_code": "ITEM-001", "qty": 10, "rate": 100}]
)
```

### 收款

```python
pay_mgr.receive_payment(
    company="My Company",
    amount=1000,
    customer="CUST-001",
    account_received="Cash - MC",
    paid_account="Debtors - MC"
)
```
