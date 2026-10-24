"""企业版门禁测试：无许可/无扩展包 → 禁用；有效许可 + 扩展包 → 启用。"""
from __future__ import annotations

import sys
import types

import pytest

from aria import enterprise, licensing


@pytest.fixture
def keypair():
    return licensing.generate_keypair()


@pytest.fixture
def fake_plugin():
    """模拟已安装的企业扩展包（真实实现在你的私有仓库）。"""
    mod = types.ModuleType("aria_enterprise")
    mod.export_audit = lambda rows, fmt="csv": "CSV:" + ",".join(rows[0].keys()) if rows else ""
    mod.tenant_scope = lambda tenant: {"tenant": tenant, "db_path": f"/tmp/{tenant}.db"}
    sys.modules["aria_enterprise"] = mod
    yield mod
    sys.modules.pop("aria_enterprise", None)


def _activate(monkeypatch, keypair, org="Acme Corp", days=30):
    priv, pub = keypair
    monkeypatch.setattr(licensing, "public_key", lambda: pub)
    monkeypatch.setenv("ARIA_LICENSE", licensing.issue(priv, org=org, days=days))


def test_community_by_default(monkeypatch):
    monkeypatch.delenv("ARIA_LICENSE", raising=False)
    monkeypatch.setattr(licensing, "public_key", lambda: None)
    st = enterprise.status()
    assert st["tier"] == "community"
    assert st["license_valid"] is False
    assert all(not f["enabled"] for f in st["features"].values())


def test_gate_blocks_without_plugin(monkeypatch, keypair):
    _activate(monkeypatch, keypair)
    assert enterprise.is_enabled("audit_export") is False  # 许可证有效但没装扩展包
    with pytest.raises(enterprise.EnterpriseRequired):
        enterprise.export_audit([{"ts": "x", "amount": 1}])


def test_gate_blocks_without_license(monkeypatch, fake_plugin):
    monkeypatch.delenv("ARIA_LICENSE", raising=False)
    monkeypatch.setattr(licensing, "public_key", lambda: None)
    assert enterprise.is_enabled("sso") is False
    with pytest.raises(enterprise.EnterpriseRequired):
        enterprise.tenant_scope("team-a")


def test_unlocked_with_license_and_plugin(monkeypatch, keypair, fake_plugin):
    _activate(monkeypatch, keypair, org="Acme Corp")
    st = enterprise.status()
    assert st["tier"] == "enterprise"
    assert st["org"] == "Acme Corp"
    assert st["seats"] == 10
    assert all(f["enabled"] for f in st["features"].values())
    # 真正调用企业能力
    assert enterprise.export_audit([{"ts": "x", "amount": 1}]).startswith("CSV:")
    assert enterprise.tenant_scope("team-a")["tenant"] == "team-a"


def test_expired_license_locks_features(monkeypatch, keypair, fake_plugin):
    _activate(monkeypatch, keypair, days=-1)
    assert enterprise.status()["tier"] == "community"
    with pytest.raises(enterprise.EnterpriseRequired):
        enterprise.export_audit([{"ts": "x"}])


def test_partial_features(monkeypatch, keypair, fake_plugin):
    priv, pub = keypair
    monkeypatch.setattr(licensing, "public_key", lambda: pub)
    monkeypatch.setenv(
        "ARIA_LICENSE",
        licensing.issue(priv, org="Partial", features=["audit_export"]),
    )
    assert enterprise.is_enabled("audit_export") is True
    assert enterprise.is_enabled("sso") is False  # 没买的功能不解锁


def test_upgrade_message_is_actionable(monkeypatch):
    monkeypatch.delenv("ARIA_LICENSE", raising=False)
    monkeypatch.setattr(licensing, "public_key", lambda: None)
    try:
        enterprise.export_audit([{"ts": "x"}])
    except enterprise.EnterpriseRequired as exc:
        msg = str(exc)
        assert "企业版" in msg and "ARIA_LICENSE" in msg and "pip install" in msg
    else:
        pytest.fail("应当被门禁拦住")
