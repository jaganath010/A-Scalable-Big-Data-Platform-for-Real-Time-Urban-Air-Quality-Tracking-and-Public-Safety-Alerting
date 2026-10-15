"""
PHASE 11 - ALERT DELIVERY with de-duplication (Telegram / e-mail / outbox)
================================================================================
Project : 23AID302 - Big Data Analytics

The streaming job writes forecast warnings into Hive (stream_alerts). This script
is the last hop: it picks the warnings that matter RIGHT NOW, writes the
resident-facing message (CPCB category + health advice) and delivers it - once.

WHICH WARNINGS (--mode window, the default)
  For every city, look at the forecast hours in (now, now + HORIZON] and take the
  worst one. If its AQI is above the threshold, the city is "under warning".
  Using the clock - not the newest row in the table - means this can run every
  hour without re-fetching anything: as time moves, a different hour of the
  already-scored forecast becomes "next".

DE-DUPLICATION (scripts/alert_state.json)
  A city is messaged only when
     - it was not under warning before, or
     - the severity got WORSE (e.g. Poor -> Severe), or
     - the COOLDOWN (default 6 h) has passed and it is still under warning.
  When a city drops out of warning its state is cleared, so a later recurrence
  alerts again. A phone is never buzzed hourly for the same smog episode.

CHANNELS
  outbox    always on     appends to docs/run_logs/alert_outbox.jsonl
  telegram  env TELEGRAM_BOT_TOKEN, subscribers by city (or TELEGRAM_CHAT_ID for one demo chat)
  email     env SMTP_HOST SMTP_USER SMTP_PASS, subscribers by city
  Without credentials it is a DRY RUN and says so - it never claims a message
  reached a phone when it did not. Secrets come from environment variables only.

SUBSCRIBERS
  scripts/subscribers.csv   columns: city,channel,address
  People can subscribe themselves from Telegram: they message the bot
  "/city Hisar"; run `send_alerts.py --poll-subscribers` (the hourly cycle does)
  and they are added and sent a confirmation.

USAGE
    python send_alerts.py                          # dry run, now = clock
    python send_alerts.py --now "2026-10-15 20:00" # replay a moment in time
    python send_alerts.py --poll-subscribers       # pick up new /city sign-ups
    TELEGRAM_BOT_TOKEN=... python send_alerts.py   # live delivery
================================================================================
"""
import argparse
import csv
import json
import os
import smtplib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("AQ_DATA") or os.path.join(ROOT, "dashboard", "dashboard_data.json")
OUTBOX = os.path.join(ROOT, "docs", "run_logs", "alert_outbox.jsonl")
STATE = os.environ.get("AQ_STATE") or os.path.join(HERE, "alert_state.json")
SUBS = os.path.join(HERE, "subscribers.csv")

RANK = {"Satisfactory": 1, "Moderate": 2, "Poor": 3, "Very Poor": 4, "Severe": 5}
ADVICE = {
    "Moderate": "Sensitive groups (asthma, heart disease, elderly, children) should limit prolonged outdoor exertion.",
    "Poor": "Avoid prolonged outdoor activity. People with breathing problems should stay indoors.",
    "Very Poor": "Stay indoors where possible. Keep windows closed. Wear an N95 mask if you must go out.",
    "Severe": "Avoid all outdoor activity. Seek care if breathing is difficult. Keep windows closed.",
}
CAUSE = {"pm10": "coarse dust (PM10)", "pm2_5": "fine particles (PM2.5)", "pm25": "fine particles (PM2.5)",
         "o3": "ozone (O3)", "no2": "nitrogen dioxide (NO2)", "so2": "sulphur dioxide (SO2)", "co": "carbon monoxide (CO)"}


def band_of(aqi):
    return "Severe" if aqi > 400 else "Very Poor" if aqi > 300 else "Poor" if aqi > 200 else "Moderate" if aqi > 100 else "Satisfactory"


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("T", " ")[:19])


def build_message(a):
    when = parse_ts(a["forecast_for"]).strftime("%d %b, %H:%M")
    cause = CAUSE.get(a["aqi_dominant_pollutant"], a["aqi_dominant_pollutant"])
    return (f"AIR QUALITY WARNING - {a['city']}\n"
            f"Expected by {when}: AQI {int(round(a['aqi_forecast']))} ({a['aqi_band']}), mainly {cause}.\n"
            f"{ADVICE.get(a['aqi_band'], '')}\n"
            f"Source: AirWatch India forecast, CPCB National AQI.")


def pick_alerts(now, horizon_h, min_aqi):
    """Worst forecast hour per city inside (now, now + horizon]."""
    d = json.load(open(DATA, encoding="utf-8"))
    end = now + timedelta(hours=horizon_h)
    best = {}
    for a in d.get("alerts_window", []):
        t = parse_ts(a["forecast_for"])
        if now < t <= end and a["aqi_forecast"] >= min_aqi:
            if a["city"] not in best or a["aqi_forecast"] > best[a["city"]]["aqi_forecast"]:
                best[a["city"]] = a
    return sorted(best.values(), key=lambda a: -a["aqi_forecast"])


def decide(alerts, state, now, cooldown_h):
    """Apply the de-duplication rule. Returns (to_send, suppressed, new_state)."""
    to_send, suppressed, new_state = [], [], {}
    for a in alerts:
        rank = RANK.get(a["aqi_band"]) or RANK[band_of(a["aqi_forecast"])]
        prev = state.get(a["city"])
        age_h = (now - parse_ts(prev["sent_at"])).total_seconds() / 3600 if prev else None
        if prev is None:
            why = "new warning"
        elif rank > prev["rank"]:
            why = f"worse ({prev['band']} -> {a['aqi_band']})"
        elif age_h >= cooldown_h:
            why = f"reminder after {cooldown_h:g} h cooldown"
        else:
            suppressed.append((a, f"already sent {age_h:.1f} h ago ({prev['band']})"))
            new_state[a["city"]] = prev
            continue
        to_send.append((a, why))
        new_state[a["city"]] = {"rank": rank, "band": a["aqi_band"], "sent_at": now.isoformat(timespec="seconds")}
    return to_send, suppressed, new_state      # cities absent from alerts are dropped -> state cleared


def tg_call(token, method, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(params).encode()), timeout=30) as r:
        return json.load(r)


def send_email(to, subject, text):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ["SMTP_USER"], to, subject
    msg.set_content(text)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)
    return True


def load_subscribers():
    return list(csv.DictReader(open(SUBS, encoding="utf-8"))) if os.path.exists(SUBS) else []


def poll_subscribers(token):
    """Telegram sign-ups: a message '/city Hisar' subscribes that chat to Hisar."""
    st = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    offset = st.get("_tg_offset", 0)
    res = tg_call(token, "getUpdates", offset=offset, timeout=0)
    known = {(s["city"].lower(), s["address"]) for s in load_subscribers()}
    added = 0
    new_rows = []
    for u in res.get("result", []):
        offset = max(offset, u["update_id"] + 1)
        m = u.get("message") or {}
        txt = (m.get("text") or "").strip()
        chat = str((m.get("chat") or {}).get("id", ""))
        if not chat:
            continue
        if txt.lower().startswith("/city"):
            city = txt[5:].strip().title()
            if not city:
                tg_call(token, "sendMessage", chat_id=chat, text="Send /city followed by your city, e.g. /city Hisar")
            elif (city.lower(), chat) in known:
                tg_call(token, "sendMessage", chat_id=chat, text=f"You are already subscribed to {city}.")
            else:
                new_rows.append({"city": city, "channel": "telegram", "address": chat})
                known.add((city.lower(), chat))
                added += 1
                tg_call(token, "sendMessage", chat_id=chat, text=f"Subscribed. You will get air-quality warnings for {city}.")
        elif txt.lower().startswith("/start"):
            tg_call(token, "sendMessage", chat_id=chat, text="AirWatch India. Send /city followed by your city, e.g. /city Hisar, to get warnings.")
    if new_rows:
        write_header = not os.path.exists(SUBS)
        with open(SUBS, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["city", "channel", "address"])
            if write_header:
                w.writeheader()
            w.writerows(new_rows)
    st["_tg_offset"] = offset
    json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
    print(f"subscriber poll: {len(res.get('result', []))} update(s), {added} new subscription(s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help='replay a moment, e.g. "2026-10-15 20:00" (default: the clock)')
    ap.add_argument("--horizon-hours", type=float, default=6, help="warn about forecast hours up to this far ahead")
    ap.add_argument("--cooldown-hours", type=float, default=6)
    ap.add_argument("--min-aqi", type=float, default=151, help="project rule: alert when forecast AQI > 150")
    ap.add_argument("--top", type=int, default=0, help="cap the number of cities messaged (0 = all)")
    ap.add_argument("--poll-subscribers", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if args.poll_subscribers:
        if not token:
            raise SystemExit("--poll-subscribers needs TELEGRAM_BOT_TOKEN")
        poll_subscribers(token)

    now = parse_ts(args.now) if args.now else datetime.now().replace(microsecond=0)
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    smtp_ok = all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    subs = load_subscribers()
    live = bool(token and (chat or subs)) or (smtp_ok and subs)
    print(f"now: {now}   mode: {'LIVE delivery' if live else 'DRY RUN (no credentials set - nothing leaves this machine)'}")

    alerts = pick_alerts(now, args.horizon_hours, args.min_aqi)
    state = {k: v for k, v in (json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}).items() if not k.startswith("_")}
    tg_offset = (json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}).get("_tg_offset")
    to_send, suppressed, new_state = decide(alerts, state, now, args.cooldown_hours)
    if args.top:                                   # unsent cities keep their old state, so they alert next pass
        for a, _ in to_send[args.top:]:
            if a["city"] in state:
                new_state[a["city"]] = state[a["city"]]
            else:
                new_state.pop(a["city"], None)
        to_send = to_send[:args.top]
    print(f"{len(alerts)} city(ies) under warning in the next {args.horizon_hours:g} h -> "
          f"{len(to_send)} to send, {len(suppressed)} suppressed (already sent)\n")

    os.makedirs(os.path.dirname(OUTBOX), exist_ok=True)
    sent = failed = 0
    with open(OUTBOX, "a", encoding="utf-8") as ob:
        for a, why in to_send:
            text = build_message(a)
            targets = [(s["channel"], s["address"]) for s in subs if s["city"].lower() == a["city"].lower()]
            if not subs and token and chat:
                targets = [("telegram", chat)]
            print("-" * 70 + f"\nTO: {a['city']} ({len(targets)} recipient(s)) - {why}\n{text}")
            status = "dry-run" if not targets else "no-credentials"
            for ch, addr in targets:
                try:
                    if ch == "telegram" and token:
                        ok = tg_call(token, "sendMessage", chat_id=addr, text=text).get("ok", False)
                    elif ch == "email" and smtp_ok:
                        ok = send_email(addr, f"Air quality warning - {a['city']}", text)
                    else:
                        ok = False
                    status = "delivered" if ok else "no-credentials"
                    sent += bool(ok)
                except Exception as e:           # a failed send is recorded, never hidden
                    status = f"failed: {e}"
                    failed += 1
            ob.write(json.dumps({"ts": now.isoformat(timespec="seconds"), "city": a["city"], "forecast_aqi": a["aqi_forecast"],
                                 "band": a["aqi_band"], "reason": why, "status": status, "message": text}) + "\n")
            if failed and status.startswith("failed"):
                new_state.pop(a["city"], None)    # not delivered -> try again next hour
    for a, why in suppressed:
        print(f"suppressed: {a['city']:<14} {why}")
    if tg_offset is not None:
        new_state["_tg_offset"] = tg_offset
    json.dump(new_state, open(STATE, "w", encoding="utf-8"), indent=1)
    print("-" * 70 + f"\nsummary: {len(to_send)} message(s) built, {sent} delivered, {failed} failed, {len(suppressed)} suppressed -> {OUTBOX}")


if __name__ == "__main__":
    main()
