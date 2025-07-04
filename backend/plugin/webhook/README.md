# Webhook 事件接收器插件

## 功能描述

Webhook插件用于接收和处理外部系统的POST事件，支持事件的存储、处理、重试和管理。支持Header验证和签名验证以确保安全性。

## 主要特性

- **事件接收**: 接收外部系统的Webhook POST事件
- **Header验证**: 支持多种Header验证规则（精确匹配、包含、正则表达式）
- **签名验证**: 支持HMAC-SHA256签名验证，兼容GitHub、GitLab等平台
- **事件存储**: 将接收到的事件存储到数据库中
- **事件处理**: 根据事件类型执行相应的业务逻辑
- **失败重试**: 支持失败事件的自动重试机制
- **事件管理**: 提供事件的查询、更新、删除等管理功能
- **状态跟踪**: 跟踪事件的处理状态（成功、失败、待处理）

## API 接口

### 1. 接收Webhook事件（无验证）
- **URL**: `POST /webhooks/v1/sys/receive`
- **描述**: 接收外部系统的Webhook事件
- **无需认证**: 此接口不需要JWT认证，便于外部系统调用

### 2. 接收Webhook事件（带验证）
- **URL**: `POST /webhooks/v1/sys/receive/validated`
- **描述**: 接收需要Header验证和签名验证的Webhook事件
- **支持验证**: Header验证规则、HMAC签名验证

### 3. 获取事件详情
- **URL**: `GET /webhooks/v1/sys/{pk}`
- **描述**: 获取指定Webhook事件的详细信息
- **需要认证**: 需要JWT认证

### 4. 分页获取事件列表
- **URL**: `GET /webhooks/v1/sys`
- **描述**: 分页获取Webhook事件列表，支持多种筛选条件
- **需要认证**: 需要JWT认证

### 5. 更新事件
- **URL**: `PUT /webhooks/v1/sys/{pk}`
- **描述**: 更新Webhook事件信息
- **需要权限**: `sys:webhook:edit`

### 6. 批量删除事件
- **URL**: `DELETE /webhooks/v1/sys`
- **描述**: 批量删除Webhook事件
- **需要权限**: `sys:webhook:del`

### 7. 重试失败事件
- **URL**: `POST /webhooks/v1/sys/retry`
- **描述**: 重试所有失败的Webhook事件
- **需要权限**: `sys:webhook:retry`

### 8. 获取待处理事件
- **URL**: `GET /webhooks/v1/sys/pending`
- **描述**: 获取待处理的Webhook事件列表
- **需要认证**: 需要JWT认证

## Header验证规则

支持三种验证类型：

### 1. 精确匹配（exact）
```json
{
  "header_name": "X-Custom-Token",
  "header_value": "secret-token-123",
  "is_required": true,
  "validation_type": "exact"
}
```

### 2. 包含匹配（contains）
```json
{
  "header_name": "User-Agent",
  "header_value": "MyApp",
  "is_required": true,
  "validation_type": "contains"
}
```

### 3. 正则表达式匹配（regex）
```json
{
  "header_name": "X-Event-Type",
  "header_value": "^(user|order|payment)\\.(created|updated|deleted)$",
  "is_required": true,
  "validation_type": "regex"
}
```

## 签名验证

支持多种签名头格式：
- `X-Hub-Signature-256` (GitHub风格)
- `X-Signature-256` (GitLab风格)
- `X-Webhook-Signature` (自定义)
- `Signature` (通用)

签名算法：HMAC-SHA256

## 事件类型

插件支持以下预定义的事件类型：

- `user.created`: 用户创建事件
- `user.updated`: 用户更新事件
- `order.created`: 订单创建事件
- `payment.completed`: 支付完成事件

您可以根据需要在服务层添加更多事件类型的处理逻辑。

## 事件状态

- `0`: 处理失败
- `1`: 处理成功
- `2`: 待处理

## 使用示例

### 发送普通Webhook事件

```bash
curl -X POST "http://your-domain/webhooks/v1/sys/receive" \
  -H "Content-Type: application/json" \
  -H "X-Event-Type: user.created" \
  -H "X-Source: external-system" \
  -d '{
    "event_type": "user.created",
    "data": {
      "user_id": 123,
      "username": "john_doe",
      "email": "john@example.com"
    }
  }'
```

### 发送带Header验证的Webhook事件

```bash
curl -X POST "http://your-domain/webhooks/v1/sys/receive/validated?secret_key=your-secret-key" \
  -H "Content-Type: application/json" \
  -H "X-Event-Type: user.created" \
  -H "X-Source: external-system" \
  -H "X-Custom-Token: secret-token-123" \
  -H "X-Hub-Signature-256: sha256=calculated-signature" \
  -d '{
    "event_type": "user.created",
    "data": {
      "user_id": 123,
      "username": "john_doe",
      "email": "john@example.com"
    },
    "validation_rules": [
      {
        "header_name": "X-Custom-Token",
        "header_value": "secret-token-123",
        "is_required": true,
        "validation_type": "exact"
      }
    ]
  }'
```

### 生成GitHub风格签名（Python示例）

```python
import hashlib
import hmac

def generate_signature(payload: str, secret: str) -> str:
    """生成GitHub风格的签名"""
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"
```

### 查询事件列表

```bash
curl -X GET "http://your-domain/webhooks/v1/sys?event_type=user.created&status=1" \
  -H "Authorization: Bearer your-jwt-token"
```

## 数据库表结构

### sys_webhook 表

```sql
CREATE TABLE sys_webhook (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_type VARCHAR(100) NOT NULL COMMENT '事件类型',
    source VARCHAR(100) NOT NULL COMMENT '事件来源',
    webhook_url VARCHAR(500) COMMENT 'Webhook URL',
    headers JSON COMMENT '请求头信息',
    payload LONGTEXT NOT NULL COMMENT '事件数据',
    status INT DEFAULT 1 COMMENT '处理状态（0：失败、1：成功、2：待处理）',
    error_message VARCHAR(500) COMMENT '错误信息',
    processed_at VARCHAR(19) COMMENT '处理时间',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### sys_webhook_config 表

```sql
CREATE TABLE sys_webhook_config (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL COMMENT '配置名称',
    endpoint_url VARCHAR(500) NOT NULL COMMENT '接收端点URL',
    secret_key VARCHAR(255) COMMENT '密钥用于签名验证',
    required_headers JSON COMMENT '必需的请求头',
    allowed_event_types JSON COMMENT '允许的事件类型',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 安全建议

1. **使用签名验证**: 在生产环境中强烈建议启用签名验证
2. **Header验证**: 添加自定义Header验证以增强安全性
3. **HTTPS**: 确保所有Webhook通信都使用HTTPS
4. **密钥管理**: 定期轮换签名密钥
5. **IP白名单**: 在网络层面限制允许的来源IP

## 扩展开发

如需添加新的事件类型处理逻辑，请在 `webhook_service.py` 文件中的 `_process_webhook_event` 方法里添加相应的处理分支，并实现对应的处理方法。

如需自定义验证逻辑，可以扩展 `_validate_headers` 和 `_validate_signature` 方法。 