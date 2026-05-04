import os
import logging
import threading
import requests
import telebot
import replicate

# ================= CONFIG =================
TOKEN = os.environ.get("TELEGRAM_TOKEN_BOT2")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

if not TOKEN:
    raise Exception("Falta TELEGRAM_TOKEN_BOT2")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)

PENDING = {}

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🚀 Envia uma foto para começar.")

# ================= FOTO =================
@bot.message_handler(content_types=['photo'])
def on_photo(msg):
    uid = msg.from_user.id
    file_id = msg.photo[-1].file_id

    PENDING[uid] = {
        "file_id": file_id,
        "waiting_prompt": True
    }

    bot.send_message(uid, "✏️ Escreve o prompt para a imagem:")

# ================= PROMPT =================
@bot.message_handler(func=lambda m: True)
def get_prompt(msg):
    uid = msg.from_user.id

    if uid not in PENDING:
        return

    if not PENDING[uid].get("waiting_prompt"):
        return

    prompt = msg.text
    PENDING[uid]["waiting_prompt"] = False
    PENDING[uid]["prompt"] = prompt

    bot.send_message(uid, "⏳ A gerar...")

    threading.Thread(target=run_generation, args=(uid,), daemon=True).start()

# ================= DOWNLOAD =================
def download_photo(file_id):
    info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TOKEN}/{info.file_path}"
    r = requests.get(url)
    return r.content

def to_data_url(b):
    import base64
    return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"

# ================= GENERATE =================
def run_generation(uid):
    try:
        data = PENDING[uid]
        file_id = data["file_id"]
        prompt = data["prompt"]

        img = download_photo(file_id)
        data_url = to_data_url(img)

        output = replicate.run(
            "xai/grok-imagine-image",
            input={
                "prompt": prompt,
                "image_input": data_url
            }
        )

        if isinstance(output, list):
            url = str(output[0])
        else:
            url = str(output)

        bot.send_photo(uid, url, caption="✅ Pronto!")

    except Exception as e:
        logging.error(e)
        bot.send_message(uid, "❌ Erro ao gerar imagem")

    finally:
        PENDING.pop(uid, None)

# ================= RUN =================
print("Bot 2 a rodar...")
bot.infinity_polling()