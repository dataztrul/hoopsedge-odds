# hoopsedge-odds

Logg över pre-game-odds för europeisk basket (herr och dam), från två offentliga källor:

- **Pinnacle** (gäst-API): moneyline, huvudspread och huvudtotal.
- **Kambi** (Unibet SE): samma marknader, där varje match kopplas till Pinnacles matchup-id.

En ögonblicksbild tas var 5:e minut när en match börjar inom 75 minuter, annars var 10–15:e minut.
Bara ändrade priser sparas.

| Fil | Innehåll |
|---|---|
| `data/odds/YYYY-MM-DD.csv` | Pinnacle: ts, matchup_id, liga, marknad, linje, decimalodds, insatsgräns |
| `data/kambi/YYYY-MM-DD.csv` | Kambi: ts, event_id, grupp, lag, marknad, linje, decimalodds, pin_matchup_id |
| `data/matchups.csv` | Pinnacle-matcher: liga, start, lag, första och senaste gång de sågs |

Inofficiella källor som kan ändras utan förvarning.
