"""市场：Agent 面对的统一交易界面（工具 + 技能）。

所有交易都过账本；所有拒绝都留决策日志。
"""
from __future__ import annotations

import random

from .skills import SkillManager
from .tools import ToolManager


class Marketplace:
    def __init__(self, tools: ToolManager, skills: SkillManager, rng: random.Random | None = None):
        self.tools = tools
        self.skills = skills
        self.rng = rng or random.Random()

    def list_items(self) -> str:
        return self.tools.listing() + "\n\n" + self.skills.listing()

    def buy(self, item_name: str, type: str | None = None) -> str:
        in_tools = item_name in self.tools.catalog
        in_skills = item_name in self.skills.catalog
        if type is None:
            if in_tools and in_skills:
                return f"Both a tool and a skill named '{item_name}' exist; specify type"
            type = "tool" if in_tools else "skill"
        if type == "tool":
            return self.tools.buy(item_name)
        return self.skills.buy(item_name)

    def repair_tool(self, tool_name: str) -> str:
        return self.tools.repair(tool_name)

    def give_away_tool(self, tool_name: str) -> str:
        return self.tools.give_away(tool_name, self.rng)

    def rent_tool(self, tool_name: str, sessions: int = 3) -> str:
        return self.tools.rent(tool_name, sessions)
