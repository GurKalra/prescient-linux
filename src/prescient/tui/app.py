import os
import time
import subprocess
import webbrowser
from pathlib import Path
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Center, Middle, Horizontal, Vertical
from textual.widgets import Static, Button, Footer, ListView, ListItem, Label, Markdown

from prescient.core.update_checker import get_local_version, check_for_updates
from prescient.core.logger import logger
from prescient.tui.widgets import DuneWave

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Command Config
COMMAND_REGISTRY = {
    "predict": "docs/predict.md",
    "diagnose": "docs/diagnose.md",
    "heal": "docs/heal.md",
    "undo": "docs/undo.md",
    "update": "docs/update.md",
    "uninstall": "docs/uninstall.md",
}

ASCII_LOGO = r"""[bold #8ec07c]
___  ____ ____ ____ ____ _ ____ _  _ ___ 
|__] |__/ |___ [__  |    | |___ |\ |  |  
|    |  \ |___ ___] |___ | |___ | \|  |  
[/bold #8ec07c]"""

def get_last_health_status() -> str:
    log_path = Path("/var/log/prescient.log")
    if not log_path.exists():
        return "Health : [#fabd2f]Unknown[/#fabd2f]\n[dim](Run predict to check)[/dim]"
    
    try:
        lines = log_path.read_text().splitlines()
        for line in reversed(lines):
            if "Pre-flight audit passed successfully" in line:
                timestamp = line.split("]")[0].strip("[")
                return f"Health: [bold #b8bb26]Healthy[/bold #b8bb26]\n[dim]Last check: {timestamp}[/dim]"
            if "VETO" in line or "BROKEN" in line:
                timestamp = line.split("]")[0].strip("[")
                return f"Health: [bold #fb4934]Issues Detected[/bold #fb4934]\n[dim]Last check: {timestamp}[/dim]"
    except Exception:
        pass
    
    return "Health: [#fabd2f]Unknown[/#fabd2f]\n[dim](Run predict to check)[/dim]"

# WIDGETS
class TopHeader(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static(ASCII_LOGO, id="logo")
        with Vertical(id="tagline-container"):
            yield Static(f"Predict. Protect. Recover. | v{get_local_version()}", id="tagline")
        with Vertical(id="header-right"):
            yield Static("[@click=app.open_link]Repository[/]\n[dim]Thank you for using prescient[/dim]\n[dim]Consider starring the project![/dim]", id="github-text")

class MainDashboard(Container):
    def compose(self) -> ComposeResult:
        yield TopHeader(id="top-header")

        with Horizontal(id="main-content-split"):
            with Vertical(id="sidebar"):
                yield Static("COMMANDS", classes="sidebar-title")
                yield ListView(
                    ListItem(Label("> predict"), id="cmd-predict"),
                    ListItem(Label("> diagnose"), id="cmd-diagnose"),
                    ListItem(Label("> undo"), id="cmd-undo"),
                    ListItem(Label("> heal"), id="cmd-heal"),
                    ListItem(Label("> update"), id="cmd-update"),
                    ListItem(Label("> uninstall"), id="cmd-uninstall"),
                    id="command-list"
                )
                yield Static(get_last_health_status(), id="health-status")
            
            with Vertical(id="right-pane"):
                with Horizontal(id="update-banner"):
                    yield Static("System is up to date. No new OTA releases.", id="update-text")
                    yield DuneWave(id="main-wave")
                
                with Vertical(id="content-area"):
                    yield Markdown("Select a command from the left to view its documentation.", id="doc-viewer")
    
    async def on_mount(self) -> None:
        self.app.run_update_check()

class InstallScreen(Container):
    def compose(self) -> ComposeResult:
        with Vertical(id="install-content"):
            yield Static(ASCII_LOGO, id="install-title")
            yield Static("System hooks are not yet installed.", classes="install-text")
            yield Static("Press [bold #8ec07c]Enter[/bold #8ec07c] to wire Prescient into your package manager.", classes="dim-text")
            yield Static("", id="install-status", classes="dim-text")
        yield DuneWave(id="install-wave-bottom")

# Main App
class PrescientTUI(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", ""),
        ("j", "cursor_down", "Down"),     
        ("k", "cursor_up", "Up"),
        ("l", "focus_right_pane", "Right"),
        ("h", "focus_sidebar", "Left"),
        ("r", "refresh_health", "Refresh"),
        ("u", "open_update", "Update"),
        ("?", "show_help", "Help"),
        ("enter", "install_hooks", "Install"),
    ]

    CSS = """
    /* Gruvbox Dark Color Palette */
    $surface: #282828;
    $boost: #3c3836;
    $primary-darken-2: #504945;
    $text: #ebdbb2;
    $text-muted: #a89984;
    $accent: #8ec07c;
    $success: #b8bb26;
    $warning: #fabd2f;
    $error: #fb4934;

    Screen { background: $surface; }

    #top-header { height: 5; dock: top; padding: 0 1; border-bottom: solid $primary-darken-2; }
    #logo { width: 45; content-align: left middle; }
    #tagline-container { width: 1fr; content-align: left middle; padding-top: 2; }
    #tagline { color: $text-muted; }
    #header-right { width: 40; content-align: right middle; padding-top: 1; }
    #github-text { text-align: right; }
    #exit-button { margin-top: 1; min-width: 15; }

    #main-content-split { height: 1fr; }
    #sidebar { width: 30; border-right: solid $primary-darken-2; height: 100%; padding: 1 1; }
    .sidebar-title { text-style: bold; color: $text-muted; margin-bottom: 1; padding-left: 1; }
    #health-status { dock: bottom; border-top: solid $primary-darken-2; padding: 1 0 0 1; height: 4; }

    #right-pane { width: 1fr; height: 100%; }
    #update-banner { height: 8; border-bottom: solid $primary-darken-2; padding: 0 2; align: center middle; }
    #update-text { width: 1fr; height: 8; content-align: center middle; text-align: center; color: $success; text-style: bold; }
    #main-wave { width: 1fr; height: 8; dock: right;}

    #content-area { height: 1fr; padding: 1 3; }
    #doc-viewer { height: 1fr; overflow-y: auto; }

    .terminal-btn {
        background: $surface;
        border: none;
        color: $text-muted;
        text-style: bold;
    }
    .terminal-btn:focus { background: $accent; color: $surface; }
    .terminal-btn:hover { background: $boost; }

    /* Install Screen Aesthetics */
    #install-content { height: 1fr; align: center middle; }
    #install-wave-bottom { height: 9; width: 100%; dock: bottom; }
    #install-title { width: 100%; text-align:center; margin-bottom: 2; }
    .install-text { text-align: center; margin-bottom: 2; }
    .dim-text { color: $text-muted; text-align: center; margin-top: 2; }
    """

    async def on_mount(self) -> None:
        logger.info("Prescient TUI fully mounted.")
    
    @work(thread=True)
    def run_update_check(self) -> None:
        if check_for_updates():
            logger.info("TUI update check: new version available.")
            self.call_from_thread(self._show_update_banner)
    
    def _show_update_banner(self) -> None:
        try:
            self.query_one("#update-text", Static).update(
                "[bold #fabd2f]New Prescient version available![/bold #fabd2f]\nPress 'u' to jump to 'update'."
            )
        except Exception as e:
            logger.error(f"TUI failed to display update banner: {e}")
    
    def compose(self) -> ComposeResult:
        apt_hook = "/etc/apt/apt.conf.d/99prescient-guardian"
        pacman_hook = "/etc/pacman.d/hooks/99-prescient-guardian.hook"

        if os.path.exists(apt_hook) or os.path.exists(pacman_hook):
            yield MainDashboard(id="main-dashboard")
        else:
            yield InstallScreen(id="install-screen")
        yield Footer()

    # ACTION HANDLERS
    def action_install_hooks(self) -> None:
        """
        Securely handles the Enter keypress to install hooks.
        """
        try:
            status_text = self.query_one("#install-status", Static)
        except Exception:
            return
        
        logger.info("User initiated hook installation via Enter key.")

        try:
            status_text.update("[dim #8ec07c]Installing hooks... do not close terminal[/dim #8ec07c]")
        except Exception:
            pass
        
        success = False
        with self.suspend():
            print("\n[Prescient] Installing system hooks. You may be prompted for your password...")
            try:
                subprocess.run(
                    ["sudo", "prescient", "install-hooks"],
                    check=True
                )
                print("\n[Prescient] Hooks successfully installed!")
                time.sleep(1.3)
                success=True
            except subprocess.CalledProcessError as e:
                print(f"\n[Prescient] Hook installation failed (exit code {e.returncode}).")
                input("\nPress Enter to return to the TUI...")
        if success:
            logger.info("Hot-swapping to MainDashboard after successful install.")
            self.query_one("#install-screen").remove()
            self.mount(MainDashboard(id="main-dashboard"), before = self.query_one(Footer))
            self.notify("Vanguard Engine Online.", title="System Ready")
        else:
            try:
                status_text.update("[#fb4934]Installation failed. Check prescient.log[/#fb4934]")
            except Exception:
                pass

    def action_focus_right_pane(self) -> None:
        try:
            self.query_one("#doc-viewer", Markdown).focus()
        except Exception:
            pass
    
    def action_focus_sidebar(self) -> None:
        try:
            self.query_one("#command-list", ListView).focus()
        except Exception:
            pass

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
        try:
            self.query_one("#health-status", Static).update(get_last_health_status())
            self.notify("Health refreshed.", title="Refresh")
        except Exception:
            pass

    def action_open_link(self) -> None:
        webbrowser.open("https://github.com/GurKalra/prescient-linux")

    def action_open_update(self) -> None:
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
        self.notify("j/k — navigate list  |  l — scroll docs  |  h — back to list  |  r — refresh health", title="Controls")
    
    # EVENT HANDLERS
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not event.item:
            return
        
        try:
            self.query_one("#doc-viewer", Markdown)
        except Exception:
            return
        
        cmd = event.item.id.replace("cmd-", "")

        doc_file = COMMAND_REGISTRY.get(cmd)

        if doc_file:
            doc_path = BASE_DIR / doc_file
            try:
                with open(doc_path, "r") as f:
                    self.query_one("#doc-viewer", Markdown).update(f.read())
            except FileNotFoundError:
                logger.warning(f"TUI doc file missing: {doc_path}")
                self.query_one("#doc-viewer", Markdown).update(f"# Missing Doc\nCould not find `{doc_path}`.")
