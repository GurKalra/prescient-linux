import os
import subprocess
import webbrowser
from pathlib import Path
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Center, Middle, Horizontal, Vertical
from textual.widgets import Static, Button, Footer, ListView, ListItem, Label, Markdown, RichLog
from textual.screen import Screen
from textual.reactive import reactive

from prescient.core.update_checker import get_local_version, check_for_updates
from prescient.core.logger import logger
from prescient.tui.widgets import DuneWave

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Command Configuration
COMMAND_REGISTRY = {
    "predict": {"file": "docs/predict.md", "runnable": True},
    "diagnose": {"file": "docs/diagnose.md", "runnable": True},
    "heal": {"file": "docs/heal.md", "runnable": True},
    "undo": {"file": "docs/undo.md", "runnable": False, "cli_cmd": "sudo prescient undo"},
    "update": {"file": "docs/update.md", "runnable": True},
    "uninstall": {"file": "docs/uninstall.md", "runnable": False, "cli_cmd": "sudo prescient uninstall"},
}

ASCII_LOGO = r"""[bold cyan]
___  ____ ____ ____ ____ _ ____ _  _ ___ 
|__] |__/ |___ [__  |    | |___ |\ |  |  
|    |  \ |___ ___] |___ | |___ | \|  |  
[/bold cyan]"""

def get_last_health_status() -> str:
    """
    Reads the last predict result from the log file.
    """
    log_path = Path("/var/log/prescient.log")

    if not log_path.exists():
        logger.debug("TUI health check: prescient.log not found.")
        return "Health: [yellow]Unknown[/yellow]\n[dim](Run predict to check)[/dim]"
    
    try:
        lines = log_path.read_text().splitlines()
        for line in reversed(lines):
            if "Pre-flight audit passed successfully" in line:
                logger.debug(f"TUI health status resolved: Healthy.")
                timestamp = line.split("]")[0].strip("[")
                return f"Health: [bold green]Healthy[/bold green]\n[dim]Last check: {timestamp}[/dim]"
            if "VETO" in line or "BROKEN" in line:
                logger.debug(f"TUI health status resolved: Issues Detected.")
                timestamp = line.split("]")[0].strip("[")
                return f"Health: [bold red]Issues Detected[/bold red]\n[dim]Last check: {timestamp}[/dim]"
    except Exception as e:
        logger.error(f"TUI failed to parse health status from log: {e}")

    return "Health: [yellow]Unknown[/yellow]\n[dim](Run predict to check)[/dim]"

# SCREENS

class CommandOutputScreen(Screen):
    """
    Overlay screen that shows live command output.
    """

    BINDINGS = [
        ("q", "pop_screen", "Back"),
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, command: str):
        super().__init__()
        self.command = command
    
    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold cyan]> prescient {self.command}[/bold cyan]\n[dim]Press Q or Esc to return[/dim]", 
            id="output-header"
        )
        yield RichLog(id="output-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_command_worker()
    
    @work(thread=True)
    def run_command_worker(self) -> None:
        log = self.query_one("#output-log", RichLog)
        try:
            process = subprocess.Popen(
                ["prescient", self.command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            for line in process.stdout:
                self.app.call_from_thread(log.write, line.rstrip())
            
            process.wait()

            if process.returncode == 0:
                self.call_from_thread(log.write, "\n[bold green]Command completed successfully.[/bold green]")
                self.call_from_thread(log.write, "[dim]Press Q or Esc to return to dashboard.[/dim]")
                logger.info(f"TUI overlay command '{self.command}' completed successfully.")
            else:
                self.call_from_thread(log.write, f"\n[bold red]Command failed with exit code {process.returncode}.[/bold red]")
                logger.error(f"TUI overlay command '{self.command}' failed: exit {process.returncode}")
        
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]Error: {e}[/bold red]")
            logger.error(f"TUI overlay worker crashed for '{self.command}': {e}")

# WIDGETS
class TopHeader(Horizontal):
    """
    The custom header with the logo, tagline, GitHub link, and exit button.
    """
    def compose(self) -> ComposeResult:
        yield Static(ASCII_LOGO, id="logo")
        with Vertical(id="tagline-container"):
            yield Static(
                f"Predict. Protect. Recover. | v{get_local_version()}", 
                id="tagline"
            )
            
        with Vertical(id="header-right"):
            yield Static(
                "[@click=app.open_link]Repository[/]\nConsider starring the project!",
                id="github-text"
            )
            yield Button("[ Exit TUI ]", id="exit-button", classes="terminal-btn")

class MainDashboard(Container):
    """
    The main dashboard layout.
    """
    def compose(self) -> ComposeResult:
        yield TopHeader(id="top-header")

        with Horizontal(id="main-content-split"):
            # Left Sidebar
            with Vertical(id="sidebar"):
                yield Static("COMMANDS", classes="sidebar-title")
                yield ListView(
                    ListItem(Label("predict"), id="cmd-predict"),
                    ListItem(Label("diagnose"), id="cmd-diagnose"),
                    ListItem(Label("undo"), id="cmd-undo"),
                    ListItem(Label("heal"), id="cmd-heal"),
                    ListItem(Label("update"), id="cmd-update"),
                    ListItem(Label("uninstall"), id="cmd-uninstall"),
                    id="command-list"
                )
                yield Static(get_last_health_status(), id="health-status")
            
            # Right Content area
            with Vertical(id="right-pane"):
                # Update Banner / Animation
                with Horizontal(id="update-banner"):
                    yield Static("System is up to date. No new OTA releases.", id="update-text")
                    yield DuneWave(id="main-wave")

                # Markdown docs for each command
                with Vertical(id="content-area"):
                    yield Markdown("Select a command from the left to view its documentation.", id="doc-viewer")

                    with Center(id="action-area"):
                        yield Button("[ Run Command ]", id="btn-run-cmd", classes="hidden terminal-btn")
                        yield Static("To use this, exit the TUI and run:\n[bold cyan]sudo prescient ...[/bold cyan]", id="cli-warning", classes="hidden")

    async def on_mount(self) -> None:
        """
        Added this to make sure it runs after the whole dashboard is loaded
        """
        logger.debug("MainDashboard mounted. Triggering update check.")
        self.app.run_update_check()
class InstallScreen(Container):
    """
    The centered first-time install screen.
    """
    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Static("Prescient is installed, but system hooks are missing.", classes="install-text")
                yield Button("Install System Hooks", id="btn-install-hooks", classes="terminal-btn")
                yield Static("", id="install-status", classes="dim-text")

# MAIN APP

class PrescientTUI(App):
    """
    The main Prescient Terminal UI.
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", ""),
        ("j", "cursor_down", "Down"),     
        ("k", "cursor_up", "Up"),
        ("enter", "run_command", "Run"),
        ("r", "refresh_health", "Refresh"),
        ("u", "open_update", "Update"),
        ("h", "focus_sidebar", "Commands"),
        ("?", "show_help", "Help"),
    ]

    current_command: reactive[str] = reactive("")

    CSS = """
    Screen { background: $surface; }

    /* Header */
    #top-header { height: 5; dock: top; padding: 0 1; border-bottom: solid $primary-darken-2; }
    #logo { width: 45; content-align: left middle; }
    #tagline-container { width: 1fr; content-align: left middle; padding-top: 2; }
    #tagline { color: $text-muted; }
    #header-right { width: 40; content-align: right middle; padding-top: 1; }
    #github-text { text-align: right; }
    #exit-button { margin-top: 1; }

    /* Main Layout */
    #main-content-split { height: 1fr; }
    #sidebar { width: 30; border-right: solid $primary-darken-2; height: 100%; padding: 1 1; }
    .sidebar-title { text-style: bold; color: $text-muted; margin-bottom: 1; padding-left: 1; }
    #health-status { dock: bottom; border-top: solid $primary-darken-2; padding: 1 0 0 1; height: 4; }

    /* Right Pane */
    #right-pane { width: 1fr; height: 100%; }
    #update-banner { height: 5; border-bottom: solid $primary-darken-2; padding: 0 2; }
    #update-text { width: 1fr; content-align: left middle; color: $success; text-style: bold; }
    #main-wave { width: 40; height: 5; }

    /* Content Area */
    #content-area { height: 1fr; padding: 1 3; }
    #doc-viewer { height: 1fr; overflow-y: auto; }
    #action-area { height: auto; padding-top: 1; border-top: dashed $primary-darken-2; }
    #cli-warning { text-align: center; padding: 1; color: $warning; }
    .hidden { display: none; }

    /* Terminal Button Styling */
    .terminal-btn {
        background: transparent;
        border: none;
        color: $accent;
        text-style: bold;
        min-width: 20;
    }
    .terminal-btn:focus { background: $accent; color: $surface; }
    .terminal-btn:hover { background: $boost; }

    /* Install Screen */
    .install-text { text-align: center; margin-bottom: 2; }
    .dim-text { color: $text-muted; text-align: center; margin-top: 2; }

    /* Overlay Screen */
    #output-header { padding: 1; border-bottom: solid $primary-darken-2; background: $boost; }
    #output-log { height: 1fr; padding: 1; background: $surface; }
    """

    async def on_mount(self) -> None:
        logger.info("Prescient TUI fully mounted.")

    @work(thread=True)
    def run_update_check(self) -> None:
        """
        Runs the network request in the background.
        """
        if check_for_updates():
            logger.info("TUI update check: new version available.")
            self.call_from_thread(self._show_update_banner)
    
    def _show_update_banner(self) -> None:
        """
        Thread-safe UI update for the update banner.
        """
        try:
            self.query_one("#update-text", Static).update(
                "[bold yellow]New Prescient version available![/bold yellow]\nSelect 'update' from the left panel."
            )
            logger.info("TUI update banner displayed successfully.")
        except Exception as e:
            logger.error(f"TUI failed to display update banner: {e}")
    
    def compose(self) -> ComposeResult:
        hook_path = "/etc/apt/apt.conf.d/99prescient-guardian"
        if os.path.exists(hook_path):
            logger.info("TUI launched: hooks detected, showing main dashboard.")
            yield MainDashboard(id="main-dashboard")
        else:
            logger.warning("TUI launched: hooks not detected, showing install screen.")
            yield InstallScreen(id="install-screen")
        
        yield Footer()

    # ACTION HANDLERS

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#command-list", ListView).action_cursor_down()
        except Exception:
            pass
    
    def action_cursor_up(self) -> None:
        try:
            self.query_one("#command-list", ListView).action_cursor_up()
        except Exception:
            pass
    
    def action_refresh_health(self) -> None:
        self._refresh_health()
    
    def action_focus_sidebar(self) -> None:
        try:
            self.query_one("#command-list", ListView).focus()
        except Exception:
            pass
    
    def action_run_command(self) -> None:
        if self.current_command:
            config = COMMAND_REGISTRY.get(self.current_command)
            if config and config["runnable"]:
                if self.current_command == "heal":
                    logger.info("TUI suspending for interactive heal command.")
                    with self.suspend():
                        subprocess.run(
                            ["sudo", "prescient", "heal"]
                        )
                    logger.info("TUI resumed after heal command.")
                else: 
                    logger.info(f"TUI pushing output screen for: {self.current_command}")
                    cmd = self.current_command
                    self.push_screen(
                        CommandOutputScreen(cmd),
                        callback=lambda _:self._refresh_health() if cmd == "predict" else None
                    )
            elif config and not config["runnable"]:
                logger.debug(f"TUI: user tried to run non-runnable command: {self.current_command}")
    
    def action_open_link(self) -> None:
        logger.info(f"User opened GitHub repository link.")
        webbrowser.open("https://github.com/GurKalra/prescient-linux")

    def action_open_update(self) -> None:
        """
        Jumps to and selects the update command in the sidebar.
        """
        logger.debug("User used 'u' shortcut to jump to update command.")
        try:
            listview = self.query_one("#command-list", ListView)
            listview.focus()

            for index, item in enumerate(listview.children):
                if hasattr(item, 'id') and item.id == "cmd-update":
                    listview.index = index
                    break
        except Exception:
            pass

    def action_show_help(self) -> None:
        logger.debug("User opened help overlay via '?' shortcut.")
        self.notify("Use j/k to navigate, Enter to run, q or Esc to quit.", title="Keyboard Controls")
    
    def _refresh_health(self) -> None:
        """
        Updates the health status widget.
        """
        try:
            self.query_one("#health-status", Static).update(get_last_health_status())
            logger.debug("TUI health status widget refreshed.")
        except Exception as e:
            logger.error(f"TUI failed to refresh health widget: {e}")
    
    # EVENT HANDLERS

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not event.item:
            return
        
        try:
            self.query_one("#doc-viewer", Markdown)
        except Exception:
            return

        self.current_command = event.item.id.replace("cmd-", "")
        config = COMMAND_REGISTRY.get(self.current_command)

        if config:
            doc_path = BASE_DIR / config["file"]
            try:
                with open(doc_path, "r") as f:
                    self.query_one("#doc-viewer", Markdown).update(f.read())
            except FileNotFoundError:
                logger.warning(f"TUI doc file missing: {doc_path}")
                self.query_one("#doc-viewer", Markdown).update(f"# Missing Doc\nCould not find `{doc_path}`.")

            btn = self.query_one("#btn-run-cmd", Button)
            warning = self.query_one("#cli-warning", Static)

            btn.remove_class("hidden")
            warning.remove_class("hidden")

            if config["runnable"]:
                btn.display = True
                warning.display = False
                btn.label = f"[ Run {self.current_command.capitalize()} ]"
            else:
                btn.display = False
                warning.display = True
                warning.update(f"[bold yellow]Interactive Command:[/bold yellow]\nTo use this, exit the TUI and type:\n[bold cyan]{config['cli_cmd']}[/bold cyan]")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit-button":
            logger.info("User exited TUI via Exit button.")
            self.exit()
        elif event.button.id == "btn-install-hooks":
            logger.info("User initiated hook installation from TUI.")
            self.query_one("#install-status", Static).update("[cyan]Installing hooks...[/cyan]")
            self.run_install_hooks_worker()
        elif event.button.id == "btn-run-cmd":
            logger.info(f"User clicked Run button for command: {self.current_command}")
            self.action_run_command()

    # WORKERS

    @work(thread=True)
    def run_install_hooks_worker(self) -> None:
        logger.info("Hook installation worker started.") 
        try:
            subprocess.run(
                ["sudo", "prescient", "install-hooks"],
                check=True,
                capture_output=True
            )
            logger.info("Hook installation successful via TUI.")
            self.call_from_thread(self.notify, "Hooks installed! Restarting TUI...", title="Success")
            self.call_from_thread(self.exit)
        except subprocess.CalledProcessError as e:
            logger.error(f"Hook installation failed via TUI: exit code {e.returncode}")
            self.call_from_thread(self.notify, "Hook installation failed. Try: sudo prescient install-hooks", title="Error", severity="error")