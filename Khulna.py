import os, sqlite3, threading, time, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, jsonify, request
import requests
import telebot
from telebot.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

API_TOKEN = os.getenv("BOT_TOKEN", "8695667841:AAGIRtc8JcqqL3ASJZOy8S-3Jk0Pjk1A-68")
ADMIN_ID = 6954924404
CHANNEL_USERNAME = "@all_country_sell"
FIREBASE_URL = "https://shopbotdb-default-rtdb.firebaseio.com/"
UID_1 = "1076781671"
ADDR_2 = "TPgp911fhwLoK2cKHMvV5oRzFX5hc9NCY8"

PANEL_PRICES = {"Panel 1": 1.0, "Panel 2": 1.2, "Panel 3": 2.1, "Panel 4": 1.5}
P1 = {"Colombia":0.5,"India":0.55,"Bangladesh":0.55,"United States":0.55,"Indonesia":0.6,"Chile":0.65,"Kenya":0.65,"Myanmar":0.65,"Angola":0.68,"Afghanistan":0.7,"Zimbabwe":0.7,"Sudan":0.7,"Cameroon":0.7,"Madagascar":0.7,"Tanzania":0.6,"Algeria":0.75,"Jamaica":0.75,"Sri Lanka":0.8,"Eswatini":0.8,"Burkina Faso":0.8}
P2 = {"Myanmar":0.35,"Colombia":0.55,"Uganda":0.55,"Togo":0.55,"Sudan":0.58,"Zimbabwe":0.6,"Nigeria":0.6,"Congo, The Democratic":0.6,"Sierra Leone":0.6,"Madagascar":0.6,"Angola":0.65,"Niger":0.65,"Pakistan":0.65,"Zambia":0.65,"India":0.65,"Chile":0.65,"Afghanistan":0.65,"Ghana":0.65,"Cuba":0.7,"Thailand":0.7}
P3 = {"Nigeria":0.5}
PANEL_MAP = {"1": P1, "2": P2, "3": P3}

T_EN = {
 "welcome":"Welcome {name}!\n\nPlease select from menu:",
 "tg_prompt":"Select your panel:", "panel_country":"Panel {panel}\n\nSelect country:",
 "back_panels":"Back to Panels", "back":"Back",
 "stock_out":"Stock Out! Sorry, out of stock.",
 "no_bal":"Insufficient Balance!\nPrice: {price} USDT, Balance: {balance:.2f} USDT",
 "ask_qty":"Selected: {panel}\nStock: {stock} pcs\nPrice: {price} USDT\nBalance: {balance:.2f} USDT\n\nHow many? Enter number:",
 "buy_ok":"Purchase Successful! Bought {qty} pcs! Deducted: {cost} USDT New Balance: {new_bal:.2f} USDT",
 "bought":"Your Products ({panel}):\n\n{products}",
 "profile":"Profile:\nID: {uid}\nName: {name}\nBalance: {balance:.2f} USDT\nTotal Buys: {total}",
 "dep_main":"Deposit System\n\nSelect method:", "dep_step1":"{method} Deposit\n\nSend to:\n{address}\n\nEnter amount you sent (e.g. 5):",
 "dep_step2":"Now send your Order ID / TrxID:", "dep_pending":"Deposit request sent to admin. Please wait.",
 "support":"Support\n\nContact: @GV_gmail_07\nAvailable: 24/7",
 "invalid":"Enter valid number.", "no_stock":"Only {stock} pcs available.", "invalid_amt":"Enter valid amount.",
 "dep_ok":"Deposit {amount:.2f} USDT successful! Balance: {balance:.2f} USDT", "dep_cancel":"Deposit cancelled.",
 "lang_ok":"Language changed to English!", "select_lang":"Select language:"
}
T_ZH = {
 "welcome":"Welcome {name}!",
 "tg_prompt":"Select panel:", "panel_country":"Panel {panel}\n\nSelect country:",
 "back_panels":"Back", "back":"Back", "stock_out":"Stock Out!",
 "no_bal":"Balance low! Price: {price} Balance: {balance:.2f}",
 "ask_qty":"Selected: {panel}\nStock: {stock}\nPrice: {price}\nBalance: {balance:.2f}\n\nEnter qty:",
 "buy_ok":"Bought {qty} pcs! Deducted {cost} New Balance {new_bal:.2f}",
 "bought":"Your Products ({panel}):\n\n{products}",
 "profile":"Profile ID: {uid} Name: {name} Balance: {balance:.2f} Buys: {total}",
 "dep_main":"Deposit System", "dep_step1":"{method} Deposit\nSend to: {address}\nEnter amount:",
 "dep_step2":"Send Order ID / TrxID:", "dep_pending":"Deposit sent to admin.",
 "support":"Support @GV_gmail_07", "invalid":"Enter valid number.", "no_stock":"Only {stock} pcs.",
 "invalid_amt":"Enter valid amount.", "dep_ok":"Deposit {amount:.2f} OK! Balance {balance:.2f}",
 "dep_cancel":"Deposit cancelled.", "lang_ok":"Language changed!", "select_lang":"Select language:"
}
TR = {"en": T_EN, "zh": T_ZH}
def t(lang): return TR.get(lang, T_EN)

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")
app = Flask(__name__)
user_states = {}
_cache = {"data": {}, "time": 0}

def safe_key(s): return s.replace(" ","_").replace(",","").replace(".","")
def get_all_stock():
    if time.time() - _cache["time"] < 5 and _cache["data"]: return _cache["data"]
    try:
        d = requests.get(f"{FIREBASE_URL}stock.json", timeout=5).json() or {}
        _cache["data"]=d; _cache["time"]=time.time(); return d
    except: return _cache["data"]
def get_stock(path):
    d = get_all_stock().get(safe_key(path))
    if isinstance(d, list): return [x for x in d if x]
    if isinstance(d, dict): return list(d.values())
    return []
def update_stock(path, rem):
    try:
        requests.put(f"{FIREBASE_URL}stock/{safe_key(path)}.json", json=rem, timeout=5); _cache["time"]=0
    except: pass
def get_user_data(uid):
    try:
        d = requests.get(f"{FIREBASE_URL}users/{uid}.json", timeout=3).json()
        if not d: return 0.0,0,"en"
        return float(d.get("balance",0.0)), int(d.get("total_buy",0)), d.get("language","en")
    except: return 0.0,0,"en"
def get_user(msg):
    uid=msg.from_user.id
    try:
        url=f"{FIREBASE_URL}users/{uid}.json"; d=requests.get(url, timeout=5).json()
        if not d:
            requests.put(url, json={"user_id":uid,"first_name":msg.from_user.first_name or "U","username":msg.from_user.username or "","balance":0.0,"total_buy":0,"language":"en"}, timeout=5); return 0.0,0,"en"
        return float(d.get("balance",0.0)), int(d.get("total_buy",0)), d.get("language","en")
    except: return 0.0,0,"en"
def main_menu(lang):
    mk=ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(KeyboardButton("Telegram Buy Now"), KeyboardButton("Profile"), KeyboardButton("Deposit"), KeyboardButton("Support"), KeyboardButton("Language"))
    return mk
def panel_menu():
    mk=InlineKeyboardMarkup(row_width=2)
    mk.add(InlineKeyboardButton("Panel 1", callback_data="p1"), InlineKeyboardButton("Panel 2", callback_data="p2"), InlineKeyboardButton("Panel 3", callback_data="p3"), InlineKeyboardButton("Panel 4", callback_data="p4"))
    return mk
def dep_menu():
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("Method 1 UID", callback_data="dep_bin"), InlineKeyboardButton("Method 2 TRC20", callback_data="dep_tron")); return mk
def safe_edit(call, text, markup=None):
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    except:
        try: bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")
        except: pass

@bot.message_handler(commands=["start"])
def start_h(m):
    _,_,lang=get_user(m); user_states.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, t(lang)["welcome"].format(name=m.from_user.first_name), reply_markup=main_menu(lang))

@bot.message_handler(func=lambda m: m.text=="Telegram Buy Now")
def buy_h(m):
    _,_,lang=get_user_data(m.from_user.id)
    bot.send_message(m.chat.id, t(lang)["tg_prompt"], reply_markup=panel_menu())

@bot.message_handler(func=lambda m: m.text=="Deposit")
def dep_h(m):
    _,_,lang=get_user_data(m.from_user.id)
    bot.send_message(m.chat.id, t(lang)["dep_main"], reply_markup=dep_menu())

@bot.message_handler(func=lambda m: m.text=="Profile")
def prof_h(m):
    bal,tot,lang=get_user_data(m.from_user.id)
    bot.send_message(m.chat.id, t(lang)["profile"].format(uid=m.from_user.id, name=m.from_user.first_name, balance=bal, total=tot))

@bot.message_handler(func=lambda m: m.text=="Support")
def sup_h(m):
    _,_,lang=get_user_data(m.from_user.id)
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("Contact Support", url="https://t.me/GV_gmail_07"))
    bot.send_message(m.chat.id, t(lang)["support"], reply_markup=mk)

@bot.message_handler(func=lambda m: m.text=="Language")
def lang_h(m):
    _,_,lang=get_user_data(m.from_user.id)
    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("English", callback_data="lang_en"), InlineKeyboardButton("Chinese", callback_data="lang_zh"))
    bot.send_message(m.chat.id, t(lang)["select_lang"], reply_markup=mk)

@bot.message_handler(commands=["addstock"])
def addstock(m):
    if m.from_user.id!=ADMIN_ID: bot.reply_to(m, "No permission"); return
    try:
        _,content=m.text.split(maxsplit=1); tp,raw=content.split("|",1)
        new=[x.strip() for x in raw.split("\n") if x.strip()]
        sl=get_stock(tp.strip()); sl.extend(new); update_stock(tp.strip(), sl)
        bot.reply_to(m, f"Added {len(new)} to {tp.strip()} Total {len(sl)}")
    except Exception as e: bot.reply_to(m, f"Error {e}")

@bot.message_handler(func=lambda m: True)
def all_text(m):
    uid=m.from_user.id; st=user_states.get(uid, {}); act=st.get("action")
    if not act: return
    _,_,lang=get_user_data(uid); tr=t(lang)
    if act=="buy_qty":
        try:
            qty=int(m.text.strip())
            if qty<=0: raise ValueError
            stock=get_stock(st["panel"])
            if qty>len(stock): bot.send_message(m.chat.id, tr["no_stock"].format(stock=len(stock))); return
            total=qty*st["price"]; bal,_,_=get_user_data(uid)
            if bal<total:
                bot.send_message(m.chat.id, tr["no_bal"].format(price=total, balance=bal), reply_markup=dep_menu()); user_states.pop(uid,None); return
            bought=stock[:qty]; update_stock(st["panel"], stock[qty:])
            nb=bal-total; requests.put(f"{FIREBASE_URL}users/{uid}/balance.json", json=nb, timeout=5)
            _,cur,_=get_user_data(uid); requests.put(f"{FIREBASE_URL}users/{uid}/total_buy.json", json=cur+1, timeout=5)
            user_states.pop(uid,None)
            prod="\n".join([f"<code>{x}</code>" for x in bought])
            bot.send_message(m.chat.id, tr["bought"].format(panel=st["panel"], products=prod), parse_mode="HTML")
            bot.send_message(m.chat.id, tr["buy_ok"].format(qty=qty, cost=total, new_bal=nb), reply_markup=main_menu(lang))
        except: bot.send_message(m.chat.id, tr["invalid"])
    elif act=="dep_amt":
        try:
            amt=float(m.text.strip())
            if amt<=0: raise ValueError
            st["amount"]=amt; st["action"]="dep_oid"; bot.send_message(m.chat.id, tr["dep_step2"])
        except: bot.send_message(m.chat.id, tr["invalid_amt"])
    elif act=="dep_oid":
        st2=user_states.pop(uid, {}); amt=st2.get("amount",0.0); oid=m.text.strip()
        bot.send_message(m.chat.id, tr["dep_pending"], reply_markup=main_menu(lang))
        mk=InlineKeyboardMarkup(); mk.row(InlineKeyboardButton("Approve", callback_data=f"depapprove|{uid}|{amt:.2f}|{oid}"), InlineKeyboardButton("Reject", callback_data=f"depreject|{uid}|{oid}"))
        bot.send_message(ADMIN_ID, f"New Deposit!\nUser {m.from_user.first_name} ({uid})\nMethod {st2.get('method')}\nAmount {amt:.2f}\nTrx {oid}", reply_markup=mk, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def ALL_CALLBACKS(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    data=call.data or ""
    uid=call.from_user.id
    _,_,lang=get_user_data(uid); tr=t(lang)
    try:
        if data=="back_panels":
            safe_edit(call, tr["tg_prompt"], panel_menu()); return
        if data=="back_dep":
            safe_edit(call, tr["dep_main"], dep_menu()); return
        if data.startswith("lang_"):
            lg=data.split("_")[1]; requests.put(f"{FIREBASE_URL}users/{uid}/language.json", json=lg, timeout=5)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            bot.send_message(call.message.chat.id, t(lg)["lang_ok"], reply_markup=main_menu(lg)); return
        if data in ["p1","p2","p3","p4"]:
            num=data[1]; pname=f"Panel {num}"; bal,_,_=get_user_data(uid)
            if num in PANEL_MAP:
                countries=list(PANEL_MAP[num].keys()); mk=InlineKeyboardMarkup(row_width=2)
                for idx, cname in enumerate(countries):
                    cnt=len(get_stock(f"{pname}/{cname}"))
                    mk.add(InlineKeyboardButton(f"{cname} [{cnt}]", callback_data=f"c{num}:{idx}"))
                mk.add(InlineKeyboardButton(tr["back_panels"], callback_data="back_panels"))
                safe_edit(call, tr["panel_country"].format(panel=pname), mk); return
            else:
                price=PANEL_PRICES[pname]; stock=get_stock(pname)
                if not stock:
                    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(tr["back_panels"], callback_data="back_panels")); safe_edit(call, tr["stock_out"], mk); return
                if bal<price:
                    mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton("Method 1 UID", callback_data="dep_bin"), InlineKeyboardButton("Method 2 TRC20", callback_data="dep_tron")); mk.add(InlineKeyboardButton(tr["back_panels"], callback_data="back_panels")); safe_edit(call, tr["no_bal"].format(price=price, balance=bal), mk); return
                user_states[uid]={"action":"buy_qty","panel":pname,"price":price}
                mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(tr["back_panels"], callback_data="back_panels")); safe_edit(call, tr["ask_qty"].format(panel=pname, stock=len(stock), price=price, balance=bal), mk); return
        if data.startswith("c") and ":" in data:
            try: num=data[1]; idx=int(data.split(":")[1]); pname=f"Panel {num}"; countries=list(PANEL_MAP[num].keys()); cname=countries[idx]; price=PANEL_MAP[num][cname]
            except: return
            bal,_,_=get_user_data(uid); path=f"{pname}/{cname}"; stock=get_stock(path)
            mk_back=InlineKeyboardMarkup(); mk_back.add(InlineKeyboardButton(f"{tr['back']} {pname}", callback_data=f"p{num}"))
            if not stock: safe_edit(call, f"{cname} ({pname})\n\n"+tr["stock_out"], mk_back); return
            if bal<price:
                pay=InlineKeyboardMarkup(); pay.add(InlineKeyboardButton("Method 1 UID", callback_data="dep_bin"), InlineKeyboardButton("Method 2 TRC20", callback_data="dep_tron")); pay.add(InlineKeyboardButton(f"{tr['back']} {pname}", callback_data=f"p{num}")); safe_edit(call, f"{cname}\nPrice {price}\n\n"+tr["no_bal"].format(price=price, balance=bal), pay); return
            user_states[uid]={"action":"buy_qty","panel":path,"price":price}; safe_edit(call, tr["ask_qty"].format(panel=f"{pname} / {cname}", stock=len(stock), price=price, balance=bal), mk_back); return
        if data in ["dep_bin","dep_tron"]:
            method="Method 1 UID" if data=="dep_bin" else "Method 2 TRC20"; addr=UID_1 if data=="dep_bin" else ADDR_2
            user_states[uid]={"action":"dep_amt","method":method}
            mk=InlineKeyboardMarkup(); mk.add(InlineKeyboardButton(tr["back"], callback_data="back_dep")); safe_edit(call, tr["dep_step1"].format(method=method, address=addr), mk); return
        if data.startswith("depapprove|") or data.startswith("depreject|"):
            p=data.split("|"); tid=int(p[1]); _,_,tl=get_user_data(tid); tt=t(tl)
            if p[0]=="depapprove":
                amt=float(p[2]); oid=p[3]; cur,_,_=get_user_data(tid); nb=cur+amt; requests.put(f"{FIREBASE_URL}users/{tid}/balance.json", json=nb, timeout=5)
                bot.edit_message_text(f"Approved {amt:.2f} for {tid} | {oid}", call.message.chat.id, call.message.message_id)
                try: bot.send_message(tid, tt["dep_ok"].format(amount=amt, balance=nb))
                except: pass
            else:
                bot.edit_message_text(f"Rejected {tid} | {p[2]}", call.message.chat.id, call.message.message_id)
                try: bot.send_message(tid, tt["dep_cancel"])
                except: pass
            return
    except Exception as e:
        print("CALLBACK ERROR:", e); traceback.print_exc()

def init_db():
    c=sqlite3.connect("auto_payments.db"); c.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, trx_id TEXT UNIQUE, amount REAL, sender TEXT)"); c.commit(); c.close()
init_db()
@app.route("/webhook/payment", methods=["POST"])
def pay():
    d=request.json
    if not d or not d.get("trx_id"): return jsonify({"status":"error"}),400
    try:
        c=sqlite3.connect("auto_payments.db"); c.execute("INSERT INTO transactions (trx_id, amount, sender) VALUES (?,?,?)", (d["trx_id"], float(d["amount"]), d.get("sender","")) ); c.commit(); c.close(); return jsonify({"status":"success"})
    except: return jsonify({"status":"error","message":"dup"}),400
class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Alive")
    def log_message(self, *a): return
def run_server(): HTTPServer(("0.0.0.0", int(os.environ.get("PORT",8080))), H).serve_forever()

if __name__=="__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Bot starting...")
    try: bot.remove_webhook(drop_pending_updates=True); time.sleep(1)
    except Exception as e: print(e)
    try: bot.set_my_commands([BotCommand("start","Re-start")])
    except: pass
    while True:
        try: bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e: print("Polling:", e); time.sleep(5)
