from __future__ import annotations
import os
import logging
import threading
import traceback
from pathlib import Path
from io import BytesIO

import telebot
from telebot import types
import replicate
import requests

# ===================== CONFIG =====================
TOKEN = os.environ.get("TELEGRAM_TOKEN_BOT2")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN_BOT2 não definido")

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot2")

bot = telebot.TeleBot(TOKEN)

# guardar fotos temporárias
PENDING = {}

# ===================== START =====================
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(msg, "🚀 Bot 2 ativo!\n\nEnvia uma foto.")

# ===================== FOTO =====================
@bot.message_handler(content_types=["photo"])
def on_photo(msg):
    uid = msg.from_user.id
    file_id = msg.photo[-1].file_id
    PENDING[uid] = file_id

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎨 Gerar imagem", callback_data="generate"))

    bot.send_message(uid, "📸 Foto recebida!", reply_markup=kb)

# ===================== GERAR =====================
@bot.callback_query_handler(func=lambda c: c.data == "generate")
def generate(c):
    uid = c.from_user.id

    if uid not in PENDING:
        bot.send_message(uid, "❌ Envia uma foto primeiro")
        return

    bot.send_message(uid, "⏳ A gerar...")

    threading.Thread(target=run_generation, args=(uid,), daemon=True).start()

def download_photo(file_id):
    info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TOKEN}/{info.file_path}"
    r = requests.get(url)
    return r.content

def to_data_url(b):
    import base64
    return f"data:image/jpeg;base64,{base64.b64encode(b).decode()}"

def run_generation(uid):
    try:
        file_id = PENDING[uid]

        img = download_photo(file_id)
        data_url = to_data_url(img)

        output = replicate.run(
            "xai/grok-imagine-image",
            input={
                "prompt": "high quality portrait, realistic",
                "image_input": data_url
            }
        )

        if isinstance(output, list):
            url = str(output[0])
        else:
            url = str(output)

        bot.send_photo(uid, url, caption="✅ Pronto!")

    except Exception as e:
        log.error(e)
        bot.send_message(uid, "❌ Erro ao gerar imagem")

# ===================== RUN =====================
if __name__ == "__main__":
    print("Bot2 a rodar...")
    bot.infinity_polling()