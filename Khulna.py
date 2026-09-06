from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import sqlite3
import threading
import time
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

# Firebase Realtime Database URL
FIREBASE_URL = "https://shopbotdb-default-rtdb.firebaseio.com/"

DOLLAR_CONFIG = {
    "binance_uid": "1076781671",
    "tron_address": "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8",
}

# Product Prices (in USDT)
PRODUCT_PRICES = {
    "+880": 1.0,
    "+91": 1.2,
    "+7": 2.1,
    "+1": 1.5,
    "+972": 1.1,
    "+34": 1.0,
    "+54": 3.0,
    "+62": 1.5,
    "+95": 1.2,
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


def get_stock(country_code):
  try:
    normalized_code = country_code if country_code.startswith("+") else "+" + country_code
    url = f"{FIREBASE_URL}stock/{normalized_code}.json"
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


def update_stock(country_code, remaining_items):
  try:
    normalized_code = country_code if country_code.startswith("+") else "+" + country_code
    url = f"{FIREBASE_URL}stock/{normalized_code}.json"
    requests.put(url, json=remaining_items, timeout=10)
  except Exception as e:
    print(f"Firebase update_stock Error: {e}")


def get_main_menu():
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      KeyboardButton("📱 Telegram"),
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
  countries = [
      ("+880", "BD"),
      ("+91", "IN"),
      ("+7", "RU"),
      ("+1", "US"),
      ("+972", "IS"),
      ("+34", "SP"),
      ("+54", "IRG"),
      ("+62", "IN"),
      ("+95", "MY"),
  ]
  
  row = []
  for code, name in countries:
    stock_items = get_stock(code)
    count = len(stock_items)
    btn_text = f"★ {code} ({name}) [{count} pcs]"
    row.append(InlineKeyboardButton(btn_text, callback_data=f"cnt_{code}"))
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

  bot.send_message(
      message.chat.id,
      f"🌸 Welcome <b>{message.from_user.first_name}</b>!\n\nWelcome to our shop. Please select from the menu below:",
      reply_markup=get_main_menu(),
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
          "⚠️ Please write in the correct format:\n<code>/addstock +880 | product1\nproduct2</code>",
          parse_mode="HTML",
      )
      return

    content = text_parts[1]
    if "|" not in content:
      bot.reply_to(
          message, "⚠️ Please put a pipe (|) between the country and the product."
      )
      return

    country_code, products_raw = content.split("|", 1)
    country_code = country_code.strip()
    
    new_products = [p.strip() for p in products_raw.split("\n") if p.strip()]

    if not new_products:
      bot.reply_to(message, "⚠️ No valid products found!")
      return

    stock_list = get_stock(country_code)
    stock_list.extend(new_products)

    update_stock(country_code, stock_list)
    bot.reply_to(
        message,
        f"✅ Successfully added {len(new_products)} items to stock!\n🌍 Country: {country_code}",
        parse_mode="HTML",
    )
  except Exception as e:
    bot.reply_to(message, f"❌ Error occurred: {e}")


@bot.message_handler(func=lambda message: message.text == "📱 Telegram")
def telegram_button_handler(message):
  bot.send_message(
      message.chat.id, 
      "Select your country from the Telegram section:", 
      reply_markup=get_telegram_main_menu()
  )


@bot.callback_query_handler(func=lambda call: call.data == "tg_all_countries" or call.data == "back_to_telegram")
def show_all_countries_menu(call):
  bot.edit_message_text(
      "🌍 Select your desired country from the list:",
      call.message.chat.id,
      call.message.message_id,
      reply_markup=get_telegram_main_menu(),
  )


@bot.callback_query_handler(func=lambda call: call.data.startswith("cnt_"))
def country_folder_selected(call):
  country_code = call.data.split("_")[1]
  user_id = call.from_user.id
  balance, _ = get_user_balance_by_id(user_id)
  
  item_price_usdt = PRODUCT_PRICES.get(country_code, 1.0)
  stock_items = get_stock(country_code)
  stock_count = len(stock_items)

  if stock_count <= 0:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back to Countries", callback_data="back_to_telegram"))
    bot.edit_message_text(
        f"❌ <b>Stock Out!</b>\n\nSorry, products for this country are currently out of stock. Please try another country.",
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
    markup.add(InlineKeyboardButton("🔙 Back to Countries", callback_data="back_to_telegram"))
    
    bot.edit_message_text(
        f"❌ <b>Insufficient Balance!</b>\n\nYou do not have enough USDT in your account. Price per piece is {item_price_usdt} USDT. Please deposit from the options below:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )
  else:
    user_states[user_id] = {"action": "buy_item_quantity", "country": country_code, "price": item_price_usdt}
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back to Countries", callback_data="back_to_telegram"))
    
    bot.edit_message_text(
        f"📁 Selected Country: <b>{country_code}</b>\n📦 Available Stock: {stock_count} pcs\n💲 Price per piece: {item_price_usdt} USDT\n💰 Your Balance: {balance:.2f} USDT\n\nHow many pieces do you want to buy? Enter a number:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )


@bot.message_handler( func=lambda msg: user_states.get(msg.from_user.id, {}).get("action") == "buy_item_quantity" )
def process_buy_quantity(message):
  user_id = message.from_user.id
  state_data = user_states.get(user_id, {})
  country_code = state_data.get("country")
  
  try:
    qty = int(message.text)
    if qty <= 0:
      bot.send_message(message.chat.id, "❌ Please enter a valid number.")
      return
    
    stock_items = get_stock(country_code)
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
    update_stock(country_code, remaining_items)

    new_balance = balance - total_cost
    url = f"{FIREBASE_URL}users/{user_id}/balance.json"
    requests.put(url, json=new_balance, timeout=10)
    add_buy_count(user_id)

    user_states.pop(user_id, None)

    products_text = "\n".join([f"<code>{item}</code>" for item in purchased_items])
    bot.send_message(
        message.chat.id,
        f"🛍️ <b>Your Purchased Products ({country_code}):</b>\n\n{products_text}",
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
  balance, total_buy = get_user_balance_by_id(message.from_user.id)
  user_info = (
      f"👤 <b>Your Profile Information:</b>\n\n"
      f"🆔 User ID: <code>{message.from_user.id}</code>\n"
      f"📛 Name: {message.from_user.first_name}\n"
      f"💰 Balance: {balance:.2f} USDT\n"
      f"🛍️ Total Purchases: {total_buy}"
  )
  bot.send_message(message.chat.id, user_info)


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
  method_map = {
      "dep_binance_uid": ("Binance UID", DOLLAR_CONFIG["binance_uid"]),
      "dep_tron": ("Tron-TRC20", DOLLAR_CONFIG["tron_address"])
  }
  method_name, address = method_map[call.data]
  
  user_states[call.from_user.id] = {"action": "deposit_amount", "method": method_name}
  
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


@bot.message_handler(func=lambda message: message.text == "🔗 Refer")
def refer_handler(message):
  bot_username = bot.get_me().username
  bot_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
  text = f"🔗 Your referral link:\n<code>{bot_link}</code>\n\nInvite friends and win bonuses!"
  bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["support"])
@bot.message_handler(func=lambda message: message.text == "☎️ Support")
def support_handler(message):
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
  bot.send_message(message.chat.id, text, reply_markup=markup)


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
