# 微信公众号素材中转

使用服务器固定出口 IP 调用微信公众号文章图片上传接口，解决本地 IP 不在公众号白名单时无法上传的问题。支持任意公众号账号，服务器不保存任何公众号信息。

## 原理

图片不保存在服务器，也不做任何持久化：

1. 客户端用共享密钥 AES-GCM 加密 `{appid, appsecret, iat}` 得到 `payload`。
2. 服务器解密并校验时间戳（防重放）后，向微信获取该账号的 `access_token`。
3. 服务器把图片流式转发到微信 `media/uploadimg`。
4. 服务器只返回微信生成的永久图片 URL，不保留图片和凭证。

加密凭证同时充当鉴权：没有共享密钥的请求无法构造有效 `payload`，请求会被拒绝。

## 配置

服务器 `.env` 只需一个通用密钥（非公众号信息）：

```env
WECHAT_MEDIA_SECRET_KEY=<与客户端一致的 32 字节密钥 base64>
WECHAT_MEDIA_IMAGE_SIZE_MAX=10485760
```

生成密钥：

```bash
python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
```

服务器出口 IP 需要加入对应公众号的 IP 白名单。

## 接口

- `POST /api/v1/wechat/media/test`：表单字段 `payload`，验证凭证并能获取 access_token
- `POST /api/v1/wechat/media/upload`：multipart 字段 `file` + 表单字段 `payload`

`payload` 为客户端 AES-GCM 加密结果，格式为 `base64(nonce(12) + ciphertext + tag(16))`，明文为 JSON：

```json
{
  "appid": "wx...",
  "appsecret": "...",
  "iat": 1710000000
}
```

上传成功返回：

```json
{
  "code": 200,
  "msg": "请求成功",
  "data": {
    "url": "https://mmbiz.qpic.cn/..."
  }
}
```

微信 `media/uploadimg` 没有对应的服务端图片删除流程。
