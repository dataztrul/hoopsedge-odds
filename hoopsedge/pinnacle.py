"""Pinnacle pre-game snapshots (moneyline, main spread, main total) for every European league.

Two requests cover all basketball. Only prices that changed since the last snapshot are written,
so data/odds/ stays small enough for git.
"""
from __future__ import annotations

import csv
import datetime as dt
import json

import pandas as pd

from .util import CONFIG, DATA, american_to_decimal, get, league_by_pinnacle

API = "https://guest.api.arcadia.pinnacle.com/0.1/sports/4/{what}"
ODDS_COLS = ["ts", "matchup_id", "league", "type", "line", "dec_1", "dec_2", "limit", "version", "start"]
MATCHUP_COLS = ["matchup_id", "league_key", "pin_league", "start", "home", "away", "first_seen", "last_seen"]


def _prefixes() -> list[str]:
    return json.loads((CONFIG / "leagues.json").read_text())["log_all_pinnacle_leagues_matching"]


def fetch():
    m = get(API.format(what="matchups"), json_out=True)
    k = get(API.format(what="markets/straight"), json_out=True)
    return m or [], k or []


def parse(matchups, markets, now: dt.datetime):
    by_pin = league_by_pinnacle()
    pref = _prefixes()
    keep = {}
    for x in matchups:
        if x.get("parentId") or x.get("isLive") or x.get("type") == "special":
            continue
        lname = (x.get("league") or {}).get("name", "")
        if lname not in by_pin and not any(lname.startswith(p) for p in pref):
            continue
        if "Women" not in lname and any(w in lname for w in ("U16", "U18", "U20", "U21", "Youth", "Espoirs")):
            continue
        parts = {p.get("alignment"): p.get("name") for p in x.get("participants", [])}
        if "home" not in parts or "away" not in parts:
            continue
        start = pd.Timestamp(x["startTime"])
        if start <= now:
            continue
        keep[x["id"]] = dict(matchup_id=x["id"], league_key=(by_pin.get(lname) or {}).get("key", ""), pin_league=lname,
                             start=start.isoformat(), home=parts["home"], away=parts["away"])
    rows = []
    for k in markets:
        mid = k.get("matchupId")
        if mid not in keep or k.get("period") != 0 or k.get("isAlternate") or k.get("status") != "open":
            continue
        t = k.get("type")
        if t not in ("moneyline", "spread", "total"):
            continue
        pr = {p.get("designation"): p for p in k.get("prices", [])}
        a, b = ("home", "away") if t != "total" else ("over", "under")
        if a not in pr or b not in pr:
            continue
        line = pr[a].get("points")
        lim = next((l.get("amount") for l in k.get("limits", []) if l.get("type") == "maxRiskStake"), None)
        rows.append(dict(ts=now.isoformat(), matchup_id=mid, league=keep[mid]["pin_league"], type=t, line=line,
                         dec_1=round(american_to_decimal(pr[a]["price"]), 4), dec_2=round(american_to_decimal(pr[b]["price"]), 4),
                         limit=lim, version=k.get("version"), start=keep[mid]["start"]))
    return keep, rows


def snapshot(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    matchups, markets = fetch()
    keep, rows = parse(matchups, markets, now)
    state_p = DATA / "state" / "last_prices.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    changed = []
    for r in rows:
        key = f"{r['matchup_id']}|{r['type']}"
        sig = f"{r['line']}|{r['dec_1']}|{r['dec_2']}"
        if state.get(key, {}).get("sig") != sig:
            changed.append(r)
            state[key] = {"sig": sig, "start": r["start"]}
    # forget games that started more than 2 days ago
    cutoff = (now - dt.timedelta(days=2)).isoformat()
    state = {k: v for k, v in state.items() if v.get("start", "") > cutoff}
    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(json.dumps(state, separators=(",", ":")))
    if changed:
        f = DATA / "odds" / f"{now:%Y-%m-%d}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        new = not f.exists()
        with f.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=ODDS_COLS)
            if new:
                w.writeheader()
            w.writerows(changed)
    _update_matchups(keep, now)
    return dict(matchups=len(keep), prices=len(rows), changed=len(changed), rows=rows)


def _update_matchups(keep: dict, now: dt.datetime):
    p = DATA / "matchups.csv"
    old = pd.read_csv(p, dtype={"matchup_id": int}) if p.exists() else pd.DataFrame(columns=MATCHUP_COLS)
    new = pd.DataFrame(list(keep.values()))
    if new.empty:
        return
    new["first_seen"] = now.isoformat()
    new["last_seen"] = now.isoformat()
    if not old.empty:
        first = old.set_index("matchup_id").first_seen
        new["first_seen"] = new.matchup_id.map(first).fillna(new.first_seen)
    d = pd.concat([old[~old.matchup_id.isin(new.matchup_id)], new], ignore_index=True)
    d.sort_values(["start", "matchup_id"]).to_csv(p, index=False)


def load_odds(days: int | None = None) -> pd.DataFrame:
    files = sorted((DATA / "odds").glob("*.csv"))
    if days:
        files = files[-days:]
    if not files:
        return pd.DataFrame(columns=ODDS_COLS)
    d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    d["ts"] = pd.to_datetime(d.ts, utc=True)
    d["start"] = pd.to_datetime(d.start, utc=True)
    return d
