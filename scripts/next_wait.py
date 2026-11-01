"""Seconds to sleep before the next snapshot: 5 min when a logged game starts within 75 min
(so the closing price is at most ~5 min old), 10 min when one starts within 6 h, otherwise 15 min."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

p = Path(__file__).resolve().parents[1] / "data" / "matchups.csv"
now = pd.Timestamp(dt.datetime.now(dt.timezone.utc))
wait = 900
try:
    m = pd.read_csv(p, usecols=["start"])
    st = pd.to_datetime(m.start, utc=True)
    ahead = (st - now).dt.total_seconds() / 60
    ahead = ahead[ahead > -5]
    if len(ahead) and ahead.min() <= 75:
        wait = 300
    elif len(ahead) and ahead.min() <= 360:
        wait = 600
except Exception:  # noqa: BLE001
    wait = 600
print(wait)
sys.exit(0)
