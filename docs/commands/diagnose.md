# `prescient diagnose`

> The Pattern Interpretation Engine that parses your current boot's error logs and translates cryptic system failures into a ranked, human-readable breakdown of what went wrong and why.

---

## Purpose

`diagnose` is your first tool to reach for after a system crash, a broken update, or any situation where something stopped working and you don't know why. It runs entirely without root in most cases, reads only from `journalctl`, and produces nothing destructive.

It is especially designed for the **TTY scenario**, when your graphical environment is dead and you're staring at a black screen with a blinking cursor. You don't need a browser, a man page, or Stack Overflow. You run `prescient diagnose` and it tells you which subsystem failed, how many times, and what it last said before dying.

The `--share` flag extends this for **remote debugging** as it packages the full report into a single URL you can paste into a chat or forum without needing a working browser or GUI.

---

## Usage

```bash
# Standard diagnostic scan (no root required on most systems)
prescient diagnose

# Package and export crash report to termbin.com
prescient diagnose --share
```

### Options

| Flag‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ | Description                                                                                                                                                                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--share`                                 | Builds a full crash report (structured summary + last 50 raw log lines) and uploads it to `termbin.com` via raw TCP socket. Returns a short URL. Falls back to saving locally at `/tmp/prescient_crash_report.txt` if offline. |

> **!!Tip:** `prescient diagnose` reads only the **current boot** (`-b 0`). If you rebooted after a crash, the logs from the crashed boot are in the previous boot (`-b -1`). Prescient currently targets the current boot (run immediately after a crash before rebooting for best results.)

---

## Prerequisites

- [ ] `systemd` and `journalctl` must be installed (standard on Ubuntu, Debian, Arch, Fedora)
- [ ] Root is **recommended** for full journal access — some systems restrict journal reads to the `systemd-journal` group
- [ ] Network access required for `--share` upload (offline fallback available automatically)

---

## Under the Hood

### Standard Run

1. **Log Fetch** - Runs `journalctl -p 3 -b -o json` to pull all errors, criticals, alerts, and emergencies from the current boot as structured JSON. Priority 3 = errors and above (includes 0-3: emergency, alert, critical, error).

2. **Culprit Grouping** - Each log entry is assigned to a subsystem using a fallback chain.

3. **Ranking** - All identified culprits are sorted by error count, descending. The subsystem that threw the most errors is listed first.

4. **Table Output** - The **top 5** worst offenders are displayed in a formatted table showing:
   - Failing subsystem name
   - Total error count for this boot
   - Latest error message (truncated to 70 characters)

### `--share` Flag

When `--share` is passed, after the table is displayed prescient builds a structured crash report containing:

1. A timestamped header with kernel version (`uname -r`) and OS info
2. The structured culprit summary (same data as the table, in plain text)
3. The last **50 lines** of raw `journalctl -p 3 -b -n 50` output

The report is uploaded to `termbin.com` via a **raw TCP socket on port 9999** — no `netcat`, no `curl`, no external dependencies. The socket sends the data, signals EOF with `SHUT_WR`, and reads the URL response. A **30-second timeout** prevents hanging if the network is degraded.

If the upload fails for any reason (offline, timeout, unexpected response), the full report is saved locally to `/tmp/prescient_crash_report.txt` with `0o600` permissions (owner-read only) and the path is printed to the terminal.

> **!!Privacy note:** Logs uploaded to `termbin.com` are public and accessible to anyone with the URL. Avoid using `--share` on systems with sensitive service names or credentials in log output.

---

## Example Output

**Clean system (no errors this boot):**

```
 prescient is dynamically analyzing current boot logs...

 No critical errors found in the current boot log!
```

**System with failures:**

```
 prescient is dynamically analyzing current boot logs...

!!!!! System Instability Detected (47 total errors)

 Failing Subsystem          Error Count   Latest Error Message
 ──────────────────────────────────────────────────────────────────────────────
 kernel                          32        vmwgfx 0000:00:02.0: *ERROR* Please switch to a supported gra...
 NetworkManager                   9        <error> [1742673901.3241] dhcp4 (enp0s3): request timed out
 gdm3                             4        Failed to start service: org.gnome.DisplayManager
 systemd                          1        Failed to start casper-md5check.service
 dbus                             1        Unable to autolaunch a dbus-daemon without a $DISPLAY

 Tip: If you are stuck in a TTY, identify the failing subsystem above.
   If an update caused this, run your Timeshift/Snapper restore command.
```

**With `--share` — successful upload:**

```
!!!!! System Instability Detected (47 total errors)
[... table as above ...]

Packaging crash report...
Note: Logs will be uploaded publicly to termbin.com. Avoid sharing on sensitive systems.
Attempting to upload to termbin.com...
Report exported successfully!
Share this URL for support: https://termbin.com/url
```

**With `--share` — offline fallback:**

```
Attempting to upload to termbin.com...
Network upload failed (Are you offline?).
Saved crash report locally instead: /tmp/prescient_crash_report.txt

You can read it with: sudo cat /tmp/prescient_crash_report.txt
```

---

## Warnings

> Logs uploaded via `--share` are **publicly accessible** on termbin.com. The URL is not secret. Do not use on production servers or systems where service names, hostnames, or error messages may contain sensitive information.

> `diagnose` reads the **current boot only**. If your system crashed and you have already rebooted, the crash logs are in the previous boot. Run `journalctl -p 3 -b -1` manually to inspect the previous boot's errors - prescient currently does not expose a `--previous-boot` flag.

---

## Related Commands

- [`prescient heal`](./heal.md) - Automatically propose and execute fixes for the failures `diagnose` surfaces
- [`prescient undo`](./undo.md) - If an update caused the crash, roll back to the pre-update snapshot
- [`prescient predict`](./predict.md) - Prevent this situation from happening in the first place
