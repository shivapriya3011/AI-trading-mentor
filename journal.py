import os
from datetime import datetime

from supabase import create_client, Client
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL or SUPABASE_KEY is missing in .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# SUPABASE STORAGE BUCKET
# =========================================================

BUCKET_NAME = "trade-screenshots"


# =========================================================
# SAVE TRADE
# =========================================================

def save_trade(
    trade_data,
    screenshot_bytes=None,
    screenshot_type=None
):
    """
    Save trade details to Supabase database
    and screenshot to Supabase Storage.
    """

    screenshot_url = None

    # -----------------------------------------------------
    # SAVE SCREENSHOT
    # -----------------------------------------------------

    if screenshot_bytes:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        if screenshot_type == "image/png":
            extension = "png"
            content_type = "image/png"
        else:
            extension = "jpg"
            content_type = "image/jpeg"

        filename = f"trade_{timestamp}.{extension}"

        supabase.storage \
            .from_(BUCKET_NAME) \
            .upload(
                filename,
                screenshot_bytes,
                {
                    "content-type": content_type
                }
            )

        # -------------------------------------------------
        # PUBLIC IMAGE URL
        # -------------------------------------------------

        screenshot_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/"
            f"{BUCKET_NAME}/{filename}"
        )

    # -----------------------------------------------------
    # SAVE TRADE DATA
    # -----------------------------------------------------

    trade_record = {
        "direction": trade_data.get("direction"),
        "entry": trade_data.get("entry"),
        "stop_loss": trade_data.get("stop_loss"),
        "take_profit": trade_data.get("take_profit"),
        "timeframe": trade_data.get("timeframe"),
        "reason": trade_data.get("reason"),
        "ai_review": trade_data.get("ai_review"),
        "screenshot_url": screenshot_url,
        "saved_at": datetime.now().isoformat()
    }

    # -----------------------------------------------------
    # INSERT INTO SUPABASE
    # -----------------------------------------------------

    response = (
        supabase
        .table("trades")
        .insert(trade_record)
        .execute()
    )

    return response.data


# =========================================================
# GET ALL TRADES
# =========================================================

def get_trades():

    response = (
        supabase
        .table("trades")
        .select("*")
        .order(
            "saved_at",
            desc=False
        )
        .execute()
    )

    return response.data


# =========================================================
# DELETE TRADE
# =========================================================

def delete_trade(
    trade_id,
    screenshot_url=None
):
    """
    Delete one trade from Supabase database
    and delete its screenshot from Supabase Storage.
    """

    # -----------------------------------------------------
    # DELETE SCREENSHOT
    # -----------------------------------------------------

    if screenshot_url:

        try:
            # Get filename from screenshot URL
            filename = screenshot_url.rstrip("/").split("/")[-1]

            if filename:
                supabase.storage \
                    .from_(BUCKET_NAME) \
                    .remove([filename])

        except Exception:
            # Even if screenshot deletion fails,
            # continue deleting the database record.
            pass

    # -----------------------------------------------------
    # DELETE TRADE FROM DATABASE
    # -----------------------------------------------------

    response = (
        supabase
        .table("trades")
        .delete()
        .eq("id", trade_id)
        .execute()
    )

    return response.data