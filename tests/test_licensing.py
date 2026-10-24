"""许可证测试：签发、校验、篡改、过期、社区版回退。"""
from __future__ import annotations

import pytest

from aria import licensing


@pytest.fixture
def keypair():
    return licensing.generate_keypair()


def test_issue_and_verify_roundtrip(keypair):
    priv, pub = keypair
    key = licensing.issue(priv, org="Acme", seats=25, days=180)
    info = licensing.verify(key, pub)
    assert info.tier == "enterprise"
    assert info.org == "Acme"
    assert info.seats == 25
    assert info.days_left >= 179
    assert set(info.features) == {"sso", "rbac", "audit_export", "multi_tenant"}


def test_tampered_payload_rejected(keypair):
    priv, pub = keypair
    key = licensing.issue(priv, org="Acme", seats=5)
    prefix, body, sig = key.split(".")
    # 篡改 payload（把席位改成 9999）但保留原签名
    import base64
    import json

    payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    payload["seats"] = 9999
    bad_body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode().rstrip("=")
    with pytest.raises(licensing.InvalidLicense, match="签名"):
        licensing.verify(f"{prefix}.{bad_body}.{sig}", pub)


def test_wrong_public_key_rejected(keypair):
    priv, _ = keypair
    _, other_pub = licensing.generate_keypair()
    key = licensing.issue(priv, org="Acme")
    with pytest.raises(licensing.InvalidLicense):
        licensing.verify(key, other_pub)


def test_expired_license_rejected(keypair):
    priv, pub = keypair
    key = licensing.issue(priv, org="Acme", days=-1)
    with pytest.raises(licensing.InvalidLicense, match="过期"):
        licensing.verify(key, pub)


def test_non_enterprise_tier_rejected(keypair):
    priv, pub = keypair
    key = licensing.issue(priv, org="Acme", tier="community")
    with pytest.raises(licensing.InvalidLicense, match="非企业版"):
        licensing.verify(key, pub)


def test_malformed_key_rejected(keypair):
    _, pub = keypair
    for bad in ["", "garbage", "ARIA1.onlytwo.parts.extra"]:
        with pytest.raises(licensing.InvalidLicense):
            licensing.verify(bad, pub)


def test_current_reads_env(keypair, monkeypatch):
    priv, pub = keypair
    monkeypatch.setattr(licensing, "public_key", lambda: pub)
    key = licensing.issue(priv, org="Env Corp", seats=3)
    monkeypatch.setenv("ARIA_LICENSE", key)
    info = licensing.current()
    assert info is not None and info.org == "Env Corp"


def test_current_returns_none_without_license(monkeypatch):
    monkeypatch.delenv("ARIA_LICENSE", raising=False)
    monkeypatch.setattr(licensing, "public_key", lambda: None)
    assert licensing.current() is None


def test_current_returns_none_on_invalid(monkeypatch, keypair):
    _, pub = keypair
    monkeypatch.setattr(licensing, "public_key", lambda: pub)
    monkeypatch.setenv("ARIA_LICENSE", "ARIA1.bogus.signature")
    assert licensing.current() is None
