import streamlit as st
from journal import get_trades

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Trading Dashboard")
st.caption("Summary of your saved trading journal")

trades = get_trades()

if not trades:
    st.info("No trades available in the journal.")
    st.stop()

# -----------------------------
# Basic Statistics
# -----------------------------

total_trades = len(trades)

sell_trades = sum(
    1 for trade in trades
    if trade.get("direction", "").lower() == "sell"
)

buy_trades = sum(
    1 for trade in trades
    if trade.get("direction", "").lower() == "buy"
)

partial_matches = sum(
    1 for trade in trades
    if "PARTIAL" in trade.get("ai_review", "").upper()
)

# -----------------------------
# Top Metrics
# -----------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Trades", total_trades)

with col2:
    st.metric("Sell Trades", sell_trades)

with col3:
    st.metric("Buy Trades", buy_trades)

with col4:
    st.metric("Partial Strategy Match", partial_matches)

st.divider()

# -----------------------------
# Trade Overview
# -----------------------------

st.subheader("📋 Trade Overview")

for index, trade in enumerate(trades, start=1):

    direction = trade.get("direction", "Unknown")
    entry = trade.get("entry", 0)
    sl = trade.get("stop_loss", 0)
    tp = trade.get("take_profit", 0)
    timeframe = trade.get("timeframe", "Unknown")

    if direction.lower() == "sell":
        risk = abs(sl - entry)
        reward = abs(entry - tp)
    else:
        risk = abs(entry - sl)
        reward = abs(tp - entry)

    rr = reward / risk if risk > 0 else 0

    with st.expander(f"Trade {index} — {direction} — {timeframe}"):

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.write("**Entry**")
            st.write(entry)

        with col2:
            st.write("**Stop Loss**")
            st.write(sl)

        with col3:
            st.write("**Take Profit**")
            st.write(tp)

        with col4:
            st.write("**Planned R:R**")
            st.write(f"1:{rr:.2f}")

st.divider()

# -----------------------------
# Pattern Analysis
# -----------------------------

st.subheader("🔎 Trading Patterns")

dcr_count = 0
session_issue_count = 0
rr_below_one_count = 0

for trade in trades:

    reason = trade.get("reason", "").lower()
    review = trade.get("ai_review", "").lower()

    if "dcr" in reason:
        dcr_count += 1

    if "outside the strategy" in review:
        session_issue_count += 1

    entry = trade.get("entry", 0)
    sl = trade.get("stop_loss", 0)
    tp = trade.get("take_profit", 0)
    direction = trade.get("direction", "").lower()

    if direction == "sell":
        risk = abs(sl - entry)
        reward = abs(entry - tp)
    else:
        risk = abs(entry - sl)
        reward = abs(tp - entry)

    if risk > 0:
        rr = reward / risk

        if rr < 1:
            rr_below_one_count += 1

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "DCR-related Trades",
        dcr_count
    )

with col2:
    st.metric(
        "R:R Below 1:1",
        rr_below_one_count
    )

with col3:
    st.metric(
        "Session Issues",
        session_issue_count
    )

st.divider()

# -----------------------------
# Main Lessons
# -----------------------------

st.subheader("🎯 Main Trading Focus")

st.markdown("""
- Verify higher-timeframe context before entry.
- Confirm the exact entry condition instead of relying only on a setup label.
- Check Entry, SL and TP distances before execution.
- Record the relevant candle levels and break/re-break conditions.
- Follow the defined trading session.
""")

st.divider()

st.subheader("📌 Current Journal Status")

st.success(
    f"Your journal currently contains {total_trades} saved trades."
)