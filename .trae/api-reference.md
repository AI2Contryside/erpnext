# TradeMind API 参考文档

## 概述

TradeMind API 为外贸ERP智能助手系统提供RESTful接口，支持多版本兼容（v1正式版，v2预留）。

**基础URL:**

- 生产环境: `https://api.trademind.io/v1`
- 开发环境: `http://localhost:8080/v1`

**认证方式:**

- Bearer Token (JWT)
- API Key

---

## 认证授权

### 用户登录

**POST** `/auth/login`

**请求体:**

```json
{
  "login_id": "string",
  "password": "string",
  "tenant_id": 0
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| login_id | string | 是 | 登录ID (手机号/邮箱/用户名) |
| password | string | 是 | 密码 |
| tenant_id | integer | 否 | 租户ID |

**响应 (200):**

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "expires_in": 3600,
  "token_type": "Bearer",
  "user": {
    "id": 1,
    "tenant_id": 1,
    "username": "admin",
    "real_name": "管理员",
    "phone": "13800138000",
    "email": "admin@example.com",
    "role": "admin",
    "avatar": "string",
    "status": 1,
    "last_login_at": "2026-03-15T10:00:00Z",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

---

### 刷新Token

**POST** `/auth/refresh`

**请求体:**

```json
{
  "refresh_token": "string"
}
```

**响应 (200):**

```json
{
  "access_token": "string",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

---

### 用户注册

**POST** `/auth/register`

**请求体:**

```json
{
  "username": "string",
  "password": "string",
  "phone": "string",
  "email": "string",
  "real_name": "string",
  "tenant_id": 0
}
```

**响应 (201):** 创建成功

---

### 修改密码

**POST** `/auth/change-password`

*需要认证*

**请求体:**

```json
{
  "old_password": "string",
  "new_password": "string"
}
```

---

### 用户登出

**POST** `/auth/logout`

*需要认证*

---

## 租户管理

### 获取租户列表

**GET** `/tenants`

*需要认证*

**查询参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | integer | 1 | 页码 |
| page_size | integer | 20 | 每页数量 |
| status | integer | - | 状态 0=禁用 1=正常 2=试用 |

**响应 (200):**

```json
{
  "list": [
    {
      "id": 1,
      "name": "外贸公司A",
      "contact_name": "张三",
      "contact_phone": "13800138000",
      "contact_email": "zhangsan@example.com",
      "package_level": "pro",
      "package_expire_at": "2026-12-31T23:59:59Z",
      "llm_query_qpm": 60,
      "status": 1,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-03-15T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

---

### 创建租户

**POST** `/tenants`

*需要认证*

**请求体:**

```json
{
  "name": "string",
  "contact_name": "string",
  "contact_phone": "string",
  "contact_email": "string"
}
```

**响应 (201):** 返回创建的租户信息

---

### 获取租户详情

**GET** `/tenants/{id}`

*需要认证*

**路径参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | integer | 租户ID |

---

### 更新租户信息

**PUT** `/tenants/{id}`

*需要认证*

---

### 删除租户

**DELETE** `/tenants/{id}`

*需要认证*

**响应 (204):** 删除成功

---

### 获取租户配置

**GET** `/tenants/{id}/config`

*需要认证*

**响应 (200):**

```json
{
  "reply_style": "professional",
  "work_hours": {
    "timezone": "Asia/Shanghai",
    "start": "09:00",
    "end": "18:00"
  },
  "languages": ["zh-CN", "en-US"],
  "sensitive_words": ["关键词1", "关键词2"]
}
```

---

### 更新租户配置

**PUT** `/tenants/{id}/config`

*需要认证*

---

### 更新租户套餐

**PUT** `/tenants/{id}/package`

*需要认证*

**请求体:**

```json
{
  "package_level": "basic|pro|enterprise",
  "duration": 12
}
```

---

## 用户管理

### 获取用户列表

**GET** `/users`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| tenant_id | integer | 租户ID |
| role | string | 角色 (admin/manager/employee/customer) |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

---

### 创建用户

**POST** `/users`

*需要认证*

**请求体:**

```json
{
  "username": "string",
  "password": "string",
  "phone": "string",
  "email": "string",
  "real_name": "string",
  "role": "employee"
}
```

**响应 (201):** 返回创建的用户信息

---

### 获取用户详情

**GET** `/users/{id}`

*需要认证*

---

### 更新用户信息

**PUT** `/users/{id}`

*需要认证*

**请求体:**

```json
{
  "real_name": "string",
  "email": "string",
  "avatar": "string"
}
```

---

### 删除用户

**DELETE** `/users/{id}`

*需要认证*

---

### 更新用户角色

**PUT** `/users/{id}/role`

*需要认证*

**请求体:**

```json
{
  "role": "admin|manager|employee|customer"
}
```

---

### 获取当前用户信息

**GET** `/users/me`

*需要认证*

---

### 更新当前用户信息

**PUT** `/users/me/profile`

*需要认证*

---

## 会话管理

### 获取会话列表

**GET** `/sessions`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| tenant_id | integer | 租户ID |
| user_id | integer | 用户ID |
| customer_id | integer | 客户ID |
| channel | string | 渠道 (pc/app/feishu/whatsapp/web) |
| status | integer | 状态 0=已结束 1=进行中 |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

---

### 创建会话

**POST** `/sessions`

*需要认证*

**请求体:**

```json
{
  "channel": "pc",
  "title": "客户咨询",
  "customer_id": 0
}
```

**响应 (201):**

```json
{
  "id": 1,
  "tenant_id": 1,
  "user_id": 1,
  "customer_id": 0,
  "channel": "pc",
  "title": "客户咨询",
  "status": 1,
  "session_id": "sess_abc123",
  "last_message_at": "2026-03-15T10:00:00Z",
  "created_at": "2026-03-15T10:00:00Z"
}
```

---

### 获取会话详情

**GET** `/sessions/{id}`

*需要认证*

---

### 结束会话

**DELETE** `/sessions/{id}`

*需要认证*

---

### 获取会话消息历史

**GET** `/sessions/{id}/messages`

*需要认证*

**响应 (200):**

```json
{
  "list": [
    {
      "id": 1,
      "session_id": 1,
      "role": "user",
      "content": "你好，我想查询订单状态",
      "attachments": [],
      "created_at": "2026-03-15T10:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 50
}
```

---

## Agent服务

### 发送聊天消息

**POST** `/agent/chat`

*需要认证*

**请求体:**

```json
{
  "session_id": 1,
  "message": "帮我查询上个月的销售订单",
  "attachments": [
    {
      "type": "image|file",
      "url": "string"
    }
  ]
}
```

**响应 (200):**

```json
{
  "message": "已为您查询到上个月的销售订单，共计52笔，总金额¥1,234,567.89。",
  "session_id": 1,
  "task_id": "task_abc123",
  "results": {
    "orders": [...],
    "total": 52,
    "amount": 1234567.89
  }
}
```

---

### 流式聊天 (SSE)

**POST** `/agent/chat/stream`

*需要认证*

**请求体:**

```json
{
  "session_id": 1,
  "message": "帮我查询订单"
}
```

**响应:** Content-Type: `text/event-stream`

---

### 数据导入

**POST** `/agent/import`

*需要认证*

**请求体:**

```json
{
  "type": "file|natural_language",
  "file_id": "string",
  "content": "从Excel导入100个商品",
  "target_doctype": "Item",
  "dry_run": false
}
```

**响应 (200):**

```json
{
  "success": true,
  "imported_count": 98,
  "failed_count": 2,
  "errors": [
    {"row": 5, "error": "商品编码重复"},
    {"row": 10, "error": "缺少必填字段"}
  ],
  "results": [...]
}
```

---

### 自然语言数据查询

**POST** `/agent/query`

*需要认证*

**请求体:**

```json
{
  "query": "查看上月美国客户的订单汇总",
  "target_doctype": "Sales Order",
  "generate_chart": true,
  "export_format": "xlsx"
}
```

**响应 (200):**

```json
{
  "data": [...],
  "total": 100,
  "chart_url": "https://cdn.example.com/chart_abc.png",
  "export_url": "https://cdn.example.com/export_abc.xlsx",
  "sql": "SELECT * FROM `tabSales Order` WHERE ..."
}
```

---

### 获取任务列表

**GET** `/agent/tasks`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| session_id | integer | 会话ID |
| status | string | 状态 (pending/running/completed/failed/cancelled) |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

---

### 获取任务详情

**GET** `/agent/tasks/{id}`

*需要认证*

**响应 (200):**

```json
{
  "id": "task_abc123",
  "session_id": 1,
  "status": "completed",
  "progress": 100,
  "result": {...},
  "error": null,
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:01:00Z"
}
```

---

### 取消任务

**POST** `/agent/tasks/{id}/cancel`

*需要认证*

---

### 获取可用工具列表

**GET** `/agent/tools`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| category | string | 工具分类 |
| enabled_only | boolean | 仅返回启用的工具 (默认: true) |

**响应 (200):**

```json
{
  "list": [
    {
      "name": "erp_query_item",
      "description": "查询ERP商品数据",
      "category": "erp",
      "parameters": {...},
      "enabled": true
    }
  ]
}
```

---

### 执行工具

**POST** `/agent/tools/{name}/execute`

*需要认证*

**请求体:** 工具参数 (JSON对象)

---

## 文件管理

### 文件上传

**POST** `/files/upload`

*需要认证*

**Content-Type:** `multipart/form-data`

**表单字段:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | binary | 是 | 文件内容 |
| category | string | 否 | 类别 (document/image/audio/other) |

**响应 (200):**

```json
{
  "id": "file_abc123",
  "name": "order_data.xlsx",
  "size": 102400,
  "url": "https://cdn.example.com/files/file_abc123.xlsx"
}
```

---

### 获取文件信息

**GET** `/files/{id}`

*需要认证*

---

### 删除文件

**DELETE** `/files/{id}`

*需要认证*

---

### 下载文件

**GET** `/files/{id}/download`

*需要认证*

**响应:** Content-Type: `application/octet-stream`

---

### 解析文件

**POST** `/files/{id}/parse`

*需要认证*

**请求体:**

```json
{
  "parse_type": "auto|excel|csv|pdf|image",
  "target_structure": {
    "fields": ["item_code", "item_name", "price"]
  }
}
```

**响应 (200):**

```json
{
  "success": true,
  "data": [
    {"item_code": "A001", "item_name": "商品A", "price": 100},
    {"item_code": "A002", "item_name": "商品B", "price": 200}
  ],
  "structure": {
    "columns": ["item_code", "item_name", "price"],
    "rows": 2
  },
  "errors": []
}
```

---

### 获取文件列表

**GET** `/files`

*需要认证*

---

## ERP集成

### 查询商品

**GET** `/erp/item`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| keyword | string | 关键词 |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

---

### 创建商品

**POST** `/erp/item`

*需要认证*

**请求体:**

```json
{
  "item_code": "A001",
  "item_name": "商品名称",
  "item_group": "商品组",
  "stock_uom": "个",
  "description": "商品描述"
}
```

---

### 获取商品详情

**GET** `/erp/item/{id}`

*需要认证*

---

### 更新商品

**PUT** `/erp/item/{id}`

*需要认证*

---

### 删除商品

**DELETE** `/erp/item/{id}`

*需要认证*

---

### 查询客户

**GET** `/erp/customer`

*需要认证*

---

### 创建客户

**POST** `/erp/customer`

*需要认证*

---

### 获取客户详情

**GET** `/erp/customer/{id}`

*需要认证*

---

### 更新客户

**PUT** `/erp/customer/{id}`

*需要认证*

---

### 查询供应商

**GET** `/erp/supplier`

*需要认证*

---

### 创建供应商

**POST** `/erp/supplier`

*需要认证*

---

### 查询订单

**GET** `/erp/order`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| keyword | string | 关键词 |
| customer_id | string | 客户ID |
| status | string | 状态 |
| date_from | string | 开始日期 (YYYY-MM-DD) |
| date_to | string | 结束日期 (YYYY-MM-DD) |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

---

### 创建订单

**POST** `/erp/order`

*需要认证*

---

### 获取订单详情

**GET** `/erp/order/{id}`

*需要认证*

---

### 更新订单

**PUT** `/erp/order/{id}`

*需要认证*

---

### 查询库存

**GET** `/erp/stock`

*需要认证*

---

### 获取库存余额

**GET** `/erp/stock/balance`

*需要认证*

---

### 同步数据到ERP

**POST** `/erp/sync`

*需要认证*

**请求体:**

```json
{
  "doctype": "Item",
  "data": {...},
  "mode": "create|update"
}
```

**响应 (200):**

```json
{
  "success": true,
  "erp_id": "item_abc123",
  "message": "数据同步成功"
}
```

---

### ERP Webhook回调

**POST** `/erp/webhook`

---

## Token消耗

### 获取Token消耗记录

**GET** `/tokens/records`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| tenant_id | integer | 租户ID |
| user_id | integer | 用户ID |
| session_id | integer | 会话ID |
| date_from | string | 开始日期 |
| date_to | string | 结束日期 |
| page | integer | 页码 |
| page_size | integer | 每页数量 |

**响应 (200):**

```json
{
  "list": [
    {
      "id": 1,
      "tenant_id": 1,
      "user_id": 1,
      "session_id": 1,
      "round": 1,
      "model": "claude-3-opus",
      "input_tokens": 150,
      "output_tokens": 300,
      "total_tokens": 450,
      "created_at": "2026-03-15T10:00:00Z"
    }
  ],
  "total": 1000,
  "page": 1,
  "page_size": 20
}
```

---

### 获取Token消耗统计

**GET** `/tokens/statistics`

*需要认证*

**响应 (200):**

```json
{
  "total_tokens": 1000000,
  "input_tokens": 400000,
  "output_tokens": 600000,
  "total_cost": 150.50,
  "by_model": {
    "claude-3-opus": 800000,
    "gpt-4": 200000
  },
  "by_user": {
    "1": 500000,
    "2": 300000
  }
}
```

---

### 获取当前租户Token使用量

**GET** `/tokens/usage`

*需要认证*

**响应 (200):**

```json
{
  "tenant_id": 1,
  "used_tokens": 500000,
  "limit_tokens": 1000000,
  "used_percentage": 50.0
}
```

---

## 订阅管理

### 获取订阅记录

**GET** `/subscriptions`

*需要认证*

---

### 创建订阅

**POST** `/subscriptions`

*需要认证*

**请求体:**

```json
{
  "tenant_id": 1,
  "package_level": "pro",
  "duration": 12,
  "amount": 9999.00,
  "type": 1
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| type | integer | 1=单次订阅 2=自动续费 |

---

### 获取套餐列表

**GET** `/subscriptions/packages`

**响应 (200):**

```json
{
  "list": [
    {
      "id": "basic",
      "name": "基础版",
      "level": "basic",
      "price": 99,
      "duration": 1,
      "features": {
        "users": 5,
        "storage_gb": 10,
        "llm_qpm": 10
      },
      "limits": {
        "api_calls": 1000,
        "file_size_mb": 50
      }
    }
  ]
}
```

---

### 获取套餐详情

**GET** `/subscriptions/packages/{id}`

---

### 获取交易记录

**GET** `/transactions`

*需要认证*

---

## IM渠道

### IM平台Webhook

**POST** `/im/webhook/{platform}`

**路径参数:**

| 参数 | 说明 |
|------|------|
| platform | 平台 (feishu/whatsapp/wechat/dingtalk) |

---

### 获取IM渠道列表

**GET** `/im/channels`

*需要认证*

---

### 创建IM渠道

**POST** `/im/channels`

*需要认证*

**请求体:**

```json
{
  "platform": "feishu",
  "name": "飞书客服",
  "config": {
    "app_id": "string",
    "app_secret": "string"
  }
}
```

---

### 获取IM渠道详情

**GET** `/im/channels/{id}`

*需要认证*

---

### 更新IM渠道

**PUT** `/im/channels/{id}`

*需要认证*

---

### 删除IM渠道

**DELETE** `/im/channels/{id}`

*需要认证*

---

### 测试IM渠道

**POST** `/im/channels/{id}/test`

*需要认证*

---

## 后台管理

### 获取系统配置

**GET** `/admin/config`

*需要认证*

**响应 (200):**

```json
{
  "llm_config": {
    "default_model": "claude-3-opus",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "tool_permissions": ["erp_query", "file_parse"],
  "sensitive_words": ["word1", "word2"],
  "api_quotas": {
    "default": 1000,
    "basic": 500,
    "pro": 5000,
    "enterprise": -1
  }
}
```

---

### 更新系统配置

**PUT** `/admin/config`

*需要认证*

---

### 获取运营指标

**GET** `/admin/metrics`

*需要认证*

**查询参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| date_from | string | 开始日期 |
| date_to | string | 结束日期 |

**响应 (200):**

```json
{
  "active_tenants": 50,
  "total_requests": 100000,
  "total_tokens": 50000000,
  "error_rate": 0.5,
  "avg_response_time": 1.2,
  "by_day": [
    {
      "date": "2026-03-15",
      "requests": 10000,
      "tokens": 5000000
    }
  ]
}
```

---

### 获取审计日志

**GET** `/admin/audit-logs`

*需要认证*

---

### 获取所有租户用户

**GET** `/admin/users`

*需要认证*

---

### 获取限流配置

**GET** `/admin/rate-limits`

*需要认证*

---

### 更新限流配置

**PUT** `/admin/rate-limits`

*需要认证*

---

### 获取LLM模型配置

**GET** `/admin/models`

*需要认证*

---

### 添加LLM模型

**POST** `/admin/models`

*需要认证*

**请求体:**

```json
{
  "name": "Claude 3 Opus",
  "provider": "anthropic",
  "model_id": "claude-3-opus-20240229",
  "enabled": true
}
```

| provider | 说明 |
|----------|------|
| openai | OpenAI |
| anthropic | Anthropic (Claude) |
| alibaba | 阿里云 (通义千问) |
| baidu | 百度 (文心一言) |

---

### 更新LLM模型

**PUT** `/admin/models/{id}`

*需要认证*

---

### 系统健康检查

**GET** `/admin/health`

**响应 (200):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-15T10:00:00Z"
}
```

---

## 错误响应

### 状态码说明

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 (限流) |
| 500 | 服务器内部错误 |
| 502 | 网关错误 |
| 503 | 服务不可用 |

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数错误：缺少必填字段"
  }
}
```

### 常见错误码

| 错误码 | 说明 |
|--------|------|
| INVALID_PARAMETER | 请求参数无效 |
| UNAUTHORIZED | 未认证 |
| FORBIDDEN | 无权限 |
| NOT_FOUND | 资源不存在 |
| RATE_LIMIT_EXCEEDED | 超出限流 |
| TOKEN_EXPIRED | Token已过期 |
| INSUFFICIENT_BALANCE | 余额不足 |

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0.0 | 2026-03-15 | 初始版本 |
