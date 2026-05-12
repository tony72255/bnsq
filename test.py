import os
import requests
from dotenv import load_dotenv
import telebot
from telebot import types
from flask import Flask, request

load_dotenv()

# ================== FLASK APP ==================
app = Flask(__name__)

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def home():
    return "Chuyên Gia Crypto Bot đang chạy 24/7 📊"

# ================== WEBHOOK TELEGRAM ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📥 Nhận request từ Telegram!")  # ← log để debug
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        print(f"❌ Lỗi xử lý webhook: {e}")
        return '', 400

# ================== BIẾN MÔI TRƯỜNG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_SQUARE_KEY = os.getenv("BINANCE_SQUARE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# URL webhook trên Render (PHẢI CHÍNH XÁC)
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')}/webhook"

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)  # ← Quan trọng!
pending_contents = {}

# ================== (giữ nguyên các hàm generate_villain_content, post_to_binance_square, handlers...) ==================
# (copy nguyên phần này từ code cũ của bạn, mình không thay đổi logic)

def generate_villain_content(prompt):  # ... (giữ nguyên)
    # ... code cũ của bạn ...

def post_to_binance_square(content):  # ... (giữ nguyên)
    # ... code cũ của bạn ...

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "📊 **Chuyên Gia Crypto Bot 4.0** đang chạy 24/7!\nGửi ý tưởng coin để tao phân tích.")

@bot.message_handler(commands=['post'])
def post_cmd(message):
    prompt = message.text.replace('/post', '').strip()
    if not prompt:
        bot.reply_to(message, "❌ Gõ /post + ý tưởng đi!")
        return
    process_idea(message, prompt)

@bot.message_handler(func=lambda m: True)
def handle_idea(message):
    if not message.text.startswith('/'):
        process_idea(message, message.text)

def process_idea(message, prompt):
    bot.reply_to(message, "📊 Đang phân tích chuyên sâu...")
    content = generate_villain_content(prompt)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ ĐĂNG NGAY", callback_data="post_yes"),
        types.InlineKeyboardButton("❌ HỦY", callback_data="post_no")
    )
    
    sent_msg = bot.send_message(
        message.chat.id,
        f"**Phân tích từ Chuyên Gia (~50 từ):**\n\n{content}\n\n**Đăng lên Binance Square không?**",
        reply_markup=markup,
        parse_mode='Markdown'
    )
    pending_contents[sent_msg.message_id] = content

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "post_yes":
        content = pending_contents.get(call.message.message_id)
        if content:
            result = post_to_binance_square(content)
            bot.edit_message_text(f"**ĐÃ ĐĂNG THÀNH CÔNG!** 📊\n\n{content}\n\n{result}", call.message.chat.id, call.message.message_id)
            pending_contents.pop(call.message.message_id, None)
    elif call.data == "post_no":
        bot.edit_message_text("❌ Đã hủy.", call.message.chat.id, call.message.message_id)
        pending_contents.pop(call.message.message_id, None)

# ================== KHỞI ĐỘNG BOT ==================
if __name__ == "__main__":
    print("🚀 Bot đang khởi động trên Render (Webhook mode)...")
    
    # Xóa webhook cũ và set lại
    bot.delete_webhook()
    bot.remove_webhook()
    
    success = bot.set_webhook(url=WEBHOOK_URL, max_connections=100)
    if success:
        print(f"✅ Webhook đã set thành công: {WEBHOOK_URL}")
        print("🔍 Webhook info:", bot.get_webhook_info())
    else:
        print("❌ Không set được webhook! Kiểm tra token và URL")

    # Chạy Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)