"""Rich terminal UI for the interview bot."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.live import Live
from rich.markdown import Markdown
from rich import box

console = Console()


def print_banner():
    banner = Text()
    banner.append("  ALGO  ", style="bold white on blue")
    banner.append("  DSA Interview Bot  ", style="bold cyan")
    banner.append("\n")
    banner.append("  Voice-powered mock interviews with a local LLM\n", style="dim")
    banner.append("  Commands: ", style="dim")
    banner.append("'hint'", style="yellow")
    banner.append(" | ", style="dim")
    banner.append("'done'", style="green")
    banner.append(" | ", style="dim")
    banner.append("'skip'", style="red")
    banner.append(" | ", style="dim")
    banner.append("'topic'", style="magenta")
    banner.append(" | ", style="dim")
    banner.append("'voice on/off'", style="cyan")
    banner.append(" | ", style="dim")
    banner.append("'quit'", style="red")
    console.print(Panel(banner, box=box.DOUBLE, border_style="blue"))


def print_question(title: str, description: str, difficulty: str, examples: list[dict]):
    diff_colors = {"easy": "green", "medium": "yellow", "hard": "red"}
    color = diff_colors.get(difficulty, "white")

    table = Table(show_header=False, box=box.ROUNDED, border_style="cyan", expand=True)
    table.add_column(ratio=1)

    table.add_row(Text(f"  {title}", style="bold white"))
    table.add_row(Text(f"  Difficulty: {difficulty.upper()}", style=f"bold {color}"))
    table.add_row(Text(""))
    table.add_row(Text(f"  {description}", style="white"))

    if examples:
        table.add_row(Text(""))
        for i, ex in enumerate(examples):
            table.add_row(Text(f"  Example {i+1}:", style="bold dim"))
            table.add_row(Text(f"    Input:  {ex.get('input', '')}", style="dim"))
            table.add_row(Text(f"    Output: {ex.get('output', '')}", style="dim"))

    console.print(table)


def print_bot(text: str):
    console.print(f"\n [bold blue]Algo:[/bold blue] {text}")


def print_bot_streaming(text_gen):
    """Print bot response as it streams in. Returns full text."""
    full = ""
    console.print("\n [bold blue]Algo:[/bold blue] ", end="")
    for chunk in text_gen:
        console.print(chunk, end="", highlight=False)
        full += chunk
    console.print()
    return full


def print_user(text: str):
    console.print(f"\n [bold green]You:[/bold green] {text}")


def print_status(topic: str, difficulty: str, hints_used: int, max_hints: int, voice: bool):
    status = Text()
    status.append(f" Topic: {topic} ", style="bold magenta")
    status.append("|", style="dim")
    status.append(f" Difficulty: {difficulty} ", style="bold yellow")
    status.append("|", style="dim")
    status.append(f" Hints: {hints_used}/{max_hints} ", style="bold cyan")
    status.append("|", style="dim")
    voice_str = "ON" if voice else "OFF"
    voice_style = "bold green" if voice else "bold red"
    status.append(f" Voice: {voice_str} ", style=voice_style)
    console.print(Panel(status, box=box.SIMPLE, border_style="dim"))


def print_hint(hint_num: int, max_hints: int, hint_text: str):
    console.print(
        Panel(
            f"[yellow]Hint {hint_num}/{max_hints}:[/yellow] {hint_text}",
            border_style="yellow",
            box=box.ROUNDED,
        )
    )


def print_evaluation(text: str):
    console.print(
        Panel(
            text,
            title="[bold green]Evaluation[/bold green]",
            border_style="green",
            box=box.DOUBLE,
        )
    )


def print_info(text: str):
    console.print(f" [dim]{text}[/dim]")


def print_error(text: str):
    console.print(f" [bold red]Error:[/bold red] {text}")


def print_file_change(filepath: str):
    console.print(f" [dim cyan]File updated: {filepath}[/dim cyan]")


def get_input(prompt: str = "You") -> str:
    try:
        return console.input(f"\n [bold green]{prompt}:[/bold green] ").strip()
    except (EOFError, KeyboardInterrupt):
        return "quit"


def print_topic_menu(topics: list[str]):
    table = Table(title="Available Topics", box=box.ROUNDED, border_style="magenta")
    table.add_column("#", style="bold", width=4)
    table.add_column("Topic", style="cyan")

    for i, topic in enumerate(topics, 1):
        display = topic.replace("_", " ").title()
        table.add_row(str(i), display)

    console.print(table)
