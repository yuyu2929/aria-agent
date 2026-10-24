"""企业版扩展的**集成层**（开源侧，MIT）。

开源仓库只放"集成点 + 许可校验"；真正的企业实现放在私有包 `aria_enterprise`
（企业内部发布，pip 安装后由本模块动态加载）。

这样分层的原因：
- 个人/社区：核心功能永久免费（MIT），不依赖任何闭源代码
- 企业：购买许可证后安装私有扩展包，解锁 SSO / RBAC / 审计导出 / 多租户

未安装扩展包或无有效许可证 → 功能禁用，并给出明确的升级提示（不会静默降级）。
"""
from __future__ import annotations

from functools import wraps

from .. import licensing

FEATURES = {
    "sso": "单点登录（SAML/OIDC）",
    "rbac": "角色与权限控制（RBAC）",
    "audit_export": "账本审计导出（CSV/JSON，合规用）",
    "multi_tenant": "多租户隔离（按团队隔离钱包与账本）",
}

_PLUGIN_NAME = "aria_enterprise"


class EnterpriseRequired(Exception):
    """功能属于企业版：未安装扩展包或许可证无效。"""


def _upgrade_message(feature: str) -> str:
    return (
        f"「{FEATURES.get(feature, feature)}」属于 Aria 企业版功能。\n"
        f"  1) 获取许可证（含组织名/席位数/有效期）\n"
        f"  2) 安装私有扩展包：pip install {_PLUGIN_NAME}\n"
        f"  3) 设置环境变量 ARIA_LICENSE=<你的许可证>\n"
        f"开源核心（MIT）永久免费，企业付费的是上述闭源扩展与服务。"
    )


def plugin():
    """加载已安装的企业扩展包；未安装返回 None。"""
    import importlib

    try:
        return importlib.import_module(_PLUGIN_NAME)
    except ImportError:
        return None


def license_info():
    return licensing.current()


def is_enabled(feature: str) -> bool:
    """功能是否可用：有效许可证 + 已装扩展包 + 该功能在授权范围内。"""
    info = license_info()
    if info is None or info.expired:
        return False
    if not info.has(feature):
        return False
    return plugin() is not None


def require(feature: str):
    """装饰器：企业功能门禁。"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_enabled(feature):
                raise EnterpriseRequired(_upgrade_message(feature))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def status() -> dict:
    """当前授权状态（CLI/Web 展示用）。"""
    info = license_info()
    installed = plugin() is not None
    return {
        "tier": licensing.TIER_ENTERPRISE if (info and installed) else licensing.TIER_COMMUNITY,
        "license_valid": bool(info and not info.expired),
        "plugin_installed": installed,
        "org": info.org if info else "",
        "seats": info.seats if info else 0,
        "days_left": info.days_left if info else 0,
        "expires_at": info.expires_at if info else "",
        "features": {
            name: {"description": desc, "enabled": is_enabled(name)}
            for name, desc in FEATURES.items()
        },
    }


# ---- 企业能力的开源侧入口（实现在私有包里）----
@require("audit_export")
def export_audit(rows: list[dict], fmt: str = "csv") -> str:
    """导出账本审计记录——实现由企业扩展包提供。"""
    return plugin().export_audit(rows, fmt=fmt)


@require("multi_tenant")
def tenant_scope(tenant: str):
    """按租户隔离的状态命名空间——实现由企业扩展包提供。"""
    return plugin().tenant_scope(tenant)
