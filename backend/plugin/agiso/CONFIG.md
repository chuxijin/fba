# 阿奇索插件配置说明

## 1. 环境变量配置

在项目根目录的 `.env` 文件中添加以下配置：

```env
# 阿奇索配置
AGISO_APP_SECRET=your_app_secret_here
```

**获取 AppSecret 方法：**
1. 登录阿奇索开放平台
2. 进入开发者中心
3. 复制您的 AppSecret

## 2. 数据库初始化

执行对应数据库的 SQL 脚本：

**MySQL：**
```bash
mysql -u your_user -p your_database < backend/plugin/agiso/sql/mysql.sql
```

**PostgreSQL：**
```bash
psql -U your_user -d your_database -f backend/plugin/agiso/sql/postgresql.sql
```

## 3. 阿奇索后台配置

登录阿奇索后台，配置推送地址：

### 统一推送地址（推荐）
```
https://your-domain.com/api/v1/agiso/webhooks/delivery
```

**说明：**
- 阿奇索只能配置一个推送地址
- 系统会自动识别推送类型（支付推送或发卡推送）
- 识别逻辑：
  - 包含 `Cards` 字段 → 发卡推送
  - 包含 `Payment` 字段 → 支付推送

**注意事项：**
- 推送地址必须是公网可访问的 HTTPS 地址
- 推送地址需要在阿奇索后台的「推送设置」中配置
- 支付推送类型码：2097152（买家付款）

## 4. 测试推送

### 测试工具

可以使用以下命令测试推送接口：

**测试支付推送：**
```bash
curl -X POST "http://your-domain.com/api/v1/agiso/webhooks/delivery?timestamp=1234567890&sign=YOUR_SIGN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'json={"Tid":2067719225654838,"Status":"WAIT_SELLER_SEND_GOODS","SellerNick":"测试店铺","BuyerNick":"测试买家","Payment":"100.00","Type":"fixed"}'
```

**说明**：
- 表单字段名保持为 `json`（阿奇索推送的标准字段名）
- 系统内部使用 `json_data` 变量名以避免与 Pydantic 内置方法冲突

**测试发卡推送：**
```bash
curl -X POST "http://your-domain.com/api/v1/agiso/webhooks/delivery?timestamp=1234567890&sign=YOUR_SIGN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'json={"Tid":2067719225654838,"Status":"TRADE_FINISHED","BuyerNick":"测试买家","Cards":[{"card_no":"CARD001","card_pwd":"PWD123","card_value":"100"}]}'
```

### 签名计算

签名计算方式（Python 示例）：

```python
import hashlib

app_secret = "your_app_secret"
json_str = '{"Tid":2067719225654838,...}'
timestamp = "1234567890"

sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
```

## 5. 查看推送日志

所有推送记录都会保存在 `agiso_push_log` 表中，包括：
- 推送类型（支付/发卡）
- 订单编号
- 原始推送数据
- 处理状态（待处理/成功/失败）
- 错误信息
- 重试次数

可通过数据库直接查询：

```sql
SELECT * FROM agiso_push_log ORDER BY created_time DESC LIMIT 10;
```

## 6. 常见问题

### Q: 签名验证失败？
A:
1. 检查 `.env` 文件中的 `AGISO_APP_SECRET` 是否正确
2. 确认推送数据中的 json 参数没有被修改
3. 检查 timestamp 参数是否一致

### Q: 推送后没有创建订单？
A:
1. 查看 `agiso_push_log` 表中的错误信息
2. 检查 `app_order` 表的 `package_id` 是否存在（默认为 1）
3. 查看应用日志中的错误堆栈

### Q: 如何关联具体的会员套餐？
A:
当前代码中 `package_id` 默认为 1，您需要根据实际业务修改 `webhook_service.py` 中的逻辑，
可以：
1. 在阿奇索订单中添加套餐ID字段
2. 在推送数据的 remark 或自定义字段中传递套餐信息
3. 根据订单金额匹配对应的套餐

## 7. 生产环境注意事项

1. **启用 HTTPS**：阿奇索推送要求使用 HTTPS
2. **配置防火墙**：确保推送地址可以被阿奇索服务器访问
3. **监控日志**：定期检查推送日志，及时发现问题
4. **幂等性**：推送可能会重复，已通过订单号做了去重处理
5. **异常重试**：失败的推送会记录重试次数，可手动重新处理
