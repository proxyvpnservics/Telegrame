import telebot
from telebot import types
import pyzipper
from datetime import datetime, timezone
import random
import os
import io
import time
import base64
import requests
from flask import Flask, request

# Load credentials strictly from Environment Variables (Safe for GitHub)
TOKEN = os.environ.get("BOT_TOKEN")
FIREBASE_URL = os.environ.get("FIREBASE_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")
if not FIREBASE_URL:
    raise ValueError("FIREBASE_URL environment variable is missing!")

FIREBASE_URL = FIREBASE_URL.rstrip("/")

bot = telebot.TeleBot(TOKEN, threaded=False)

# Support Username & Admin IDs
support_admin_username = "@LSY0088"
ADMIN_IDS = [6954924404, 8138758919]

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
    return '', 403
# --------------------------------------------------------------------------

# Database Setup with Categories (Fallback if Firebase is empty)
DEFAULT_DATABASE = {
    "support_admin": "@LSY0088",
    "product_inventory": {
        "Countries": {
            "type": "countries",
            "items": {
                "Bangladesh": {
                    "code": "+880",
                    "price": 1.50,
                    "names": {"en": "Bangladesh", "zh": "孟加拉国"},
                    "accounts": [], "zip_files": []
                }
            }
        },
        "Google_Voice": {
            "type": "digital_goods",
            "names": {"en": "Google Voice", "zh": "谷歌Voice"},
            "items": {
                "GV_US_Random": {
                    "price": 2.50,
                    "names": {"en": "US Google Voice (Random)", "zh": "美国谷歌Voice(随机)"},
                    "accounts": []
                }
            }
        },
        "Gmail": {
            "type": "digital_goods",
            "names": {"en": "Gmail Accounts", "zh": "Gmail 邮箱"},
            "items": {
                "Gmail_Old": {
                    "price": 0.80,
                    "names": {"en": "Old Aged Gmail", "zh": "老号 Gmail"},
                    "accounts": []
                }
            }
        },
        "VPN": {
            "type": "digital_goods",
            "names": {"en": "VPN Services", "zh": "VPN 服务"},
            "items": {
                "VPN_1Month": {
                    "price": 5.00,
                    "duration": "1 Month",
                    "names": {"en": "Premium VPN 1 Month", "zh": "高级 VPN 1个月"},
                    "accounts": []
                }
            }
        }
    }
}

product_inventory = DEFAULT_DATABASE["product_inventory"]

# ----------------- FIREBASE HELPER FUNCTIONS -----------------
def fb_get(path):
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Firebase GET Error ({path}): {e}")
    return None

def fb_put(path, data):
    try:
        response = requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=20)
        if response.status_code != 200:
            print(f"Firebase PUT Failed ({path}): {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Firebase PUT Error ({path}): {e}")
    return False

def load_data_from_firebase():
    global user_balances, user_purchases, user_deposits, user_languages, all_users
    global product_inventory, support_admin_username, pending_deposits, used_txids

    b = fb_get("user_balances")
    if b and isinstance(b, dict):
        user_balances = {int(k): float(v) for k, v in b.items() if v is not None}

    p = fb_get("user_purchases")
    if p and isinstance(p, dict):
        user_purchases = {int(k): v for k, v in p.items() if v is not None}

    d = fb_get("user_deposits")
    if d and isinstance(d, dict):
        user_deposits = {int(k): v for k, v in d.items() if v is not None}

    l = fb_get("user_languages")
    if l and isinstance(l, dict):
        user_languages = {int(k): v for k, v in l.items() if v is not None}

    u = fb_get("all_users")
    if u and isinstance(u, dict):
        all_users = set(int(k) for k, v in u.items() if v)

    pd = fb_get("pending_deposits")
    if pd and isinstance(pd, dict):
        pending_deposits = pd

    ut = fb_get("used_txids")
    if ut and isinstance(ut, list):
        used_txids = set(ut)
    elif ut and isinstance(ut, dict):
        used_txids = set(ut.keys())

    inv = fb_get("product_inventory")
    if inv and isinstance(inv, dict):
        for cat_key, cat_val in inv.items():
            if isinstance(cat_val, dict):
                if "items" not in cat_val or cat_val["items"] is None:
                    cat_val["items"] = {}
                for item_key, item_val in cat_val["items"].items():
                    if "accounts" not in item_val or item_val["accounts"] is None:
                        item_val["accounts"] = []
                    if cat_key == "Countries":
                        if "zip_files" not in item_val or item_val["zip_files"] is None:
                            item_val["zip_files"] = []
                        else:
                            for zf in item_val["zip_files"]:
                                if "extracted_files" not in zf or zf["extracted_files"] is None:
                                    zf["extracted_files"] = []
        product_inventory = inv

    sup = fb_get("support_admin_username")
    if sup:
        support_admin_username = sup

def ensure_user_registered(user_id):
    is_new = False
    if user_id not in all_users:
        all_users.add(user_id)
        is_new = True
    if user_id not in user_balances:
        user_balances[user_id] = 0.00
    if user_id not in user_purchases:
        user_purchases[user_id] = []
    if user_id not in user_deposits:
        user_deposits[user_id] = []
    if is_new:
        save_user_data(user_id)

def save_user_data(user_id):
    fb_put(f"user_balances/{user_id}", user_balances.get(user_id, 0.0))
    fb_put(f"user_purchases/{user_id}", user_purchases.get(user_id, []))
    fb_put(f"user_deposits/{user_id}", user_deposits.get(user_id, []))
    fb_put(f"user_languages/{user_id}", user_languages.get(user_id, "en"))
    fb_put(f"all_users/{user_id}", True)

def save_inventory():
    return fb_put("product_inventory", product_inventory)

def save_support():
    fb_put("support_admin_username", support_admin_username)

def save_pending_deposits():
    fb_put("pending_deposits", pending_deposits)

def save_used_txids():
    fb_put("used_txids", list(used_txids))

# Load data & configure webhook immediately at startup
print("Initializing & Loading data from Firebase...")
load_data_from_firebase()

def setup_bot_startup():
    try:
        commands = [telebot.types.BotCommand("/start", "Re-start Bot & Open Menu")]
        bot.set_my_commands(commands)
        if RENDER_URL:
            clean_render_url = RENDER_URL.rstrip("/")
            current_webhook = bot.get_webhook_info().url
            target_webhook = f"{clean_render_url}/{TOKEN}"
            if current_webhook != target_webhook:
                bot.remove_webhook()
                time.sleep(0.5)
                bot.set_webhook(url=target_webhook)
                print(f"Webhook set to: {target_webhook}")
    except Exception as e:
        print(f"Startup webhook/command setup warning: {e}")

setup_bot_startup()
# ----------------- END FIREBASE & STARTUP HELPERS -----------------

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

LANG = {
    "en": {
        "welcome": "📍 Main Menu\n👋 Hello {user_name}!\n\nWelcome to Telegram Bot!\n\nMain Features:\n• User Center - Manage your account\n• Buy Now - Browse and buy products (Telegram, Google Voice, Gmail, VPN)\n• Recharge - Multiple payment methods\n• Support: {support_user} - 24/7 online service\n• Language - Language settings\n\nTips:\nClick the buttons below to access features!",
        "products": "📁 Select a category / product folder:",
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
        "language": "🌐 Language Settings\n\nPlease click the button below to switch language:",
        "admin": "🛠️ Welcome to Admin Panel\n\nChoose an option below:",
        "menu_products": "🛍️ Buy Now",
        "menu_account": "👤 User Center",
        "menu_deposit": "💰 Recharge",
        "menu_support": "💬 Support",
        "menu_lang": "🌐 Language",
        "menu_admin": "🛠️ Admin Panel",
        "select_qty": "🔢 Select Quantity:\n\nChoose how many items you want to buy:",
        "select_country": "🌍 Select item & specifications:",
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
        "deposit_select_amt": "Enter custom deposit amount (USDT, Min $2.5):",
        "min_network": "❌ Minimum deposit for this network is $2.50!",
        "order_created": "[ ORDER CREATED ]",
        "send_exact": "Send exactly",
        "credit_by_admin": "Your balance will be credited by admin once verified.",
        "proof_prompt": "Now please send your payment Proof / Trx Order ID / Screenshot:",
        "proof_sent": "📤 Your payment proof / Order ID has been sent to the admin successfully. Please wait for verification.",
        "txid_used": "❌ This Order ID / TxID has already been used! Each ID can only be used once for a deposit."
    },
    "zh": {
        "welcome": "📍 主菜单\n👋 你好 {user_name}！\n\n欢迎使用电报机器人！\n\n主要功能：\n• 用户中心 - 管理您的账户\n• 立即购买 - 浏览并购买产品（电报、谷歌Voice、Gmail、VPN）\n• 账户充值 - 多种支付方式\n• 客服支持：{support_user} - 7/24在线服务\n• 语言设置 - 切换语言选项\n\n提示：\n点击下方按钮访问各项功能！",
        "products": "📁 选择分类 / 产品文件夹：",
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
        "language": "🌐 语言设置\n\n请点击下方按钮切换语言：",
        "admin": "🛠️ 欢迎来到管理面板\n\n在下方选择一个选项：",
        "menu_products": "🛍️ 立即购买",
        "menu_account": "👤 用户中心",
        "menu_deposit": "💰 账户充值",
        "menu_support": "💬 客服支持",
        "menu_lang": "🌐 语言设置",
        "menu_admin": "🛠️ 管理面板",
        "select_qty": "🔢 选择数量：\n\n请选择您要购买的数量：",
        "select_country": "🌍 选择产品与规格：",
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
        "deposit_select_amt": "请输入自定义充值金额 (USDT，最低 $2.5)：",
        "min_network": "❌ 该网络最低充值金额为 $2.50！",
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

def get_main_menu_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(t["menu_products"]),
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
        types.InlineKeyboardButton("2.5 USDT", callback_data="amt_2.5"),
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
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💵 USDT (TRC20) (Min $2.5)" if lang_code == "en" else "💵 USDT (TRC20) (最低 $2.5)", callback_data="order_usdt_trc20"),
        types.InlineKeyboardButton("💵 USDT (BEP20) (Min $2.5)" if lang_code == "en" else "💵 USDT (BEP20) (最低 $2.5)", callback_data="order_usdt_bep20"),
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
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    other_qty_text = "其他数量" if lang_code == "zh" else "Other Quantity"
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("1", callback_data=f"qty_{item_key}_1"),
        types.InlineKeyboardButton("2", callback_data=f"qty_{item_key}_2"),
        types.InlineKeyboardButton("3", callback_data=f"qty_{item_key}_3"),
        types.InlineKeyboardButton("5", callback_data=f"qty_{item_key}_5"),
        types.InlineKeyboardButton("10", callback_data=f"qty_{item_key}_10"),
        types.InlineKeyboardButton(other_qty_text, callback_data=f"qty_other_{item_key}"),
        types.InlineKeyboardButton(t["back"], callback_data="back_to_products_menu")
    )
    return markup

def get_account_keyboard(user_id):
    t = LANG[get_lang(user_id)]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_products_categories_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=2)

    cat_icons = {
        "Countries": "📱 Telegram Accounts" if lang_code == "en" else "📱 电报账号",
        "Google_Voice": "📞 Google Voice" if lang_code == "en" else "📞 谷歌 Voice",
        "Gmail": "📧 Gmail Accounts" if lang_code == "en" else "📧 Gmail 邮箱",
        "VPN": "🔒 VPN Services" if lang_code == "en" else "🔒 VPN 服务"
    }

    for cat_key, cat_data in product_inventory.items():
        c_name = cat_data.get("names", {}).get(lang_code, cat_key)
        display_name = cat_icons.get(cat_key, c_name)
        markup.add(types.InlineKeyboardButton(display_name, callback_data=f"cat_{cat_key}"))

    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_category_items_keyboard(cat_key, user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=1)
    cat_data = product_inventory.get(cat_key, {})
    items = cat_data.get("items", {})

    for item_key, item_val in items.items():
        item_name = item_val.get("names", {}).get(lang_code, item_key)
        price = item_val.get("price", 0.0)
        country_code = item_val.get("code")
        display_name = f"{item_name} ({country_code})" if country_code else item_name

        zip_stock = sum(len(zf.get("extracted_files", [])) for zf in item_val.get("zip_files", []))
        total_stock = len(item_val.get("accounts", [])) + zip_stock

        btn_text = f"📦 {display_name} - ${price:.2f} [{total_stock}]"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_item_{cat_key}_{item_key}"))

    markup.add(types.InlineKeyboardButton(t["back"], callback_data="back_to_products_menu"))
    return markup

def get_language_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    btn_text = "🇨🇳 切换到中文 (Switch to Chinese)" if lang_code == "en" else "🇬🇧 Switch to English"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn_text, callback_data="lang_toggle"))
    markup.add(types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu"))
    return markup

def get_admin_panel_keyboard(user_id):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    markup = types.InlineKeyboardMarkup(row_width=1)
    if lang_code == "en":
        markup.add(
            types.InlineKeyboardButton("📱 Telegram Account Management", callback_data="admin_telegram_accounts_menu"),
            types.InlineKeyboardButton("🔒 VPN Management", callback_data="admin_vpn_menu"),
            types.InlineKeyboardButton("📧 Gmail / Google Voice Management", callback_data="admin_gmail_gv_menu"),
            types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast_start"),
            types.InlineKeyboardButton("👥 Management (Users & Balance)", callback_data="admin_management"),
            types.InlineKeyboardButton("📞 Change Support Username", callback_data="admin_change_support"),
            types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("📱 电报账号管理", callback_data="admin_telegram_accounts_menu"),
            types.InlineKeyboardButton("🔒 VPN 服务管理", callback_data="admin_vpn_menu"),
            types.InlineKeyboardButton("📧 Gmail / 谷歌Voice管理", callback_data="admin_gmail_gv_menu"),
            types.InlineKeyboardButton("📢 广播消息", callback_data="admin_broadcast_start"),
            types.InlineKeyboardButton("👥 用户管理（用户与余额）", callback_data="admin_management"),
            types.InlineKeyboardButton("📞 更改客服用户名", callback_data="admin_change_support"),
            types.InlineKeyboardButton(t["main_menu"], callback_data="go_main_menu")
        )
    return markup

def get_telegram_admin_menu_keyboard(user_id):
    lang_code = get_lang(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    if lang_code == "en":
        markup.add(
            types.InlineKeyboardButton("🗂️ Add Zip File Stock", callback_data="admin_add_zip_menu"),
            types.InlineKeyboardButton("➕ Add New Country", callback_data="admin_add_country"),
            types.InlineKeyboardButton("Country Edit/Delete", callback_data="admin_edit_delete_countries_menu"),
            types.InlineKeyboardButton("Country Price", callback_data="admin_edit_countries_price_menu"),
            types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🗂️ 添加 ZIP 文件库存", callback_data="admin_add_zip_menu"),
            types.InlineKeyboardButton("➕ 添加新国家", callback_data="admin_add_country"),
            types.InlineKeyboardButton("国家编辑/删除", callback_data="admin_edit_delete_countries_menu"),
            types.InlineKeyboardButton("国家价格设置", callback_data="admin_edit_countries_price_menu"),
            types.InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_back")
        )
    return markup

def get_vpn_admin_menu_keyboard(user_id):
    lang_code = get_lang(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    if lang_code == "en":
        markup.add(
            types.InlineKeyboardButton("➕ Add New VPN", callback_data="admin_vpn_add"),
            types.InlineKeyboardButton("✏️ VPN Edit/Delete", callback_data="admin_vpn_edit_delete"),
            types.InlineKeyboardButton("💵 VPN Price Edit", callback_data="admin_vpn_price_menu"),
            types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("➕ 添加新 VPN", callback_data="admin_vpn_add"),
            types.InlineKeyboardButton("✏️ VPN 编辑/删除", callback_data="admin_vpn_edit_delete"),
            types.InlineKeyboardButton("💵 VPN 价格修改", callback_data="admin_vpn_price_menu"),
            types.InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_back")
        )
    return markup

def get_gmail_gv_admin_menu_keyboard(user_id):
    lang_code = get_lang(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    if lang_code == "en":
        markup.add(
            types.InlineKeyboardButton("➕ Add Gmail / Google Voice", callback_data="admin_gg_add"),
            types.InlineKeyboardButton("✏️ Edit / Delete Gmail / GV", callback_data="admin_gg_edit_delete"),
            types.InlineKeyboardButton("💵 Gmail Price Edit", callback_data="admin_gmail_price_menu"),
            types.InlineKeyboardButton("💵 Google Voice Price Edit", callback_data="admin_gv_price_menu"),
            types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("➕ 添加 Gmail / 谷歌Voice", callback_data="admin_gg_add"),
            types.InlineKeyboardButton("✏️ 编辑 / 删除 Gmail / GV", callback_data="admin_gg_edit_delete"),
            types.InlineKeyboardButton("💵 Gmail 价格修改", callback_data="admin_gmail_price_menu"),
            types.InlineKeyboardButton("💵 谷歌Voice 价格修改", callback_data="admin_gv_price_menu"),
            types.InlineKeyboardButton("🔙 返回管理面板", callback_data="admin_back")
        )
    return markup

def get_management_keyboard(user_id):
    lang_code = get_lang(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    total_users = len(all_users)
    if lang_code == "en":
        markup.add(types.InlineKeyboardButton(f"👥 All Users List ({total_users})", callback_data="mgmt_users_0"))
        markup.add(types.InlineKeyboardButton("🔍 Search User by ID", callback_data="mgmt_search_user"))
        markup.add(types.InlineKeyboardButton("💰 Top Balance Users", callback_data="mgmt_top_balance"))
        markup.add(types.InlineKeyboardButton("🛠️ Back to Admin Panel", callback_data="admin_back"))
    else:
        markup.add(types.InlineKeyboardButton(f"👥 所有用户列表 ({total_users})", callback_data="mgmt_users_0"))
        markup.add(types.InlineKeyboardButton("🔍 通过 ID 搜索用户", callback_data="mgmt_search_user"))
        markup.add(types.InlineKeyboardButton("💰 余额最高用户", callback_data="mgmt_top_balance"))
        markup.add(types.InlineKeyboardButton("🛠️ 返回管理面板", callback_data="admin_back"))
    return markup

def get_users_list_keyboard(page=0, per_page=10, user_id=6954924404):
    lang_code = get_lang(user_id)
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
        prev_text = "⬅️ Prev" if lang_code == "en" else "⬅️ 上一页"
        nav.append(types.InlineKeyboardButton(prev_text, callback_data=f"mgmt_users_{page-1}"))
    if page < total_pages - 1:
        next_text = "Next ➡️" if lang_code == "en" else "下一页 ➡️"
        nav.append(types.InlineKeyboardButton(next_text, callback_data=f"mgmt_users_{page+1}"))
    if nav:
        markup.add(*nav)
    page_text = f"📄 Page {page+1}/{total_pages} | Total: {total}" if lang_code == "en" else f"📄 页码 {page+1}/{total_pages} | 总计: {total}"
    markup.add(types.InlineKeyboardButton(page_text, callback_data="noop"))
    back_text = "🔙 Back to Management" if lang_code == "en" else "🔙 返回用户管理"
    markup.add(types.InlineKeyboardButton(back_text, callback_data="admin_management"))
    return markup, total_pages, total

def get_user_detail_keyboard(target_uid, user_id=6954924404):
    lang_code = get_lang(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    if lang_code == "en":
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
    else:
        markup.add(
            types.InlineKeyboardButton("➕ 增加余额", callback_data=f"mgmt_bal_add_{target_uid}"),
            types.InlineKeyboardButton("➖ 扣除余额", callback_data=f"mgmt_bal_sub_{target_uid}"),
            types.InlineKeyboardButton("✏️ 设置余额", callback_data=f"mgmt_bal_set_{target_uid}"),
            types.InlineKeyboardButton("🔄 重置为 $0", callback_data=f"mgmt_bal_reset_{target_uid}"),
        )
        markup.add(
            types.InlineKeyboardButton("📦 购买历史", callback_data=f"mgmt_hist_pur_{target_uid}"),
            types.InlineKeyboardButton("💰 充值历史", callback_data=f"mgmt_hist_dep_{target_uid}"),
        )
        markup.add(types.InlineKeyboardButton("🔙 返回用户列表", callback_data="mgmt_users_0"))
        markup.add(types.InlineKeyboardButton("🛠️ 返回管理面板", callback_data="admin_back"))
    return markup

def get_user_detail_text(target_uid, user_id=6954924404):
    lang_code = get_lang(user_id)
    bal = user_balances.get(int(target_uid), 0.0)
    pur = user_purchases.get(int(target_uid), [])
    dep = user_deposits.get(int(target_uid), [])
    lang = user_languages.get(int(target_uid), "en")
    is_adm = "Yes 👑" if is_admin(target_uid) else ("是 👑" if lang_code == "zh" else "No")

    if lang_code == "en":
        return (
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
    else:
        return (
            f"👤 用户管理\n"
            f"──────────────────────\n"
            f"🆔 用户 ID: {target_uid}\n"
            f"💰 余额: ${bal:.2f}\n"
            f"🌐 语言: {lang}\n"
            f"👑 管理员: {is_adm}\n"
            f"📦 总购买数: {len(pur)}\n"
            f"💰 总充值数: {len(dep)}\n"
            f"──────────────────────\n"
            f"请选择操作选项以编辑余额："
        )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    ensure_user_registered(user_id)
    user_name = message.from_user.first_name or "User"
    lang_code = get_lang(user_id)
    welcome_text = LANG[lang_code]["welcome"].format(user_name=user_name, support_user=support_admin_username)
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu_keyboard(user_id))

@bot.message_handler(commands=['admin'])
def admin_command(message):
    user_id = message.from_user.id
    lang_code = get_lang(user_id)
    if not is_admin(user_id):
        err_msg = "❌ You are not authorized to use the admin panel." if lang_code == "en" else "❌ 您无权使用管理面板。"
        bot.send_message(message.chat.id, err_msg)
        return
    admin_welcome = "🛠️ Welcome to Admin Panel\n\nChoose an option below:" if lang_code == "en" else "🛠️ 欢迎来到管理面板\n\n在下方选择一个选项："
    bot.send_message(message.chat.id, admin_welcome, reply_markup=get_admin_panel_keyboard(user_id))

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    user_id = message.from_user.id
    lang_code = get_lang(user_id)
    user_states.pop(user_id, None)
    cancel_msg = "❌ Current operation cancelled." if lang_code == "en" else "❌ 当前操作已取消。"
    bot.send_message(message.chat.id, cancel_msg, reply_markup=get_main_menu_keyboard(user_id))

@bot.message_handler(content_types=['document'])
def handle_document_uploads(message):
    user_id = message.from_user.id
    lang_code = get_lang(user_id)
    if user_states.get(user_id) == "waiting_for_zip_file" and is_admin(user_id):
        country_name = temp_admin_data.get(user_id)
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        if "Countries" in product_inventory and country_name in product_inventory["Countries"]["items"]:
            temp_admin_data[f"zip_bytes_{user_id}"] = downloaded_file
            user_states[user_id] = "waiting_for_zip_2fa"
            if lang_code == "en":
                response_msg = (
                    f"✅ ZIP File uploaded successfully for Telegram Country: {country_name}!\n\n"
                    f"🔐 Now, please send the Password / 2FA Code for this ZIP file so it can be verified and read properly:"
                )
            else:
                response_msg = (
                    f"✅ 电报国家 {country_name} 的 ZIP 文件上传成功！\n\n"
                    f"🔐 现在，请发送此 ZIP 文件的密码 / 2FA 验证码以便正确验证和读取："
                )
            bot.send_message(message.chat.id, response_msg)
        else:
            err_txt = "❌ Invalid Telegram country selected." if lang_code == "en" else "❌ 选择的电报国家无效。"
            bot.send_message(message.chat.id, err_txt)
            user_states.pop(user_id, None)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio'])
def handle_all_messages(message):
    global support_admin_username
    user_id = message.from_user.id
    ensure_user_registered(user_id)

    lang_code = get_lang(user_id)
    t = LANG[lang_code]
    text = message.text if message.text else (message.caption if message.caption else "")

    # 1. Main Menu Buttons Check FIRST (Prevents getting stuck in any input state)
    is_products = text in [LANG["en"]["menu_products"], LANG["zh"]["menu_products"]]
    is_account = text in [LANG["en"]["menu_account"], LANG["zh"]["menu_account"]]
    is_deposit = text in [LANG["en"]["menu_deposit"], LANG["zh"]["menu_deposit"]]
    is_support = text in [LANG["en"]["menu_support"], LANG["zh"]["menu_support"]]
    is_lang = text in [LANG["en"]["menu_lang"], LANG["zh"]["menu_lang"]]
    is_admin_menu = text in [LANG["en"]["menu_admin"], LANG["zh"]["menu_admin"]]

    if any([is_products, is_account, is_deposit, is_support, is_lang, is_admin_menu]):
        user_states.pop(user_id, None)

        if is_lang:
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
        elif is_admin_menu:
            if not is_admin(user_id):
                unauth_txt = "❌ Unauthorized." if lang_code == "en" else "❌ 未授权。"
                bot.send_message(message.chat.id, unauth_txt)
                return
            admin_w = "🛠️ Welcome to Admin Panel\n\nChoose an option below:" if lang_code == "en" else "🛠️ 欢迎来到管理面板\n\n在下方选择一个选项："
            bot.send_message(message.chat.id, admin_w, reply_markup=get_admin_panel_keyboard(user_id))
            return
        elif is_products:
            bot.send_message(message.chat.id, t["products"], reply_markup=get_products_categories_keyboard(user_id))
            return
        elif is_deposit:
            user_states[user_id] = "waiting_for_deposit"
            bot.send_message(message.chat.id, t["deposit"], reply_markup=get_select_amount_keyboard(user_id))
            return
        elif is_account:
            user = message.from_user
            username = f"@{user.username}" if user.username else "N/A"
            name = user.first_name or "N/A"
            balance_val = user_balances.get(user_id, 0.00)
            purchased_total = len(user_purchases.get(user_id, []))
            account_text = t["account"].format(user_id=user.id, username=username, name=name, balance=balance_val, purchased_total=purchased_total)
            bot.send_message(message.chat.id, account_text, reply_markup=get_account_keyboard(user_id))
            return
        elif is_support:
            support_msg = t["support"].format(support_user=support_admin_username)
            bot.send_message(message.chat.id, support_msg)
            return

    # 2. Admin-only Input States
    state = user_states.get(user_id, "")

    if state == "waiting_for_new_support_username" and is_admin(user_id):
        new_support = text.strip()
        if not new_support:
            return
        if not new_support.startswith("@"):
            new_support = "@" + new_support
        support_admin_username = new_support
        save_support()
        user_states.pop(user_id, None)
        success_sup = f"✅ Support admin username successfully updated to: {support_admin_username}" if lang_code == "en" else f"✅ 客服管理员用户名已成功更新为: {support_admin_username}"
        bot.send_message(message.chat.id, success_sup, reply_markup=get_admin_panel_keyboard(user_id))
        return

    if state.startswith("waiting_for_vpn_price_edit_") and is_admin(user_id):
        vpn_key = state.replace("waiting_for_vpn_price_edit_", "")
        try:
            new_price = float(text.strip())
            if "VPN" in product_inventory and vpn_key in product_inventory["VPN"]["items"]:
                product_inventory["VPN"]["items"][vpn_key]["price"] = new_price
                save_inventory()
                suc_msg = f"✅ VPN price successfully updated to ${new_price:.2f}!" if lang_code == "en" else f"✅ VPN 价格已成功更新为 ${new_price:.2f}！"
                bot.send_message(message.chat.id, suc_msg, reply_markup=get_admin_panel_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, "❌ VPN package not found." if lang_code == "en" else "❌ 未找到该 VPN 套餐。")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 5.00):" if lang_code == "en" else "❌ 价格无效！请输入有效数字（例如：5.00）：")
        user_states.pop(user_id, None)
        return

    if state.startswith("waiting_for_gmail_price_edit_") and is_admin(user_id):
        gmail_key = state.replace("waiting_for_gmail_price_edit_", "")
        try:
            new_price = float(text.strip())
            if "Gmail" in product_inventory and gmail_key in product_inventory["Gmail"]["items"]:
                product_inventory["Gmail"]["items"][gmail_key]["price"] = new_price
                save_inventory()
                suc_msg = f"✅ Gmail price successfully updated to ${new_price:.2f}!" if lang_code == "en" else f"✅ Gmail 价格已成功更新为 ${new_price:.2f}！"
                bot.send_message(message.chat.id, suc_msg, reply_markup=get_admin_panel_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, "❌ Gmail package not found." if lang_code == "en" else "❌ 未找到该 Gmail 套餐。")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 0.80):" if lang_code == "en" else "❌ 价格无效！请输入有效数字（例如：0.80）：")
        user_states.pop(user_id, None)
        return

    if state.startswith("waiting_for_gv_price_edit_") and is_admin(user_id):
        gv_key = state.replace("waiting_for_gv_price_edit_", "")
        try:
            new_price = float(text.strip())
            if "Google_Voice" in product_inventory and gv_key in product_inventory["Google_Voice"]["items"]:
                product_inventory["Google_Voice"]["items"][gv_key]["price"] = new_price
                save_inventory()
                suc_msg = f"✅ Google Voice price successfully updated to ${new_price:.2f}!" if lang_code == "en" else f"✅ 谷歌Voice 价格已成功更新为 ${new_price:.2f}！"
                bot.send_message(message.chat.id, suc_msg, reply_markup=get_admin_panel_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, "❌ Google Voice package not found." if lang_code == "en" else "❌ 未找到该谷歌Voice套餐。")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 2.50):" if lang_code == "en" else "❌ 价格无效！请输入有效数字（例如：2.50）：")
        user_states.pop(user_id, None)
        return

    if state == "waiting_for_vpn_name" and is_admin(user_id):
        temp_admin_data[f"vpn_name_{user_id}"] = text.strip()
        user_states[user_id] = "waiting_for_vpn_duration"
        prompt_dur = "⏱️ Now enter the duration (e.g., 1 Month, 7 Days):" if lang_code == "en" else "⏱️ 现在输入有效时间（例如：1 Month 或 7 Days）："
        bot.send_message(message.chat.id, prompt_dur)
        return

    if state == "waiting_for_vpn_duration" and is_admin(user_id):
        temp_admin_data[f"vpn_duration_{user_id}"] = text.strip()
        user_states[user_id] = "waiting_for_vpn_price"
        prompt_prc = "💵 Now enter the price in USD (e.g., 5.00):" if lang_code == "en" else "💵 现在输入美元价格（例如：5.00）："
        bot.send_message(message.chat.id, prompt_prc)
        return

    if state == "waiting_for_vpn_price" and is_admin(user_id):
        try:
            vpn_price = float(text.strip())
            vpn_name = temp_admin_data.get(f"vpn_name_{user_id}")
            vpn_duration = temp_admin_data.get(f"vpn_duration_{user_id}")
            vpn_key = f"VPN_{int(time.time())}"

            if "VPN" not in product_inventory:
                product_inventory["VPN"] = {"type": "digital_goods", "names": {"en": "VPN Services", "zh": "VPN 服务"}, "items": {}}

            product_inventory["VPN"]["items"][vpn_key] = {
                "price": vpn_price,
                "duration": vpn_duration,
                "names": {"en": f"{vpn_name} ({vpn_duration})", "zh": f"{vpn_name} ({vpn_duration})"},
                "accounts": []
            }
            save_inventory()
            user_states.pop(user_id, None)
            suc_vpn = f"✅ VPN package '{vpn_name} ({vpn_duration})' added successfully!" if lang_code == "en" else f"✅ VPN 套餐 '{vpn_name} ({vpn_duration})' 添加成功！"
            bot.send_message(message.chat.id, suc_vpn, reply_markup=get_admin_panel_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 5.00):" if lang_code == "en" else "❌ 价格无效！请输入有效数字（例如：5.00）：")
        return

    if state.startswith("waiting_for_vpn_stock_") and is_admin(user_id):
        vpn_key = state.replace("waiting_for_vpn_stock_", "")
        lines = text.strip().split("\n")
        added_count = 0
        for line in lines:
            parts = line.strip().split(" ", 1)
            if len(parts) >= 2:
                acc_info, acc_pass = parts[0], parts[1]
                if "VPN" in product_inventory and vpn_key in product_inventory["VPN"]["items"]:
                    product_inventory["VPN"]["items"][vpn_key].setdefault("accounts", []).append({"info": acc_info, "password": acc_pass})
                    added_count += 1
        save_inventory()
        user_states.pop(user_id, None)
        suc_stk = f"✅ Successfully added {added_count} stock items to VPN!" if lang_code == "en" else f"✅ 成功为 VPN 添加了 {added_count} 个库存项目！"
        bot.send_message(message.chat.id, suc_stk, reply_markup=get_admin_panel_keyboard(user_id))
        return

    if state == "waiting_for_gg_type" and is_admin(user_id):
        gg_choice = text.strip()
        if "1" in gg_choice:
            temp_admin_data[f"gg_cat_{user_id}"] = "Gmail"
            bot.send_message(message.chat.id, "📧 Enter Gmail package name (e.g., Old Aged Gmail):" if lang_code == "en" else "📧 输入 Gmail 套餐名称（例如：老号 Gmail）：")
        else:
            temp_admin_data[f"gg_cat_{user_id}"] = "Google_Voice"
            bot.send_message(message.chat.id, "📞 Enter Google Voice package name (e.g., US Google Voice):" if lang_code == "en" else "📞 输入谷歌Voice套餐名称（例如：美国谷歌Voice）：")
        user_states[user_id] = "waiting_for_gg_name"
        return

    if state == "waiting_for_gg_name" and is_admin(user_id):
        temp_admin_data[f"gg_name_{user_id}"] = text.strip()
        user_states[user_id] = "waiting_for_gg_price"
        bot.send_message(message.chat.id, "💵 Enter price in USD (e.g., 0.80):" if lang_code == "en" else "💵 输入美元价格（例如：0.80）：")
        return

    if state == "waiting_for_gg_price" and is_admin(user_id):
        try:
            price = float(text.strip())
            cat = temp_admin_data.get(f"gg_cat_{user_id}")
            name = temp_admin_data.get(f"gg_name_{user_id}")
            key = f"{cat}_{int(time.time())}"

            if cat not in product_inventory:
                product_inventory[cat] = {"type": "digital_goods", "names": {"en": cat, "zh": cat}, "items": {}}

            product_inventory[cat]["items"][key] = {
                "price": price,
                "names": {"en": name, "zh": name},
                "accounts": []
            }
            save_inventory()
            user_states.pop(user_id, None)
            suc_cat = f"✅ Category '{name}' created successfully!" if lang_code == "en" else f"✅ 分类 '{name}' 创建成功！"
            bot.send_message(message.chat.id, suc_cat, reply_markup=get_admin_panel_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter numbers only:" if lang_code == "en" else "❌ 价格无效！请输入纯数字：")
        return

    if state.startswith("waiting_for_gg_stock_") and is_admin(user_id):
        key = state.replace("waiting_for_gg_stock_", "")
        lines = text.strip().split("\n")
        added_count = 0
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2:
                email = parts[0]
                password = parts[1]
                recovery = parts[2] if len(parts) > 2 else "N/A"

                target_cat = None
                for cat_k in ["Gmail", "Google_Voice"]:
                    if cat_k in product_inventory and key in product_inventory[cat_k]["items"]:
                        target_cat = cat_k
                        break
                if target_cat:
                    product_inventory[target_cat]["items"][key].setdefault("accounts", []).append({
                        "info": email,
                        "password": password,
                        "recovery": recovery
                    })
                    added_count += 1
        save_inventory()
        user_states.pop(user_id, None)
        suc_accs = f"✅ Successfully added {added_count} accounts/stock!" if lang_code == "en" else f"✅ 成功添加了 {added_count} 个账号/库存！"
        bot.send_message(message.chat.id, suc_accs, reply_markup=get_admin_panel_keyboard(user_id))
        return

    if state == "waiting_for_mgmt_search" and is_admin(user_id):
        user_states.pop(user_id, None)
        try:
            target = int(text.strip())
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid User ID! Please enter numbers only (e.g., 123456789):" if lang_code == "en" else "❌ 用户 ID 无效！请输入纯数字（例如：123456789）：", reply_markup=get_admin_panel_keyboard(user_id))
            return
        ensure_user_registered(target)
        bot.send_message(message.chat.id, get_user_detail_text(target, user_id), reply_markup=get_user_detail_keyboard(target, user_id))
        return

    if state.startswith("waiting_for_mgmt_bal_") and is_admin(user_id):
        parts = state.replace("waiting_for_mgmt_bal_", "").split("_")
        action = parts[0]
        target_uid = int(parts[1])
        try:
            amount = float(text.strip())
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid amount! Please enter a valid number (e.g., 10 or 5.50):" if lang_code == "en" else "❌ 金额无效！请输入有效数字（例如：10 或 5.50）：")
            return
        old_bal = user_balances.get(target_uid, 0.0)
        if action == "add":
            new_bal = old_bal + amount
            msg_action = f"➕ Added ${amount:.2f}" if lang_code == "en" else f"➕ 已增加 ${amount:.2f}"
        elif action == "sub":
            new_bal = max(0.0, old_bal - amount)
            msg_action = f"➖ Subtracted ${amount:.2f}" if lang_code == "en" else f"➖ 已扣除 ${amount:.2f}"
        elif action == "set":
            new_bal = amount
            msg_action = f"✏️ Set to ${amount:.2f}" if lang_code == "en" else f"✏️ 已设置为 ${amount:.2f}"
        else:
            new_bal = old_bal
            msg_action = ""
        user_balances[target_uid] = round(new_bal, 2)
        save_user_data(target_uid)
        user_states.pop(user_id, None)

        upd_bal_msg = (
            f"✅ Balance Updated!\n\n👤 User ID: {target_uid}\n{msg_action}\n💰 Old Balance: ${old_bal:.2f}\n💰 New Balance: ${new_bal:.2f}"
            if lang_code == "en" else
            f"✅ 余额已更新！\n\n👤 用户 ID: {target_uid}\n{msg_action}\n💰 原余额: ${old_bal:.2f}\n💰 新余额: ${new_bal:.2f}"
        )
        bot.send_message(message.chat.id, upd_bal_msg, reply_markup=get_user_detail_keyboard(target_uid, user_id))
        try:
            u_msg = f"💰 Your balance has been updated by Admin!\n\nNew Balance: ${new_bal:.2f}" if lang_code == "en" else f"💰 管理员已更新您的账户余额！\n\n新余额: ${new_bal:.2f}"
            bot.send_message(target_uid, u_msg)
        except Exception:
            pass
        return

    if state == "waiting_for_new_country" and is_admin(user_id):
        c_name = text.strip().capitalize()
        if "Countries" in product_inventory and c_name not in product_inventory["Countries"]["items"]:
            temp_admin_data[user_id] = c_name
            user_states[user_id] = "waiting_for_country_code"
            bot.send_message(message.chat.id, f"📱 Now enter country phone code for Telegram {c_name} (e.g., +880):" if lang_code == "en" else f"📱 现在为电报国家 {c_name} 输入电话区号（例如：+880）：")
        else:
            bot.send_message(message.chat.id, f"⚠️ Telegram country {c_name} already exists." if lang_code == "en" else f"⚠️ 电报国家 {c_name} 已存在。")
            user_states.pop(user_id, None)
        return

    if state == "waiting_for_country_code" and is_admin(user_id):
        c_code = text.strip()
        c_name = temp_admin_data.get(user_id)
        if c_name:
            product_inventory.setdefault("Countries", {"type": "countries", "items": {}})["items"][c_name] = {
                "code": c_code,
                "price": 1.00,
                "names": {"en": c_name, "zh": c_name},
                "accounts": [],
                "zip_files": []
            }
            save_inventory()
            bot.send_message(message.chat.id, f"✅ Telegram Country {c_name} ({c_code}) added successfully!" if lang_code == "en" else f"✅ 电报国家 {c_name} ({c_code}) 添加成功！", reply_markup=get_admin_panel_keyboard(user_id))
        user_states.pop(user_id, None)
        return

    if state.startswith("waiting_for_edit_price_") and is_admin(user_id):
        country_name = state.replace("waiting_for_edit_price_", "")
        try:
            new_price = float(text.strip())
            if "Countries" in product_inventory and country_name in product_inventory["Countries"]["items"]:
                product_inventory["Countries"]["items"][country_name]["price"] = new_price
                save_inventory()
                bot.send_message(message.chat.id, f"✅ Price for Telegram country {country_name} successfully updated to ${new_price:.2f}!" if lang_code == "en" else f"✅ 电报国家 {country_name} 的价格已成功更新为 ${new_price:.2f}！", reply_markup=get_admin_panel_keyboard(user_id))
            else:
                bot.send_message(message.chat.id, "❌ Country not found." if lang_code == "en" else "❌ 未找到该国家。")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price! Please enter a valid number (e.g., 1.50 or 2):" if lang_code == "en" else "❌ 价格无效！请输入有效数字（例如：1.50 或 2）：")
        user_states.pop(user_id, None)
        return

    if state.startswith("waiting_for_rename_country_") and is_admin(user_id):
        old_country = state.replace("waiting_for_rename_country_", "")
        new_country = text.strip().capitalize()
        proto_items = product_inventory.get("Countries", {}).get("items", {})
        if new_country in proto_items:
            bot.send_message(message.chat.id, f"⚠️ Country {new_country} already exists!" if lang_code == "en" else f"⚠️ 国家 {new_country} 已存在！")
        elif old_country in proto_items:
            proto_items[new_country] = proto_items.pop(old_country)
            if "names" in proto_items[new_country]:
                proto_items[new_country]["names"]["en"] = new_country
                proto_items[new_country]["names"]["zh"] = new_country
            save_inventory()
            bot.send_message(message.chat.id, f"✅ Successfully renamed country {old_country} to {new_country}!" if lang_code == "en" else f"✅ 成功将国家 {old_country} 重命名为 {new_country}！", reply_markup=get_admin_panel_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, "❌ Country not found." if lang_code == "en" else "❌ 未找到该国家。")
        user_states.pop(user_id, None)
        return

    if state == "waiting_for_broadcast_message" and is_admin(user_id):
        user_states.pop(user_id, None)
        success_count = 0
        fail_count = 0
        bot.send_message(message.chat.id, "⏳ Broadcasting message to all users, please wait..." if lang_code == "en" else "⏳ 正在向所有用户广播消息，请稍候...")
        for uid in list(all_users):
            try:
                bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
                success_count += 1
            except Exception:
                fail_count += 1
        bc_res = (
            f"✅ Broadcast Completed!\n\n👥 Successfully sent: {success_count} users\n❌ Failed (Blocked bot): {fail_count} users"
            if lang_code == "en" else
            f"✅ 广播完成！\n\n👥 成功发送: {success_count} 名用户\n❌ 发送失败（已拉黑机器人）: {fail_count} 名用户"
        )
        bot.send_message(message.chat.id, bc_res, reply_markup=get_main_menu_keyboard(user_id))
        return

    if state == "waiting_for_zip_2fa" and is_admin(user_id):
        tfa_code = text.strip()
        country_name = temp_admin_data.get(user_id)
        raw_zip_bytes = temp_admin_data.get(f"zip_bytes_{user_id}")
        if country_name and raw_zip_bytes and tfa_code:
            zip_bytes = io.BytesIO(raw_zip_bytes)
            try:
                with pyzipper.AESZipFile(zip_bytes, 'r') as zf:
                    zf.setpassword(tfa_code.encode('utf-8'))
                    file_list = zf.namelist()
                    valid_files = [f for f in file_list if not f.endswith('/')]
                    if not valid_files:
                        bot.send_message(message.chat.id, "❌ The ZIP archive contains no valid files.", reply_markup=get_admin_panel_keyboard(user_id))
                    else:
                        product_inventory["Countries"]["items"][country_name].setdefault("zip_files", []).append({
                            "zip_b64": base64.b64encode(raw_zip_bytes).decode('utf-8'),
                            "2fa": tfa_code,
                            "extracted_files": valid_files
                        })
                        saved = save_inventory()
                        if saved:
                            suc_z = (
                                f"✅ Successfully added & saved ZIP stock for Telegram country {country_name}!\n📁 Total valid files: {len(valid_files)}\n🔐 Password / 2FA: {tfa_code}"
                                if lang_code == "en" else
                                f"✅ 成功为电报国家 {country_name} 添加并保存 ZIP 库存！\n📁 有效文件总数: {len(valid_files)}\n🔐 密码 / 2FA: {tfa_code}"
                            )
                            bot.send_message(message.chat.id, suc_z, reply_markup=get_admin_panel_keyboard(user_id))
                        else:
                            bot.send_message(message.chat.id, "⚠️ Failed to save to Firebase! Please check file size.", reply_markup=get_admin_panel_keyboard(user_id))
            except Exception as e:
                err_pw = f"❌ Password Error!\nError details: {str(e)}" if lang_code == "en" else f"❌ 密码错误！\n错误详情: {str(e)}"
                bot.send_message(message.chat.id, err_pw, reply_markup=get_admin_panel_keyboard(user_id))
        user_states.pop(user_id, None)
        temp_admin_data.pop(user_id, None)
        temp_admin_data.pop(f"zip_bytes_{user_id}", None)
        return

    # 3. User Input States
    if state.startswith("waiting_for_txid_"):
        order_id = state.replace("waiting_for_txid_", "")
        txid_input = text.strip() if text else f"Photo_Proof_{message.message_id}"

        if txid_input.lower() in used_txids:
            bot.send_message(message.chat.id, t["txid_used"], reply_markup=get_main_menu_keyboard(user_id))
            user_states.pop(user_id, None)
            return

        used_txids.add(txid_input.lower())
        save_used_txids()
        user_states.pop(user_id, None)

        dep_amt = user_amounts.get(user_id, 2.50)
        dep_id = f"dep_{user_id}_{int(time.time())}"
        pending_deposits[dep_id] = {
            "user_id": user_id,
            "amount": dep_amt,
            "order_id": order_id,
            "txid": txid_input
        }
        save_pending_deposits()

        admin_id = ADMIN_IDS[0]
        user_name = message.from_user.first_name or "N/A"
        username = f"@{message.from_user.username}" if message.from_user.username else "N/A"

        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        admin_markup.add(
            types.InlineKeyboardButton("✅ Accept", callback_data=f"dep_accept_{dep_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{dep_id}")
        )

        admin_notification = (
            f"💰 New Deposit Request!\n"
            f"──────────────────────\n"
            f"👤 User: {user_name} ({username})\n"
            f"🆔 User ID: {user_id}\n"
            f"📦 Order ID: {order_id}\n"
            f"💵 Amount: ${dep_amt:.2f}\n"
            f"TxID / Proof: {txid_input}\n"
            f"──────────────────────\n"
            f"Click buttons below to Accept or Reject:"
        )
        try:
            bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
            bot.send_message(admin_id, admin_notification, reply_markup=admin_markup)
        except Exception as e:
            print(f"Failed to send proof to admin: {e}")

        bot.send_message(message.chat.id, t["proof_sent"], reply_markup=get_main_menu_keyboard(user_id))
        return

    if state.startswith("waiting_for_custom_qty_"):
        item_key = state.replace("waiting_for_custom_qty_", "")
        try:
            qty = int(text.strip())
            if qty <= 0:
                bot.send_message(message.chat.id, "❌ Please enter a valid quantity greater than 0:" if lang_code == "en" else "❌ 请输入大于 0 的有效数量：")
                return
            user_states.pop(user_id, None)
            process_product_purchase(message.chat.id, user_id, item_key, qty)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid number! Please enter a valid integer (e.g., 2, 5):" if lang_code == "en" else "❌ 数字无效！请输入有效的整数（例如：2, 5）：")
        return

    if state == "waiting_for_custom_amount":
        try:
            custom_amount = float(text.strip())
            min_limit = 2.50
            if custom_amount < min_limit:
                bot.send_message(message.chat.id, f"❌ Minimum deposit amount is ${min_limit:.2f}. Please enter again:" if lang_code == "en" else f"❌ 最低充值金额为 ${min_limit:.2f}。请重新输入：")
                return
            user_amounts[user_id] = custom_amount
            user_states[user_id] = "waiting_for_payment_method"
            payment_text = f"💰 Selected Amount: ${custom_amount:.2f}\n\nPlease select your preferred payment method:" if lang_code == "en" else f"💰 已选金额： ${custom_amount:.2f}\n\n请选择您的首选付款方式："
            bot.send_message(message.chat.id, payment_text, reply_markup=get_payment_methods_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid amount. Please enter a valid number (e.g., 5 or 10):" if lang_code == "en" else "❌ 金额无效。请输入有效数字（例如：5 或 10）：")
        return

def process_product_purchase(chat_id, user_id, item_key, qty):
    lang_code = get_lang(user_id)
    t = LANG[lang_code]

    target_item = None
    for cat_k, cat_v in product_inventory.items():
        if item_v := cat_v.get("items", {}).get(item_key):
            target_item = item_v
            break

    if target_item is None:
        bot.send_message(chat_id, "❌ Product not found." if lang_code == "en" else "❌ 未找到产品。")
        return

    price_per_unit = target_item.get("price", 1.00)
    zip_list = target_item.get("zip_files", [])
    accounts_list = target_item.get("accounts", [])

    zip_total_files = sum(len(zf.get("extracted_files", [])) for zf in zip_list)
    total_stock = len(accounts_list) + zip_total_files
    if total_stock < qty:
        bot.send_message(chat_id, f"{t['insufficient_stock']} {total_stock} items.", reply_markup=get_main_menu_keyboard(user_id))
        return

    total_price = round(price_per_unit * qty, 2)
    user_balance = user_balances.get(user_id, 0.00)
    if user_balance < total_price:
        bal_err_txt = f"{t['insufficient_balance']} ${total_price:.2f}\n{t['balance_text']} ${user_balance:.2f}"
        bot.send_message(chat_id, bal_err_txt, reply_markup=get_main_menu_keyboard(user_id))
        return

    delivered_count = 0
    for _ in range(qty):
        try:
            while len(zip_list) > 0 and len(zip_list[0].get("extracted_files", [])) == 0:
                zip_list.pop(0)

            if len(zip_list) > 0:
                zip_item = zip_list[0]
                if "zip_b64" in zip_item:
                    orig_zip_bytes = base64.b64decode(zip_item["zip_b64"])
                else:
                    orig_zip_bytes = bytes(zip_item["zip_bytes"])
                tfa_code = zip_item["2fa"]
                files_in_zip = zip_item["extracted_files"]
                target_file_name = files_in_zip[0]

                single_zip_buffer = io.BytesIO()
                with pyzipper.AESZipFile(single_zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as new_zip:
                    new_zip.setpassword(tfa_code.encode('utf-8'))
                    with pyzipper.AESZipFile(io.BytesIO(orig_zip_bytes), 'r') as orig_zip:
                        orig_zip.setpassword(tfa_code.encode('utf-8'))
                        file_data = orig_zip.read(target_file_name)
                        new_zip.writestr(os.path.basename(target_file_name), file_data)
                single_zip_buffer.seek(0)

                files_in_zip.pop(0)
                if len(files_in_zip) == 0:
                    zip_list.pop(0)

                user_balances[user_id] = round(user_balances.get(user_id, 0.0) - price_per_unit, 2)
                purchase_text = f"Bought {item_key} (ZIP file) for ${price_per_unit:.2f}"
                user_purchases.setdefault(user_id, []).append({"text": purchase_text, "timestamp": time.time()})
                delivered_count += 1

                file_short_name = os.path.basename(target_file_name)
                if lang_code == "en":
                    caption_text = f"✅ Purchase Successful!\n\n📦 Item: {item_key}\n📁 File: {file_short_name}\n🔐 2FA & ZIP Password: {tfa_code}\n💵 Paid: ${price_per_unit:.2f}\n\nRemaining Balance: ${user_balances[user_id]:.2f}"
                else:
                    caption_text = f"✅ 购买成功！\n\n📦 项目: {item_key}\n📁 文件: {file_short_name}\n🔐 2FA & ZIP 密码: {tfa_code}\n💵 支付: ${price_per_unit:.2f}\n\n剩余余额: ${user_balances[user_id]:.2f}"

                bot.send_document(
                    chat_id,
                    document=single_zip_buffer,
                    visible_file_name=f"{item_key}_{file_short_name}.zip",
                    caption=caption_text
                )
            elif len(accounts_list) > 0:
                purchased_item = accounts_list.pop(0)
                user_balances[user_id] = round(user_balances.get(user_id, 0.0) - price_per_unit, 2)
                delivered_count += 1

                if "number" in purchased_item:
                    acc_num = purchased_item.get("number", "N/A")
                    acc_2fa = purchased_item.get("2fa", "N/A")
                    purchase_text = f"Bought {item_key}: {acc_num} for ${price_per_unit:.2f}"
                    user_purchases.setdefault(user_id, []).append({"text": purchase_text, "timestamp": time.time()})

                    if lang_code == "en":
                        success_text = (
                            f"✅ **Purchase Successful!**\n\n"
                            f"📦 Country: `{item_key}`\n"
                            f"📱 Telegram Number: `{acc_num}`\n"
                            f"🔐 2FA Code: `{acc_2fa}`\n"
                            f"💵 Paid: `${price_per_unit:.2f}`\n\n"
                            f"Remaining Balance: `${user_balances[user_id]:.2f}`"
                        )
                    else:
                        success_text = (
                            f"✅ **购买成功！**\n\n"
                            f"📦 国家: `{item_key}`\n"
                            f"📱 电报号码: `{acc_num}`\n"
                            f"🔐 2FA 验证码: `{acc_2fa}`\n"
                            f"💵 支付: `${price_per_unit:.2f}`\n\n"
                            f"剩余余额: `${user_balances[user_id]:.2f}`"
                        )
                else:
                    acc_info = purchased_item.get("info", "N/A")
                    acc_pass = purchased_item.get("password", "N/A")
                    acc_rec = purchased_item.get("recovery", "")
                    rec_text = f"\n🛡️ Recovery: `{acc_rec}`" if acc_rec and acc_rec != "N/A" else ""

                    purchase_text = f"Bought {item_key}: {acc_info} for ${price_per_unit:.2f}"
                    user_purchases.setdefault(user_id, []).append({"text": purchase_text, "timestamp": time.time()})

                    if lang_code == "en":
                        success_text = (
                            f"✅ **Purchase Successful!**\n\n"
                            f"📦 Product: `{item_key}`\n"
                            f"📧 Username/Email: `{acc_info}`\n"
                            f"🔑 Password: `{acc_pass}`{rec_text}\n"
                            f"💵 Paid: `${price_per_unit:.2f}`\n\n"
                            f"Remaining Balance: `${user_balances[user_id]:.2f}`"
                        )
                    else:
                        success_text = (
                            f"✅ **购买成功！**\n\n"
                            f"📦 产品: `{item_key}`\n"
                            f"📧 用户名/邮箱: `{acc_info}`\n"
                            f"🔑 密码: `{acc_pass}`{rec_text}\n"
                            f"💵 支付: `${price_per_unit:.2f}`\n\n"
                            f"剩余余额: `${user_balances[user_id]:.2f}`"
                        )
                bot.send_message(chat_id, success_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Error in delivering product: {e}")
            bot.send_message(chat_id, f"❌ Error delivering item: {str(e)}" if lang_code == "en" else f"❌ 发货出错: {str(e)}")
            break

    if delivered_count > 0:
        save_user_data(user_id)
        save_inventory()

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_clicks(call):
    user_id = call.from_user.id
    ensure_user_registered(user_id)

    lang_code = get_lang(user_id)
    t = LANG[lang_code]

    if call.data == "admin_change_support":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_new_support_username"
        bot.answer_callback_query(call.id, "Change Support Username")
        try:
            sup_prompt = "📞 Change Support Username\n\nPlease send new support username (e.g., @YourUsername):" if lang_code == "en" else "📞 更改客服用户名\n\n请发送新的客服用户名（例如：@YourUsername）："
            bot.edit_message_text(sup_prompt, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_telegram_accounts_menu":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id, "Telegram Accounts Menu")
        try:
            tg_txt = "📱 Telegram Account Management\n\nChoose an option below:" if lang_code == "en" else "📱 电报账号管理\n\n在下方选择一个选项："
            bot.edit_message_text(tg_txt, call.message.chat.id, call.message.message_id, reply_markup=get_telegram_admin_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data == "admin_vpn_menu":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id, "VPN Management")
        try:
            vpn_m_txt = "🔒 VPN Management\n\nChoose an option below:" if lang_code == "en" else "🔒 VPN 服务管理\n\n在下方选择一个选项："
            bot.edit_message_text(vpn_m_txt, call.message.chat.id, call.message.message_id, reply_markup=get_vpn_admin_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data == "admin_gmail_gv_menu":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id, "Gmail/GV Management")
        try:
            gg_m_txt = "📧 Gmail & Google Voice Management\n\nChoose an option below:" if lang_code == "en" else "📧 Gmail & 谷歌Voice管理\n\n在下方选择一个选项："
            bot.edit_message_text(gg_m_txt, call.message.chat.id, call.message.message_id, reply_markup=get_gmail_gv_admin_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data == "admin_vpn_price_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        vpn_items = product_inventory.get("VPN", {}).get("items", {})
        for k, v in vpn_items.items():
            name = v.get("names", {}).get(lang_code, k)
            price = v.get("price", 0.0)
            markup.add(types.InlineKeyboardButton(f"💵 {name} (${price:.2f}) - Edit Price" if lang_code == "en" else f"💵 {name} (${price:.2f}) - 修改价格", callback_data=f"vpn_edit_price_{k}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_vpn_menu"))
        bot.answer_callback_query(call.id, "VPN Price Menu")
        try:
            bot.edit_message_text("💵 VPN Price Management:\nSelect a VPN package to change its price:" if lang_code == "en" else "💵 VPN 价格管理：\n选择要更改价格的 VPN 套餐：", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("vpn_edit_price_"):
        if not is_admin(user_id):
            return
        vpn_key = call.data.replace("vpn_edit_price_", "")
        user_states[user_id] = f"waiting_for_vpn_price_edit_{vpn_key}"
        curr_price = product_inventory["VPN"]["items"].get(vpn_key, {}).get("price", 0.0)
        bot.answer_callback_query(call.id, "Edit VPN Price")
        try:
            p_text = f"💵 Enter new price for VPN (Current: ${curr_price:.2f}):" if lang_code == "en" else f"💵 输入 VPN 的新价格（当前: ${curr_price:.2f}）："
            bot.edit_message_text(p_text, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_gmail_price_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        gmail_items = product_inventory.get("Gmail", {}).get("items", {})
        for k, v in gmail_items.items():
            name = v.get("names", {}).get(lang_code, k)
            price = v.get("price", 0.0)
            markup.add(types.InlineKeyboardButton(f"💵 {name} (${price:.2f}) - Edit Price" if lang_code == "en" else f"💵 {name} (${price:.2f}) - 修改价格", callback_data=f"gmail_edit_price_{k}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_gmail_gv_menu"))
        bot.answer_callback_query(call.id, "Gmail Price Menu")
        try:
            bot.edit_message_text("💵 Gmail Price Management:\nSelect a Gmail package to change its price:" if lang_code == "en" else "💵 Gmail 价格管理：\n选择要更改价格的 Gmail 套餐：", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("gmail_edit_price_"):
        if not is_admin(user_id):
            return
        gmail_key = call.data.replace("gmail_edit_price_", "")
        user_states[user_id] = f"waiting_for_gmail_price_edit_{gmail_key}"
        curr_price = product_inventory["Gmail"]["items"].get(gmail_key, {}).get("price", 0.0)
        bot.answer_callback_query(call.id, "Edit Gmail Price")
        try:
            p_text = f"💵 Enter new price for Gmail (Current: ${curr_price:.2f}):" if lang_code == "en" else f"💵 输入 Gmail 的新价格（当前: ${curr_price:.2f}）："
            bot.edit_message_text(p_text, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_gv_price_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        gv_items = product_inventory.get("Google_Voice", {}).get("items", {})
        for k, v in gv_items.items():
            name = v.get("names", {}).get(lang_code, k)
            price = v.get("price", 0.0)
            markup.add(types.InlineKeyboardButton(f"💵 {name} (${price:.2f}) - Edit Price" if lang_code == "en" else f"💵 {name} (${price:.2f}) - 修改价格", callback_data=f"gv_edit_price_{k}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_gmail_gv_menu"))
        bot.answer_callback_query(call.id, "Google Voice Price Menu")
        try:
            bot.edit_message_text("💵 Google Voice Price Management:\nSelect a Google Voice package to change its price:" if lang_code == "en" else "💵 谷歌Voice 价格管理：\n选择要更改价格的谷歌Voice套餐：", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("gv_edit_price_"):
        if not is_admin(user_id):
            return
        gv_key = call.data.replace("gv_edit_price_", "")
        user_states[user_id] = f"waiting_for_gv_price_edit_{gv_key}"
        curr_price = product_inventory["Google_Voice"]["items"].get(gv_key, {}).get("price", 0.0)
        bot.answer_callback_query(call.id, "Edit Google Voice Price")
        try:
            p_text = f"💵 Enter new price for Google Voice (Current: ${curr_price:.2f}):" if lang_code == "en" else f"💵 输入谷歌Voice的新价格（当前: ${curr_price:.2f}）："
            bot.edit_message_text(p_text, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_vpn_add":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_vpn_name"
        bot.answer_callback_query(call.id, "Add VPN")
        try:
            vpn_add_txt = "🔒 Enter VPN Package Name (e.g., ExpressVPN / NordVPN):\n(Do NOT include duration here, it will be asked next)" if lang_code == "en" else "🔒 输入 VPN 套餐名称（例如：ExpressVPN / NordVPN）：\n（请勿在此包含时长，下一步会询问）"
            bot.edit_message_text(vpn_add_txt, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_vpn_edit_delete":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        vpn_items = product_inventory.get("VPN", {}).get("items", {})
        for k, v in vpn_items.items():
            name = v.get("names", {}).get(lang_code, k)
            if lang_code == "en":
                markup.add(
                    types.InlineKeyboardButton(f"➕ Add Stock: {name}", callback_data=f"vpn_add_stock_{k}"),
                    types.InlineKeyboardButton(f"❌ Delete: {name}", callback_data=f"vpn_del_{k}")
                )
            else:
                markup.add(
                    types.InlineKeyboardButton(f"➕ 添加库存: {name}", callback_data=f"vpn_add_stock_{k}"),
                    types.InlineKeyboardButton(f"❌ 删除: {name}", callback_data=f"vpn_del_{k}")
                )
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_vpn_menu"))
        bot.answer_callback_query(call.id, "VPN Edit/Delete")
        try:
            vpn_ed_txt = "🔒 Select VPN to add stock or delete:" if lang_code == "en" else "🔒 选择要添加库存或删除的 VPN："
            bot.edit_message_text(vpn_ed_txt, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("vpn_add_stock_"):
        if not is_admin(user_id):
            return
        vpn_key = call.data.replace("vpn_add_stock_", "")
        user_states[user_id] = f"waiting_for_vpn_stock_{vpn_key}"
        bot.answer_callback_query(call.id, "Add Stock")
        try:
            vpn_stk_txt = "📥 Send stock accounts in format:\n`username password` (one per line):" if lang_code == "en" else "📥 发送库存账号格式：\n`username password`（每行一个）："
            bot.edit_message_text(vpn_stk_txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        except Exception:
            pass
        return

    if call.data.startswith("vpn_del_"):
        if not is_admin(user_id):
            return
        vpn_key = call.data.replace("vpn_del_", "")
        if vpn_key in product_inventory.get("VPN", {}).get("items", {}):
            del product_inventory["VPN"]["items"][vpn_key]
            save_inventory()
            bot.answer_callback_query(call.id, "VPN Deleted Successfully!" if lang_code == "en" else "VPN 删除成功！", show_alert=True)
        try:
            vpn_del_suc = "✅ VPN package deleted successfully!" if lang_code == "en" else "✅ VPN 套餐删除成功！"
            bot.edit_message_text(vpn_del_suc, call.message.chat.id, call.message.message_id, reply_markup=get_vpn_admin_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data == "admin_gg_add":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_gg_type"
        bot.answer_callback_query(call.id, "Add Gmail/GV")
        try:
            gg_add_p = "📧 Choose Category to Add:\n\n1. Gmail Accounts\n2. Google Voice\n\n(Send 1 or 2):" if lang_code == "en" else "📧 选择要添加的分类：\n\n1. Gmail 邮箱\n2. 谷歌 Voice\n\n（发送 1 或 2）："
            bot.edit_message_text(gg_add_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data == "admin_gg_edit_delete":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for cat_k in ["Gmail", "Google_Voice"]:
            items = product_inventory.get(cat_k, {}).get("items", {})
            for k, v in items.items():
                name = v.get("names", {}).get(lang_code, k)
                if lang_code == "en":
                    markup.add(
                        types.InlineKeyboardButton(f"➕ Add Stock ({cat_k}): {name}", callback_data=f"gg_add_stock_{k}"),
                        types.InlineKeyboardButton(f"❌ Delete: {name}", callback_data=f"gg_del_{k}")
                    )
                else:
                    markup.add(
                        types.InlineKeyboardButton(f"➕ 添加库存 ({cat_k}): {name}", callback_data=f"gg_add_stock_{k}"),
                        types.InlineKeyboardButton(f"❌ 删除: {name}", callback_data=f"gg_del_{k}")
                    )
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_gmail_gv_menu"))
        bot.answer_callback_query(call.id, "Gmail/GV Edit/Delete")
        try:
            gg_ed_txt = "📧 Select Gmail or Google Voice to add stock or delete:" if lang_code == "en" else "📧 选择要添加库存或删除的 Gmail 或 谷歌Voice："
            bot.edit_message_text(gg_ed_txt, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("gg_add_stock_"):
        if not is_admin(user_id):
            return
        gg_key = call.data.replace("gg_add_stock_", "")
        user_states[user_id] = f"waiting_for_gg_stock_{gg_key}"
        bot.answer_callback_query(call.id, "Add Stock")
        try:
            gg_s_txt = "📥 Send accounts stock in format (one per line):\n`email password [recovery]` (Recovery optional):" if lang_code == "en" else "📥 发送账号库存格式（每行一个）：\n`email password [recovery]`（辅助邮箱可选）："
            bot.edit_message_text(gg_s_txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        except Exception:
            pass
        return

    if call.data.startswith("gg_del_"):
        if not is_admin(user_id):
            return
        gg_key = call.data.replace("gg_del_", "")
        for cat_k in ["Gmail", "Google_Voice"]:
            if gg_key in product_inventory.get(cat_k, {}).get("items", {}):
                del product_inventory[cat_k]["items"][gg_key]
                save_inventory()
                break
        bot.answer_callback_query(call.id, "Item Deleted Successfully!" if lang_code == "en" else "项目删除成功！", show_alert=True)
        try:
            item_del_suc = "✅ Item deleted successfully!" if lang_code == "en" else "✅ 项目删除成功！"
            bot.edit_message_text(item_del_suc, call.message.chat.id, call.message.message_id, reply_markup=get_gmail_gv_admin_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data.startswith("dep_accept_") or call.data.startswith("dep_reject_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized" if lang_code == "en" else "未授权", show_alert=True)
            return

        action = "accept" if "accept" in call.data else "reject"
        dep_id = call.data.replace("dep_accept_", "").replace("dep_reject_", "")

        if dep_id in pending_deposits:
            dep_info = pending_deposits.pop(dep_id)
            save_pending_deposits()

            target_uid = int(dep_info["user_id"])
            amount = float(dep_info["amount"])
            order_id = dep_info["order_id"]

            if action == "accept":
                old_bal = user_balances.get(target_uid, 0.0)
                new_bal = round(old_bal + amount, 2)
                user_balances[target_uid] = new_bal

                user_deposits.setdefault(target_uid, []).append({
                    "text": f"Deposited ${amount:.2f} (Order: {order_id})",
                    "timestamp": time.time()
                })
                save_user_data(target_uid)

                bot.answer_callback_query(call.id, "Deposit Accepted & Credited!" if lang_code == "en" else "充值已接受并到账！", show_alert=True)
                try:
                    acc_edit_txt = f"✅ Deposit Accepted!\nOrder ID: {order_id}\nCredited Amount: ${amount:.2f} to User {target_uid}" if lang_code == "en" else f"✅ 充值已接受！\n订单号: {order_id}\n已向用户 {target_uid} 入账: ${amount:.2f}"
                    bot.edit_message_text(acc_edit_txt, call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
                try:
                    u_acc_msg = f"✅ Your deposit has been accepted successfully!\n\n💰 ${amount:.2f} has been credited to your account." if lang_code == "en" else f"✅ 您的充值已被成功受理！\n\n💰 ${amount:.2f} 已存入您的账户。"
                    bot.send_message(target_uid, u_acc_msg)
                except Exception:
                    pass
            else:
                txid_val = dep_info.get("txid", "")
                if txid_val and txid_val.lower() in used_txids:
                    used_txids.remove(txid_val.lower())
                    save_used_txids()

                bot.answer_callback_query(call.id, "Deposit Rejected!" if lang_code == "en" else "充值已被拒绝！", show_alert=True)
                try:
                    rej_edit_txt = f"❌ Deposit Rejected!\nOrder ID: {order_id} for User {target_uid}" if lang_code == "en" else f"❌ 充值已被拒绝！\n用户 {target_uid} 的订单号: {order_id}"
                    bot.edit_message_text(rej_edit_txt, call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
                try:
                    u_rej_msg = f"❌ Sorry, your deposit request has been rejected by admin.\nOrder ID: {order_id}" if lang_code == "en" else f"❌ 很抱歉，您的充值请求已被管理员拒绝。\n订单号: {order_id}"
                    bot.send_message(target_uid, u_rej_msg)
                except Exception:
                    pass
        else:
            bot.answer_callback_query(call.id, "Request already processed or expired!" if lang_code == "en" else "请求已处理或已过期！", show_alert=True)
        return

    if call.data.startswith("send_order_id_"):
        order_id = call.data.replace("send_order_id_", "")
        user_states[user_id] = f"waiting_for_txid_{order_id}"
        bot.answer_callback_query(call.id, "Send Order ID / TxID")

        if lang_code == "en":
            prompt_text = f"📤 Please send your payment Transaction ID (TxID) or Proof:\n\nOrder ID: {order_id}"
        else:
            prompt_text = f"📤 请发送您的付款交易单号 (TxID) 或凭证截图：\n\n订单号: {order_id}"
        try:
            bot.edit_message_text(prompt_text, call.message.chat.id, call.message.message_id)
        except Exception:
            bot.send_message(call.message.chat.id, prompt_text)
        return

    if call.data == "admin_management":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "Unauthorized" if lang_code == "en" else "未授权", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Management")
        total_users = len(all_users)
        text = (
            f"👥 Management\n──────────────────────\n👥 Total Users: {total_users}\n──────────────────────\nSelect option below:"
            if lang_code == "en" else
            f"👥 用户管理\n──────────────────────\n👥 总用户数: {total_users}\n──────────────────────\n请在下方选择选项："
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_management_keyboard(user_id))
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=get_management_keyboard(user_id))
        return

    if call.data.startswith("mgmt_users_"):
        if not is_admin(user_id):
            return
        try:
            page = int(call.data.replace("mgmt_users_", ""))
        except Exception:
            page = 0
        bot.answer_callback_query(call.id, f"Page {page+1}")
        markup, total_pages, total = get_users_list_keyboard(page, 10, user_id)
        text = (
            f"👥 All Users List\n──────────────────────\nTotal Users: {total}\nClick a user to edit balance:"
            if lang_code == "en" else
            f"👥 所有用户列表\n──────────────────────\n总用户数: {total}\n点击用户可编辑余额："
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data == "mgmt_search_user":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_mgmt_search"
        bot.answer_callback_query(call.id, "Search User")
        try:
            s_u_txt = "🔍 Search User\n\nPlease send User ID (e.g., 123456789):" if lang_code == "en" else "🔍 搜索用户\n\n请发送用户 ID（例如：123456789）："
            bot.edit_message_text(s_u_txt, call.message.chat.id, call.message.message_id)
        except Exception:
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
        back_m_txt = "🔙 Back to Management" if lang_code == "en" else "🔙 返回用户管理"
        markup.add(types.InlineKeyboardButton(back_m_txt, callback_data="admin_management"))
        try:
            top_txt = "💰 Top 10 Balance Users:" if lang_code == "en" else "💰 余额最高的 10 位用户："
            bot.edit_message_text(top_txt, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("mgmt_user_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_user_", ""))
        bot.answer_callback_query(call.id, f"User {target_uid}")
        try:
            bot.edit_message_text(get_user_detail_text(target_uid, user_id), call.message.chat.id, call.message.message_id, reply_markup=get_user_detail_keyboard(target_uid, user_id))
        except Exception:
            bot.send_message(call.message.chat.id, get_user_detail_text(target_uid, user_id), reply_markup=get_user_detail_keyboard(target_uid, user_id))
        return

    if call.data.startswith("mgmt_bal_add_") or call.data.startswith("mgmt_bal_sub_") or call.data.startswith("mgmt_bal_set_"):
        if not is_admin(user_id):
            return
        rest = call.data.replace("mgmt_bal_", "")
        action, target_uid = rest.split("_")
        user_states[user_id] = f"waiting_for_mgmt_bal_{action}_{target_uid}"
        old_bal = user_balances.get(int(target_uid), 0.0)

        if lang_code == "en":
            label = {"add": "➕ Add Balance", "sub": "➖ Subtract Balance", "set": "✏️ Set Balance"}[action]
            bal_edit_p = f"{label}\n\n👤 User ID: {target_uid}\n💰 Current Balance: ${old_bal:.2f}\n\nPlease send amount (e.g., 10):"
        else:
            label = {"add": "➕ 增加余额", "sub": "➖ 扣除余额", "set": "✏️ 设置余额"}[action]
            bal_edit_p = f"{label}\n\n👤 用户 ID: {target_uid}\n💰 当前余额: ${old_bal:.2f}\n\n请发送金额（例如：10）："

        bot.answer_callback_query(call.id, label)
        try:
            bot.edit_message_text(bal_edit_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data.startswith("mgmt_bal_reset_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_bal_reset_", ""))
        old_bal = user_balances.get(target_uid, 0.0)
        user_balances[target_uid] = 0.0
        save_user_data(target_uid)
        bot.answer_callback_query(call.id, "Balance Reset to $0" if lang_code == "en" else "余额已重置为 $0", show_alert=True)
        try:
            res_txt = (
                f"✅ Balance Reset!\n\n👤 User ID: {target_uid}\n💰 Old: ${old_bal:.2f} → New: $0.00"
                if lang_code == "en" else
                f"✅ 余额已重置！\n\n👤 用户 ID: {target_uid}\n💰 原余额: ${old_bal:.2f} → 新余额: $0.00"
            )
            bot.edit_message_text(res_txt, call.message.chat.id, call.message.message_id, reply_markup=get_user_detail_keyboard(target_uid, user_id))
        except Exception:
            pass
        try:
            bot.send_message(target_uid, "💰 Your balance has been reset to $0.00 by Admin." if lang_code == "en" else "💰 管理员已将您的余额重置为 $0.00。")
        except Exception:
            pass
        return

    if call.data.startswith("mgmt_hist_pur_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_hist_pur_", ""))
        pur = user_purchases.get(target_uid, [])
        no_pur = "No purchases yet." if lang_code == "en" else "暂无购买记录。"
        txt = "\n".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in pur[-20:]]) or no_pur
        bot.answer_callback_query(call.id, "Purchase History" if lang_code == "en" else "购买历史")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back" if lang_code == "en" else "🔙 返回", callback_data=f"mgmt_user_{target_uid}"))
        try:
            bot.edit_message_text(f"📦 Purchase History - {target_uid}\n──────────────────────\n{txt}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    if call.data.startswith("mgmt_hist_dep_"):
        if not is_admin(user_id):
            return
        target_uid = int(call.data.replace("mgmt_hist_dep_", ""))
        dep = user_deposits.get(target_uid, [])
        no_dep = "No deposits yet." if lang_code == "en" else "暂无充值记录。"
        txt = "\n".join([d.get("text", "") if isinstance(d, dict) else str(d) for d in dep[-20:]]) or no_dep
        bot.answer_callback_query(call.id, "Deposit History" if lang_code == "en" else "充值历史")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back" if lang_code == "en" else "🔙 返回", callback_data=f"mgmt_user_{target_uid}"))
        try:
            bot.edit_message_text(f"💰 Deposit History - {target_uid}\n──────────────────────\n{txt}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
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
            bot.edit_message_text(t["language"], call.message.chat.id, call.message.message_id, reply_markup=get_language_keyboard(user_id))
        except Exception:
            pass
        try:
            bot.send_message(call.message.chat.id, "👇 Menu updated:" if lang_code == "en" else "👇 菜单已更新：", reply_markup=get_main_menu_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data == "back_to_account":
        bot.answer_callback_query(call.id, "Account Menu")
        user = call.from_user
        username = f"@{user.username}" if user.username else "N/A"
        name = user.first_name or "N/A"
        balance_val = user_balances.get(user_id, 0.00)
        purchased_total = len(user_purchases.get(user_id, []))
        account_text = t["account"].format(user_id=user.id, username=username, name=name, balance=balance_val, purchased_total=purchased_total)
        try:
            bot.edit_message_text(account_text, call.message.chat.id, call.message.message_id, reply_markup=get_account_keyboard(user_id))
        except Exception:
            pass
        return

    if call.data.startswith("qty_other_"):
        item_key = call.data.replace("qty_other_", "")
        user_states[user_id] = f"waiting_for_custom_qty_{item_key}"
        bot.answer_callback_query(call.id, "Enter custom quantity" if lang_code == "en" else "输入自定义数量")
        bot.send_message(call.message.chat.id, "🔢 Please enter the quantity you want to buy (e.g., 4, 15):" if lang_code == "en" else "🔢 请输入您要购买的数量（例如：4, 15）：")
        return

    if call.data.startswith("qty_"):
        remainder = call.data.replace("qty_", "")
        last_underscore = remainder.rfind("_")
        item_key = remainder[:last_underscore]
        qty = int(remainder[last_underscore + 1:])
        bot.answer_callback_query(call.id, f"Selected {qty} qty" if lang_code == "en" else f"已选择 {qty} 个")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        process_product_purchase(call.message.chat.id, user_id, item_key, qty)
        return

    elif call.data.startswith("cat_"):
        cat_key = call.data.replace("cat_", "")
        bot.answer_callback_query(call.id, cat_key)
        try:
            cat_name = product_inventory.get(cat_key, {}).get("names", {}).get(lang_code, cat_key)
            category_text = (
                f"📁 Category: {cat_name}\n\nSelect an item below to buy:"
                if lang_code == "en" else
                f"📁 分类: {cat_name}\n\n请在下方选择要购买的项目："
            )
            bot.edit_message_text(category_text, call.message.chat.id, call.message.message_id, reply_markup=get_category_items_keyboard(cat_key, user_id))
        except Exception:
            pass
        return

    elif call.data.startswith("buy_item_"):
        parts = call.data.replace("buy_item_", "").split("_", 1)
        cat_key = parts[0]
        item_key = parts[1]
        bot.answer_callback_query(call.id, item_key)

        target_item = product_inventory.get(cat_key, {}).get("items", {}).get(item_key, {})
        price = target_item.get("price", 1.00)
        duration = f" ({target_item.get('duration')})" if target_item.get('duration') else ""

        zip_stock = sum(len(zf.get("extracted_files", [])) for zf in target_item.get("zip_files", []))
        stock_count = len(target_item.get("accounts", [])) + zip_stock

        markup = types.InlineKeyboardMarkup(row_width=1)
        cart_sel_text = "🛒 Select Quantity" if lang_code == "en" else "🛒 选择数量"
        markup.add(
            types.InlineKeyboardButton(cart_sel_text, callback_data=f"buy_confirm_{item_key}"),
            types.InlineKeyboardButton(t["back"], callback_data=f"cat_{cat_key}")
        )
        try:
            if lang_code == "en":
                item_detail_text = f"📦 Product: {item_key}{duration}\n\n💰 Price: ${price:.2f}\n📦 Available {t['stock']}: {stock_count} items\n\nClick below to proceed to quantity selection:"
            else:
                item_detail_text = f"📦 产品: {item_key}{duration}\n\n💰 价格: ${price:.2f}\n📦 可用{t['stock']}: {stock_count} 件\n\n点击下方继续选择数量："
            bot.edit_message_text(item_detail_text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("buy_confirm_"):
        item_key = call.data.replace("buy_confirm_", "")
        bot.answer_callback_query(call.id, item_key)
        try:
            proto_qty_text = (
                f"🔢 Select Quantity for {item_key}:\n\nChoose how many items you want to buy:"
                if lang_code == "en" else
                f"🔢 选择 {item_key} 的数量：\n\n请选择您要购买的数量："
            )
            bot.edit_message_text(proto_qty_text, call.message.chat.id, call.message.message_id, reply_markup=get_quantity_keyboard(item_key, user_id))
        except Exception:
            pass
        return

    elif call.data == "admin_broadcast_start":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_broadcast_message"
        bot.answer_callback_query(call.id, "Broadcast Mode")
        try:
            bc_p = "📢 Broadcast System\n\nPlease send the message, photo, video or file that you want to send to all users:" if lang_code == "en" else "📢 广播系统\n\n请发送您要群发给所有用户的消息、照片、视频或文件："
            bot.edit_message_text(bc_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_add_country":
        if not is_admin(user_id):
            return
        user_states[user_id] = "waiting_for_new_country"
        bot.answer_callback_query(call.id, "Add Telegram Country")
        try:
            add_c_p = "🌍 Enter new Telegram country name (e.g., Canada):" if lang_code == "en" else "🌍 输入新电报国家名称（例如：Canada）："
            bot.edit_message_text(add_c_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_edit_delete_countries_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        proto_items = product_inventory.get("Countries", {}).get("items", {})
        if proto_items:
            for c_name in proto_items.keys():
                if lang_code == "en":
                    markup.add(
                        types.InlineKeyboardButton(f"✏️ Rename: {c_name}", callback_data=f"admin_rename_country_{c_name}"),
                        types.InlineKeyboardButton(f"❌ Delete: {c_name}", callback_data=f"admin_delete_country_{c_name}")
                    )
                else:
                    markup.add(
                        types.InlineKeyboardButton(f"✏️ 重命名: {c_name}", callback_data=f"admin_rename_country_{c_name}"),
                        types.InlineKeyboardButton(f"❌ 删除: {c_name}", callback_data=f"admin_delete_country_{c_name}")
                    )
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_telegram_accounts_menu"))
        bot.answer_callback_query(call.id, "Country Edit/Delete Menu")
        try:
            ed_c_txt = "🌐 Manage Countries (Edit/Delete):\nSelect an option below:" if lang_code == "en" else "🌐 管理国家（编辑/删除）：\n请在下方选择一个选项："
            bot.edit_message_text(ed_c_txt, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data == "admin_edit_countries_price_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        proto_items = product_inventory.get("Countries", {}).get("items", {})
        if proto_items:
            for c_name, c_val in proto_items.items():
                c_price = c_val.get("price", 1.00)
                if lang_code == "en":
                    markup.add(types.InlineKeyboardButton(f"💵 {c_name} (${c_price:.2f}) - Edit Price", callback_data=f"admin_edit_price_{c_name}"))
                else:
                    markup.add(types.InlineKeyboardButton(f"💵 {c_name} (${c_price:.2f}) - 修改价格", callback_data=f"admin_edit_price_{c_name}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_telegram_accounts_menu"))
        bot.answer_callback_query(call.id, "Country Price Menu")
        try:
            pr_m_txt = "💵 Country Price Management:\nSelect a country to change its price:" if lang_code == "en" else "💵 国家价格管理：\n选择要更改价格的国家："
            bot.edit_message_text(pr_m_txt, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_edit_price_"):
        if not is_admin(user_id):
            return
        country_name = call.data.replace("admin_edit_price_", "")
        user_states[user_id] = f"waiting_for_edit_price_{country_name}"
        current_price = product_inventory["Countries"]["items"].get(country_name, {}).get("price", 1.00)
        bot.answer_callback_query(call.id, f"Edit Price {country_name}")
        try:
            ed_pr_p = (
                f"💵 Edit Price for Telegram Country: {country_name}\n\nCurrent Price: ${current_price:.2f}\n\nPlease send new price (e.g., 1.50 or 2):"
                if lang_code == "en" else
                f"💵 修改电报国家 {country_name} 的价格\n\n当前价格: ${current_price:.2f}\n\n请发送新价格（例如：1.50 或 2）："
            )
            bot.edit_message_text(ed_pr_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_rename_country_"):
        if not is_admin(user_id):
            return
        country_name = call.data.replace("admin_rename_country_", "")
        user_states[user_id] = f"waiting_for_rename_country_{country_name}"
        bot.answer_callback_query(call.id, f"Rename {country_name}")
        try:
            rn_p = f"✏️ Enter new name for Telegram country {country_name}:" if lang_code == "en" else f"✏️ 输入电报国家 {country_name} 的新名称："
            bot.edit_message_text(rn_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data.startswith("admin_delete_country_"):
        if not is_admin(user_id):
            return
        country_name = call.data.replace("admin_delete_country_", "")
        proto_items = product_inventory.get("Countries", {}).get("items", {})
        if country_name in proto_items:
            del proto_items[country_name]
            save_inventory()
            bot.answer_callback_query(call.id, f"Deleted {country_name}")
            markup = types.InlineKeyboardMarkup(row_width=1)
            for c in proto_items.keys():
                if lang_code == "en":
                    markup.add(
                        types.InlineKeyboardButton(f"✏️ Rename: {c}", callback_data=f"admin_rename_country_{c}"),
                        types.InlineKeyboardButton(f"❌ Delete: {c}", callback_data=f"admin_delete_country_{c}")
                    )
                else:
                    markup.add(
                        types.InlineKeyboardButton(f"✏️ 重命名: {c}", callback_data=f"admin_rename_country_{c}"),
                        types.InlineKeyboardButton(f"❌ 删除: {c}", callback_data=f"admin_delete_country_{c}")
                    )
            markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_telegram_accounts_menu"))
            try:
                del_suc = f"✅ Telegram Country {country_name} deleted successfully!\n\n🌐 Manage Countries:" if lang_code == "en" else f"✅ 电报国家 {country_name} 删除成功！\n\n🌐 管理国家："
                bot.edit_message_text(del_suc, call.message.chat.id, call.message.message_id, reply_markup=markup)
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "Country not found" if lang_code == "en" else "未找到该国家", show_alert=True)
        return

    elif call.data == "admin_add_zip_menu":
        if not is_admin(user_id):
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        countries = product_inventory.get("Countries", {}).get("items", {})
        for c in countries.keys():
            markup.add(types.InlineKeyboardButton(f"🗂️ Telegram Country ({c})" if lang_code == "en" else f"🗂️ 电报国家 ({c})", callback_data=f"select_zip_country_{c}"))
        markup.add(types.InlineKeyboardButton(t["back"], callback_data="admin_telegram_accounts_menu"))
        bot.answer_callback_query(call.id, "ZIP Menu")
        try:
            sel_c_zip = "Select Telegram country to upload ZIP file stock:" if lang_code == "en" else "选择要上传 ZIP 文件库存的电报国家："
            bot.edit_message_text(sel_c_zip, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    elif call.data.startswith("select_zip_country_"):
        if not is_admin(user_id):
            return
        country_name = call.data.replace("select_zip_country_", "")
        temp_admin_data[user_id] = country_name
        user_states[user_id] = "waiting_for_zip_file"
        bot.answer_callback_query(call.id, country_name)
        try:
            zip_p = f"📁 Please send the .zip file stock for Telegram Country: {country_name}:" if lang_code == "en" else f"📁 请发送电报国家 {country_name} 的 .zip 文件库存："
            bot.edit_message_text(zip_p, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    elif call.data == "admin_back":
        if not is_admin(user_id):
            return
        try:
            admin_w2 = "🛠️ Welcome to Admin Panel\n\nChoose an option below:" if lang_code == "en" else "🛠️ 欢迎来到管理面板\n\n在下方选择一个选项："
            bot.edit_message_text(admin_w2, call.message.chat.id, call.message.message_id, reply_markup=get_admin_panel_keyboard(user_id))
        except Exception:
            pass
        return

    elif call.data == "noop":
        bot.answer_callback_query(call.id)
        return

    if call.data in ["btn_deposit_open", "dep_confirm", "▲ Deposit"]:
        try:
            bot.answer_callback_query(call.id, "Loading..." if lang_code == "en" else "加载中...")
            bot.edit_message_text(t["deposit"], call.message.chat.id, call.message.message_id, reply_markup=get_select_amount_keyboard(user_id))
        except Exception:
            bot.send_message(call.message.chat.id, t["deposit"], reply_markup=get_select_amount_keyboard(user_id))
        return

    elif call.data.startswith("amt_"):
        if call.data == "amt_other":
            user_states[user_id] = "waiting_for_custom_amount"
            bot.answer_callback_query(call.id, "Enter custom amount" if lang_code == "en" else "输入自定义金额")
            bot.send_message(call.message.chat.id, t["deposit_select_amt"])
        else:
            try:
                selected_val = float(call.data.split("_")[1])
                user_amounts[user_id] = selected_val
                user_states[user_id] = "waiting_for_payment_method"
                payment_text = f"💰 Selected Amount: ${selected_val:.2f}\n\nPlease select your preferred payment method:" if lang_code == "en" else f"💰 已选金额： ${selected_val:.2f}\n\n请选择您的首选付款方式："
                bot.answer_callback_query(call.id, f"Selected ${selected_val:.2f}" if lang_code == "en" else f"已选择 ${selected_val:.2f}")
                bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, reply_markup=get_payment_methods_keyboard(user_id))
            except Exception:
                pass
        return

    elif call.data in ["order_usdt_trc20", "order_usdt_bep20"]:
        current_amount = user_amounts.get(user_id, 2.50)
        if current_amount < 2.5:
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
        deposit_text = f"Deposited ${current_amount:.2f} (Order: {order_id})"
        user_deposits.setdefault(user_id, []).append({"text": deposit_text, "timestamp": time.time()})
        save_user_data(user_id)

        if lang_code == "en":
            order_text = (
                f"*[ ORDER CREATED ]*  {currency_type}\n"
                f"──────────────────────\n"
                f"  Send     ·  `{send_val}`\n"
                f"  Credit   ·  `{credit_val}`\n"
                f"  Order    ·  `{order_id}`\n"
                f"  Network  ·  {network_name}\n"
                f"  Address  ·  `{wallet_address}`\n"
                f"  Expires  ·  {current_time}\n"
                f"──────────────────────\n"
                f"Send exactly `{send_val}`, including all decimals. This amount was converted from `${current_amount:.2f}` at the Binance price when the order was created and ends in a unique identifier; `${current_amount:.2f}` is credited when it arrives.\n"
                f"Send native assets/tokens on the {network_name} network only.\n"
                f"Your balance will be credited by admin once verified."
            )
        else:
            order_text = (
                f"*[ 订单已创建 ]*  {currency_type}\n"
                f"──────────────────────\n"
                f"  发送金额 ·  `{send_val}`\n"
                f"  到账金额 ·  `{credit_val}`\n"
                f"  订单号   ·  `{order_id}`\n"
                f"  网络     ·  {network_name}\n"
                f"  充值地址 ·  `{wallet_address}`\n"
                f"  有效期   ·  {current_time}\n"
                f"──────────────────────\n"
                f"请准确发送 `{send_val}`（包含所有小数）。此金额根据下单时的币安价格换算，带有独特的尾数识别；到账后将为您的账户充值 `${current_amount:.2f}`。\n"
                f"请仅通过 {network_name} 网络发送相应的资产/代币。\n"
                f"管理员验证后将自动为您的账户充值余额。"
            )
        bot.answer_callback_query(call.id, "Order Generated!" if lang_code == "en" else "订单已生成！")
        try:
            bot.edit_message_text(order_text, call.message.chat.id, call.message.message_id, reply_markup=get_order_created_keyboard(net_code, order_id, user_id), parse_mode="Markdown")
        except Exception:
            bot.send_message(call.message.chat.id, order_text, reply_markup=get_order_created_keyboard(net_code, order_id, user_id), parse_mode="Markdown")
        return

    elif call.data == "back_to_products_menu":
        bot.answer_callback_query(call.id, "Buy Now Menu")
        try:
            bot.edit_message_text(t["products"], call.message.chat.id, call.message.message_id, reply_markup=get_products_categories_keyboard(user_id))
        except Exception:
            pass
        return

    elif call.data in ["go_main_menu", "dep_cancel"]:
        bot.answer_callback_query(call.id, "MainMenu")
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"Webhook Bot is running on port {port}...")
    app.run(host='0.0.0.0', port=port)
