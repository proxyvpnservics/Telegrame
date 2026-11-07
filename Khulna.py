import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, jsonify, request
import requests
import telebot
from telebot.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

API_TOKEN = os.getenv("BOT_TOKEN", "8695667841:AAGIRtc8JcqqL3ASJZOy8S-3Jk0Pjk1A-68")
ADMIN_ID = 6954924404
CHANNEL_USERNAME = "@all_country_sell"
FIREBASE_URL = "https://shopbotdb-default-rtdb.firebaseio.com/"

DOLLAR_CONFIG = {"binance_uid": "1076781671", "tron_address": "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8"}
PANEL_PRICES = {"Panel 1": 1.0, "Panel 2": 1.2, "Panel 3": 2.1, "Panel 4": 1.5}

PANEL_1_COUNTRIES = {"Colombia": 0.5, "India": 0.55, "Bangladesh": 0.55, "United States": 0.55, "Indonesia": 0.6, "Chile": 0.65, "Kenya": 0.65, "Myanmar": 0.65, "Angola": 0.68, "Afghanistan": 0.7, "Zimbabwe": 0.7, "Sudan": 0.7, "Cameroon": 0.7, "Madagascar": 0.7, "Tanzania": 0.6, "Algeria": 0.75, "Jamaica": 0.75, "Sri Lanka": 0.8, "Eswatini": 0.8, "Burkina Faso": 0.8}
PANEL_2_COUNTRIES = {"Myanmar": 0.35, "Colombia": 0.55, "Uganda": 0.55, "Togo": 0.55, "Sudan": 0.58, "Zimbabwe": 0.6, "Nigeria": 0.6, "Congo, The Democratic": 0.6, "Sierra Leone": 0.6, "Madagascar": 0.6, "Angola": 0.65, "Niger": 0.65, "Pakistan": 0.65, "Zambia": 0.65, "India": 0.65, "Chile": 0.65, "Afghanistan": 0.65, "Ghana": 0.65, "Cuba": 0.7, "Thailand": 0.7}
PANEL_3_COUNTRIES = {"Nigeria": 0.5}

# Panel -> Country List Map (Index দিয়ে কাজ করবো, নাম দিয়ে না)
PANEL_MAP = {"1": PANEL_1_COUNTRIES, "2": PANEL_2_COUNTRIES, "3": PANEL_3_COUNTRIES}

TRANSLATIONS = {
    "en": {
        "welcome": "🌸 Welcome <b>{name}</b>!\n\nPlease select from the menu below:",
        "join_req": "🌸 Welcome <b>{name}</b>!\n\n⚠️ Please join our channel first!",
        "join_btn": "📢 Join Channel", "joined_btn": "Joined ✅", "joined_success": "Thank you! You have joined.",
        "not_joined": "You haven't joined yet!", "menu_telegram": "📱 Telegram Buy Now", "menu_profile": "👤 Profile",
        "menu_deposit": "💰 Deposit", "menu_support": "☎️ Support", "menu_language": "🌐 Language",
        "select_lang": "🌐 Please select your language:", "lang_changed": "✅ Language changed to English!",
        "tg_main_prompt": "Select your panel:", "tg_all_panels": "🌍 Select your desired panel:",
        "panel_select_country": "📁 <b>{panel}</b>\n\nSelect a country:", "back_to_panels": "🔙 Back to Panels",
        "stock_out": "❌ <b>Stock Out!</b>\n\nSorry, out of stock.", "insufficient_bal": "❌ <b>Insufficient Balance!</b>\n\nPrice: {price} USDT, Balance: {balance:.2f} USDT. Please deposit:",
        "ask_qty": "📁 Selected: <b>{panel}</b>\n📦 Stock: {stock} pcs\n💲 Price: {price} USDT\n💰 Balance: {balance:.2f} USDT\n\nHow many pieces? Enter number:",
        "purchase_success": "✅ <b>Purchase Successful!</b>\nBought {qty} pcs!\n💵 Deducted: {cost} USDT\n💎 New Balance: {new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>Your Products ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>Profile:</b>\n\n🆔 ID: <code>{user_id}</code>\n📛 Name: {name}\n💰 Balance: {balance:.2f} USDT\n🛍️ Total Buys: {total_buy}",
        "deposit_main": "💎 <b>Deposit System</b>\n\nSelect method:", "deposit_step1": "💎 <b>{method} Deposit</b>\n\nSend to:\n<code>{address}</code>\n\nEnter amount you sent (e.g., 5):",
        "deposit_step2": "🧾 Now send your <b>Order ID / TrxID</b>:", "deposit_pending": "⏳ Deposit request sent to admin.",
        "support_text": "☎️ <b>Support</b>\n\n💬 <a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ 24/7",
        "contact_admin": "🟢 Contact Support", "back": "🔙 Back", "invalid_num": "❌ Enter valid number.",
        "not_enough_stock": "❌ Only {stock} pcs available.", "enter_valid_amount": "❌ Enter valid amount.",
        "dep_success_user": "🎉 Deposit {amount:.2f} USDT successful!\n💰 Balance: {balance:.2f} USDT", "dep_cancel_user": "❌ Deposit cancelled."
    },
    "zh": {
        "welcome": "🌸 欢迎 <b>{name}</b>！\n\n请从下方菜单中选择：", "join_req": "🌸 欢迎 <b>{name}</b>！\n\n⚠️ 请先加入我们的频道！",
        "join_btn": "📢 加入频道", "joined_btn": "已加入 ✅", "joined_success": "谢谢！您已成功加入。",
        "not_joined": "您还没有加入频道！", "menu_telegram": "📱 电报购买", "menu_profile": "👤 个人资料",
        "menu_deposit": "💰 充值", "menu_support": "☎️ 客服支持", "menu_language": "🌐 语言",
        "select_lang": "🌐 请选择您的语言:", "lang_changed": "✅ 语言已更改为中文！",
        "tg_main_prompt": "请从下方选择您的面板：", "tg_all_panels": "🌍 选择您想要的面板：",
        "panel_select_country": "📁 <b>{panel}</b>\n\n选择一个国家：", "back_to_panels": "🔙 返回面板",
        "stock_out": "❌ <b>缺货！</b>", "insufficient_bal": "❌ <b>余额不足！</b>\n\n价格：{price} USDT，余额：{balance:.2f} USDT",
        "ask_qty": "📁 已选：<b>{panel}</b>\n📦 库存：{stock} 件\n💲 单价：{price} USDT\n💰 余额：{balance:.2f} USDT\n\n请输入购买数量：",
        "purchase_success": "✅ <b>购买成功！</b>\n购买 {qty} 件！\n💵 扣除：{cost} USDT\n💎 新余额：{new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>您购买的商品 ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>您的个人资料：</b>\n\n🆔 ID: <code>{user_id}</code>\n📛 姓名：{name}\n💰 余额：{balance:.2f} USDT\n🛍️ 总购买：{total_buy}",
        "deposit_main": "💎 <b>充值系统</b>\n\n请选择支付方式：", "deposit_step1": "💎 <b>{method} 充值</b>\n\n发送至:\n<code>{address}</code>\n\n输入您发送的金额：",
        "deposit_step2": "🧾 请发送您的 <b>订单号 / TrxID</b>：", "deposit_pending": "⏳ 充值请求已发送给管理员。",
        "support_text": "☎️ <b>客户支持</b>\n\n💬 <a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ 24/7",
        "contact_admin": "🟢 联系客服", "back": "🔙 返回", "invalid_num": "❌ 请输入有效的数字。",
        "not_enough_stock": "❌ 库存不足！仅剩 {stock} 件。", "enter_valid_amount": "❌ 请输入有效的金额。",
        "dep_success_user": "🎉 充值 {amount:.2f} USDT 成功！\n💰 余额：{balance:.2f} USDT", "dep_cancel_user": "❌ 充值请求已被取消。"
    }
}

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_states = {}

# ---- STOCK CACHE: পুরো stock একবারে আনবো ----
_stock_cache = {"data": {}, "time": 0}
def get_all_stock():
    now = time.time()
    if now - _stock_cache["time"] < 5 and _stock_cache["data"]:
        return _stock_cache["data"]
    try:
        data = requests.get(f"{FIREBASE_URL}stock.json", timeout=10).json() or {}
        _stock_cache["data"] = data
        _stock_cache["time"] = now
        return data
    except:
        return _stock_cache["data"]

def safe_key(path_key):
    return path_key.replace(" ", "_").replace(",", "").replace(".", "")

def get_stock(path_key):
    all_stock = get_all_stock()
    data = all_stock.get(safe_key(path_key))
    if isinstance(data, list): return [i for i in data if i]
    if isinstance(data, dict): return list(data.values())
    return []

def update_stock(path_key, remaining):
    try:
        requests.put(f"{FIREBASE_URL}stock/{safe_key(path_key)}.json", json=remaining, timeout=10)
        _stock_cache["time"] = 0  # cache clear
    except: pass

def init_local_db():
    conn = sqlite3.connect("auto_payments.db")
    conn.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, trx_id TEXT UNIQUE, amount REAL, sender TEXT, status TEXT DEFAULT 'unused')")
    conn.commit(); conn.close()
init_local_db()

@app.route("/webhook/payment", methods=["POST"])
def receive_payment():
    data = request.json
    if not data or not data.get("trx_id") or not data.get("amount"): return jsonify({"status":"error"}),400
    try:
        conn = sqlite3.connect("auto_payments.db")
        conn.execute("INSERT INTO transactions (trx_id, amount, sender) VALUES (?,?,?)", (data["trx_id"].strip(), float(data["amount"]), data.get("sender","Personal")))
        conn.commit(); conn.close(); return jsonify({"status":"success"})
    except sqlite3.IntegrityError: return jsonify({"status":"error","message":"Duplicate"}),400

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Bot Alive")
    def log_message(self, format, *args): return
def run_fake_server():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT",8080))), HealthCheckHandler).serve_forever()

def check_subscription(uid):
    try:
        m = bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ['creator','administrator','member']
    except: return True

def get_user_data_by_id(uid):
    try:
        d = requests.get(f"{FIREBASE_URL}users/{uid}.json", timeout=10).json()
        if not d: return 0.0,0,"en"
        return float(d.get("balance",0.0)), int(d.get("total_buy",0)), d.get("language","en")
    except: return 0.0,0,"en"

def get_user(msg):
    uid=msg.from_user.id
    try:
        url=f"{FIREBASE_URL}users/{uid}.json"
        d=requests.get(url, timeout=10).json()
        if not d:
            requests.put(url, json={"user_id":uid,"first_name":msg.from_user.first_name or "Unknown","username":msg.from_user.username or "No_Username","balance":0.0,"total_buy":0,"language":"en"}, timeout=10)
            return 0.0,0,"en"
        return float(d.get("balance",0.0)), int(d.get("total_buy",0)), d.get("language","en")
    except: return 0.0,0,"en"

def update_balance(uid, amt):
    cur,_,_=get_user_data_by_id(uid); new=cur+amt
    requests.put(f"{FIREBASE_URL}users/{uid}/balance.json", json=new, timeout=10); return new
def add_buy_count(uid):
    _,cur,_=get_user_data_by_id(uid); requests.put(f"{FIREBASE_URL}users/{uid}/total_buy.json", json=cur+1, timeout=10)

def get_main_menu(lang="en"):
    t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mk=ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(KeyboardButton(t["menu_telegram"]), KeyboardButton(t["menu_profile"]), KeyboardButton(t["menu_deposit"]), KeyboardButton(t["menu_support"]), KeyboardButton(t["menu_language"]))
    return mk

def get_panel_menu():
    mk=InlineKeyboardMarkup(row_width=2)
    mk.add(InlineKeyboardButton("★ Panel 1", callback_data="p1"),
           InlineKeyboardButton("★ Panel 2", callback_data="p2"),
           InlineKeyboardButton("★ Panel 3", callback_data="p3"),
           InlineKeyboardButton("★ Panel 4", callback_data="p4"))
    return mk

def get_deposit_markup():
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🆔 【entity-Binance¦canonical_name=Binance】 UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")); return mk

# ---------- START / JOIN ----------
@bot.message_handler(commands=["start"])
def send_welcome(message):
    _,_,lang=get_user(message); user_states.pop(message.from_user.id, None)
    t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    if not check_subscription(message.from_user.id):
        ch=InlineKeyboardMarkup(); ch.add(InlineKeyboardButton(t["join_btn"], url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")); ch.add(InlineKeyboardButton(t["joined_btn"], callback_data="check_join"))
        bot.send_message(message.chat.id, t["join_req"].format(name=message.from_user.first_name), reply_markup=ch); return
    bot.send_message(message.chat.id, t["welcome"].format(name=message.from_user.first_name), reply_markup=get_main_menu(lang))

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def check_join_cb(call):
    bot.answer_callback_query(call.id)
    _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    if check_subscription(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.send_message(call.message.chat.id, t["welcome"].format(name=call.from_user.first_name), reply_markup=get_main_menu(lang))
    else: bot.answer_callback_query(call.id, t["not_joined"], show_alert=True)

@bot.message_handler(func=lambda m: m.text in ["🌐 Language","🌐 语言"])
def lang_menu(m):
    _,_,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇨🇳 Chinese", callback_data="lang_zh"))
    bot.send_message(m.chat.id, t["select_lang"], reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def lang_cb(call):
    bot.answer_callback_query(call.id)
    lang=call.data.split("_")[1]
    requests.put(f"{FIREBASE_URL}users/{call.from_user.id}/language.json", json=lang, timeout=10)
    t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_message(call.message.chat.id, t["welcome"].format(name=call.from_user.first_name), reply_markup=get_main_menu(lang))

# ---------- TELEGRAM BUY NOW - FIXED PANEL SYSTEM ----------
@bot.message_handler(func=lambda m: m.text in ["📱 Telegram Buy Now","📱 电报购买"])
def telegram_btn(m):
    _,_,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(m.chat.id, t["tg_main_prompt"], reply_markup=get_panel_menu())

@bot.callback_query_handler(func=lambda c: c.data=="back_panels")
def back_panels(call):
    bot.answer_callback_query(call.id)
    _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    try: bot.edit_message_text(t["tg_all_panels"], call.message.chat.id, call.message.message_id, reply_markup=get_panel_menu())
    except: pass

# Panel Click: p1, p2, p3, p4
@bot.callback_query_handler(func=lambda c: c.data in ["p1","p2","p3","p4"])
def panel_click(call):
    bot.answer_callback_query(call.id)  # Loading বন্ধ করার জন্য মাস্ট
    panel_num = call.data[1]  # "1"
    panel_name = f"Panel {panel_num}"
    _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    balance,_,_=get_user_data_by_id(call.from_user.id)

    # Panel 1,2,3 -> Country List
    if panel_num in PANEL_MAP:
        countries = list(PANEL_MAP[panel_num].keys())
        mk=InlineKeyboardMarkup(row_width=2)
        # Cache থেকে stock নেওয়া হচ্ছে, তাই fast
        for idx, country in enumerate(countries):
            cnt = len(get_stock(f"{panel_name}/{country}"))
            mk.add(InlineKeyboardButton(f"🌍 {country} [{cnt}]", callback_data=f"c{panel_num}:{idx}"))
        mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_panels"))
        try:
            bot.edit_message_text(t["panel_select_country"].format(panel=panel_name), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
        except Exception as e: print("Panel edit error:", e)
        return

    # Panel 4 -> Direct Buy (No Country)
    price = PANEL_PRICES[panel_name]
    stock = get_stock(panel_name)
    if not stock:
        mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_panels"))
        bot.edit_message_text(t["stock_out"], call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML"); return
    if balance < price:
        mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🆔 【entity-Binance¦canonical_name=Binance】 UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
        mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_panels"))
        bot.edit_message_text(t["insufficient_bal"].format(price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
    else:
        user_states[call.from_user.id]={"action":"buy_item_quantity","panel":panel_name,"price":price}
        mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_panels"))
        bot.edit_message_text(t["ask_qty"].format(panel=panel_name, stock=len(stock), price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")

# Country Click: c1:0 , c2:5  (Panel:Index)
@bot.callback_query_handler(func=lambda c: c.data.startswith("c") and ":" in c.data and c.data[1].isdigit())
def country_click(call):
    bot.answer_callback_query(call.id)
    try:
        panel_num = call.data[1]
        idx = int(call.data.split(":")[1])
        panel_name = f"Panel {panel_num}"
        countries = list(PANEL_MAP[panel_num].keys())
        country_name = countries[idx]
        price = PANEL_MAP[panel_num][country_name]
    except:
        return
    _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    balance,_,_=get_user_data_by_id(call.from_user.id)
    path_key = f"{panel_name}/{country_name}"
    stock = get_stock(path_key)
    mk_back=InlineKeyboardMarkup(); mk_back.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"p{panel_num}"))
    if not stock:
        bot.edit_message_text(f"🌍 <b>{country_name}</b> ({panel_name})\n\n"+t["stock_out"], call.message.chat.id, call.message.message_id, reply_markup=mk_back, parse_mode="HTML"); return
    if balance < price:
        pay=InlineKeyboardMarkup(); pay.add(InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
        pay.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"p{panel_num}"))
        bot.edit_message_text(f"🌍 <b>{country_name}</b>\n💲 Price: {price} USDT\n\n"+t["insufficient_bal"].format(price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=pay, parse_mode="HTML")
    else:
        user_states[call.from_user.id]={"action":"buy_item_quantity","panel":path_key,"price":price}
        bot.edit_message_text(t["ask_qty"].format(panel=f"{panel_name} / {country_name}", stock=len(stock), price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk_back, parse_mode="HTML")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("action")=="buy_item_quantity")
def process_buy(m):
    uid=m.from_user.id; _,_,lang=get_user_data_by_id(uid); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    state=user_states.get(uid, {})
    try:
        qty=int(m.text.strip())
        if qty<=0: raise ValueError
        stock=get_stock(state["panel"])
        if qty>len(stock): bot.send_message(m.chat.id, t["not_enough_stock"].format(stock=len(stock))); return
        total=qty*state["price"]; bal,_,_=get_user_data_by_id(uid)
        if bal<total:
            mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🆔 【entity-Binance¦canonical_name=Binance】 UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
            bot.send_message(m.chat.id, t["insufficient_bal"].format(price=total, balance=bal), reply_markup=mk); user_states.pop(uid,None); return
        purchased=stock[:qty]; update_stock(state["panel"], stock[qty:])
        new_bal=bal-total
        requests.put(f"{FIREBASE_URL}users/{uid}/balance.json", json=new_bal, timeout=10); add_buy_count(uid); user_states.pop(uid,None)
        prod="\n".join([f"<code>{x}</code>" for x in purchased])
        bot.send_message(m.chat.id, t["purchased_products"].format(panel=state["panel"], products=prod), parse_mode="HTML")
        bot.send_message(m.chat.id, t["purchase_success"].format(qty=qty, cost=total, new_bal=new_bal), reply_markup=get_main_menu(lang))
    except: bot.send_message(m.chat.id, t["invalid_num"])

# ---------- DEPOSIT ----------
@bot.message_handler(func=lambda m: m.text in ["💰 Deposit","💰 充值"])
@bot.message_handler(commands=["deposit"])
def deposit_h(m):
    _,_,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(m.chat.id, t["deposit_main"], reply_markup=get_deposit_markup(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data=="back_to_deposit")
def back_dep(call):
    bot.answer_callback_query(call.id); _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.edit_message_text(t["deposit_main"], call.message.chat.id, call.message.message_id, reply_markup=get_deposit_markup(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data in ["dep_binance_uid","dep_tron"])
def dep_method(call):
    bot.answer_callback_query(call.id); _,_,lang=get_user_data_by_id(call.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    method, addr = ("【entity-Binance¦canonical_name=Binance】 UID", DOLLAR_CONFIG["binance_uid"]) if call.data=="dep_binance_uid" else ("Tron-TRC20", DOLLAR_CONFIG["tron_address"])
    user_states[call.from_user.id]={"action":"deposit_amount","method":method}
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back"], callback_data="back_to_deposit"))
    bot.edit_message_text(t["deposit_step1"].format(method=method, address=addr), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("action")=="deposit_amount")
def dep_amt(m):
    _,_,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    try:
        amt=float(m.text.strip())
        if amt<=0: raise ValueError
        user_states[m.from_user.id]["amount"]=amt; user_states[m.from_user.id]["action"]="deposit_order_id"
        bot.send_message(m.chat.id, t["deposit_step2"], parse_mode="HTML")
    except: bot.send_message(m.chat.id, t["enter_valid_amount"])

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("action")=="deposit_order_id")
def dep_oid(m):
    uid=m.from_user.id; _,_,lang=get_user_data_by_id(uid); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    st=user_states.pop(uid, {}); amt=st.get("amount",0.0); oid=m.text.strip()
    bot.send_message(m.chat.id, t["deposit_pending"], reply_markup=get_main_menu(lang))
    mk=InlineKeyboardMarkup(); mk.row(InlineKeyboardButton("✅ Approve", callback_data=f"depapprove|{uid}|{amt:.2f}|{oid}"), InlineKeyboardButton("❌ Reject", callback_data=f"depreject|{uid}|{oid}"))
    bot.send_message(ADMIN_ID, f"🔔 <b>New Deposit!</b>\n\n👤 {m.from_user.first_name} (<code>{uid}</code>)\n💳 {st.get('method')}\n💵 {amt:.2f} USDT\n🧾 <code>{oid}</code>", reply_markup=mk, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("depapprove|") or c.data.startswith("depreject|"))
def dep_admin(call):
    bot.answer_callback_query(call.id)
    p=call.data.split("|"); tid=int(p[1]); _,_,tl=get_user_data_by_id(tid); tt=TRANSLATIONS.get(tl, TRANSLATIONS["en"])
    if p[0]=="depapprove":
        amt=float(p[2]); oid=p[3]; nb=update_balance(tid, amt)
        bot.edit_message_text(f"✅ Approved {amt:.2f} for {tid} | {oid}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tid, tt["dep_success_user"].format(amount=amt, balance=nb))
        except: pass
    else:
        bot.edit_message_text(f"❌ Rejected {tid} | {p[2]}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(tid, tt["dep_cancel_user"])
        except: pass

# ---------- ADMIN / PROFILE / SUPPORT ----------
@bot.message_handler(commands=["addstock"])
def addstock(m):
    if m.from_user.id!=ADMIN_ID: bot.reply_to(m, "❌ No permission"); return
    try:
        _,content=m.text.split(maxsplit=1); tp, raw = content.split("|",1)
        new=[x.strip() for x in raw.split("\n") if x.strip()]
        sl=get_stock(tp.strip()); sl.extend(new); update_stock(tp.strip(), sl)
        bot.reply_to(m, f"✅ Added {len(new)} to {tp.strip()} | Total now: {len(sl)}")
    except Exception as e: bot.reply_to(m, f"Error: {e}")

@bot.message_handler(func=lambda m: m.text in ["👤 Profile","👤 个人资料"])
@bot.message_handler(commands=["profile"])
def profile(m):
    bal,tot,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(m.chat.id, t["profile_text"].format(user_id=m.from_user.id, name=m.from_user.first_name, balance=bal, total_buy=tot), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in ["☎️ Support","☎️ 客服支持"])
@bot.message_handler(commands=["support"])
def support(m):
    _,_,lang=get_user_data_by_id(m.from_user.id); t=TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["contact_admin"], url="https://t.me/GV_gmail_07"))
    bot.send_message(m.chat.id, t["support_text"], reply_markup=mk, parse_mode="HTML")

if __name__=="__main__":
    threading.Thread(target=run_fake_server, daemon=True).start()
    print("Bot starting...")
    try: bot.remove_webhook(); time.sleep(1)
    except: pass
    bot.set_my_commands([BotCommand("start","Re-start Bot")])
    while True:
        try: bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e: print("Polling error:", e); time.sleep(5)
