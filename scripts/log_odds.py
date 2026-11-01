"""One snapshot: Pinnacle (moneyline, main spread, main total) and Kambi prices; only changed prices are written."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hoopsedge import kambi, pinnacle  # noqa: E402

now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
p = pinnacle.snapshot(now)
k = kambi.snapshot(now)
print(f"{now:%Y-%m-%d %H:%M} pinnacle matchups={p['matchups']} prices={p['prices']} changed={p['changed']} "
      f"kambi={ {x: v for x, v in k.items() if x != 'rows'} }")
