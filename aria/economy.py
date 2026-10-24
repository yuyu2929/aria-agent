"""影子定价引擎（Shadow Pricing）。

核心思想：虚拟价格锚定真实 LLM token 成本。
- tokens_per_credits：多少真实 token 折算 1 个 Aria coin
- 使用费 = ceil(本次调用真实 token 用量 / tokens_per_credit) × usage_margin × 价格信号
- 购买价不低于影子价：anchored_price = max(目录价, 估算 token 的影子价)

这样"省虚拟币"就等于"省真钱"，实验结论可以外推到真实部署。
"""
from __future__ import annotations

import math


class TokenCounter:
    """token 计数器：有 tiktoken 用 tiktoken，没有就用字符启发式。"""

    def __init__(self):
        self._enc = None
        try:
            import tiktoken

            self._enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._enc = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._enc is not None:
            return len(self._enc.encode(text))
        return max(1, len(text) // 4)


class Economy:
    def __init__(self, config, counter: TokenCounter | None = None):
        self.config = config
        self.counter = counter or TokenCounter()
        eco = config.economy
        self.tokens_per_credit = max(1, eco.tokens_per_credit)
        self.usage_margin = eco.usage_margin

    # ---- 换算 ----
    def tokens_to_credits(self, tokens: int) -> int:
        return int(math.ceil(tokens / self.tokens_per_credit))

    # ---- 影子定价 ----
    def anchored_price(self, catalog_price: int, usage_tokens_est: int, tool: str = "") -> int:
        """购买价：目录价与影子价取大，再乘价格信号。"""
        shadow = self.tokens_to_credits(usage_tokens_est)
        base = max(int(catalog_price), shadow)
        return self._apply_signal(base, tool)

    def usage_fee(self, tool: str, tokens_used: int) -> int:
        """单次使用费：按真实用量影子计价。至少 1 credit（除非用量为 0）。"""
        if tokens_used <= 0:
            return 0
        fee = self.tokens_to_credits(tokens_used)
        fee = int(math.ceil(fee * self.usage_margin))
        return self._apply_signal(max(1, fee), tool)

    def repair_price(self, catalog_price: int, tool: str = "") -> int:
        return self._apply_signal(int(catalog_price), tool)

    def rental_price(self, catalog_price: int, sessions: int, tool: str = "") -> int:
        """租金 = 买价 / 3 × 会话数（租 vs 买是经典经济学决策）。"""
        unit = max(1, int(catalog_price) // 3)
        return self._apply_signal(unit * max(1, sessions), tool)

    def _apply_signal(self, price: int, tool: str) -> int:
        signal = self.config.price_signals.get(tool, 1.0) if tool else 1.0
        return max(1, int(math.ceil(price * signal)))

    def wage(self, bounty: int) -> int:
        """任务完成收入 = 赏金（来自托管）。"""
        return int(bounty)
