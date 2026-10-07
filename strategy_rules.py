# strategy_rules.py

STRATEGY_RULES = """
TRADING STRATEGY REFERENCE

MARKET
XAUUSD


TRADING SESSIONS

Asian:
4:30 AM - 7:30 AM

Mid Asian to London Open:
10:30 AM - 2:30 PM

Pre-New York to New York:
4:30 PM - 8:30 PM

Most trades are taken during:
Mid Asian to London Open.


ANALYSIS CRITERIA

Analyse the market from the higher timeframe
to the lower timeframe.

Analysis flow:

4H
↓
H1
↓
M30

The overall market condition must be analysed
before evaluating the trade.

Support and Resistance must be considered.

A trade should not be judged only because price
touches a Support or Resistance area.


TRADING TERMINOLOGY

BOPCH = Break of Previous Candle High
BOPCL = Break of Previous Candle Low

BOOCH = Break of Own Candle High
BOOCL = Break of Own Candle Low

PCH = Previous Candle High
PCL = Previous Candle Low

OCH = Own Candle High
OCL = Own Candle Low

DCR = Double Clean Range
DCR refers to clean double-side moves to the left.


ENTRY MODELS

The strategy reference contains the following
entry models:

1. Counter Buy
2. Counter Sell
3. Impulse Breakout
4. Complete Breakout
5. S/R Buy
6. S/R Sell
7. Wickfill
8. A+/Impulse
9. Pullback
10. Fakeout
11. Big Body Breakout


TRADE ANALYSIS

When analysing a trade, consider:

- Trading session
- Overall market condition
- Higher timeframe context
- H1 context
- M30 context
- Support and Resistance
- DCR where applicable
- Applicable entry model
- Relevant candle levels
- Entry execution
- Stop Loss
- Take Profit
- Risk management


RISK MANAGEMENT

The strategy reference includes:

- 15P profit → BE / P.SL management
- Partial cut when price struggles
- Risk reduction when the previous high/low
  breaks back towards the entry
- Larger risk-cut considerations around
  own high/low breaks

Apply these only when the corresponding
condition is actually present in the trade.

Do not invent a risk-management condition
when the required information is unavailable.


AI REVIEW RULE

The AI must analyse every trade according to
this trader's own strategy.

The AI must identify:

1. What went right
2. What went wrong
3. Better entry idea
4. Better risk-management idea
5. How to execute the next trade better

The AI must not use generic trading rules in place
of the trader's strategy.

If the screenshot or trade information is insufficient,
say:

"Not enough information"

Do not guess or invent missing information.

The AI must not guarantee profit or predict the
future market with certainty.
"""