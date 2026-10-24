"""许可证签发与校验（Ed25519 非对称签名）。

设计要点：
- **验证只需公钥**——公钥随开源代码分发，能验签但**无法伪造**许可证
- **签发需要私钥**——私钥只有你（厂商）持有，**绝不能进 git**
- 开源核心（MIT）永久免费；企业版扩展（SSO/RBAC/审计导出/多租户）需要有效许可证

许可证格式：ARIA1.<base64url(payload)>.<base64url(signature)>
payload: {tier, org, seats, features, iat, exp, jti}
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFIX = "ARIA1"
PUBLIC_KEY_FILE = Path(__file__).resolve().parent / "license_public.pem"
TIER_COMMUNITY = "community"
TIER_ENTERPRISE = "enterprise"


class InvalidLicense(Exception):
    """许可证无效、被篡改或已过期。"""


@dataclass
class LicenseInfo:
    tier: str
    org: str
    seats: int
    features: list[str] = field(default_factory=list)
    issued_at: str = ""
    expires_at: str = ""
    key_id: str = ""

    @property
    def expired(self) -> bool:
        try:
            return datetime.now(timezone.utc) > datetime.fromisoformat(self.expires_at)
        except (ValueError, TypeError):
            return True

    @property
    def days_left(self) -> int:
        try:
            delta = datetime.fromisoformat(self.expires_at) - datetime.now(timezone.utc)
            return max(0, delta.days)
        except (ValueError, TypeError):
            return 0

    def has(self, feature: str) -> bool:
        return feature in (self.features or [])


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _load_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization

        return serialization, InvalidSignature
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "企业版功能需要 cryptography（企业扩展包会自带）：pip install cryptography"
        ) from exc


def generate_keypair() -> tuple[str, str]:
    """生成 Ed25519 密钥对，返回 (private_pem, public_pem)。"""
    serialization, _ = _load_crypto()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def issue(
    private_pem: str,
    org: str,
    seats: int = 10,
    features: list[str] | None = None,
    days: int = 365,
    tier: str = TIER_ENTERPRISE,
) -> str:
    """签发一张许可证（用私钥签名）。私钥绝不外泄。"""
    serialization, _ = _load_crypto()
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    now = datetime.now(timezone.utc)
    payload = {
        "tier": tier,
        "org": org,
        "seats": int(seats),
        "features": list(features or ["sso", "rbac", "audit_export", "multi_tenant"]),
        "iat": now.isoformat(),
        "exp": (now + timedelta(days=days)).isoformat(),
        "jti": _b64e(os.urandom(9)),
    }
    body = _b64e(json.dumps(payload, sort_keys=True).encode())
    signature = _b64e(private_key.sign(body.encode()))
    return f"{PREFIX}.{body}.{signature}"


def public_key() -> str | None:
    """读取随代码分发的公钥（可能未初始化）。"""
    if PUBLIC_KEY_FILE.exists():
        return PUBLIC_KEY_FILE.read_text()
    return None


def verify(key: str, public_pem: str | None = None) -> LicenseInfo:
    """校验许可证：格式 → 签名 → 过期。任何一步失败都抛 InvalidLicense。"""
    serialization, InvalidSignature = _load_crypto()
    public_pem = public_pem or public_key()
    if not public_pem:
        raise InvalidLicense("未配置许可证公钥（aria/license_public.pem）")
    try:
        prefix, body, signature = key.strip().split(".")
    except ValueError:
        raise InvalidLicense("许可证格式错误")
    if prefix != PREFIX:
        raise InvalidLicense(f"未知许可证前缀：{prefix}")

    public = serialization.load_pem_public_key(public_pem.encode())
    try:
        public.verify(_b64d(signature), body.encode())
    except InvalidSignature:
        raise InvalidLicense("签名校验失败：许可证被篡改或不是本产品签发")
    except Exception as exc:
        raise InvalidLicense(f"签名校验异常：{type(exc).__name__}")

    try:
        payload = json.loads(_b64d(body))
    except Exception:
        raise InvalidLicense("许可证内容损坏")

    info = LicenseInfo(
        tier=payload.get("tier", TIER_COMMUNITY),
        org=payload.get("org", ""),
        seats=int(payload.get("seats", 0)),
        features=list(payload.get("features") or []),
        issued_at=payload.get("iat", ""),
        expires_at=payload.get("exp", ""),
        key_id=payload.get("jti", ""),
    )
    if info.tier != TIER_ENTERPRISE:
        raise InvalidLicense(f"非企业版许可证（tier={info.tier}）")
    if info.expired:
        raise InvalidLicense(f"许可证已于 {info.expires_at} 过期")
    return info


def current() -> LicenseInfo | None:
    """读取当前许可证（环境变量 ARIA_LICENSE 或 ~/.aria/license.key）。

    无效/缺失都返回 None —— 此时运行在社区版（MIT 免费）模式。
    """
    key = os.getenv("ARIA_LICENSE", "").strip()
    if not key:
        path = Path.home() / ".aria" / "license.key"
        if path.exists():
            key = path.read_text().strip()
    if not key:
        return None
    try:
        return verify(key)
    except (InvalidLicense, RuntimeError):
        return None
