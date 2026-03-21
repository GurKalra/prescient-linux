import os
import re
import urllib.request
from urllib.error import URLError, HTTPError
import urllib.parse
import concurrent.futures
from rich.console import Console
from prescient.core.logger import logger
from prescient.core.update_checker import get_local_version

console = Console()

def get_active_mirrors() -> set:
    """
    Scans APT sources lists to extract unique, active base URLs.
    """
    mirrors = set()

    sources_files = ['/etc/apt/sources.list']
    
    sources_d = '/etc/apt/sources.list.d/'
    if os.path.exists(sources_d):
        for file in os.listdir(sources_d):
            if file.endswith('.list') or file.endswith('.sources'):
                sources_files.append(os.path.join(sources_d, file))
    
    # Regex to extract the URL from an apt source line
    url_pattern = re.compile(r'^(?:deb|deb-src|URIs:)\s+(?:\[.*?\]\s+)?(https?://\S+)')

    for filepath in sources_files:
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    # Ignoring user comments and CD-ROM mounts
                    if line.startswith('#') or 'cdrom:' in line:
                        continue

                    match = url_pattern.search(line)
                    if match:
                        full_url = match.group(1)
                        parsed = urllib.parse.urlparse(full_url)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        mirrors.add(base_url)
        except PermissionError:
            logger.warning(f"Permission denied reading {filepath}. Run as root for full audit.")
        
    return mirrors

def check_single_mirror(url: str, timeout: float = 2.0, version: str = "unknown") -> tuple[str, bool, str]:
    """
    Pings a single mirror base URL using a lightweight HEAD request.
    """
    try:
        # Using HEAD to save bandwidth and not get the HTML payload, only the status code
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', f'Prescient-Linux-Preflight/{version}')

        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status < 400:
                return (url, True, "OK")
            return (url, False, f"HTTP {response.status}")
    
    except HTTPError as e:
        logger.debug(f"Mirror {url} returned HTTP {e.code}")
        return (url, False, f"HTTP {e.code}")
    except URLError as e:
        logger.warning(f"Mirror {url} unreachable: {e.reason}")
        return (url, False, str(e.reason))
    except Exception as e:
        logger.error(f"Unexpected error pinging mirror {url}: {type(e).__name__}: {e}")
        return (url, False, f"Unknown Error: {type(e).__name__}")
    
def audit_all_mirrors() -> list[tuple[str, bool, str]]:
    """
    Audits all extracted mirrors concurrently.
    """
    mirrors = get_active_mirrors()
    if not mirrors:
        logger.warning("No HTTP/HTTPS mirrors found to audit.")
        return []
    
    local_ver = get_local_version()
    results = []
    # Dynamic thread cap
    max_threads = min(10, len(mirrors))

    # Simultaneous network requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_url = {executor.submit(check_single_mirror, url, 2.0, local_ver): url for url in mirrors}

        for future in concurrent.futures.as_completed(future_to_url):
            try:
                results.append(future.result())
            except Exception as e:
                url = future_to_url[future]
                results.append((url, False, f"Thread crashed: {type(e).__name__}"))
    
    return results

def run_mirror_preflight() -> bool:
    """
    Entry point for the predict engine.
    """
    results = audit_all_mirrors()
    if not results:
        return True
    
    dead = [(url, msg) for url, ok, msg in results if not ok]
    alive = [url for url, ok, msg in results if ok]

    if dead:
        for url, msg in dead:
            logger.warning(f"Mirror unreachable: {url} ({msg})")
            console.print(f"  [yellow]Mirror unreachable:[/yellow] {url} ([dim]{msg}[/dim])")
    
    if not alive:
        logger.error("PREFLIGHT VETO: All mirrors are unreachable.")
        console.print("  [bold red]All mirrors unreachable. Blocking transaction to prevent partial update.[/bold red]")
        return False
    
    return True