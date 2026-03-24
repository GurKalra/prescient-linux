# `prescient tui`

> The Gruvbox-themed Terminal User Interface that serves as prescient's visual command center. Handling first-time onboarding, system health monitoring, OTA update notifications, and live command documentation browsing, all from a single keyboard-driven screen.

---

## Purpose

`tui` is the recommended entry point for prescient, especially on a fresh install. It is a fully interactive, keyboard-driven dashboard built with [Textual](https://github.com/Textualize/textual). It does two distinct jobs depending on the state of your system.

**On a fresh install (hooks not yet installed):** The TUI detects that no package manager hook exists and boots directly into the **Onboarding Screen**. From here you can press Enter to trigger `sudo prescient install-hooks` without ever leaving the interface. Once hooks are installed, it immediately hot-swaps to the **Snapshot Configuration Screen** to ask for your auto-snapshot preference, then lands on the main dashboard.

**On an established install (hooks present):** The TUI boots straight into the **Main Dashboard**. A split-pane layout with a command navigator on the left and a live documentation viewer on the right. A background thread silently checks for OTA updates and surfaces a banner if a newer version of prescient is available.

The TUI is entirely **read-only and safe**. It never executes system commands on your behalf except during the explicit onboarding flow. You cannot accidentally trigger a rollback or heal sequence by browsing it.

---

## Usage

```bash
prescient tui
```

### Options

| Flag     | Description                               |
| -------- | ----------------------------------------- |
| _(none)_ | No flags. The TUI is fully self-managing. |

> **!!Tip:** `prescient tui` is the only command that does **not** require `sudo`. It is intentionally designed to be safe to open as a regular user. The onboarding flow will prompt for your password at the point it needs root (hook installation), not before.

---

## Prerequisites

- [x] Python 3.11+ with `textual>=0.52.0` installed (handled by `install.sh`)
- [x] A terminal emulator with at least 80×24 character support — the DuneWave animation requires a minimum of 10 columns and 3 rows to render
- [ ] `sudo` access required only during the first-time onboarding flow (hook installation)
- [ ] `/var/log/prescient.log` must exist for the health status widget to show a real status — it is created automatically the first time `predict` runs as root

---

## Screens

The TUI has three distinct screens. Which one you see first depends on whether hooks are installed.

### Onboarding Screen (First Launch)

Shown when neither `/etc/apt/apt.conf.d/99prescient-guardian` (APT) nor `/etc/pacman.d/hooks/99-prescient-guardian.hook` (Pacman) exist on the system.

- Displays the ASCII prescient logo centered on screen
- Prompts the user to press **Enter** to begin hook installation
- On Enter, the TUI **suspends itself** (drops back to the raw terminal), runs `sudo prescient install-hooks` as a subprocess, and waits for it to complete
- On success, it hot-swaps seamlessly into the **Snapshot Configuration Screen** without requiring a restart
- On failure, it displays an error message and the path to check in `prescient.log`

### Snapshot Configuration Screen

Shown immediately after a successful first-time hook installation. Never shown again after the choice is saved.

- Asks whether prescient should automatically create system snapshots before high-risk updates
- **`y`:** enables auto-snapshots, saves `auto_snapshot = true` to `prescient.toml`
- **`n`:** disables auto-snapshots, saves `auto_snapshot = false` to `prescient.toml`
- Either choice immediately transitions to the **Main Dashboard** and triggers a `"Vanguard Engine Online."` system notification

### Main Dashboard

The primary interface shown on every subsequent launch. A two-column split layout:

**Left Sidebar ---- Command Navigator**

A keyboard-navigable list of all prescient commands. Highlighting a command instantly loads its full Markdown documentation into the right pane. The currently available commands in the list are:

`tui` · `install-hooks` · `predict` · `diagnose` · `undo` · `heal` · `update` · `uninstall`

At the bottom of the sidebar, pinned above the footer, is the **Health Status Widget**. It reads `/var/log/prescient.log` in reverse to find the most recent audit result and displays one of three states:

| State                   | Condition                                                        |
| ----------------------- | ---------------------------------------------------------------- |
| `Healthy` (green)       | Last log entry contains `"Pre-flight audit passed successfully"` |
| `Issues Detected` (red) | Last log entry contains `"VETO"` or `"BROKEN"`                   |
| `Unknown` (yellow)      | Log file doesn't exist or no audit has been run yet              |

**Right Pane - Content Area**

Split vertically into two zones:

- **Update Banner** (top, height 8): Hidden by default. If the background OTA check finds a newer version on GitHub, this zone reveals a yellow update notice and instructs the user to press `u`. Behind the banner, the **DuneWave** animation always runs. A three layered ASCII sine waves rendered at 12 frames per second using `math.sin`, tinted in Gruvbox green (`#8ec07c`).
- **Documentation Viewer** (bottom): A scrollable Markdown renderer. Loads the `.md` file from `docs/commands/` that corresponds to whichever command is highlighted in the sidebar. Defaults to a prompt message on launch.

---

## Keyboard Controls

All controls work from within the Main Dashboard.

| Key      | Action                                                             |
| -------- | ------------------------------------------------------------------ |
| `j`      | Move cursor down in the command list                               |
| `k`      | Move cursor up in the command list                                 |
| `l`      | Focus the documentation viewer (enables scrolling with arrow keys) |
| `h`      | Return focus to the command list sidebar                           |
| `r`      | Refresh the health status widget by re-reading the log file        |
| `u`      | Jump the sidebar cursor directly to the `update` command entry     |
| `?`      | Show a help notification summarizing all keybindings               |
| `q`      | Quit the TUI                                                       |
| `Escape` | Quit the TUI                                                       |

| Onboarding Key | Action                  |
| -------------- | ----------------------- |
| `Enter`        | Begin hook installation |

| Config Screen Key | Action                              |
| ----------------- | ----------------------------------- |
| `y`               | Enable auto-snapshots and continue  |
| `n`               | Disable auto-snapshots and continue |

---

## Under the Hood

### Boot Sequence

When `prescient tui` is called, `cli.py` skips the global OTA update check (the `tui` subcommand is explicitly excluded from the `@app.callback()` check). It then imports and instantiates `PrescientTUI` (a `textual.App` subclass) and calls `.run()`.

On mount, `PrescientTUI.compose()` checks for the existence of the APT or Pacman hook files and yields either `MainDashboard` or `InstallScreen` accordingly, followed by a `Footer` widget.

### OTA Update Check

When `MainDashboard` mounts, it calls `self.app.run_update_check()`. This spins up a background worker thread (via `@work(thread=True)`) that calls `check_for_updates(force_network=True)`, bypassing the 24-hour cache. If an update is found, it uses `call_from_thread()` to safely update the UI from the worker thread, making the update banner visible.

### Health Status

`get_last_health_status()` reads `/var/log/prescient.log` line by line in reverse order and returns on the first line that matches either a passing or failing audit signature. This means it always reflects the most recent `predict` run, not the first one.

### DuneWave Animation

The `DuneWave` widget renders three offset sine waves as ASCII underscore characters (`_`) into a 2D character grid on every tick. It runs at 12 FPS (`set_interval(1/12, self.tick)`), advancing the phase offset by `0.35` radians per frame. The three layers use different amplitude multipliers (`1.0`, `0.6`, `0.3`) and phase offsets (`0`, `+2.0`, `+4.0`) to create the illusion of depth. The widget gracefully degrades to `"__"` if its render area is smaller than 10×3 characters.

### Onboarding Hot-Swap

After `install-hooks` completes successfully inside the suspended terminal, the TUI resumes and calls `self.remove()` on `InstallScreen`, then mounts `ConfigScreen` in its place and all that without restarting the application. After the snapshot preference is saved, `_finalize_onboarding()` removes `ConfigScreen` and mounts `MainDashboard`, completing the full first-run flow in a single session.

---

## Warnings

> The TUI suspends itself and drops to the raw terminal during hook installation. Do not close the terminal window during this step. If installation fails, re-open the TUI and check the error message or inspect `/var/log/prescient.log` and `/tmp/prescient-user.log`.

> The health status widget reads the log file at mount time and again when `r` is pressed. It does not auto-refresh. If `predict` runs while the TUI is open (e.g. you triggered an `apt upgrade` in another terminal), press `r` to see the updated status.

> The documentation viewer loads `.md` files from `docs/commands/` relative to the prescient installation root (`~/.prescient`). If a doc file is missing for a given command, the viewer displays a `# Missing Doc` message with the expected path. This does not affect any prescient functionality.

> `prescient tui` is excluded from the global OTA check that runs before all other commands. The TUI performs its own non-blocking OTA check internally via a background thread, which is why no update warning is printed to the terminal before the interface launches.

---

## Related Commands

- [`prescient install-hooks`](./install-hooks.md) — What the onboarding screen calls on first launch
- [`prescient predict`](./predict.md) — The engine whose audit results populate the health status widget
- [`prescient update`](./update.md) — The command the update banner directs you to run
- [`prescient diagnose`](./diagnose.md) — Navigate to it from the sidebar when investigating a crash
