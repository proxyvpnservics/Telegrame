import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, jsonify, request
import requests
import telebot
from telebot.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --- CONFIG ---
API_TOKEN = os.getenv("BOT_TOKEN", "8695667841:AAGIRtc8JcqqL3ASJZOy8S-3Jk0Pjk1A-68")
ADMIN_ID = 6954924404
CHANNEL_USERNAME = "@all_country_sell"
FIREBASE_URL = "https://shopbotdb-default-rtdb.firebaseio.com/"

DOLLAR_CONFIG = {
    "binance_uid": "1076781671",
    "tron_address": "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8",
}

PANEL_PRICES = { "Panel 1": 1.0, "Panel 2": 1.2, "Panel 3": 2.1, "Panel 4": 1.5 }

PANEL_1_COUNTRIES = {
    "Colombia": 0.5, "India": 0.55, "Bangladesh": 0.55, "United States": 0.55,
    "Indonesia": 0.6, "Chile": 0.65, "Kenya": 0.65, "Myanmar": 0.65, "Angola": 0.68,
    "Afghanistan": 0.7, "Zimbabwe": 0.7, "Sudan": 0.7, "Cameroon": 0.7, "Madagascar": 0.7,
    "Tanzania": 0.6, "Algeria": 0.75, "Jamaica": 0.75, "Sri Lanka": 0.8, "Eswatini": 0.8, "Burkina Faso": 0.8,
}
PANEL_2_COUNTRIES = {
    "Myanmar": 0.35, "Colombia": 0.55, "Uganda": 0.55, "Togo": 0.55, "Sudan": 0.58,
    "Zimbabwe": 0.6, "Nigeria": 0.6, "Congo, The Democratic": 0.6, "Sierra Leone": 0.6,
    "Madagascar": 0.6, "Angola": 0.65, "Niger": 0.65, "Pakistan": 0.65, "Zambia": 0.65,
    "India": 0.65, "Chile": 0.65, "Afghanistan": 0.65, "Ghana": 0.65, "Cuba": 0.7, "Thailand": 0.7,
}
PANEL_3_COUNTRIES = { "Nigeria": 0.5 }

TRANSLATIONS = {
    "en": {
        "welcome": "🌸 Welcome <b>{name}</b>!\n\nPlease select from the menu below:",
        "join_req": "🌸 Welcome <b>{name}</b>!\n\n⚠️ Please join our channel first before using the bot!",
        "join_btn": "📢 Join Channel", "joined_btn": "Joined ✅", "joined_success": "Thank you! You have joined the channel.",
        "not_joined": "You haven't joined the channel yet! Please join first.",
        "menu_telegram": "📱 Telegram Buy Now", "menu_profile": "👤 Profile", "menu_deposit": "💰 Deposit",
        "menu_support": "☎️ Support", "menu_language": "🌐 Language", "select_lang": "🌐 Please select your language / 请选择您的语言:",
        "lang_changed": "✅ Language changed to English successfully!", "tg_main_prompt": "Select your panel from the section below:",
        "tg_all_panels": "🌍 Select your desired panel from the list:", "panel_select_country": "📁 <b>{panel}</b>\n\nSelect a country:",
        "back_to_panels": "🔙 Back to Panels", "stock_out": "❌ <b>Stock Out!</b>\n\nSorry, products for this panel/country are currently out of stock.",
        "insufficient_bal": "❌ <b>Insufficient Balance!</b>\n\nPrice: {price} USDT, but your balance is {balance:.2f} USDT. Please deposit below:",
        "ask_qty": "📁 Selected: <b>{panel}</b>\n📦 Available Stock: {stock} pcs\n💲 Price per piece: {price} USDT\n💰 Your Balance: {balance:.2f} USDT\n\nHow many pieces do you want to buy? Enter a number:",
        "purchase_success": "✅ <b>Purchase Successful!</b>\n\nBought {qty} pcs!\n💵 Deducted: {cost} USDT\n💎 New Balance: {new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>Your Products ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>Your Profile:</b>\n\n🆔 User ID: <code>{user_id}</code>\n📛 Name: {name}\n💰 Balance: {balance:.2f} USDT\n🛍️ Total Purchases: {total_buy}",
        "deposit_main": "💎 <b>Deposit System</b>\n\nSelect payment method:", "deposit_step1": "💎 <b>{method} Deposit</b>\n\nSend payment to:\n<code>{address}</code>\n\nStep 1: Enter amount of USDT you sent (e.g., 5):",
        "deposit_step2": "🧾 Now send your <b>Order ID / TrxID</b>:", "deposit_pending": "⏳ Deposit request sent to admin. Please wait.",
        "support_text": "☎️ <b>Support</b>\n\n💬 Official Support: <a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ Available: 24/7",
        "contact_admin": "🟢 Contact Support", "back": "🔙 Back", "invalid_num": "❌ Please enter a valid number.",
        "not_enough_stock": "❌ Not enough stock! Only {stock} pcs available.", "enter_valid_amount": "❌ Please enter valid amount.",
        "dep_success_user": "🎉 Deposit of {amount:.2f} USDT successful!\n💰 Balance: {balance:.2f} USDT", "dep_cancel_user": "❌ Deposit request cancelled."
    },
    "zh": {
        "welcome": "🌸 欢迎 <b>{name}</b>！\n\n请从下方菜单中选择：", "join_req": "🌸 欢迎 <b>{name}</b>！\n\n⚠️ 使用机器人之前，请先加入我们的频道！",
        "join_btn": "📢 加入频道", "joined_btn": "已加入 ✅", "joined_success": "谢谢！您已成功加入频道。",
        "not_joined": "您还没有加入频道！请先加入。", "menu_telegram": "📱 电报购买", "menu_profile": "👤 个人资料",
        "menu_deposit": "💰 充值", "menu_support": "☎️ 客服支持", "menu_language": "🌐 语言",
        "select_lang": "🌐 请选择您的语言 / Please select your language:", "lang_changed": "✅ 语言已成功更改为中文！",
        "tg_main_prompt": "请从下方选择您的面板：", "tg_all_panels": "🌍 从列表中选择您想要的面板：",
        "panel_select_country": "📁 <b>{panel}</b>\n\n选择一个国家/地区：", "back_to_panels": "🔙 返回面板",
        "stock_out": "❌ <b>缺货！</b>\n\n抱歉，此面板/国家的商品目前暂无库存。",
        "insufficient_bal": "❌ <b>余额不足！</b>\n\n价格：{price} USDT，但您的余额为 {balance:.2f} USDT。请在下方充值：",
        "ask_qty": "📁 已选：<b>{panel}</b>\n📦 可用库存：{stock} 件\n💲 单价：{price} USDT\n💰 您的余额：{balance:.2f} USDT\n\n您想购买多少件？请输入数字：",
        "purchase_success": "✅ <b>购买成功！</b>\n\n成功购买 {qty} 件！\n💵 扣除：{cost} USDT\n💎 新余额：{new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>您购买的商品 ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>您的个人资料：</b>\n\n🆔 用户 ID: <code>{user_id}</code>\n📛 姓名：{name}\n💰 余额：{balance:.2f} USDT\n🛍️ 总购买量：{total_buy}",
        "deposit_main": "💎 <b>充值系统</b>\n\n请从下方按钮中选择您要充值的支付方式：",
        "deposit_step1": "💎 <b>{method} 充值</b>\n\n请将款项发送至:\n地址 / ID: <code>{address}</code>\n\n第一步：输入您发送的 USDT 金额（仅限数字，例如 5 或 10）：",
        "deposit_step2": "🧾 现在请发送您的 <b>订单号 / 交易哈希 (TrxID)</b>：", "deposit_pending": "⏳ 您的充值请求已发送给管理员，请耐心等待。",
        "support_text": "☎️ <b>客户支持</b>\n\n💬 官方客服：<a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ 服务时间：24/7 全天候",
        "contact_admin": "🟢 联系客服", "back": "🔙 返回", "invalid_num": "❌ 请输入有效的数字。",
        "not_enough_stock": "❌ 库存不足！当前仅剩 {stock} 件库存。", "enter_valid_amount": "❌ 请输入有效的金额。",
        "dep_success_user": "🎉 您充值的 {amount:.2f} USDT 已成功到账！\n💰 当前余额：{balance:.2f} USDT", "dep_cancel_user": "❌ 您的充值请求已被取消。"
    }
}

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_states = {}

# --- DB ---
def init_local_db():
    conn = sqlite3.connect("auto_payments.db")
    conn.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, trx_id TEXT UNIQUE, amount REAL, sender TEXT, status TEXT DEFAULT 'unused')")
    conn.commit(); conn.close()
init_local_db()

@app.route("/webhook/payment", methods=["POST"])
def receive_payment():
    data = request.json
    if not data or not data.get("trx_id") or not data.get("amount"):
        return jsonify({"status": "error"}), 400
    try:
        conn = sqlite3.connect("auto_payments.db")
        conn.execute("INSERT INTO transactions (trx_id, amount, sender) VALUES (?, ?, ?)", (data["trx_id"].strip(), float(data["amount"]), data.get("sender","Personal")))
        conn.commit(); conn.close()
        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Duplicate TrxID"}), 400

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.send_header("Content-type","text/plain"); self.end_headers(); self.wfile.write(b"Bot Alive")
    def log_message(self, format, *args): return
def run_fake_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

# --- HELPERS ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['creator','administrator','member']
    except: return True # Channel না থাকলে বা error হলে True ধরে নিবে যাতে bot আটকে না থাকে

def get_user(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Unknown"
    username = message.from_user.username or "No_Username"
    try:
        url = f"{FIREBASE_URL}users/{user_id}.json"
        res = requests.get(url, timeout=10).json()
        if not res:
            new_user = {"user_id": user_id, "first_name": first_name, "username": username, "balance": 0.0, "total_buy": 0, "language": "en"}
            requests.put(url, json=new_user, timeout=10)
            return 0.0, 0, "en"
        return float(res.get("balance",0.0)), int(res.get("total_buy",0)), res.get("language","en")
    except: return 0.0, 0, "en"

def get_user_data_by_id(user_id):
    try:
        url = f"{FIREBASE_URL}users/{user_id}.json"
        res = requests.get(url, timeout=10).json()
        if not res: return 0.0, 0, "en"
        return float(res.get("balance",0.0)), int(res.get("total_buy",0)), res.get("language","en")
    except: return 0.0, 0, "en"

def update_user_language(user_id, lang):
    try: requests.put(f"{FIREBASE_URL}users/{user_id}/language.json", json=lang, timeout=10)
    except: pass
def update_balance(user_id, amount):
    try:
        cur,_,_ = get_user_data_by_id(user_id)
        new = cur + amount
        requests.put(f"{FIREBASE_URL}users/{user_id}/balance.json", json=new, timeout=10)
        return new
    except: return 0.0
def add_buy_count(user_id):
    try:
        _, cur, _ = get_user_data_by_id(user_id)
        requests.put(f"{FIREBASE_URL}users/{user_id}/total_buy.json", json=cur+1, timeout=10)
    except: pass

def get_stock(path_key):
    try:
        safe_key = path_key.replace(" ", "_").replace(",", "").replace(".", "")
        url = f"{FIREBASE_URL}stock/{safe_key}.json"
        data = requests.get(url, timeout=10).json()
        if isinstance(data, list): return [i for i in data if i]
        if isinstance(data, dict): return list(data.values())
        return []
    except: return []
def update_stock(path_key, remaining):
    try:
        safe_key = path_key.replace(" ", "_").replace(",", "").replace(".", "")
        requests.put(f"{FIREBASE_URL}stock/{safe_key}.json", json=remaining, timeout=10)
    except: pass

def get_main_menu(lang="en"):
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton(t["menu_telegram"]), KeyboardButton(t["menu_profile"]),
               KeyboardButton(t["menu_deposit"]), KeyboardButton(t["menu_support"]),
               KeyboardButton(t["menu_language"]))
    return markup

# FIXED: Panel menu এখন আর stock count এর জন্য Firebase call করবে না, তাই instant open হবে
def get_telegram_main_menu_fixed():
    markup = InlineKeyboardMarkup(row_width=2)
    for panel in ["Panel 1", "Panel 2", "Panel 3", "Panel 4"]:
        markup.add(InlineKeyboardButton(f"★ {panel}", callback_data=f"pnl_{panel.replace(' ', '_')}"))
    return markup

def get_deposit_main_markup():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🆔 【entity-Binance¦canonical_name=Binance】 UID", callback_data="dep_binance_uid"),
          InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
    return m

# --- HANDLERS ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    _,_,lang = get_user(message)
    user_states.pop(message.from_user.id, None)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    if not check_subscription(message.from_user.id):
        ch = InlineKeyboardMarkup()
        ch.add(InlineKeyboardButton(t["join_btn"], url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"))
        ch.add(InlineKeyboardButton(t["joined_btn"], callback_data="check_join"))
        bot.send_message(message.chat.id, t["join_req"].format(name=message.from_user.first_name), reply_markup=ch); return
    bot.send_message(message.chat.id, t["welcome"].format(name=message.from_user.first_name), reply_markup=get_main_menu(lang))

@bot.callback_query_handler(func=lambda c: c.data=="check_join")
def callback_check_join(call):
    _,_,lang = get_user_data_by_id(call.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, t["joined_success"])
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        bot.send_message(call.message.chat.id, t["welcome"].format(name=call.from_user.first_name), reply_markup=get_main_menu(lang))
    else: bot.answer_callback_query(call.id, t["not_joined"], show_alert=True)

@bot.message_handler(func=lambda m: m.text in ["🌐 Language", "🌐 语言"])
def language_menu_handler(message):
    _,_,lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇨🇳 Chinese", callback_data="lang_zh"))
    bot.send_message(message.chat.id, t["select_lang"], reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def language_callback_handler(call):
    lang = call.data.split("_")[1]
    update_user_language(call.from_user.id, lang)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.answer_callback_query(call.id, t["lang_changed"])
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_message(call.message.chat.id, t["welcome"].format(name=call.from_user.first_name), reply_markup=get_main_menu(lang), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in ["📱 Telegram Buy Now", "📱 电报购买"])
def telegram_button_handler(message):
    _,_,lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(message.chat.id, t["tg_main_prompt"], reply_markup=get_telegram_main_menu_fixed())

@bot.callback_query_handler(func=lambda c: c.data=="back_to_telegram")
def back_to_telegram(call):
    _,_,lang = get_user_data_by_id(call.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.edit_message_text(t["tg_all_panels"], call.message.chat.id, call.message.message_id, reply_markup=get_telegram_main_menu_fixed())

@bot.callback_query_handler(func=lambda c: c.data.startswith("pnl_") or c.data.startswith("cntry_"))
def dynamic_navigation_handler(call):
    user_id = call.from_user.id
    balance,_,lang = get_user_data_by_id(user_id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    if call.data.startswith("pnl_"):
        panel_name = call.data.split("_",1)[1].replace("_"," ")
        if panel_name in ["Panel 1","Panel 2","Panel 3"]:
            target_dict = PANEL_1_COUNTRIES if panel_name=="Panel 1" else PANEL_2_COUNTRIES if panel_name=="Panel 2" else PANEL_3_COUNTRIES
            mk = InlineKeyboardMarkup(row_width=2)
            for country in target_dict.keys():
                stock_count = len(get_stock(f"{panel_name}/{country}")) # এখন শুধু country menu তে count দেখাবে
                mk.add(InlineKeyboardButton(f"🌍 {country} [{stock_count}]", callback_data=f"cntry_{panel_name.split(' ')[1]}_{country.replace(' ','_')}"))
            mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
            bot.edit_message_text(t["panel_select_country"].format(panel=panel_name), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
            return
        else: # Panel 4 direct buy
            price = PANEL_PRICES.get(panel_name,1.5)
            stock = get_stock(panel_name)
            if not stock:
                mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
                bot.edit_message_text(t["stock_out"], call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML"); return
            if balance < price:
                mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
                mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
                bot.edit_message_text(t["insufficient_bal"].format(price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
            else:
                user_states[user_id] = {"action":"buy_item_quantity","panel":panel_name,"price":price}
                mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
                bot.edit_message_text(t["ask_qty"].format(panel=panel_name, stock=len(stock), price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")
    else: # Country buy
        parts = call.data.split("_",2)
        panel_num, slug = parts[1], parts[2]
        panel_name = f"Panel {panel_num}"
        target_dict = PANEL_1_COUNTRIES if panel_num=="1" else PANEL_2_COUNTRIES if panel_num=="2" else PANEL_3_COUNTRIES
        country_name = next((c for c in target_dict if c.replace(" ","_")==slug), None)
        if not country_name: return
        path_key = f"{panel_name}/{country_name}"
        price = target_dict.get(country_name,0.5)
        stock = get_stock(path_key)
        mk_back = InlineKeyboardMarkup(); mk_back.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"pnl_{panel_name.replace(' ','_')}"))
        if not stock:
            bot.edit_message_text(f"🌍 <b>{country_name}</b> ({panel_name})\n\n"+t["stock_out"], call.message.chat.id, call.message.message_id, reply_markup=mk_back, parse_mode="HTML"); return
        if balance < price:
            pay = InlineKeyboardMarkup(); pay.add(InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
            pay.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"pnl_{panel_name.replace(' ','_')}"))
            bot.edit_message_text(f"🌍 <b>{country_name}</b>\n💲 Price: {price} USDT\n\n"+t["insufficient_bal"].format(price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=pay, parse_mode="HTML")
        else:
            user_states[user_id] = {"action":"buy_item_quantity","panel":path_key,"price":price}
            bot.edit_message_text(t["ask_qty"].format(panel=f"{panel_name} / {country_name}", stock=len(stock), price=price, balance=balance), call.message.chat.id, call.message.message_id, reply_markup=mk_back, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("action")=="buy_item_quantity")
def process_buy_quantity(message):
    user_id = message.from_user.id
    _,_,lang = get_user_data_by_id(user_id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    state = user_states.get(user_id, {})
    try:
        qty = int(message.text)
        if qty<=0: raise ValueError
        stock_items = get_stock(state["panel"])
        if qty > len(stock_items): bot.send_message(message.chat.id, t["not_enough_stock"].format(stock=len(stock_items))); return
        total_cost = qty * state["price"]
        bal,_,_ = get_user_data_by_id(user_id)
        if bal < total_cost:
            mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"), InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron"))
            bot.send_message(message.chat.id, t["insufficient_bal"].format(price=total_cost, balance=bal), reply_markup=mk); user_states.pop(user_id,None); return
        purchased = stock_items[:qty]
        update_stock(state["panel"], stock_items[qty:])
        new_bal = bal - total_cost
        requests.put(f"{FIREBASE_URL}users/{user_id}/balance.json", json=new_bal, timeout=10)
        add_buy_count(user_id); user_states.pop(user_id,None)
        prod_text = "\n".join([f"<code>{item}</code>" for item in purchased])
        bot.send_message(message.chat.id, t["purchased_products"].format(panel=state["panel"], products=prod_text), parse_mode="HTML")
        bot.send_message(message.chat.id, t["purchase_success"].format(qty=qty, cost=total_cost, new_bal=new_bal), reply_markup=get_main_menu(lang))
    except ValueError: bot.send_message(message.chat.id, t["invalid_num"])

# --- DEPOSIT FIXED ---
@bot.message_handler(func=lambda m: m.text in ["💰 Deposit", "💰 充值"])
@bot.message_handler(commands=["deposit"])
def deposit_handler(message):
    _,_,lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(message.chat.id, t["deposit_main"], reply_markup=get_deposit_main_markup(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data=="back_to_deposit")
def back_to_deposit_menu(call):
    _,_,lang = get_user_data_by_id(call.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.edit_message_text(t["deposit_main"], call.message.chat.id, call.message.message_id, reply_markup=get_deposit_main_markup(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data in ["dep_binance_uid","dep_tron"])
def deposit_method_selected(call):
    _,_,lang = get_user_data_by_id(call.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    method_name, address = ("Binance UID", DOLLAR_CONFIG["binance_uid"]) if call.data=="dep_binance_uid" else ("Tron-TRC20", DOLLAR_CONFIG["tron_address"])
    user_states[call.from_user.id] = {"action":"deposit_amount","method":method_name}
    mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["back"], callback_data="back_to_deposit"))
    bot.edit_message_text(t["deposit_step1"].format(method=method_name, address=address), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="HTML")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("action")=="deposit_amount")
def get_deposit_amount(message):
    _,_,lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    try:
        amt = float(message.text.strip())
        if amt<=0: raise ValueError
        user_states[message.from_user.id]["amount"]=amt
        user_states[message.from_user.id]["action"]="deposit_order_id"
        bot.send_message(message.chat.id, t["deposit_step2"], parse_mode="HTML")
    except: bot.send_message(message.chat.id, t["enter_valid_amount"])

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id, {}).get("action")=="deposit_order_id")
def get_deposit_order_id(message):
    user_id = message.from_user.id
    _,_,lang = get_user_data_by_id(user_id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    state = user_states.pop(user_id, {})
    amount = state.get("amount",0.0); order_id = message.text.strip()
    bot.send_message(message.chat.id, t["deposit_pending"], reply_markup=get_main_menu(lang))
    admin_mk = InlineKeyboardMarkup()
    admin_mk.row(InlineKeyboardButton("✅ Approve", callback_data=f"depapprove|{user_id}|{amount:.2f}|{order_id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"depreject|{user_id}|{order_id}"))
    bot.send_message(ADMIN_ID, f"🔔 <b>New Deposit!</b>\n\n👤 User: {message.from_user.first_name} (<code>{user_id}</code>)\n💳 Method: {state.get('method')}\n💵 Amount: {amount:.2f} USDT\n🧾 TrxID: <code>{order_id}</code>", reply_markup=admin_mk, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("depapprove|") or c.data.startswith("depreject|"))
def admin_deposit_action(call):
    parts = call.data.split("|")
    target_id = int(parts[1])
    _,_,tlang = get_user_data_by_id(target_id)
    tt = TRANSLATIONS.get(tlang, TRANSLATIONS["en"])
    if parts[0]=="depapprove":
        amount = float(parts[2]); order_id = parts[3]
        new_bal = update_balance(target_id, amount)
        bot.edit_message_text(f"✅ Approved {amount:.2f} USDT for {target_id} | Trx: {order_id}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(target_id, tt["dep_success_user"].format(amount=amount, balance=new_bal))
        except: pass
    else:
        order_id = parts[2]
        bot.edit_message_text(f"❌ Rejected for {target_id} | Trx: {order_id}", call.message.chat.id, call.message.message_id)
        try: bot.send_message(target_id, tt["dep_cancel_user"])
        except: pass

# --- OTHER COMMANDS ---
@bot.message_handler(commands=["addstock"])
def add_stock_handler(message):
    if message.from_user.id != ADMIN_ID: bot.reply_to(message, "❌ No permission"); return
    try:
        _, content = message.text.split(maxsplit=1)
        if "|" not in content: bot.reply_to(message, "Use: /addstock Panel 1/India | item1\nitem2"); return
        target_path, products_raw = content.split("|",1)
        new_products = [p.strip() for p in products_raw.split("\n") if p.strip()]
        stock_list = get_stock(target_path.strip()); stock_list.extend(new_products)
        update_stock(target_path.strip(), stock_list)
        bot.reply_to(message, f"✅ Added {len(new_products)} items to {target_path.strip()}")
    except Exception as e: bot.reply_to(message, f"Error: {e}")

@bot.message_handler(func=lambda m: m.text in ["👤 Profile", "👤 个人资料"])
@bot.message_handler(commands=["profile"])
def profile_handler(message):
    bal, total, lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    bot.send_message(message.chat.id, t["profile_text"].format(user_id=message.from_user.id, name=message.from_user.first_name, balance=bal, total_buy=total), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in ["☎️ Support", "☎️ 客服支持"])
@bot.message_handler(commands=["support"])
def support_handler(message):
    _,_,lang = get_user_data_by_id(message.from_user.id)
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mk = InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(t["contact_admin"], url="https://t.me/GV_gmail_07"))
    bot.send_message(message.chat.id, t["support_text"], reply_markup=mk, parse_mode="HTML")

if __name__=="__main__":
    threading.Thread(target=run_fake_server, daemon=True).start()
    print("Bot starting...")
    try: bot.remove_webhook(); time.sleep(1)
    except: pass
    bot.set_my_commands([BotCommand("start","Re-start Bot")])
    while True:
        try: bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e: print(f"Polling error: {e}"); time.sleep(5)
