# Scheduling — Daily Opportunity Cycle

The daily opportunity cycle (`scan-opportunities → resolve-calls → weekly backfill`) runs locally
via macOS **launchd**. Scheduling is intentionally local rather than cloud-hosted: ADR-007 chose
local SQLite as the persistence layer, which means the data store lives on this machine. A cloud
runner would have no access to that database, so local scheduling is the natural consequence of
that decision (see [ADR-007 deviation note](#adr-007-deviation-note) below).

---

## launchd plist

Save the file below as `~/Library/LaunchAgents/com.tirthjoshi.stockrec.daily-cycle.plist`.

> **Before saving**, replace `/PATH/TO/venv/bin/python` with the path to the Python interpreter
> inside your activated virtual environment. Run `which python` with the environment active to get
> the correct path (e.g. `/Users/tirthjoshi/miniconda3/envs/multi-modal-stock-ml/bin/python`).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>

    <!-- Job identity -->
    <key>Label</key>
    <string>com.tirthjoshi.stockrec.daily-cycle</string>

    <!-- Command to run -->
    <key>ProgramArguments</key>
    <array>
        <string>/PATH/TO/venv/bin/python</string>
        <string>-m</string>
        <string>application.cli</string>
        <string>daily-cycle</string>
    </array>

    <!-- Working directory (must match the repo root) -->
    <key>WorkingDirectory</key>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender</string>

    <!-- Run at 08:00 local machine time (pre-market, ~30 min before US open)
         DST caveat: launchd uses LOCAL time, not UTC. When the machine observes
         EDT (UTC-4, Mar–Nov) this fires at 12:00 UTC; under EST (UTC-5, Nov–Mar)
         it fires at 13:00 UTC. Adjust Hour if you want a fixed UTC anchor. -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- Log files — directory must exist; create with:
         mkdir -p data/reports  (relative to WorkingDirectory above) -->
    <key>StandardOutPath</key>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/daily_cycle.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/daily_cycle.log</string>

    <!-- Environment variables
         Reddit credentials are optional. Remove the three Reddit keys entirely
         if you are not using the Reddit adapter.
         See .env.example for the full list of supported variables. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>REDDIT_CLIENT_ID</key>
        <string>REPLACE_WITH_YOUR_REDDIT_CLIENT_ID</string>
        <key>REDDIT_CLIENT_SECRET</key>
        <string>REPLACE_WITH_YOUR_REDDIT_CLIENT_SECRET</string>
        <key>REDDIT_USER_AGENT</key>
        <string>REPLACE_WITH_YOUR_REDDIT_USER_AGENT</string>
    </dict>

    <!-- Do not run immediately when loaded; wait for the scheduled time -->
    <key>RunAtLoad</key>
    <false/>

</dict>
</plist>
```

---

## Installation

### 1. Ensure the log directory exists

```bash
mkdir -p "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports"
```

### 2. Copy the plist to LaunchAgents

```bash
cp com.tirthjoshi.stockrec.daily-cycle.plist ~/Library/LaunchAgents/
```

### 3. Load and enable the job

```bash
launchctl load -w ~/Library/LaunchAgents/com.tirthjoshi.stockrec.daily-cycle.plist
```

The `-w` flag removes the disabled key (if present) so the job persists across reboots.

### 4. Verify the job is registered

```bash
launchctl list | grep stockrec
# Expected output (PID is - when not currently running):
# -    0    com.tirthjoshi.stockrec.daily-cycle
```

### 5. Trigger a one-off run immediately (optional smoke test)

```bash
launchctl start com.tirthjoshi.stockrec.daily-cycle
# Then tail the log:
tail -f "/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/daily_cycle.log"
```

### Unload (disable scheduling)

```bash
launchctl unload -w ~/Library/LaunchAgents/com.tirthjoshi.stockrec.daily-cycle.plist
```

---

## Reddit credentials

Reddit credentials are **optional** — the daily cycle falls back to RSS-only sentiment if they are
absent. To supply them, choose one of two approaches:

**Option A — plist EnvironmentVariables block (recommended for scheduled jobs)**

Edit the `EnvironmentVariables` dict in the plist directly (as shown above). Values are stored in
plaintext in `~/Library/LaunchAgents/`, which launchd owns and reads before forking the process.
Set file permissions to `600`:

```bash
chmod 600 ~/Library/LaunchAgents/com.tirthjoshi.stockrec.daily-cycle.plist
```

**Option B — sourced `.env` file**

Copy `.env.example` to `.env` in the repo root and fill in the Reddit values. Then wrap the
`daily-cycle` invocation in a shell script that sources `.env` first, and point `ProgramArguments`
at that script instead of the Python interpreter directly.

---

## Live APIs — not run in CI

The daily cycle calls live external APIs:

| Source | API |
|--------|-----|
| Price data | yfinance (Yahoo Finance) |
| News sentiment | GDELT DOC API |
| Search trends | Google Trends (pytrends) |
| Market events | Wikipedia (event context) |

These calls are **intentionally excluded from the CI test suite**. All adapters are tested with
fakes/mocks; real network calls only happen in the scheduled daily run. Do not add `daily-cycle`
to `.github/workflows/`.

---

## Laptop sleep

launchd will **not** fire a scheduled job while the Mac is asleep or the lid is closed. This is a
direct consequence of the ADR-007 local-scheduler decision: a cloud runner would sidestep the
problem, but cloud runners cannot reach the local SQLite file, so we accept the trade-off.

**Mitigation — wrap the job in `caffeinate`:**

Replace the `ProgramArguments` in the plist with:

```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/bin/caffeinate</string>
    <string>-i</string>
    <string>/PATH/TO/venv/bin/python</string>
    <string>-m</string>
    <string>application.cli</string>
    <string>daily-cycle</string>
</array>
```

`caffeinate -i` holds a system-sleep assertion for the lifetime of the child process. launchd
launches `caffeinate`, which keeps the machine awake just long enough to complete the daily cycle,
then releases the assertion and lets the system sleep normally. No external tool is required —
`/usr/bin/caffeinate` ships with macOS.

**Alternative — Energy Saver / `pmset`:**

If you prefer a schedule-based approach rather than per-job wrapping, you can use `pmset` to
schedule a wake window around 08:00:

```bash
# Wake at 07:55, allow natural sleep afterwards
sudo pmset repeat wakeorpoweron MTWRFSU 07:55:00
```

This is coarser but works without modifying the plist. The `caffeinate` wrapper is recommended
because it is scoped to the daily-cycle process and requires no `sudo`.

**Honest caveat:** if the machine is powered off (not just sleeping), neither approach helps.
The daily cycle will simply be skipped for that day. This is acceptable for a local research
tool — see ADR-007 for the rationale behind the local-scheduler decision.

---

## Holdings Discipline daily run (ADR-048)

A second, independent job logs a dated discipline assessment of the real holdings every weekday so
the **forward-calibration gate** (ADR-048) accrues `REDUCE` flags to resolve. It writes only
gitignored files (`data/personal/discipline_log.jsonl` for the dated flags,
`data/personal/holdings_risk_detail.txt` for the per-ticker table) and a masked stdout cron log
(`data/personal/holdings_risk_cron.log`). Nothing personal is committed.

The plist is installed at `~/Library/LaunchAgents/com.tirthjoshi.holdings-risk-daily.plist`. It runs
**weekdays (Mon–Fri) at 13:30 local** — ~30 min after the US close (16:00 ET) so yfinance has the
day's final daily bar. Weekends are skipped so Friday's close is not re-logged on Sat/Sun.

```bash
# Already installed + loaded this session. To reload after edits:
launchctl unload ~/Library/LaunchAgents/com.tirthjoshi.holdings-risk-daily.plist
launchctl load -w ~/Library/LaunchAgents/com.tirthjoshi.holdings-risk-daily.plist
launchctl list | grep holdings-risk            # confirm loaded (exit code 0)
# Run once now to test:
launchctl start com.tirthjoshi.holdings-risk-daily
# Stop scheduling:
launchctl unload -w ~/Library/LaunchAgents/com.tirthjoshi.holdings-risk-daily.plist
```

It reuses the same `caffeinate -i` sleep handling and the same powered-off caveat as the daily
cycle above.

**Calibration caveat (ADR-048):** daily re-logging produces *overlapping* 21-day windows for a
name that stays broken — the gate's `n ≥ 30` is a nominal count of REDUCE observations, not 30
independent events (consecutive days are autocorrelated). For a personal decision-support tool this
is acceptable; the gate is a trust signal, not a publishable significance test. If a cleaner read is
wanted later, de-duplicate to one flag per name per non-overlapping window before scoring.

---

## Discipline forward-calibration daily logging (ADR-048/051)

The opportunity `daily-cycle` plist above does NOT log discipline verdicts. For the
ADR-048 REDUCE-flag forward gate you must run `holdings-risk` itself daily so the
forward log accrues date-diverse `as_of` snapshots. Save as
`~/Library/LaunchAgents/com.tirthjoshi.stockrec.discipline-daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.tirthjoshi.stockrec.discipline-daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/scripts/discipline_daily.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DISCIPLINE_PYTHON</key>
    <string>/PATH/TO/venv/bin/python</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/discipline_daily.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/tirthjoshi/My Data Science Projects/ML_Portfolio_Projects/multi-modal-stock-recommender/data/reports/discipline_daily.log</string>
</dict>
</plist>
```

Load: `launchctl load -w ~/Library/LaunchAgents/com.tirthjoshi.stockrec.discipline-daily.plist`

**Laptop sleep:** launchd will not fire while asleep. Keep the machine awake at the
scheduled time (`caffeinate -i` during a known-awake window) or run `pmset schedule
wake` before 18:00. Verify the cron is alive with
`python -m application.cli discipline-calibration-status` — the "last logged … days
ago" line is your dead-cron detector.

---

## ADR-007 deviation note

ADR-007 chose local SQLite as the persistence layer to keep the project self-contained and avoid
cloud infrastructure costs during the research phase. A direct consequence is that scheduling must
also be local: a cloud cron runner (GitHub Actions scheduled workflow, AWS EventBridge, etc.) cannot
read or write the SQLite file on this machine. launchd is therefore not a separate architectural
choice — it is the scheduling mechanism implied by ADR-007. If the project ever migrates to a
hosted database, the scheduling decision should be revisited (see docs/adr/ for the relevant ADR).
