import os
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = os.getenv("BOT_TOKEN", "8695667841:AAGIRtc8JcqqL3ASJZOy8S-3Jk0Pjk1A-68")
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Panel 1", callback_data="p1"))
    bot.send_message(message.chat.id, "Select a panel:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id, "Button clicked!")
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"You clicked: {call.data}")

if __name__ == '__main__':
    bot.remove_webhook()
    print("Test Bot Started...")
    bot.infinity_polling()
