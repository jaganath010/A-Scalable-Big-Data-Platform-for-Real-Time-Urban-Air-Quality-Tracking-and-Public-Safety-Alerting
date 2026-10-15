# Alerting people - hourly loop with de-duplication

Files: `scripts/run_hourly_cycle.py`, `scripts/send_alerts.py`, `dashboard/export_dashboard_data.py` (exports `alerts_window`).

## How it runs
| Stage | What | Needs Docker | How often |
|---|---|---|---|
| SCORE | fetch CAMS + weather -> enrich on YARN -> stream scoring -> Hive export -> website | yes | every 6 h (CAMS refreshes a few times a day) |
| DISPATCH | pick the worst forecast hour per city in the next 6 h, de-duplicate, message people | no | every hour |

Only forecast hours newer than the last scored hour (`scripts/stream_watermark.txt`) are given to the stream, so a re-fetch never scores an hour twice.

## De-duplication (`scripts/alert_state.json`)
A city is messaged only if it is newly under warning, the severity got worse, or 6 h have passed (reminder). When it drops out of warning its state is cleared.
Verified on a replay of the real October forecast: `docs/run_logs/hourly_dedupe_demo.log` (20:00 messages 2 cities; 21:00 suppresses the 2 already sent and messages 2 others; 02:00 next day: no warnings).

## Telegram setup (free; the only credential needed)
1. In Telegram open **@BotFather** -> `/newbot` -> copy the **token**.
2. Set it for the session: `$env:TELEGRAM_BOT_TOKEN = "<token>"` (never commit it).
3. People subscribe by messaging the bot `/city Hisar`. `send_alerts.py --poll-subscribers` (the hourly cycle does this) adds them to `scripts/subscribers.csv` and replies.
4. For a one-person demo skip step 3: message the bot anything, then `$env:TELEGRAM_CHAT_ID = "<your chat id>"`.
5. `python scripts\run_hourly_cycle.py --once dispatch`

## Run
```
python scripts\run_hourly_cycle.py --once score --manage-docker   # one scoring cycle (starts/stops Docker itself)
python scripts\run_hourly_cycle.py --once dispatch                # one alert pass
python scripts\run_hourly_cycle.py --loop --manage-docker         # forever: dispatch hourly, score every 6 h
```

## Verified vs not
- Verified: de-dup rules (new / worse / cooldown / cleared), `--top` cap keeps unsent cities eligible, export of `alerts_window` from Hive, Docker start/stop handling, dry-run dispatch on the real October forecast.
- NOT yet run end to end: a full SCORE stage with fresh data (fetch -> YARN -> stream -> export) in the new hourly form, and any real Telegram/e-mail delivery (no token set). SMS needs a paid gateway.

## End-to-end run, 15 Oct 2026 14:00 (docs/run_logs/hourly_score_e2e.log)
- Ran: Docker auto-start -> fetch (230 cities) -> upload -> LiveEnrichment on YARN (16,560 rows) -> watermark filter -> Docker auto-stop. Result: 0 hours newer than the watermark (2026-10-15 23:00), so nothing was handed to the stream - correct, the source only extends to the end of the current day.
- Bug found and fixed in that run: the weather fetcher skipped existing files and reused the 1-15 Oct weather next to the fresh 2-day air-quality pull. step_fetch now clears both staging folders first.
- NOT exercised yet: the stream hand-off, batch wait and export inside run_hourly_cycle.py. They run the first time a new day of hours exists (16 Oct onward).

## Live mode of the website (dashboard/serve_live.py)
`python dashboard/serve_live.py` serves the page at http://localhost:8000 and rebuilds it from `dashboard_data.json` on every request. The page polls `/api/version` every 10 seconds and reloads itself when the pipeline publishes new data; the header badge shows "LIVE - checked HH:MM:SS". Tested by changing the data file while the page was open (page reloaded within one poll).
- The numbers change only when a scoring cycle finishes and publishes (`run_hourly_cycle.py --once score`); CAMS itself refreshes a few times a day.
- Opened as a file, or on GitHub Pages, the page is a static snapshot and its badge says so.

## Which warnings the board shows (fixed 15 Oct 2026)
The cards used each city's PEAK warning over the whole 1-15 Oct run, so on 15 Oct a card could say "by 20:00 on 2026-10-11". The board now shows, per city, the worst forecast hour in the NEXT 6 hours after "now": the clock in live mode (served by serve_live.py), or the last scored hour in the static snapshot. If the live data is more than 3 h older than the clock the banner says so. The whole-run charts (warnings per hour, causes) are labelled as such. The export (`alerts_window`) now carries observed_at, pm25_now and pm25_forecast for the last 24 forecast hours.
Result at 23:20 on 15 Oct: 72 cities forecast above AQI 150 for 00:00 on 16 Oct (worst Hisar, AQI 429). The data ends at 2026-10-16 00:00, so after that a new scoring run is needed.
