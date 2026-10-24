# 本地联调用示例（**不要提交到开源仓库**）

`examples/enterprise_plugin/` 里的 `aria_enterprise` 是企业扩展包的**最小参考实现**，
用途只有一个：让你在本地把"企业付费门禁"整条链路跑通。

## 本地验证步骤

```bash
# 1) 装示例扩展包（模拟付费客户安装私有包）
pip install -e examples/enterprise_plugin

# 2) 导入本次交付自带的 30 天演示许可证
export ARIA_LICENSE=$(cat keys/demo-license.txt)

# 3) 查看授权状态
python -m aria
> /license

# 4) 试着调用企业功能（审计导出）
python -c "
import sys; sys.path.insert(0, '.')
from aria import enterprise
print(enterprise.status())
print(enterprise.export_audit([{'ts':'2026-01-01','amount':10}])[:60])
"

# 5) 把 ARIA_LICENSE 清空，再看一次 —— 功能应当被门禁挡住
unset ARIA_LICENSE
```

## 正式发布前

1. 把 `examples/enterprise_plugin/` 移入你的私有仓库 `aria-enterprise`
2. 根目录 `.gitignore` 已排除本目录；若你决定保留在仓库内，请删除该排除行
3. 给付费客户：`pip install aria-enterprise` + 你签发的 `ARIA_LICENSE`
