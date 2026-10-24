"""CLI：rich 终端聊天 + 斜杠命令。

命令：
  /status              余额、工具健康度、技能、任务一览
  /market              市场清单
  /buy <name> [tool|skill]   购买
  /rent <name> [n]     租赁
  /repair <name>       修复
  /skills              已掌握技能
  /tasks               任务板
  /post <bounty> | <标题> | <简述>   发任务（托管赏金）
  /done <id> [tip]     手动结算成功
  /fail <id> [penalty] 手动结算失败
  /ledger [n]          最近流水
  /license             当前授权层级（社区版 MIT 免费 / 企业版）
  /grant <n>           实验 seed 资金
  /quit                退出
聊天时可用 "赏金 50: ..." 前缀直接发任务。
"""
from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agent import Agent
from .llm import EchoClient, OpenAIClient


def _fmt_status(agent: Agent):
    from rich.console import Group

    st = agent.status()
    t = Table(show_header=True, header_style="bold")
    t.add_column("Tool")
    t.add_column("Owned")
    t.add_column("Life")
    t.add_column("Calls")
    t.add_column("Repairs")
    for name, h in st["tools"].items():
        if h["owned"] or h["calls"]:
            t.add_row(
                name, "✓" if h["owned"] else "·",
                f"{h['life']:.0f}" if h["life"] is not None else "-",
                str(h["calls"]), str(h["repairs_left"]),
            )
    skills = ", ".join(
        f"{n}({h['available_lines']}/{h['max_lines']})"
        for n, h in st["skills"].items() if h["owned"]
    ) or "none"
    body = Group(
        f"[bold]Balance:[/] {st['balance']} Aria coins",
        t,
        f"[bold]Skills:[/] {skills}",
        f"[bold]Open tasks:[/] {sum(1 for x in st['tasks'] if x['status'] in ('open', 'assigned'))}",
    )
    return Panel(body, title="LivingAI status", expand=False)


def main():
    console = Console()
    root = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("/"):
        root = sys.argv[1]

    client = None
    try:
        client = OpenAIClient()
        if not client.api_key:
            client = None
    except Exception:
        client = None
    if client is None:
        console.print("[yellow]No ARIA_API_KEY — demo mode: scripted policy driver.[/]")
        from aria.experiments import PolicyClient

        client = PolicyClient(agent=None, want_tool="calculator", query="1+1")
        # PolicyClient 需要 agent 引用；先建 agent 再注入
        agent = Agent(root=root, client=None)
        client.agent = agent
        agent.client = client
    else:
        agent = Agent(root=root, client=client)
    console.print(_fmt_status(agent))
    console.print("[dim]Type /help for commands. '赏金 50: ...' posts a task with a bounty.[/]")

    while True:
        try:
            text = console.input("[bold green]You:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/exit", "quit", "exit"):
            break
        if text.startswith("/"):
            _handle_command(console, agent, text)
            continue
        try:
            reply = agent.handle(text)
        except Exception as exc:
            console.print(f"[red]error: {type(exc).__name__}: {exc}[/]")
            continue
        console.print(Panel(reply or "(empty)", title="LivingAI", expand=False))


def _handle_command(console: Console, agent: Agent, text: str) -> None:
    parts = text.split(maxsplit=1)
    cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
    if cmd == "/status":
        console.print(_fmt_status(agent))
    elif cmd == "/market":
        console.print(agent.marketplace.list_items())
    elif cmd == "/buy":
        bits = arg.split()
        console.print(agent.marketplace.buy(bits[0], bits[1] if len(bits) > 1 else None))
    elif cmd == "/rent":
        bits = arg.split()
        console.print(agent.marketplace.rent_tool(bits[0], int(bits[1]) if len(bits) > 1 else 3))
    elif cmd == "/repair":
        console.print(agent.marketplace.repair_tool(arg))
    elif cmd == "/skills":
        console.print(agent.skills.descriptions())
    elif cmd == "/tasks":
        console.print(agent.board.listing())
    elif cmd == "/post":
        try:
            bounty, title, brief = [x.strip() for x in arg.split("|")]
            t = agent.board.post(title=title, brief=brief, bounty=int(bounty))
            console.print(f"Posted task {t.id[:8]} (bounty {t.bounty} escrowed).")
        except ValueError:
            console.print("Usage: /post <bounty> | <title> | <brief>")
    elif cmd == "/done":
        bits = arg.split()
        tip = int(bits[1]) if len(bits) > 1 else 0
        console.print(agent.board.submit(bits[0], True, "manual", tip=tip))
    elif cmd == "/fail":
        bits = arg.split()
        pen = int(bits[1]) if len(bits) > 1 else 0
        console.print(agent.board.submit(bits[0], False, "manual", penalty=pen))
    elif cmd == "/ledger":
        n = int(arg) if arg else 15
        for e in agent.ledger.history(n):
            console.print(f"{e.ts[11:19]} {e.kind:<18} {e.debit} -> {e.credit}  {e.amount:>4}  {e.ref[:8]} {e.note}")
    elif cmd == "/grant":
        agent.grant(int(arg))
        console.print(f"Granted {arg}. Balance: {agent.wallet.balance()}")
    elif cmd == "/license":
        _show_license(console)
    elif cmd == "/help":
        console.print(__doc__)
    else:
        console.print(f"[red]unknown command {cmd}[/] — /help")


def _show_license(console: Console) -> None:
    """显示当前授权层级：社区版（MIT 免费）还是企业版。"""
    from . import enterprise

    st = enterprise.status()
    if st["tier"] == "community":
        console.print(
            "[bold]社区版（MIT，永久免费）[/]\n"
            "核心功能全部可用。企业版（SSO/RBAC/审计导出/多租户）见 docs/LICENSING.md"
        )
    else:
        console.print(
            f"[bold green]企业版[/] · {st['org']} · {st['seats']} 席位 · "
            f"{st['days_left']} 天后到期（{st['expires_at'][:10]}）"
        )
    t = Table(show_header=True, header_style="bold")
    t.add_column("功能")
    t.add_column("状态")
    for name, meta in st["features"].items():
        t.add_row(
            f"{name} — {meta['description']}",
            "[green]已启用[/]" if meta["enabled"] else "[dim]需企业许可[/]",
        )
    console.print(t)


if __name__ == "__main__":
    main()
