import base64
import hashlib
import io
import time

import streamlit as st

from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

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
# API SETUP
# =========================================================

load_dotenv()

client = OpenAI()


# =========================================================
# IMAGE PREPARATION
# =========================================================

def prepare_trade_image(image_bytes):

    image = Image.open(
        io.BytesIO(image_bytes)
    )

    if image.mode != "RGB":
        image = image.convert("RGB")

    max_dimension = 1280

    if max(
        image.width,
        image.height
    ) > max_dimension:

        image.thumbnail(
            (
                max_dimension,
                max_dimension
            )
        )

    output = io.BytesIO()

    image.save(
        output,
        format="JPEG",
        quality=75,
        optimize=True
    )

    return output.getvalue()


# =========================================================
# OPENAI SAFE REQUEST
# =========================================================

def call_openai_with_retry(
    input_data,
    max_output_tokens,
    max_retries=6
):
    """
    Safely call OpenAI.

    Handles temporary rate limits using
    exponential backoff.

    The function does not immediately expose
    429 errors to the user.
    """

    last_error = None

    for attempt in range(
        max_retries + 1
    ):

        try:

            response = client.responses.create(
                model="gpt-6-luna",
                input=input_data,
                max_output_tokens=max_output_tokens
            )

            return response

        except Exception as e:

            last_error = e

            error_text = str(e).lower()

            is_rate_limit = (
                "429" in error_text
                or "rate_limit" in error_text
                or "rate limit" in error_text
                or "too many requests" in error_text
            )

            if not is_rate_limit:
                raise

            if attempt >= max_retries:
                break

            # Increasing wait time:
            # 2, 4, 8, 16, 32, 64 seconds
            wait_time = min(
                2 ** attempt,
                60
            )

            time.sleep(
                wait_time
            )

    # Do not expose raw OpenAI error.
    raise RuntimeError(
        "AI_SERVICE_TEMPORARILY_UNAVAILABLE"
    )


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

if "pattern_analysis" not in st.session_state:
    st.session_state.pattern_analysis = None

if "page" not in st.session_state:
    st.session_state.page = "Trade Analysis"

if "analysed_trade" not in st.session_state:
    st.session_state.analysed_trade = None

# Cache completed trade analyses
if "analysis_cache" not in st.session_state:
    st.session_state.analysis_cache = {}

# Prevent duplicate analysis requests
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False

# Cache pattern analysis
if "pattern_cache" not in st.session_state:
    st.session_state.pattern_cache = {}


# =========================================================
# DESIGN
# =========================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #FFF4B8;
    }

    p, label, span {
        color: #000000 !important;
    }

    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }

    .subtitle {
        text-align: center;
        color: #000000 !important;
        font-size: 16px;
        margin-bottom: 30px;
    }

    .section {
        background-color: #FFFFFF;
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #D1D5DB;
        margin-bottom: 20px;
    }

    .result-box {
        background-color: #FFFFFF;
        border: 1px solid #D1D5DB;
        padding: 20px;
        border-radius: 15px;
        margin-top: 20px;
    }

    .result-box * {
        color: #000000 !important;
    }

    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #9CA3AF !important;
        border-radius: 8px !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: #555555 !important;
        opacity: 1 !important;
    }

    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #9CA3AF !important;
        border-radius: 8px !important;
    }

    .stSelectbox div[data-baseweb="select"] span {
        color: #000000 !important;
    }

    .stSelectbox div[data-baseweb="select"] svg {
        fill: #000000 !important;
        color: #000000 !important;
    }

    div[data-baseweb="popover"] {
        background-color: #FFFFFF !important;
    }

    ul[role="listbox"] {
        background-color: #FFFFFF !important;
    }

    li[role="option"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }

    li[role="option"] * {
        color: #000000 !important;
    }

    li[role="option"]:hover {
        background-color: #E5E7EB !important;
    }

    section[data-testid="stFileUploaderDropzone"] {
        background-color: #FFFFFF !important;
        border: 1px dashed #9CA3AF !important;
    }

    section[data-testid="stFileUploaderDropzone"] * {
        color: #000000 !important;
    }

    .stButton > button {
        width: 100%;
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border: none;
        border-radius: 10px;
        padding: 12px;
        font-size: 16px;
        font-weight: 600;
    }

    .stButton > button * {
        color: #FFFFFF !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "📈 AI Trading Mentor"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Trade Analysis",
        "Trade Journal",
        "Dashboard"
    ],
    index=[
        "Trade Analysis",
        "Trade Journal",
        "Dashboard"
    ].index(
        st.session_state.page
    )
)

st.session_state.page = page


# =========================================================
# TRADE ANALYSIS
# =========================================================

if page == "Trade Analysis":

    st.markdown(
        '<h1 style="text-align:center;">'
        '📈 AI Trading Mentor'
        '</h1>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Analyse your trade based on your own trading strategy'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section">',
        unsafe_allow_html=True
    )

    st.subheader(
        "Trade Details"
    )


    # =====================================================
    # SCREENSHOT
    # =====================================================

    screenshot = st.file_uploader(
        "Upload Trade Screenshot",
        type=[
            "png",
            "jpg",
            "jpeg"
        ],
        key="trade_screenshot"
    )

    if screenshot is not None:

        new_screenshot = screenshot.getvalue()

        # Only reset analysis when screenshot actually changes
        if (
            st.session_state.screenshot_bytes
            != new_screenshot
        ):

            st.session_state.screenshot_bytes = (
                new_screenshot
            )

            st.session_state.screenshot_type = (
                screenshot.type
            )

            st.session_state.analysis = None
            st.session_state.analysed_trade = None
            st.session_state.trade_saved = False


    # =====================================================
    # TRADE DETAILS
    # =====================================================

    direction = st.selectbox(
        "Trade Direction",
        [
            "Buy",
            "Sell"
        ],
        key="direction"
    )

    entry = st.number_input(
        "Entry Price",
        min_value=0.0,
        format="%.3f",
        key="entry"
    )

    sl = st.number_input(
        "Stop Loss",
        min_value=0.0,
        format="%.3f",
        key="sl"
    )

    tp = st.number_input(
        "Take Profit",
        min_value=0.0,
        format="%.3f",
        key="tp"
    )

    timeframe = st.selectbox(
        "Execution Timeframe",
        [
            "15M",
            "M30",
            "H1",
            "H4",
            "Daily"
        ],
        key="timeframe"
    )


    # =====================================================
    # STRATEGY CONTEXT
    # =====================================================

    st.subheader(
        "Strategy Context"
    )

    trading_session = st.selectbox(
        "Trading Session",
        [
            "Asian",
            "Mid Asian → London Open",
            "Pre-New York → New York",
            "Other / Not sure"
        ],
        key="trading_session"
    )

    entry_model = st.selectbox(
        "Entry Model",
        [
            "Counter Buy",
            "Counter Sell",
            "Impulse Breakout Buy",
            "Impulse Breakout Sell",
            "Complete Breakout Buy",
            "Complete Breakout Sell",
            "S/R Buy",
            "S/R Sell",
            "Wickfill",
            "Impulse / A+",
            "Pullback Buy",
            "Pullback Sell",
            "Fakeout Buy",
            "Fakeout Sell",
            "Big Body Breakout",
            "Not sure"
        ],
        key="entry_model"
    )

    col1, col2 = st.columns(2)

    with col1:

        m30_trend = st.selectbox(
            "M30 Trend / Context",
            [
                "Bullish",
                "Bearish",
                "Range / Neutral",
                "Not sure"
            ],
            key="m30_trend"
        )

    with col2:

        h1_trend = st.selectbox(
            "H1 Trend / Context",
            [
                "Bullish",
                "Bearish",
                "Range / Neutral",
                "Not sure"
            ],
            key="h1_trend"
        )

    current_session_trend = st.selectbox(
        "Current Session Trend",
        [
            "Bullish",
            "Bearish",
            "Range / Neutral",
            "Not sure"
        ],
        key="current_session_trend"
    )

    htf_zone = st.selectbox(
        "H1 / H4 Zone Nearby?",
        [
            "Yes",
            "No",
            "Not sure"
        ],
        key="htf_zone"
    )

    entry_confirmation = st.selectbox(
        "Entry Confirmation",
        [
            "Break of Previous High / Low",
            "Re-break",
            "Flip",
            "Own High / Low Break",
            "Wick Entry",
            "Pullback Confirmation",
            "No Clear Confirmation",
            "Not sure"
        ],
        key="entry_confirmation"
    )

    reason = st.text_area(
        "Why did you take this trade?",
        placeholder=(
            "Explain your reason for entering this trade..."
        ),
        key="reason"
    )

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )


    # =====================================================
    # ANALYSE TRADE
    # =====================================================

    if st.button(
        "🔍 Analyse Trade"
    ):

        if st.session_state.screenshot_bytes is None:

            st.warning(
                "Please upload a trade screenshot."
            )

        elif entry == 0 or sl == 0 or tp == 0:

            st.warning(
                "Please enter Entry, SL and TP."
            )

        elif direction == "Buy" and not (
            sl < entry < tp
        ):

            st.warning(
                "For a Buy trade: "
                "SL must be below Entry and "
                "TP must be above Entry."
            )

        elif direction == "Sell" and not (
            sl > entry > tp
        ):

            st.warning(
                "For a Sell trade: "
                "SL must be above Entry and "
                "TP must be below Entry."
            )

        elif st.session_state.analysis_running:

            st.info(
                "Your trade is already being analysed."
            )

        else:

            st.session_state.analysis_running = True

            try:

                # =================================================
                # PREPARE IMAGE
                # =================================================

                prepared_image = (
                    prepare_trade_image(
                        st.session_state.screenshot_bytes
                    )
                )

                image_base64 = (
                    base64.b64encode(
                        prepared_image
                    ).decode(
                        "utf-8"
                    )
                )

                image_data = (
                    "data:image/jpeg;base64,"
                    + image_base64
                )


                # =================================================
                # BUILD PROMPT
                # =================================================

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

Trading Session:
{trading_session}

Entry Model Selected By Trader:
{entry_model}

M30 Trend / Context:
{m30_trend}

H1 Trend / Context:
{h1_trend}

Current Session Trend:
{current_session_trend}

H1 / H4 Zone Nearby:
{htf_zone}

Entry Confirmation Selected By Trader:
{entry_confirmation}

IMPORTANT:

Treat the above as information provided by the trader,
not independently verified facts.

Compare these details with the uploaded screenshot
and the trader's strategy reference.

If the screenshot does not support a claimed condition,
say that it cannot be verified.

Do not invent missing market information.
"""


                # =================================================
                # UNIQUE REQUEST ID
                # =================================================

                request_key = hashlib.sha256(
                    (
                        st.session_state.screenshot_bytes
                        + prompt.encode("utf-8")
                    )
                ).hexdigest()


                # =================================================
                # CACHE CHECK
                # =================================================

                cached_analysis = (
                    st.session_state.analysis_cache.get(
                        request_key
                    )
                )

                if cached_analysis:

                    analysis_text = (
                        cached_analysis
                    )

                else:

                    # =================================================
                    # OPENAI REQUEST
                    # =================================================

                    response = call_openai_with_retry(
                        input_data=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": prompt
                                    },
                                    {
                                        "type": "input_image",
                                        "image_url": image_data
                                    }
                                ]
                            }
                        ],
                        max_output_tokens=1000,
                        max_retries=6
                    )

                    analysis_text = (
                        response.output_text
                    )

                    # Save completed result
                    st.session_state.analysis_cache[
                        request_key
                    ] = analysis_text


                # =================================================
                # SAVE ANALYSIS
                # =================================================

                st.session_state.analysis = (
                    analysis_text
                )

                st.session_state.analysed_trade = {

                    "direction":
                        direction,

                    "entry":
                        entry,

                    "stop_loss":
                        sl,

                    "take_profit":
                        tp,

                    "timeframe":
                        timeframe,

                    "reason":
                        reason
                }

                st.session_state.trade_saved = False

                st.success(
                    "✅ Trade analysed successfully."
                )


            except RuntimeError as e:

                if str(e) == (
                    "AI_SERVICE_TEMPORARILY_UNAVAILABLE"
                ):

                    # IMPORTANT:
                    # Do NOT show 429 / rate-limit terminology.

                    st.error(
                        "AI analysis is temporarily unavailable. "
                        "Your trade details are still safe. "
                        "Please try again shortly."
                    )

                else:

                    st.error(
                        "AI analysis could not be completed. "
                        "Please try again."
                    )


            except Exception:

                st.error(
                    "AI analysis could not be completed. "
                    "Please try again."
                )

            finally:

                st.session_state.analysis_running = False


    # =====================================================
    # AI RESULT
    # =====================================================

    if st.session_state.analysis:

        st.markdown(
            '<div class="result-box">',
            unsafe_allow_html=True
        )

        st.subheader(
            "📊 AI Trade Review"
        )

        st.markdown(
            st.session_state.analysis
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )


        # =================================================
        # SAVE TRADE
        # =================================================

        if st.button(
            "💾 Save Trade to Journal"
        ):

            if st.session_state.trade_saved:

                st.info(
                    "This trade is already saved."
                )

            elif (
                st.session_state.analysed_trade
                is None
            ):

                st.error(
                    "Please analyse the trade again before saving."
                )

            else:

                analysed_trade = (
                    st.session_state.analysed_trade
                )

                trade_data = {

                    "direction":
                        analysed_trade["direction"],

                    "entry":
                        analysed_trade["entry"],

                    "stop_loss":
                        analysed_trade["stop_loss"],

                    "take_profit":
                        analysed_trade["take_profit"],

                    "timeframe":
                        analysed_trade["timeframe"],

                    "reason":
                        analysed_trade["reason"],

                    "ai_review":
                        st.session_state.analysis
                }

                try:

                    save_trade(
                        trade_data,

                        screenshot_bytes=
                            st.session_state.screenshot_bytes,

                        screenshot_type=
                            st.session_state.screenshot_type
                    )

                    st.session_state.trade_saved = True

                    st.success(
                        "✅ Trade + Screenshot saved permanently to Supabase!"
                    )

                except Exception as e:

                    st.error(
                        f"Failed to save trade: {str(e)}"
                    )


# =========================================================
# TRADE JOURNAL
# =========================================================

elif page == "Trade Journal":

    st.title(
        "📖 Trade Journal"
    )

    st.caption(
        "Your saved trades and AI reviews"
    )

    try:

        trades = get_trades()

    except Exception as e:

        st.error(
            "Could not load journal."
        )

        st.stop()

    if not trades:

        st.info(
            "No trades saved yet."
        )

    else:

        st.success(
            f"Total Trades: {len(trades)}"
        )

        for i, trade in enumerate(
            reversed(trades),
            start=1
        ):

            direction = trade.get(
                "direction",
                "Unknown"
            )

            entry = trade.get(
                "entry",
                0
            )

            sl = trade.get(
                "stop_loss",
                0
            )

            tp = trade.get(
                "take_profit",
                0
            )

            timeframe = trade.get(
                "timeframe",
                "Unknown"
            )

            reason = trade.get(
                "reason",
                ""
            )

            ai_review = trade.get(
                "ai_review",
                ""
            )

            screenshot_url = trade.get(
                "screenshot_url"
            )

            saved_at = trade.get(
                "saved_at",
                ""
            )

            trade_id = trade.get(
                "id"
            )

            with st.expander(
                f"Trade {i} — "
                f"{direction} — "
                f"{timeframe}"
            ):

                col1, col2, col3, col4 = (
                    st.columns(4)
                )

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

                    st.caption(
                        f"Saved: {saved_at}"
                    )


                # -----------------------------------------
                # SCREENSHOT
                # -----------------------------------------

                st.subheader(
                    "📷 Trade Screenshot"
                )

                if screenshot_url:

                    st.image(
                        screenshot_url,
                        caption="Trade Screenshot",
                        use_container_width=True
                    )

                else:

                    st.info(
                        "No screenshot saved for this trade."
                    )


                # -----------------------------------------
                # REASON
                # -----------------------------------------

                st.subheader(
                    "Trade Reason"
                )

                if reason:

                    st.write(reason)

                else:

                    st.write(
                        "No reason recorded."
                    )


                # -----------------------------------------
                # AI REVIEW
                # -----------------------------------------

                st.subheader(
                    "📊 AI Trade Review"
                )

                if ai_review:

                    st.markdown(
                        ai_review
                    )

                else:

                    st.info(
                        "No AI review available."
                    )


                # -----------------------------------------
                # DELETE
                # -----------------------------------------

                st.divider()

                st.subheader(
                    "🗑️ Trade Management"
                )

                if trade_id is not None:

                    delete_key = (
                        f"delete_trade_{trade_id}"
                    )

                    confirm_key = (
                        f"confirm_delete_{trade_id}"
                    )

                    if not st.session_state.get(
                        confirm_key,
                        False
                    ):

                        if st.button(
                            "🗑️ Delete Trade",
                            key=delete_key
                        ):

                            st.session_state[
                                confirm_key
                            ] = True

                            st.rerun()

                    else:

                        st.warning(
                            "Are you sure you want to delete "
                            "this trade and its screenshot?"
                        )

                        confirm_col1, confirm_col2 = (
                            st.columns(2)
                        )

                        with confirm_col1:

                            if st.button(
                                "✅ Yes, Delete",
                                key=f"yes_{trade_id}"
                            ):

                                try:

                                    delete_trade(
                                        trade_id,
                                        screenshot_url
                                    )

                                    st.session_state.pop(
                                        confirm_key,
                                        None
                                    )

                                    st.success(
                                        "Trade deleted successfully."
                                    )

                                    st.rerun()

                                except Exception:

                                    st.error(
                                        "Failed to delete trade."
                                    )

                        with confirm_col2:

                            if st.button(
                                "❌ Cancel",
                                key=f"cancel_{trade_id}"
                            ):

                                st.session_state.pop(
                                    confirm_key,
                                    None
                                )

                                st.rerun()

                else:

                    st.warning(
                        "This trade has no database ID, "
                        "so it cannot be deleted."
                    )


# =========================================================
# DASHBOARD
# =========================================================

elif page == "Dashboard":

    st.title(
        "📊 Trading Dashboard"
    )

    st.caption(
        "Summary of your saved trading journal"
    )

    try:

        trades = get_trades()

    except Exception:

        st.error(
            "Could not load dashboard."
        )

        st.stop()

    if not trades:

        st.info(
            "No trades available in the journal."
        )

        st.stop()


    # =====================================================
    # BASIC STATISTICS
    # =====================================================

    total_trades = len(
        trades
    )

    sell_trades = sum(
        1
        for trade in trades
        if trade.get(
            "direction",
            ""
        ).lower() == "sell"
    )

    buy_trades = sum(
        1
        for trade in trades
        if trade.get(
            "direction",
            ""
        ).lower() == "buy"
    )

    partial_matches = sum(
        1
        for trade in trades
        if "PARTIAL"
        in trade.get(
            "ai_review",
            ""
        ).upper()
    )


    # =====================================================
    # METRICS
    # =====================================================

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Total Trades",
            total_trades
        )

    with col2:

        st.metric(
            "Sell Trades",
            sell_trades
        )

    with col3:

        st.metric(
            "Buy Trades",
            buy_trades
        )

    with col4:

        st.metric(
            "Partial Strategy Match",
            partial_matches
        )

    st.divider()


    # =====================================================
    # TRADE OVERVIEW
    # =====================================================

    st.subheader(
        "📋 Trade Overview"
    )

    for index, trade in enumerate(
        reversed(trades),
        start=1
    ):

        direction = trade.get(
            "direction",
            "Unknown"
        )

        entry = trade.get(
            "entry",
            0
        )

        sl = trade.get(
            "stop_loss",
            0
        )

        tp = trade.get(
            "take_profit",
            0
        )

        timeframe = trade.get(
            "timeframe",
            "Unknown"
        )

        if direction.lower() == "sell":

            risk = abs(
                sl - entry
            )

            reward = abs(
                entry - tp
            )

        else:

            risk = abs(
                entry - sl
            )

            reward = abs(
                tp - entry
            )

        rr = (
            reward / risk
            if risk > 0
            else 0
        )

        with st.expander(
            f"Trade {index} — "
            f"{direction} — "
            f"{timeframe}"
        ):

            col1, col2, col3, col4 = (
                st.columns(4)
            )

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
                st.write(
                    f"1:{rr:.2f}"
                )


    st.divider()


    # =====================================================
    # PATTERN ANALYSIS
    # =====================================================

    st.subheader(
        "🔎 Trading Patterns"
    )

    dcr_count = 0

    rr_below_one_count = 0

    for trade in trades:

        reason_text = trade.get(
            "reason",
            ""
        ).lower()

        if "dcr" in reason_text:

            dcr_count += 1

        entry = trade.get(
            "entry",
            0
        )

        sl = trade.get(
            "stop_loss",
            0
        )

        tp = trade.get(
            "take_profit",
            0
        )

        direction = trade.get(
            "direction",
            ""
        ).lower()

        if direction == "sell":

            risk = abs(
                sl - entry
            )

            reward = abs(
                entry - tp
            )

        else:

            risk = abs(
                entry - sl
            )

            reward = abs(
                tp - entry
            )

        if risk > 0:

            rr = reward / risk

            if rr < 1:

                rr_below_one_count += 1


    col1, col2 = (
        st.columns(2)
    )

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

    st.divider()


    # =====================================================
    # AI PATTERN ANALYSIS
    # =====================================================

    st.subheader(
        "🤖 AI Pattern Analysis"
    )

    st.caption(
        "AI compares your saved trades and identifies "
        "repeated trading patterns."
    )

    # Create fingerprint for current journal
    journal_fingerprint = hashlib.sha256(
        str(
            [
                (
                    trade.get("id"),
                    trade.get("ai_review", "")
                )
                for trade in trades
            ]
        ).encode("utf-8")
    ).hexdigest()


    if st.button(
        "🔍 Analyse Repeated Trading Patterns"
    ):

        try:

            # ---------------------------------------------
            # USE CACHE IF JOURNAL HAS NOT CHANGED
            # ---------------------------------------------

            cached_pattern = (
                st.session_state.pattern_cache.get(
                    journal_fingerprint
                )
            )

            if cached_pattern:

                st.session_state.pattern_analysis = (
                    cached_pattern
                )

            else:

                with st.spinner(
                    "AI is analysing your trading journal..."
                ):

                    pattern_prompt = (
                        build_pattern_analysis_prompt(
                            trades
                        )
                    )

                    pattern_response = (
                        call_openai_with_retry(
                            input_data=pattern_prompt,
                            max_output_tokens=700,
                            max_retries=6
                        )
                    )

                    pattern_text = (
                        pattern_response.output_text
                    )

                    st.session_state.pattern_analysis = (
                        pattern_text
                    )

                    st.session_state.pattern_cache[
                        journal_fingerprint
                    ] = pattern_text


        except RuntimeError as e:

            if str(e) == (
                "AI_SERVICE_TEMPORARILY_UNAVAILABLE"
            ):

                st.error(
                    "AI analysis is temporarily unavailable. "
                    "Please try again shortly."
                )

            else:

                st.error(
                    "AI pattern analysis could not be completed."
                )

        except Exception:

            st.error(
                "AI pattern analysis could not be completed."
            )


    if st.session_state.pattern_analysis:

        st.markdown(
            '<div class="result-box">',
            unsafe_allow_html=True
        )

        st.subheader(
            "📊 Repeated Trading Patterns"
        )

        st.markdown(
            st.session_state.pattern_analysis
        )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

    st.divider()


    # =====================================================
    # MAIN TRADING FOCUS
    # =====================================================

    st.subheader(
        "🎯 Main Trading Focus"
    )

    st.markdown(
        """
        - Verify higher-timeframe context before entry.
        - Confirm the exact entry condition instead of relying only on a setup label.
        - Check Entry, SL and TP distances before execution.
        - Record the relevant candle levels and break/re-break conditions.
        - Follow the defined trading session.
        """
    )

    st.divider()


    # =====================================================
    # JOURNAL STATUS
    # =====================================================

    st.subheader(
        "📌 Current Journal Status"
    )

    st.success(
        f"Your journal currently contains "
        f"{total_trades} saved trades."
    )
