"""Shared helpers: config, polite HTTP, odds math, paths."""
from __future__ import annotations

import json
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports"
UA = "Mozilla/5.0 (X11; Linux x86_64) hoopsedge-research/0.1"


def leagues() -> list[dict]:
    return json.loads((CONFIG / "leagues.json").read_text())["leagues"]


def league_by_pinnacle() -> dict[str, dict]:
    return {p: lg for lg in leagues() for p in lg["pinnacle"]}


def get(url: str, *, json_out: bool = False, retries: int = 3, pause: float = 0.0, timeout: int = 30):
    """GET with retries and a small pause between calls (be polite to the sources)."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                final = r.geturl()
            # a redirect to another page (e.g. an unknown season -> home page) means "not found"
            if final.split("?")[0].rstrip("/") != url.split("?")[0].rstrip("/"):
                return None
            if pause:
                time.sleep(pause)
            return json.loads(body) if json_out else body.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # network hiccup
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url}: {last}")


def american_to_decimal(a: float) -> float:
    a = float(a)
    return 1 + (a / 100 if a > 0 else 100 / -a)


def novig_two_way(dh: float, da: float) -> float:
    """Home win probability with the margin removed proportionally."""
    ih, ia = 1 / dh, 1 / da
    return ih / (ih + ia)


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    for ch in ".,'()/-":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def season_label(year_start: int, split: bool = True) -> str:
    return f"{year_start}-{year_start + 1}" if split else str(year_start)


def current_season_start(today=None) -> int:
    import datetime as dt
    today = today or dt.date.today()
    return today.year if today.month >= 7 else today.year - 1
