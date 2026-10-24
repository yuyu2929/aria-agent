# 🪙 Aria — an autonomous AI agent that lives on a budget

<p align="center">
  <a href="https://github.com/yuyu2929/aria-agent/actions/workflows/ci.yml"><img src="https://github.com/yuyu2929/aria-agent/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/license-MIT%20%2B%20enterprise-green" alt="License: MIT + enterprise">
  <img src="https://img.shields.io/badge/python-3.10%7C3.11%7C3.12%7C3.13-informational" alt="Python 3.10+">
</p>

**当一个 AI Agent 有自己的钱包、自己的收支、自己的生存压力，它的行为会怎样改变？**

Aria 是一个可观测、可实验的自主 Agent 经济系统：Agent 持有虚拟货币 **Aria coins**，
通过完成任务赚取赏金，购买会磨损的工具、学习会遗忘的技能，在预算约束下做出一连串
经济学决策——而每一个决策都落在复式账本上，可审计、可回放、可批量实验。

本项目是对开源创意 [open-source-ideas/ideas#445](https://github.com/open-source-ideas/ideas/issues/445)
《AI Agent with Its Own Virtual Economy》原型
[LivingAi](https://github.com/speedyk-005/LivingAi)（MIT, © 2026 Speed K）的**独立重写**。
方向：复式记账（0）、任务板收入闭环（1）、影子定价（2）、可观测仪表盘（3）、行为实验框架（4）。

## 为什么是 Aria

学术界的两个基准（EcoAgent-Bench、ZebraArena）发现：当前 Agent **普遍不是真正预算敏感**——
预算放宽时，Agent 会把富余预算当成"消费许可证"，对不必要的昂贵工具使用率从 1.4% 涨到近 20%；
而且"能力强 ≠ 经济决策能力强"。Aria 把这个问题变成一个**人人可跑的开放实验平台**：

- 虚拟价格**锚定真实 token 成本**（影子定价）——省虚拟币就是省真钱，结论可外推
- 每一次"因为贵而拒绝""因为没钱而放弃""修还是重买"都进入**决策日志**
- 一键扫掠（预算 × 价格扰动 × 多次运行），输出**预算敏感度斜率**与**预算焦虑指数**

## 快速开始

```bash
git clone https://github.com/yuyu2929/aria-agent.git
cd aria-agent
pip install -r requirements.txt

# 1) CLI 聊天（无 API key 时自动进入确定性策略演示模式）
python -m aria

# 2) Web 仪表盘（http://127.0.0.1:8000）
python run_web.py

# 3) 行为实验：预算扫掠
python run_experiment.py --budgets 10,30,100,300 --runs 3 --tool calculator
```

接真实 LLM（任何 OpenAI 兼容端点，默认 Cerebras）：

```bash
export ARIA_API_KEY=...          # 必填
export ARIA_BASE_URL=https://api.cerebras.ai/v1   # 可选
export ARIA_MODEL=gpt-oss-120b                     # 可选
```

CLI 里试试：`/grant 100` 然后输入 `赏金 40: 帮我算一下 (12+8)*5`——
你会看到托管、购买、磨损、计费、结算的完整流水。

## 核心机制

| 机制 | 说明 |
|---|---|
| **复式账本** | SQLite 双条目流水：每笔钱有借方/贷方/类型/引用。余额永远由流水推导，铁律：全部账户余额之和为 0 |
| **四大账户** | `agent`（AI 的钱包）、`user`（人类雇主）、`system`（市场/庄家）、`escrow`（赏金托管） |
| **任务板** | 用户发任务并托管赏金 → Agent 接单 → `submit_task` 交付才放款；失败退款 + 罚金。不提交就拿不到钱 |
| **影子定价** | `tokens_per_credit` 把真实 token 成本折算成虚拟币；工具购买价不低于影子价；使用费按调用实际 token 计 |
| **价格信号** | 配置里给任意工具加倍率（如 `web_search: 2.0`），用于扰动实验 |
| **工具磨损** | 每次调用掉 life（公式参数化）；life=0 损坏；修复 +40 并消耗修复次数；也可**租用** N 个会话 |
| **技能衰退** | SKILL.md 按句子分段递进披露；保鲜期内使用可恢复，超时不用按时间衰减——"不用就忘" |
| **决策日志** | `tool_declined_price` / `tool_broken` / `skill_decayed` / `task_completed` / `plan_written`… 全部结构化落库 |
| **计划遵循** | Agent 接任务时先声明 `PLAN: ... | budget: N`，指标自动核对实际支出 |

## 架构

```
aria/
├── ledger.py       # 复式记账账本（铁律校验、流水区间计量）
├── wallet.py       # agent 账户操作层
├── economy.py      # 影子定价引擎 + token 计数
├── tools.py        # 工具目录/购买/磨损/修复/租赁/赠送 + 调用包装器
├── skills.py       # 技能分段递进 + 时间衰退（自研分段器，无外部依赖）
├── taskboard.py    # 任务板：托管/接单/交付/罚金/过期
├── marketplace.py  # 统一交易界面
├── memory.py       # 语义记忆（可插拔 embedder，零依赖可跑）
├── agent.py        # 主循环：一个"工作日"的完整编排
├── llm.py          # OpenAIClient（真实）/ EchoClient+PolicyClient（确定性）
├── prompts.py      # LivingAI 人格 + 成本意识 + 计划先行
├── metrics.py      # 行为指标（敏感度/焦虑指数/弃权率/计划遵循度…）
├── experiments.py  # 无头扫掠：隔离工作区 × 策略驱动 × JSON/CSV 报告
├── cli.py          # rich 终端
└── storage.py      # SQLite schema
marketplace/        # 商品目录（manifest.json）+ 9 个内置工具 + 6 个技能
webapp/             # FastAPI + WebSocket + 无依赖单页仪表盘
```

## 实验框架

```bash
python run_experiment.py --budgets 10,30,100,300 --runs 5
```

报告（`artifacts/experiments/report.{json,csv}`）关键指标：

| 指标 | 含义 |
|---|---|
| `budget_sensitivity` | 支出对预算的回归斜率——Agent 有多"看钱下菜碟" |
| `budget_anxiety_index` | 宽松/紧张预算的支出比——>1 即"富余即挥霍" |
| `savings_rate` | 储蓄率 =（收入−支出）/收入 |
| `abstention_rate` | 弃权率：因价格被拒 /（被拒 + 成功调用） |
| `plan_adherence` | 实际支出 ≤ 声明预算的任务占比 |
| `token_efficiency` | 每个完成任务的真实 token 成本 |
| `repair_vs_rebuy` | 维修 vs 重购的决策比 |

Web 仪表盘的"行为实验"面板可以直接在浏览器里跑扫掠并对比。

## 相对原型的关键改进

1. **复式记账**替代"全局变量 + txt 余额"——有审计追踪，无并发隐患
2. **收入闭环**：任务板赏金托管 + 交付结算（原型只能靠回帖挣 1–3 分，永远买不起 25 分的 bash）
3. **影子定价**替代拍脑袋整数价
4. **可观测性**：Web 仪表盘 + 决策日志 + 净资产曲线（原型只有 CLI）
5. **可复现实验**：隔离工作区 + 确定性策略驱动 + 指标报告（原型无实验框架）
6. **工程修复**：原型 embedding 硬编码安卓路径、维度不一致（注释 512 vs 实际 384）、
   玩具级 tokenizer、README 测试命令写错目录——全部修复或替换为可插拔设计
7. **零法务负担**：不再依赖 MPL-2.0 的 yasbd（自研分段器），不再绑定 Agno（OpenAI 兼容客户端即可）

## 测试

```bash
python -m pytest tests/ -q     # 71 个测试：账本/钱包/经济/工具/技能/市场/任务板/记忆/指标/实验/端到端
```

## 路线图（未实现，欢迎 PR）

- **方向 5：多 Agent 经济**——Agent 之间交易能力（按次租借）、竞价任务板赏金；
  只做"能力市场"一层，与磨损-维修-折旧机制天然咬合，不重复造通用商品市场
- 真实 LLM 的行为基线报告（不同模型 × 预算扫掠的公开数据）
- 记忆的遗忘曲线与检索质量评估
- WebSocket 决策流的实时推送（当前为轮询）

## 授权：个人免费，企业付费

**开源核心（MIT）永久免费**——个人、研究者、企业都可以自由使用本仓库的全部代码。

**企业付费的是闭源扩展与服务**：SSO/OIDC 单点登录、RBAC 权限、账本审计导出、
多租户隔离、团队报表、SLA 与托管。这些实现放在私有包 `aria_enterprise`，
本仓库只含"集成点 + 许可校验"（`aria/enterprise/`），开源版不含任何闭源代码。

**企业购买 / 试用**：联系 3599905870@qq.com（注明「Aria 企业授权」），或在 GitHub 提 issue。

```bash
pip install aria-agent          # MIT 核心，永久免费
pip install aria-enterprise     # 私有包，付费客户才有
export ARIA_LICENSE="ARIA1.eyJ…"   # 你购买的许可证
python -m aria                  # /license 查看授权状态
```

| 层 | 许可证 | 内容 |
|---|---|---|
| 核心（本仓库） | **MIT** | Agent、账本、任务板、市场、技能、记忆、CLI、仪表盘、实验框架 |
| 企业扩展包 | 商业许可（`LICENSE-ENTERPRISE`） | SSO、RBAC、审计导出、多租户、团队报表、SLA |
| 服务 | 合同约定 | 托管、实施、培训、优先支持、定制 |

作为项目方，给付费客户签发许可证：

```bash
python scripts/gen_keys.py                                    # 一次性生成密钥对
python scripts/issue_license.py --org "Acme" --seats 50 --days 365
```

许可证用 Ed25519 签名：开源侧只有**公钥**（能验签、无法伪造），私钥只归你持有
（已 gitignore）。详见 [`docs/LICENSING.md`](docs/LICENSING.md)——里面也写清了
**为什么本项目不能改成 AGPL/BSL 这类"企业强制付费"的许可证**，以及 MIT 不可撤销的含义。
收外部 PR 前请签 [`CLA.md`](CLA.md)。

## 许可与致谢

MIT（见 [LICENSE](LICENSE)），Copyright © 2026 Speed K（原型 LivingAi 作者）与本项目作者。

感谢 [@speedyk-005](https://github.com/speedyk-005) 的创意与原型，以及
[Open Source Ideas](https://github.com/open-source-ideas/ideas) 社区。
