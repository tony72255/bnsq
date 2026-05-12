import os
import requests
import threading
from dotenv import load_dotenv
import telebot
from telebot import types
from flask import Flask, request

load_dotenv()

# ================== FLASK APP (chỉ 1 app duy nhất) ==================
app = Flask(__name__)

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def home():
    return "Chuyên Gia Crypto Bot đang chạy 24/7 📊"

# ================== WEBHOOK CHO TELEGRAM ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 400

# ================== CÁC BIẾN MÔI TRƯỜNG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_SQUARE_KEY = os.getenv("BINANCE_SQUARE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# URL webhook của Render (bạn thay bằng link thật của app)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ví dụ: https://ten-bot-cua-ban.onrender.com/webhook

bot = telebot.TeleBot(TELEGRAM_TOKEN)
pending_contents = {}

# ================== GEMINI - CHUYÊN GIA CRYPTO ==================
def generate_villain_content(prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{
                    "text": f"""Bạn là Chuyên Gia Phân Tích Crypto nghiêm túc. 
Viết bài SIÊU NGẮN (45-55 từ), phân tích rõ ràng. 
Kết thúc bằng lời khuyên cụ thể: NÊN MUA / NÊN BÁN / NÊN HOLD. 
Khi nhắc coin thì tự động thêm $TICKER, tối đa 2-3 tag. 
Giọng điệu chuyên nghiệp, ít emoji.
Ý tưởng: {prompt}"""
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 600
            }
        }
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return f"Lỗi Gemini: {response.text[:300]}"
    except Exception as e:
        return f"Lỗi kết nối Gemini: {str(e)}"

# ================== ĐĂNG BINANCE SQUARE ==================
def post_to_binance_square(content):
    try:
        url = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
        headers = {
            "X-Square-OpenAPI-Key": BINANCE_SQUARE_KEY,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill"
        }
        payload = {
            "bodyTextOnly": content,
            "contentType": 1,
            "title": "",
            "tags": ["crypto", "analysis", "expert"]
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            post_id = response.json().get('data', {}).get('id', 'unknown')
            return f"✅ ĐĂNG THÀNH CÔNG!\nPost ID: {post_id}\n🔗 https://www.binance.com/en/square/post/{post_id}"
        return f"❌ Lỗi Square: {response.status_code}"
    except Exception as e:
        return f"❌ Lỗi Square: {str(e)}"

# ================== XỬ LÝ BOT ==================
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

# ================== CHẠY BOT + FLASK ==================
if __name__ == "__main__":
    print("🚀 Bot đang khởi động trên Render (Webhook mode)...")
    
    # Xóa webhook cũ và set webhook mới
    bot.delete_webhook()
    bot.remove_webhook()
    success = bot.set_webhook(url=WEBHOOK_URL, max_connections=100)
    if success:
        print(f"✅ Webhook đã set thành công: {WEBHOOK_URL}")
    else:
        print("❌ Không set được webhook! Kiểm tra WEBHOOK_URL trong .env")

    # Chạy Flask server
    app.run(host='0.0.0.0', port=10000)