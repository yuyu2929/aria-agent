# ⚠️ 私钥目录——禁止提交到任何代码仓库

`aria-license-private.pem` 是**签发企业许可证的私钥**。
任何拿到它的人都能伪造无限量企业许可证。

## 规矩

1. 已在根目录 `.gitignore` 中排除，请勿 `git add -f`
2. 不要放进 Docker 镜像、CI 日志、前端包、客户交付物
3. 建议放进密码管理器或云 KMS（AWS KMS / GCP Secret Manager / Vault）
4. 泄露后：重新生成密钥对（`python scripts/gen_keys.py`）并**给所有存量客户重签**许可证
   （旧公钥失效意味着旧许可证失效，务必先通知客户）

`aria/license_public.pem` 是公钥，**可以且必须**随代码分发——它只能验签，无法伪造。

`demo-license.txt` 是本次交付自带的一张 30 天演示许可证，用于本地验证门禁是否工作。
