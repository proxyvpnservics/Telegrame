import telebot
from telebot import types
import pyzipper
from datetime import datetime, timezone, timedelta
import random
import os
import io
import json
import time
import requests
from flask import Flask, request

# Token Setup
TOKEN = "8908618066:AAHCcMP6YcGtSeOGlEpFW98CjljFPtwGfNw"
bot = telebot.TeleBot(TOKEN, threaded=False)

# Firebase Database URL
FIREBASE_URL = "https://pranto-7b42c-default-rtdb.firebaseio.com"

# Support Username
support_admin_username = "@LSY0088"

# Admin ID List
ADMIN_IDS = [8138758919]

# In-memory Database & State Management
user_amounts = {}
user_states = {}
user_balances = {}
user_purchases = {}
user_deposits = {}
pending_deposits = {}
used_txids = set()
user_languages = {}
all_users = set()
temp_admin_data = {}

# ----------------- FLASK WEB SERVER & WEBHOOK ROUTE -----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is Running via Webhook!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403
# --------------------------------------------------------------------------

# ----------------- FIREBASE HELPER FUNCTIONS -----------------
def fb_get(path):
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Firebase GET Error ({path}): {e}")
    return None

def fb_put(path, data):
    try:
        response = requests.put(f"{FIREBASE_URL}/{path}.json", json=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Firebase PUT Error ({path}): {e}")
    return False

def load_data_from_firebase():
    global user_balances, user_purchases, user_deposits, user_languages, all_users, product_inventory, support_admin_username
    
    b = fb_get("user_balances")
    if b: user_balances = {int(k): float(v) for k, v in b.items()}
    
    p = fb_get("user_purchases")
    if p: user_purchases = {int(k): v for k, v in p.items()}
    
    d = fb_get("user_deposits")
    if d: user_deposits = {int(k): v for k, v in d.items()}
    
    l = fb_get("user_languages")
    if l: user_languages = {int(k): v for k, v in l.items()}
    
    u = fb_get("all_users")
    if u: all_users = set(int(k) for k in u)
    
    inv = fb_get("product_inventory")
    if inv: product_inventory = inv
    
    sup = fb_get("support_admin_username")
    if sup: support_admin_username = sup

def save_user_data(user_id):
    fb_put(f"user_balances/{user_id}", user_balances.get(user_id, 0.0))
    fb_put(f"user_purchases/{user_id}", user_purchases.get(user_id, []))
    fb_put(f"user_deposits/{user_id}", user_deposits.get(user_id, []))
    fb_put(f"user_languages/{user_id}", user_languages.get(user_id, "en"))
    fb_put(f"all_users/{user_id}", True)

def save_inventory():
    fb_put("product_inventory", product_inventory)

def save_support():
    fb_put("support_admin_username", support_admin_username)

# ----------------- END FIREBASE HELPERS -----------------

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

# Default Store Inventory Database with Subcategories (Google Voice, Gmail, VPN)
DEFAULT_DATABASE = {
    "support_admin": "@LSY0088",
    "product_inventory": {
        "Categories": {
            "items": {
                "Google Voice": {
                    "price": 2.50,
                    "names": {"en": "Google Voice", "zh": "谷歌Voice"},
                    "accounts": [], "zip_files": []
                },
                "Gmail": {
                    "price": 0.80,
                    "names": {"en": "Gmail", "zh": "Gmail邮箱"},
                    "accounts": [], "zip_files": []
                },
                "VPN": {
                    "price": 3.00,
                    "names": {"en": "VPN", "zh": "VPN服务"},
                    "accounts": [], "zip_files": []
                }
            }
        }
    }
}

product_inventory = DEFAULT_DATABASE["product_inventory"]

LANG = {
    "en": {
        "welcome": "📍 Main Menu\n👋 Hello {user_name}!\n\nWelcome to Telegram Bot!\n\nMain Features:\n• 🛍️ BUY (TG - Tdata+Session)\n• User Center - Manage your account\n• TRX & Energy - TRX and energy trading\n• Recharge - Multiple payment methods\n• Support: @LSY0088 - 24/7 online service\n• Language - Language settings\n\nTips:\nClick the buttons below to access features!",
        "buy_menu": "📂 Select a Category / Product Folder:",
        "account": (
            "╭───────────────┬──────────────────────╮\n"
            "│     Field     │         Value        │\n"
            "├───────────────┼──────────────────────┤\n"
            "│ 💰 Balance    │ ${balance:.2f}                │\n"
            "│ 🧾 Orders     │ {purchased_total}                    │\n"
            "│ 👤 Name       │ {name}         │\n"
            "│ 🆔 Username   │ {username}        │\n"
            "│ 📱 Chat ID    │ {user_id}          │\n"
            "╰───────────────┴──────────────────────╯"
        ),
        "deposit": "Select amount (USDT):",
        "support": "📞 Support Center\n\nFor any help, issues or assistance, please contact our support admin:\n👉 {support_user}",
        "language": "🌐 Language Settings / 语言设置\n\nPlease click the button below to switch language:",
        "admin": "🛠️ Welcome to Admin Panel\n\nChoose an option below:",
        "menu_buy": "🛍️ BUY (TG - Tdata+Session)",
        "menu_account": "👤 User Center",
        "menu_deposit": "💰 Recharge",
        "menu_support": "💬 Support",
        "menu_lang": "🌐 Language",
        "menu_admin": "🛠️ Admin Panel",
        "select_qty": "🔢 Select Quantity:\n\nChoose how many items you want to buy:",
        "back": "< Back",
        "main_menu": "< Main Menu",
        "other_amt": "Other Amount",
        "cancel": "< Cancel",
        "stock": "Stock",
        "price": "Price",
        "purchase_success": "✅ Purchase Successful!",
        "insufficient_stock": "❌ Insufficient stock! Available stock:",
        "insufficient_balance": "❌ Insufficient balance!\nRequired:",
        "balance_text": "Remaining Balance:",
        "deposit_select_amt": "Enter custom deposit amount (USDT, Min $3):",
        "min_network": "❌ Minimum deposit for this network is $3.00!",
        "order_created": "[ ORDER CREATED ]",
        "send_exact": "Send exactly",
        "credit_by_admin": "Your balance will be credited by admin once verified.",
        "proof_prompt": "Now please send your payment Proof / Trx Order ID / Screenshot:",
        "proof_sent": "📤 Your payment proof / Order ID has been sent to the admin successfully. Please wait for verification.",
        "txid_used": "❌ This Order ID / TxID has already been used! Each ID can only be used once for a deposit."
    },
    "zh": {
        "welcome": "📍 主菜单\n👋 你好 {user_name}！\n\n欢迎使用电报机器人！\n\n主要功能：\n• 🛍️ 购买 (TG - Tdata+Session)\n• 用户中心 - 管理您的账户\n• TRX与能量 - TRX及能量交易\n• 账户充值 - 多种支付方式\n• 客服支持：@LSY0088 - 7/24在线服务\n• 语言设置 - 切换语言选项\n\n提示：\n点击下方按钮访问各项功能！",
        "buy_menu": "📂 请选择产品分类 / 文件夹：",
        "account": (
            "╭───────────────┬──────────────────────╮\n"
            "│     字段      │         数值         │\n"
            "├───────────────┼──────────────────────┤\n"
            "│ 💰 余额       │ ${balance:.2f}                │\n"
            "│ 🧾 订单数     │ {purchased_total}                    │\n"
            "│ 👤 姓名       │ {name}         │\n"
            "│ 🆔 用户名     │ {username}        │\n"
            "│ 📱 聊天ID     │ {user_id}          │\n"
            "╰───────────────┴──────────────────────╯"
        ),
        "deposit": "请选择充值金额 (USDT)：",
        "support": "📞 支持中心\n\n如有任何帮助、问题或协助，请直接联系我们的支持管理员：\n👉 {support_user}",
        "language": "🌐 语言设置 / Language Settings\n\nPlease click the button below to switch language:",
        "admin": "🛠️ 欢迎来到管理面板\n\n在下方选择一个选项：",
        "menu_buy": "🛍️ 购买 (TG - Tdata+Session)",
        "menu_account": "👤 用户中心",
        "menu_deposit": "💰 账户充值",
        "menu_support": "💬 客服支持",
        "menu_lang": "🌐 语言设置",
        "menu_admin": "🛠️ 管理面板",
        "select_qty": "🔢 选择数量：\n\n请选择您要购买的数量：",
        "back": "< 返回",
        "main_menu": "< 主菜单",
        "other_amt": "其他金额",
        "cancel": "< 取消",
        "stock": "库存",
        "price": "价格",
        "purchase_success": "✅ 购买成功！",
        "insufficient_stock": "❌ 库存不足！可用库存：",
        "insufficient_balance": "❌ 余额不足！\n需要：",
        "balance_text": "剩余余额：",
        "deposit_select_amt": "请输入自定义充值金额 (USDT，最低 $3)：",
        "min_network": "❌ 该网络最低充值金额为 $3.00！",
        "order_created": "[ 订单已创建 ]",
        "send_exact": "请准确发送",
        "credit_by_admin": "管理员验证后将自动为您的账户充值余额。",
        "proof_prompt": "请发送您的付款凭证 / 交易单号 (TxID) / 截图：",
        "proof_sent": "📤 您的付款凭证 / 订单号已成功发送给管理员，请等待验证。",
        "txid_used": "❌ 此订单号 / TxID 已被使用！ 每个单号只能用于充值一次。"
    }
}

def get_lang(user_id):
    return user_languages.get(user_id, "en")

def set_bot_commands(bot_instance):
    commands = [telebot.types.BotCommand("/start", "Re-start Bot & Open Menu")]
    bot_instance.set_my_commands(commands)

def get_main_menu_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(t["menu_buy"]),
        types.KeyboardButton(t["menu_account"]),
        types.KeyboardButton(t["menu_deposit"]),
        types.KeyboardButton(t["menu_support"]),
        types.KeyboardButton(t["menu_lang"])
    )
    if is_admin(user_id):
        markup.add(types.KeyboardButton(t["menu_admin"]))
    return markup

def get_select_amount_keyboard(user_id):
    t = LANG[get_lang(user_id)]
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("3 USDT", callback_data="amt_3"),
        types.InlineKeyboardButton("5 USDT", callback_data="amt_5"),
        types.InlineKeyboardButton("10 USDT", callback_data="amt_10"),
        types.InlineKeyboardButton("20 USDT", callback_data="amt_20"),
        types.InlineKeyboardButton("50 USDT", callback_data="amt_50"),
        types.InlineKeyboardButton("100 USDT", callback_data="amt_100"),
        types.InlineKeyboardButton(t["other_amt"], callback_data="amt_other"),
        types.InlineKeyboardButton(t["cancel"], callback_data="dep_cancel")
    )
    return markup

def get_payment_methods_keyboard(user_id):
    t = LANG[get_lang(user_id)]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💵 USDT (TRC20) (Min $3)", callback_data="order_usdt_trc20"),
        types.InlineKeyboardButton("💵 USDT (BEP20) (Min $3)", callback_data="order_usdt_bep20"),
        types.InlineKeyboardButton(t["cancel"], callback_data="dep_cancel")
    )
    return markup

def get_order_created_keyboard(net_code, order_id, user_id):
    t = LANG[get_lang(user_id)]
    lang_code = get_lang(user_id)
    send_text = "📤 发送订单号 / 交易单号 (TxID)" if lang_code == "zh" else "📤 Send Order Id / TxID"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(send_text, callback_data=f"send_order_id_{order_id}"))
    markup.add(types.InlineKeyboardButton(t["back"], callback_data="dep_confirm"))
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_quantity_keyboard(item_key, user_id):
    t = LANG[get_lang(user_id)]
    lang_code = get_lang(user_id)
    other_qty_text = "其他数量" if lang_code == "zh" else "Other Quantity"
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("1", callback_data=f"qty_{item_key}_1"),
        types.InlineKeyboardButton("2", callback_data=f"qty_{item_key}_2"),
        types.InlineKeyboardButton("3", callback_data=f"qty_{item_key}_3"),
        types.InlineKeyboardButton("5", callback_data=f"qty_{item_key}_5"),
        types.InlineKeyboardButton("10", callback_data=f"qty_{item_key}_10"),
        types.InlineKeyboardButton(other_qty_text, callback_data=f"qty_other_{item_key}"),
        types.InlineKeyboardButton(t["back"], callback_data="back_to_buy_menu")
    )
    return markup

def get_account_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_buy_categories_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=1)
    if "Categories" in product_inventory and "items" in product_inventory["Categories"]:
        buttons = []
        for cat_name, data in product_inventory["Categories"]["items"].items():
            c_name = data.get("names", {}).get(lang_code, cat_name)
            zip_stock_count = sum(len(zf.get("extracted_files", [])) for zf in data.get("zip_files", []))
            total_stock = len(data.get("accounts", [])) + zip_stock_count
            btn_text = f"📂 {c_name} [{total_stock} Stock]"
            buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"select_cat_{cat_name}"))
        markup.add(*buttons)
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_language_keyboard(user_id):
    t = LANG[get_lang(user_id)]
    current_lang = get_lang(user_id)
    if current_lang == "en":
        btn_text = "🇨🇳 切换到中文 (Switch to Chinese)"
    else:
        btn_text = "🇬🇧 Switch to English"
        
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn_text, callback_data="lang_toggle"))
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_admin_panel_keyboard(user_id):
    t = LANG[get_lang(user_id)]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast_start"),
        types.InlineKeyboardButton("👥 Management (Users & Balance)", callback_data="admin_management"),
        types.InlineKeyboardButton("➕ Add New Category Folder", callback_data="admin_add_category"),
        types.InlineKeyboardButton("🗂️ Add Zip File Stock", callback_data="admin_add_zip_menu"),
        types.InlineKeyboardButton("✏️ Edit / Delete Categories", callback_data="admin_edit_delete_categories_menu"),
        types.InlineKeyboardButton("📞 Change Support Username", callback_data="admin_change_support"),
        types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu")
    )
    return markup

def get_management_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    total_users = len(all_users)
    markup.add(types.InlineKeyboardButton(f"👥 All Users List ({total_users})", callback_data="mgmt_users_0"))
    markup.add(types.InlineKeyboardButton("🔍 Search User by ID", callback_data="mgmt_search_user"))
    markup.add(types.InlineKeyboardButton("💰 Top Balance Users", callback_data="mgmt_top_balance"))
    markup.add(types.InlineKeyboardButton("🛠️ Back to Admin Panel", callback_data="admin_back"))
    return markup

def get_users_list_keyboard(page=0, per_page=10):
    markup = types.InlineKeyboardMarkup(row_width=1)
    users_sorted = sorted(list(all_users), reverse=True)
    total = len(users_sorted)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    for uid in users_sorted[start:end]:
        bal = user_balances.get(int(uid), 0.0)
        crown = " 👑" if is_admin(uid) else ""
        markup.add(types.InlineKeyboardButton(f"👤 {uid}{crown} | 💰 ${bal:.2f}", callback_data=f"mgmt_user_{uid}"))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"mgmt_users_{page-1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"mgmt_users_{page+1}"))
    if nav:
        markup.add(*nav)
    markup.add(types.InlineKeyboardButton(f"📄 Page {page+1}/{total_pages} | Total: {total}", callback_data="noop"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Management", callback_data="admin_management"))
    return markup, total_pages, total

def get_user_detail_keyboard(target_uid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add Balance", callback_data=f"mgmt_bal_add_{target_uid}"),
        types.InlineKeyboardButton("➖ Subtract Balance", callback_data=f"mgmt_bal_sub_{target_uid}"),
        types.InlineKeyboardButton("✏️ Set Balance", callback_data=f"mgmt_bal_set_{target_uid}"),
        types.InlineKeyboardButton("🔄 Reset to $0", callback_data=f"mgmt_bal_reset_{target_uid}"),
    )
    markup.add(
        types.InlineKeyboardButton("📦 Purchase History", callback_data=f"mgmt_hist_pur_{target_uid}"),
        types.InlineKeyboardButton("💰 Deposit History", callback_data=f"mgmt_hist_dep_{target_uid}"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Back to Users List", callback_data="mgmt_users_0"))
    markup.add(types.InlineKeyboardButton("🛠️ Back to Admin Panel", callback_data="admin_back"))
    return markup

def get_user_detail_text(target_uid):
    bal = user_balances.get(int(target_uid), 0.0)
    pur = user_purchases.get(int(target_uid), [])
    dep = user_deposits.get(int(target_uid), [])
    lang = user_languages.get(int(target_uid), "en")
    is_adm = "Yes 👑" if is_admin(target_uid) else "No"
    text = (
        f"👤 User Management\n"
        f"──────────────────────\n"
        f"🆔 User ID: {target_uid}\n"
        f"💰 Balance: ${bal:.2f}\n"
        f"🌐 Language: {lang}\n"
        f"👑 Admin: {is_adm}\n"
        f"📦 Total Purchases: {len(pur)}\n"
        f"💰 Total Deposits: {len(dep)}\n"
        f"──────────────────────\n"
        f"Select an option to edit balance:"
    )
    return text

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    all_users.add(user_id)
    save_user_data(user_id)
    user_name = message.from_user.first_name or "Support"
    lang_code = get_lang(user_id)
    welcome_text = LANG[lang_code]["welcome"].format(user_name=user_name)
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu_keyboard(user_id))

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ You are not authorized to use the admin panel.")
        return
    bot.send_message(message.chat.id, "🛠️ Welcome to Admin Panel\n\nChoose an option below:", reply_markup=get_admin_panel_keyboard(message.from_user.id))

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "❌ Current operation cancelled.", reply_markup=get_main_menu_keyboard(message.from_user.id))

@bot.message_handler(content_types=['document'])
def handle_document_uploads(message):
    user_id = message.from_user.id
    if user_states.get(user_id) == "waiting_for_zip_file":
        cat_name = temp_admin_data.get(user_id)
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        if cat_name in product_inventory["Categories"]["items"]:
            temp_admin_data[f"zip_bytes_{user_id}"] = list(downloaded_file)
            user_states[user_id] = "waiting_for_zip_2fa"
            response_msg = (
                f"✅ ZIP File uploaded successfully for folder {cat_name}!\n\n"
                f"🔐 Now, please send the Password / 2FA Code for this ZIP file so it can be verified and read properly:"
            )
            bot.send_message(message.chat.id, response_msg)
        else:
            bot.send_message(message.chat.id, "❌ Invalid category folder selected.")
            user_states.pop(user_id, None)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'])
def handle_all_messages(message):
    user_id = message.from_user.id
    all_users.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0.00
    if user_id not in user_purchases:
        user_purchases[user_id] = []
    if user_id not in user_deposits:
        user_deposits[user_id] = []
    save_user_data(user_id)
    
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    text = message.text if message.text else ""

    if user_states.get(user_id) == "waiting_for_new_support_username":
        global support_admin_username
        new_support = message.text.strip()
        if not new_support.startswith("@"):
            new_support = "@" + new_support
        support_admin_username = new_support
        save_support()
        user_states.pop(user_id, None)
        bot.send_message(
            message.chat.id, 
            f"✅ Support admin username successfully updated to: {support_admin_username}", 
            reply_markup=get_admin_panel_keyboard(user_id)
        )
        return

    if user_states.get(user_id, "").startswith("waiting_for_txid_"):
        order_id = user_states.get(user_id).replace("waiting_for_txid_", "")
        user_states.pop(user_id, None)
        
        dep_amt = user_amounts.get(user_id, 3.00)
        dep_id = f"dep_{user_id}_{int(time.time())}"
        pending_deposits[dep_id] = {
            "user_id": user_id,
            "amount": dep_amt,
            "order_id": order_id
        }

        admin_id = ADMIN_IDS[0] if ADMIN_IDS else 8138758919
        user_name = message.from_user.first_name or "N/A"
        username = f"@{message.from_user.username}" if message.from_user.username else "N/A"
        
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton("✅ Accept", callback_data=f"dep_accept_{dep_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{dep_id}")
        )

        trx_info = message.text if message.text else "Screenshot / Media"

        admin_notification = (
            f"💰 New Deposit Request!\n"
            f"──────────────────────\n"
            f"👤 User: {user_name} ({username})\n"
            f"🆔 User ID: {user_id}\n"
            f"📦 Order ID: {order_id}\n"
            f"💵 Amount: ${dep_amt:.2f}\n"
            f"Trx: {trx_info}\n"
            f"──────────────────────\n"
            f"Click buttons below to Accept or Reject:"
        )
        try:
            bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
            bot.send_message(admin_id, admin_notification, reply_markup=admin_markup)
        except Exception as e:
            print(f"Failed to send proof to admin: {e}")

        success_msg = "📤 Your payment proof / TxID has been sent successfully. Please wait for admin verification."
        bot.send_message(message.chat.id, success_msg, reply_markup=get_main_menu_keyboard(user_id))
        return

    if text in [LANG["en"]["menu_lang"], LANG["zh"]["menu_lang"]]:
        user_states.pop(user_id, None)
        current_lang = user_languages.get(user_id, "en")
        if current_lang == "en":
            user_languages[user_id] = "zh"
            new_lang_name = "中文 (China)"
        else:
            user_languages[user_id] = "en"
            new_lang_name = "English"
            
        save_user_data(user_id)
        new_lang_code = get_lang(user_id)
        success_msg = f"🌐 Language successfully switched to: {new_lang_name}" if new_lang_code == "en" else f"🌐 语言已成功切换为：{new_lang_name}"
        bot.send_message(message.chat.id, success_msg, reply_markup=get_main_menu_keyboard(user_id))
        return

    if user_states.get(user_id) == "waiting_for_mgmt_search":
        user_states.pop(user_id, None)
        try:
            target = int(message.text.strip())
        except:
            bot.send_message(message.chat.id, "❌ Invalid User ID! Please enter numbers only (e.g., 123456789):", reply_markup=get_admin_panel_keyboard(user_id))
            return
        if target not in all_users:
            all_users.add(target)
            if target not in user_balances:
                user_balances[target] = 0.0
            save_user_data(target)
        bot.send_message(message.chat.id, get_user_detail_text(target), reply_markup=get_user_detail_keyboard(target))
        return

    if user_states.get(user_id, "").startswith("waiting_for_mgmt_bal_"):
        state = user_states.get(user_id)
        parts = state.replace("waiting_for_mgmt_bal_", "").split("_")
        action = parts[0]
        target_uid = int(parts[1])
        try:
            amount = float(message.text.strip())
        except:
            bot.send_message(message.chat.id, "❌ Invalid amount! Please enter a valid number (e.g., 10 or 5.50):")
            return
        old_bal = user_balances.get(target_uid, 0.0)
        if action == "add":
            new_bal = old_bal + amount
            msg_action = f"➕ Added ${amount:.2f}"
        elif action == "sub":
            new_bal = old_bal - amount
            if new_bal < 0:
                new_bal = 0.0
            msg_action = f"➖ Subtracted ${amount:.2f}"
        elif action == "set":
            new_bal = amount
            msg_action = f"✏️ Set to ${amount:.2f}"
        else:
            new_bal = old_bal
            msg_action = ""
        user_balances[target_uid] = round(new_bal, 2)
        save_user_data(target_uid)
        user_states.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            f"✅ Balance Updated!\n\n👤 User ID: {target_uid}\n{msg_action}\n💰 Old Balance: ${old_bal:.2f}\n💰 New Balance: ${new_bal:.2f}",
            reply_markup=get_user_detail_keyboard(target_uid)
        )
        try:
            bot.send_message(target_uid, f"💰 Your balance has been updated by Admin!\n\nNew Balance: ${new_bal:.2f}")
        except:
            pass
        return

    if user_states.get(user_id) == "waiting_for_new_category":
        c_name = message.text.strip()
        if c_name not in product_inventory["Categories"]["items"]:
            product_inventory["Categories"]["items"][c_name] = {
                "price": 1.00, 
                "names": {"en": c_name, "zh": c_name}, 
                "accounts": [], 
                "zip_files": []
            }
            save_inventory()
            bot.send_message(message.chat.id, f"✅ Product folder category '{c_name}' added successfully!", reply_markup=get_admin_panel_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, f"⚠️ Category '{c_name}' already exists.")
        user_states.pop(user_id, None)
        return

    if user_states.get(user_id, "").startswith("waiting_for_edit_price_"):
        cat_name = user_states.get(user_id).replace("waiting_for_edit_price_", "")
        try:
            new_price = float(message.text.strip())
            if cat_name in product_inventory["Categories"]["items"]:
                product_inventory["Categories"]["items"][cat_name]["price"] = new_price
                save_inventory()
                bot.send_message(message.chat.id, f"✅ Price for category '{cat_name}' successfully updated to ${new_price:.2f}!", reply_markup=get_admin_panel_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, "❌ Category not found.")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 1.50 or 2):")
        user_states.pop(user_id, None)
        return

    if user_states.get(user_id, "").startswith("waiting_for_rename_category_"):
        old_cat = user_states.get(user_id).replace("waiting_for_rename_category_", "")
        new_cat = message.text.strip()
        proto_items = product_inventory["Categories"]["items"]
        if new_cat in proto_items:
            bot.send_message(message.chat.id, f"⚠️ Category '{new_cat}' already exists!")
        elif old_cat in proto_items:
            proto_items[new_cat] = proto_items.pop(old_cat)
            save_inventory()
            bot.send_message(message.chat.id, f"✅ Successfully renamed category from '{old_cat}' to '{new_cat}'!", reply_markup=get_admin_panel_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "❌ Category not found.")
        user_states.pop(user_id, None)
        return

    if user_states.get(user_id) == "waiting_for_broadcast_message":
        user_states.pop(user_id, None)
        success_count = 0
        fail_count = 0
        bot.send_message(message.chat.id, "⏳ Broadcasting message to all users, please wait...")
        for uid in all_users:
            try:
                bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
                success_count += 1
            except Exception:
                fail_count += 1
        bot.send_message(message.chat.id, f"✅ Broadcast Completed!\n\n👥 Successfully sent: {success_count} users\n❌ Failed (Blocked bot): {fail_count} users", reply_markup=get_main_menu_keyboard(user_id))
        return

    if user_states.get(user_id, "").startswith("waiting_for_custom_qty_"):
        item_key = user_states.get(user_id).replace("waiting_for_custom_qty_", "")
        try:
            qty = int(message.text.strip())
            if qty <= 0:
                bot.send_message(message.chat.id, "❌ Please enter a valid quantity greater than 0:")
                return
            user_states.pop(user_id, None)
            process_product_purchase(message.chat.id, user_id, item_key, qty)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid number! Please enter a valid integer (e.g., 2, 5):")
        return

    if user_states.get(user_id) == "waiting_for_custom_amount":
        try:
            custom_amount = float(message.text.strip())
            min_limit = 3.00
            if custom_amount < min_limit:
                bot.send_message(message.chat.id, f"❌ Minimum deposit amount is ${min_limit:.2f}. Please enter again:")
                return
            user_amounts[user_id] = custom_amount
            user_states[user_id] = "waiting_for_payment_method"
            payment_text = f"💰 Selected Amount: ${custom_amount:.2f}\n\nPlease select your preferred payment method:" if lang_code == "en" else f"💰 已选金额： ${custom_amount:.2f}\n\n请选择您的首选付款方式："
            bot.send_message(message.chat.id, payment_text, reply_markup=get_payment_methods_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid amount. Please enter a valid number (e.g., 5 or 10):")
        return

    if user_states.get(user_id) == "waiting_for_payment_proof":
        bot.send_message(message.chat.id, t["proof_sent"], reply_markup=get_main_menu_keyboard(user_id))
        user_states.pop(user_id, None)
        temp_admin_data.pop(f"order_info_{user_id}", None)
        return

    if user_states.get(user_id) == "waiting_for_zip_2fa":
        tfa_code = message.text.strip() if message.text else ""
        cat_name = temp_admin_data.get(user_id)
        zip_bytes_list = temp_admin_data.get(f"zip_bytes_{user_id}")
        if cat_name and zip_bytes_list and tfa_code:
            zip_bytes = io.BytesIO(bytes(zip_bytes_list))
            try:
                with pyzipper.AESZipFile(zip_bytes, 'r') as zf:
                    zf.setpassword(tfa_code.encode('utf-8'))
                    file_list = zf.namelist()
                    valid_files = [f for f in file_list if not f.endswith('/')]
                    if "zip_files" not in product_inventory["Categories"]["items"][cat_name]:
                        product_inventory["Categories"]["items"][cat_name]["zip_files"] = []
                    product_inventory["Categories"]["items"][cat_name]["zip_files"].append({
                        "zip_bytes": zip_bytes_list,
                        "2fa": tfa_code,
                        "extracted_files": valid_files
                    })
                    save_inventory()
                    bot.send_message(message.chat.id, f"✅ Successfully added ZIP stock for '{cat_name}'!\n📁 Total valid files: {len(valid_files)}\n🔐 Password / 2FA: {tfa_code}", reply_markup=get_admin_panel_keyboard(user_id))
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Password Error!\nError details: {str(e)}", reply_markup=get_admin_panel_keyboard(user_id))
        user_states.pop(user_id, None)
        temp_admin_data.pop(user_id, None)
        temp_admin_data.pop(f"zip_bytes_{user_id}", None)
        return

    is_buy = text in [LANG["en"]["menu_buy"], LANG["zh"]["menu_buy"]]
    is_account = text in [LANG["en"]["menu_account"], LANG["zh"]["menu_account"]]
    is_deposit = text in [LANG["en"]["menu_deposit"], LANG["zh"]["menu_deposit"]]
    is_support = text in [LANG["en"]["menu_support"], LANG["zh"]["menu_support"]]
    is_admin_menu = text in [LANG["en"]["menu_admin"], LANG["zh"]["menu_admin"]]

    if any([is_buy, is_account, is_deposit, is_support, is_admin_menu]):
        user_states.pop(user_id, None)

    if is_admin_menu:
        if not is_admin(user_id):
            bot.send_message(message.chat.id, "❌ Unauthorized.")
            return
        bot.send_message(message.chat.id, "🛠️ Welcome to Admin Panel\n\nChoose an option below:", reply_markup=get_admin_panel_keyboard(message.from_user.id))
        return
    elif is_buy:
        bot.send_message(message.chat.id, t["buy_menu"], reply_markup=get_buy_categories_keyboard(user_id))
    elif is_deposit:
        user_states[user_id] = "waiting_for_deposit"
        bot.send_message(message.chat.id, t["deposit"], reply_markup=get_select_amount_keyboard(user_id))
    elif is_account:
        user = message.from_user
        username = f"@{user.username}" if user.username else "N/A"
        name = user.first_name or "N/A"
        balance_val = user_balances.get(user_id, 0.00)
        purchased_total = len(user_purchases.get(user_id, []))
        account_text = t["account"].format(user_id=user.id, username=username, name=name, balance=balance_val, purchased_total=purchased_total)
        bot.send_message(message.chat.id, account_text, reply_markup=get_account_keyboard(user_id))
    elif is_support:
        support_msg = t["support"].format(support_user=support_admin_username)
        bot.send_message(message.chat.id, support_msg)

def process_product_purchase(chat_id, user_id, item_key, qty):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    if "Categories" in product_inventory and item_key in product_inventory["Categories"]["items"]:
        c_data = product_inventory["Categories"]["items"][item_key]
        price_per_unit = c_data.get("price", 1.00)
        zip_list = c_data.get("zip_files", [])
        accounts_list = c_data.get("accounts", [])
    else:
        bot.send_message(chat_id, "❌ Category folder not found.")
        return

    zip_total_files = sum(len(zf.get("extracted_files", [])) for zf in zip_list)
    total_stock = len(accounts_list) + zip_total_files
    if total_stock < qty:
        bot.send_message(chat_id, f"{t['insufficient_stock']} {total_stock} items.", reply_markup=get_main_menu_keyboard(chat_id))
        return
    total_price = price_per_unit * qty
    user_balance = user_balances.get(user_id, 0.00)
    if user_balance < total_price:
        bot.send_message(chat_id, f"{t['insufficient_balance']} ${total_price:.2f}\n{t['balance_text'].replace('Remaining', 'Your')} ${user_balance:.2f}\nPlease deposit first.", reply_markup=get_main_menu_keyboard(chat_id))
        return
    user_balances[user_id] = user_balance - total_price

    for _ in range(qty):
        try:
            while len(zip_list) > 0 and len(zip_list[0].get("extracted_files", [])) == 0:
                zip_list.pop(0)
            if len(zip_list) > 0:
                zip_item = zip_list[0]
                orig_zip_bytes = bytes(zip_item["zip_bytes"])
                tfa_code = zip_item["2fa"]
                files_in_zip = zip_item["extracted_files"]
                target_file_name = files_in_zip.pop(0)
                single_zip_buffer = io.BytesIO()
                with pyzipper.AESZipFile(single_zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as new_zip:
                    new_zip.setpassword(tfa_code.encode('utf-8'))
                    with pyzipper.AESZipFile(io.BytesIO(orig_zip_bytes), 'r') as orig_zip:
                        orig_zip.setpassword(tfa_code.encode('utf-8'))
                        file_data = orig_zip.read(target_file_name)
                        new_zip.writestr(os.path.basename(target_file_name), file_data)
                single_zip_buffer.seek(0)
                if len(files_in_zip) == 0:
                    zip_list.pop(0)
                purchase_text = f"Bought {item_key} (ZIP file) for ${price_per_unit:.2f}"
                if user_id not in user_purchases:
                    user_purchases[user_id] = []
                user_purchases[user_id].append({"text": purchase_text, "timestamp": time.time()})
                save_user_data(user_id)
                save_inventory()
                file_short_name = os.path.basename(target_file_name)
                bot.send_document(
                    chat_id, 
                    document=single_zip_buffer, 
                    visible_file_name=f"{item_key}_{file_short_name}.zip", 
                    caption=f"{t['purchase_success']}\n\n📂 Category: {item_key}\n📦 File: {file_short_name}\n🔐 2FA & ZIP Password: {tfa_code}\n💵 Paid: ${price_per_unit:.2f}\n\n{t['balance_text']} ${user_balances[user_id]:.2f}"
                )
            elif len(accounts_list) > 0:
                purchased_item = accounts_list.pop(0)
                acc_num = purchased_item.get("number", "N/A")
                acc_2fa = purchased_item.get("2fa", "N/A")
                purchase_text = f"Bought {item_key}: {acc_num} for ${price_per_unit:.2f}"
                if user_id not in user_purchases:
                    user_purchases[user_id] = []
                user_purchases[user_id].append({"text": purchase_text, "timestamp": time.time()})
                save_user_data(user_id)
                save_inventory()
                success_text = f"{t['purchase_success']}\n\n📂 Category: {item_key}\n📱 Detail: {acc_num}\n🔐 2FA Code: {acc_2fa}\n💵 Paid: ${price_per_unit:.2f}\n\n{t['balance_text']} ${user_balances[user_id]:.2f}"
                bot.send_message(chat_id, success_text)
        except Exception as e:
            print(f"Error in delivering product: {e}")
            bot.send_message(chat_id, f"❌ Error delivering item: {str(e)}")

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_clicks(call):
    user_id = call.from_user.id
    all_users.add(user_id)
    if user_id not in user_balances:
        user_balances[user_id] = 0.00
    if user_id not in user_purchases:
        user_purchases[user_id] = []
    if user_id not in user_deposits:
        user_deposits[user_id] = []
    save_user_data(user_id)
    
    lang_code = get_lang(user_id)
    t = LANG[lang_code]

    if call.data == "admin_change_support":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_new_support_username"
        bot.answer_callback_query(call.id, "Change Support Username")
        try:
            bot.edit_message_text(
                "📞 Change Support Username\n\nPlease send new support username (e.g., @YourUsername):",
                call.message.chat.id, 
                call.message.message_id
            )
        except Exception:
            pass
        return

    if call.data.startswith("dep_accept_") or call.data.startswith("dep_reject_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        
        action = "accept" if "accept" in call.data else "reject"
        dep_id = call.data.replace("dep_accept_", "").replace("dep_reject_", "")
        
        if dep_id in pending_deposits:
            dep_info = pending_deposits.pop(dep_id)
            target_uid = dep_info["user_id"]
            amount = dep_info["amount"]
            order_id = dep_info["order_id"]
            
            if action == "accept":
                old_bal = user_balances.get(target_uid, 0.0)
                new_bal = old_bal + amount
                user_balances[target_uid] = round(new_bal, 2)
                
                if target_uid not in user_deposits:
                    user_deposits[target_uid] = []
                user_deposits[target_uid].append({"text": f"Deposited ${amount:.2f} (Order: {order_id})", "timestamp": time.time()})
                save_user_data(target_uid)
                
                bot.answer_callback_query(call.id, "Deposit Accepted & Credited!", show_alert=True)
                try:
                    bot.edit_message_text(f"✅ Deposit Accepted!\nOrder ID: {order_id}\nCredited Amount: ${amount:.2f} to User {target_uid}", call.message.chat.id, call.message.message_id)
                except:
                    pass
                
                try:
                    bot.send_message(target_uid, f"✅ Your deposit has been accepted successfully!\n\n💰 ${amount:.2f} has been credited to your account.")
                except:
                    pass
            else:
                bot.answer_callback_query(call.id, "Deposit Rejected!", show_alert=True)
                try:
                    bot.edit_message_text(f"❌ Deposit Rejected!\nOrder ID: {order_id} for User {target_uid}", call.message.chat.id, call.message.message_id)
                except:
                    pass
                try:
                    bot.send_message(target_uid, f"❌ Sorry, your deposit request has been rejected by admin.\nOrder ID: {order_id}")
                except:
                    pass
        else:
            bot.answer_callback_query(call.id, "Request already processed or expired!", show_alert=True)
        return

    if call.data.startswith("send_order_id_"):
        order_id = call.data.replace("send_order_id_", "")
        user_states[user_id] = f"waiting_for_txid_{order_id}"
        bot.answer_callback_query(call.id, "Send Order ID / TxID")
        
        prompt_text = (
            "📤 Please send your payment Transaction ID (TxID) or Proof:\n\n"
            f"Order ID: {order_id}"
        )
        try:
            bot.edit_message_text(prompt_text, call.message.chat.id, call.message.message_id)
        except:
            bot.send_message(call.message.chat.id, prompt_text)
        return

    if call.data == "admin_management":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Management")
        total_users = len(all_users)
        text = (
            f"👥 Management\n"
            f"──────────────────────\n"
            f"👥 Total Users: {total_users}\n"
            f"──────────────────────\n"
            f"Select option below:"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_management_keyboard(user_id))
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=get_management_keyboard(user_id))
        return

    if call.data.startswith("mgmt_users_"):
        if not is_admin(user_id):
            return
        try:
            page = int(call.data.replace("mgmt_users_", ""))
        except:
            page = 0
        bot.answer_callback_query(call.id, f"Page {page+1}")
        markup, total_pages, total = get_users_list_keyboard(page)
        text = f"👥 All Users List\n──────────────────────\nTotal Users: {total}\nClick a user to edit balance:"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            pass
        return

    if call.data == "mgmt_search_user":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_mgmt_search"
        bot.answer_callback_query(call.id, "Search User")
        try:
            bot.edit_message_text("🔍 Search User\n\nPlease send User ID (e.g., 123456789):", call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    if call.data == "mgmt_top_balance":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id, "Top Balance")
        top = sorted(all_users, key=lambda u: user_balances.get(int(u), 0.0), reverse=True)[:10]
        markup = types.InlineKeyboardMarkup(row_width=1)
        for uid in top:
            bal = user_balances.get(int(uid), 0.0)
            markup.add(types.InlineKeyboardButton(f"👤 {uid} | 💰 ${bal:.2f}", callback_data=f"mgmt_user_{uid}"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Management", callback_data="admin_management"))
        try:
            bot.edit_message_text("💰 Top 10 Balance Users:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            pass
        return

    if call.data.startswith("mgmt_user_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_user_", ""))
        bot.answer_callback_query(call.id, f"User {target_uid}")
        try:
            bot.edit_message_text(get_user_detail_text(target_uid), call.message.chat.id, call.message.message_id, reply_markup=get_user_detail_keyboard(target_uid))
        except:
            bot.send_message(call.message.chat.id, get_user_detail_text(target_uid), reply_markup=get_user_detail_keyboard(target_uid))
        return

    if call.data.startswith("mgmt_bal_add_") or call.data.startswith("mgmt_bal_sub_") or call.data.startswith("mgmt_bal_set_"):
        if not is_admin(user_id):
            return
        rest = call.data.replace("mgmt_bal_", "")
        action, target_uid = rest.split("_")
        user_states[user_id] = f"waiting_for_mgmt_bal_{action}_{target_uid}"
        old_bal = user_balances.get(int(target_uid), 0.0)
        label = {"add": "➕ Add Balance", "sub": "➖ Subtract Balance", "set": "✏️ Set Balance"}[action]
        bot.answer_callback_query(call.id, label)
        try:
            bot.edit_message_text(
                f"{label}\n\n👤 User ID: {target_uid}\n💰 Current Balance: ${old_bal:.2f}\n\nPlease send amount (e.g., 10):",
                call.message.chat.id, call.message.message_id
            )
        except:
            pass
        return

    if call.data.startswith("mgmt_bal_reset_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_bal_reset_", ""))
        old_bal = user_balances.get(target_uid, 0.0)
        user_balances[target_uid] = 0.0
        save_user_data(target_uid)
        bot.answer_callback_query(call.id, "Balance Reset to $0", show_alert=True)
        try:
            bot.edit_message_text(
                f"✅ Balance Reset!\n\n👤 User ID: {target_uid}\n💰 Old: ${old_bal:.2f} → New: $0.00",
                call.message.chat.id, call.message.message_id, reply_markup=get_user_detail_keyboard(target_uid)
            )
        except:
            pass
        try:
            bot.send_message(target_uid, "💰 Your balance has been reset to $0.00 by Admin.")
        except:
            pass
        return

    if call.data.startswith("mgmt_hist_pur_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_hist_pur_", ""))
        pur = user_purchases.get(target_uid, [])
        txt = "\n".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in pur[-20:]]) or "No purchases yet."
        bot.answer_callback_query(call.id, "Purchase History")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data=f"mgmt_user_{target_uid}"))
        try:
            bot.edit_message_text(f"📦 Purchase History - {target_uid}\n──────────────────────\n{txt}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            pass
        return

    if call.data.startswith("mgmt_hist_dep_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_hist_dep_", ""))
        dep = user_deposits.get(target_uid, [])
        txt = "\n".join([d.get("text", "") if isinstance(d, dict) else str(d) for d in dep[-20:]]) or "No deposits yet."
        bot.answer_callback_query(call.id, "Deposit History")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data=f"mgmt_user_{target_uid}"))
        try:
            bot.edit_message_text(f"💰 Deposit History - {target_uid}\n──────────────────────\n{txt}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except:
            pass
        return

    if call.data == "lang_toggle":
        current_lang = user_languages.get(user_id, "en")
        if current_lang == "en":
            user_languages[user_id] = "zh"
            alert_text = "语言已成功切换为中文！"
        else:
            user_languages[user_id] = "en"
            alert_text = "Language successfully changed to English!"
            
        save_user_data(user_id)
        bot.answer_callback_query(call.id, alert_text)
        lang_code = get_lang(user_id)
        t = LANG[lang_code]
        try:
            bot.edit_message_text(
                t["language"],
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_language_keyboard(user_id)
            )
        except Exception:
            pass
        try:
            update_msg = "👇 Menu updated:"
            bot.send_message(call.message.chat.id, update_msg, reply_markup=get_main_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data.startswith("qty_"):
        remainder = call.data.replace("qty_", "")
        last_underscore = remainder.rfind("_")
        item_key = remainder[:last_underscore]
        qty = int(remainder[last_underscore + 1:])
        bot.answer_callback_query(call.id, f"Selected {qty} qty")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        process_product_purchase(call.message.chat.id, user_id, item_key, qty)
        return

    elif call.data.startswith("select_cat_"):
        cat_name = call.data.replace("select_cat_", "")
        bot.answer_callback_query(call.id, cat_name)
        c_data = product_inventory["Categories"]["items"].get(cat_name, {})
        price = c_data.get("price", 1.00)
        zip_stock_count = sum(len(zf.get("extracted_files", [])) for zf in c_data.get("zip_files", []))
        stock_count = len(c_data.get("accounts", [])) + zip_stock_count
        markup = types.InlineKeyboardMarkup(row_width=1)
        cart_sel_text = "🛒 Select Quantity"
        markup.add(
            types.InlineKeyboardButton(cart_sel_text, callback_data=f"buy_cat_{cat_name}"),
            types.InlineKeyboardButton(t["back"], callback_data="back_to_buy_menu")
        )
        try:
            cat_detail_text = f"📂 Folder: {cat_name}\n\n💰 Price: ${price:.2f}\n📦 Available {t['stock']}: {stock_count} items\n\nClick below to proceed to quantity selection:"
            bot.edit_message_text(cat_detail_text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("buy_cat_"):
        cat_name = call.data.replace("buy_cat_", "")
        bot.answer_callback_query(call.id, cat_name)
        try:
            proto_qty_text = f"🔢 Select Quantity for {cat_name}:\n\nChoose how many items you want to buy:"
            bot.edit_message_text(proto_qty_text, call.message.chat.id, call.message.message_id, reply_markup=get_quantity_keyboard(cat_name, user_id))
        except Exception:
            pass
        return

    elif call.data == "admin_broadcast_start":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_broadcast_message"
        bot.answer_callback_query(call.id, "Broadcast Mode")
        try:
            bot.edit_message_text("📢 Broadcast System\n\nPlease send the message, photo, video or file that you want to send to all users:", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_add_category":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_new_category"
        bot.answer_callback_query(call.id, "Add Category")
        try:
            bot.edit_message_text("📂 Enter new folder category name (e.g., Telegram Accounts):", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_edit_delete_categories_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        proto_items = product_inventory.get("Categories", {}).get("items", {})
        if proto_items:
            for c_name in proto_items.keys():
                markup.add(
                    types.InlineKeyboardButton(f"💵 Edit Price: {c_name}", callback_data=f"admin_edit_price_{c_name}"),
                    types.InlineKeyboardButton(f"✏️ Rename: {c_name}", callback_data=f"admin_rename_category_{c_name}"),
                    types.InlineKeyboardButton(f"❌ Delete: {c_name}", callback_data=f"admin_delete_category_{c_name}")
                )
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_back"))
        bot.answer_callback_query(call.id, "Categories Edit Menu")
        try:
            bot.edit_message_text("📂 Manage Product Folders:\nSelect an option below:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_edit_price_"):
        if not is_admin(user_id):
            return
        cat_name = call.data.replace("admin_edit_price_", "")
        user_states[user_id] = f"waiting_for_edit_price_{cat_name}"
        current_price = product_inventory["Categories"]["items"].get(cat_name, {}).get("price", 1.00)
        bot.answer_callback_query(call.id, f"Edit Price {cat_name}")
        try:
            bot.edit_message_text(f"💵 Edit Price for '{cat_name}'\n\nCurrent Price: ${current_price:.2f}\n\nPlease send new price (e.g., 1.50 or 2):", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_rename_category_"):
        if not is_admin(user_id):
            return
        cat_name = call.data.replace("admin_rename_category_", "")
        user_states[user_id] = f"waiting_for_rename_category_{cat_name}"
        bot.answer_callback_query(call.id, f"Rename {cat_name}")
        try:
            bot.edit_message_text(f"✏️ Enter new name for folder '{cat_name}':", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_delete_category_"):
        if not is_admin(user_id):
            return
        cat_name = call.data.replace("admin_delete_category_", "")
        proto_items = product_inventory.get("Categories", {}).get("items", {})
        if cat_name in proto_items:
            del proto_items[cat_name]
            save_inventory()
            bot.answer_callback_query(call.id, f"Deleted {cat_name}")
            markup = types.InlineKeyboardMarkup(row_width=1)
            for c in proto_items.keys():
                markup.add(
                    types.InlineKeyboardButton(f"💵 Edit Price: {c}", callback_data=f"admin_edit_price_{c}"),
                    types.InlineKeyboardButton(f"✏️ Rename: {c}", callback_data=f"admin_rename_category_{c}"),
                    types.InlineKeyboardButton(f"❌ Delete: {c}", callback_data=f"admin_delete_category_{c}")
                )
            markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_back"))
            try:
                bot.edit_message_text(f"✅ Folder '{cat_name}' deleted successfully!\n\n📂 Manage Categories:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "Category not found", show_alert=True)
        return

    elif call.data == "admin_add_zip_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in product_inventory["Categories"]["items"].keys():
            markup.add(types.InlineKeyboardButton(f"🗂️ Folder ({c})", callback_data=f"select_zip_cat_{c}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_back"))
        bot.answer_callback_query(call.id, "ZIP Menu")
        try:
            bot.edit_message_text("Select product folder to upload ZIP file stock:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("select_zip_cat_"):
        if not is_admin(user_id):
            return
        cat_name = call.data.replace("select_zip_cat_", "")
        temp_admin_data[user_id] = cat_name
        user_states[user_id] = "waiting_for_zip_file"
        bot.answer_callback_query(call.id, cat_name)
        try:
            bot.edit_message_text(f"📁 Please send the .zip file for folder '{cat_name}':", call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_back":
        if not is_admin(user_id):
            return
        try:
            bot.edit_message_text("🛠️ Welcome to Admin Panel\n\nChoose an option below:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_panel_keyboard(user_id))
        except Exception:
            pass
        return

    elif call.data == "noop":
        bot.answer_callback_query(call.id)
        return

    if call.data == "btn_deposit_open" or call.data == "dep_confirm" or call.data == "▲ Deposit":
        try:
            bot.answer_callback_query(call.id, "Loading...")
            bot.edit_message_text(t["deposit"], call.message.chat.id, call.message.message_id, reply_markup=get_select_amount_keyboard(user_id))
        except Exception:
            bot.send_message(call.message.chat.id, t["deposit"], reply_markup=get_select_amount_keyboard(user_id))
        return

    elif call.data.startswith("amt_"):
        if call.data == "amt_other":
            user_states[user_id] = "waiting_for_custom_amount"
            bot.answer_callback_query(call.id, "Enter custom amount")
            bot.send_message(call.message.chat.id, t["deposit_select_amt"])
        else:
            try:
                selected_val = float(call.data.split("_")[1])
                user_amounts[user_id] = selected_val
                user_states[user_id] = "waiting_for_payment_method"
                payment_text = f"💰 Selected Amount: ${selected_val:.2f}\n\nPlease select your preferred payment method:"
                bot.answer_callback_query(call.id, f"Selected ${selected_val:.2f}")
                bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, reply_markup=get_payment_methods_keyboard(user_id))
            except Exception:
                pass
        return

    elif call.data in ["order_usdt_trc20", "order_usdt_bep20"]:
        current_amount = user_amounts.get(user_id, 3.00)
        if current_amount < 3.0:
            bot.answer_callback_query(call.id, t["min_network"], show_alert=True)
            return
        order_id = f"ORD-{random.randint(100000, 999999)}"
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        if call.data == "order_usdt_trc20":
            calculated_val = current_amount * (10.016 / 10.0)
            send_val = f"{calculated_val:.3f} USDT"
            credit_val = f"${current_amount:.2f}"
            currency_type = "USDT · TRC20"
            wallet_address = "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8"
            network_name = "Tron (TRC20)"
            net_code = "tron"
        else:
            calculated_val = current_amount * (10.076 / 10.0)
            send_val = f"{calculated_val:.3f} USDT"
            credit_val = f"${current_amount:.2f}"
            currency_type = "USDT · BEP20"
            wallet_address = "0x6ea90338aa1f55b4cbd6326c781549df59e416d7"
            network_name = "BNB Smart Chain (BEP20)"
            net_code = "bsc"

        temp_admin_data[f"order_temp_{user_id}"] = {"order_id": order_id, "method": currency_type}
        deposit_text = f"Order: {order_id} | Amt: ${current_amount:.2f} ({currency_type}) | Time: {current_time}"
        if user_id not in user_deposits:
            user_deposits[user_id] = []
        user_deposits[user_id].append({"text": deposit_text, "timestamp": time.time()})
        save_user_data(user_id)
        
        order_text = (
            "[ ORDER CREATED ]  " + currency_type + "\n"
            "──────────────────────\n"
            f"  Send     ·  {send_val}\n"
            f"  Credit   ·  {credit_val}\n"
            f"  Order    ·  {order_id}\n"
            f"  Network  ·  {network_name}\n"
            f"  Address  ·  {wallet_address}\n"
            f"  Expires  ·  {current_time}\n"
            "──────────────────────\n"
            f"Send exactly {send_val}, including all decimals. This amount was converted from ${current_amount:.2f} at the Binance price when the order was created and ends in a unique identifier; ${current_amount:.2f} is credited when it arrives.\n"
            f"Send native assets/tokens on the {network_name} network only.\n"
            "Your balance will be credited by admin once verified."
        )
        bot.answer_callback_query(call.id, "Order Generated!")
        try:
            bot.edit_message_text(order_text, call.message.chat.id, call.message.message_id, reply_markup=get_order_created_keyboard(net_code, order_id, user_id))
        except Exception:
            bot.send_message(call.message.chat.id, order_text, reply_markup=get_order_created_keyboard(net_code, order_id, user_id))
        return

    elif call.data == "back_to_buy_menu":
        bot.answer_callback_query(call.id, "BUY Menu")
        try:
            bot.edit_message_text(t["buy_menu"], call.message.chat.id, call.message.message_id, reply_markup=get_buy_categories_keyboard(user_id))
        except Exception:
            pass
        return

    elif call.data == "go_main_menu" or call.data == "dep_cancel":
        bot.answer_callback_query(call.id, "MainMenu")
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)

if __name__ == '__main__':
    print("Loading data from Firebase...")
    load_data_from_firebase()
    set_bot_commands(bot)
    
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://telegram-nirupom-bot.onrender.com")
    
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
    
    port = int(os.environ.get("PORT", 8080))
    print(f"Webhook Bot is running on port {port}...")
    app.run(host='0.0.0.0', port=port)
