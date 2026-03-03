# 安全策略 (Security Policy)

## 支持的版本

我们会对当前主分支（main/master）的最近版本提供安全更新。

## 敏感信息

- **切勿**将 API Key、Secret、Passphrase 提交到仓库。
- 使用 `.env`（已加入 .gitignore）或环境变量存储密钥。
- 配置文件示例中不要包含真实密钥；已用 `configs/.key`、`configs/secure.enc`、`configs/*_private.json` 忽略。

## 报告漏洞

如发现安全问题，请通过 **Issue** 报告（可设为私密），或通过项目维护者提供的联系方式私下报告。请勿在公开 Issue 中粘贴密钥或敏感配置。

## 安全实践建议

1. 仅使用**测试网**进行开发与回测。
2. 为生产环境使用**只读或受限权限**的 API Key（若交易所支持）。
3. 定期轮换密钥，并避免在共享环境中使用同一套密钥。
