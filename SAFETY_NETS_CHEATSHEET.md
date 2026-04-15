# 🛡️ Safety Nets Quick Reference

## 🚨 What Each Protection Does

| Protection | Triggers At | Action | Can Disable? |
|------------|-------------|--------|--------------|
| **Daily Loss Limit** | Net loss ≤ -$100 | Blocks ALL new entries, activates Recovery | ❌ No (critical) |
| **Spread Check** | Spread > 30 pips (XAU) / 50 (BTC) | Blocks entry only | ✅ Yes per-symbol |
| **Weekend Close** | Friday 22:00+ | Closes all positions, blocks entries | ✅ Yes (`ENABLE_WEEKEND_CLOSE`) |
| **Portfolio Cap** | Total loss > $200 | Blocks new entries | ❌ No (critical) |
| **MT5 Disconnect** | Connection lost | Alerts + auto-reconnect every 5 min | ❌ No (critical) |
| **Hedge Safety** | Hedge already exists | Blocks duplicate hedge | ❌ No (critical) |

---

## 📊 Current Settings

```
MAX_DAILY_LOSS_USD     = $100
MAX_PORTFOLIO_RISK_USD = $200
MAX_SPREAD_PIPS        = 30 (XAU) / 50 (BTC)
Weekend Close          = Friday 22:00 (ON)
```

---

## 🔔 Notifications You'll Receive

### Daily Loss Hit
```
🚨 DAILY LOSS LIMIT HIT ($-XXX.XX) — Activating Recovery Mode
```
**Action:** EA stops taking new trades. Review positions manually.

---

### Spread Too Wide
```
🚫 [XAUUSDc] Spread 45.0 pips > 30 — blocked
```
**Action:** Normal. Waits for spread to normalize.

---

### Weekend Close
```
🔒 [XAUUSDc] Closed 0.05 SELL @ 2678.45 (Weekend Close)
✅ Closed 3 positions (Weekend Close)
```
**Action:** Normal. Positions reopen Monday via regular signals.

---

### MT5 Disconnected
```
🔴 MT5 Disconnected — Attempting reconnect...
✅ MT5 Reconnected successfully
```
**OR if fails:**
```
🚨 MT5 Reconnect FAILED — Check broker connection!
```
**Action:** Check MT5 terminal and broker status.

---

### Portfolio Risk Exceeded
```
🚫 Portfolio exposure $245.30 > $200.00 — blocked
```
**Action:** Wait for existing positions to close or improve.

---

## 🛠️ Manual Overrides

### Check Current Daily PnL
Look at your Telegram/Line reports, or check database:
```sql
SELECT SUM(profit) FROM trades 
WHERE date(timestamp) = date('now') AND result != 'PENDING';
```

### Force Disable Recovery Mode
If stuck and you want to resume trading:
```python
# Run in Python console or create test script
import database
database.set_bot_setting("global_recovery_active", False)
```

### Adjust Limits (Edit config.py)
```python
MAX_DAILY_LOSS_USD     = 150.0  # Increase from $100 to $150
MAX_PORTFOLIO_RISK_USD = 300.0  # Increase from $200 to $300
MAX_SPREAD_PIPS        = 40     # Increase from 30 to 40 pips
ENABLE_WEEKEND_CLOSE   = False  # Disable weekend auto-close
```

⚠️ **Warning:** Only increase limits if you understand the risk!

---

## 🧪 How to Test Each Safety Net

### Test Daily Loss Limit
1. Open losing positions manually in MT5
2. Close them at loss until total < -$100
3. Verify EA stops opening new trades
4. Check for "DAILY LOSS LIMIT HIT" message

### Test Spread Protection
1. Wait for high-impact news (NFP, CPI, FOMC)
2. Watch for "Spread X pips > 30 — blocked" messages
3. Verify no entries during spike

### Test Weekend Close
1. Leave EA running Friday night
2. Check logs around 22:00
3. Verify "Weekend_Close" messages
4. Confirm no positions open Saturday

---

## 📞 Emergency Contacts

If something goes wrong:

1. **Stop EA:** Press `Ctrl+C` in terminal
2. **Close all manually:** Right-click positions in MT5 → Close
3. **Check logs:** Look in `C:\Users\HeyBo\OneDrive\Desktop\Forex\` for error messages
4. **Review database:** Open `trades.db` with DB Browser for SQLite

---

## 🎯 Key Metrics to Watch

| Metric | Safe Zone | Warning | Danger |
|--------|-----------|---------|--------|
| Daily PnL | > -$50 | -$50 to -$80 | < -$80 |
| Portfolio Exposure | < $100 | $100-$150 | > $150 |
| Spread (XAU) | < 20 pips | 20-25 pips | > 25 pips |
| Open Positions | 1-2 | 3 | 4+ |

---

*Keep this handy when running the EA!*
