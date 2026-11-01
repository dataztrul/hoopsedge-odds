"""Map Pinnacle team names to results-source (BetExplorer) names per league.

Automatic fuzzy matching against teams seen in the league's results; manual overrides in
config/team_aliases.json win. Unresolved names are listed in reports/unmatched.md.
"""
from __future__ import annotations

import json
import re

from rapidfuzz import fuzz, process

from .util import CONFIG, norm_name

ALIAS = CONFIG / "team_aliases.json"
NOISE = {"basket", "basketball", "bc", "kk", "bk", "kosarkaski", "klub", "club", "cb", "sad", "ba", "bb", "jda",
         "sluc", "asvel", "ldlc", "women", "w", "fc", "sk", "cs", "ac", "as", "pallacanestro", "basquet", "basquetbol",
         "team", "the", "de", "di", "del", "la", "le", "les", "ss", "sp", "ok", "kb", "ks", "mks", "bk"}


def _core(s: str) -> str:
    toks = [t for t in norm_name(s).split() if t not in NOISE and not re.fullmatch(r"\d+", t)]
    return " ".join(toks) or norm_name(s)


def load_aliases() -> dict:
    return json.loads(ALIAS.read_text()) if ALIAS.exists() else {}


def match(league_key: str, pin_name: str, candidates: list[str], aliases: dict | None = None) -> tuple[str | None, float]:
    aliases = aliases if aliases is not None else load_aliases()
    manual = aliases.get(league_key, {}).get(pin_name)
    if manual:
        return manual, 100.0
    if not candidates:
        return None, 0.0
    if pin_name in candidates:
        return pin_name, 100.0
    cores = {c: _core(c) for c in candidates}
    q = _core(pin_name)
    best = process.extract(q, cores, scorer=fuzz.token_set_ratio, limit=3)
    if not best:
        return None, 0.0
    (_, s1, c1) = best[0]
    s2 = best[1][1] if len(best) > 1 else 0
    # require a clear winner; partial_ratio helps "Dijon" vs "JDA Dijon Basket"
    pr = fuzz.partial_ratio(q, cores[c1])
    score = max(s1, pr)
    if score >= 85 and s1 - s2 >= 8:
        return c1, float(score)
    return None, float(score)
