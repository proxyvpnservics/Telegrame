import os
import threading
import time
import zipfile
import io
import requests
import telebot
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ===== ENV CONFIG =====
# এখানে আপনার Demo_Bot এর সঠিক Token দিন
API_TOKEN = os.getenv("BOT_TOKEN", "8908618066:AAFYqlJ0fW4PJWjW-UqYpziXu6WyT7Gul00")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8138758919"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "proxyvpnservice17")
FIREBASE_URL = os.getenv(
    "FIREBASE_URL", "https://shopbotdb-default-rtdb.firebaseio.com/"
)
if not FIREBASE_URL.endswith("/"):
    FIREBASE_URL += "/"
if not API_TOKEN:
    raise SystemExit("ERROR: BOT_TOKEN env variable পাওয়া যায়নি")

CATEGORIES = {
    "telegram_premium": "⭐ Telegram Premium",
    "telegram_protocol": "🌐 Telegram Protocol",
    "vpn_service": "🔒 VPN Service",
    "google_voice": "📞 Google Voice",
    "gmail_account": "📧 Gmail Account",
    "contact_free": "📞 Contact Free",
    "spam_limit": "⚠️ Spam Limit",
    "global_session": "📁 Global Session",
}

DEFAULT_PRODUCTS = {
    "tp_1m": {
        "cat": "telegram_premium",
        "name": "Telegram Premium",
        "package": "1 Month",
        "price": 2,
        "unit": "USDT",
    },
    "tp_12m": {
        "cat": "telegram_premium",
        "name": "Telegram Premium",
        "package": "12 Months",
        "price": 10,
        "unit": "USDT",
    },
    "t_proto": {
        "cat": "telegram_protocol",
        "name": "Telegram Protocol",
        "package": "Standard",
        "price": 1,
        "unit": "USDT",
    },
    "vpn_serv": {
        "cat": "vpn_service",
        "name": "VPN Service",
        "package": "30 Days",
        "price": 1,
        "unit": "USDT",
    },
    "g_voice": {
        "cat": "google_voice",
        "name": "Google Voice US",
        "package": "1 Pc",
        "price": 1,
        "unit": "USDT",
    },
    "gmail_acc": {
        "cat": "gmail_account",
        "name": "Gmail Account",
        "package": "1 Pc",
        "price": 0.20,
        "unit": "USDT",
    },
    "contact_free": {
        "cat": "contact_free",
        "name": "Contact Free",
        "package": "Standard",
        "price": 0.50,
        "unit": "USDT",
    },
    "spam_limit": {
        "cat": "spam_limit",
        "name": "Spam Limit Remove",
        "package": "Standard",
        "price": 1,
        "unit": "USDT",
    },
    "global_session": {
        "cat": "global_session",
        "name": "Global Session",
        "package": "Standard",
        "price": 0.80,
        "unit": "USDT",
    },
}

PRODUCTS = {}
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
trade_data = {}
user_states = {}

try:
    bot.remove_webhook()
    time.sleep(1)
except Exception as e:
    print(f"Webhook warning: {e}")


# ---------- Firebase ----------
def fb_get(p):
    try:
        return requests.get(f"{FIREBASE_URL}{p}.json", timeout=10).json()
    except Exception as e:
        print(f"GET {p}: {e}")
        return None


def fb_put(p, d):
    try:
        requests.put(f"{FIREBASE_URL}{p}.json", json=d, timeout=10)
        return True
    except Exception as e:
        print(f"PUT {p}: {e}")
        return False


def fb_patch(p, d):
    try:
        requests.patch(f"{FIREBASE_URL}{p}.json", json=d, timeout=10)
        return True
    except Exception as e:
        print(f"PATCH {p}: {e}")
        return False


def fb_delete(p):
    try:
        requests.delete(f"{FIREBASE_URL}{p}.json", timeout=10)
        return True
    except Exception as e:
        print(f"DEL {p}: {e}")
        return False


def save_log(uid, act, det, amt):
    try:
        lid = int(time.time() * 1000)
        fb_put(
            f"chatbot_logs/{lid}",
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": str(uid),
                "action_type": act,
                "details": det,
                "amount": str(amt),
            },
        )
    except Exception as e:
        print(e)


def load_products():
    global PRODUCTS
    d = fb_get("products")
    if d and isinstance(d, dict):
        PRODUCTS = d
    else:
        PRODUCTS = DEFAULT_PRODUCTS.copy()
        fb_put("products", PRODUCTS)


def get_user(m):
    uid = m.from_user.id
    fn = m.from_user.first_name or "Unknown"
    ln = m.from_user.last_name or ""
    full_name = f"{fn} {ln}".strip()
    un = m.from_user.username or "No_Username"
    d = fb_get(f"users/{uid}")
    if not d:
        fb_put(
            f"users/{uid}",
            {
                "user_id": uid,
                "first_name": full_name,
                "username": un,
                "balance": 0.0,
                "total_buy": 0,
            },
        )
        return 0.0, 0
    if d.get("first_name") != full_name or d.get("username") != un:
        fb_patch(f"users/{uid}", {"first_name": full_name, "username": un})
    return float(d.get("balance", 0.0)), int(d.get("total_buy", 0))


def get_balance(uid):
    d = fb_get(f"users/{uid}")
    if not d:
        return 0.0, 0
    return float(d.get("balance", 0.0)), int(d.get("total_buy", 0))


def update_balance(uid, amt):
    bal, _ = get_balance(uid)
    new = bal + amt
    fb_put(f"users/{uid}/balance", new)
    return new


def set_balance(uid, nb):
    return fb_put(f"users/{uid}/balance", float(nb))


def add_buy_count(uid):
    _, c = get_balance(uid)
    fb_put(f"users/{uid}/total_buy", c + 1)


def clean_trx(t):
    return (
        t.strip()
        .replace("/", "_")
        .replace(".", "_")
        .replace("#", "_")
        .replace("$", "_")
        .replace("[", "_")
        .replace("]", "_")
    )


def is_trx_used(trx):
    return fb_get(f"transactions/{clean_trx(trx)}") is not None


def record_trx(trx, uid, amt, method):
    fb_put(
        f"transactions/{clean_trx(trx)}",
        {
            "trx_id": trx.strip(),
            "user_id": uid,
            "amount": amt,
            "method": method,
            "status": "pending",
            "time": int(time.time()),
        },
    )
    save_log(uid, "Deposit_Request", f"Method: {method}, TrxID: {trx}", amt)


def update_trx_status(trx, s):
    fb_put(f"transactions/{clean_trx(trx)}/status", s)


def create_order(uid, item, amt, qty, unit, pkg, mid):
    oid = int(time.time() * 1000)
    fb_put(
        f"orders/{oid}",
        {
            "order_id": oid,
            "user_id": uid,
            "item_name": item,
            "amount": amt,
            "qty": qty,
            "unit": unit,
            "package": pkg,
            "sent_msg_id": mid,
            "status": "pending",
            "time": oid,
        },
    )
    save_log(uid, "Order_Placed", f"{item} ({qty} {unit}) [{pkg}]", amt)
    return oid


def update_order_status(oid, s):
    fb_put(f"orders/{oid}/status", s)


def get_order_status(oid):
    return fb_get(f"orders/{oid}/status")


def get_order_details(oid):
    return fb_get(f"orders/{oid}")


# ---------- Menus ----------
def is_admin(o):
    try:
        u = o.from_user
        return u.id == ADMIN_ID or (u.username or "").lower() == ADMIN_USERNAME.lower()
    except Exception:
        return False


def get_main_menu(message=None):
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(KeyboardButton("🛍️ Products"))
    m.row(KeyboardButton("👤 User Center"), KeyboardButton("💰 Deposit"))
    m.row(KeyboardButton("📦 My Orders"))
    if message and is_admin(message):
        m.row(KeyboardButton("⚙️ Admin Control"))
    return m


def cancel_markup():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("❌ Close", callback_data="close"))
    return m


def get_categories_menu():
    m = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(v, callback_data=f"user_view_cat|{k}")
        for k, v in CATEGORIES.items()
    ]
    m.add(*buttons)
    return m


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return


def run_fake_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer.allow_reuse_address = True
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()


def set_bot_commands():
    try:
        bot.set_my_commands([BotCommand("start", "Re-start Bot & Open Menu")])
    except Exception as e:
        print(e)


# ---------- Basic & User Center (Table Design, No Country) ----------
def send_welcome(message):
    get_user(message)
    user_states.pop(message.from_user.id, None)
    bot.clear_step_handler_by_chat_id(message.chat.id)
    trade_data.pop(message.from_user.id, None)
    bot.send_message(
        message.chat.id,
        f"🌸 Welcome 👉 {message.from_user.first_name}!\n\nWelcome to our Shop. Select from the menu below:",
        reply_markup=get_main_menu(message),
    )


def profile_handler(message):
    uid = message.from_user.id
    fn = message.from_user.first_name or "Unknown"
    ln = message.from_user.last_name or ""
    full_name = f"{fn} {ln}".strip()
    un = f"@{message.from_user.username}" if message.from_user.username else "N/A"
    bal, total = get_balance(uid)

    m = InlineKeyboardMarkup(row_width=2)
    m.row(
        InlineKeyboardButton("Field", callback_data="prof_noop"),
        InlineKeyboardButton("Value", callback_data="prof_noop"),
    )
    m.row(
        InlineKeyboardButton("💰 Balance", callback_data="prof_noop"),
        InlineKeyboardButton(f"${bal:.2f}", callback_data="prof_noop"),
    )
    m.row(
        InlineKeyboardButton("🧾 Orders", callback_data="prof_noop"),
        InlineKeyboardButton(f"{total}", callback_data="prof_noop"),
    )
    m.row(
        InlineKeyboardButton("👤 Name", callback_data="prof_noop"),
        InlineKeyboardButton(f"{full_name}", callback_data="prof_noop"),
    )
    m.row(
        InlineKeyboardButton("🆔 Username", callback_data="prof_noop"),
        InlineKeyboardButton(f"{un}", callback_data="prof_noop"),
    )
    m.row(
        InlineKeyboardButton("📱 Chat ID", callback_data="prof_noop"),
        InlineKeyboardButton(f"{uid}", callback_data="prof_noop"),
    )

    bot.send_message(
        message.chat.id,
        "👤 <b>User Center</b>",
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data == "prof_noop")
def profile_noop_callback(call):
    bot.answer_callback_query(call.id)


def global_main_menu(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    trade_data.pop(message.chat.id, None)
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Main Menu:", reply_markup=get_main_menu(message))


MENU_MAP = {
    "🛍️ Buy Product": "buy",
    "🛍️ Products": "buy",
    "👤 Profile": "profile",
    "👤 User Center": "profile",
    "💰 Deposit": "deposit",
    "📦 My Orders": "orders",
    "⚙️ Admin Control": "admin",
    "🏠 Main Menu": "home",
    "< Main Menu": "home",
}


@bot.message_handler(func=lambda m: m.text in MENU_MAP or (m.text or "").startswith("/"))
def menu_router(message):
    text = message.text or ""
    user_states.pop(message.from_user.id, None)
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if text == "/start":
        send_welcome(message)
        return
    a = MENU_MAP.get(text)
    if a == "buy":
        buy_product(message)
    elif a == "profile":
        profile_handler(message)
    elif a == "deposit":
        deposit_handler(message)
    elif a == "orders":
        my_orders_menu(message)
    elif a == "admin":
        admin_control_entry(message)
    elif a == "home":
        global_main_menu(message)


# ---------- Deposit ----------
def deposit_handler(message):
    user_states.pop(message.from_user.id, None)
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("🟡 Binance Pay", callback_data="deposit_binance"),
        InlineKeyboardButton("🌐 Tron Network", callback_data="deposit_tron"),
        InlineKeyboardButton("🔷 BNS Network", callback_data="deposit_bns"),
    )
    bot.send_message(
        message.chat.id, "💎 <b>Select a payment method:</b>", reply_markup=m
    )


@bot.callback_query_handler(func=lambda c: c.data in ["deposit_binance", "deposit_tron", "deposit_bns"])
def deposit_methods(call):
    d = call.data
    if "binance" in d:
        method = "Binance Pay"
        min_amt = 2.0
    elif "tron" in d:
        method = "Tron Network"
        min_amt = 3.0
    elif "bns" in d:
        method = "BNS Network"
        min_amt = 3.0
    else:
        method = "Binance Pay"
        min_amt = 2.0

    user_states[call.from_user.id] = {
        "action": "deposit_select_amt",
        "method": method,
        "min_amt": min_amt,
        "amount_val": 0.0,
    }

    text = (
        f"💵 <b>Method: {method}</b>\n\n"
        f"Select an amount.\n"
        f"Currency: USDT\n"
        f"Minimum: {min_amt} USDT"
    )

    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("💵 0.20", callback_data="dep_amt|0.20"),
        InlineKeyboardButton("💵 0.50", callback_data="dep_amt|0.50"),
        InlineKeyboardButton("💵 1", callback_data="dep_amt|1"),
        InlineKeyboardButton("💵 2", callback_data="dep_amt|2"),
        InlineKeyboardButton("⬅️ Back", callback_data="dep_back"),
        InlineKeyboardButton("📝 Custom", callback_data="dep_custom"),
    )

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=m,
        )
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=m)


@bot.callback_query_handler(func=lambda c: c.data == "dep_back")
def deposit_back_callback(call):
    user_states.pop(call.from_user.id, None)
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("🟡 Binance Pay", callback_data="deposit_binance"),
        InlineKeyboardButton("🌐 Tron Network", callback_data="deposit_tron"),
        InlineKeyboardButton("🔷 BNS Network", callback_data="deposit_bns"),
    )
    text = "💎 <b>Select a payment method:</b>"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=m)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=m)


@bot.callback_query_handler(func=lambda c: c.data == "dep_custom")
def deposit_custom_callback(call):
    uid = call.from_user.id
    st = user_states.get(uid, {})
    min_amt = st.get("min_amt", 2.0)
    if uid in user_states:
        user_states[uid]["action"] = "deposit_custom_input"

    msg = bot.send_message(
        call.message.chat.id,
        f"✍️ Enter custom USDT amount (Minimum {min_amt}):",
        reply_markup=cancel_markup(),
    )
    bot.register_next_step_handler(msg, process_deposit_custom_amount)


@bot.callback_query_handler(func=lambda c: c.data.startswith("dep_amt|"))
def deposit_amount_selected(call):
    uid = call.from_user.id
    amt = float(call.data.split("|")[1])
    st = user_states.get(uid, {})
    method = st.get("method", "Binance Pay")
    min_amt = st.get("min_amt", 2.0)

    user_states[uid] = {
        "action": "deposit_select_amt",
        "method": method,
        "min_amt": min_amt,
        "amount_val": amt,
    }

    text = (
        f"💵 <b>Method: {method}</b>\n\n"
        f"Select an amount.\n"
        f"Currency: USDT\n"
        f"Minimum: {min_amt} USDT\n\n"
        f"Selected amount: <b>{amt:g} USDT</b>"
    )

    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("💵 0.20", callback_data="dep_amt|0.20"),
        InlineKeyboardButton("💵 0.50", callback_data="dep_amt|0.50"),
        InlineKeyboardButton("💵 1", callback_data="dep_amt|1"),
        InlineKeyboardButton("💵 2", callback_data="dep_amt|2"),
        InlineKeyboardButton("⬅️ Back", callback_data="dep_back"),
        InlineKeyboardButton("📝 Custom", callback_data="dep_custom"),
        InlineKeyboardButton("➡️ Next", callback_data="dep_next"),
    )

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=m)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=m)


def process_deposit_custom_amount(message):
    uid = message.from_user.id
    if (message.text or "") in ["❌ Cancel", "/start"]:
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return
    try:
        amt = float(message.text.strip())
        st = user_states.get(uid, {})
        min_amt = st.get("min_amt", 2.0)
        method = st.get("method", "Binance Pay")

        user_states[uid] = {
            "action": "deposit_select_amt",
            "method": method,
            "min_amt": min_amt,
            "amount_val": amt,
        }

        text = (
            f"💵 <b>Method: {method}</b>\n\n"
            f"Select an amount.\n"
            f"Currency: USDT\n"
            f"Minimum: {min_amt} USDT\n\n"
            f"Selected amount: <b>{amt:g} USDT</b>"
        )

        m = InlineKeyboardMarkup(row_width=2)
        m.add(
            InlineKeyboardButton("💵 0.20", callback_data="dep_amt|0.20"),
            InlineKeyboardButton("💵 0.50", callback_data="dep_amt|0.50"),
            InlineKeyboardButton("💵 1", callback_data="dep_amt|1"),
            InlineKeyboardButton("💵 2", callback_data="dep_amt|2"),
            InlineKeyboardButton("⬅️ Back", callback_data="dep_back"),
            InlineKeyboardButton("📝 Custom", callback_data="dep_custom"),
            InlineKeyboardButton("➡️ Next", callback_data="dep_next"),
        )

        bot.send_message(message.chat.id, text, reply_markup=m)
    except ValueError:
        st = user_states.get(uid, {})
        min_amt = st.get("min_amt", 2.0)
        msg = bot.send_message(message.chat.id, f"❌ Please enter a valid number (Minimum {min_amt}):")
        bot.register_next_step_handler(msg, process_deposit_custom_amount)


@bot.callback_query_handler(func=lambda c: c.data == "dep_next")
def deposit_next_callback(call):
    uid = call.from_user.id
    st = user_states.get(uid, {})
    amt = st.get("amount_val", 0.0)
    min_amt = st.get("min_amt", 2.0)
    method = st.get("method", "Binance Pay")

    if amt < min_amt:
        bot.answer_callback_query(call.id, f"Please select at least {min_amt} USDT!", show_alert=True)
        return

    user_states[uid]["action"] = "deposit_trx"

    binance_id = os.getenv("BINANCE_ID", "1290480685")
    tron_address = os.getenv("TRON_ADDRESS", "TXxxxxxx...xxxxxx")
    bns_address = os.getenv("BNS_ADDRESS", "BNSxxxxx...xxxxx")

    if method == "Binance Pay":
        info = f"{binance_id}"
    elif method == "Tron Network":
        info = f"{tron_address}"
    else:
        info = f"{bns_address}"

    text = (
        f"💲 <b>Payment Details</b>\n\n"
        f"💲 Amount: <b>{amt:g} USDT</b>\n"
        f"📱 Address: <code>{info}</code>\n\n"
        f"1. Send {amt:g} USDT via {method} to this address.\n\n"
        f"2. After payment, send the Transaction ID (TrxID) below."
    )

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=None)

    bot.send_message(call.message.chat.id, "✍️ Now send your Transaction ID (TrxID) / Hash below:")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("action") == "deposit_trx")
def deposit_text_flow(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    st = user_states.get(uid, {})

    method = st.get("method", "Binance Pay")
    usdt_amt = st.get("amount_val", 0.0)
    trx = text

    if is_trx_used(trx):
        bot.send_message(
            message.chat.id,
            f"⚠️ This Transaction ID/Hash ('{trx}') already used! Provide correct ID:",
            reply_markup=cancel_markup(),
        )
        return

    record_trx(trx, uid, usdt_amt, method)
    user_states.pop(uid, None)

    bot.send_message(
        message.chat.id,
        "⏳ Your payment / deposit request is pending verification.",
        reply_markup=get_main_menu(message),
    )

    am = InlineKeyboardMarkup()
    am.row(
        InlineKeyboardButton(
            "✅ Approve Deposit", callback_data=f"depapprove|{uid}|{usdt_amt}|{trx}"
        ),
        InlineKeyboardButton("❌ Reject Deposit", callback_data=f"depreject|{uid}|{trx}"),
    )
    bot.send_message(
        ADMIN_ID,
        f"🔔 <b>New Deposit Request!</b>\n\n👤 User: {message.from_user.first_name} (<code>{uid}</code>)\n💳 Method: {method}\n💰 Amount: {usdt_amt:g} USDT\n🔢 TrxID/Hash: <code>{trx}</code>",
        reply_markup=am,
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("depapprove|") or c.data.startswith("depreject|")
)
def admin_deposit_action(call):
    if not is_admin(call):
        bot.answer_callback_query(call.id, "You are not admin!", show_alert=True)
        return
    bot.answer_callback_query(call.id, text="Processed!")
    p = call.data.split("|")
    act = p[0]
    tid = int(p[1])
    if act == "depapprove":
        amt = float(p[2])
        trx = p[3]
        nb = update_balance(tid, amt)
        update_trx_status(trx, "approved")
        try:
            bot.edit_message_text(
                f"✅ Deposit approved!\n🆔 User: <code>{tid}</code>\n🔢 TrxID: <code>{trx}</code>\n💰 Added: {amt:g} USDT",
                call.message.chat.id,
                call.message.message_id,
            )
        except Exception:
            pass
        try:
            bot.send_message(
                tid,
                f"✅ Your deposit was verified!\n💰 {amt:g} USDT added.\n💵 Balance: ${nb:.2f}",
            )
        except Exception:
            pass
    else:
        trx = p[2]
        update_trx_status(trx, "rejected")
        try:
            bot.edit_message_text(
                f"❌ Deposit rejected.\n🆔 User: <code>{tid}</code>\n🔢 TrxID: <code>{trx}</code>",
                call.message.chat.id,
                call.message.message_id,
            )
        except Exception:
            pass
        try:
            bot.send_message(tid, "❌ Your deposit request has been rejected.")
        except Exception:
            pass


# ---------- Broadcast ----------
@bot.message_handler(commands=["broadcast"])
def broadcast_message(message):
    if not is_admin(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(
            message.chat.id, "❌ Example:\n<code>/broadcast Your message here</code>"
        )
        return
    users = fb_get("users") or {}
    if not isinstance(users, dict) or not users:
        bot.send_message(message.chat.id, "❌ No users found.")
        return
    bot.send_message(message.chat.id, "⏳ Broadcasting started...")
    ok = fail = 0
    for uid_str in list(users.keys()):
        try:
            bot.send_message(int(uid_str), parts[1])
            ok += 1
            time.sleep(0.1)
        except Exception as e:
            fail += 1
            print(e)
    bot.send_message(
        message.chat.id,
        f"✅ <b>Broadcast Completed!</b>\nSent: {ok}\nFailed: {fail}",
    )


# ---------- Admin ----------
def admin_control_entry(message):
    if not is_admin(message):
        return
    bot.clear_step_handler_by_chat_id(message.chat.id)
    user_states.pop(message.from_user.id, None)
    show_admin_control_dashboard(message.chat.id)


def get_admin_dashboard_markup():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton(
            "🛍️ Product Control (Edit / Delete / Add)",
            callback_data="adm_prod_menu",
        ),
        InlineKeyboardButton(
            "📁 Export/Import Products ZIP",
            callback_data="adm_zip_menu",
        ),
        InlineKeyboardButton(
            "👥 User Info & Balance Management", callback_data="adm_users_list"
        ),
        InlineKeyboardButton("❌ Close", callback_data="close"),
    )
    return m


def show_admin_control_dashboard(chat_id, mid=None):
    users = fb_get("users") or {}
    total = len(users) if isinstance(users, dict) else 0
    text = f"⚙️ <b>Admin Control Dashboard</b>\n\n🔹 <b>Total Products:</b> {len(PRODUCTS)}\n🔹 <b>Total Users:</b> {total}"
    if mid:
        try:
            bot.edit_message_text(
                text, chat_id, mid, reply_markup=get_admin_dashboard_markup()
            )
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=get_admin_dashboard_markup())


@bot.callback_query_handler(func=lambda c: c.data == "adm_back_dash")
def admin_back_to_dash(call):
    show_admin_control_dashboard(call.message.chat.id, call.message.message_id)


# -------- Zip Export/Import & Auto-Stock Management --------
@bot.callback_query_handler(func=lambda c: c.data == "adm_zip_menu")
def admin_zip_menu(call):
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("📥 Download Products ZIP", callback_data="adm_download_zip"),
        InlineKeyboardButton("📤 Upload Products ZIP", callback_data="adm_upload_zip_prompt"),
        InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_back_dash"),
    )
    bot.edit_message_text(
        "📁 <b>ZIP File Management</b>\n\nManage products via ZIP:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data == "adm_download_zip")
def admin_download_zip(call):
    target_cats = ["telegram_protocol", "contact_free", "spam_limit", "global_session"]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for pid, p in PRODUCTS.items():
            if p.get("cat") in target_cats:
                content = (
                    f"Category: {p.get('cat')}\n"
                    f"Country: {p.get('country', 'N/A')}\n"
                    f"Country Code: {p.get('country_code', 'N/A')}\n"
                    f"Price: {p.get('price')} USDT\n"
                    f"Unit: {p.get('unit')}"
                )
                zip_file.writestr(f"{p.get('cat')}_{pid}.txt", content)

    zip_buffer.seek(0)
    bot.send_document(
        call.message.chat.id,
        (f"products_backup_{int(time.time())}.zip", zip_buffer.read()),
        caption="📁 Here is the ZIP file containing products backup.",
    )
    bot.answer_callback_query(call.id, "ZIP downloaded successfully!")


@bot.callback_query_handler(func=lambda c: c.data == "adm_upload_zip_prompt")
def admin_upload_zip_prompt(call):
    user_states[call.from_user.id] = {"action": "waiting_for_zip"}
    msg = bot.send_message(
        call.message.chat.id,
        "📤 Please send the `.zip` file containing product text files:",
        reply_markup=cancel_markup(),
    )
    bot.register_next_step_handler(msg, handle_uploaded_zip)


def handle_uploaded_zip(message):
    uid = message.from_user.id
    if (message.text or "") in ["❌ Cancel", "/start"]:
        user_states.pop(uid, None)
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return

    if not message.document or not message.document.file_name.endswith(".zip"):
        msg = bot.send_message(message.chat.id, "❌ Please send a valid `.zip` file:")
        bot.register_next_step_handler(msg, handle_uploaded_zip)
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with zipfile.ZipFile(io.BytesIO(downloaded_file), "r") as z:
            count = 0
            for filename in z.namelist():
                if filename.endswith(".txt"):
                    with z.open(filename) as f:
                        lines = f.read().decode("utf-8").splitlines()
                        data = {}
                        for line in lines:
                            if ":" in line:
                                k, v = line.split(":", 1)
                                data[k.strip().lower()] = v.strip()

                        cat = data.get("category", "telegram_protocol")
                        country = data.get("country", "Standard")
                        country_code = data.get("country_code", "")
                        try:
                            price = float(data.get("price", "1").replace("USDT", "").strip())
                        except ValueError:
                            price = 1.0

                        pid = f"{cat}_{int(time.time()*1000)}_{count}"
                        np = {
                            "cat": cat,
                            "name": CATEGORIES.get(cat, "Product"),
                            "package": f"{country} ({country_code})" if country_code else country,
                            "country": country,
                            "country_code": country_code,
                            "price": price,
                            "unit": "USDT",
                        }
                        PRODUCTS[pid] = np
                        fb_put(f"products/{pid}", np)
                        count += 1

        user_states.pop(uid, None)
        bot.send_message(
            message.chat.id,
            f"✅ Successfully imported {count} items from ZIP!",
            reply_markup=get_main_menu(message),
        )
    except Exception as e:
        user_states.pop(uid, None)
        bot.send_message(
            message.chat.id,
            f"❌ Failed to process ZIP: {e}",
            reply_markup=get_main_menu(message),
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_upload_stock|"))
def admin_upload_stock_prompt(call):
    pid = call.data.split("|")[1]
    user_states[call.from_user.id] = {"action": "waiting_for_stock_file", "pid": pid}
    msg = bot.send_message(
        call.message.chat.id,
        "📤 Please send a `.txt` or `.zip` file containing accounts/2FA details (one per line):",
        reply_markup=cancel_markup(),
    )
    bot.register_next_step_handler(msg, process_stock_file_upload)


def process_stock_file_upload(message):
    uid = message.from_user.id
    st = user_states.get(uid, {})
    pid = st.get("pid")

    if (message.text or "") in ["❌ Cancel", "/start"]:
        user_states.pop(uid, None)
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return

    if not message.document:
        msg = bot.send_message(message.chat.id, "❌ Please upload a valid file (.txt or .zip):")
        bot.register_next_step_handler(msg, process_stock_file_upload)
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        new_stocks = []
        filename = message.document.file_name

        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(downloaded_file), "r") as z:
                for sub_file in z.namelist():
                    if sub_file.endswith(".txt"):
                        with z.open(sub_file) as f:
                            lines = f.read().decode("utf-8").splitlines()
                            for line in lines:
                                if line.strip():
                                    new_stocks.append(line.strip())
        else:
            lines = downloaded_file.decode("utf-8").splitlines()
            for line in lines:
                if line.strip():
                    new_stocks.append(line.strip())

        existing_stocks = fb_get(f"products/{pid}/stocks") or []
        if isinstance(existing_stocks, list):
            existing_stocks.extend(new_stocks)
        else:
            existing_stocks = new_stocks

        fb_put(f"products/{pid}/stocks", existing_stocks)
        user_states.pop(uid, None)

        bot.send_message(
            message.chat.id,
            f"✅ Successfully added <b>{len(new_stocks)}</b> items to stock!\nTotal Stock: <b>{len(existing_stocks)}</b>",
            reply_markup=get_main_menu(message),
        )
    except Exception as e:
        user_states.pop(uid, None)
        bot.send_message(
            message.chat.id,
            f"❌ Error processing file: {e}",
            reply_markup=get_main_menu(message),
        )


@bot.callback_query_handler(func=lambda c: c.data == "adm_users_list")
def admin_users_list_handler(call):
    users = fb_get("users") or {}
    if not users or not isinstance(users, dict):
        bot.answer_callback_query(call.id, "No user data!", show_alert=True)
        return
    m = InlineKeyboardMarkup(row_width=1)
    for uid_str, u in users.items():
        if isinstance(u, dict):
            m.add(
                InlineKeyboardButton(
                    f"👤 {u.get('first_name','User')} (@{u.get('username','No_Username')}) | 💰 ${float(u.get('balance',0)):.2f}",
                    callback_data=f"adm_user_view|{uid_str}",
                )
            )
    m.add(
        InlineKeyboardButton(
            "🔙 Back to Dashboard", callback_data="adm_back_dash"
        )
    )
    bot.edit_message_text(
        "👥 <b>All Users List:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_user_view|"))
def admin_view_single_user(call):
    uid_str = call.data.split("|")[1]
    u = fb_get(f"users/{uid_str}")
    if not u or not isinstance(u, dict):
        bot.answer_callback_query(call.id, "User not found!", show_alert=True)
        return
    text = f"👤 <b>User Details</b>\n\n📛 <b>Name:</b> {u.get('first_name','Unknown')}\n🏷️ <b>Username:</b> @{u.get('username','No_Username')}\n🆔 <b>User ID:</b> <code>{uid_str}</code>\n💰 <b>Balance:</b> ${float(u.get('balance',0)):.2f}\n🛍️ <b>Total Purchases:</b> {int(u.get('total_buy',0))}"
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton(
            "💵 Edit Balance", callback_data=f"adm_edit_bal|{uid_str}"
        ),
        InlineKeyboardButton("🔙 User List", callback_data="adm_users_list"),
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=m
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_edit_bal|"))
def admin_edit_user_balance_prompt(call):
    uid_str = call.data.split("|")[1]
    msg = bot.send_message(
        call.message.chat.id,
        f"💳 Enter new balance for user <code>{uid_str}</code> in USDT:",
        reply_markup=cancel_markup(),
    )
    bot.register_next_step_handler(msg, process_admin_edit_balance, uid_str)


def process_admin_edit_balance(message, uid_str):
    if (message.text or "") in ["❌ Cancel", "🏠 Main Menu", "< Main Menu"]:
        bot.send_message(
            message.chat.id, "Cancelled.", reply_markup=get_main_menu(message)
        )
        return
    try:
        nb = float(message.text.strip())
        if set_balance(uid_str, nb):
            bot.send_message(
                message.chat.id,
                f"✅ Updated user <code>{uid_str}</code> balance to <b>${nb:.2f}</b>.",
            )
            try:
                bot.send_message(
                    int(uid_str),
                    f"🔔 Your balance updated by admin.\n💰 Current Balance: <b>${nb:.2f}</b>",
                )
            except Exception:
                pass
        else:
            bot.send_message(message.chat.id, "❌ Failed.")
        show_admin_control_dashboard(message.chat.id)
    except Exception as e:
        bot.send_message(
            message.chat.id, f"❌ Valid number দিন: {e}", reply_markup=get_main_menu(message)
        )


@bot.callback_query_handler(func=lambda c: c.data == "adm_prod_menu")
def admin_product_menu(call):
    m = InlineKeyboardMarkup(row_width=2)
    for k, v in CATEGORIES.items():
        m.add(InlineKeyboardButton(v, callback_data=f"adm_cat|{k}"))
    m.add(
        InlineKeyboardButton(
            "➕ Add New Product", callback_data="adm_add_prod_cat_select"
        )
    )
    m.add(
        InlineKeyboardButton(
            "🔙 Back to Dashboard", callback_data="adm_back_dash"
        )
    )
    bot.edit_message_text(
        "🛍️ <b>Product Control Panel</b>\n\nSelect category:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_cat|"))
def admin_show_category_products(call):
    cat = call.data.split("|")[1]
    matched = {pid: p for pid, p in PRODUCTS.items() if p.get("cat") == cat}
    m = InlineKeyboardMarkup(row_width=1)
    for pid, p in matched.items():
        country_info = f" [{p.get('country')} ({p.get('country_code')})]" if p.get("country") else ""
        m.add(
            InlineKeyboardButton(
                f"⚙️ {p.get('name')}{country_info} - {p.get('price')} USDT",
                callback_data=f"admpview|{pid}",
            )
        )
    m.add(
        InlineKeyboardButton(
            f"➕ Add New {CATEGORIES.get(cat)}",
            callback_data=f"adm_add_to_cat|{cat}",
        )
    )
    m.add(
        InlineKeyboardButton(
            "🔙 Back to Categories", callback_data="adm_prod_menu"
        )
    )
    bot.edit_message_text(
        f"📂 <b>{CATEGORIES.get(cat)} Products ({len(matched)}):</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admpview|"))
def admin_view_product_details(call):
    pid = call.data.split("|")[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        bot.answer_callback_query(call.id, "❌ Product not found!", show_alert=True)
        return
    stocks = fb_get(f"products/{pid}/stocks") or []
    stock_count = len(stocks) if isinstance(stocks, list) else 0
    text = (
        f"📦 <b>Product Details</b>\n\n"
        f"🏷️ <b>Name:</b> {prod.get('name')}\n"
        f"🌍 <b>Country:</b> {prod.get('country', 'N/A')}\n"
        f"🔢 <b>Country Code:</b> {prod.get('country_code', 'N/A')}\n"
        f"📦 <b>Package:</b> {prod.get('package')}\n"
        f"💰 <b>Price:</b> {prod.get('price')} USDT\n"
        f"📊 <b>Available Stock:</b> {stock_count} Pc\n"
        f"📂 <b>Category:</b> {CATEGORIES.get(prod.get('cat'),'N/A')}"
    )
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("📤 Upload Stock (.zip/.txt)", callback_data=f"adm_upload_stock|{pid}")
    )
    m.add(
        InlineKeyboardButton("💰 Edit Price", callback_data=f"admedit_price|{pid}"),
        InlineKeyboardButton("🏷️ Edit Name", callback_data=f"admedit_name|{pid}"),
    )
    m.add(
        InlineKeyboardButton("🌍 Edit Country", callback_data=f"admedit_country|{pid}"),
        InlineKeyboardButton("🔢 Edit Code", callback_data=f"admedit_code|{pid}"),
    )
    m.add(
        InlineKeyboardButton("🗑️ Delete / Remove", callback_data=f"admpdel|{pid}"),
        InlineKeyboardButton("🔙 Back", callback_data=f"adm_cat|{prod.get('cat')}"),
    )
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=m
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("admpdel|"))
def admin_delete_product(call):
    pid = call.data.split("|")[1]
    prod = PRODUCTS.pop(pid, None)
    if prod:
        fb_delete(f"products/{pid}")
        bot.answer_callback_query(call.id, "✅ Removed!", show_alert=True)
        call.data = f"adm_cat|{prod.get('cat')}"
        admin_show_category_products(call)
    else:
        bot.answer_callback_query(call.id, "❌ Not found!", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("admedit_"))
def admin_edit_product_prompt(call):
    parts = call.data.split("|")
    field = parts[0].replace("admedit_", "")
    pid = parts[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        bot.answer_callback_query(call.id, "Not found!", show_alert=True)
        return
    if field == "price":
        msg = bot.send_message(call.message.chat.id, "Enter new price in USDT:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, process_update_prod_field, pid, "price", float)
    elif field == "name":
        msg = bot.send_message(call.message.chat.id, "Enter new name:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, process_update_prod_field, pid, "name", str)
    elif field == "country":
        msg = bot.send_message(call.message.chat.id, "Enter Country name (e.g. Bangladesh):", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, process_update_prod_field, pid, "country", str)
    elif field == "code":
        msg = bot.send_message(call.message.chat.id, "Enter Country Code (e.g. +880):", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, process_update_prod_field, pid, "country_code", str)


def process_update_prod_field(message, pid, fk, vt):
    if (message.text or "") in ["❌ Cancel", "🏠 Main Menu", "< Main Menu"]:
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return
    try:
        nv = vt(message.text.strip())
        if pid in PRODUCTS:
            PRODUCTS[pid][fk] = nv
            fb_put(f"products/{pid}", PRODUCTS[pid])
            bot.send_message(message.chat.id, f"✅ Updated <b>{fk}</b> to: <code>{nv}</code>")
        show_admin_control_dashboard(message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Invalid: {e}", reply_markup=get_main_menu(message))


@bot.callback_query_handler(
    func=lambda c: c.data in ["adm_add_prod_cat_select"]
    or c.data.startswith("adm_add_to_cat|")
)
def admin_add_product_step1(call):
    if call.data.startswith("adm_add_to_cat|"):
        start_add_product_flow(call.message.chat.id, call.data.split("|")[1])
    else:
        m = InlineKeyboardMarkup(row_width=2)
        for k, v in CATEGORIES.items():
            m.add(InlineKeyboardButton(v, callback_data=f"adm_add_to_cat|{k}"))
        m.add(InlineKeyboardButton("🔙 Back", callback_data="adm_prod_menu"))
        bot.edit_message_text(
            "Select category to add:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=m,
        )


def start_add_product_flow(chat_id, cat_key):
    user_states[chat_id] = {"action": "adding_product", "cat": cat_key}
    msg = bot.send_message(
        chat_id,
        f"🌍 Enter Country Name for <b>{CATEGORIES.get(cat_key)}</b>:",
        reply_markup=cancel_markup(),
    )
    bot.register_next_step_handler(msg, add_prod_step_country)


def add_prod_step_country(message):
    if (message.text or "") in ["❌ Cancel", "🏠 Main Menu", "< Main Menu"]:
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return
    user_states[message.chat.id]["country"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "🔢 Enter Country Code (e.g. +880):", reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, add_prod_step_code)


def add_prod_step_code(message):
    if (message.text or "") in ["❌ Cancel", "🏠 Main Menu", "< Main Menu"]:
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return
    user_states[message.chat.id]["country_code"] = message.text.strip()
    msg = bot.send_message(message.chat.id, "💰 Enter price in USDT:", reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, add_prod_step_price)


def add_prod_step_price(message):
    if (message.text or "") in ["❌ Cancel", "🏠 Main Menu", "< Main Menu"]:
        bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_main_menu(message))
        return
    try:
        user_states[message.chat.id]["price"] = float(message.text.strip())
        d = user_states.pop(message.chat.id, {})
        pid = f"{d.get('cat','telegram_protocol')}_{int(time.time()*1000)}"
        country = d.get("country", "Bangladesh")
        country_code = d.get("country_code", "+880")
        np = {
            "cat": d.get("cat", "telegram_protocol"),
            "name": CATEGORIES.get(d.get("cat"), "Product"),
            "package": f"{country} ({country_code})",
            "country": country,
            "country_code": country_code,
            "price": d.get("price", 1),
            "unit": "USDT",
        }
        PRODUCTS[pid] = np
        fb_put(f"products/{pid}", np)
        bot.send_message(
            message.chat.id,
            f"✅ <b>New product added!</b>\n\n🌍 Country: {country} ({country_code})\n💰 Price: {np['price']} USDT",
        )
        show_admin_control_dashboard(message.chat.id)
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Valid number দিন:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, add_prod_step_price)


# ---------- Buy Product (User Centre - No Country Display) ----------
def buy_product(message):
    bot.send_message(
        message.chat.id,
        "Select a category what you want to buy:",
        reply_markup=get_categories_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("user_view_cat|"))
def user_view_category(call):
    cat = call.data.split("|")[1]
    matched = [(pid, p) for pid, p in PRODUCTS.items() if p.get("cat") == cat]
    if not matched:
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_cat"))
        bot.edit_message_text(
            f"Sorry, no products in <b>{CATEGORIES.get(cat)}</b>.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=m,
        )
        return
    m = InlineKeyboardMarkup(row_width=1)
    for pid, p in matched:
        m.add(
            InlineKeyboardButton(
                f"🛡️ {p.get('name')} - {float(p.get('price')):g} USDT",
                callback_data=f"selprod|{pid}",
            )
        )
    m.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_cat"))
    bot.edit_message_text(
        f"Select package for <b>{CATEGORIES.get(cat)}</b>:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("selprod|"))
def ask_product_quantity(call):
    pid = call.data.split("|")[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        bot.answer_callback_query(call.id, "Not available!", show_alert=True)
        return
    user_states[call.from_user.id] = {
        "action": "enter_qty",
        "pid": pid,
        "product": prod.get("name"),
        "rate": float(prod.get("price")),
        "unit": prod.get("unit", "Pc"),
        "package": prod.get("package", "Standard"),
    }
    rate = float(prod.get("price"))
    msg = f"🔑 Product: {prod.get('name')}\n\nMinimum: 1 Pc\nPrice: 1 Pc = {rate:g} USDT\n\nHow many pieces? (Enter numbers only)"
    bot.send_message(call.message.chat.id, msg)


@bot.message_handler(
    func=lambda m: user_states.get(m.from_user.id, {}).get("action") == "enter_qty"
)
def handle_quantity(message):
    uid = message.from_user.id
    st = user_states.get(uid, {})
    try:
        qty = float((message.text or "").strip())
        if qty <= 0:
            raise ValueError()
        if qty != int(qty):
            bot.send_message(message.chat.id, "❌ Please enter a whole number (1, 2, 5).")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Valid number দিন.")
        return
    total = qty * st["rate"]
    trade_data[uid] = {
        "pid": st["pid"],
        "product": st["product"],
        "unit": st["unit"],
        "package": st["package"],
    }
    user_states.pop(uid, None)
    qs = f"{qty:g}"
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton(
            f"💰 Pay {total:g} USDT from Balance", callback_data=f"paybal|{qs}|{total}"
        )
    )
    m.add(InlineKeyboardButton("❌ Cancel", callback_data="close"))
    bot.send_message(
        message.chat.id,
        f"🧾 <b>Order Summary</b>\n\n📦 Product: {st['product']}\n🔢 Quantity: {qs} {st['unit']}\n💰 Total: <b>{total:g} USDT</b>\n\nConfirm payment:",
        reply_markup=m,
    )


def deliver_stock_item_to_user(uid, pid, qty, oid, smid):
    stocks = fb_get(f"products/{pid}/stocks")
    if not stocks or not isinstance(stocks, list) or len(stocks) < int(qty):
        return False

    delivered_items = stocks[: int(qty)]
    remaining_stocks = stocks[int(qty) :]
    fb_put(f"products/{pid}/stocks", remaining_stocks)

    code_text = "\n".join(delivered_items)
    update_order_status(oid, "delivered")

    bal, _ = get_balance(uid)
    if smid:
        try:
            bot.delete_message(uid, smid)
        except Exception:
            pass

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("Reply to Admin", url=f"https://t.me/{ADMIN_USERNAME}"))

    try:
        bot.send_message(
            uid,
            f"✅ <b>Purchase Successful!</b>\n\n📦 Order: #{oid}\n🔢 Quantity: {qty:g} Pc\n💰 Balance: <b>${bal:.2f}</b>\n\n🔑 <b>Your Account / 2FA Details :</b>\n<code>{code_text}</code>",
            reply_markup=m,
        )
        bot.send_message(
            ADMIN_ID,
            f"✅ Order #{oid} automatically delivered {qty:g} items to user <code>{uid}</code> from stock!",
        )
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Failed to deliver message to user: {e}")
    return True


@bot.callback_query_handler(func=lambda c: c.data.startswith("paybal|"))
def process_balance_payment(call):
    try:
        _, qs, ps = call.data.split("|")
        qty = float(qs)
        price = float(ps)
        info = trade_data.get(call.from_user.id, {})
        pid = info.get("pid")
        item = info.get("product", "Product")
        unit = info.get("unit", "Pc")
        pkg = info.get("package", "Standard")
        bal, _ = get_balance(call.from_user.id)
        if bal < price:
            bot.answer_callback_query(call.id, "❌ Balance কম!", show_alert=True)
            return
        update_balance(call.from_user.id, -price)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        smid = 0
        try:
            sm = bot.send_message(
                call.message.chat.id,
                "🤗 Your order has been received.\nChecking stock for instant delivery...",
            )
            smid = sm.message_id
        except Exception as e:
            print(e)
        oid = create_order(call.from_user.id, item, price, qs, unit, pkg, smid)
        add_buy_count(call.from_user.id)
        bot.answer_callback_query(call.id, "✅ Payment successful!")

        if pid and deliver_stock_item_to_user(call.from_user.id, pid, qty, oid, smid):
            return

        threading.Thread(
            target=check_and_refund,
            args=(oid, call.from_user.id, price, item, smid),
            daemon=True,
        ).start()
        am = InlineKeyboardMarkup()
        am.add(
            InlineKeyboardButton(
                "📦 Deliver Order", callback_data=f"sendproduct|{oid}"
            )
        )
        bot.send_message(
            ADMIN_ID,
            f"🛒 New Order! #{oid} (Manual Delivery)\n\n👤 User: {call.from_user.first_name} (<code>{call.from_user.id}</code>)\n📦 Product: {item}\n💰 Price: {price:g} USDT",
            reply_markup=am,
        )
    except Exception as e:
        print(e)
        bot.answer_callback_query(call.id, "❌ Error!", show_alert=True)


def check_and_refund(oid, uid, amt, item, smid):
    time.sleep(1800)
    if get_order_status(oid) == "pending":
        update_balance(uid, amt)
        update_order_status(oid, "refunded")
        try:
            bot.delete_message(uid, smid)
        except Exception:
            pass
        try:
            bot.send_message(
                uid, f"⚠️ Sorry! Your order ({item}) auto-cancelled and refunded."
            )
            bot.send_message(
                ADMIN_ID,
                f"🚨 Auto-Refund! User <code>{uid}</code> order #{oid} ({item}) refunded.",
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("sendproduct|"))
def admin_ask_delivery_code(call):
    if not is_admin(call):
        bot.answer_callback_query(call.id, "Not admin!", show_alert=True)
        return
    oid = call.data.split("|")[1]
    o = get_order_details(oid)
    if not o:
        bot.answer_callback_query(call.id, "❌ Order not found!", show_alert=True)
        return
    user_states[ADMIN_ID] = {
        "action": "delivering_code",
        "order_id": oid,
        "target_user": int(o.get("user_id")),
        "product": o.get("item_name"),
        "qty": o.get("qty"),
        "unit": o.get("unit"),
        "price": o.get("amount"),
        "package": o.get("package", "Standard"),
        "sent_msg_id": int(o.get("sent_msg_id", 0)),
    }
    bot.send_message(
        ADMIN_ID,
        f"📝 Order ID: #{oid}\nProduct: {o.get('item_name')} ({o.get('qty')} {o.get('unit')})\nUser ID: <code>{o.get('user_id')}</code>\n\nSend delivery details:",
    )


@bot.message_handler(
    func=lambda m: m.from_user.id == ADMIN_ID
    and user_states.get(ADMIN_ID, {}).get("action") == "delivering_code"
)
def send_product_to_user(message):
    d = user_states.pop(ADMIN_ID, {})
    oid = d.get("order_id")
    tgt = d.get("target_user")
    code = (message.text or "").strip()
    update_order_status(oid, "delivered")
    bal, _ = get_balance(tgt)
    if d.get("sent_msg_id"):
        try:
            bot.delete_message(tgt, d["sent_msg_id"])
        except Exception:
            pass
    qf = f"{d.get('qty')} Pc"
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("Reply to Admin", url=f"https://t.me/{ADMIN_USERNAME}"))
    try:
        bot.send_message(
            tgt,
            f"✅ <b>Purchase Successful!</b>\n\n📦 Order: #{oid}\n🏢 Provider: {d.get('product')}\n🔢 Quantity: {qf}\n💰 Balance: <b>${bal:.2f}</b>\n💸 Paid: {float(d.get('price', 0)):g} USDT\n\n🔑 <b>Your code / key(s) :</b>\n{code}",
            reply_markup=m,
        )
        bot.send_message(ADMIN_ID, f"✅ Order #{oid} delivered to <code>{tgt}</code>!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Failed: {e}")


# ---------- My Orders ----------
def my_orders_menu(message):
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("🛒 Order History", callback_data="history_orders"),
        InlineKeyboardButton("💳 Recharge History", callback_data="history_recharges"),
        InlineKeyboardButton("❌ Close", callback_data="close"),
    )
    bot.send_message(
        message.chat.id, "📦 <b>My Orders & History Menu</b>", reply_markup=m
    )


@bot.callback_query_handler(
    func=lambda c: c.data in ["history_orders", "history_recharges"]
)
def show_user_history(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id, text="Loading...")
    if call.data == "history_orders":
        data = fb_get("orders") or {}
        lst = [
            v
            for v in data.values()
            if isinstance(v, dict) and str(v.get("user_id")) == str(uid)
        ]
        if not lst:
            text = "🛒 <b>Order History:</b>\n\nNo order found."
        else:
            text = "🛒 <b>Your Order History (Last 5):</b>\n\n"
            for i, o in enumerate(
                sorted(lst, key=lambda x: x.get("order_id", 0), reverse=True)[:5],
                1,
            ):
                s = o.get("status", "pending")
                ic = (
                    "⏳ Pending"
                    if s == "pending"
                    else (
                        "✅ Delivered"
                        if s == "delivered"
                        else ("🔄 Refunded" if s == "refunded" else s)
                    )
                )
                text += f"<b>{i}. Order ID:</b> #{o.get('order_id')}\n📦 <b>Item:</b> {o.get('item_name')} ({o.get('qty')} {o.get('unit')})\n💰 <b>Amount:</b> {float(o.get('amount', 0)):g} USDT\n📌 <b>Status:</b> {ic}\n\n"
    else:
        data = fb_get("transactions") or {}
        lst = [
            v
            for v in data.values()
            if isinstance(v, dict) and str(v.get("user_id")) == str(uid)
        ]
        if not lst:
            text = "💳 <b>Recharge History:</b>\n\nNo recharge found."
        else:
            text = "💳 <b>Your Recharge History (Last 5):</b>\n\n"
            for i, t in enumerate(
                sorted(lst, key=lambda x: x.get("time", 0), reverse=True)[:5], 1
            ):
                s = t.get("status", "pending")
                ic = (
                    "⏳ Pending"
                    if s == "pending"
                    else (
                        "✅ Approved"
                        if s == "approved"
                        else ("❌ Rejected" if s == "rejected" else s)
                    )
                )
                text += f"<b>{i}. Method:</b> {t.get('method')}\n💰 <b>Amount:</b> {float(t.get('amount', 0)):g} USDT\n🔢 <b>TrxID:</b> <code>{t.get('trx_id')}</code>\n📌 <b>Status:</b> {ic}\n\n"
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_history_menu"))
    try:
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id, reply_markup=m
        )
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=m)


@bot.callback_query_handler(func=lambda c: c.data == "back_to_history_menu")
def back_to_history_main(call):
    m = InlineKeyboardMarkup(row_width=1)
    m.add(
        InlineKeyboardButton("🛒 Order History", callback_data="history_orders"),
        InlineKeyboardButton("💳 Recharge History", callback_data="history_recharges"),
        InlineKeyboardButton("❌ Close", callback_data="close"),
    )
    bot.edit_message_text(
        "📦 <b>My Orders & History Menu</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=m,
    )


# ---------- Global ----------
@bot.callback_query_handler(func=lambda c: c.data == "cancel_action")
def cancel_callback(call):
    cid = call.message.chat.id
    bot.clear_step_handler_by_chat_id(cid)
    trade_data.pop(cid, None)
    user_states.pop(call.from_user.id, None)
    try:
        bot.delete_message(cid, call.message.message_id)
    except Exception:
        pass
    bot.send_message(cid, "Operation cancelled.", reply_markup=get_main_menu(call))


@bot.callback_query_handler(func=lambda c: c.data == "back_to_cat")
def back_cat(call):
    bot.edit_message_text(
        "Select a category what you want to buy:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_categories_menu(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "close")
def close_msg(call):
    cid = call.message.chat.id
    bot.clear_step_handler_by_chat_id(cid)
    user_states.pop(call.from_user.id, None)
    trade_data.pop(cid, None)
    try:
        bot.delete_message(cid, call.message.message_id)
    except Exception:
        pass


if __name__ == "__main__":
    threading.Thread(target=run_fake_server, daemon=True).start()
    print("Loading products...")
    load_products()
    print("Setting commands...")
    set_bot_commands()
    print("Bot starting...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e:
            print(f"Polling: {e}. Reconnecting...")
            time.sleep(5)
