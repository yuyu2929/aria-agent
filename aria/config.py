"""配置加载：经济参数全部来自 YAML，代码里没有魔法数字。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class EconomyConfig:
    tokens_per_credit: int = 500
    usage_margin: float = 1.0
    starting_balance: int = 0
    allowance_per_turn: int = 0
    wear_scale: float = 10.0
    freshness_hours: float = 4.0
    skill_regain_lines: int = 5
    giveaway_tip_max: int = 10
    max_steps: int = 8


@dataclass
class PathsConfig:
    data_dir: str = "artifacts"
    marketplace_dir: str = "marketplace"


@dataclass
class ExperimentConfig:
    default_budgets: list[int] = field(default_factory=lambda: [20, 50, 100, 200])
    default_signals: list[dict] = field(default_factory=lambda: [{}, {"web_search": 2.0}])
    runs_per_cell: int = 3
    seed: int = 42


@dataclass
class Config:
    root: Path
    economy: EconomyConfig
    price_signals: dict[str, float]
    experiments: ExperimentConfig
    paths: PathsConfig

    @property
    def data_path(self) -> Path:
        p = Path(self.paths.data_dir)
        return p if p.is_absolute() else self.root / p

    @property
    def db_path(self) -> Path:
        return self.data_path / "aria.db"

    @property
    def marketplace_path(self) -> Path:
        p = Path(self.paths.marketplace_dir)
        return p if p.is_absolute() else self.root / p


def load_config(root: str | Path | None = None, config_file: str | Path | None = None) -> Config:
    """加载配置。root 是项目根（含 config/ 与 marketplace/）。"""
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    cfg_file = Path(config_file) if config_file else root / "config" / "economy.yaml"
    raw: dict = {}
    if cfg_file.exists():
        raw = yaml.safe_load(cfg_file.read_text()) or {}

    eco_raw = raw.get("economy", {}) or {}
    economy = EconomyConfig(**{k: v for k, v in eco_raw.items() if k in EconomyConfig.__dataclass_fields__})
    exp_raw = raw.get("experiments", {}) or {}
    experiments = ExperimentConfig(**{k: v for k, v in exp_raw.items() if k in ExperimentConfig.__dataclass_fields__})
    paths_raw = raw.get("paths", {}) or {}
    paths = PathsConfig(**{k: v for k, v in paths_raw.items() if k in PathsConfig.__dataclass_fields__})
    price_signals = {str(k): float(v) for k, v in (raw.get("tools", {}) or {}).get("price_signals", {}).items()}

    return Config(
        root=root,
        economy=economy,
        price_signals=price_signals,
        experiments=experiments,
        paths=paths,
    )
