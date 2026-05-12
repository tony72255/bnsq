import os
import requests
import threading
import time
from dotenv import load_dotenv
import telebot
from telebot import types
from flask import Flask, request
from threading import Lock
import logging

load_dotenv()

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================== FLASK APP ==================
app = Flask(__name__)

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def home():
    return "Chuyên Gia Crypto Bot 4.1 đang chạy 24/7 📊"

# ================== WEBHOOK ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        threading.Thread(
            target=bot.process_new_updates,
            args=([update],),
            daemon=True
        ).start()
        
        return '', 200
    except Exception as e:
        logger.error(f"Lỗi webhook: {e}")
        return '', 400

# ================== BIẾN MÔI TRƯỜNG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_SQUARE_KEY = os.getenv("BINANCE_SQUARE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')}/webhook"

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# Pending contents an toàn hơn
pending_contents = {}  # key: (chat_id, message_id)
pending_lock = Lock()

# ================== GEMINI - PROMPT TỰ NHIÊN ==================
def generate_crypto_analysis(prompt: str) -> str:
    """Tạo phân tích crypto với giọng điệu tự nhiên như trader thật"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        
        system_prompt = """Bạn là một trader crypto Việt Nam có 8 năm kinh nghiệm, giọng điệu tự nhiên, gần gũi, đôi khi lầy lầy như dân crypto thật.
Không nói kiểu giáo viên, không quá trang trọng, không dùng từ quá sách vở.

Yêu cầu:
- Bài viết siêu ngắn (45-60 từ)
- Viết như đang đăng bài cá nhân trên Binance Square hoặc chat group
- Dùng ngôn ngữ đời thường: "mình thấy", "theo anh/chị", "có khả năng", "đang sideway mãi", "pump nhẹ", "cẩn thận vùng này", "mình đang accumulate"...
- Thêm chút cảm xúc cá nhân nhưng không hype quá
- Kết thúc bằng khuyến nghị rõ ràng: NÊN MUA / NÊN BÁN / NÊN HOLD
- Khi nhắc coin thì thêm $TICKER
- Tối đa 2-3 coin

Ví dụ phong cách:
"ETH đang sideway khá chán quanh 2500-2600. Volume không tăng, funding rate vẫn âm. Mình nghĩ nếu giữ vững trên 2480 thì có cửa test 2800. Còn break 2450 là nên cắt sớm. 
Khuyến nghị: NÊN HOLD"

"$SOL sau đợt dump tuần trước đang có dấu hiệu tích lũy khá tốt. RSI rời vùng oversold. Mình đang mua dần, target ngắn hạn 165-170$. 
Khuyến nghị: NÊN MUA"

Bây giờ phân tích cho ý tưởng sau:"""

        data = {
            "contents": [{
                "parts": [{
                    "text": f"{system_prompt}\n\n{prompt}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.85,
                "maxOutputTokens": 400,
                "topP": 0.92
            }
        }

        response = requests.post(url, headers={"Content-Type": "application/json"}, json=data, timeout=20)
        
        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text
        else:
            logger.error(f"Gemini API error: {response.text[:300]}")
            return f"Lỗi Gemini: {response.status_code}"
            
    except Exception as e:
        logger.error(f"Lỗi generate analysis: {e}")
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
        logger.error(f"Lỗi post Square: {e}")
        return f"❌ Lỗi Square: {str(e)}"

# ================== BOT HANDLERS ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "📊 **Chuyên Gia Crypto Bot 4.1** đang chạy 24/7!\nGửi ý tưởng coin để tao phân tích nhé.")

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
    bot.reply_to(message, "📊 Đang phân tích theo style trader thật...")
    
    content = generate_crypto_analysis(prompt)
    
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
    
    with pending_lock:
        pending_contents[(message.chat.id, sent_msg.message_id)] = content

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    with pending_lock:
        key = (call.message.chat.id, call.message.message_id)
        content = pending_contents.get(key)
        
        if not content:
            bot.answer_callback_query(call.id, "Nội dung đã hết hạn!")
            return

        if call.data == "post_yes":
            result = post_to_binance_square(content)
            bot.edit_message_text(
                f"**ĐÃ ĐĂNG THÀNH CÔNG!** 📊\n\n{content}\n\n{result}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        elif call.data == "post_no":
            bot.edit_message_text("❌ Đã hủy.", call.message.chat.id, call.message.message_id)
        
        pending_contents.pop(key, None)

# ================== KEEP ALIVE ==================
def keep_alive():
    while True:
        try:
            hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')
            requests.get(f"https://{hostname}/ping", timeout=10)
            logger.info("🔄 Self-ping thành công")
        except Exception as e:
            logger.warning(f"⚠️ Self-ping lỗi: {e}")
        time.sleep(240)

# ================== KHỞI ĐỘNG ==================
if __name__ == "__main__":
    logger.info("🚀 Bot 4.1 đang khởi động trên Render...")
    
    bot.delete_webhook()
    bot.remove_webhook()
    success = bot.set_webhook(url=WEBHOOK_URL, max_connections=100, drop_pending_updates=True)
    
    if success:
        logger.info(f"✅ Webhook set thành công: {WEBHOOK_URL}")
    else:
        logger.error("❌ Không set được webhook!")
    
    threading.Thread(target=keep_alive, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
