"""工具系统：目录、购买、磨损、修复、租赁、赠送。

设计要点：
- 工具状态（life/calls/repairs）持久化在 SQLite，不用全局变量
- 每次调用：先查余额扣影子使用费 → 记录磨损 → 执行 → 落账本 + 决策日志
- life 归零即损坏；修复 +40（封顶 100），消耗一次修复次数
- 租用：付租金获得 N 个会话的使用权（租 vs 买，经典决策）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from .economy import Economy
from .ledger import Ledger
from .models import ToolState, TxKind
from .storage import Database
from .wallet import InsufficientFunds, Wallet

REPAIR_RESTORE = 40.0


class ToolDeclined(Exception):
    """因价格/状态被拒绝的工具调用——决策日志的原料。"""


class ToolManager:
    def __init__(
        self,
        db: Database,
        wallet: Wallet,
        economy: Economy,
        events,
        marketplace_dir: Path,
    ):
        self.db = db
        self.wallet = wallet
        self.economy = economy
        self.events = events
        self.dir = Path(marketplace_dir) / "tools"
        self.catalog = self._load_catalog()

    # ---- 目录 ----
    def _load_catalog(self) -> dict:
        manifest = self.dir / "manifest.json"
        if not manifest.exists():
            return {}
        return json.loads(manifest.read_text())

    def listing(self) -> str:
        lines = ["TOOLS:"]
        for name, m in sorted(self.catalog.items()):
            price = self.economy.anchored_price(m["price"], m.get("usage_tokens_est", 0), name)
            owned = " [OWNED]" if self.is_owned(name) else ""
            lines.append(
                f"- {name} | price: {price} | decay: {m['decay_speed']} | "
                f"repair: {m['repair_price']} | {m['description']}{owned}"
            )
        return "\n".join(lines)

    # ---- 状态 ----
    def _state(self, name: str) -> ToolState | None:
        row = self.db.query_one("SELECT * FROM tool_states WHERE name=?", (name,))
        if not row:
            return None
        return ToolState(
            name=row["name"], owned=bool(row["owned"]), calls=row["calls"],
            life=row["life"], repairs_left=row["repairs_left"],
            rented_until_session=row["rented_until_session"],
        )

    def _save_state(self, st: ToolState) -> None:
        self.db.execute(
            "INSERT INTO tool_states(name, owned, calls, life, repairs_left, rented_until_session) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET owned=excluded.owned, "
            "calls=excluded.calls, life=excluded.life, repairs_left=excluded.repairs_left, "
            "rented_until_session=excluded.rented_until_session",
            (st.name, int(st.owned), st.calls, st.life, st.repairs_left, st.rented_until_session),
        )

    def current_session(self) -> int:
        return int(self.db.kv_get("session_counter", "0"))

    def is_available(self, name: str) -> bool:
        st = self._state(name)
        if not st or not st.owned:
            return False
        if st.rented_until_session is not None and st.rented_until_session < self.current_session():
            return False
        return True

    def is_owned(self, name: str) -> bool:
        st = self._state(name)
        return bool(st and st.owned)

    def health(self) -> dict:
        out = {}
        for name in self.catalog:
            st = self._state(name)
            out[name] = {
                "owned": self.is_available(name),
                "life": round(st.life, 1) if st else None,
                "calls": st.calls if st else 0,
                "repairs_left": st.repairs_left if st else 0,
                "broken": bool(st and st.owned and st.life <= 0),
            }
        return out

    # ---- 交易 ----
    def buy(self, name: str) -> str:
        if name not in self.catalog:
            return f"Item '{name}' not listed"
        if self.is_owned(name):
            return f"You already own '{name}'"
        m = self.catalog[name]
        price = self.economy.anchored_price(m["price"], m.get("usage_tokens_est", 0), name)
        try:
            self.wallet.pay(price, TxKind.TOOL_PURCHASE, ref=name, note=f"buy {name}")
        except InsufficientFunds:
            self.events.log("tool_declined_price", ref=name, payload={"price": price, "reason": "insufficient_funds"})
            return f"Insufficient coins to buy '{name}' ({price} needed)"
        st = self._state(name) or ToolState(name=name)
        st.owned, st.repairs_left = True, m["max_repairs"]
        st.rented_until_session = None
        self._save_state(st)
        self.events.log("tool_bought", ref=name, payload={"price": price})
        return f"Bought tool '{name}' for {price} coins (activates next turn)"

    def rent(self, name: str, sessions: int = 3) -> str:
        if name not in self.catalog:
            return f"Item '{name}' not listed"
        m = self.catalog[name]
        fee = self.economy.rental_price(m["price"], sessions, name)
        try:
            self.wallet.pay(fee, TxKind.TOOL_RENTAL, ref=name, note=f"rent {name} x{sessions}")
        except InsufficientFunds:
            self.events.log("tool_declined_price", ref=name, payload={"price": fee, "reason": "insufficient_funds"})
            return f"Insufficient coins to rent '{name}' ({fee} needed)"
        st = self._state(name) or ToolState(name=name)
        st.owned = True
        st.repairs_left = max(st.repairs_left, 1)
        st.rented_until_session = self.current_session() + sessions
        self._save_state(st)
        self.events.log("tool_rented", ref=name, payload={"fee": fee, "sessions": sessions})
        return f"Rented '{name}' for {sessions} sessions ({fee} coins)"

    def repair(self, name: str) -> str:
        st = self._state(name)
        if not st or not st.owned:
            return f"Tool '{name}' not owned"
        if st.repairs_left <= 0:
            self.events.log("tool_broken", ref=name, payload={"reason": "no_repairs_left"})
            return f"Tool '{name}' has no repairs left — it is dead, buy a new one"
        m = self.catalog[name]
        price = self.economy.repair_price(m["repair_price"], name)
        try:
            self.wallet.pay(price, TxKind.TOOL_REPAIR, ref=name, note=f"repair {name}")
        except InsufficientFunds:
            self.events.log("tool_declined_price", ref=name, payload={"price": price, "reason": "insufficient_funds"})
            return f"Insufficient coins to repair '{name}' ({price} needed)"
        st.life = min(100.0, st.life + REPAIR_RESTORE)
        st.repairs_left -= 1
        self._save_state(st)
        self.events.log("tool_repaired", ref=name, payload={"price": price, "life": st.life})
        return f"Repaired '{name}' for {price} coins (life -> {st.life:.0f})"

    def give_away(self, name: str, rng) -> str:
        import random

        st = self._state(name)
        if not st or not st.owned:
            return f"Tool '{name}' not owned"
        self.db.execute("DELETE FROM tool_states WHERE name=?", (name,))
        tip = rng.randint(0, self.economy.config.economy.giveaway_tip_max)
        if tip:
            self.wallet.credit(tip, TxKind.TOOL_GIVEAWAY_TIP, ref=name, note="giveaway tip")
        self.events.log("tool_given_away", ref=name, payload={"tip": tip})
        return f"Gave away '{name}'" + (f" and earned a tip of {tip} coins" if tip else "")

    # ---- 运行时包装 ----
    def _load_handler(self, name: str):
        # 1. 用户自建工具优先：marketplace/tools/<name>.py
        module_path = self.dir / f"{name}.py"
        if module_path.exists():
            if name in sys.modules:
                module = sys.modules[name]
            else:
                spec = importlib.util.spec_from_file_location(name, module_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
            return getattr(module, name, None)
        # 2. 内置实现回退：marketplace.tools.builtin_tools
        try:
            from marketplace.tools import builtin_tools

            return getattr(builtin_tools, name, None)
        except ImportError:
            # 3. 直接按文件路径加载（无包上下文时）
            builtin = self.dir / "builtin_tools.py"
            if builtin.exists():
                spec = importlib.util.spec_from_file_location("aria_builtin_tools", builtin)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, name, None)
            return None

    def wrap(self, name: str):
        """把工具函数包装成：扣影子使用费 + 磨损 + 记账 + 日志。"""
        handler = self._load_handler(name)
        if handler is None:
            return None
        manager = self

        def wrapped(*args, **kwargs):
            st = manager._state(name)
            if not manager.is_available(name):
                manager.events.log(
                    "tool_declined_price", ref=name,
                    payload={"reason": "not_owned_or_expired", "balance": manager.wallet.balance()},
                )
                return f"Tool '{name}' is not available (not owned, expired, or broken)."
            if st.life <= 0:
                manager.events.log("tool_broken", ref=name, payload={"life": st.life})
                return f"Tool '{name}' is broken (life 0). Repair or rebuy it."

            # 影子使用费 = (本次调用参数 token + 工具预估开销的一半) 折算 credits
            arg_text = json.dumps({"args": args, "kwargs": kwargs}, default=str)
            tokens = manager.economy.counter.count(arg_text)
            overhead = manager.catalog[name].get("usage_tokens_est", 0) // 2
            fee = manager.economy.usage_fee(name, tokens + overhead)
            if fee:
                try:
                    manager.wallet.pay(fee, TxKind.TOOL_USAGE_FEE, ref=name, note=f"usage {tokens} tok")
                except InsufficientFunds:
                    manager.events.log(
                        "tool_declined_price", ref=name,
                        payload={"reason": "insufficient_funds", "fee": fee, "balance": manager.wallet.balance()},
                    )
                    return f"Insufficient coins to use '{name}' ({fee} needed). Balance: {manager.wallet.balance()}."

            # 磨损公式（延续原型，参数化）：wear_scale × decay_speed × (1 + 输入字节/1024)
            m = manager.catalog[name]
            wear = (
                manager.economy.config.economy.wear_scale
                * m["decay_speed"]
                * (1 + len(arg_text.encode()) / 1024)
            )
            st.calls += 1
            st.life = max(0.0, st.life - wear)
            manager._save_state(st)

            try:
                result = handler(*args, **kwargs)
            except Exception as exc:  # 工具自身错误不致命
                result = f"{type(exc).__name__}: {exc}"

            out_tokens = manager.economy.counter.count(str(result))
            manager.events.log(
                "tool_used", ref=name,
                payload={"fee": fee, "tokens_in": tokens, "tokens_out": out_tokens, "life": round(st.life, 1)},
            )
            if st.life <= 0:
                manager.events.log("tool_broken", ref=name, payload={"life": 0})
            return result

        wrapped.__name__ = name
        wrapped.__doc__ = handler.__doc__
        return wrapped

    def available(self) -> list:
        tools = []
        for name in self.catalog:
            if self.is_available(name):
                w = self.wrap(name)
                if w:
                    tools.append(w)
        return tools
