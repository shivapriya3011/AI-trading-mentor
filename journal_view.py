import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from journal import get_trades

load_dotenv()
client = OpenAI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="Trade Journal",
    page_icon="📖",
    layout="centered"
)

st.title("📖 Trade Journal")

trades = get_trades()

if not trades:
    st.info("No trades saved yet.")

else:
    st.write(f"**Total Trades: {len(trades)}**")

    # ---------------- PATTERN ANALYSIS ----------------

    if len(trades) >= 2:

        st.markdown("---")
        st.subheader("🧠 AI Trading Pattern Analysis")

        if st.button("🔍 Analyse My Trading Patterns"):

            with st.spinner("AI is analysing your trading history..."):

                try:

                    trade_history = ""

                    for i, trade in enumerate(trades, start=1):

                        trade_history += f"""
TRADE {i}

Direction:
{trade['direction']}

Entry:
{trade['entry']}

Stop Loss:
{trade['stop_loss']}

Take Profit:
{trade['take_profit']}

Timeframe:
{trade['timeframe']}

Reason:
{trade['reason']}

AI Review:
{trade['ai_review']}

--------------------------------
"""

                    prompt = f"""
You are an AI Trading Mentor.

Analyse the trader's saved XAUUSD trade journal.

Analyse ONLY the information available in the saved trades
and their AI reviews.

Do NOT give generic trading advice.

TRADING HISTORY:

{trade_history}

Return exactly:

TRADING PATTERN ANALYSIS

REPEATED MISTAKES:
- Mention repeated mistakes only if they appear in multiple trades.
- If no clear repeated mistake, say:
  "No clear repeated mistake yet."

REPEATED GOOD DECISIONS:
- Mention decisions repeatedly consistent with strategy.

ENTRY PATTERNS:
- Recurring entry behaviours.

RISK MANAGEMENT PATTERNS:
- Recurring risk-management behaviours.

STRATEGY ADHERENCE:
- Whether consistently following own strategy.
- No score unless supported.

MAIN PATTERN:
- Most important repeated pattern.

NEXT TRADE FOCUS:
- 1 to 3 specific things.

IMPORTANT:
- No invented information.
- No missing assumptions.
- No profit guarantees.
- No future predictions.
- No generic strategy replacement.
"""

                    response = client.responses.create(
                        model="gpt-6-luna",
                        input=prompt
                    )

                    st.session_state["pattern_analysis"] = response.output_text

                except Exception as e:
                    st.error(f"Pattern analysis failed: {str(e)}")

    # ---------------- PATTERN REPORT ----------------

    if "pattern_analysis" in st.session_state:

        st.markdown("---")
        st.subheader("📊 Trading Pattern Report")

        st.write(
            st.session_state["pattern_analysis"]
        )

    # ---------------- TRADE HISTORY ----------------

    st.markdown("---")
    st.subheader("📚 Trade History")

    # Latest trade first
    latest_trades = list(reversed(trades))

    for i, trade in enumerate(latest_trades, start=1):

        st.markdown("---")

        # ---------------- TRADE HEADER ----------------

        direction = trade.get("direction", "Unknown")
        timeframe = trade.get("timeframe", "Unknown")

        st.subheader(
            f"Trade {i} — {direction} — {timeframe}"
        )

        st.write(f"**Entry:** {trade.get('entry', 'N/A')}")
        st.write(f"**Stop Loss:** {trade.get('stop_loss', 'N/A')}")
        st.write(f"**Take Profit:** {trade.get('take_profit', 'N/A')}")

        # ---------------- SAVED TIME ----------------

        st.caption(
            f"Saved: {trade.get('saved_at', 'Unknown')}"
        )

        # ---------------- STRATEGY CONTEXT ----------------

        st.markdown("### Strategy Context")

        st.write(
            f"**Trading Session:** "
            f"{trade.get('trading_session', 'Not recorded')}"
        )

        st.write(
            f"**Entry Model:** "
            f"{trade.get('entry_model', 'Not recorded')}"
        )

        st.write(
            f"**M30 Trend:** "
            f"{trade.get('m30_trend', 'Not recorded')}"
        )

        st.write(
            f"**H1 Trend:** "
            f"{trade.get('h1_trend', 'Not recorded')}"
        )

        st.write(
            f"**Current Session Trend:** "
            f"{trade.get('current_session_trend', 'Not recorded')}"
        )

        st.write(
            f"**H1 / H4 Zone Nearby:** "
            f"{trade.get('h1_h4_zone', 'Not recorded')}"
        )

        st.write(
            f"**Entry Confirmation:** "
            f"{trade.get('entry_confirmation', 'Not recorded')}"
        )

        # ---------------- SCREENSHOT ----------------

        st.markdown("### 📷 Trade Screenshot")

        screenshot_path = trade.get("screenshot")

        if screenshot_path:

            # Handle both absolute and relative paths
            if os.path.isabs(screenshot_path):
                final_screenshot_path = screenshot_path
            else:
                final_screenshot_path = os.path.join(
                    BASE_DIR,
                    screenshot_path
                )

            final_screenshot_path = os.path.abspath(
                final_screenshot_path
            )

            if os.path.isfile(final_screenshot_path):

                st.image(
                    final_screenshot_path,
                    caption="Trade Screenshot",
                    use_container_width=True
                )

            else:

                st.warning(
                    f"Screenshot file not found:\n"
                    f"{final_screenshot_path}"
                )

        else:

            # Old trades without screenshot path
            # Match old records in chronological order
            old_reference_map = {
                1: "reference/trade1.jpg",
                2: "reference/trade2.jpg",
                3: "reference/trade3.jpg"
            }

            # Find original position of this trade
            try:
                original_index = trades.index(trade) + 1
            except ValueError:
                original_index = None

            reference_image = old_reference_map.get(
                original_index
            )

            if reference_image:

                reference_path = os.path.join(
                    BASE_DIR,
                    reference_image
                )

                if os.path.isfile(reference_path):

                    st.image(
                        reference_path,
                        caption="Trade Screenshot",
                        use_container_width=True
                    )

                else:

                    st.info(
                        "No screenshot saved for this trade."
                    )

            else:

                st.info(
                    "No screenshot saved for this trade."
                )

        # ---------------- TRADE REASON ----------------

        st.markdown("### Trade Reason")

        st.write(
            trade.get("reason", "Not recorded")
        )

        # ---------------- AI REVIEW ----------------

        st.markdown("### 🤖 AI Trade Review")

        st.write(
            trade.get(
                "ai_review",
                "No AI review available."
            )
        )