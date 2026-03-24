import os
import re
import shlex
import subprocess
import typer
from rich.console import Console
from prescient.core.logger import logger

console = Console()

# Mapping specific logs identifiers / error messages to bash commands
HEAL_PLAYBOOK = {
    "NetworkManager": ["systemctl restart NetworkManager"],
    "systemd-resolved": ["systemctl restart systemd-resolved"],
    "bluetooth": ["systemctl restart bluetooth"],
    "gdm3": ["systemctl restart gdm3"],
    "lightdm": ["systemctl restart lightdm"],
    "dpkg": ["dpkg --configure -a", "apt install -f -y"],
    "apt": ["dpkg --configure -a", "apt install -f -y"],
}

def determine_fixes(culprits: list) -> list[tuple[str, list[str]]]:
    """Analyzes the culprits and builds a list of specific bash commands to run."""
    proposed_fixes = []
    seen_identifiers = set()

    # Only looking at the top 3 worst offenders
    for identifier, data in culprits[:3]:
        if identifier in seen_identifiers:
            continue
        seen_identifiers.add(identifier)
        msg = str(data["latest_msg"]).lower()

        # Checking for specific string matched in error message
        if "could not get lock" in msg or "frontend lock" in msg:
            cmds = [
                "rm -f /var/lib/apt/lists/lock",
                "rm -f /var/cache/apt/archives/lock",
                "rm -f /var/lib/dpkg/lock-frontend",
                "dpkg --configure -a"
            ]
            proposed_fixes.append(("APT/DPkg Deadlock Detected", cmds))
            continue

        if "unmet dependencies" in msg:
            proposed_fixes.append(("Broken Package Dependencies", ["apt install -f -y"]))
            continue

        # If the failing service is directly in the "HEAL_PLAYBOOK"
        if identifier in HEAL_PLAYBOOK:
            proposed_fixes.append((f"{identifier} Crash", HEAL_PLAYBOOK[identifier]))
            continue
        
        # If systemd is complaning , search through the actual message
        if identifier.lower() == "systemd":
            matched = False
            for service, cmds in HEAL_PLAYBOOK.items():
                if service.lower() in msg:
                    proposed_fixes.append((f"{service} Crash (Caught via systemd)", cmds))
                    matched = True
                    break
            if matched:
                continue
        
        # For genral fallback, propose a general restart
        if identifier.lower() not in ["kernel", "systemd", "unknown subsystem"]:
            safe_id = re.sub(r'[^a-zA-Z0-9\-_\.]', '', identifier)
            proposed_fixes.append((f"{identifier} Service Failure", [f"systemctl restart {identifier}"]))
        
    return proposed_fixes

def run_autoheal_sequence(culprits: list):
    """The interactive CLI sequence that proposes commands and executes them."""
    
    # Enforce root privilages before doing anything
    if os.geteuid() != 0:
        logger.error("Autoheal aborted: Root privileges required.")
        console.print("\n[bold red]Error: Auto-Heal requires root privileges to restart services.[/bold red]")
        console.print("Try running: [bold yellow]sudo prescient heal[/bold yellow]\n")
        return
    
    if not culprits:
        logger.info("Autoheal bypassed: No culprits provided by diagnostics.")
        return
    
    console.print("\n[bold cyan]prescient Auto-Heal Engine: Formulating Plan...[/bold cyan]")
    fixes = determine_fixes(culprits)

    if not fixes:
        logger.info("Autoheal bypassed: No automated fixes mapped for current issues.")
        console.print("[yellow]No automated fixes available (yet) for current issues.[/yellow]")
        return
    
    # Showing exactly what will be run
    console.print("[bold white]Proposed Remediation Actions:[/bold white]")
    for issue, commands in fixes:
        console.print(f"\n  [bold red]Issue:[/bold red] {issue}")
        for cmd in commands:
            console.print(f"    [dim green]↳ Run:[/dim green] [yellow]{cmd}[/yellow]")
        
    console.print("")
    # Confirmation
    confirm = typer.confirm("Execute these commands automatically?")

    if not confirm:
        logger.info("User aborted Auto-Heal sequence at confirmation prompt.")
        console.print("[yellow]Auto-Heal aborted by user.[/yellow]")
        return
    
    # The execution
    logger.info(f"User confirmed Auto-Heal execution for {len(fixes)} issues.")
    console.print("\n[bold cyan]Executing Fixes...[/bold cyan]")

    for issue, commands in fixes:
        console.print(f"  [cyan]Resolving {issue}...[/cyan]")
        for cmd in commands:
            try:
                logger.debug(f"Autoheal executing: {cmd}")
                subprocess.run(
                    shlex.split(cmd),
                    check=True,
                    capture_output=True,
                    text=True
                )
                console.print(f"    [bold green]Success:[/bold green] {cmd}")
            except subprocess.CalledProcessError as e:
                console.print(f"    [bold red]Failed:[/bold red] {cmd}")
                error_out = e.stderr.strip() if e.stderr else e.stdout.strip()
                logger.error(f"Autoheal failed on '{cmd}': {error_out}")
                console.print(f"      [dim red]Error details: {error_out}[/dim red]")
    
    console.print("\n[bold green]Auto-Heal sequence complete. Verify system stability.[/bold green]")
