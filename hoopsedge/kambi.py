"""Kambi (Unibet, Svenska Spel's partner books, LeoVegas, ...) pre-game prices for all European basketball.

Kambi is the main soft-book engine on the Swedish market. We log its moneyline, main spread and
main total the same way as Pinnacle (only changed prices), and match every Kambi event to the
Pinnacle matchup it corresponds to, so CLV can be measured *at a price that is actually
available* (Kambi) against the sharp close (Pinnacle).
"""
from __future__ import annotations

import csv
import datetime as dt
import json

import pandas as pd
from rapidfuzz import fuzz

from . import names as N
from .util import DATA, get

OP = "ubse"   # Unibet Sweden; Kambi operators share one price feed with small per-operator differences
BASE = f"https://eu-offering-api.kambicdn.com/offering/v2018/{OP}"
Q = "lang=en_GB&market=SE&useCombined=true"
SKIP = ("ncaab", "ncaaw", "nba", "wnba", "wnba_series_markets", "argentina", "australia", "japan", "philippines",
        "south_korea", "china", "chinese_taipei", "new_zealand", "indonesia")
COLS = ["ts", "event_id", "group", "home", "away", "start", "type", "line", "dec_1", "dec_2", "pin_matchup_id", "match_score"]
TYPES = {"Moneyline - Including Overtime": "moneyline", "Point Spread - Including Overtime": "spread",
         "Total Points - Including Overtime": "total"}


def groups() -> list[str]:
    tree = get(f"{BASE}/group/1000093204.json?{Q}", json_out=True) or {}
    out = []

    def walk(g, path):
        p = path + [g.get("termKey")]
        if g.get("groups"):
            for c in g["groups"]:
                walk(c, p)
        elif g.get("eventCount") and p[1] not in SKIP:
            out.append("/".join(p[1:]))
    if tree:
        walk(tree["group"], [])
    return out


def fetch(now: dt.datetime) -> list[dict]:
    rows = []
    for gpath in groups():
        parts = gpath.split("/") + ["all"] * 3
        d = get(f"{BASE}/listView/basketball/{'/'.join(parts[:3])}/matches.json?{Q}", json_out=True, pause=0.3) or {}
        for e in d.get("events", []):
            ev = e["event"]
            if ev.get("state") != "NOT_STARTED" or "homeName" not in ev:
                continue
            start = pd.Timestamp(ev["start"])
            if start <= now:
                continue
            for b in e.get("betOffers", []):
                t = TYPES.get(b["criterion"].get("englishLabel"))
                tags = b.get("tags", [])
                if not t or ("MAIN" not in tags and "MAIN_LINE" not in tags):
                    continue
                oc = {o.get("type"): o for o in b.get("outcomes", []) if o.get("status") == "OPEN"}
                a, c = ("OT_ONE", "OT_TWO") if t != "total" else ("OT_OVER", "OT_UNDER")
                if a not in oc or c not in oc or not oc[a].get("odds") or not oc[c].get("odds"):
                    continue
                line = oc[a].get("line")
                rows.append(dict(ts=now.isoformat(), event_id=ev["id"], group=gpath, home=ev["homeName"], away=ev["awayName"],
                                 start=start.isoformat(), type=t, line=None if line is None else line / 1000,
                                 dec_1=oc[a]["odds"] / 1000, dec_2=oc[c]["odds"] / 1000))
    return rows


def _pair_score(kh, ka, ph, pa) -> float:
    s = lambda x, y: fuzz.token_set_ratio(N._core(x), N._core(y))  # noqa: E731
    return (s(kh, ph) + s(ka, pa)) / 2


def match_events(rows: list[dict], pin_matchups: pd.DataFrame, memo: dict) -> None:
    """Attach the Pinnacle matchup id: same start (+-3 h) and best combined home/away name match (>= 70)."""
    pm = pin_matchups.copy()
    pm["start"] = pd.to_datetime(pm.start, utc=True)
    for r in rows:
        k = str(r["event_id"])
        if k in memo:
            r["pin_matchup_id"], r["match_score"] = memo[k]
            continue
        st = pd.Timestamp(r["start"])
        cand = pm[(pm.start - st).abs() <= pd.Timedelta(hours=3)]
        best, score = None, 0.0
        for c in cand.itertuples():
            sc = _pair_score(r["home"], r["away"], c.home, c.away)
            if sc > score:
                best, score = int(c.matchup_id), sc
        if best and score >= 70:
            memo[k] = (best, round(score, 1))
        r["pin_matchup_id"], r["match_score"] = memo.get(k, (None, round(score, 1)))


def snapshot(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    try:
        rows = fetch(now)
    except Exception as e:  # noqa: BLE001 - never break the Pinnacle snapshot because of Kambi
        return dict(error=str(e))
    state_p = DATA / "state" / "kambi_last.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    memo = state.pop("_match", {})
    mp = DATA / "matchups.csv"
    if mp.exists():
        match_events(rows, pd.read_csv(mp), memo)
    changed = []
    for r in rows:
        key = f"{r['event_id']}|{r['type']}"
        sig = f"{r['line']}|{r['dec_1']}|{r['dec_2']}|{r.get('pin_matchup_id')}"
        if state.get(key, {}).get("sig") != sig:
            changed.append(r)
            state[key] = {"sig": sig, "start": r["start"]}
    cutoff = (now - dt.timedelta(days=2)).isoformat()
    state = {k: v for k, v in state.items() if v.get("start", "") > cutoff}
    live_ids = {str(r["event_id"]) for r in rows}
    state["_match"] = {k: v for k, v in memo.items() if k in live_ids or any(s.startswith(k + "|") for s in state)}
    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(json.dumps(state, separators=(",", ":")))
    if changed:
        f = DATA / "kambi" / f"{now:%Y-%m-%d}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        new = not f.exists()
        with f.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerows(changed)
    return dict(rows=rows, events=len({r["event_id"] for r in rows}), prices=len(rows), changed=len(changed),
                matched=len({r["event_id"] for r in rows if r.get("pin_matchup_id")}))


def load() -> pd.DataFrame:
    files = sorted((DATA / "kambi").glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=COLS)
    d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    d["ts"] = pd.to_datetime(d.ts, utc=True)
    d["start"] = pd.to_datetime(d.start, utc=True)
    return d
