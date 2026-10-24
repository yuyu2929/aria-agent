"""给付费客户签发许可证（这是你"企业付费"的交付动作）。

    python scripts/issue_license.py --org "Acme 科技" --seats 50 --days 365
    python scripts/issue_license.py --org "Acme" --seats 50 --features sso,audit_export

功能列表：sso（单点登录）、rbac（权限）、audit_export（审计导出）、multi_tenant（多租户）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aria import licensing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = ROOT / "keys" / "aria-license-private.pem"
ALL = ["sso", "rbac", "audit_export", "multi_tenant"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True, help="客户组织名（会显示在许可证里）")
    ap.add_argument("--seats", type=int, default=10, help="席位数")
    ap.add_argument("--days", type=int, default=365, help="有效期天数")
    ap.add_argument("--features", default=",".join(ALL), help="授权的功能，逗号分隔")
    ap.add_argument("--private-key", default=str(KEY_FILE))
    args = ap.parse_args()

    priv_path = Path(args.private_key)
    if not priv_path.exists():
        print(f"找不到私钥 {priv_path}，请先运行 python scripts/gen_keys.py")
        raise SystemExit(1)

    features = [f.strip() for f in args.features.split(",") if f.strip()]
    unknown = [f for f in features if f not in ALL]
    if unknown:
        print(f"未知功能：{unknown}；可用：{ALL}")
        raise SystemExit(1)

    key = licensing.issue(
        priv_path.read_text(), org=args.org, seats=args.seats,
        features=features, days=args.days,
    )
    info = licensing.verify(key)
    print("=" * 72)
    print(f"客户：{info.org}   席位：{info.seats}   有效期至：{info.expires_at[:10]}（{info.days_left} 天）")
    print(f"功能：{', '.join(info.features)}")
    print("-" * 72)
    print(key)
    print("=" * 72)
    print("交付方式：把上面这串密钥发给客户，让他们运行")
    print('  export ARIA_LICENSE="<密钥>"   或写入 ~/.aria/license.key')


if __name__ == "__main__":
    main()
