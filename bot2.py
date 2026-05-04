"""
Remake Pixel — Bot 2 (FAST/SLIM)
================================
Fluxo:
  /start → escolha de língua (PT/EN/ES) → tutorial → user envia foto →
    - ADMIN: 2 botões (🎨 Estilos | ✏️ Prompt livre)  · custo 0
    - USER : 1 botão  (🎨 Estilos)                    · custo 10 cred

Partilha MongoDB e estilos com o bot1 e o site (via /app/bot/shared/*).
Quem não tem créditos é redirecionado para o bot1 (link Stripe lá dentro).
"""
from __future__ import annotations
import os
import sys
import logging
import threading
import traceback
from io import BytesIO
from pathlib import Path

# Allow `from shared.*` imports when launched as `python bot/bot2.py`
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

from dotenv import load_dotenv
load_dotenv(_THIS_DIR.parent / "backend" / ".env")

import telebot
from telebot import types
import replicate
import requests

from shared import db as sdb
from shared import styles as sst

# ===================== CONFIG =====================
TOKEN = os.environ.get("TELEGRAM_TOKEN_BOT2")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN_BOT2 não definido em /app/backend/.env")

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

BOT1_USERNAME = os.environ.get("BOT_USERNAME", "RemakePix_bot")
GENERATION_COST = int(os.environ.get("GENERATION_COST", "10"))
SOURCE_TAG = "bot2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [bot2] %(levelname)s %(message)s")
log = logging.getLogger("bot2")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Per-user pending photo state (in-memory; OK for slim bot)
PENDING_PHOTOS: dict[int, dict] = {}
# user_id -> {file_id, expects_prompt: bool}

# ===================== I18N =====================
T = {
    "pt": {
        "welcome": "👋 Bem-vindo ao <b>Remake Pixel Quick</b>!\n\nEscolhe o idioma:",
        "lang_set": "✅ Idioma: <b>Português</b>",
        "tutorial": (
            "🎨 <b>Como funciona</b>\n\n"
            "1. Envia uma foto tua\n"
            "2. Escolhe um estilo do catálogo\n"
            "3. Recebe a tua imagem editada (~15s)\n\n"
            "💰 Custo: <b>{cost} créditos</b> por imagem\n"
            "🎁 Tens <b>{credits}</b> créditos para começar!\n\n"
            "📷 Envia agora a tua foto."
        ),
        "tutorial_admin": (
            "👑 <b>Modo Admin ativo</b>\n\n"
            "✨ Créditos ilimitados\n"
            "✨ Botão de prompt livre desbloqueado\n\n"
            "📷 Envia a tua foto."
        ),
        "photo_received": "📸 <b>Foto recebida!</b>\nO que queres fazer?",
        "btn_styles": "🎨 Escolher Estilo",
        "btn_freeprompt": "✏️ Prompt livre (admin)",
        "btn_cancel": "❌ Cancelar",
        "send_photo_first": "📷 Envia primeiro uma foto.",
        "no_credits": (
            "💸 <b>Sem créditos suficientes</b> (precisas de {cost}, tens {have}).\n\n"
            "🛒 Compra créditos no bot principal:\n"
            "👉 https://t.me/{bot1}\n\n"
            "Os créditos comprados aí funcionam aqui automaticamente."
        ),
        "choose_cat": "Escolhe uma categoria:",
        "choose_style": "Escolhe um estilo:",
        "locked": "🔒 <b>Estilo Premium</b>\n\nDesbloqueia comprando qualquer pacote no bot principal:\n👉 https://t.me/{bot1}",
        "type_prompt": "✏️ <b>Prompt livre</b>\n\nDigita o que queres gerar (texto livre).",
        "generating": "⏳ A gerar... (~15s)",
        "result": "✅ <b>Pronto!</b>\n💰 Créditos: <b>{credits}</b>",
        "error": "❌ Erro ao gerar. Os créditos não foram cobrados. Tenta outra foto/estilo.",
        "cancelled": "❌ Cancelado.",
        "credits_label": "💰 Créditos: <b>{credits}</b>",
        "back": "« Voltar",
    },
    "en": {
        "welcome": "👋 Welcome to <b>Remake Pixel Quick</b>!\n\nChoose your language:",
        "lang_set": "✅ Language: <b>English</b>",
        "tutorial": (
            "🎨 <b>How it works</b>\n\n"
            "1. Send a photo of yourself\n"
            "2. Pick a style from the catalog\n"
            "3. Receive your edited image (~15s)\n\n"
            "💰 Cost: <b>{cost} credits</b> per image\n"
            "🎁 You have <b>{credits}</b> credits to start!\n\n"
            "📷 Send your photo now."
        ),
        "tutorial_admin": (
            "👑 <b>Admin mode active</b>\n\n"
            "✨ Unlimited credits\n"
            "✨ Free-prompt button unlocked\n\n"
            "📷 Send your photo."
        ),
        "photo_received": "📸 <b>Photo received!</b>\nWhat do you want to do?",
        "btn_styles": "🎨 Pick a Style",
        "btn_freeprompt": "✏️ Free prompt (admin)",
        "btn_cancel": "❌ Cancel",
        "send_photo_first": "📷 Send a photo first.",
        "no_credits": (
            "💸 <b>Not enough credits</b> (need {cost}, have {have}).\n\n"
            "🛒 Buy credits on the main bot:\n"
            "👉 https://t.me/{bot1}\n\n"
            "Credits bought there work here automatically."
        ),
        "choose_cat": "Pick a category:",
        "choose_style": "Pick a style:",
        "locked": "🔒 <b>Premium style</b>\n\nUnlock by buying any pack on the main bot:\n👉 https://t.me/{bot1}",
        "type_prompt": "✏️ <b>Free prompt</b>\n\nType what you want to generate.",
        "generating": "⏳ Generating... (~15s)",
        "result": "✅ <b>Done!</b>\n💰 Credits: <b>{credits}</b>",
        "error": "❌ Generation failed. Credits were not charged. Try another photo/style.",
        "cancelled": "❌ Cancelled.",
        "credits_label": "💰 Credits: <b>{credits}</b>",
        "back": "« Back",
    },
    "es": {
        "welcome": "👋 Bienvenido a <b>Remake Pixel Quick</b>!\n\nElige idioma:",
        "lang_set": "✅ Idioma: <b>Español</b>",
        "tutorial": (
            "🎨 <b>Cómo funciona</b>\n\n"
            "1. Envía una foto tuya\n"
            "2. Elige un estilo del catálogo\n"
            "3. Recibe tu imagen editada (~15s)\n\n"
            "💰 Coste: <b>{cost} créditos</b> por imagen\n"
            "🎁 Tienes <b>{credits}</b> créditos para empezar!\n\n"
            "📷 Envía tu foto ahora."
        ),
        "tutorial_admin": (
            "👑 <b>Modo Admin activo</b>\n\n"
            "✨ Créditos ilimitados\n"
            "✨ Botón prompt libre desbloqueado\n\n"
            "📷 Envía tu foto."
        ),
        "photo_received": "📸 <b>¡Foto recibida!</b>\n¿Qué quieres hacer?",
        "btn_styles": "🎨 Elegir Estilo",
        "btn_freeprompt": "✏️ Prompt libre (admin)",
        "btn_cancel": "❌ Cancelar",
        "send_photo_first": "📷 Envía primero una foto.",
        "no_credits": (
            "💸 <b>Créditos insuficientes</b> (necesitas {cost}, tienes {have}).\n\n"
            "🛒 Compra créditos en el bot principal:\n"
            "👉 https://t.me/{bot1}\n\n"
            "Los créditos comprados allí funcionan aquí automáticamente."
        ),
        "choose_cat": "Elige una categoría:",
        "choose_style": "Elige un estilo:",
        "locked": "🔒 <b>Estilo Premium</b>\n\nDesbloquea comprando cualquier paquete en el bot principal:\n👉 https://t.me/{bot1}",
        "type_prompt": "✏️ <b>Prompt libre</b>\n\nEscribe lo que quieres generar.",
        "generating": "⏳ Generando... (~15s)",
        "result": "✅ <b>¡Listo!</b>\n💰 Créditos: <b>{credits}</b>",
        "error": "❌ Falló la generación. No se cobraron créditos. Prueba con otra foto/estilo.",
        "cancelled": "❌ Cancelado.",
        "credits_label": "💰 Créditos: <b>{credits}</b>",
        "back": "« Volver",
    },
}


def t(user_id: int, key: str, **kw) -> str:
    lang = sdb.get_lang(user_id) or "pt"
    txt = T.get(lang, T["pt"]).get(key) or T["pt"].get(key, key)
    return txt.format(bot1=BOT1_USERNAME, **kw) if kw or "{bot1}" in txt else txt


# ===================== HANDLERS =====================
@bot.message_handler(commands=["start"])
def cmd_start(msg: types.Message):
    uid = msg.from_user.id
    sdb.get_or_create_user(uid, source=SOURCE_TAG, name=msg.from_user.first_name)
    sdb.log_event(telegram_id=uid, type_="start", payload={"source": SOURCE_TAG})

    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("🇵🇹 PT", callback_data="lang_pt"),
        types.InlineKeyboardButton("🇬🇧 EN", callback_data="lang_en"),
        types.InlineKeyboardButton("🇪🇸 ES", callback_data="lang_es"),
    )
    bot.send_message(uid, T["pt"]["welcome"], reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def cb_lang(c: types.CallbackQuery):
    uid = c.from_user.id
    lang = c.data.split("_", 1)[1]
    sdb.set_lang(uid, lang)
    bot.answer_callback_query(c.id)
    user = sdb.get_user_by_telegram(uid)
    credits = (user or {}).get("credits", 0)
    is_admin = sdb.is_super_admin(uid)
    bot.edit_message_text(t(uid, "lang_set"), uid, c.message.message_id)
    if is_admin:
        bot.send_message(uid, t(uid, "tutorial_admin"))
    else:
        bot.send_message(uid, t(uid, "tutorial", cost=GENERATION_COST, credits=credits))


@bot.message_handler(content_types=["photo"])
def on_photo(msg: types.Message):
    uid = msg.from_user.id
    sdb.get_or_create_user(uid, source=SOURCE_TAG, name=msg.from_user.first_name)
    file_id = msg.photo[-1].file_id
    PENDING_PHOTOS[uid] = {"file_id": file_id, "expects_prompt": False}

    is_admin = sdb.is_super_admin(uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(t(uid, "btn_styles"), callback_data="cats"))
    if is_admin:
        kb.add(types.InlineKeyboardButton(t(uid, "btn_freeprompt"), callback_data="freeprompt"))
    kb.add(types.InlineKeyboardButton(t(uid, "btn_cancel"), callback_data="cancel"))

    bot.send_message(uid, t(uid, "photo_received"), reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "cancel")
def cb_cancel(c: types.CallbackQuery):
    uid = c.from_user.id
    PENDING_PHOTOS.pop(uid, None)
    bot.answer_callback_query(c.id)
    bot.edit_message_text(t(uid, "cancelled"), uid, c.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data == "cats")
def cb_cats(c: types.CallbackQuery):
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    if uid not in PENDING_PHOTOS:
        bot.edit_message_text(t(uid, "send_photo_first"), uid, c.message.message_id)
        return
    lang = sdb.get_lang(uid) or "pt"
    cats_present = []
    for cat in sst.BOT2_CATEGORIES:
        if any(s.get("cat") == cat for s in sst.STYLES.values()):
            cats_present.append(cat)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cat in cats_present:
        label = sst.CAT_LABELS[lang].get(cat, cat)
        kb.add(types.InlineKeyboardButton(label, callback_data=f"cat:{cat}:0"))
    kb.add(types.InlineKeyboardButton(t(uid, "back"), callback_data="back_main"))
    bot.edit_message_text(t(uid, "choose_cat"), uid, c.message.message_id, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(c: types.CallbackQuery):
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    is_admin = sdb.is_super_admin(uid)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(t(uid, "btn_styles"), callback_data="cats"))
    if is_admin:
        kb.add(types.InlineKeyboardButton(t(uid, "btn_freeprompt"), callback_data="freeprompt"))
    kb.add(types.InlineKeyboardButton(t(uid, "btn_cancel"), callback_data="cancel"))
    bot.edit_message_text(t(uid, "photo_received"), uid, c.message.message_id, reply_markup=kb)


PAGE_SIZE = 8


@bot.callback_query_handler(func=lambda c: c.data.startswith("cat:"))
def cb_cat(c: types.CallbackQuery):
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    _, cat, page_str = c.data.split(":")
    page = int(page_str)
    user = sdb.get_user_by_telegram(uid) or {}
    items = sorted(
        [s for s in sst.STYLES.values() if s.get("cat") == cat],
        key=lambda x: (x.get("locked", False), x.get("nome", "")),
    )
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in chunk:
        prefix = "🔒 " if sdb.is_style_locked_for(user, s) else ""
        kb.add(types.InlineKeyboardButton(prefix + s.get("nome", s["key"]), callback_data=f"st:{s['key']}"))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("‹", callback_data=f"cat:{cat}:{page-1}"))
    nav.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("›", callback_data=f"cat:{cat}:{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton(t(uid, "back"), callback_data="cats"))
    bot.edit_message_text(t(uid, "choose_style"), uid, c.message.message_id, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(c):
    bot.answer_callback_query(c.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("st:"))
def cb_style(c: types.CallbackQuery):
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    style_key = c.data.split(":", 1)[1]
    style = sst.get_style(style_key)
    if not style:
        bot.send_message(uid, "Estilo não encontrado.")
        return
    user = sdb.get_user_by_telegram(uid) or {}
    if sdb.is_style_locked_for(user, style):
        bot.edit_message_text(t(uid, "locked"), uid, c.message.message_id, disable_web_page_preview=True)
        return
    if uid not in PENDING_PHOTOS:
        bot.edit_message_text(t(uid, "send_photo_first"), uid, c.message.message_id)
        return
    threading.Thread(target=_run_generation, args=(uid, c.message.message_id, style_key, ""), daemon=True).start()


@bot.callback_query_handler(func=lambda c: c.data == "freeprompt")
def cb_freeprompt(c: types.CallbackQuery):
    uid = c.from_user.id
    bot.answer_callback_query(c.id)
    if not sdb.is_super_admin(uid):
        return  # silent reject
    if uid not in PENDING_PHOTOS:
        bot.edit_message_text(t(uid, "send_photo_first"), uid, c.message.message_id)
        return
    PENDING_PHOTOS[uid]["expects_prompt"] = True
    bot.edit_message_text(t(uid, "type_prompt"), uid, c.message.message_id)


@bot.message_handler(func=lambda m: True, content_types=["text"])
def on_text(msg: types.Message):
    uid = msg.from_user.id
    state = PENDING_PHOTOS.get(uid)
    if not state or not state.get("expects_prompt"):
        return  # ignore random text
    if not sdb.is_super_admin(uid):
        return
    prompt = (msg.text or "").strip()
    if not prompt:
        return
    state["expects_prompt"] = False
    threading.Thread(target=_run_generation, args=(uid, None, None, prompt), daemon=True).start()


# ===================== GENERATION =====================
def _download_photo(file_id: str) -> bytes:
    info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TOKEN}/{info.file_path}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def _to_data_url(b: bytes, mime: str = "image/jpeg") -> str:
    import base64
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


def _run_generation(uid: int, status_msg_id: int | None, style_key: str | None, free_prompt: str):
    is_admin = sdb.is_super_admin(uid)
    state = PENDING_PHOTOS.get(uid)
    if not state:
        bot.send_message(uid, t(uid, "send_photo_first"))
        return
    file_id = state["file_id"]

    user = sdb.get_user_by_telegram(uid) or sdb.get_or_create_user(uid, source=SOURCE_TAG)

    # Credit check (admin bypass)
    if not is_admin:
        if user.get("credits", 0) < GENERATION_COST:
            bot.send_message(uid, t(uid, "no_credits", cost=GENERATION_COST, have=user.get("credits", 0)),
                             disable_web_page_preview=True)
            return

    progress = bot.send_message(uid, t(uid, "generating"))

    # Debit FIRST (admin bypass)
    debited = False
    if not is_admin:
        if not sdb.use_credits(uid, GENERATION_COST):
            bot.edit_message_text(t(uid, "no_credits", cost=GENERATION_COST, have=user.get("credits", 0)),
                                  uid, progress.message_id, disable_web_page_preview=True)
            return
        debited = True

    try:
        img_bytes = _download_photo(file_id)
        data_url = _to_data_url(img_bytes)
        final_prompt = sst.build_final_prompt(style_key, free_prompt)

        sdb.log_event(telegram_id=uid, type_="generate_start",
                      payload={"source": SOURCE_TAG, "style_key": style_key, "admin": is_admin})

        output = replicate.run(
            "xai/grok-imagine-image",
            input={"prompt": final_prompt, "image_input": data_url, "aspect_ratio": "1:1"},
        )
        if hasattr(output, "__iter__") and not isinstance(output, str):
            urls = [str(x) for x in output]
        else:
            urls = [str(output)]
        result_url = urls[0] if urls else None
        if not result_url:
            raise RuntimeError("No image returned")

        # Save to history
        sdb.save_creation(
            user_id=user["id"],
            source=SOURCE_TAG,
            style_key=style_key,
            prompt=final_prompt,
            result_url=result_url,
        )

        # Send photo
        try:
            bot.delete_message(uid, progress.message_id)
        except Exception:
            pass
        new_credits = sdb.get_credits(uid)
        caption = t(uid, "result", credits="∞" if is_admin else new_credits)
        bot.send_photo(uid, result_url, caption=caption)
        PENDING_PHOTOS.pop(uid, None)
    except Exception as e:
        log.error(f"Generation failed for {uid}: {e}\n{traceback.format_exc()}")
        # Refund
        if debited:
            sdb.add_credits(uid, GENERATION_COST, motivo="reembolso")
        try:
            bot.edit_message_text(t(uid, "error"), uid, progress.message_id)
        except Exception:
            bot.send_message(uid, t(uid, "error"))


@bot.message_handler(commands=["creditos", "credits", "saldo", "balance"])
def cmd_credits(msg: types.Message):
    uid = msg.from_user.id
    sdb.get_or_create_user(uid, source=SOURCE_TAG)
    if sdb.is_super_admin(uid):
        bot.reply_to(msg, "👑 Admin · ∞ créditos")
        return
    c = sdb.get_credits(uid)
    bot.reply_to(msg, t(uid, "credits_label", credits=c) +
                 f"\n\n🛒 https://t.me/{BOT1_USERNAME} para comprar mais.",
                 disable_web_page_preview=True)


@bot.message_handler(commands=["help", "ajuda"])
def cmd_help(msg: types.Message):
    cmd_start(msg)


# ===================== STARTUP =====================
if __name__ == "__main__":
    log.info(f"Bot 2 (FAST) starting · token=...{TOKEN[-6:]} · super_admins={sdb.SUPER_ADMIN_IDS}")
    log.info(f"Styles loaded: {len(sst.STYLES)} · Mongo: {sdb.DB_NAME}")
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=30)
