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
      }
      requests.put(url, json=new_user, timeout=10)
      return 0.0, 0

    existing_name = data.get("first_name", "")
    existing_uname = data.get("username", "")
    if existing_name != first_name or existing_uname != username:
      requests.patch(
          url,
          json={"first_name": first_name, "username": username},
          timeout=10,
      )

    return float(data.get("balance", 0.0)), int(data.get("total_buy", 0))
  except Exception as e:
    print(f"Firebase get_user Error: {e}")
    return 0.0, 0


def get_user_balance_by_id(user_id):
  try:
    url = f"{FIREBASE_URL}users/{user_id}.json"
    res = requests.get(url, timeout=10)
    data = res.json()
    if not data:
      return 0.0, 0
    return float(data.get("balance", 0.0)), int(data.get("total_buy", 0))
  except Exception as e:
    print(f"Firebase get_user_balance_by_id Error: {e}")
    return 0.0, 0


def update_balance(user_id, amount):
  try:
    current_bal, _ = get_user_balance_by_id(user_id)
    new_bal = current_bal + amount
    url = f"{FIREBASE_URL}users/{user_id}/balance.json"
    requests.put(url, json=new_bal, timeout=10)
    return new_bal
  except Exception as e:
    print(f"Firebase update_balance Error: {e}")
    return 0.0


def add_buy_count(user_id):
  try:
    _, current_buy = get_user_balance_by_id(user_id)
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


def get_main_menu():
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton("📱 Telegram Sell"),
      KeyboardButton("👤 Profile"),
      KeyboardButton("💰 Deposit"),
      KeyboardButton("🔗 Refer"),
      KeyboardButton("☎️ Support")
  )
  return markup


def cancel_markup():
  markup = InlineKeyboardMarkup()
  markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"))
  return markup


def get_telegram_main_menu():
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
  get_user(message)
  user_states.pop(user_id, None)
  bot.clear_step_handler_by_chat_id(user_id)
  trade_data.pop(user_id, None)

  # Check Force Subscription
  if not check_subscription(user_id):
    channel_markup = InlineKeyboardMarkup()
    channel_markup.add(InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
    channel_markup.add(InlineKeyboardButton("Joined ✅", callback_data="check_join"))

    bot.send_message(
        message.chat.id,
        f"🌸 Welcome <b>{message.from_user.first_name}</b>!\n\n⚠️ আগে আমাদের চ্যানেলে জয়েন করুন, তারপরে বট ব্যবহার করতে পারবেন!",
        reply_markup=channel_markup,
        parse_mode="HTML",
    )
    return

  bot.send_message(
      message.chat.id,
      f"🌸 Welcome <b>{message.from_user.first_name}</b>!\n\nPlease select from the menu below:",
      reply_markup=get_main_menu(),
      parse_mode="HTML"
  )


# 'Joined ✅' Callback Handler
@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
  user_id = call.from_user.id
  if check_subscription(user_id):
    bot.answer_callback_query(call.id, "ধন্যবাদ! আপনি চ্যানেলে জয়েন করেছেন।")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
        "Please select from the menu below:",
        reply_markup=get_main_menu(),
    )
  else:
    bot.answer_callback_query(call.id, "আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে আগে জয়েন করুন।", show_alert=True)


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


@bot.message_handler(func=lambda message: message.text == "📱 Telegram Sell")
def telegram_button_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করতে হবে, তারপরে এই অপশন আসবে। /start লিখে চেক করুন।")
    return

  bot.send_message(
      message.chat.id, 
      "Select your panel from the section below:", 
      reply_markup=get_telegram_main_menu()
  )


@bot.callback_query_handler(func=lambda call: call.data == "tg_all_countries" or call.data == "back_to_telegram")
def show_all_countries_menu(call):
  bot.edit_message_text(
      "🌍 Select your desired panel from the list:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=get_telegram_main_menu(),
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("pnl_") or call.data.startswith("cntry_"))
def dynamic_navigation_handler(call):
  user_id = call.from_user.id
  if not check_subscription(user_id):
    bot.answer_callback_query(call.id, "আগে চ্যানেলে জয়েন করুন!", show_alert=True)
    return

  balance, _ = get_user_balance_by_id(user_id)
  
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
      markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          "📁 <b>Panel 1</b>\n\nSelect a country:",
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
      markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          "📁 <b>Panel 2</b>\n\nSelect a country:",
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
      markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
      
      bot.edit_message_text(
          "📁 <b>Panel 3</b>\n\nSelect a country:",
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
        markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
        bot.edit_message_text(
            f"❌ <b>Stock Out!</b>\n\nSorry, products for this panel are currently out of stock.",
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
        markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
        bot.edit_message_text(
            f"❌ <b>Insufficient Balance!</b>\n\nPrice per piece is {item_price_usdt} USDT.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
      else:
        user_states[user_id] = {"action": "buy_item_quantity", "panel": panel_name, "price": item_price_usdt}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back to Panels", callback_data="back_to_telegram"))
        bot.edit_message_text(
            f"📁 Selected Panel: <b>{panel_name}</b>\n📦 Available Stock: {stock_count} pcs\n💲 Price per piece: {item_price_usdt} USDT\n💰 Your Balance: {balance:.2f} USDT\n\nHow many pieces do you want to buy? Enter a number:",
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
    markup.add(InlineKeyboardButton(f"🔙 Back to {panel_name}", callback_data=f"pnl_{panel_name.replace(' ', '_')}"))

    if stock_count <= 0:
      bot.edit_message_text(
          f"🌍 Country: <b>{country_name}</b> ({panel_name})\n💲 Price: {item_price_usdt} USDT\n\n❌ <b>Stock Out!</b>\n\nProducts for this country are currently out of stock.",
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
      pay_markup.add(InlineKeyboardButton(f"🔙 Back to {panel_name}", callback_data=f"pnl_{panel_name.replace(' ', '_')}"))
      
      bot.edit_message_text(
          f"🌍 Country: <b>{country_name}</b> ({panel_name})\n💲 Price: {item_price_usdt} USDT\n\n❌ <b>Insufficient Balance!</b>\n\nYour balance is {balance:.2f} USDT. Please deposit below:",
          call.message.chat.id,
          call.message.message_id,
          reply_markup=pay_markup,
          parse_mode="HTML"
      )
    else:
      user_states[user_id] = {"action": "buy_item_quantity", "panel": path_key, "price": item_price_usdt}
      bot.edit_message_text(
          f"🌍 Country: <b>{country_name}</b> ({panel_name})\n📦 Available Stock: {stock_count} pcs\n💲 Price per piece: {item_price_usdt} USDT\n💰 Your Balance: {balance:.2f} USDT\n\nHow many pieces do you want to buy? Enter a number:",
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode="HTML"
      )


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "buy_item_quantity" )
def process_buy_quantity(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করুন!")
    return

  state_data = user_states.get(user_id, {})
  panel_name = state_data.get("panel")
  
  try:
    qty = int(message.text)
    if qty <= 0:
      bot.send_message(message.chat.id, "❌ Please enter a valid number.")
      return
    
    stock_items = get_stock(panel_name)
    if qty > len(stock_items):
      bot.send_message(message.chat.id, f"❌ Not enough stock available! Currently only {len(stock_items)} pcs are in stock.")
      return

    price_per_item = state_data.get("price", 1.0)
    total_cost = qty * price_per_item
    balance, _ = get_user_balance_by_id(user_id)

    if balance < total_cost:
      markup = InlineKeyboardMarkup()
      markup.add(
          InlineKeyboardButton("🆔 Binance UID", callback_data="dep_binance_uid"),
          InlineKeyboardButton("🔹 Tron-TRC20", callback_data="dep_tron")
      )
      bot.send_message(
          message.chat.id,
          f"❌ <b>Insufficient Balance!</b>\n\nTotal cost: {total_cost} USDT, but your balance is: {balance:.2f} USDT. Please deposit via:",
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
        f"🛍️ <b>Your Purchased Products ({panel_name}):</b>\n\n{products_text}",
        parse_mode="HTML"
    )

    bot.send_message(
        message.chat.id,
        f"✅ <b>Purchase Successful!</b>\n\nSuccessfully bought {qty} pcs!\n💵 Deducted: {total_cost} USDT\n💎 New Balance: {new_balance:.2f} USDT",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
  except ValueError:
    bot.send_message(message.chat.id, "❌ Please enter a valid number.")


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
@bot.message_handler(func=lambda message: message.text == "👤 Profile")
def profile_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করুন!")
    return

  balance, total_buy = get_user_balance_by_id(user_id)
  user_info = (
      f"👤 <b>Your Profile Information:</b>\n\n"
      f"🆔 User ID: <code>{user_id}</code>\n"
      f"📛 Name: {message.from_user.first_name}\n"
      f"💰 Balance: {balance:.2f} USDT\n"
      f"🛍️ Total Purchases: {total_buy}"
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
@bot.message_handler(func=lambda message: message.text == "💰 Deposit")
def deposit_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করুন!")
    return

  deposit_info = (
      "💎 <b>Deposit System</b>\n\n"
      "Select the payment method you want to deposit with from the buttons below:"
  )
  bot.send_message(
      message.chat.id, deposit_info, reply_markup=get_deposit_main_markup(), parse_mode="HTML"
  )


@bot.callback_query_handler(func=lambda call: call.data == "back_to_deposit")
def back_to_deposit_menu(call):
  deposit_info = (
      "💎 <b>Deposit System</b>\n\n"
      "Select the payment method you want to deposit with from the buttons below:"
  )
  bot.edit_message_text(
      deposit_info,
      call.message.chat.id,
      call.message.message_id,
      reply_markup=get_deposit_main_markup(),
      parse_mode="HTML"
  )


@bot.callback_query_handler(func=lambda call: call.data in ["dep_binance_uid", "dep_tron"])
def deposit_method_selected(call):
  user_id = call.from_user.id
  if not check_subscription(user_id):
    bot.answer_callback_query(call.id, "আগে চ্যানেলে জয়েন করুন!", show_alert=True)
    return

  method_map = {
      "dep_binance_uid": ("Binance UID", DOLLAR_CONFIG["binance_uid"]),
      "dep_tron": ("Tron-TRC20", DOLLAR_CONFIG["tron_address"])
  }
  method_name, address = method_map[call.data]
  
  user_states[user_id] = {"action": "deposit_amount", "method": method_name}
  
  text = (
      f"💎 <b>{method_name} Deposit</b>\n\n"
      f"Send payment to:\nAddress / ID: <code>{address}</code>\n\n"
      "Step 1: Enter the amount of USDT you sent (numbers only, e.g., 5 or 10):"
  )
  markup = InlineKeyboardMarkup()
  markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_to_deposit"))
  bot.edit_message_text(
      text,
      call.message.chat.id,
      call.message.message_id,
      reply_markup=markup,
      parse_mode="HTML",
  )


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "deposit_amount" )
def get_deposit_amount(message):
  try:
    amount = float(message.text)
    if amount <= 0:
      bot.send_message(message.chat.id, "❌ Please enter a valid amount.")
      return

    user_id = message.from_user.id
    user_states[user_id]["amount"] = amount
    user_states[user_id]["action"] = "deposit_order_id"

    bot.send_message(
        message.chat.id,
        "🧾 Now please send your <b>Order ID / Transaction ID (TrxID)</b>:",
        parse_mode="HTML"
    )
  except ValueError:
    bot.send_message(message.chat.id, "❌ Please enter a valid number.")


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "deposit_order_id" )
def get_deposit_order_id(message):
  user_id = message.from_user.id
  state_data = user_states.pop(user_id, {})
  method = state_data.get("method", "Crypto")
  amount = state_data.get("amount", 0.0)
  order_id = message.text.strip()

  bot.send_message(
      message.chat.id,
      "⏳ Your deposit request has been sent to the admin. Please wait.",
      reply_markup=get_main_menu()
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
          f"🎉 Your deposit of {amount:.2f} USDT is successful!\n💰 Current Balance: {new_balance:.2f} USDT",
      )
    except:
      pass

  elif action == "depreject":
    order_id = parts[2]
    bot.edit_message_text(
        f"❌ Deposit cancelled.\n🆔 User ID: <code>{target_id}</code>\n🧾 Order ID: <code>{order_id}</code>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML"
    )
    try:
      bot.send_message(target_id, "❌ Your deposit request has been cancelled.")
    except:
      pass


@bot.message_handler(commands=["refer"])
@bot.message_handler(func=lambda message: message.text == "🔗 Refer")
def refer_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করুন!")
    return

  bot_username = bot.get_me().username
  bot_link = f"https://t.me/{bot_username}?start={user_id}"
  text = f"🔗 Your referral link:\n<code>{bot_link}</code>\n\nInvite friends and win bonuses!"
  bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["support"])
@bot.message_handler(func=lambda message: message.text == "☎️ Support")
def support_handler(message):
  user_id = message.from_user.id
  if not check_subscription(user_id):
    bot.send_message(message.chat.id, "⚠️ আগে চ্যানেলে জয়েন করুন!")
    return

  text = (
      "☎️ <b>Customer Support & Official Contact</b>\n\n"
      "For any issues, purchasing products, or payment assistance, please contact our support account directly.\n\n"
      "💬 Admin Support: <a href='https://t.me/GV_gmail_07'>@GV_gmail_07</a>\n"
      "⏰ Service Time: 24/7 Hours"
  )
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton(
          "🟢 Contact Admin", url="https://t.me/GV_gmail_07"
      )
  )
  bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")


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
