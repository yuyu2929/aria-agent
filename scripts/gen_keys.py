"""生成许可证密钥对（只需做一次）。

    python scripts/gen_keys.py

产出：
- aria/license_public.pem          ← 随开源代码分发（只能验签，不能伪造）
- keys/aria-license-private.pem    ← 只有你能持有；已加入 .gitignore，绝不提交

私钥泄露 = 任何人都能伪造企业许可证。请把它放进密码管理器/密钥管理服务。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aria import licensing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    private_pem, public_pem = licensing.generate_keypair()
    (ROOT / "aria" / "license_public.pem").write_text(public_pem)
    keys_dir = ROOT / "keys"
    keys_dir.mkdir(exist_ok=True)
    priv_path = keys_dir / "aria-license-private.pem"
    priv_path.write_text(private_pem)
    priv_path.chmod(0o600)
    print(f"公钥： {ROOT / 'aria' / 'license_public.pem'}（可提交）")
    print(f"私钥： {priv_path}（保密！已 gitignore，权限 600）")
    print("接下来用 scripts/issue_license.py 给付费客户签发许可证。")


if __name__ == "__main__":
    main()
