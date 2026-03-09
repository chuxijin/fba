# OSS

云存储上传插件，当前支持：
- 阿里云 OSS
- 七牛云 Kodo

## 接口

- `POST /api/v1/oss/upload`
- API 层只有这一套，由 `sys_config` 决定实际 provider
- 返回字段包含：
  - `url`：访问地址
  - `object_key`：对象 key（建议前端保存，用于后续删除/管理）

### 表单参数

- `file`：必填，上传文件
- `path`：可选，上传子目录，例如 `test/images/2026`
- `url_expire_seconds`：可选，覆盖本次签名 URL 有效期（秒）
- `object_expire_days`：可选，覆盖本次对象过期天数

## sys_config 动态配置

建议 `type=STORAGE`，常用 key：

- `STORAGE_CONFIG_STATUS`：`1` 开启动态配置，`0` 关闭
- `STORAGE_PROVIDER`：`aliyun_oss` / `qiniu_kodo`
- `STORAGE_KEY_PREFIX`：对象 key 前缀（例如 `test`）
- `STORAGE_USE_SIGNED_URL`：`true` / `false`
- `STORAGE_SIGNED_URL_EXPIRE_SECONDS`：签名 URL 有效期（秒）
- `STORAGE_OBJECT_EXPIRE_DAYS`：对象过期天数（0 表示不设置）

## 环境变量

阿里云：
- `OSS_ACCESS_KEY`
- `OSS_SECRET_KEY`
- `OSS_BUCKET_NAME`
- `OSS_ENDPOINT`

七牛云：
- `QINIU_KODO_ACCESS_KEY`
- `QINIU_KODO_SECRET_KEY`
- `QINIU_KODO_BUCKET`
- `QINIU_KODO_DOMAIN`
- `QINIU_KODO_USE_HTTPS`（可选，默认 `true`）

## 过期策略说明

- `url_expire_seconds` / `STORAGE_SIGNED_URL_EXPIRE_SECONDS` 只控制访问 URL 有效期，不删除文件。
- `object_expire_days` / `STORAGE_OBJECT_EXPIRE_DAYS` 控制对象自动过期：
  - 七牛云：通过上传策略 `deleteAfterDays` 生效。
  - 阿里云：上传接口不支持按对象直接设置，请在 Bucket 生命周期规则中按前缀配置。
