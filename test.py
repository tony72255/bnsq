import os
import requests
import threading
import time
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

# ================== WEBHOOK TELEGRAM (FIX SPAM) ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    print("📥 Nhận request từ Telegram!")
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        # Xử lý trong thread riêng → trả response 200 NGAY
        threading.Thread(
            target=bot.process_new_updates,
            args=([update],),
            daemon=True
        ).start()
        
        return '', 200
    except Exception as e:
        print(f"❌ Lỗi webhook: {e}")
        return '', 400

# ================== BIẾN MÔI TRƯỜNG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_SQUARE_KEY = os.getenv("BINANCE_SQUARE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')}/webhook"

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
pending_contents = {}

# ================== GEMINI ==================
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
        response = requests.post(url, headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return f"Lỗi Gemini: {response.text[:300]}"
    except Exception as e:
        return f"Lỗi kết nối Gemini: {str(e)}"

# ================== POST BINANCE SQUARE ==================
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

# ================== BOT HANDLERS ==================
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
            bot.edit_message_text(
                f"**ĐÃ ĐĂNG THÀNH CÔNG!** 📊\n\n{content}\n\n{result}",
                call.message.chat.id,
                call.message.message_id
            )
            pending_contents.pop(call.message.message_id, None)
    elif call.data == "post_no":
        bot.edit_message_text("❌ Đã hủy.", call.message.chat.id, call.message.message_id)
        pending_contents.pop(call.message.message_id, None)

# ================== SELF KEEP-ALIVE (Không ngủ) ==================
def keep_alive():
    while True:
        try:
            hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')
            requests.get(f"https://{hostname}/ping", timeout=10)
            print("🔄 Self-ping thành công - giữ bot không ngủ")
        except Exception as e:
            print(f"⚠️ Self-ping lỗi: {e}")
        time.sleep(240)  # 4 phút

# ================== KHỞI ĐỘNG ==================
if __name__ == "__main__":
    print("🚀 Bot đang khởi động trên Render (Webhook + Keep-alive)...")
    
    # Set webhook
    bot.delete_webhook()
    bot.remove_webhook()
    success = bot.set_webhook(url=WEBHOOK_URL, max_connections=100)
    if success:
        print(f"✅ Webhook đã set thành công: {WEBHOOK_URL}")
    else:
        print("❌ Không set được webhook!")

    # Bật self keep-alive
    threading.Thread(target=keep_alive, daemon=True).start()

    # Chạy Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)