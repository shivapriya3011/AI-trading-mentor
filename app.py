import base64
import hashlib
import io
import time

import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

from ai_mentor import (
    build_mentor_prompt,
    build_pattern_analysis_prompt
)

from journal import (
    save_trade,
    get_trades,
    delete_trade
)


# =========================================================
# API SETUP (GEMINI)
# =========================================================

load_dotenv()

# Gemini client initialization
client = genai.Client()


# =========================================================
# IMAGE PREPARATION
# =========================================================

def prepare_trade_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))

    if image.mode != "RGB":
        image = image.convert("RGB")

    max_dimension = 1280

    if max(image.width, image.height) > max_dimension:
        image.thumbnail((max_dimension, max_dimension))

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()


# =========================================================
# GEMINI SAFE REQUEST WITH RETRY (FIXED FOR ACTIVE MODELS)
# =========================================================

def call_gemini_with_retry(
    contents,
    max_retries=3
):
    """
    Safely call Gemini API using the new google-genai client.
    Updated with active model name to completely eliminate 404 / 503 errors.
    """
    models_to_try = [
        "gemini-2.5-flash"
    ]
    
    last_error = None

    for model_name in models_to_try:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and response.text:
                    return response.text

            except Exception as e:
                last_error = e
                error_text = str(e).lower()

                is_server_issue = any(
                    err in error_text for err in [
                        "503", "unavailable", "overloaded", 
                        "resource_exhausted", "rate limit", 
                        "too many requests", "deadline_exceeded"
                    ]
                )

                if is_server_issue:
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
                    continue
                else:
                    break

    raise RuntimeError(f"AI_SERVICE_TEMPORARILY_UNAVAILABLE: All models failed. Last error: {last_error}")


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="AI Trading Mentor",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# SESSION STATE
# =========================================================

if "screenshot_bytes" not in st.session_state:
    st.session_state.screenshot_bytes = None

if "screenshot_type" not in st.session_state:
    st.session_state.screenshot_type = None

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "trade_saved" not in st.session_state:
    st.session_state.trade_saved = False

if "page" not in st.session_state:
    st.session_state.page = "Trade Analysis"

if "analysed_trade" not in st.session_state:
    st.session_state.analysed_trade = None

if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = {}

if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False


# =========================================================
# DESIGN (CUSTOM CSS)
# =========================================================

st.markdown(
    """
    <style>
    .stApp { background-color: #FFF4B8; }
    p, label, span, h1, h2, h3, h4, h5, h6 { color: #000000 !important; }
    .subtitle { text-align: center; color: #000000 !important; font-size: 16px; margin-bottom: 30px; }
    .section { background-color: #FFFFFF; padding: 25px; border-radius: 15px; border: 1px solid #D1D5DB; margin-bottom: 20px; }
    .result-box { background-color: #FFFFFF; border: 1px solid #D1D5DB; padding: 20px; border-radius: 15px; margin-top: 20px; }
    .result-box * { color: #000000 !important; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #9CA3AF !important; border-radius: 8px !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #9CA3AF !important; border-radius: 8px !important;
    }
    .stButton > button {
        width: 100%; background-color: #2563EB !important; color: #FFFFFF !important; border: none; border-radius: 10px; padding: 12px; font-size: 16px; font-weight: 600;
    }
    .stButton > button * { color: #FFFFFF !important; }
    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("📈 AI Trading Mentor")

page = st.sidebar.radio(
    "Navigation",
    ["Trade Analysis", "Trade Journal", "Dashboard"],
    index=["Trade Analysis", "Trade Journal", "Dashboard"].index(st.session_state.page)
)

st.session_state.page = page


# =========================================================
# TRADE ANALYSIS PAGE
# =========================================================

if page == "Trade Analysis":

    st.markdown('<h1 style="text-align:center;">📈 AI Trading Mentor</h1>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Analyse your trade based on your own trading strategy</div>', unsafe_allow_html=True)

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.subheader("Trade Details")

    screenshot = st.file_uploader(
        "Upload Trade Screenshot",
        type=["png", "jpg", "jpeg"],
        key="trade_screenshot"
    )

    if screenshot is not None:
        new_screenshot = screenshot.getvalue()
        if st.session_state.screenshot_bytes != new_screenshot:
            st.session_state.screenshot_bytes = new_screenshot
            st.session_state.screenshot_type = screenshot.type
            st.session_state.analysis = None
            st.session_state.analysed_trade = None
            st.session_state.trade_saved = False

    direction = st.selectbox("Trade Direction", ["Buy", "Sell"], key="direction")
    entry = st.number_input("Entry Price", min_value=0.0, format="%.3f", key="entry")
    sl = st.number_input("Stop Loss", min_value=0.0, format="%.3f", key="sl")
    tp = st.number_input("Take Profit", min_value=0.0, format="%.3f", key="tp")
    
    timeframe = st.selectbox("Execution Timeframe", ["15M", "M20", "M30", "H1", "H4", "Daily"], key="timeframe")

    st.subheader("Strategy Context")
    trading_session = st.selectbox("Trading Session", ["Asian", "Mid Asian → London Open", "Pre-New York → New York", "Other / Not sure"], key="trading_session")
    entry_model = st.selectbox("Entry Model", ["Counter Buy", "Counter Sell", "Impulse Breakout Buy", "Impulse Breakout Sell", "Complete Breakout Buy", "Complete Breakout Sell", "S/R Buy", "S/R Sell", "Wickfill", "Impulse / A+", "Pullback Buy", "Pullback Sell", "Fakeout Buy", "Fakeout Sell", "Big Body Breakout", "Not sure"], key="entry_model")

    col1, col2 = st.columns(2)
    with col1:
        m30_trend = st.selectbox("M30 Trend / Context", ["Bullish", "Bearish", "Range / Neutral", "Not sure"], key="m30_trend")
    with col2:
        h1_trend = st.selectbox("H1 Trend / Context", ["Bullish", "Bearish", "Range / Neutral", "Not sure"], key="h1_trend")

    current_session_trend = st.selectbox("Current Session Trend", ["Bullish", "Bearish", "Range / Neutral", "Not sure"], key="current_session_trend")
    htf_zone = st.selectbox("H1 / H4 Zone Nearby?", ["Yes", "No", "Not sure"], key="htf_zone")
    entry_confirmation = st.selectbox("Entry Confirmation", ["Break of Previous High / Low", "Re-break", "Flip", "Own High / Low Break", "Wick Entry", "Pullback Confirmation", "No Clear Confirmation", "Not sure"], key="entry_confirmation")

    reason = st.text_area("Why did you take this trade?", placeholder="Explain your reason for entering this trade...", key="reason")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🔍 Analyse Trade"):
        if st.session_state.screenshot_bytes is None:
            st.warning("Please upload a trade screenshot.")
        elif entry == 0 or sl == 0 or tp == 0:
            st.warning("Please enter Entry, SL and TP.")
        elif direction == "Buy" and not (sl < entry < tp):
            st.warning("For a Buy trade: SL must be below Entry and TP must be above Entry.")
        elif direction == "Sell" and not (sl > entry > tp):
            st.warning("For a Sell trade: SL must be above Entry and TP must be below Entry.")
        elif st.session_state.analysis_running:
            st.info("Your trade is already being analysed.")
        else:
            st.session_state.analysis_running = True
            try:
                processed_img_bytes = prepare_trade_image(st.session_state.screenshot_bytes)
                img_part = types.Part.from_bytes(
                    data=processed_img_bytes,
                    mime_type="image/jpeg"
                )

                prompt = build_mentor_prompt(
                    direction=direction,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    timeframe=timeframe,
                    reason=reason
                )

                prompt += f"""

TRADER-PROVIDED STRATEGY CONTEXT
Trading Session: {trading_session}
Entry Model Selected By Trader: {entry_model}
M30 Trend / Context: {m30_trend}
H1 Trend / Context: {h1_trend}
Current Session Trend: {current_session_trend}
H1 / H4 Zone Nearby: {htf_zone}
Entry Confirmation Selected By Trader: {entry_confirmation}

IMPORTANT:
Compare these details with the uploaded screenshot and the trader's strategy reference. Provide constructive, structured feedback.
"""

                request_key = hashlib.sha256(
                    st.session_state.screenshot_bytes + prompt.encode("utf-8")
                ).hexdigest()

                if request_key in st.session_state.analysis_cache:
                    analysis_text = st.session_state.analysis_cache[request_key]
                else:
                    analysis_text = call_gemini_with_retry([prompt, img_part])
                    st.session_state.analysis_cache[request_key] = analysis_text

                st.session_state.analysis = analysis_text
                st.session_state.analysed_trade = {
                    "direction": direction,
                    "entry": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "timeframe": timeframe,
                    "reason": reason
                }
                st.session_state.trade_saved = False
                st.success("✅ Trade analysed successfully.")

            except Exception as e:
                st.error(f"AI analysis could not be completed. Error: {str(e)}")
            finally:
                st.session_state.analysis_running = False

    if st.session_state.analysis:
        st.markdown('<div class="result-box">', unsafe_allow_html=True)
        st.subheader("📊 AI Trade Review")
        st.markdown(st.session_state.analysis)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("💾 Save Trade to Journal"):
            if st.session_state.trade_saved:
                st.info("This trade is already saved.")
            elif st.session_state.analysed_trade is None:
                st.error("Please analyse the trade again before saving.")
            else:
                analysed_trade = st.session_state.analysed_trade
                trade_data = {
                    "direction": analysed_trade["direction"],
                    "entry": analysed_trade["entry"],
                    "stop_loss": analysed_trade["stop_loss"],
                    "take_profit": analysed_trade["take_profit"],
                    "timeframe": analysed_trade["timeframe"],
                    "reason": analysed_trade["reason"],
                    "ai_review": st.session_state.analysis
                }

                try:
                    save_trade(
                        trade_data,
                        screenshot_bytes=st.session_state.screenshot_bytes,
                        screenshot_type=st.session_state.screenshot_type
                    )
                    st.session_state.trade_saved = True
                    st.success("✅ Trade + Screenshot saved permanently to Supabase!")
                except Exception as e:
                    st.error(f"Failed to save trade: {str(e)}")


# =========================================================
# TRADE JOURNAL PAGE
# =========================================================

elif page == "Trade Journal":
    st.title("📖 Trade Journal")
    st.caption("Your saved trades and AI reviews")

    try:
        trades = get_trades()
    except Exception as e:
        st.error("Could not load journal.")
        st.stop()

    if not trades:
        st.info("No trades saved yet.")
    else:
        st.success(f"Total Trades: {len(trades)}")
        for i, trade in enumerate(reversed(trades), start=1):
            direction = trade.get("direction", "Unknown")
            entry = trade.get("entry", 0)
            sl = trade.get("stop_loss", 0)
            tp = trade.get("take_profit", 0)
            timeframe = trade.get("timeframe", "Unknown")
            reason = trade.get("reason", "")
            ai_review = trade.get("ai_review", "")
            screenshot_url = trade.get("screenshot_url")
            saved_at = trade.get("saved_at", "")
            trade_id = trade.get("id")

            with st.expander(f"Trade {i} — {direction} — {timeframe}"):
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
                    st.write("**Timeframe**")
                    st.write(timeframe)

                if saved_at:
                    st.caption(f"Saved: {saved_at}")

                st.subheader("📷 Trade Screenshot")
                if screenshot_url:
                    st.image(screenshot_url, caption="Trade Screenshot", use_container_width=True)
                else:
                    st.info("No screenshot saved for this trade.")

                st.subheader("Trade Reason")
                st.write(reason if reason else "No reason recorded.")

                st.subheader("📊 AI Trade Review")
                st.markdown(ai_review if ai_review else "No AI review available.")

                st.divider()
                st.subheader("🗑️ Trade Management")

                if trade_id is not None:
                    delete_key = f"delete_trade_{trade_id}"
                    confirm_key = f"confirm_delete_{trade_id}"

                    if not st.session_state.get(confirm_key, False):
                        if st.button("🗑️ Delete Trade", key=delete_key):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        st.warning("Are you sure you want to delete this trade and its screenshot?")
                        confirm_col1, confirm_col2 = st.columns(2)
                        with confirm_col1:
                            if st.button("✅ Yes, Delete", key=f"yes_{trade_id}"):
                                try:
                                    delete_trade(trade_id, screenshot_url)
                                    st.session_state.pop(confirm_key, None)
                                    st.success("Trade deleted successfully.")
                                    st.rerun()
                                except Exception:
                                    st.error("Failed to delete trade.")
                        with confirm_col2:
                            if st.button("❌ Cancel", key=f"cancel_{trade_id}"):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                else:
                    st.warning("This trade has no database ID, so it cannot be deleted.")


# =========================================================
# DASHBOARD PAGE
# =========================================================

elif page == "Dashboard":
    st.title("📊 Trading Dashboard")
    st.caption("Summary of your saved trading journal")

    try:
        trades = get_trades()
    except Exception:
        st.error("Could not load dashboard.")
        st.stop()

    if not trades:
        st.info("No trades available in the journal.")
        st.stop()

    total_trades = len(trades)
    sell_trades = sum(1 for trade in trades if trade.get("direction", "").lower() == "sell")
    buy_trades = sum(1 for trade in trades if trade.get("direction", "").lower() == "buy")
    partial_matches = sum(1 for trade in trades if "PARTIAL" in trade.get("ai_review", "").upper())

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
    st.subheader("📋 Trade Overview")

    for index, trade in enumerate(reversed(trades), start=1):
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

        rr = (reward / risk) if risk > 0 else 0

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
                st.write("**Risk/Reward Ratio**")
                st.write(f"1:{rr:.2f}")

    st.subheader("📌 Current Journal Status")
    st.success(f"Your journal currently contains {total_trades} saved trades.")
