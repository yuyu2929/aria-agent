# Issue #445《AI Agent with Its Own Virtual Economy》深度调研报告

> 调研时间：2026-10-20 ｜ 调研对象：[open-source-ideas/ideas#445](https://github.com/open-source-ideas/ideas/issues/445) 及其原型 [speedyk-005/LivingAi](https://github.com/speedyk-005/LivingAi)

---

## 一、这个链接是什么

这是 GitHub 社区项目 **Open Source Ideas** 的第 445 号 Issue，标题为 **"AI Agent with Its Own Virtual Economy"（拥有自己虚拟经济的 AI Agent）**。

这个社区的模式很特别：**整个仓库不用来放代码，而是用 GitHub Issues 收集"开源项目创意"**。每个 Issue 就是一个待领走的项目点子，附有难度、工作量、技术分类标签。README 显示社区已积累 **200+ 个创意**，并促成了 **11 个真实项目落地**（见仓库的 Completed Hall of Fame，如 pagecli.com、projectunicorn.net 等）。项目始于 2016 年（最初由 @mikaelbr 发起），理念来自一篇 HackerNoon 文章：对开源贡献者来说，限制因素从来不是好点子，而是时间——让有点子没时间的人和有时间没点子的人互补。

---

## 二、Issue #445 核心内容

### 2.1 元数据

| 项目 | 值 |
|---|---|
| 作者 | [@speedyk-005](https://github.com/speedyk-005)（与仓库无隶属关系，NONE） |
| 创建时间 | 2026-10-07 22:59 UTC |
| 状态 | **open（开放待领走）** |
| 评论 / 反应 / 标签 / 认领人 | 0 / 0 / 无 / 无 |
| 最后更新 | 2026-10-09 |

### 2.2 核心思想

> **"如果一个 AI agent 拥有自己的假钱，并且必须用这些钱去完成目标，会发生什么？当智能和工具不再免费时，agent 的行为会如何改变？"**

具体设想：构建一个可通过 **CLI 或 Web UI** 交互的自主 Agent。它持有有限量的虚拟货币（无真实价值，纯约束机制/游戏化机制），需要挣钱、花钱、做财务决策：

- 以有限的初始资金开局
- 通过完成任务**赚取**虚拟货币
- 花钱**使用/获取**工具
- **购买技能**或其他能力
- 付费**修复/维护**能力（工具会磨损）
- 自行决定**储蓄还是消费**
- 余额和状态**跨会话持久化**
- 未来可能与其他 Agent **交易**

Issue 中给出的典型决策场景：

> "我有 30 credits。一次网络搜索花 10 credits，修复我的文件写入工具花 15。哪个对我当前任务更重要？"

作者描绘的远期愿景是一个**小型模拟经济**：agent 通过工作挣钱、买卖能力、签订合约、互相交易、对供需做出反应。

### 2.3 作者的真实诉求（重要）

作者明确说明了三点：

1. 原型**不是**完整实现，是粗糙的概念验证（POC），实验了虚拟钱包、工具成本、工具磨损与修复、技能、市场、持久记忆和 agent 界面；
2. 原型"错误处理粗糙、逻辑和 agent 流程不稳健、prompt 工程可大幅改进"，作者自认为没有足够的 prompt 工程和自主 agent 设计经验来独立完成完整 redesign 和长期维护；
3. **这个 idea 的目标不是维护现有原型**，而是给对 AI agent 和模拟经济感兴趣的人一个"不必从零开始"的起点。架构、LLM 提供商、agent 框架、UI 全部开放。

即：**这是一个"求接手"的 idea，而非"求贡献"的项目**。

### 2.4 模板遗留问题（细节）

按仓库惯例，Issue 应标注工作量（Little/Medium/Much work）、难度（Beginner/Intermediate/Advanced）和技术分类标签。但 #445 **没有打任何标签**，且正文中 Complexity / ETA / Categories 三节把模板的**所有选项原样罗列**（三档难度、三档工作量、16 个分类全列），未作选择。这意味着该 Issue 在仓库里较难被标签检索到，是作者提交时的疏忽。

仓库内主题相近的 Issue：#78《Nile: decentralized, commission-free, local-economy focused ecommerce》（去中心化本地经济电商，方向不同）；未发现其他"agent 经济"主题的重复 idea。

---

## 三、原型项目 LivingAi 全景

### 3.1 概况

- **定位**（README 原话）："A prototype autonomous agent with a persistent identity, an economy, and evolving capabilities. LivingAI treats itself as a person born in a bot skin"——LivingAI 把自己当作"生在机器人皮囊里的人"：赚取和花费 credits、购买和修复工具、学习技能、跨运行保持语义记忆。
- **时间线**：2026-08-04 initial commit，几乎全部核心代码在**同一天**提交（一个密集的冲刺）；2026-10-07 清理 embedding 脚本注释（与 Issue 创建同日）。
- **技术栈**：Python + [Agno](https://github.com/agno-agi/agno)（agent 框架）+ Cerebras 的 `gpt-oss-120b` 模型 + loguru + rich + tiktoken + VectorLiteDB + ONNX Runtime + [YASBD](https://github.com/speedyk-005/yasbd-lib)（作者自研的句子边界检测库）。
- **许可证**：MIT（Copyright (c) 2026 Speed K）。
- **测试**：4 个测试文件，覆盖市场交易（购买/修复/赠送/余额不足）、工具磨损与修复、技能分段与衰退、记忆系统（存取/检索/过滤）。

### 3.2 系统架构

```
main.py ── Agno Team（多 agent 协作）
├── lead agent（LivingAI 本体：身份 + 经济 + 工具）
│   ├── instructions：BASE_INSTRUCT 人格提示词 + 运行时余额注入 + 技能清单
│   ├── tools：ToolManager 包装后的工具 + marketplace 交易工具 + use_skill
│   └── post_hooks：billing_hook（每次回答后给 agent 计账发薪）
└── memory_agent（独立记忆 agent：语义记忆的存/取/删）
持久化状态（artifacts/ 目录）：
├── agent_balance.txt   钱包余额（一个纯数字）
├── tool_usage.json     工具登记表（calls/life/repairs/decay_speed/usage_price）
├── skill_usage.json    技能登记表（calls/available_lines/last_date_called...）
├── session.db          会话历史（SqliteDb，保留最近 15 轮）
└── records.db          记忆向量库（VectorLiteDB，384 维，L2 距离）
```

### 3.3 经济机制拆解（原型的实际规则）

**1. 钱包（wallet.py）**
- 只记 agent 一个余额，**初始为 0**，持久化为 `artifacts/agent_balance.txt` 里的一个整数；"用户方是隐形的、无限的"。
- `agent_credit` / `agent_debit`（余额不足抛 ValueError）。
- 代码用模块级全局变量 `BALANCE` 持有状态，无事务日志、无并发保护。

**2. 赚钱：billing_hook（main.py 的后置钩子）**
每轮回答结束后给 agent 发薪：
- 每条消息 +1 分；
- 回答超过 512 token（tiktoken cl100k_base 计）再 +1 分；
- 每使用一个付费工具再 +1 分（查余额免费）。
- 注释里写着 "Award agent credits and debit user the same amount"（给用户记支出），但用户侧钱包实际上是隐形的——**目前 agent 基本只能靠"回答用户问题"挣钱**。

**3. 工具磨损与修复（tool_manager.py）**
- 每个工具登记 `calls`、`life`（初始 100）、`repairs`、`decay_speed`、`usage_price`。
- 每次调用包装器：先扣 `usage_price`（如有），再按公式磨损：
  `wear = decay_speed × 10 × (1 + 输入参数字节数 / 1024)`
- `life <= 0` → 工具损坏，无法使用；`repair` 恢复 40 点 life（封顶 100），消耗 1 次修复次数。
- 工具函数从 `marketplace/tools/<name>.py` 动态 importlib 加载。

**4. 技能分段与衰退（skill_manager.py）**
- 技能是 `marketplace/skills/<name>/SKILL.md` 知识包，用 YASBD 按**句子边界**切段。
- `use_skill` 只返回前 `available_lines` 个段落（类似"渐进式上下文披露"）。
- **时间衰退规则**：距上次使用 < 4 小时 → 可用段数 +5（不超过上限）；超过 4 小时不用 → 段数按 `decay_speed × (空闲小时数-4) × 5` 衰减（封顶 0）。即技能"不用就忘"。

**5. 市场（marketplace/__init__.py）**
- `list_marketplace_items`：列出全部上架工具和技能及价格；
- `buy`：扣钱买工具或技能（余额不足返回提示；**新购工具下一轮才生效**，prompt 里专门叮嘱 agent 不要当回合使用）；
- `repair_tool`：按 manifest 的 `repair_price` 收费修复；
- `give_away_tool`：免费送掉工具，随机获得 0–10 的小费（quirky 设计）。

**6. 人格提示词（BASE_INSTRUCT）**
- 人设：直接、非正式、简短、密实的回答风格；干幽默、偶尔反向心理学；镜像用户语气和语言。
- 经济规则：明示当前余额；花钱买工具/修复/学技能。
- 行为约束："对验证信息上瘾"——外部事实、日期、计算**必须**用工具验证，禁止凭记忆；缺工具时向用户提议去市场采购；展示选项时必须给出明确成本权衡。

### 3.4 商品目录

**工具（9 个，marketplace/tools/manifest.json）**

| 工具 | 价格 | 磨损速度 | 可修次数 | 修复价 | 每次使用费 | 说明 |
|---|---|---|---|---|---|---|
| get_time | 5 | 0.3 | 5 | 4 | 0 | 当前 UTC 时间 |
| calculator | 10 | 0.2 | 5 | 4 | 0 | 安全数学求值 |
| read_file | 12 | 0.5 | 4 | 5 | 0 | 读取文件编号切片 |
| write_file | 15 | 0.6 | 3 | 6 | 0 | 写文件 |
| edit_file | 20 | 0.8 | 2 | 8 | 0 | 文本替换并打印 diff |
| search_wikipedia | 20 | 1.0 | 1 | 10 | 1 | 维基百科摘要 |
| web_fetch | 22 | 0.7 | 2 | 8 | 1 | 抓取 URL |
| web_search | 25 | 0.9 | 2 | 10 | 2 | 网络搜索（README 称走 Parallel search MCP） |
| bash | 25 | 1.0 | 1 | 10 | 0 | 无 shell 执行命令（subprocess shell=False + shlex） |

定价逻辑清晰：**能力越强/越危险，买价、磨损、修复越贵**；bash 和 web_search 这类高危工具可修次数只有 1–2 次，形成持续消耗。

**技能（12 个，10–20 credits）**：python_expert、blog-post、humanizer、github-issues、pr-message、naming-analyzer、social-media-posts、algorithmic-art、code-simplification、explain-codebase、git-guardian、git-workflow-and-versioning。均为 SKILL.md 知识包形式。

### 3.5 记忆系统（memory_system.py）

- 独立的 `memory_agent`（Agno Agent 而非 Team 成员工具），负责长期语义知识层。
- 存储：VectorLiteDB（`records.db`，384 维，L2），embedding 由本地 ONNX 模型产生。
- 接口：`add_or_update_memories`（content + metadata）、`retrieve_memory`（top_k + **过滤表达式**，如 `category == 'programming'`、`importance >= 5`，经 SafeEval 安全求值）、`delete_memory`。
- 指令要求：回答"我没有相关信息"前必须先检索记忆；记忆保持原子性、不重复、不编造。

### 3.6 代码层面的已知问题（调研发现）

1. **embedding/emb.py 硬编码 Android 路径** `parent_dir = "/storage/emulated/0/workspace/LivingAI/embedding/"`，测试注释也提到 "local Termux environment"——原型是在**安卓手机 Termux 里开发的**，直接在桌面环境运行会因找不到模型而失败。
2. **维度不一致**：emb.py 注释称输出 512 维，memory_system.py 里 VectorLiteDB 初始化为 384 维；且 tokenizer 是"按空格切词 + 词表查 [UNK]"的极简实现， embedding 质量有限。
3. **README 测试命令有误**：写的是 `python -m pytest test/ -q`，实际目录是 `tests/`。
4. **wallet.py 全局可变状态**：`BALANCE` 模块级变量 + txt 文件，无事务/并发保护；marketplace/__init__.py 里还留着一句过期注释 "wallet.py is an empty stub for now"。
5. **经济闭环缺失**：没有"工作/合约"系统，agent 只能靠回帖挣 1–3 分/轮，而 bash 工具买价 25——**挣钱速度远低于工具价格**，agent 可能长期困在"买不起工具"的境地（这本身也是个有意思的行为实验，但作者未调参）。
6. **单 agent 设计**："用户侧无限"意味着预算是单向压力；多 agent 交易、供需、合约均未实现（作者也承认是 future work）。
7. 无 Web UI，仅 CLI。

---

## 四、这个 Idea 的价值与定位

- **研究价值**：它是"资源约束下的 agent 行为学"实验——当 token、工具、能力都有标价，agent 的规划、优先级权衡、自我保全（修工具还是先搜索？）行为会如何变化，与经济学中的"预算约束下的理性选择"形成有趣对照。远期可演化为多 agent 模拟经济（agent 通过工作挣钱、交易能力、响应供需）。
- **工程价值**：一个"游戏化生存"的 agent demo，有天然的可观测性和传播性（看 AI 精打细算过日子）；磨损-修复-技能衰退三套机制已经跑通，可作为"agent 生命周期管理"的参考实现。
- **现实参照**：该方向与学术界的 LLM 经济 agent / agent 社会模拟研究同属一支，但把它做成"用户可围观、可插手"的开源玩具/工具的公开项目并不多——这正是 #445 的差异化空间。
- **社区状态**：Issue 开放 13 天，0 评论 0 认领 0 标签，竞争为零；作者明确欢迎任何人接手并允许完全重构。

---

## 五、如果想接手：路径建议

1. **先跑起来**：`pip install -r requirement.txt` → 修正 emb.py 的模型路径（把 embedding 目录指向本地实际位置）→ `python main.py`；运行 `python -m pytest tests/ -q` 确认基线。
2. **最小可行重构**（对应 Issue 列出的方向）：
   - 重做货币系统：引入通胀/收入曲线、"工作/合约"任务板，让 agent 有稳定的挣钱渠道；
   - 修复原型硬伤：embedding 路径、维度不一致、README 命令；
   - 把磨损公式从"输入字节数"启发式改为更有经济含义的计价（如按 token 用量、按结果价值）；
   - 加一个 Web UI 或 TUI 仪表盘：实时显示余额、工具健康度、技能状态、收支流水（这是 Issue 明确点名的方向）；
   - 实验设计：定义"财务约束下的行为"观测指标（储蓄率、维修 vs 新购决策、工具闲置率），让项目从玩具变成有数据的实验平台。
3. **进阶**：多 agent 经济（交易、合约、供需定价）、agent 经营"生意/服务"、经济状态跨会话持久化。
4. **协作方式**：按 Open Source Ideas 社区惯例，直接在 Issue 下评论表达意向，向作者提问；项目完成后回帖链接，Issue 关闭并进入 Hall of Fame。原代码 MIT 许可，可自由复用。

---

## 六、关键事实速查

| 问题 | 答案 |
|---|---|
| 链接是什么？ | Open Source Ideas 社区（用 GitHub Issues 收集开源创意的社区）的第 445 号创意 Issue |
| 标题 | AI Agent with Its Own Virtual Economy |
| 状态 | open，无标签、无评论、无人认领（2026-10-07 创建） |
| 作者诉求 | 求接手：原型已证明概念可行，作者无力独立完成完整重构与长期维护 |
| 原型 | speedyk-005/LivingAi（Python，MIT，Agno + Cerebras gpt-oss-120b，2026-08-04 一天内建成主体） |
| 核心机制 | 虚拟钱包（初始 0）+ 回答发薪（1–3 分/轮）+ 9 个计价工具（磨损/修复/按次收费）+ 12 个会"遗忘"的技能 + 向量语义记忆 + 单 agent 市场 |
| 最大缺口 | 无挣钱系统（无工作/合约）、无多 agent 经济、无 Web UI、若干硬编码 bug |
| 作者寄语 | "The goal is not to maintain the existing prototype, but to give someone a concrete starting point." |

**参考链接**
- Issue：https://github.com/open-source-ideas/ideas/issues/445
- 社区仓库：https://github.com/open-source-ideas/ideas
- 原型：https://github.com/speedyk-005/LivingAi
- Agno 框架：https://github.com/agno-agi/agno
- YASBD（作者自研句边界检测库）：https://github.com/speedyk-005/yasbd-lib
