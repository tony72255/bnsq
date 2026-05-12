import os
import requests
import threading
import time
import random
from collections import defaultdict
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

# ================== FLASK ==================
app = Flask(__name__)

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def home():
    return "Chuyên Gia Crypto Bot 5.0 Fixed 🚀 Đang chạy 24/7"

# ================== WEBHOOK ROUTE (RẤT QUAN TRỌNG) ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📥 NHẬN WEBHOOK TỪ TELEGRAM!")
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        if update and update.message:
            logger.info(f"📨 Tin nhắn từ user {update.message.from_user.id}: {update.message.text}")
        
        # Xử lý trong thread riêng
        threading.Thread(
            target=bot.process_new_updates,
            args=([update],),
            daemon=True
        ).start()
        
        return '', 200
    except Exception as e:
        logger.error(f"❌ Lỗi webhook: {e}")
        return '', 400

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_SQUARE_KEY = os.getenv("BINANCE_SQUARE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')}/webhook"

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

pending_contents = {}
user_styles = {}
user_last_request = defaultdict(list)
pending_lock = Lock()

RATE_LIMIT = 3
RATE_WINDOW = 60

# ================== RATE LIMIT ==================
def check_rate_limit(user_id):
    now = time.time()
    user_last_request[user_id] = [t for t in user_last_request[user_id] if now - t < RATE_WINDOW]
    if len(user_last_request[user_id]) >= RATE_LIMIT:
        return False
    user_last_request[user_id].append(now)
    return True

# ================== POST PROCESS ==================
def post_process(text: str) -> str:
    text = text.replace("Khuyến nghị:", "\n\nKhuyến nghị:")
    emojis = ["📈", "📉", "⚡", "🔥", "🧿", "💎"]
    if random.random() > 0.6:
        text += f" {random.choice(emojis)}"
    return text.strip()

# ================== GENERATE ANALYSIS ==================
def generate_crypto_analysis(prompt: str, user_id: int) -> str:
    style = user_styles.get(user_id, "trader")
    
    system_prompt = f"""Bạn là trader crypto Việt Nam kinh nghiệm 8 năm, giọng điệu {style}.
Viết ngắn (45-60 từ), tự nhiên như đăng bài thật trên Binance Square.
Dùng ngôn ngữ đời thường, thêm cảm xúc cá nhân nhẹ.
Kết thúc bằng "Khuyến nghị: NÊN MUA / NÊN BÁN / NÊN HOLD"
Thêm $TICKER."""

    # Thử Groq trước
    if GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.85,
                max_tokens=400
            )
            return post_process(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # Fallback Gemini
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        data = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
            "generationConfig": {"temperature": 0.85, "maxOutputTokens": 400}
        }
        resp = requests.post(url, json=data, timeout=25)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return post_process(text)
        else:
            return f"Lỗi Gemini: {resp.status_code}"
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "Lỗi phân tích. Thử lại sau nhé!"

# ================== BINANCE DATA ==================
def get_binance_data(symbol: str):
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol.upper()}USDT"
        data = requests.get(url, timeout=10).json()
        return {
            "price": float(data['lastPrice']),
            "change": float(data['priceChangePercent']),
        }
    except:
        return None

# ================== BOT HANDLERS ==================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🚀 **Crypto Bot 5.0 Fixed** sẵn sàng!\nGửi coin hoặc ý tưởng để phân tích.")

@bot.message_handler(commands=['style'])
def set_style(message):
    styles = ["pro", "lầy", "meme", "trader"]
    style = message.text.replace('/style', '').strip().lower()
    if style in styles:
        user_styles[message.from_user.id] = style
        bot.reply_to(message, f"✅ Style: **{style}**")
    else:
        bot.reply_to(message, "Style: pro, lầy, meme, trader")

@bot.message_handler(commands=['post'])
def post_cmd(message):
    prompt = message.text.replace('/post', '').strip()
    if prompt:
        process_idea(message, prompt)

@bot.message_handler(func=lambda m: True)
def handle_idea(message):
    if message.text and message.text.startswith('/'):
        return
    process_idea(message, message.text or "")

def process_idea(message, prompt):
    if not prompt:
        return
    user_id = message.from_user.id
   
    if not check_rate_limit(user_id):
        bot.reply_to(message, "⏳ Đợi chút, bạn gửi nhanh quá (max 3 tin/phút).")
        return

    bot.reply_to(message, "📡 Đang phân tích...")

    market_data = ""
    if len(prompt.split()) == 1 and prompt.upper().isalpha():
        data = get_binance_data(prompt)
        if data:
            market_data = f"\nGiá: ${data['price']:,.4f} | 24h: {data['change']:+.2f}%"

    content = generate_crypto_analysis(prompt + market_data, user_id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ ĐĂNG NGAY", callback_data="post_yes"),
        types.InlineKeyboardButton("❌ HỦY", callback_data="post_no")
    )

    sent_msg = bot.send_message(
        message.chat.id,
        f"**Phân tích {prompt.upper()}**\n\n{content}\n\n**Đăng lên Binance Square?**",
        reply_markup=markup,
        parse_mode='Markdown'
    )

    with pending_lock:
        pending_contents[(message.chat.id, sent_msg.message_id)] = content

# ================== CALLBACK ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    with pending_lock:
        key = (call.message.chat.id, call.message.message_id)
        content = pending_contents.get(key)
        if not content:
            bot.answer_callback_query(call.id, "Nội dung hết hạn!")
            return

        if call.data == "post_yes":
            result = post_to_binance_square(content)
            bot.edit_message_text(
                f"**✅ ĐÃ ĐĂNG THÀNH CÔNG!**\n\n{content}\n\n{result}",
                call.message.chat.id, call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.edit_message_text("❌ Đã hủy.", call.message.chat.id, call.message.message_id)
        
        pending_contents.pop(key, None)

# ================== POST TO BINANCE SQUARE ==================
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
            "tags": ["crypto", "analysis"]
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            post_id = r.json().get('data', {}).get('id', 'unknown')
            return f"Post ID: {post_id}\n🔗 https://www.binance.com/en/square/post/{post_id}"
        return f"Lỗi Square: {r.status_code}"
    except Exception as e:
        logger.error(f"Square error: {e}")
        return "Lỗi khi đăng Square"

# ================== KEEP ALIVE ==================
def keep_alive():
    while True:
        try:
            hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'bnsq.onrender.com')
            requests.get(f"https://{hostname}/ping", timeout=10)
            logger.info("Self-ping OK")
        except:
            pass
        time.sleep(240)

# ================== START ==================
if __name__ == "__main__":
    logger.info("🚀 Bot 5.0 Fixed đang khởi động...")

    # Force reset webhook
    bot.remove_webhook()
    time.sleep(1.5)
    
    success = bot.set_webhook(
        url=WEBHOOK_URL,
        max_connections=100,
        drop_pending_updates=True
    )
    
    logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}")
    logger.info(f"✅ Set webhook thành công: {success}")

    # Kiểm tra webhook info
    try:
        info = bot.get_webhook_info()
        logger.info(f"📊 Webhook status: {info.url if info else 'None'}")
    except Exception as e:
        logger.error(f"Không lấy được webhook info: {e}")

    threading.Thread(target=keep_alive, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
