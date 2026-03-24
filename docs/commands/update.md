# `prescient update`

> The Secure OTA Update Engine which checks GitHub for a newer version of Prescient, pulls the verified source code via Git, and reinstalls it into the isolated virtual environment in a single command.

---

## Purpose

`update` keeps Prescient itself up to date. It is the only safe way to update Prescient, using the same isolated virtual environment and editable install that the original `install.sh` set up, rather than touching your system Python or running arbitrary scripts as root.

It includes a version check before pulling anything. If you are already on the latest version, it exits immediately with a clean message and makes no network requests beyond the initial version comparison. Use `--force` to override this and reinstall regardless.

> **!!Tip:** The `prescient tui` dashboard runs a background OTA check on every launch and surfaces a yellow banner if a newer version is available. From there, navigate to `update` in the sidebar and run this command.

---

## Usage

```bash
sudo prescient update

# Force reinstall even if already up to date
sudo prescient update --force
```

### Options

| Flag ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ | Description                                                                                                                                                                                                                 |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--force`                            | Bypasses the version check and forces a full `git pull` and `pip install --upgrade` regardless of whether the local version matches the remote. Useful for repairing a corrupted install or reverting local source changes. |

---

## Prerequisites

- [x] Requires `sudo` (root privileges) - needed to write to the virtual environment and update system binaries
- [x] Requires `git` - used to pull the latest source code
- [x] Requires the `~/.prescient` directory to exist with a valid `.git` repository - created by `install.sh`
- [x] Requires `~/.prescient/.venv/bin/python` to exist - the isolated Python environment
- [x] Requires network access to `github.com` and `raw.githubusercontent.com`

---

## Under the Hood

### Stage 1 - Version Check (skipped with `--force`)

Before touching anything, `update` runs a **forced network version check** (`force_network=True`) that bypasses the 24-hour cache used by the background TUI checker.

`get_local_version()` reads `pyproject.toml` directly from `~/.prescient/pyproject.toml` using a regex match on `^\s*version\s*=\s*["']([^"']+)["']`. This bypasses `importlib.metadata` caching bugs that affect editable installs — the file on disk is always the ground truth. Falls back to `importlib.metadata` if the file is not found.

`check_for_updates()` fetches `https://raw.githubusercontent.com/GurKalra/prescient-linux/main/pyproject.toml` with a **15-second timeout** and applies the same regex to extract the remote version. Both version strings are normalized with `.lstrip("v").strip()` before comparison so `v0.11.0` and `0.11.0` are treated as equal.

If the versions match, prescient prints a clean "up to date" message and exits with code 0. No git pull, no pip install, nothing else runs.

After a successful network check the result is **cached to `prescient.toml`** (timestamp + boolean) so that subsequent commands within the next 24 hours skip the network entirely. The `--force` flag bypasses both the cache read and the early-exit check.

### Stage 2 - Installation Directory Validation

Before pulling, prescient validates that:

- `~/.prescient` exists
- `~/.prescient/.git` exists (confirms it is a git repository, not a partial install)
- `~/.prescient/.venv/bin/python` exists (confirms the virtual environment is intact)

The home directory is resolved correctly under `sudo` by reading `$SUDO_USER` and calling `pwd.getpwnam()`. This prevents the update from running against `/root/.prescient` when invoked as `sudo prescient update` from a regular user's terminal.

If any of these checks fail, prescient prints a specific error message and exits with code 1 without attempting a pull.

### Stage 3 - Git Pull

Runs:

```bash
git -C ~/.prescient pull origin main
```

Uses `capture_output=True` so git output does not bleed into the terminal. If the pull fails (network error, merge conflict, detached HEAD), `subprocess.CalledProcessError` is caught, the stderr is logged, and an error message is printed.

### Stage 4 - Pip Reinstall

Runs the virtual environment's own Python binary directly:

```bash
~/.prescient/.venv/bin/python -m pip install --upgrade -e .
```

Using `python -m pip` instead of calling the `pip` binary directly ensures pip runs fully inside the virtual environment context, bypassing Debian/Ubuntu's `externally-managed-environment` restriction. The `-e` flag keeps the editable install intact so future `git pull` runs are reflected immediately without reinstalling. `cwd=install_dir` ensures pip installs from the correct source directory.

> **!!Security note:** The update pulls only from the official `main` branch of `github.com/GurKalra/prescient-linux` via HTTPS. No scripts are piped to shell. No arbitrary code runs outside of the trusted git repository and pip install process.

---

## Example Output

**Already up to date:**

```
Verifying system state and fetching latest updates...
System is already up to date. No new OTA releases found.
(Use 'sudo prescient update --force' to reinstall anyway)
```

**Successful update:**

```
Verifying system state and fetching latest updates...
Pulling verified source code via git...
Applying updates to isolated environment...

Prescient updated successfully!
```

**Force reinstall:**

```
Verifying system state and fetching latest updates...
Pulling verified source code via git...
Applying updates to isolated environment...

Prescient updated successfully!
```

**Installation directory not found:**

```
Error: Core installation directory (~/.prescient) or Git repository not found.
Please re-run the initial installation script to repair the local repository.
```

**Virtual environment missing:**

```
Error: Virtual environment not found in ~/.prescient/.venv
Please re-run the installation script to repair it.
```

**Network error or git failure:**

```
Pulling verified source code via git...

Update failed. Please check your network connection or repository state.
```

---

## Warnings

> After a successful update, the new version is not reflected by `get_local_version()` until the `prescient` process restarts. This is a known Python limitation (`importlib.metadata`) caches the package version at import time. The log entry after an update reads the pre-update version. This is cosmetic only and does not affect functionality.

> `--force` performs a full `git pull` and `pip install --upgrade`. If you have made local modifications to the source code in `~/.prescient`, a `git pull` may create merge conflicts. In that case the pull will fail with a `CalledProcessError` and your local changes will be preserved untouched.

> The update only pulls from the `main` branch. There is no flag to pull from a specific branch or tag. For development purposes, use `git -C ~/.prescient checkout <branch>` manually.

---

## Related Commands

- [`prescient tui`](./tui.md) - Surfaces the OTA update banner when a new version is available
- [`prescient uninstall`](./uninstall.md) - Complete removal if you no longer want Prescient
- [`prescient predict`](./predict.md) - The core engine whose improvements are delivered via this command
