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

# Bot Token & Admin ID
API_TOKEN = os.getenv("BOT_TOKEN", "8695667841:AAGIRtc8JcqqL3ASJZOy8S-3Jk0Pjk1A-68")
ADMIN_ID = 6954924404

# Force Subscribe Channel Username
CHANNEL_USERNAME = "@all_country_sell"

# Firebase Realtime Database URL
FIREBASE_URL = "https://shopbotdb-default-rtdb.firebaseio.com/"

DOLLAR_CONFIG = {
    "binance_uid": "1076781671",
    "tron_address": "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8",
}

# Panel Prices (in USDT)
PANEL_PRICES = {
    "Panel 1": 1.0,
    "Panel 2": 1.2,
    "Panel 3": 2.1,
    "Panel 4": 1.5,
}

# Panel 1 Country Prices
PANEL_1_COUNTRIES = {
    "Colombia": 0.5,
    "India": 0.55,
    "Bangladesh": 0.55,
    "United States": 0.55,
    "Indonesia": 0.6,
    "Chile": 0.65,
    "Kenya": 0.65,
    "Myanmar": 0.65,
    "Angola": 0.68,
    "Afghanistan": 0.7,
    "Zimbabwe": 0.7,
    "Sudan": 0.7,
    "Cameroon": 0.7,
    "Madagascar": 0.7,
    "Tanzania": 0.6,
    "Algeria": 0.75,
    "Jamaica": 0.75,
    "Sri Lanka": 0.8,
    "Eswatini": 0.8,
    "Burkina Faso": 0.8,
}

# Panel 2 Country Prices
PANEL_2_COUNTRIES = {
    "Myanmar": 0.35,
    "Colombia": 0.55,
    "Uganda": 0.55,
    "Togo": 0.55,
    "Sudan": 0.58,
    "Zimbabwe": 0.6,
    "Nigeria": 0.6,
    "Congo, The Democratic": 0.6,
    "Sierra Leone": 0.6,
    "Madagascar": 0.6,
    "Angola": 0.65,
    "Niger": 0.65,
    "Pakistan": 0.65,
    "Zambia": 0.65,
    "India": 0.65,
    "Chile": 0.65,
    "Afghanistan": 0.65,
    "Ghana": 0.65,
    "Cuba": 0.7,
    "Thailand": 0.7,
}

# Panel 3 Country Prices
PANEL_3_COUNTRIES = {
    "Nigeria": 0.5,
}

# Full Bilingual Translations Dictionary
TRANSLATIONS = {
    "en": {
        "welcome": "🌸 Welcome <b>{name}</b>!\n\nPlease select from the menu below:",
        "join_req": "🌸 Welcome <b>{name}</b>!\n\n⚠️ Please join our channel first before using the bot!",
        "join_btn": "📢 Join Channel",
        "joined_btn": "Joined ✅",
        "joined_success": "Thank you! You have joined the channel.",
        "not_joined": "You haven't joined the channel yet! Please join first.",
        "menu_telegram": "📱 Telegram Buy Now",
        "menu_profile": "👤 Profile",
        "menu_deposit": "💰 Deposit",
        "menu_refer": "🔗 Refer",
        "menu_support": "☎️ Support",
        "menu_language": "🌐 Language",
        "select_lang": "🌐 Please select your language / 请选择您的语言:",
        "lang_changed": "✅ Language changed to English successfully!",
        "tg_main_prompt": "Select your panel from the section below:",
        "tg_all_panels": "🌍 Select your desired panel from the list:",
        "panel_select_country": "📁 <b>{panel}</b>\n\nSelect a country:",
        "back_to_panels": "🔙 Back to Panels",
        "stock_out": "❌ <b>Stock Out!</b>\n\nSorry, products for this panel/country are currently out of stock.",
        "insufficient_bal": "❌ <b>Insufficient Balance!</b>\n\nPrice: {price} USDT, but your balance is {balance:.2f} USDT. Please deposit below:",
        "ask_qty": "📁 Selected Panel/Country: <b>{panel}</b>\n📦 Available Stock: {stock} pcs\n💲 Price per piece: {price} USDT\n💰 Your Balance: {balance:.2f} USDT\n\nHow many pieces do you want to buy? Enter a number:",
        "purchase_success": "✅ <b>Purchase Successful!</b>\n\nSuccessfully bought {qty} pcs!\n💵 Deducted: {cost} USDT\n💎 New Balance: {new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>Your Purchased Products ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>Your Profile Information:</b>\n\n🆔 User ID: <code>{user_id}</code>\n📛 Name: {name}\n💰 Balance: {balance:.2f} USDT\n🛍️ Total Purchases: {total_buy}",
        "deposit_main": "💎 <b>Deposit System</b>\n\nSelect the payment method you want to deposit with from the buttons below:",
        "deposit_step1": "💎 <b>{method} Deposit</b>\n\nSend payment to:\nAddress / ID: <code>{address}</code>\n\nStep 1: Enter the amount of USDT you sent (numbers only, e.g., 5 or 10):",
        "deposit_step2": "🧾 Now please send your <b>Order ID / Transaction ID (TrxID)</b>:",
        "deposit_pending": "⏳ Your deposit request has been sent to the admin. Please wait.",
        "refer_text": "🔗 <b>Referral Program</b>\n\nInvite your friends to our bot using your personal referral link below and grow your network!\n\n🔗 Your Referral Link:\n<code>{link}</code>",
        "support_text": "☎️ <b>Customer Support & Assistance</b>\n\nNeed help with anything? Feel free to reach out to our support team anytime for assistance.\n\n💬 Official Support: <a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ Available: 24/7 Hours",
        "contact_admin": "🟢 Contact Support",
        "back": "🔙 Back",
        "invalid_num": "❌ Please enter a valid number.",
        "not_enough_stock": "❌ Not enough stock available! Currently only {stock} pcs are in stock.",
        "enter_valid_amount": "❌ Please enter a valid amount.",
        "dep_success_user": "🎉 Your deposit of {amount:.2f} USDT is successful!\n💰 Current Balance: {balance:.2f} USDT",
        "dep_cancel_user": "❌ Your deposit request has been cancelled."
    },
    "zh": {
        "welcome": "🌸 欢迎 <b>{name}</b>！\n\n请从下方菜单中选择：",
        "join_req": "🌸 欢迎 <b>{name}</b>！\n\n⚠️ 使用机器人之前，请先加入我们的频道！",
        "join_btn": "📢 加入频道",
        "joined_btn": "已加入 ✅",
        "joined_success": "谢谢！您已成功加入频道。",
        "not_joined": "您还没有加入频道！请先加入。",
        "menu_telegram": "📱 电报购买",
        "menu_profile": "👤 个人资料",
        "menu_deposit": "💰 充值",
        "menu_refer": "🔗 推荐",
        "menu_support": "☎️ 客服支持",
        "menu_language": "🌐 语言",
        "select_lang": "🌐 请选择您的语言 / Please select your language:",
        "lang_changed": "✅ 语言已成功更改为中文！",
        "tg_main_prompt": "请从下方选择您的面板：",
        "tg_all_panels": "🌍 从列表中选择您想要的面板：",
        "panel_select_country": "📁 <b>{panel}</b>\n\n选择一个国家/地区：",
        "back_to_panels": "🔙 返回面板",
        "stock_out": "❌ <b>缺货！</b>\n\n抱歉，此面板/国家的商品目前暂无库存。",
        "insufficient_bal": "❌ <b>余额不足！</b>\n\n价格：{price} USDT，但您的余额为 {balance:.2f} USDT。请在下方充值：",
        "ask_qty": "📁 已选面板/国家：<b>{panel}</b>\n📦 可用库存：{stock} 件\n💲 单价：{price} USDT\n💰 您的余额：{balance:.2f} USDT\n\n您想购买多少件？请输入数字：",
        "purchase_success": "✅ <b>购买成功！</b>\n\n成功购买 {qty} 件！\n💵 扣除：{cost} USDT\n💎 新余额：{new_bal:.2f} USDT",
        "purchased_products": "🛍️ <b>您购买的商品 ({panel}):</b>\n\n{products}",
        "profile_text": "👤 <b>您的个人资料：</b>\n\n🆔 用户 ID: <code>{user_id}</code>\n📛 姓名：{name}\n💰 余额：{balance:.2f} USDT\n🛍️ 总购买量：{total_buy}",
        "deposit_main": "💎 <b>充值系统</b>\n\n请从下方按钮中选择您要充值的支付方式：",
        "deposit_step1": "💎 <b>{method} 充值</b>\n\n请将款项发送至:\n地址 / ID: <code>{address}</code>\n\n第一步：输入您发送的 USDT 金额（仅限数字，例如 5 或 10）：",
        "deposit_step2": "🧾 现在请发送您的 <b>订单号 / 交易哈希 (TrxID)</b>：",
        "deposit_pending": "⏳ 您的充值请求已发送给管理员，请耐心等待。",
        "refer_text": "🔗 <b>推荐计划</b>\n\n使用下方的个人推荐链接邀请您的好友加入我们的机器人，拓展您的网络！\n\n🔗 您的推荐链接：\n<code>{link}</code>",
        "support_text": "☎️ <b>客户支持与协助</b>\n\n需要任何帮助吗？随时联系我们的客服团队获取支持。\n\n💬 官方客服：<a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n⏰ 服务时间：24/7 全天候",
        "contact_admin": "🟢 联系客服",
        "back": "🔙 返回",
        "invalid_num": "❌ 请输入有效的数字。",
        "not_enough_stock": "❌ 库存不足！当前仅剩 {stock} 件库存。",
        "enter_valid_amount": "❌ 请输入有效的金额。",
        "dep_success_user": "🎉 您充值的 {amount:.2f} USDT 已成功到账！\n💰 当前余额：{balance:.2f} USDT",
        "dep_cancel_user": "❌ 您的充值请求已被取消。"
    }
}

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
app = Flask(__name__)

trade_data = {}
user_states = {}

# --- Webhook Reset ---
try:
  bot.remove_webhook(drop_pending_updates=True)
  time.sleep(1)
except Exception as e:
  print(f"Webhook reset warning: {e}")


# --- Local Database (Auto Payment) ---
def init_local_db():
  conn = sqlite3.connect("auto_payments.db")
  cursor = conn.cursor()
  cursor.execute(""" CREATE TABLE IF NOT EXISTS transactions ( id INTEGER PRIMARY KEY AUTOINCREMENT, trx_id TEXT UNIQUE, amount REAL, sender TEXT, status TEXT DEFAULT 'unused' ) """)
  conn.commit()
  conn.close()


init_local_db()


@app.route("/webhook/payment", methods=["POST"])
def receive_payment():
  data = request.json
  if not data:
    return jsonify({"status": "error", "message": "No data provided"}), 400

  trx_id = data.get("trx_id")
  amount = data.get("amount")
  sender = data.get("sender", "Personal")

  if not trx_id or not amount:
    return jsonify({"status": "error", "message": "Invalid data"}), 400

  try:
    conn = sqlite3.connect("auto_payments.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (trx_id, amount, sender) VALUES (?, ?, ?)",
        (trx_id.strip(), float(amount), sender),
    )
    conn.commit()
    conn.close()
    return jsonify(
        {"status": "success", "message": "Payment stored successfully"}
    )
  except sqlite3.IntegrityError:
    return (
        jsonify({"status": "error", "message": "Transaction ID already exists"}),
        400,
    )
  except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500


class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.send_header("Content-type", "text/plain")
    self.end_headers()
    self.wfile.write(b"Bot and Auto-Payment Server are alive and running!")

  def log_message(self, format, *args):
    return


def run_fake_server():
  port = int(os.environ.get("PORT", 8080))
  HTTPServer.allow_reuse_address = True
  server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
  server.serve_forever()


def set_bot_commands():
  commands = [
      BotCommand("start", "Re-start Bot & Open Menu"),
  ]
  try:
    bot.set_my_commands(commands)
  except Exception as e:
    print(f"Failed to set bot commands: {e}")


# --- Force Subscription Check Function ---
def check_subscription(user_id):
  try:
    member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
    if member.status in ['creator', 'administrator', 'member']:
      return True
    return False
  except Exception as e:
    return False


def get_user(message):
  user_id = message.from_user.id
  first_name = message.from_user.first_name or "Unknown"
  username = message.from_user.username or "No_Username"

  try:
    url = f"{FIREBASE_URL}users/{user_id}.json"
    res = requests.get(url, timeout=10)
    data = res.json()

    if not data:
      new_user = {
          "user_id": user_id,
          "first_name": first_name,
          "username": username,
          "balance": 0.0,
          "total_buy": 0,
          "language": "en"
      }
      requests.put(url, json=new_user, timeout=10)
      return 0.0, 0, "en"

    existing_name = data.get("first_name", "")
    existing_uname = data.get("username", "")
    lang = data.get("language", "en")
    
    if existing_name != first_name or existing_uname != username:
      requests.patch(
          url,
          json={"first_name": first_name, "username": username},
          timeout=10,
      )

    return float(data.get("balance", 0.0)), int(data.get("total_buy", 0)), lang
  except Exception as e:
    print(f"Firebase get_user Error: {e}")
    return 0.0, 0, "en"


def get_user_data_by_id(user_id):
  try:
    url = f"{FIREBASE_URL}users/{user_id}.json"
    res = requests.get(url, timeout=10)
    data = res.json()
    if not data:
      return 0.0, 0, "en"
    return float(data.get("balance", 0.0)), int(data.get("total_buy", 0)), data.get("language", "en")
  except Exception as e:
    print(f"Firebase get_user_data_by_id Error: {e}")
    return 0.0, 0, "en"


def update_user_language(user_id, lang):
  try:
    url = f"{FIREBASE_URL}users/{user_id}/language.json"
    requests.put(url, json=lang, timeout=10)
  except Exception as e:
    print(f"Firebase update_user_language Error: {e}")


def update_balance(user_id, amount):
  try:
    current_bal, _, _ = get_user_data_by_id(user_id)
    new_bal = current_bal + amount
    url = f"{FIREBASE_URL}users/{user_id}/balance.json"
    requests.put(url, json=new_bal, timeout=10)
    return new_bal
  except Exception as e:
    print(f"Firebase update_balance Error: {e}")
    return 0.0


def add_buy_count(user_id):
  try:
    _, current_buy, _ = get_user_data_by_id(user_id)
    new_buy = current_buy + 1
    url = f"{FIREBASE_URL}users/{user_id}/total_buy.json"
    requests.put(url, json=new_buy, timeout=10)
  except Exception as e:
    print(f"Firebase add_buy_count Error: {e}")


def get_stock(path_key):
  try:
    safe_key = path_key.replace(" ", "_").replace(",", "").replace(".", "")
    url = f"{FIREBASE_URL}stock/{safe_key}.json"
    res = requests.get(url, timeout=10)
    data = res.json()
    if isinstance(data, list):
      return [item for item in data if item]
    elif isinstance(data, dict):
      return list(data.values())
    return []
  except Exception as e:
    print(f"Firebase get_stock Error: {e}")
    return []


def update_stock(path_key, remaining_items):
  try:
    safe_key = path_key.replace(" ", "_").replace(",", "").replace(".", "")
    url = f"{FIREBASE_URL}stock/{safe_key}.json"
    requests.put(url, json=remaining_items, timeout=10)
  except Exception as e:
    print(f"Firebase update_stock Error: {e}")


def get_main_menu(lang="en"):
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton(t["menu_telegram"]),
      KeyboardButton(t["menu_profile"]),
      KeyboardButton(t["menu_deposit"]),
      KeyboardButton(t["menu_refer"]),
      KeyboardButton(t["menu_support"]),
      KeyboardButton(t["menu_language"])
  )
  return markup


def get_telegram_main_menu(lang="en"):
  markup = InlineKeyboardMarkup()
  panels = ["Panel 1", "Panel 2", "Panel 3", "Panel 4"]
  
  row = []
  for panel in panels:
    stock_items = get_stock(panel)
    count = len(stock_items)
    btn_text = f"★ {panel} [{count} pcs]"
    row.append(InlineKeyboardButton(btn_text, callback_data=f"pnl_{panel.replace(' ', '_')}"))
    if len(row) == 2:
      markup.add(*row)
      row = []
  if row:
    markup.add(*row)
    
  return markup


@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id
  _, _, lang = get_user(message)
  user_states.pop(user_id, None)
  bot.clear_step_handler_by_chat_id(user_id)
  trade_data.pop(user_id, None)

  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

  # Check Force Subscription
  if not check_subscription(user_id):
    channel_markup = InlineKeyboardMarkup()
    channel_markup.add(InlineKeyboardButton(t["join_btn"], url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
    channel_markup.add(InlineKeyboardButton(t["joined_btn"], callback_data="check_join"))

    bot.send_message(
        message.chat.id,
        t["join_req"].format(name=message.from_user.first_name),
        reply_markup=channel_markup,
        parse_mode="HTML",
    )
    return

  bot.send_message(
      message.chat.id,
      t["welcome"].format(name=message.from_user.first_name),
      reply_markup=get_main_menu(lang),
      parse_mode="HTML"
  )


# 'Joined ✅' Callback Handler
@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
  user_id = call.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

  if check_subscription(user_id):
    bot.answer_callback_query(call.id, t["joined_success"])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        t["welcome"].format(name=call.from_user.first_name),
        reply_markup=get_main_menu(lang),
    )
  else:
    bot.answer_callback_query(call.id, t["not_joined"], show_alert=True)


# --- Language Selection Handlers ---
@bot.message_handler(func=lambda message: message.text in ["🌐 Language", "🌐 语言"])
def language_menu_handler(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
      InlineKeyboardButton("🇨🇳 中国人 (Chinese)", callback_data="lang_zh")
  )
  bot.send_message(
      message.chat.id,
      t["select_lang"],
      reply_markup=markup
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_callback_handler(call):
  user_id = call.from_user.id
  lang = call.data.split("_")[1]
  update_user_language(user_id, lang)
  
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  bot.answer_callback_query(call.id, t["lang_changed"])
  bot.delete_message(call.message.chat.id, call.message.message_id)
  
  bot.send_message(
      call.message.chat.id,
      t["welcome"].format(name=call.from_user.first_name),
      reply_markup=get_main_menu(lang),
      parse_mode="HTML"
  )


@bot.message_handler(commands=["addstock"])
def add_stock_handler(message):
  if message.from_user.id != ADMIN_ID:
    bot.reply_to(message, "❌ You do not have permission to use this command!")
    return

  try:
    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) < 2:
      bot.reply_to(
          message,
          "⚠️ Please write in the correct format:\n<code>/addstock Panel 1/India | product1\nproduct2</code>",
          parse_mode="HTML",
      )
      return

    content = text_parts[1]
    if "|" not in content:
      bot.reply_to(
          message, "⚠️ Please put a pipe (|) between the path and the product."
      )
      return

    target_path, products_raw = content.split("|", 1)
    target_path = target_path.strip()
    
    new_products = [p.strip() for p in products_raw.split("\n") if p.strip()]

    if not new_products:
      bot.reply_to(message, "⚠️ No valid products found!")
      return

    stock_list = get_stock(target_path)
    stock_list.extend(new_products)

    update_stock(target_path, stock_list)
    bot.reply_to(
        message,
        f"✅ Successfully added {len(new_products)} items to stock!\n📦 Target: {target_path}",
        parse_mode="HTML",
    )
  except Exception as e:
    bot.reply_to(message, f"❌ Error occurred: {e}")


@bot.message_handler(func=lambda message: message.text in ["📱 Telegram Buy Now", "📱 电报购买"])
def telegram_button_handler(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  bot.send_message(
      message.chat.id, 
      t["tg_main_prompt"], 
      reply_markup=get_telegram_main_menu(lang)
  )


@bot.callback_query_handler(func=lambda call: call.data == "tg_all_countries" or call.data == "back_to_telegram")
def show_all_countries_menu(call):
  user_id = call.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  bot.edit_message_text(
      t["tg_all_panels"],
      call.message.chat.id,
      call.message.message_id,
      reply_markup=get_telegram_main_menu(lang),
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("pnl_") or call.data.startswith("cntry_"))
def dynamic_navigation_handler(call):
  user_id = call.from_user.id
  if not check_subscription(user_id):
    bot.answer_callback_query(call.id, "Please join the channel first!", show_alert=True)
    return

  balance, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  
  if call.data.startswith("pnl_"):
    panel_key = call.data.split("_", 1)[1]
    panel_name = panel_key.replace("_", " ")
    
    if panel_name == "Panel 1":
      markup = InlineKeyboardMarkup()
      row = []
      for country in PANEL_1_COUNTRIES.keys():
        path_key = f"Panel 1/{country}"
        stock_count = len(get_stock(path_key))
        btn_text = f"🌍 {country} [{stock_count} pcs]"
        callback_val = f"cntry_1_{country.replace(' ', '_')}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_val))
        if len(row) == 2:
          markup.add(*row)
          row = []
      if row:
        markup.add(*row)
      markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          t["panel_select_country"].format(panel="Panel 1"),
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )
      return
      
    elif panel_name == "Panel 2":
      markup = InlineKeyboardMarkup()
      row = []
      for country in PANEL_2_COUNTRIES.keys():
        path_key = f"Panel 2/{country}"
        stock_count = len(get_stock(path_key))
        btn_text = f"🌍 {country} [{stock_count} pcs]"
        callback_val = f"cntry_2_{country.replace(' ', '_')}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_val))
        if len(row) == 2:
          markup.add(*row)
          row = []
      if row:
        markup.add(*row)
      markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          t["panel_select_country"].format(panel="Panel 2"),
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )
      return

    elif panel_name == "Panel 3":
      markup = InlineKeyboardMarkup()
      row = []
      for country in PANEL_3_COUNTRIES.keys():
        path_key = f"Panel 3/{country}"
        stock_count = len(get_stock(path_key))
        btn_text = f"🌍 {country} [{stock_count} pcs]"
        callback_val = f"cntry_3_{country.replace(' ', '_')}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_val))
        if len(row) == 2:
          markup.add(*row)
          row = []
      if row:
        markup.add(*row)
      markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          t["panel_select_country"].format(panel="Panel 3"),
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )
      return

    else:
      item_price_usdt = PANEL_PRICES.get(panel_name, 1.5)
      stock_items = get_stock(panel_name)
      stock_count = len(stock_items)
      
      if stock_count <= 0:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
        bot.edit_message_text(
            t["stock_out"],
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

      if balance < item_price_usdt:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"),
            InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")
        )
        markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
        bot.edit_message_text(
            t["insufficient_bal"].format(price=item_price_usdt, balance=balance),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
      else:
        user_states[user_id] = {"action": "buy_item_quantity", "panel": panel_name, "price": item_price_usdt}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(t["back_to_panels"], callback_data="back_to_telegram"))
        bot.edit_message_text(
            t["ask_qty"].format(panel=panel_name, stock=stock_count, price=item_price_usdt, balance=balance),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
      return

  elif call.data.startswith("cntry_"):
    parts = call.data.split("_", 2)
    panel_num = parts[1]
    panel_name = f"Panel {panel_num}"
    slug = parts[2]
    
    country_name = None
    if panel_num == "1":
      target_dict = PANEL_1_COUNTRIES
    elif panel_num == "2":
      target_dict = PANEL_2_COUNTRIES
    else:
      target_dict = PANEL_3_COUNTRIES

    for c in target_dict.keys():
      if slug == c.replace(" ", "_"):
        country_name = c
        break
        
    if not country_name:
      return

    path_key = f"{panel_name}/{country_name}"
    item_price_usdt = target_dict.get(country_name, 0.5)
    stock_items = get_stock(path_key)
    stock_count = len(stock_items)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"pnl_{panel_name.replace(' ', '_')}"))

    if stock_count <= 0:
      bot.edit_message_text(
          f"🌍 Country: <b>{country_name}</b> ({panel_name})\n💲 Price: {item_price_usdt} USDT\n\n" + t["stock_out"],
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )
      return

    if balance < item_price_usdt:
      pay_markup = InlineKeyboardMarkup()
      pay_markup.add(
          InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"),
          InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")
      )
      pay_markup.add(InlineKeyboardButton(f"{t['back']} {panel_name}", callback_data=f"pnl_{panel_name.replace(' ', '_')}"))
      
      bot.edit_message_text(
          f"🌍 Country: <b>{country_name}</b> ({panel_name})\n💲 Price: {item_price_usdt} USDT\n\n" + t["insufficient_bal"].format(price=item_price_usdt, balance=balance),
          call.message.chat.id,
          call.message.message_id,
          reply_markup=pay_markup,
          parse_mode="HTML"
      )
    else:
      user_states[user_id] = {"action": "buy_item_quantity", "panel": path_key, "price": item_price_usdt}
      bot.edit_message_text(
          t["ask_qty"].format(panel=f"{panel_name} / {country_name}", stock=stock_count, price=item_price_usdt, balance=balance),
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "buy_item_quantity" )
def process_buy_quantity(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  state_data = user_states.get(user_id, {})
  panel_name = state_data.get("panel")
  
  try:
    qty = int(message.text)
    if qty <= 0:
      bot.send_message(message.chat.id, t["invalid_num"])
      return
    
    stock_items = get_stock(panel_name)
    if qty > len(stock_items):
      bot.send_message(message.chat.id, t["not_enough_stock"].format(stock=len(stock_items)))
      return

    price_per_item = state_data.get("price", 1.0)
    total_cost = qty * price_per_item
    balance, _, _ = get_user_data_by_id(user_id)

    if balance < total_cost:
      markup = InlineKeyboardMarkup()
      markup.add(
          InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"),
          InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")
      )
      bot.send_message(
          message.chat.id,
          t["insufficient_bal"].format(price=total_cost, balance=balance),
          reply_markup=markup,
          parse_mode="HTML"
      )
      user_states.pop(user_id, None)
      return

    purchased_items = stock_items[:qty]
    remaining_items = stock_items[qty:]
    update_stock(panel_name, remaining_items)

    new_balance = balance - total_cost
    url = f"{FIREBASE_URL}users/{user_id}/balance.json"
    requests.put(url, json=new_balance, timeout=10)
    add_buy_count(user_id)

    user_states.pop(user_id, None)

    products_text = "\n".join([f"<code>{item}</code>" for item in purchased_items])
    bot.send_message(
        message.chat.id,
        t["purchased_products"].format(panel=panel_name, products=products_text),
        parse_mode="HTML"
    )

    bot.send_message(
        message.chat.id,
        t["purchase_success"].format(qty=qty, cost=total_cost, new_bal=new_balance),
        reply_markup=get_main_menu(lang),
        parse_mode="HTML"
    )
  except ValueError:
    bot.send_message(message.chat.id, t["invalid_num"])


@bot.message_handler(commands=["broadcast"])
def broadcast_handler(message):
  if message.from_user.id != ADMIN_ID:
    bot.reply_to(message, "❌ You do not have permission to use this command!")
    return

  text_parts = message.text.split(maxsplit=1)
  if len(text_parts) < 2:
    bot.reply_to(
        message,
        "⚠️ Please write the broadcast message.\nExample: <code>/broadcast your message</code>",
    )
    return

  broadcast_msg = text_parts[1]

  try:
    url = f"{FIREBASE_URL}users.json"
    res = requests.get(url, timeout=15)
    users_data = res.json()
  except Exception as e:
    bot.reply_to(message, f"❌ Firebase load error: {e}")
    return

  if not users_data:
    bot.reply_to(message, "No users found in the database!")
    return

  success_count = 0
  fail_count = 0
  blocked_users_list = []

  sent_notification = bot.reply_to(
      message, "🚀 Broadcast started, please wait..."
  )

  for u_id_str, u_info in users_data.items():
    try:
      u_id = int(u_id_str)
      name = (
          u_info.get("first_name", "Unknown")
          if isinstance(u_info, dict)
          else "Unknown"
      )
      uname = (
          u_info.get("username", "No_Username")
          if isinstance(u_info, dict)
          else "No_Username"
      )

      bot.send_message(u_id, broadcast_msg, parse_mode="HTML")
      success_count += 1
      time.sleep(0.08)
    except Exception as e:
      fail_count += 1
      err_str = str(e).lower()
      if (
          "blocked" in err_str
          or "deactivated" in err_str
          or "forbidden" in err_str
      ):
        blocked_users_list.append(
            f"• {name} (@{uname}) - <code>{u_id_str}</code>"
        )
      else:
        blocked_users_list.append(
            f"• {name} (@{uname}) - <code>{u_id_str}</code> (Error)"
        )

  report_text = (
      f"✅ <b>Broadcast Completed!</b>\n\n"
      f"👥 Successfully sent: {success_count}\n"
      f"❌ Failed: {fail_count}\n"
  )

  if blocked_users_list:
    report_text += (
        f"\n🚫 <b>Blocked or Failed Users:</b>\n"
        + "\n".join(blocked_users_list[:20])
    )

  bot.edit_message_text(
      report_text,
      chat_id=message.chat.id,
      message_id=sent_notification.message_id,
      parse_mode="HTML",
  )


@bot.message_handler(commands=["users"])
def list_users(message):
  if message.from_user.id != ADMIN_ID:
    bot.reply_to(message, "❌ You do not have permission to use this command!")
    return

  try:
    url = f"{FIREBASE_URL}users.json"
    res = requests.get(url, timeout=15)
    users_data = res.json()
  except Exception as e:
    bot.reply_to(message, f"❌ Firebase load error: {e}")
    return

  if not users_data:
    bot.reply_to(message, "No users in the database!")
    return

  text = f"👥 <b>Total Users: {len(users_data)}</b>\n\n"
  count = 1

  for u_id_str, u_info in users_data.items():
    if isinstance(u_info, dict):
      name = u_info.get("first_name", "Unknown")
      uname = u_info.get("username", "No_Username")
      u_id = u_info.get("user_id", u_id_str)
      text += f"{count}. {name} (@{uname}) - <code>{u_id}</code>\n"
    else:
      text += f"{count}. ID: <code>{u_id_str}</code>\n"
    count += 1
    if count > 30:
      text += "\n...and many more."
      break

  bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["key"])
def send_key(message):
  key_text = "SUP-7FE5-9F3A-2B8F-6736-5C32-353D-8EC1-B954"
  bot.send_message(message.chat.id, f"`{key_text}`", parse_mode="Markdown")


@bot.message_handler(commands=["profile"])
@bot.message_handler(func=lambda message: message.text in ["👤 Profile", "👤 个人资料"])
def profile_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  balance, total_buy, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  
  user_info = t["profile_text"].format(
      user_id=user_id,
      name=message.from_user.first_name,
      balance=balance,
      total_buy=total_buy
  )
  bot.send_message(message.chat.id, user_info, parse_mode="HTML")


def get_deposit_main_markup():
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"),
      InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")
  )
  return markup


@bot.message_handler(commands=["deposit"])
@bot.message_handler(func=lambda message: message.text in ["💰 Deposit", "💰 充值"])
def deposit_handler(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  bot.send_message(
      message.chat.id, t["deposit_main"], reply_markup=get_deposit_main_markup(), parse_mode="HTML"
  )


@bot.callback_query_handler(func=lambda call: call.data == "back_to_deposit")
def back_to_deposit_menu(call):
  user_id = call.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  
  bot.edit_message_text(
      t["deposit_main"],
      call.message.chat.id,
      call.message.message_id,
      reply_markup=get_deposit_main_markup(),
      parse_mode="HTML"
  )


@bot.callback_query_handler(func=lambda call: call.data in ["dep_binance_uid", "dep_tron"])
def deposit_method_selected(call):
  user_id = call.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  if not check_subscription(user_id):
    bot.answer_callback_query(call.id, "Please join the channel first!", show_alert=True)
    return

  method_map = {
      "dep_binance_uid": ("Binance UID", DOLLAR_CONFIG["binance_uid"]),
      "dep_tron": ("Tron-TRC20", DOLLAR_CONFIG["tron_address"])
  }
  method_name, address = method_map[call.data]
  
  user_states[user_id] = {"action": "deposit_amount", "method": method_name}
  
  markup = InlineKeyboardMarkup()
  markup.add(InlineKeyboardButton(t["back"], callback_data="back_to_deposit"))
  bot.edit_message_text(
      t["deposit_step1"].format(method=method_name, address=address),
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="HTML",
  )


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "deposit_amount" )
def get_deposit_amount(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  
  try:
    amount = float(message.text)
    if amount <= 0:
      bot.send_message(message.chat.id, t["enter_valid_amount"])
      return

    user_states[user_id]["amount"] = amount
    user_states[user_id]["action"] = "deposit_order_id"

    bot.send_message(
        message.chat.id,
        t["deposit_step2"],
        parse_mode="HTML"
    )
  except ValueError:
    bot.send_message(message.chat.id, t["invalid_num"])


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "deposit_order_id" )
def get_deposit_order_id(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  
  state_data = user_states.pop(user_id, {})
  method = state_data.get("method", "Crypto")
  amount = state_data.get("amount", 0.0)
  order_id = message.text.strip()

  bot.send_message(
      message.chat.id,
      t["deposit_pending"],
      reply_markup=get_main_menu(lang)
  )

  admin_markup = InlineKeyboardMarkup()
  admin_markup.row(
      InlineKeyboardButton(
          "✅ Approve",
          callback_data=f"depapprove|{user_id}|{amount:.2f}|{order_id}",
      ),
      InlineKeyboardButton(
          "❌ Reject",
          callback_data=f"depreject|{user_id}|{order_id}",
      ),
  )

  bot.send_message(
      ADMIN_ID,
      f"🔔 <b>New Deposit Request!</b>\n\n"
      f"👤 User: {message.from_user.first_name} (<code>{user_id}</code>)\n"
      f"💳 Method: {method}\n"
      f"💵 Amount: {amount:.2f} USDT\n"
      f"🧾 Order ID / TrxID: <code>{order_id}</code>",
      reply_markup=admin_markup,
      parse_mode="HTML"
  )


@bot.callback_query_handler( func=lambda call: call.data.startswith("depapprove|") or call.data.startswith("depreject|") )
def admin_deposit_action(call):
  parts = call.data.split("|")
  action = parts[0]
  target_id = int(parts[1])
  _, _, target_lang = get_user_data_by_id(target_id)
  target_t = TRANSLATIONS.get(target_lang, TRANSLATIONS["en"])

  if action == "depapprove":
    amount = float(parts[2])
    order_id = parts[3]
    new_balance = update_balance(target_id, amount)

    bot.edit_message_text(
        f"✅ Deposit approved successfully!\n\n🆔 User ID: <code>{target_id}</code>\n🧾 Order ID: <code>{order_id}</code>\n💰 Added Balance: {amount:.2f} USDT",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML"
    )
    try:
      bot.send_message(
          target_id,
          target_t["dep_success_user"].format(amount=amount, balance=new_balance),
      )
    except:
      pass

  elif action == "depreject":
    order_id = parts[2]
    bot.edit_message_text(
        f"❌ Deposit cancelled.\n🆔 User ID: <code>{target_id}</code>\n🧾 Order ID: <code>{order_id}</code>",
        call.message.chat.id,
        call.message.message_id,
        parse_no="HTML"
    )
    try:
      bot.send_message(target_id, target_t["dep_cancel_user"])
    except:
      pass


@bot.message_handler(commands=["refer"])
@bot.message_handler(func=lambda message: message.text in ["🔗 Refer", "🔗 推荐"])
def refer_handler(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  bot_username = bot.get_me().username
  bot_link = f"https://t.me/{bot_username}?start={user_id}"
  bot.send_message(message.chat.id, t["refer_text"].format(link=bot_link), parse_mode="HTML")


@bot.message_handler(commands=["support"])
@bot.message_handler(func=lambda message: message.text in ["☎️ Support", "☎️ 客服支持"])
def support_handler(message):
  user_id = message.from_user.id
  _, _, lang = get_user_data_by_id(user_id)
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ Please join the channel first!")
    return

  t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton(
          t["contact_admin"], url="https://t.me/GV_gmail_07"
      )
  )
  bot.send_message(message.chat.id, t["support_text"], reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "close")
def close_msg(call):
  bot.delete_message(call.message.chat.id, call.message.message_id)


if __name__ == "__main__":
  threading.Thread(target=run_fake_server, daemon=True).start()

  print("Setting bot commands...")
  set_bot_commands()
  print("Bot & Auto-Payment server is starting polling...")

  while True:
    try:
      bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    except Exception as e:
      print(f"Polling Exception caught: {e}. Reconnecting in 5 seconds...")
      time.sleep(5)
