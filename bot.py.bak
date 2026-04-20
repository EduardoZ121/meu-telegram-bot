# -*- coding: utf-8 -*-
"""
Remake Pixel Bot - VERSÃO SUPREMA 👑
Todas as funcionalidades avançadas implementadas
"""
import sys
import os

# Forçar encoding UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

import telebot
import replicate
import requests
import base64
import io
from PIL import Image
import os
import time
import re
import json
import stripe
from openai import OpenAI
from threading import Lock, Thread
from flask import Flask, request, jsonify
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import shutil
import random

# ==================== CONFIGURAÇÕES ====================
SUPER_ADMIN_IDS = [6936852095]  # Admin principal - NUNCA pode ser removido
ADMIN_IDS = [6936852095]  # Sera atualizado com admins secundarios
BOT_USERNAME = "RemakePix_bot"
SUPORTE_TELEGRAM = "@Remake_Pixel_adm"
SECONDARY_ADMINS_FILE = "secondary_admins.json"

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_SUCCESS_URL = f"https://t.me/{BOT_USERNAME}?start=success"
STRIPE_CANCEL_URL = f"https://t.me/{BOT_USERNAME}?start=cancel"

# Verificar chaves obrigatórias
missing = []
if not BOT_TOKEN: missing.append("TELEGRAM_TOKEN")
if not REPLICATE_API_TOKEN: missing.append("REPLICATE_API_TOKEN")
if not OPENAI_API_KEY: missing.append("OPENAI_API_KEY")
if not STRIPE_SECRET_KEY: missing.append("STRIPE_SECRET_KEY")
if missing:
    print(f"⚠️ AVISO: Variáveis em falta: {', '.join(missing)}")
    print("Configure no Render: Dashboard → Environment → Add Variable")

if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN.strip()
    print(f"✅ Replicate token: {REPLICATE_API_TOKEN[:8]}...{REPLICATE_API_TOKEN[-4:]}")
else:
    print("❌ REPLICATE_API_TOKEN em falta!")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY.strip()
client = OpenAI(api_key=(OPENAI_API_KEY or "dummy").strip())

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

@app.route("/health")
def health():
    return {"status": "online", "bot": "Remake Pixel"}, 200

# ==================== LOGGING PROFISSIONAL ====================
def setup_logger():
    logger = logging.getLogger('Remake Pixel')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh = RotatingFileHandler('bot.log', maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    fh.setFormatter(formatter)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

logger = setup_logger()

# ==================== RATE LIMITING ====================
class RateLimiter:
    def __init__(self):
        self.user_actions = defaultdict(lambda: {'images': [], 'messages': []})
        self.lock = Lock()
        self.RATE_LIMIT_IMAGES = 5
        self.RATE_LIMIT_MESSAGES = 30
        self.WINDOW = 60
    
    def check_limit(self, user_id, action_type='messages'):
        with self.lock:
            current_time = time.time()
            cutoff = current_time - self.WINDOW
            self.user_actions[user_id][action_type] = [t for t in self.user_actions[user_id][action_type] if t > cutoff]
            limit = self.RATE_LIMIT_IMAGES if action_type == 'images' else self.RATE_LIMIT_MESSAGES
            current = len(self.user_actions[user_id][action_type])
            if current >= limit:
                return False, 0
            self.user_actions[user_id][action_type].append(current_time)
            return True, limit - current - 1
    
    def get_wait_time(self, user_id, action_type='messages'):
        with self.lock:
            if not self.user_actions[user_id][action_type]:
                return 0
            oldest = min(self.user_actions[user_id][action_type])
            wait = int(self.WINDOW - (time.time() - oldest))
            return max(0, wait)

rate_limiter = RateLimiter()

# ==================== BACKUP AUTOMÁTICO ====================
class BackupManager:
    def __init__(self):
        self.backup_dir = "backups"
        self.interval = 3600
        self.keep_days = 7
        self.running = False
        self.thread = None
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def start(self):
        print("⚠️ Backup automático DESATIVADO temporariamente (evitar erro de permissão)")
        logger.info("Backup automático desativado")
        return  # NÃO inicia backup
    
    def _backup_loop(self):
        while self.running:
            try:
                self.create_backup()
                self.cleanup_old()
            except Exception as e:
                logger.error(f"Erro no backup: {e}")
            time.sleep(self.interval)
    
    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        files = ['user_credits.json', 'user_languages.json', 'user_settings.json', 
                 'pending_approvals.json', 'user_history.json', 'referrals.json', 
                 'user_onboarding.json', 'user_errors.json', 'user_favorites.json', 
                 'user_statistics.json', 'shared_creations.json']
        count = 0
        for f in files:
            if os.path.exists(f):
                shutil.copy2(f, os.path.join(backup_path, f))
                count += 1
        logger.info(f"Backup criado: {timestamp} ({count} arquivos)")
    
    def cleanup_old(self):
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        for name in os.listdir(self.backup_dir):
            path = os.path.join(self.backup_dir, name)
            if os.path.isdir(path):
                try:
                    ts = name.replace("backup_", "")
                    date = datetime.strptime(ts, "%Y%m%d_%H%M%S")
                    if date < cutoff:
                        shutil.rmtree(path)
                except:
                    pass

backup_manager = BackupManager()

# ==================== VALIDAÇÕES ====================
def validate_prompt(prompt):
    if not prompt or len(prompt) < 5:
        return False, "Prompt muito curto (mínimo 5 caracteres)"
    if len(prompt) > 500:
        return False, "Prompt muito longo (máximo 500 caracteres)"
    if re.search(r'(.)\1{10,}', prompt):
        return False, "Spam detectado"
    return True, None

# ==================== NOTIFICAÇÕES ADMIN ====================
def notify_admin(message, level="info"):
    icons = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "success": "✅", "money": "💰"}
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"{icons.get(level, '📢')} <b>NOTIFICAÇÃO</b>\n\n{message}", parse_mode='HTML')
        except:
            pass

def diagnose_and_notify(error, context=""):
    error_str = str(error)
    diagnosis = "🟣 Erro não catalogado."
    if "rate limit" in error_str.lower():
        diagnosis = "🔴 Rate limit."
    elif "sensitive" in error_str.lower() or "safety" in error_str.lower():
        diagnosis = "🟠 Filtro de conteúdo ativado."
    elif "timeout" in error_str.lower():
        diagnosis = "🟡 Timeout."
    elif "401" in error_str or "unauthenticated" in error_str.lower():
        diagnosis = "🔴 Token inválido ou expirado."
    elif "json" in error_str.lower():
        diagnosis = "🔵 Erro de serialização."
    notify_admin(f"<b>ERRO</b>\n\n📍 {context}\n🔍 {diagnosis}\n\n<code>{error_str[:300]}</code>", "error")
    logger.error(f"{context}: {error_str}")

def error_message(lang="pt"):
    """Mensagem de erro padronizada"""
    texts = {
        "pt": f"❌ Erro ao processar.\n💰 Créditos não foram consumidos.\n📩 Contacte o ADM: {SUPORTE_TELEGRAM}",
        "en": f"❌ Processing error.\n💰 Credits were not consumed.\n📩 Contact ADM: {SUPORTE_TELEGRAM}",
        "es": f"❌ Error al procesar.\n💰 Créditos no fueron consumidos.\n📩 Contacte ADM: {SUPORTE_TELEGRAM}",
    }
    return texts.get(lang, texts["pt"])

# ==================== ARQUIVOS JSON ====================
USER_LANGUAGES_FILE = "user_languages.json"
CREDITS_FILE = "user_credits.json"
SETTINGS_FILE = "user_settings.json"
PENDING_FILE = "pending_approvals.json"
HISTORY_FILE = "user_history.json"
REFERRAL_FILE = "referrals.json"
ONBOARDING_FILE = "user_onboarding.json"
ERRORS_FILE = "user_errors.json"
FAVORITES_FILE = "user_favorites.json"
STATISTICS_FILE = "user_statistics.json"
SHARED_CREATIONS_FILE = "shared_creations.json"

LANG_LOCK = Lock()
CREDITS_LOCK = Lock()
SETTINGS_LOCK = Lock()
PENDING_LOCK = Lock()
HISTORY_LOCK = Lock()
REF_LOCK = Lock()
ONBOARD_LOCK = Lock()
ERRORS_LOCK = Lock()
FAVORITES_LOCK = Lock()
STATS_LOCK = Lock()
SHARED_LOCK = Lock()

SUPPORTED_LANGUAGES = {"pt": "🇵🇹 Português", "en": "🇬🇧 English", "es": "🇪🇸 Español", "fr": "🇫🇷 Français"}

# ==================== ADMINS SECUNDARIOS ====================
def load_secondary_admins():
    """Carrega admins secundarios e atualiza ADMIN_IDS"""
    global ADMIN_IDS
    data = load_json(SECONDARY_ADMINS_FILE)
    secondary = [int(uid) for uid in data.get("admins", {}).keys()]
    ADMIN_IDS = list(set(SUPER_ADMIN_IDS + secondary))
    return data.get("admins", {})

def add_secondary_admin(user_id, name="", username=""):
    """Adiciona admin secundario"""
    data = load_json(SECONDARY_ADMINS_FILE)
    if "admins" not in data:
        data["admins"] = {}
    data["admins"][str(user_id)] = {
        "name": name,
        "username": username,
        "added_at": datetime.now().isoformat()
    }
    save_json(SECONDARY_ADMINS_FILE, data, Lock())
    load_secondary_admins()
    return True

def remove_secondary_admin(user_id):
    """Remove admin secundario"""
    data = load_json(SECONDARY_ADMINS_FILE)
    if str(user_id) in data.get("admins", {}):
        del data["admins"][str(user_id)]
        save_json(SECONDARY_ADMINS_FILE, data, Lock())
        load_secondary_admins()
        return True
    return False

def is_super_admin(user_id):
    """Verifica se e o admin principal"""
    return user_id in SUPER_ADMIN_IDS

def is_any_admin(user_id):
    """Verifica se e qualquer tipo de admin"""
    load_secondary_admins()
    return user_id in ADMIN_IDS

# Carregar admins ao iniciar - sera chamado depois de load_json

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data, lock):
    with lock:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Agora que load_json existe, carregar admins secundarios
load_secondary_admins()

# ==================== SISTEMA DE ERROS ====================
def save_user_error(user_id, error_type, error_msg, context=""):
    data = load_json(ERRORS_FILE)
    user_str = str(user_id)
    if user_str not in data:
        data[user_str] = []
    data[user_str].insert(0, {
        "type": error_type,
        "message": error_msg,
        "context": context,
        "timestamp": datetime.now().isoformat()
    })
    data[user_str] = data[user_str][:5]
    save_json(ERRORS_FILE, data, ERRORS_LOCK)
    
    # 🆕 Notificar admin sobre erro crítico
    try:
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    f"⚠️ <b>Erro Detectado</b>\n\n"
                    f"👤 User: <code>{user_id}</code>\n"
                    f"🔴 Tipo: {error_type}\n"
                    f"📝 Mensagem: {error_msg[:100]}\n"
                    f"📍 Contexto: {context}\n"
                    f"⏰ {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode='HTML'
                )
            except:
                pass
    except:
        pass

def get_user_errors(user_id):
    data = load_json(ERRORS_FILE)
    return data.get(str(user_id), [])

# ==================== ONBOARDING ====================
def is_onboarded(user_id):
    data = load_json(ONBOARDING_FILE)
    return data.get(str(user_id), False)

def set_onboarded(user_id):
    data = load_json(ONBOARDING_FILE)
    data[str(user_id)] = True
    save_json(ONBOARDING_FILE, data, ONBOARD_LOCK)

# ==================== IDIOMAS ====================
def get_user_lang(user_id):
    data = load_json(USER_LANGUAGES_FILE)
    return data.get(str(user_id), "pt")

def set_user_lang(user_id, lang_code):
    if lang_code not in SUPPORTED_LANGUAGES:
        print(f"❌ Idioma inválido: {lang_code}")
        return False
    data = load_json(USER_LANGUAGES_FILE)
    data[str(user_id)] = lang_code
    save_json(USER_LANGUAGES_FILE, data, LANG_LOCK)
    print(f"✅ Idioma '{lang_code}' salvo para user {user_id} em {USER_LANGUAGES_FILE}")
    logger.info(f"User {user_id} alterou idioma para {lang_code}")
    return True

# ==================== CRÉDITOS ====================
PACOTES = {
    1: {"nome": "Pacote Básico", "creditos": 120, "preco": 500},
    2: {"nome": "Pacote Médio", "creditos": 350, "preco": 1200},
    3: {"nome": "Pacote Pro", "creditos": 800, "preco": 2200}
}

def get_user_credits(user_id):
    data = load_json(CREDITS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            "creditos": 5,
            "total_usado": 0,
            "historico": [],
            "created_at": datetime.now().isoformat()
        }
        save_json(CREDITS_FILE, data, CREDITS_LOCK)
        logger.info(f"Novo usuário {user_id} com 5 créditos")
        
        # 🆕 NOTIFICAÇÃO INSTANTÂNEA
        try:
            for admin_id in ADMIN_IDS:
                bot.send_message(
                    admin_id,
                    f"🎉 <b>NOVO USUÁRIO!</b>\n\n"
                    f"👤 ID: <code>{user_id}</code>\n"
                    f"💳 Créditos iniciais: 5\n"
                    f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Erro ao notificar admin: {e}")
    
    return data[user_id_str]["creditos"]

def use_credit(user_id, quantidade=1):
    data = load_json(CREDITS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in data:
        get_user_credits(user_id)
        data = load_json(CREDITS_FILE)
    if data[user_id_str]["creditos"] >= quantidade:
        data[user_id_str]["creditos"] -= quantidade
        data[user_id_str]["total_usado"] += quantidade
        save_json(CREDITS_FILE, data, CREDITS_LOCK)
        logger.info(f"User {user_id} usou {quantidade} crédito(s)")
        return True
    return False

def add_credits(user_id, quantidade, tipo="compra"):
    data = load_json(CREDITS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            "creditos": 0,
            "total_usado": 0,
            "historico": [],
            "created_at": datetime.now().isoformat()
        }
    data[user_id_str]["creditos"] += quantidade
    save_json(CREDITS_FILE, data, CREDITS_LOCK)
    logger.info(f"User {user_id} recebeu {quantidade} crédito(s) ({tipo})")
    return data[user_id_str]["creditos"]

# ==================== ESTILOS PREDEFINIDOS (PERCHANCE) ====================
ASPECT_RATIOS = {
    "portrait": {"ratio": "3:4", "emoji": "📱", "desc": "Vertical (3:4)"},
    "square": {"ratio": "1:1", "emoji": "⬜", "desc": "Quadrado (1:1)"},
    "landscape": {"ratio": "16:9", "emoji": "🖼️", "desc": "Horizontal (16:9)"},
    "story": {"ratio": "9:16", "emoji": "📲", "desc": "Story/TikTok (9:16)"},
    "insta": {"ratio": "4:5", "emoji": "📷", "desc": "Instagram (4:5)"},
    "wide": {"ratio": "21:9", "emoji": "🎬", "desc": "Ultrawide (21:9)"}
}

VISUAL_STYLES = {
    "livre": {"emoji": "🆓", "desc": "Livre/Personalizado", "suffix": ""},
    "anime": {"emoji": "🎌", "desc": "Anime", "suffix": ", anime style, manga aesthetic"},
    "ghibli": {"emoji": "🌿", "desc": "Ghibli", "suffix": ", Studio Ghibli style, soft colors, Miyazaki"},
    "disney_2d": {"emoji": "👸", "desc": "Disney 2D", "suffix": ", Disney 2D animation style"},
    "disney_3d": {"emoji": "🧸", "desc": "Disney 3D", "suffix": ", Disney Pixar 3D character style"},
    "cartoon": {"emoji": "🎬", "desc": "Cartoon", "suffix": ", cartoon style, colorful, fun"},
    "comic": {"emoji": "💥", "desc": "Comic", "suffix": ", comic book style, bold lines"},
    "manga": {"emoji": "📖", "desc": "Manga", "suffix": ", manga style, black and white ink drawing"},
    "cyberpunk": {"emoji": "🌃", "desc": "Cyberpunk", "suffix": ", cyberpunk style, neon lights, futuristic"},
    "retrowave": {"emoji": "🌅", "desc": "Retrowave", "suffix": ", retrowave synthwave, 80s neon aesthetic"},
    "fantasy": {"emoji": "⚔️", "desc": "Fantasy", "suffix": ", epic fantasy art, magical atmosphere"},
    "pixel_art": {"emoji": "👾", "desc": "Pixel Art", "suffix": ", pixel art style, retro 16-bit"},
    "watercolor": {"emoji": "🎨", "desc": "Watercolor", "suffix": ", watercolor painting, soft colors"},
    "oil_paint": {"emoji": "🖼️", "desc": "Oil Paint", "suffix": ", oil painting, classical art, rich textures"},
    "digital_art": {"emoji": "🖌️", "desc": "Digital Art", "suffix": ", digital painting, artstation quality"},
    "concept_art": {"emoji": "📝", "desc": "Concept Art", "suffix": ", concept art, professional game art"},
    "sketch": {"emoji": "✏️", "desc": "Sketch", "suffix": ", pencil sketch, hand drawn, detailed lines"},
    "realistic": {"emoji": "📷", "desc": "Realista", "suffix": ", photorealistic, highly detailed, 8k"},
    "3d": {"emoji": "🧊", "desc": "3D Render", "suffix": ", 3D render, octane render, unreal engine"},
    "cute_3d": {"emoji": "🎀", "desc": "Cute 3D", "suffix": ", cute 3D chibi, kawaii render"},
    "claymation": {"emoji": "🏺", "desc": "Claymation", "suffix": ", claymation stop motion style"},
    "ukiyoe": {"emoji": "🏯", "desc": "Ukiyo-e", "suffix": ", Japanese ukiyo-e woodblock print style"},
    "art_nouveau": {"emoji": "🌺", "desc": "Art Nouveau", "suffix": ", Art Nouveau style, ornate, flowing lines"},
    "tattoo": {"emoji": "💉", "desc": "Tattoo", "suffix": ", tattoo design, ink art, bold outlines"},
    "vintage": {"emoji": "📻", "desc": "Vintage", "suffix": ", vintage retro style, aged colors, nostalgic"},
    "splatter": {"emoji": "💦", "desc": "Splatter", "suffix": ", paint splatter art, abstract colorful"},
    "gothic": {"emoji": "🦇", "desc": "Gothic", "suffix": ", gothic dark art, moody atmosphere"},
    "steampunk": {"emoji": "⚙️", "desc": "Steampunk", "suffix": ", steampunk style, Victorian mechanical"},
    "pop_art": {"emoji": "🎭", "desc": "Pop Art", "suffix": ", pop art, Andy Warhol, bold colors, halftone"},
    "neon_glow": {"emoji": "💡", "desc": "Neon Glow", "suffix": ", neon glow effect, glowing edges, dark background"},
    "anime_50s": {"emoji": "👩‍🍳", "desc": "Anime 50s", "suffix": ", 1950s anime infomercial style, retro anime"},
    "furry": {"emoji": "🐾", "desc": "Furry", "suffix": ", furry art, anthropomorphic animal character"},
    "pokemon": {"emoji": "⚡", "desc": "Pokemon", "suffix": ", Pokemon art style, Nintendo game aesthetic"},
    "grain": {"emoji": "🎞️", "desc": "Film Grain", "suffix": ", film grain, analog photography, cinematic"},
}

def get_user_style_settings(user_id):
    settings = load_json(SETTINGS_FILE)
    user_str = str(user_id)
    if user_str not in settings:
        settings[user_str] = {}
    
    # Garantir que todas as chaves existem
    if "aspect_ratio" not in settings[user_str]:
        settings[user_str]["aspect_ratio"] = "square"
    if "visual_style" not in settings[user_str]:
        settings[user_str]["visual_style"] = "livre"
    if "num_variations" not in settings[user_str]:
        settings[user_str]["num_variations"] = 1
    
    save_json(SETTINGS_FILE, settings, SETTINGS_LOCK)
    return settings[user_str]

def set_user_style(user_id, aspect_ratio=None, visual_style=None, num_variations=None):
    settings = load_json(SETTINGS_FILE)
    user_str = str(user_id)
    if user_str not in settings:
        settings[user_str] = {}
    
    # Garantir valores padrão
    if "aspect_ratio" not in settings[user_str]:
        settings[user_str]["aspect_ratio"] = "square"
    if "visual_style" not in settings[user_str]:
        settings[user_str]["visual_style"] = "livre"
    if "num_variations" not in settings[user_str]:
        settings[user_str]["num_variations"] = 1
    
    # Aplicar mudanças solicitadas
    if aspect_ratio and aspect_ratio in ASPECT_RATIOS:
        settings[user_str]["aspect_ratio"] = aspect_ratio
    if visual_style and visual_style in VISUAL_STYLES:
        settings[user_str]["visual_style"] = visual_style
    if num_variations and 1 <= num_variations <= 4:
        settings[user_str]["num_variations"] = num_variations
    
    save_json(SETTINGS_FILE, settings, SETTINGS_LOCK)
    return True

# ==================== AUTOMATIC PROMPT IMPROVER ====================
def improve_prompt_auto(user_prompt, lang="pt"):
    """Melhora automaticamente prompts simples usando IA - SEMPRE em ingles"""
    try:
        system_prompt = "You are an expert in creating image generation prompts. Take the user's prompt (in any language) and transform it into a detailed English prompt for AI image generation. Add details about lighting, composition, quality, style. Respond ONLY with the improved English prompt, no explanations. Always respond in English regardless of input language."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.8
        )
        improved = response.choices[0].message.content.strip()
        logger.info(f"Prompt melhorado: '{user_prompt}' -> '{improved}'")
        return improved
    except Exception as e:
        logger.error(f"Erro ao melhorar prompt: {e}")
        return user_prompt

# ==================== FAVORITOS ====================
def add_to_favorites(user_id, creation_id):
    data = load_json(FAVORITES_FILE)
    user_str = str(user_id)
    if user_str not in data:
        data[user_str] = []
    if creation_id not in data[user_str]:
        data[user_str].append(creation_id)
        save_json(FAVORITES_FILE, data, FAVORITES_LOCK)
        return True
    return False

def remove_from_favorites(user_id, creation_id):
    data = load_json(FAVORITES_FILE)
    user_str = str(user_id)
    if user_str in data and creation_id in data[user_str]:
        data[user_str].remove(creation_id)
        save_json(FAVORITES_FILE, data, FAVORITES_LOCK)
        return True
    return False

def get_user_favorites(user_id):
    data = load_json(FAVORITES_FILE)
    return data.get(str(user_id), [])

# ==================== ESTATÍSTICAS ====================
def update_user_stats(user_id, stat_type, value=1):
    data = load_json(STATISTICS_FILE)
    user_str = str(user_id)
    if user_str not in data:
        data[user_str] = {
            "total_creations": 0,
            "total_edits": 0,
            "total_favorites": 0,
            "total_shares": 0,
            "total_time_saved": 0,
            "first_use": datetime.now().isoformat(),
            "last_use": datetime.now().isoformat()
        }
    data[user_str][stat_type] = data[user_str].get(stat_type, 0) + value
    data[user_str]["last_use"] = datetime.now().isoformat()
    save_json(STATISTICS_FILE, data, STATS_LOCK)

def get_user_stats(user_id):
    data = load_json(STATISTICS_FILE)
    return data.get(str(user_id), {})

# ==================== COMPARTILHAMENTO ====================
def share_creation(user_id, creation_data):
    data = load_json(SHARED_CREATIONS_FILE)
    share_id = f"share_{user_id}_{int(time.time())}_{random.randint(1000, 9999)}"
    data[share_id] = {
        "user_id": user_id,
        "prompt": creation_data.get("prompt", ""),
        "url": creation_data.get("url", ""),
        "timestamp": datetime.now().isoformat(),
        "views": 0
    }
    save_json(SHARED_CREATIONS_FILE, data, SHARED_LOCK)
    update_user_stats(user_id, "total_shares")
    return share_id

def get_shared_creation(share_id):
    data = load_json(SHARED_CREATIONS_FILE)
    if share_id in data:
        data[share_id]["views"] = data[share_id].get("views", 0) + 1
        save_json(SHARED_CREATIONS_FILE, data, SHARED_LOCK)
        return data[share_id]
    return None

# ==================== PERSONALIDADES DE IA ====================
AI_PERSONALITIES = {
    "criativo": {
        "emoji": "🎨",
        "nome": "Criativo",
        "desc": "Inspirador e artístico",
        "system": "Você é um assistente SUPER criativo e artístico. Use linguagem inspiradora, dê sugestões criativas e seja entusiasta com arte e design."
    },
    "tecnico": {
        "emoji": "🤖",
        "nome": "Técnico",
        "desc": "Preciso e detalhado",
        "system": "Você é um assistente técnico e preciso. Dê respostas diretas, focadas em eficiência e qualidade técnica."
    },
    "casual": {
        "emoji": "😊",
        "nome": "Casual",
        "desc": "Amigável e descontraído",
        "system": "Você é um assistente amigável e descontraído. Use linguagem casual, emojis, e seja divertido e acessível."
    },
    "profissional": {
        "emoji": "💼",
        "nome": "Profissional",
        "desc": "Formal e eficiente",
        "system": "Você é um assistente profissional e formal. Seja educado, direto ao ponto e eficiente."
    }
}

def get_user_personality(user_id):
    settings = load_json(SETTINGS_FILE)
    return settings.get(str(user_id), {}).get("personality", "casual")

def set_user_personality(user_id, personality):
    if personality not in AI_PERSONALITIES:
        return False
    settings = load_json(SETTINGS_FILE)
    user_str = str(user_id)
    if user_str not in settings:
        settings[user_str] = {}
    settings[user_str]["personality"] = personality
    save_json(SETTINGS_FILE, settings, SETTINGS_LOCK)
    return True

# ==================== GALERIA DE EXEMPLOS ====================
EXAMPLE_GALLERY = [
    {"prompt": "Sunset over mountains, anime style", "desc": "Pôr do sol montanhas", "url": "https://replicate.delivery/pbxt/example1.jpg"},
    {"prompt": "Futuristic city, cyberpunk, neon lights", "desc": "Cidade futurista", "url": "https://replicate.delivery/pbxt/example2.jpg"},
    {"prompt": "Cute cat with flowers, watercolor painting", "desc": "Gato fofo aquarela", "url": "https://replicate.delivery/pbxt/example3.jpg"},
]

# ==================== MODELOS ====================
MODELO_PADRAO = {
    "nome": "🎨 Modelo Padrao",
    "desc": "Criacao e edicao de imagens",
    "replicate_id": "xai/grok-imagine-image",
    "custo": 1
}

MODELO_PRO = {
    "nome": "✨ Modelo Pro",
    "desc": "Melhoria fotorrealista avancada (FLUX.2 Klein 9B) - Apenas edicao",
    "replicate_id": "black-forest-labs/flux-2-klein-9b",
    "custo": 3,
    "prompt_fixo": "make it more realistic"
}

MODELO_ARTISTICO = {
    "nome": "🎭 Modelo Artistico",
    "desc": "Transforma fotos em diferentes estilos artisticos",
    "replicate_id": "black-forest-labs/flux-2-klein-9b",
    "custo": 2
}

ESTILOS_ARTISTICOS = {
    "anime": {"nome": "Anime", "prompt": "transform into anime style, anime art, manga aesthetic, keep same pose"},
    "ghibli": {"nome": "Ghibli", "prompt": "transform into Studio Ghibli anime style, soft colors, Miyazaki aesthetic"},
    "disney_2d": {"nome": "Disney 2D", "prompt": "transform into Disney 2D animation style character"},
    "disney_3d": {"nome": "Disney 3D", "prompt": "transform into Disney Pixar 3D character style, cute 3D render"},
    "cartoon": {"nome": "Cartoon", "prompt": "transform into cartoon style, colorful, exaggerated features, fun cartoon"},
    "comic": {"nome": "Comic", "prompt": "transform into comic book style, bold lines, vibrant colors"},
    "manga": {"nome": "Manga", "prompt": "transform into black and white manga style, detailed ink drawing, manga panels"},
    "pokemon_2d": {"nome": "Pokemon 2D", "prompt": "transform into Pokemon 2D art style, Nintendo Pokemon game aesthetic"},
    "pokemon_3d": {"nome": "Pokemon 3D", "prompt": "transform into Pokemon 3D render style, Nintendo 3D Pokemon"},
    "cyberpunk": {"nome": "Cyberpunk", "prompt": "transform into cyberpunk style, neon lights, futuristic, dark atmosphere"},
    "retrowave": {"nome": "Retrowave", "prompt": "transform into retrowave synthwave style, neon pink purple, 80s aesthetic"},
    "fantasy": {"nome": "Fantasy", "prompt": "transform into epic fantasy painting, magical atmosphere, fantasy art"},
    "pixel_art": {"nome": "Pixel Art", "prompt": "transform into pixel art style, retro game aesthetic, 16-bit style"},
    "watercolor": {"nome": "Watercolor", "prompt": "transform into watercolor painting, soft colors, artistic watercolor"},
    "oil_paint": {"nome": "Oil Paint", "prompt": "transform into oil painting, classical art style, rich textures"},
    "digital_art": {"nome": "Digital Art", "prompt": "transform into digital painting, detailed digital art, artstation quality"},
    "concept_art": {"nome": "Concept Art", "prompt": "transform into concept art, professional concept sketch, game art style"},
    "sketch": {"nome": "Sketch", "prompt": "transform into pencil drawing sketch, black and white, detailed lines"},
    "cute_3d": {"nome": "Cute 3D", "prompt": "transform into cute 3D chibi character, kawaii 3D render, adorable"},
    "claymation": {"nome": "Claymation", "prompt": "transform into claymation stop motion style, clay figures, handmade look"},
    "ukiyoe": {"nome": "Ukiyo-e", "prompt": "transform into Japanese ukiyo-e woodblock print style, traditional art"},
    "art_nouveau": {"nome": "Art Nouveau", "prompt": "transform into Art Nouveau style, ornate decorative, flowing lines"},
    "tattoo": {"nome": "Tattoo", "prompt": "transform into tattoo design style, ink art, bold outlines, tattoo flash"},
    "vintage": {"nome": "Vintage", "prompt": "transform into vintage retro style, aged colors, nostalgic aesthetic"},
    "splatter": {"nome": "Splatter", "prompt": "transform into paint splatter art, abstract colorful splashes, explosive"},
    "grain": {"nome": "Film Grain", "prompt": "transform with film grain effect, analog photography, cinematic grain"},
    "woodcarving": {"nome": "Woodcarving", "prompt": "transform into woodcarving art style, carved wood texture, relief sculpture"},
    "furry": {"nome": "Furry", "prompt": "transform into furry art style, anthropomorphic animal character, detailed fur"},
    "pop_art": {"nome": "Pop Art", "prompt": "transform into pop art style, Andy Warhol inspired, bold colors, halftone dots"},
    "steampunk": {"nome": "Steampunk", "prompt": "transform into steampunk style, Victorian mechanical, gears and brass"},
    "anime_50s": {"nome": "Anime 50s", "prompt": "transform into 1950s anime infomercial style, retro anime housewife aesthetic, vintage anime"},
    "neon_glow": {"nome": "Neon Glow", "prompt": "transform with neon glow effect, glowing edges, dark background, vibrant neon colors"},
    "gothic": {"nome": "Gothic", "prompt": "transform into gothic dark art style, dark aesthetic, moody atmosphere, dark fantasy"}
}

def gerar_imagem_artistica(image_input, estilo_key):
    """Transforma imagem em estilo artistico usando FLUX.2 Klein 9B"""
    try:
        estilo = ESTILOS_ARTISTICOS.get(estilo_key, ESTILOS_ARTISTICOS["anime"])
        input_params = {
            "prompt": estilo["prompt"],
            "images": [image_input],
            "aspect_ratio": "match_input_image",
            "safety_tolerance": 6,
            "disable_safety_checker": True
        }
        output = replicate.run(MODELO_ARTISTICO["replicate_id"], input=input_params)
        if isinstance(output, list):
            return [str(url) for url in output]
        elif hasattr(output, 'url'):
            return [str(output.url)]
        else:
            return [str(output)]
    except Exception as e:
        raise e

def gerar_imagem_modelo(prompt, aspect_ratio="1:1", image_input=None, num_outputs=1):
    """Gera imagem usando modelo padrao com aspect ratio configuravel"""
    try:
        input_params = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "num_outputs": num_outputs
        }
        if image_input:
            input_params["image"] = image_input
        
        output = replicate.run(MODELO_PADRAO["replicate_id"], input=input_params)
        
        if isinstance(output, list):
            return [str(url) for url in output]
        elif hasattr(output, 'url'):
            return [str(output.url)]
        else:
            return [str(output)]
    except Exception as e:
        # Retry automático para erros temporários do Replicate
        if "interrupted" in str(e).lower() or "code: PA" in str(e):
            logger.info("Replicate ocupado, tentando novamente...")
            time.sleep(3)
            try:
                output = replicate.run(MODELO_PADRAO["replicate_id"], input=input_params)
                if isinstance(output, list):
                    return [str(url) for url in output]
                elif hasattr(output, 'url'):
                    return [str(output.url)]
                else:
                    return [str(output)]
            except:
                raise e
        raise e

def gerar_imagem_pro(image_input):
    """Melhora imagem usando Modelo Pro (FLUX.2 Klein 9B) - prompt fixo"""
    try:
        input_params = {
            "prompt": MODELO_PRO["prompt_fixo"],
            "images": [image_input],
            "aspect_ratio": "match_input_image",
            "safety_tolerance": 6,
            "disable_safety_checker": True
        }
        
        output = replicate.run(MODELO_PRO["replicate_id"], input=input_params)
        
        if isinstance(output, list):
            return [str(url) for url in output]
        elif hasattr(output, 'url'):
            return [str(output.url)]
        else:
            return [str(output)]
    except Exception as e:
        raise e

# ==================== HISTÓRICO ====================
def add_to_history(user_id, action_type, prompt, image_url, creation_id=None):
    data = load_json(HISTORY_FILE)
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = []
    
    if not creation_id:
        creation_id = f"creation_{user_id}_{int(time.time())}_{random.randint(1000, 9999)}"
    
    data[user_id_str].insert(0, {
        "id": creation_id,
        "type": action_type,
        "prompt": prompt,
        "url": image_url,
        "timestamp": datetime.now().isoformat()
    })
    data[user_id_str] = data[user_id_str][:20]
    save_json(HISTORY_FILE, data, HISTORY_LOCK)
    
    if action_type == "create":
        update_user_stats(user_id, "total_creations")
    elif action_type == "edit":
        update_user_stats(user_id, "total_edits")
    
    return creation_id

def get_user_history(user_id):
    data = load_json(HISTORY_FILE)
    return data.get(str(user_id), [])

def get_creation_by_id(user_id, creation_id):
    history = get_user_history(user_id)
    for item in history:
        if item.get("id") == creation_id:
            return item
    return None

# ==================== REFERRAL ====================
def create_referral_link(user_id):
    encoded = base64.b64encode(str(user_id).encode()).decode()
    return f"https://t.me/{BOT_USERNAME}?start=ref_{encoded}"

def process_referral(referrer_id, referred_id):
    if referrer_id == referred_id:
        return False, "Auto-referral não permitido"
    data = load_json(REFERRAL_FILE)
    if not data:
        data = {"referrals": {}, "referred_by": {}}
    if str(referred_id) in data.get("referred_by", {}):
        return False, "Já foi indicado"
    data.setdefault("referrals", {}).setdefault(str(referrer_id), []).append(referred_id)
    data.setdefault("referred_by", {})[str(referred_id)] = referrer_id
    save_json(REFERRAL_FILE, data, REF_LOCK)
    return True, "Referral processado"

def get_referral_count(user_id):
    data = load_json(REFERRAL_FILE)
    return len(data.get("referrals", {}).get(str(user_id), []))

# ==================== PROMPT WIZARD (QUESTIONÁRIO) ====================
wizard_states = {}

WIZARD_QUESTIONS = {
    "pt": {
        "q1": "🎯 <b>O que você quer criar?</b>\n\n1️⃣ Flyer/Pôster profissional\n2️⃣ Logo/Identidade visual\n3️⃣ Arte Conceitual/Ilustração\n4️⃣ Personagem (anime, realista, cartoon)\n5️⃣ Paisagem/Cenário\n6️⃣ Produto/Mockup\n7️⃣ Retrato/Foto realista\n8️⃣ Outro\n\nDigite o número ou descreva:",
        "q2": "🎨 <b>Qual estilo visual prefere?</b>\n\n1️⃣ Anime/Mangá japonês\n2️⃣ Realista/Fotográfico\n3️⃣ Artístico/Pintura digital\n4️⃣ 3D Render (tipo Pixar)\n5️⃣ Sketch/Desenho à mão\n6️⃣ Minimalista/Flat design\n7️⃣ Cyberpunk/Futurista\n8️⃣ Vintage/Retrô\n\nDigite o número ou descreva:",
        "q3": "📐 <b>Qual formato?</b>\n\n1️⃣ Vertical (3:4) - Stories\n2️⃣ Quadrado (1:1) - Instagram\n3️⃣ Horizontal (16:9) - YouTube\n4️⃣ Story/TikTok (9:16)\n5️⃣ Instagram Post (4:5)\n\nDigite o número:",
        "q4": "✍️ <b>Descreva em detalhes o que quer ver:</b>\n\n💡 Quanto mais detalhes, melhor!\n\nExemplo: \"Uma cidade futurista ao pôr do sol, arranha-céus em neon azul e rosa\"",
        "q5": "📸 <b>Tem foto de referência?</b>\n\nEnvie uma foto ou digite 'não' para pular."
    },
    "en": {
        "q1": "🎯 <b>What do you want to create?</b>\n\n1️⃣ Flyer/Professional poster\n2️⃣ Logo/Visual identity\n3️⃣ Concept Art/Illustration\n4️⃣ Character (anime, realistic, cartoon)\n5️⃣ Landscape/Scenery\n6️⃣ Product/Mockup\n7️⃣ Portrait/Realistic photo\n8️⃣ Other\n\nType number or describe:",
        "q2": "🎨 <b>Which visual style?</b>\n\n1️⃣ Anime/Japanese manga\n2️⃣ Realistic/Photographic\n3️⃣ Artistic/Digital painting\n4️⃣ 3D Render (Pixar style)\n5️⃣ Sketch/Hand drawn\n6️⃣ Minimalist/Flat design\n7️⃣ Cyberpunk/Futuristic\n8️⃣ Vintage/Retro\n\nType number or describe:",
        "q3": "📐 <b>Which format/aspect ratio?</b>\n\n1️⃣ Vertical (3:4) - Stories/Mobile\n2️⃣ Square (1:1) - Instagram feed\n3️⃣ Horizontal (16:9) - Desktop/YouTube\n4️⃣ Widescreen (21:9) - Banner\n\nType number:",
        "q4": "✍️ <b>Describe in detail what you want:</b>\n\n💡 More details = better results!\n\nInclude:\n• Predominant colors\n• Environment/setting\n• Mood/atmosphere\n• Specific elements\n\nExample: \"A futuristic city at sunset, with skyscrapers lit in blue and pink neon, flying cars, cyberpunk atmosphere\"",
        "q5": "📸 <b>Do you have reference photos?</b>\n\n✨ Send 1-3 photos representing:\n• Desired visual style\n• Color palette\n• Composition\n• Character/object\n\n⚠️ Or type 'no' to skip."
    },
    "es": {
        "q1": "🎯 <b>¿Qué quieres crear?</b>\n\n1️⃣ Flyer/Póster profesional\n2️⃣ Logo/Identidad visual\n3️⃣ Arte Conceptual/Ilustración\n4️⃣ Personaje (anime, realista, cartoon)\n5️⃣ Paisaje/Escenario\n6️⃣ Producto/Mockup\n7️⃣ Retrato/Foto realista\n8️⃣ Otro\n\nEscribe el número o describe:",
        "q2": "🎨 <b>¿Qué estilo visual prefieres?</b>\n\n1️⃣ Anime/Manga japonés\n2️⃣ Realista/Fotográfico\n3️⃣ Artístico/Pintura digital\n4️⃣ 3D Render (estilo Pixar)\n5️⃣ Sketch/Dibujado a mano\n6️⃣ Minimalista/Flat design\n7️⃣ Cyberpunk/Futurista\n8️⃣ Vintage/Retro\n\nEscribe el número o describe:",
        "q3": "📐 <b>¿Qué formato/proporción?</b>\n\n1️⃣ Vertical (3:4) - Stories/Móvil\n2️⃣ Cuadrado (1:1) - Instagram feed\n3️⃣ Horizontal (16:9) - Desktop/YouTube\n4️⃣ Widescreen (21:9) - Banner\n\nEscribe el número:",
        "q4": "✍️ <b>Describe en detalle lo que quieres:</b>\n\n💡 ¡Más detalles = mejores resultados!\n\nIncluye:\n• Colores predominantes\n• Ambiente/escenario\n• Mood/atmósfera\n• Elementos específicos\n\nEjemplo: \"Una ciudad futurista al atardecer, con rascacielos iluminados en neón azul y rosa, autos voladores, atmósfera cyberpunk\"",
        "q5": "📸 <b>¿Tienes fotos de referencia?</b>\n\n✨ Envía 1-3 fotos que representen:\n• Estilo visual deseado\n• Paleta de colores\n• Composición\n• Personaje/objeto\n\n⚠️ O escribe 'no' para saltar."
    }
}

def start_wizard(user_id, lang="pt"):
    wizard_states[user_id] = {
        "step": 1,
        "answers": {},
        "lang": lang
    }
    return WIZARD_QUESTIONS[lang]["q1"]

def process_wizard_step(user_id, answer, photo_data=None):
    if user_id not in wizard_states:
        return None, False
    
    state = wizard_states[user_id]
    step = state["step"]
    lang = state["lang"]
    
    if step == 1:
        types = {1: "flyer", 2: "logo", 3: "concept_art", 4: "face_swap", 5: "other"}
        try:
            state["answers"]["type"] = types.get(int(answer), "other")
        except ValueError:
            state["answers"]["type"] = answer.lower()
        state["step"] = 2
        return WIZARD_QUESTIONS[lang]["q2"], False
    
    elif step == 2:
        styles = {1: "anime", 2: "realistic", 3: "digital_art", 4: "3d", 5: "sketch", 6: "livre", 7: "cyberpunk", 8: "vintage"}
        try:
            state["answers"]["style"] = styles.get(int(answer), "livre")
        except ValueError:
            # Tentar encontrar estilo por nome
            matched = "livre"
            for k, v in VISUAL_STYLES.items():
                if answer.lower() in v["desc"].lower() or answer.lower() in k:
                    matched = k
                    break
            state["answers"]["style"] = matched
        state["step"] = 3
        return WIZARD_QUESTIONS[lang]["q3"], False
    
    elif step == 3:
        ratios = {1: "portrait", 2: "square", 3: "landscape", 4: "story", 5: "insta"}
        try:
            state["answers"]["aspect"] = ratios.get(int(answer), "square")
        except ValueError:
            state["answers"]["aspect"] = "square"
        state["step"] = 4
        return WIZARD_QUESTIONS[lang]["q4"], False
    
    elif step == 4:
        state["answers"]["description"] = answer
        state["step"] = 5
        return WIZARD_QUESTIONS[lang]["q5"], False
    
    elif step == 5:
        if photo_data:
            state["answers"]["reference_photo"] = photo_data
            # Guardar referência para uso posterior (wizard_states é removido antes de usar)
            if not hasattr(handle_wizard, '_last_ref'):
                handle_wizard._last_ref = {}
            handle_wizard._last_ref[user_id] = photo_data
        elif answer.lower() in ['não', 'nao', 'no', 'non', 'skip', 'pular']:
            pass  # Sem foto
        else:
            # Utilizador enviou texto em vez de foto
            state["answers"]["description"] += f". {answer}"
        
        tipo = state["answers"].get("type", "other")
        style = state["answers"].get("style", "livre")
        desc = state["answers"].get("description", "")
        
        style_suffix = VISUAL_STYLES.get(style, VISUAL_STYLES["livre"])["suffix"]
        
        final_prompt = f"{desc}{style_suffix}, professional quality, {tipo} design"
        
        wizard_states.pop(user_id)
        return final_prompt, True
    
    return None, False

# ==================== CHAT SUPERINTELIGENTE COM PERSONALIDADES ====================
chat_contexts = {}
user_states = {}
pending_photos = {}
carousel_states = {}
bot_paused = False
pause_message = ""

def get_smart_chat_response(user_id, message, lang="pt"):
    """Chat IA com personalidades e memória de erros"""
    try:
        if user_id not in chat_contexts:
            chat_contexts[user_id] = []
        
        chat_contexts[user_id].append({"role": "user", "content": message})
        if len(chat_contexts[user_id]) > 10:
            chat_contexts[user_id] = chat_contexts[user_id][-10:]
        
        creditos = get_user_credits(user_id)
        erros_recentes = get_user_errors(user_id)
        personality = get_user_personality(user_id)
        personality_info = AI_PERSONALITIES[personality]
        
        erros_context = ""
        if erros_recentes:
            erros_context = "\n\nÚLTIMOS ERROS DO USUÁRIO:\n"
            for err in erros_recentes[:3]:
                erros_context += f"- {err['type']}: {err['message']}\n"
        
        lang_names = {"pt": "Português", "en": "English", "es": "Español", "fr": "Français"}
        
        bot_knowledge = """
CONHECIMENTO COMPLETO DO BOT REMAKE PIXEL:

FUNCIONALIDADES:
1. GERAR IMAGENS: Menu → Gerar Fotos → escrever descrição → IA gera (1 crédito por imagem)
2. EDITAR FOTOS: Enviar foto no chat → escolher modelo (Padrão/Pro/Artístico)
3. COMBINAR FOTOS: Enviar 2-5 fotos juntas → escolher modelo
4. CARROSSEL: Menu → Carrossel → escolher slides (2-4) → descrever cada slide (1 cred/slide)
5. CHAT IA: Escrever qualquer mensagem → resposta grátis

MODELOS DE EDIÇÃO:
- Padrão (1 crédito): Precisa de prompt/descrição. Ex: 'melhore qualidade', 'remova fundo'
- Pro (3 créditos): Melhoria fotorrealista AUTOMÁTICA. Não precisa prompt.
- Artístico (2 créditos): 33 estilos artísticos (anime, Disney, cyberpunk, etc.)

CONFIGURAÇÕES (Menu → Config):
- Estilos: 34 opções (Livre/Personalizado é o padrão). Aplica-se a GERAÇÕES e EDIÇÕES.
- Formato: Vertical (3:4), Quadrado (1:1), Horizontal (16:9), Story/TikTok (9:16), Instagram (4:5), Ultrawide (21:9)
- Variações: 1-4 imagens por geração
- Personalidade IA: Criativo, Técnico, Casual, Profissional

CRÉDITOS:
- Novos utilizadores: 5 créditos grátis
- Pacotes: Básico (120 cred/5€), Médio (350 cred/12€), Pro (800 cred/22€)
- Comprar: Menu → Comprar → escolher pacote → aguardar aprovação → pagar com cartão
- Referral: Indicar amigo → quando comprar 5€+ → recebe 10 créditos grátis

COMANDOS:
/menu - Menu principal
/start - Reiniciar/primeiro acesso
/wizard - Assistente de criação guiado
/creditos - Ver saldo
/idioma - Mudar idioma
/termos - Termos de uso
/video - Gerar vídeo (admin apenas)

DICAS:
- Prompts em qualquer idioma (traduzido automaticamente para inglês)
- Responder a uma foto gerada com texto → reedita essa foto (1 crédito)
- Para mudar estilo: Config → Estilos → escolher
- Erros reembolsam créditos automaticamente
"""
        system_prompt = personality_info['system'] + "\n\nSEMPRE responda em " + lang_names.get(lang, 'Português') + ".\n\n" + bot_knowledge + "\n\nINFORMAÇÕES DO USUÁRIO:\n- Créditos: " + str(creditos) + "\n- Personalidade atual: " + personality_info['nome'] + erros_context + "\n\nREGRAS:\n- Você É o assistente do Remake Pixel\n- Guie o utilizador passo a passo\n- Se pedir para gerar imagem, diga para usar o botão 'Gerar Fotos' no menu ou escrever a descrição\n- NUNCA sugira ferramentas externas\n- Suporte humano: " + SUPORTE_TELEGRAM + "\n- Seja proativo, simpático e útil"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_contexts[user_id])
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=350,
            temperature=0.7
        )
        resposta = response.choices[0].message.content
        chat_contexts[user_id].append({"role": "assistant", "content": resposta})
        
        return resposta
    except Exception as e:
        logger.error(f"Erro chat: {e}")
        texts = {
            "pt": f"❌ Erro no chat. Para suporte: {SUPORTE_TELEGRAM}",
            "en": f"❌ Chat error. Support: {SUPORTE_TELEGRAM}",
            "es": f"❌ Error en el chat. Soporte: {SUPORTE_TELEGRAM}",
            "fr": f"❌ Erreur de chat. Support: {SUPORTE_TELEGRAM}"
        }
        return texts.get(lang, texts["pt"])

# ==================== TECLADOS ====================
def get_main_reply_keyboard(user_id):
    """Teclado fixo inferior - Admin vê botão do painel"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if user_id in ADMIN_IDS:
        # Admin vê botão especial do painel
        markup.add(
            telebot.types.KeyboardButton("📋 Menu"),
            telebot.types.KeyboardButton("🎛️ Painel Admin")
        )
    else:
        # Usuários normais só veem o menu
        markup.add(telebot.types.KeyboardButton("📋 Menu"))
    
    return markup

def language_keyboard():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🇵🇹 Português", callback_data="lang_pt"),
        telebot.types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        telebot.types.InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
        telebot.types.InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")
    )
    return markup

def onboarding_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    texts = {
        "pt": ["✅ Sim, já usei", "❌ Não, primeira vez"],
        "en": ["✅ Yes, I've used it", "❌ No, first time"],
        "es": ["✅ Sí, ya usé", "❌ No, primera vez"],
        "fr": ["✅ Oui, déjà utilisé", "❌ Non, première fois"]
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data="onboard_yes"),
        telebot.types.InlineKeyboardButton(t[1], callback_data="onboard_no")
    )
    return markup

def main_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    texts = {
        "pt": ["🎨 Gerar Fotos", "📸 Editar Fotos", "📱 Carrossel", "💳 Créditos", "🛒 Comprar", 
               "📚 Histórico", "⭐ Favoritos", "📊 Stats", "⚙️ Config", 
               "🎁 Indicar", "❓ Ajuda"],
        "en": ["🎨 Generate", "📸 Edit Photos", "📱 Carousel", "💳 Credits", "🛒 Buy", 
               "📚 History", "⭐ Favorites", "📊 Stats", "⚙️ Settings", 
               "🎁 Refer", "❓ Help"],
        "es": ["🎨 Generar", "📸 Editar Fotos", "📱 Carrusel", "💳 Créditos", "🛒 Comprar", 
               "📚 Historial", "⭐ Favoritos", "📊 Stats", "⚙️ Config", 
               "🎁 Referir", "❓ Ayuda"],
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data="action_create"),
        telebot.types.InlineKeyboardButton(t[1], callback_data="action_edit_photos")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[2], callback_data="action_carousel"),
        telebot.types.InlineKeyboardButton(t[3], callback_data="action_credits")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[4], callback_data="action_buy"),
        telebot.types.InlineKeyboardButton(t[5], callback_data="action_history")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[6], callback_data="action_favorites"),
        telebot.types.InlineKeyboardButton(t[7], callback_data="action_stats")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[8], callback_data="action_settings"),
        telebot.types.InlineKeyboardButton(t[9], callback_data="action_referral")
    )
    markup.add(telebot.types.InlineKeyboardButton(t[10], callback_data="action_help"))
    return markup

def cancel_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup()
    texts = {"pt": "❌ Cancelar", "en": "❌ Cancel", "es": "❌ Cancelar", "fr": "❌ Annuler"}
    markup.add(telebot.types.InlineKeyboardButton(texts.get(lang, texts["pt"]), callback_data="action_cancel"))
    return markup

def buy_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACOTES.items():
        preco = p['preco'] / 100
        markup.add(telebot.types.InlineKeyboardButton(
            f"{pid}️⃣ {p['creditos']} créd (€{preco:.2f})",
            callback_data=f"buy_{pid}"
        ))
    back_texts = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver", "fr": "◀️ Retour"}
    markup.add(telebot.types.InlineKeyboardButton(back_texts.get(lang, back_texts["pt"]), callback_data="action_menu"))
    return markup

def settings_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    texts = {
        "pt": ["🎨 Estilos", "📐 Formato", "🔢 Variações", "🤖 Personalidade", "◀️ Voltar"],
        "en": ["🎨 Styles", "📐 Format", "🔢 Variations", "🤖 Personality", "◀️ Back"],
        "es": ["🎨 Estilos", "📐 Formato", "🔢 Variaciones", "🤖 Personalidad", "◀️ Volver"],
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data="settings_styles"),
        telebot.types.InlineKeyboardButton(t[1], callback_data="settings_format"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[2], callback_data="settings_variations"),
        telebot.types.InlineKeyboardButton(t[3], callback_data="settings_personality"),
    )
    markup.add(telebot.types.InlineKeyboardButton(t[4], callback_data="action_menu"))
    return markup

def styles_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    keys = list(VISUAL_STYLES.keys())
    for i in range(0, len(keys), 3):
        row = []
        for key in keys[i:i+3]:
            val = VISUAL_STYLES[key]
            row.append(telebot.types.InlineKeyboardButton(val['desc'], callback_data=f"style_{key}"))
        markup.row(*row)
    back_texts = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver"}
    markup.add(telebot.types.InlineKeyboardButton(back_texts.get(lang, back_texts["pt"]), callback_data="action_settings"))
    return markup

def aspect_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for key, val in ASPECT_RATIOS.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"{val['emoji']} {val['desc']}", 
            callback_data=f"aspect_{key}"
        ))
    back_texts = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver"}
    markup.add(telebot.types.InlineKeyboardButton(back_texts.get(lang, back_texts["pt"]), callback_data="action_settings"))
    return markup

format_keyboard = aspect_keyboard

def variations_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=4)
    for i in range(1, 5):
        markup.add(telebot.types.InlineKeyboardButton(
            f"{i}️⃣ imagem{'ns' if i > 1 else ''}", 
            callback_data=f"var_{i}"
        ))
    back_texts = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver", "fr": "◀️ Retour"}
    markup.add(telebot.types.InlineKeyboardButton(back_texts.get(lang, back_texts["pt"]), callback_data="action_settings"))
    return markup

def personality_keyboard(lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for key, val in AI_PERSONALITIES.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"{val['emoji']} {val['nome']}", 
            callback_data=f"pers_{key}"
        ))
    back_texts = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver", "fr": "◀️ Retour"}
    markup.add(telebot.types.InlineKeyboardButton(back_texts.get(lang, back_texts["pt"]), callback_data="action_settings"))
    return markup

def creation_actions_keyboard(creation_id, lang="pt"):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    texts = {
        "pt": ["⭐ Favoritar", "🔗 Compartilhar"],
        "en": ["⭐ Favorite", "🔗 Share"],
        "es": ["⭐ Favorito", "🔗 Compartir"],
        "fr": ["⭐ Favori", "🔗 Partager"]
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data=f"fav_{creation_id}"),
        telebot.types.InlineKeyboardButton(t[1], callback_data=f"share_{creation_id}")
    )
    return markup

# ==================== HELPERS ====================
def show_main_menu(chat_id, user_id, lang):
    creditos = get_user_credits(user_id)
    total_users = len(load_json(CREDITS_FILE))
    
    texts = {
        "pt": f"🎨 <b>Remake Pixel</b>\n\n👥 {total_users} usuarios | 💳 <code>{creditos}</code> creditos\n\nO que deseja fazer?",
        "en": f"🎨 <b>Remake Pixel</b>\n\n👥 {total_users} users | 💳 <code>{creditos}</code> credits\n\nWhat would you like to do?",
        "es": f"🎨 <b>Remake Pixel</b>\n\n👥 {total_users} usuarios | 💳 <code>{creditos}</code> creditos\n\nQue deseas hacer?",
        "fr": f"🎨 <b>Remake Pixel</b>\n\n👥 {total_users} utilisateurs | 💳 <code>{creditos}</code> credits\n\nQue souhaitez-vous faire?"
    }
    bot.send_message(chat_id, texts.get(lang, texts["pt"]), 
                    reply_markup=main_keyboard(lang), 
                    parse_mode='HTML')

def quick_actions_keyboard(lang="pt"):
    """Botoes rapidos apos uma acao - menos intrusivo que o menu completo"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    texts = {
        "pt": ["📋 Menu", "📸 Editar", "🎨 Gerar"],
        "en": ["📋 Menu", "📸 Edit", "🎨 Generate"],
        "es": ["📋 Menu", "📸 Editar", "🎨 Generar"]
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data="action_menu"),
        telebot.types.InlineKeyboardButton(t[1], callback_data="action_edit_photos"),
        telebot.types.InlineKeyboardButton(t[2], callback_data="action_wizard")
    )
    return markup

# ==================== PROCESSAMENTO COM VARIAÇÕES ====================
def process_multiple_photos(user_id, lang, caption):
    """Mostra opcoes de modelo para multiplas fotos"""
    try:
        if user_id not in photo_collections:
            return
        
        collection = photo_collections[user_id]
        photos = collection["photos"]
        
        if len(photos) < 2:
            return
        
        creditos = get_user_credits(user_id)
        
        # Mostrar botoes de selecao de modelo
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        texts = {
            "pt": f"📸 <b>{len(photos)} fotos recebidas!</b>\n\n<b>Escolha o modelo:</b>\n\n🎨 <b>Modelo Padrao</b> (1 credito)\nCombina as fotos conforme descrição\n\n✨ <b>Modelo Pro</b> (2 creditos)\nCombina com melhoria fotorrealista\n\n💳 Seus créditos: <code>{creditos}</code>",
            "en": f"📸 <b>{len(photos)} photos received!</b>\n\n<b>Choose model:</b>\n\n🎨 <b>Standard</b> (1 credit)\nCombine photos as described\n\n✨ <b>Pro Model</b> (2 credits)\nCombine with photorealistic enhancement\n\n💳 Your credits: <code>{creditos}</code>",
            "es": f"📸 <b>{len(photos)} fotos recibidas!</b>\n\n<b>Elige modelo:</b>\n\n🎨 <b>Modelo Estandar</b> (1 credito)\nCombina las fotos segun descripcion\n\n✨ <b>Modelo Pro</b> (2 creditos)\nCombina con mejora fotorrealista\n\n💳 Tus créditos: <code>{creditos}</code>"
        }
        markup.add(
            telebot.types.InlineKeyboardButton("🎨 Padrao - 1 credito", callback_data="multi_model_padrao"),
            telebot.types.InlineKeyboardButton("✨ Pro - 3 creditos", callback_data="multi_model_pro"),
            telebot.types.InlineKeyboardButton("🎭 Artistico - 2 creditos", callback_data="multi_model_artistico"),
            telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="multi_model_cancel")
        )
        
        # NAO limpar photo_collections aqui - sera limpo no callback
        bot.send_message(user_id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"Erro mostrando opcoes multi-foto: {e}")
        photo_collections.pop(user_id, None)


def execute_combine_padrao(user_id, lang, caption):
    """Executa combinacao com modelo padrao"""
    try:
        if user_id not in photo_collections:
            return
        
        collection = photo_collections[user_id]
        photos = collection["photos"]
        
        if not use_credit(user_id, MODELO_PADRAO["custo"]):
            bot.send_message(user_id, "❌ Créditos insuficientes!")
            return
        
        bot.send_message(user_id, f"🎨 Processando {len(photos)} fotos (foto 1 = principal)...")
        
        combine_prompt = caption if caption else "Combine these images together naturally"
        
        # Baixar TODAS as fotos
        photo_bytes = []
        for photo_id in photos[:5]:
            try:
                file_info = bot.get_file(photo_id)
                downloaded_file = bot.download_file(file_info.file_path)
                photo_bytes.append(downloaded_file)
            except:
                continue
        
        if len(photo_bytes) < 2:
            add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
            bot.send_message(user_id, "❌ Erro ao processar. Crédito reembolsado.")
            return
        
        # FOTO 1 = imagem principal (base)
        main_b64 = base64.b64encode(photo_bytes[0]).decode('utf-8')
        main_data_url = f"data:image/jpeg;base64,{main_b64}"
        
        # Melhorar prompt - indicar que foto 1 é a principal
        if caption:
            enhanced_prompt = improve_prompt_auto(
                f"Edit the main photo (photo 1). User request: {caption}. "
                f"There are {len(photo_bytes)} reference images. "
                f"Keep the person/subject from the main photo, apply the style/concept described. High quality."
            )
        else:
            enhanced_prompt = f"Edit and enhance this photo, combine with reference style, high quality, professional"
        
        style_settings = get_user_style_settings(user_id)
        aspect_ratio = style_settings.get("aspect_ratio", "square")
        if aspect_ratio not in ASPECT_RATIOS:
            aspect_ratio = "square"
        ratio = ASPECT_RATIOS[aspect_ratio]["ratio"]
        
        urls = gerar_imagem_modelo(enhanced_prompt, ratio, image_input=main_data_url, num_outputs=1)
        
        if urls and len(urls) > 0:
            image_url = urls[0]
            img_data = requests.get(image_url, timeout=60).content
            creditos_restantes = get_user_credits(user_id)
            
            success_texts = {
                "pt": f"✅ <b>Fotos combinadas!</b>\n🤖 Modelo: Padrao\n📸 {len(photos)} imagens\n💳 Créditos: <code>{creditos_restantes}</code>",
                "en": f"✅ <b>Photos combined!</b>\n🤖 Model: Standard\n📸 {len(photos)} images\n💳 Credits: <code>{creditos_restantes}</code>",
                "es": f"✅ <b>Fotos combinadas!</b>\n🤖 Modelo: Estandar\n📸 {len(photos)} imagenes\n💳 Créditos: <code>{creditos_restantes}</code>"
            }
            creation_id = add_to_history(user_id, "edit", combine_prompt, image_url)
            bot.send_photo(user_id, img_data, caption=success_texts.get(lang, success_texts["pt"]),
                         reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            update_user_stats(user_id, "total_creations")
        else:
            add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
            bot.send_message(user_id, "❌ Erro ao combinar. Crédito reembolsado.")
    
    except Exception as e:
        add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
        logger.error(f"Erro combinacao padrao: {e}")
        diagnose_and_notify(e, "combinacao_padrao")
        bot.send_message(user_id, "❌ Erro ao combinar. Crédito reembolsado.")
    finally:
        photo_collections.pop(user_id, None)


def execute_combine_pro(user_id, lang, caption):
    """Executa combinacao com modelo Pro"""
    try:
        if user_id not in photo_collections:
            return
        
        collection = photo_collections[user_id]
        photos = collection["photos"]
        
        if not use_credit(user_id, MODELO_PRO["custo"]):
            bot.send_message(user_id, "❌ Créditos insuficientes para Modelo Pro!")
            return
        
        bot.send_message(user_id, f"✨ Combinando {len(photos)} fotos com Modelo Pro...\nIsto pode demorar um pouco.")
        
        # Baixar todas as fotos como base64
        photo_data_urls = []
        for photo_id in photos[:5]:
            try:
                file_info = bot.get_file(photo_id)
                downloaded_file = bot.download_file(file_info.file_path)
                img_b64 = base64.b64encode(downloaded_file).decode('utf-8')
                photo_data_urls.append(f"data:image/jpeg;base64,{img_b64}")
            except:
                continue
        
        if len(photo_data_urls) < 2:
            add_credits(user_id, MODELO_PRO["custo"], "reembolso")
            bot.send_message(user_id, "❌ Erro ao processar fotos. Créditos reembolsados.")
            return
        
        if caption:
            enhanced_prompt = improve_prompt_auto(f"Combine these {len(photo_data_urls)} characters/people: {caption}. All subjects together, cohesive scene, high quality")
        else:
            enhanced_prompt = f"Combine all {len(photo_data_urls)} characters together in one cohesive scene, natural composition, high quality, photorealistic"
        
        input_params = {
            "prompt": enhanced_prompt,
            "images": photo_data_urls,
            "safety_tolerance": 6,
            "disable_safety_checker": True
        }
        
        output = replicate.run(MODELO_PRO["replicate_id"], input=input_params)
        
        if isinstance(output, list):
            urls = [str(url) for url in output]
        elif hasattr(output, 'url'):
            urls = [str(output.url)]
        else:
            urls = [str(output)]
        
        if urls and len(urls) > 0:
            image_url = urls[0]
            img_data = requests.get(image_url, timeout=60).content
            creditos_restantes = get_user_credits(user_id)
            
            success_texts = {
                "pt": f"✨ <b>Fotos combinadas com Pro!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B)\n📸 {len(photos)} imagens\n💳 Créditos: <code>{creditos_restantes}</code>",
                "en": f"✨ <b>Photos combined with Pro!</b>\n🤖 Model: Pro (FLUX.2 Klein 9B)\n📸 {len(photos)} images\n💳 Credits: <code>{creditos_restantes}</code>",
                "es": f"✨ <b>Fotos combinadas con Pro!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B)\n📸 {len(photos)} imagenes\n💳 Créditos: <code>{creditos_restantes}</code>"
            }
            creation_id = add_to_history(user_id, "edit", enhanced_prompt, image_url)
            bot.send_photo(user_id, img_data, caption=success_texts.get(lang, success_texts["pt"]),
                         reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            update_user_stats(user_id, "total_creations")
        else:
            add_credits(user_id, MODELO_PRO["custo"], "reembolso")
            bot.send_message(user_id, "❌ Erro ao combinar. Créditos reembolsados.")
    
    except Exception as e:
        add_credits(user_id, MODELO_PRO["custo"], "reembolso")
        logger.error(f"Erro combinacao Pro: {e}")
        diagnose_and_notify(e, "combinacao_pro")
        bot.send_message(user_id, "❌ Erro ao combinar com Pro. Créditos reembolsados.")
    finally:
        photo_collections.pop(user_id, None)

def processar_criacao(chat_id, user_id, prompt, lang, auto_improve=True):
    style_settings = get_user_style_settings(user_id)
    num_variations = style_settings.get("num_variations", 1)
    visual_style = style_settings.get("visual_style", "livre")
    aspect_ratio = style_settings.get("aspect_ratio", "square")
    
    # Validar que estilo e formato existem
    if visual_style not in VISUAL_STYLES:
        visual_style = "livre"
    if aspect_ratio not in ASPECT_RATIOS:
        aspect_ratio = "square"
    
    # Melhorar prompt automaticamente
    if auto_improve:
        improved_prompt = improve_prompt_auto(prompt, lang)
        style_suffix = VISUAL_STYLES[visual_style]["suffix"]
        final_prompt = f"{improved_prompt}{style_suffix}"
    else:
        final_prompt = prompt
    
    ratio = ASPECT_RATIOS[aspect_ratio]["ratio"]
    
    proc = bot.send_message(chat_id, f"🎨 Criando {num_variations} variação{'ões' if num_variations > 1 else ''}...")
    try:
        start = time.time()
        urls = gerar_imagem_modelo(final_prompt, ratio, num_outputs=num_variations)
        elapsed = round(time.time() - start, 1)
        creditos = get_user_credits(user_id)
        
        bot.delete_message(chat_id, proc.message_id)
        
        for i, url in enumerate(urls, 1):
            img = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "create", final_prompt, url)
            caption = f"✅ {i}/{num_variations} | ⏱️{elapsed}s\n💳 Restam: <code>{creditos}</code>"
            bot.send_photo(chat_id, img, caption=caption, reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
        
        logger.info(f"Imagens criadas para user {user_id}: {num_variations}")
    except Exception as e:
        add_credits(user_id, 1, "reembolso")
        save_user_error(user_id, "criacao", str(e), "Criação com variações")
        diagnose_and_notify(e, "criacao")
        bot.edit_message_text("❌ Erro. Crédito reembolsado.", chat_id, proc.message_id)

# ==================== CALLBACKS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def callback_language(call):
    user_id = call.from_user.id
    lang_code = call.data.replace('lang_', '')
    print(f"🌐 User {user_id} selecionou idioma: {lang_code}")
    if set_user_lang(user_id, lang_code):
        print(f"✅ Callback respondido: {SUPPORTED_LANGUAGES[lang_code]}")
        bot.answer_callback_query(call.id, f"✅ {SUPPORTED_LANGUAGES[lang_code]}")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        texts = {
            "pt": "🤖 <b>Bem-vindo ao Remake Pixel!</b> 👑\n\nVocê já usou este bot antes?",
            "en": "🤖 <b>Welcome to Remake Pixel!</b> 👑\n\nHave you used this bot before?",
            "es": "🤖 <b>¡Bienvenido a Remake Pixel!</b> 👑\n\n¿Has usado este bot antes?",
            "fr": "🤖 <b>Bienvenue sur Remake Pixel!</b> 👑\n\nAvez-vous déjà utilisé ce bot?"
        }
        print(f"📤 Enviando onboarding em {lang_code}")
        bot.send_message(call.message.chat.id, texts.get(lang_code, texts["pt"]), reply_markup=onboarding_keyboard(lang_code), parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('onboard_'))
def callback_onboarding(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('onboard_', '')
    bot.answer_callback_query(call.id)
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    if action == "yes":
        set_onboarded(user_id)
        terms = {
            "pt": "📋 <b>Termos de Uso</b>\n\n• Imagens para uso pessoal e criativo\n• Utilizador responsável pelo conteúdo\n• Créditos não reembolsáveis\n• Serviço pode ser modificado",
            "en": "📋 <b>Terms of Use</b>\n\n• Images for personal and creative use\n• User responsible for content\n• Credits non-refundable\n• Service may be modified",
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Aceito", callback_data="terms_accept"),
            telebot.types.InlineKeyboardButton("❌ Recuso", callback_data="terms_decline")
        )
        bot.send_message(call.message.chat.id, terms.get(lang, terms["pt"]), reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(call.message.chat.id, "🎨 <b>Bem-vindo ao Remake Pixel!</b>\n\nCrie e edite imagens com IA.\n5 créditos grátis para experimentar!", parse_mode='HTML')
        time.sleep(1)
        set_onboarded(user_id)
        terms = {
            "pt": "📋 <b>Termos de Uso</b>\n\n• Imagens para uso pessoal e criativo\n• Utilizador responsável pelo conteúdo\n• Créditos não reembolsáveis\n• Serviço pode ser modificado",
            "en": "📋 <b>Terms of Use</b>\n\n• Images for personal and creative use\n• User responsible for content\n• Credits non-refundable\n• Service may be modified",
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Aceito", callback_data="terms_accept"),
            telebot.types.InlineKeyboardButton("❌ Recuso", callback_data="terms_decline")
        )
        bot.send_message(call.message.chat.id, terms.get(lang, terms["pt"]), reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('action_'))
def callback_actions(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('action_', '')
    bot.answer_callback_query(call.id)
    
    if action in ["menu", "cancel"]:
        user_states.pop(user_id, None)
        pending_photos.pop(user_id, None)
        wizard_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        show_main_menu(call.message.chat.id, user_id, lang)
    
    elif action == "create":
        user_states[user_id] = "awaiting_prompt_create"
        texts = {"pt": "🎨 Descreva a imagem:", "en": "🎨 Describe the image:", "es": "🎨 Describe la imagen:", "fr": "🎨 Décrivez l'image:"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang))
    
    elif action == "create":
        # Ir direto ao prompt de geração
        user_states[user_id] = "awaiting_prompt_create"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        texts = {
            "pt": "🎨 <b>Gerar Imagem</b>\n\nDescreva a imagem que deseja criar:\n\n<b>Exemplos:</b>\n• 'Uma cidade futurista ao pôr do sol'\n• 'Retrato de uma guerreira samurai'\n• 'Logo minimalista para cafetaria'\n\n💡 Quanto mais detalhes, melhor o resultado!",
            "en": "🎨 <b>Generate Image</b>\n\nDescribe the image you want:\n\n<b>Examples:</b>\n• 'A futuristic city at sunset'\n• 'Portrait of a samurai warrior'\n• 'Minimalist logo for a coffee shop'\n\n💡 More details = better results!",
        }
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=cancel_keyboard(lang), parse_mode='HTML')
    
    elif action == "wizard":
        question = start_wizard(user_id, lang)
        user_states[user_id] = "in_wizard"
        bot.edit_message_text(f"🧙 <b>Assistente Prompt</b>\n\n{question}", call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang), parse_mode='HTML')
    
    elif action == "edit_photos":
        # Novo: Editar Fotos
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        texts = {
            "pt": ("📸 <b>Editar Fotos</b>\n\n"
                   "Envie 1 a 5 imagens no chat.\n\n"
                   "<b>3 modos disponíveis:</b>\n\n"
                   "🎨 <b>Padrão</b> (1 cred)\n"
                   "→ Requer prompt obrigatório\n"
                   "→ Ex: 'Melhore a qualidade', 'Remova o fundo'\n\n"
                   "✨ <b>Pro</b> (3 cred)\n"
                   "→ Melhoria fotorrealista automática\n"
                   "→ Não precisa de prompt\n\n"
                   "🎭 <b>Artístico</b> (2 cred)\n"
                   "→ Transforma em 33 estilos (anime, Disney, etc.)\n"
                   "→ Prompt opcional\n\n"
                   "💡 <b>Dica:</b> Envie 2-5 fotos juntas para combinar!"),
            "en": ("📸 <b>Edit Photos</b>\n\n"
                   "Send 1 to 5 images in the chat.\n\n"
                   "<b>3 modes available:</b>\n\n"
                   "🎨 <b>Standard</b> (1 cred) — Requires prompt\n"
                   "✨ <b>Pro</b> (3 cred) — Auto photorealistic (no prompt needed)\n"
                   "🎭 <b>Artistic</b> (2 cred) — 33 art styles\n\n"
                   "💡 Send 2-5 photos together to combine!"),
        }
        
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), 
                        reply_markup=cancel_keyboard(lang), parse_mode='HTML')
    
    elif action == "credits":
        creditos = get_user_credits(user_id)
        data = load_json(CREDITS_FILE)
        usados = data.get(str(user_id), {}).get("total_usado", 0)
        texts = {
            "pt": f"💳 <b>Créditos</b>\n\n✨ Disponíveis: <code>{creditos}</code>\n📊 Usados: <code>{usados}</code>",
            "en": f"💳 <b>Credits</b>\n\n✨ Available: <code>{creditos}</code>\n📊 Used: <code>{usados}</code>",
            "es": f"💳 <b>Créditos</b>\n\n✨ Disponibles: <code>{creditos}</code>\n📊 Usados: <code>{usados}</code>",
            "fr": f"💳 <b>Crédits</b>\n\n✨ Disponibles: <code>{creditos}</code>\n📊 Utilisés: <code>{usados}</code>"
        }
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang), parse_mode='HTML')
    
    elif action == "buy":
        texts = {"pt": "🛒 <b>Comprar</b>\n\nEscolha:", "en": "🛒 <b>Buy</b>\n\nChoose:", "es": "🛒 <b>Comprar</b>\n\nElige:", "fr": "🛒 <b>Acheter</b>\n\nChoisir:"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=buy_keyboard(lang), parse_mode='HTML')
    
    elif action == "settings":
        settings = get_user_style_settings(user_id)
        personality = get_user_personality(user_id)
        pers_info = AI_PERSONALITIES[personality]
        texts = {
            "pt": f"⚙️ <b>Configurações</b>\n\n🎨 Estilo: {settings['visual_style']}\n📐 Formato: {settings['aspect_ratio']}\n🔢 Variações: {settings['num_variations']}\n🤖 IA: {pers_info['emoji']} {pers_info['nome']}\n\nEscolha:",
            "en": f"⚙️ <b>Settings</b>\n\n🎨 Style: {settings['visual_style']}\n📐 Format: {settings['aspect_ratio']}\n🔢 Variations: {settings['num_variations']}\n🤖 AI: {pers_info['emoji']} {pers_info['nome']}\n\nChoose:",
            "es": f"⚙️ <b>Configuración</b>\n\n🎨 Estilo: {settings['visual_style']}\n📐 Formato: {settings['aspect_ratio']}\n🔢 Variaciones: {settings['num_variations']}\n🤖 IA: {pers_info['emoji']} {pers_info['nome']}\n\nElige:"
        }
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=settings_keyboard(lang), parse_mode='HTML')
    
    elif action == "carousel":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            telebot.types.InlineKeyboardButton("2 slides", callback_data="carousel_num_2"),
            telebot.types.InlineKeyboardButton("3 slides", callback_data="carousel_num_3"),
            telebot.types.InlineKeyboardButton("4 slides", callback_data="carousel_num_4")
        )
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="carousel_num_cancel"))
        
        creditos = get_user_credits(user_id)
        texts = {
            "pt": f"📱 <b>Carrossel Instagram</b>\n\nGera imagens em sequência para carrossel.\nCusto: 1 crédito por slide.\n\n💳 Créditos: <code>{creditos}</code>\n\nQuantos slides?",
            "en": f"📱 <b>Instagram Carousel</b>\n\nGenerate sequential images for carousel.\nCost: 1 credit per slide.\n\n💳 Credits: <code>{creditos}</code>\n\nHow many slides?",
        }
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
    
    elif action == "help":
        texts = {
            "pt": (f"❓ <b>Ajuda - Remake Pixel</b>\n\n"
                   f"<b>🎨 GERAR IMAGENS</b>\n"
                   f"No menu, clique em 'Gerar Fotos' e descreva o que quer criar.\n\n"
                   f"<b>📸 EDITAR FOTOS</b>\n"
                   f"Envie 1 a 5 fotos no chat.\n"
                   f"🎨 Padrão (1 cred) — Descreva o que quer mudar\n"
                   f"✨ Pro (3 cred) — Melhoria automática sem prompt\n"
                   f"🎭 Artístico (2 cred) — 33 estilos artísticos\n\n"
                   f"<b>📱 CARROSSEL</b>\n"
                   f"Gera 2-4 imagens em sequência para Instagram.\n\n"
                   f"<b>⚙️ CONFIGURAÇÕES</b>\n"
                   f"Estilos visuais (33 opções), formato (Instagram, TikTok, etc.), variações e personalidade da IA.\n\n"
                   f"<b>💬 CHAT IA</b>\n"
                   f"Escreva qualquer mensagem para conversar com a IA. Grátis!\n\n"
                   f"<b>📋 COMANDOS</b>\n"
                   f"/menu — Menu principal\n"
                   f"/start — Reiniciar bot\n"
                   f"/wizard — Assistente de criação\n"
                   f"/creditos — Ver saldo\n"
                   f"/idioma — Mudar idioma\n"
                   f"/termos — Termos de uso\n\n"
                   f"Dúvidas? Clique abaixo para falar com o suporte!"),
            "en": (f"❓ <b>Help - Remake Pixel</b>\n\n"
                   f"<b>🎨 GENERATE</b> — Click 'Generate' and describe what you want.\n"
                   f"<b>📸 EDIT</b> — Send 1-5 photos. Choose Standard/Pro/Artistic.\n"
                   f"<b>📱 CAROUSEL</b> — Generate 2-4 sequential images.\n"
                   f"<b>⚙️ SETTINGS</b> — 33 styles, formats, variations.\n"
                   f"<b>💬 AI CHAT</b> — Free, just type!\n\n"
                   f"Questions? Click below for support!"),
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            telebot.types.InlineKeyboardButton("💬 Perguntar ao Suporte (Chat IA)", callback_data="action_support_chat"),
            telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="action_menu")
        )
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    
    elif action == "support_chat":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        texts = {
            "pt": "💬 <b>Suporte IA</b>\n\nEscreva a sua dúvida! A IA sabe tudo sobre o bot e vai ajudá-lo.\n\nExemplos:\n• 'Como mudo o estilo das minhas imagens?'\n• 'Como funciona o modelo Pro?'\n• 'Como compro créditos?'",
            "en": "💬 <b>AI Support</b>\n\nType your question! The AI knows everything about the bot.\n\nExamples:\n• 'How do I change image style?'\n• 'How does Pro model work?'\n• 'How to buy credits?'",
        }
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), parse_mode='HTML')
    
    elif action == "referral":
        link = create_referral_link(user_id)
        total = get_referral_count(user_id)
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        texts = {
            "pt": f"🎁 <b>Indique amigos e ganhe creditos!</b>\n\n📊 Suas indicacoes: {total}\n💰 Bonus: +10 creditos quando seu amigo comprar 5EUR+\n\nClique no botao abaixo para partilhar:",
            "en": f"🎁 <b>Refer friends and earn credits!</b>\n\n📊 Your referrals: {total}\n💰 Bonus: +10 credits when friend buys 5EUR+\n\nClick button below to share:",
            "es": f"🎁 <b>Recomienda amigos y gana creditos!</b>\n\n📊 Tus referencias: {total}\n💰 Bonus: +10 creditos cuando tu amigo compre 5EUR+\n\nHaz clic en el boton para compartir:"
        }
        
        share_text = "Experimenta o Remake Pixel! Cria e edita imagens com IA no Telegram. 5 créditos grátis!"
        share_url = link
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            telebot.types.InlineKeyboardButton("📤 Partilhar com amigos", url=f"https://t.me/share/url?url={share_url}&text={share_text}"),
            telebot.types.InlineKeyboardButton("📋 Copiar link", callback_data="action_copy_link"),
            telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="action_cancel")
        )
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
    
    elif action == "copy_link":
        link = create_referral_link(user_id)
        bot.send_message(call.message.chat.id, f"📋 Seu link:\n\n<code>{link}</code>\n\nToque para copiar!", parse_mode='HTML')
    
    elif action == "history":
        history = get_user_history(user_id)
        if not history:
            texts = {"pt": "📚 Histórico vazio", "en": "📚 Empty history", "es": "📚 Historial vacío"}
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang))
        else:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            for entry in history[:5]:
                emoji = "🎨" if entry['type'] == 'create' else "✏️"
                try:
                    bot.send_photo(call.message.chat.id, entry['url'], 
                                 caption=f"{emoji} {entry['prompt'][:100]}", 
                                 reply_markup=creation_actions_keyboard(entry['id'], lang))
                except:
                    pass
            show_main_menu(call.message.chat.id, user_id, lang)
    
    elif action == "favorites":
        favorites = get_user_favorites(user_id)
        if not favorites:
            texts = {"pt": "⭐ Sem favoritos ainda", "en": "⭐ No favorites yet", "es": "⭐ Sin favoritos aún"}
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang))
        else:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            history = get_user_history(user_id)
            for fav_id in favorites[:5]:
                creation = get_creation_by_id(user_id, fav_id)
                if creation:
                    try:
                        bot.send_photo(call.message.chat.id, creation['url'], 
                                     caption=f"⭐ {creation['prompt'][:100]}")
                    except:
                        pass
            show_main_menu(call.message.chat.id, user_id, lang)
    
    elif action == "stats":
        stats = get_user_stats(user_id)
        if not stats:
            stats = {"total_creations": 0, "total_edits": 0, "total_favorites": 0, "total_shares": 0}
        texts = {
            "pt": "<b>📊 Suas Estatísticas</b>\n\n🎨 Criações: " + str(stats.get('total_creations', 0)) + "\n✏️ Edições: " + str(stats.get('total_edits', 0)) + "\n⭐ Favoritos: " + str(len(get_user_favorites(user_id))) + "\n🔗 Compartilhamentos: " + str(stats.get('total_shares', 0)) + "\n🎁 Indicações: " + str(get_referral_count(user_id)) + "\n\nContinue criando! 🚀",
            "en": "<b>📊 Your Statistics</b>\n\n🎨 Creations: " + str(stats.get('total_creations', 0)) + "\n✏️ Edits: " + str(stats.get('total_edits', 0)) + "\n⭐ Favorites: " + str(len(get_user_favorites(user_id))) + "\n🔗 Shares: " + str(stats.get('total_shares', 0)) + "\n🎁 Referrals: " + str(get_referral_count(user_id)) + "\n\nKeep creating! 🚀",
            "es": "<b>📊 Tus Estadísticas</b>\n\n🎨 Creaciones: " + str(stats.get('total_creations', 0)) + "\n✏️ Ediciones: " + str(stats.get('total_edits', 0)) + "\n⭐ Favoritos: " + str(len(get_user_favorites(user_id))) + "\n🔗 Compartidos: " + str(stats.get('total_shares', 0)) + "\n🎁 Referencias: " + str(get_referral_count(user_id)) + "\n\n¡Sigue creando! 🚀"
        }
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=cancel_keyboard(lang), parse_mode='HTML')
    
    elif action == "examples":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        texts = {"pt": "🖼️ <b>Galeria de Exemplos</b>\n\nInspire-se!", "en": "🖼️ <b>Example Gallery</b>\n\nGet inspired!", "es": "🖼️ <b>Galería de Ejemplos</b>\n\n¡Inspírate!"}
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), parse_mode='HTML')
        for ex in EXAMPLE_GALLERY:
            try:
                bot.send_photo(call.message.chat.id, ex['url'], caption=f"💡 {ex['desc']}\n<code>{ex['prompt']}</code>", parse_mode='HTML')
            except:
                pass
        show_main_menu(call.message.chat.id, user_id, lang)

@bot.callback_query_handler(func=lambda call: call.data.startswith('settings_'))
def callback_settings(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    setting = call.data.replace('settings_', '')
    bot.answer_callback_query(call.id)
    
    if setting == "styles":
        texts = {"pt": "🎨 <b>Estilos Visuais</b>\n\nEscolha:", "en": "🎨 <b>Visual Styles</b>\n\nChoose:", "es": "🎨 <b>Estilos Visuales</b>\n\nElige:"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=styles_keyboard(lang), parse_mode='HTML')
    
    elif setting == "variations":
        texts = {"pt": "🔢 <b>Número de Variações</b>\n\nQuantas imagens criar por vez?", "en": "🔢 <b>Number of Variations</b>\n\nHow many images to create at once?", "es": "🔢 <b>Número de Variaciones</b>\n\n¿Cuántas imágenes crear a la vez?"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=variations_keyboard(lang), parse_mode='HTML')
    
    elif setting == "personality":
        texts = {"pt": "🤖 <b>Personalidade da IA</b>\n\nEscolha:", "en": "🤖 <b>AI Personality</b>\n\nChoose:", "es": "🤖 <b>Personalidad de la IA</b>\n\nElige:"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=personality_keyboard(lang), parse_mode='HTML')
    
    elif setting == "format":
        texts = {"pt": "📐 <b>Formato da Imagem</b>\n\nEscolha o tamanho:", "en": "📐 <b>Image Format</b>\n\nChoose size:"}
        bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, reply_markup=format_keyboard(lang), parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('style_'))
def callback_style(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    style = call.data.replace('style_', '')
    set_user_style(user_id, visual_style=style)
    style_info = VISUAL_STYLES.get(style, VISUAL_STYLES["livre"])
    bot.answer_callback_query(call.id, f"✅ {style_info['emoji']} {style_info['desc']}")
    try:
        bot.edit_message_text(f"✅ Estilo alterado: {style_info['emoji']} {style_info['desc']}", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('aspect_'))
def callback_aspect(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    aspect = call.data.replace('aspect_', '')
    set_user_style(user_id, aspect_ratio=aspect)
    aspect_info = ASPECT_RATIOS[aspect]
    bot.answer_callback_query(call.id, f"✅ {aspect_info['emoji']} {aspect_info['desc']}")
    try:
        bot.edit_message_text(f"✅ Formato alterado: {aspect_info['emoji']} {aspect_info['desc']}", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('var_'))
def callback_variations(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    num = int(call.data.replace('var_', ''))
    set_user_style(user_id, num_variations=num)
    bot.answer_callback_query(call.id, f"✅ {num} variações")
    try:
        bot.edit_message_text(f"✅ Variações: {num}", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('pers_'))
def callback_personality(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    pers = call.data.replace('pers_', '')
    set_user_personality(user_id, pers)
    pers_info = AI_PERSONALITIES[pers]
    bot.answer_callback_query(call.id, f"✅ {pers_info['emoji']} {pers_info['nome']}")
    try:
        bot.edit_message_text(f"✅ Personalidade: {pers_info['emoji']} {pers_info['nome']}", call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('fav_'))
def callback_favorite(call):
    user_id = call.from_user.id
    creation_id = call.data.replace('fav_', '')
    success = add_to_favorites(user_id, creation_id)
    if success:
        update_user_stats(user_id, "total_favorites")
        bot.answer_callback_query(call.id, "⭐ Favoritado!")
    else:
        bot.answer_callback_query(call.id, "✅ Já nos favoritos")

@bot.callback_query_handler(func=lambda call: call.data.startswith('share_'))
def callback_share(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    creation_id = call.data.replace('share_', '')
    creation = get_creation_by_id(user_id, creation_id)
    if creation:
        share_id = share_creation(user_id, creation)
        share_link = f"https://t.me/{BOT_USERNAME}?start=view_{share_id}"
        texts = {
            "pt": f"🔗 <b>Link de Compartilhamento</b>\n\n<code>{share_link}</code>\n\nCompartilhe com seus amigos!",
            "en": f"🔗 <b>Share Link</b>\n\n<code>{share_link}</code>\n\nShare with your friends!",
            "es": f"🔗 <b>Enlace para Compartir</b>\n\n<code>{share_link}</code>\n\n¡Comparte con tus amigos!"
        }
        bot.answer_callback_query(call.id, "✅ Link criado!")
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def callback_buy(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    username = call.from_user.username or "sem_username"
    first_name = call.from_user.first_name or "Sem nome"
    pid = int(call.data.replace('buy_', ''))
    pacote = PACOTES.get(pid)
    if not pacote:
        return
    bot.answer_callback_query(call.id, "📝 Processando...")
    request_id = f"req_{user_id}_{int(time.time())}"
    pending = load_json(PENDING_FILE)
    pending[request_id] = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'pacote_id': pid,
        'pacote_nome': pacote['nome'],
        'creditos': pacote['creditos'],
        'valor': pacote['preco'],
        'status': 'pendente'
    }
    save_json(PENDING_FILE, pending, PENDING_LOCK)
    preco = pacote['preco'] / 100
    bot.edit_message_text(f"✅ Solicitado!\n\n📦 {pacote['nome']}\n💶 €{preco:.2f}\n\n⏳ Aguarde aprovação", call.message.chat.id, call.message.message_id, parse_mode='HTML')
    notify_admin(f"🛒 <b>COMPRA</b>\n\n🆔 <code>{request_id}</code>\n👤 {first_name}\n📱 @{username}\n🆔 ID: <code>{user_id}</code>\n📦 {pacote['nome']}\n💶 €{preco:.2f}\n\n/aceitar {request_id}", "money")
    
    # Enviar botao de aprovacao rapida para admin
    for admin_id in ADMIN_IDS:
        try:
            markup_admin = telebot.types.InlineKeyboardMarkup()
            markup_admin.add(telebot.types.InlineKeyboardButton("✅ Aprovar compra", callback_data=f"quick_approve_{request_id}"))
            bot.send_message(admin_id, f"👆 Clique para aprovar a compra de {first_name}:", reply_markup=markup_admin)
        except:
            pass

# ==================== PAINEL DE CONTROLE ADMINISTRATIVO ====================
admin_states = {}

def admin_panel_keyboard(user_id=None):
    """Teclado do painel administrativo - diferente para super admin e secundario"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    is_super = is_super_admin(user_id) if user_id else True
    
    if is_super:
        # Super admin - acesso total
        markup.add(
            telebot.types.InlineKeyboardButton("💳 Dar Créditos", callback_data="admin_give_credits"),
            telebot.types.InlineKeyboardButton("📊 Estatísticas", callback_data="admin_stats")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("👥 Listar Usuários", callback_data="admin_list_users"),
            telebot.types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
        )
        global bot_paused
        pause_text = "▶️ Despausar Bot" if bot_paused else "⏸️ Pausar Bot"
        markup.add(
            telebot.types.InlineKeyboardButton(pause_text, callback_data="admin_toggle_pause"),
            telebot.types.InlineKeyboardButton("🌐 Ngrok URL", callback_data="admin_ngrok")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("📈 Status Bot", callback_data="admin_bot_status"),
            telebot.types.InlineKeyboardButton("🛒 Aprovar Compras", callback_data="admin_pending")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("💰 Financeiro", callback_data="admin_finance"),
            telebot.types.InlineKeyboardButton("👑 Gerir Admins", callback_data="admin_manage_admins")
        )
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Config Avançadas", callback_data="admin_advanced"))
    else:
        # Admin secundario - acesso limitado
        markup.add(
            telebot.types.InlineKeyboardButton("📊 Estatísticas", callback_data="admin_stats"),
            telebot.types.InlineKeyboardButton("👥 Núm. Utilizadores", callback_data="admin_list_users")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            telebot.types.InlineKeyboardButton("💰 Financeiro", callback_data="admin_finance")
        )
    
    markup.add(telebot.types.InlineKeyboardButton("❌ Fechar", callback_data="admin_close"))
    return markup

def users_list_keyboard(page=0):
    """Lista de usuários com paginação - Mostra username"""
    data = load_json(CREDITS_FILE)
    users = list(data.items())
    
    # Paginação (10 por página)
    per_page = 10
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    for user_id_str, user_data in page_users:
        creditos = user_data.get('creditos', 0)
        
        # Tentar obter username do Telegram
        try:
            user_info = bot.get_chat(int(user_id_str))
            username = f"@{user_info.username}" if user_info.username else user_info.first_name
            display_name = f"{username} ({user_id_str})"
        except:
            # Se falhar, mostrar apenas ID
            display_name = f"ID: {user_id_str}"
        
        markup.add(telebot.types.InlineKeyboardButton(
            f"{display_name} | 💳 {creditos}",
            callback_data=f"admin_select_user_{user_id_str}"
        ))
    
    # Navegação
    nav_buttons = []
    if page > 0:
        nav_buttons.append(telebot.types.InlineKeyboardButton("◀️ Anterior", callback_data=f"admin_users_page_{page-1}"))
    if end < len(users):
        nav_buttons.append(telebot.types.InlineKeyboardButton("Próxima ▶️", callback_data=f"admin_users_page_{page+1}"))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar ao Painel", callback_data="admin_panel"))
    return markup

def credit_amounts_keyboard(user_id):
    """Teclado para escolher quantidade de créditos"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    amounts = [5, 10, 20, 50, 100, 200, 500, 1000]
    
    buttons = []
    for amount in amounts:
        buttons.append(telebot.types.InlineKeyboardButton(
            f"+{amount}",
            callback_data=f"admin_add_{user_id}_{amount}"
        ))
    
    # Adicionar em linhas de 3
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])
    
    markup.add(telebot.types.InlineKeyboardButton("✏️ Quantidade personalizada", callback_data=f"admin_custom_{user_id}"))
    markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_give_credits"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def callback_admin_panel(call):
    user_id = call.from_user.id
    
    # Verificar se é admin
    if user_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Acesso negado!", show_alert=True)
        return
    
    action = call.data.replace('admin_', '')
    bot.answer_callback_query(call.id)
    
    if action == "panel" or action == "close":
        if action == "close":
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            return
        
        # Mostrar painel principal
        msg = "🎛️ <b>PAINEL DE CONTROLE</b> 🔐\n\n"
        msg += "Gerencie seu bot através dos botões abaixo:"
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=admin_panel_keyboard(user_id), parse_mode='HTML')
    
    elif action == "stats":
        # Estatísticas gerais
        credits_data = load_json(CREDITS_FILE)
        ref_data = load_json(REFERRAL_FILE)
        stats_data = load_json(STATISTICS_FILE)
        
        total_users = len(credits_data)
        total_credits_distributed = sum(u.get('creditos', 0) for u in credits_data.values())
        total_credits_used = sum(u.get('total_usado', 0) for u in credits_data.values())
        total_creations = sum(s.get('total_creations', 0) for s in stats_data.values())
        total_referrals = sum(len(refs) for refs in ref_data.get('referrals', {}).values())
        
        msg = "📊 <b>ESTATÍSTICAS GERAIS</b>\n\n"
        msg += f"👥 Total de Usuários: <code>{total_users}</code>\n"
        msg += f"💳 Créditos Disponíveis: <code>{total_credits_distributed}</code>\n"
        msg += f"📉 Créditos Usados: <code>{total_credits_used}</code>\n"
        msg += f"🎨 Total de Criações: <code>{total_creations}</code>\n"
        msg += f"🎁 Total de Referrals: <code>{total_referrals}</code>\n"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "list_users":
        # Listar usuários
        data = load_json(CREDITS_FILE)
        
        msg = f"👥 <b>USUÁRIOS CADASTRADOS</b>\n\n"
        msg += f"Total: <code>{len(data)}</code> usuários\n\n"
        msg += "Selecione um usuário para ver detalhes:"
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=users_list_keyboard(0), parse_mode='HTML')
    
    elif action == "give_credits":
        # Dar créditos
        msg = "💳 <b>DAR CRÉDITOS</b>\n\n"
        msg += "Selecione o usuário para adicionar créditos:"
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=users_list_keyboard(0), parse_mode='HTML')
    
    elif action == "broadcast":
        # Iniciar broadcast
        admin_states[user_id] = "awaiting_broadcast"
        
        msg = "📢 <b>BROADCAST</b>\n\n"
        msg += "Digite a mensagem que deseja enviar para TODOS os usuários:\n\n"
        msg += "⚠️ <i>A mensagem será enviada imediatamente!</i>"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "ngrok":
        # Mostrar URL do Ngrok
        ngrok_url = get_current_ngrok_url()
        
        msg = "🌐 <b>URL DO NGROK</b>\n\n"
        if ngrok_url:
            msg += f"🔗 <code>{ngrok_url}</code>\n\n"
            msg += "✅ Bot acessível externamente"
        else:
            msg += "❌ Ngrok não detectado\n\n"
            msg += "Execute o bot com Ngrok para webhooks externos"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "bot_status":
        # Status do bot
        uptime = datetime.now() - bot_start_time
        uptime_str = str(uptime).split('.')[0]
        
        msg = "📈 <b>STATUS DO BOT</b>\n\n"
        msg += f"✅ Bot Online\n"
        msg += f"⏰ Uptime: <code>{uptime_str}</code>\n"
        msg += f"🤖 Polling ativo\n"
        msg += f"💾 Backup automático: ativo\n"
        msg += f"💓 Heartbeat: ativo\n"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "pending":
        # Aprovar compras pendentes - LIMPAR as ja processadas
        pending = load_json(PENDING_FILE)
        
        # Limpar pedidos que nao sao pendentes
        pending_only = {k: v for k, v in pending.items() if v.get('status') == 'pendente'}
        if len(pending_only) != len(pending):
            save_json(PENDING_FILE, pending_only, PENDING_LOCK)
            pending = pending_only
        
        pending_list = list(pending.keys())
        
        msg = "🛒 <b>COMPRAS PENDENTES</b>\n\n"
        
        if not pending_list:
            msg += "✅ Nenhuma compra pendente no momento"
        else:
            msg += f"📋 {len(pending_list)} compra(s) aguardando aprovação:\n\n"
            for req_id in pending_list[:10]:
                req = pending[req_id]
                msg += f"🆔 <code>{req_id}</code>\n"
                msg += f"👤 {req.get('first_name', 'N/A')} (@{req.get('username', 'N/A')})\n"
                msg += f"📦 {req['pacote_nome']} - {req.get('creditos', '?')} creditos\n"
                msg += f"💶 €{req.get('valor', 0)/100:.2f}\n"
                msg += f"➡️ <code>/aceitar {req_id}</code>\n\n"
        
        markup = telebot.types.InlineKeyboardMarkup()
        if pending_list:
            markup.add(telebot.types.InlineKeyboardButton("🗑️ Limpar tudo", callback_data="admin_clear_pending"))
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "clear_pending":
        # Limpar todos os pendentes
        save_json(PENDING_FILE, {}, PENDING_LOCK)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        bot.edit_message_text("🗑️ <b>Lista de pendentes limpa!</b>", call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "finance":
        # Painel financeiro
        credits_data = load_json(CREDITS_FILE)
        total_users = len(credits_data)
        total_creditos_em_uso = sum(u.get('creditos', 0) for u in credits_data.values())
        total_creditos_usados = sum(u.get('total_usado', 0) for u in credits_data.values())
        
        # Custos estimados por modelo
        custo_padrao = 0.005  # EUR por credito (1 cred = 1 imagem)
        custo_pro = 0.008     # EUR por credito (3 cred = 1 imagem Pro)
        custo_artistico = 0.010  # EUR por credito (2 cred = 1 imagem)
        custo_medio = 0.008   # Media
        
        custo_total_replicate = round(total_creditos_usados * custo_medio, 2)
        
        # Tabela de precos por pacote
        msg = "💰 <b>PAINEL FINANCEIRO</b>\n\n"
        msg += f"👥 Total usuarios: {total_users}\n"
        msg += f"💳 Créditos em circulação: {total_creditos_em_uso}\n"
        msg += f"🔥 Créditos já usados: {total_creditos_usados}\n\n"
        
        msg += "📊 <b>CUSTO REPLICATE ESTIMADO:</b>\n"
        msg += f"├ Total gasto: ~€{custo_total_replicate}\n"
        msg += f"└ Media por credito: ~€{custo_medio}\n\n"
        
        msg += "💶 <b>TABELA DE LUCRO POR PACOTE:</b>\n\n"
        for pid, pac in PACOTES.items():
            preco = pac['preco'] / 100
            creds = pac['creditos']
            custo = round(creds * custo_medio, 2)
            lucro = round(preco - custo, 2)
            margem = round((lucro/preco)*100, 1)
            replicate_minimo = round(custo * 1.2, 2)
            msg += f"📦 <b>{pac['nome']}</b>\n"
            msg += f"├ Preco: €{preco:.2f} ({creds} cred)\n"
            msg += f"├ Custo Replicate: ~€{custo}\n"
            msg += f"├ <b>Lucro: ~€{lucro} ({margem}%)</b>\n"
            msg += f"└ Replicate minimo: €{replicate_minimo}\n\n"
        
        msg += "💡 <i>Valores estimados. Custo real depende do mix de modelos usados.</i>"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "settings":
        # Configurações
        if not is_super_admin(user_id):
            bot.answer_callback_query(call.id, "Acesso negado!")
            return
        msg = "⚙️ <b>CONFIGURAÇÕES</b>\n\n"
        msg += f"🤖 Bot Token: <code>{BOT_TOKEN[:20]}...</code>\n"
        msg += f"👑 Super Admin: {len(SUPER_ADMIN_IDS)}\n"
        msg += f"👤 Admins Secundarios: {len(ADMIN_IDS) - len(SUPER_ADMIN_IDS)}\n"
        msg += f"💬 Suporte: {SUPORTE_TELEGRAM}\n\n"
        msg += "<i>Para editar configurações, modifique o código</i>"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "manage_admins":
        # Gerir admins secundarios - SO super admin
        if not is_super_admin(user_id):
            bot.answer_callback_query(call.id, "Apenas o admin principal!")
            return
        
        secondary = load_secondary_admins()
        msg = "👑 <b>GERIR ADMINISTRADORES</b>\n\n"
        msg += f"👑 Admin principal: <code>{SUPER_ADMIN_IDS[0]}</code>\n"
        msg += f"👤 Admins secundarios: {len(secondary)}\n\n"
        
        if secondary:
            msg += "<b>Lista de admins secundarios:</b>\n\n"
            for uid, info in secondary.items():
                msg += f"👤 {info.get('name', 'N/A')} (@{info.get('username', 'N/A')})\n"
                msg += f"🆔 <code>{uid}</code>\n"
                msg += f"📅 Desde: {info.get('added_at', 'N/A')[:10]}\n\n"
        else:
            msg += "<i>Nenhum admin secundario adicionado.</i>\n\n"
        
        msg += "➕ Para adicionar: encaminhe uma mensagem do usuario e depois use o botao abaixo\n"
        msg += "Ou use: <code>/addadmin ID_DO_USUARIO</code>"
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Adicionar Admin (por ID)", callback_data="admin_add_secondary"),
        )
        if secondary:
            for uid in secondary:
                info = secondary[uid]
                markup.add(
                    telebot.types.InlineKeyboardButton(f"🗑️ Remover {info.get('name', uid)}", callback_data=f"admin_remove_{uid}")
                )
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "add_secondary":
        if not is_super_admin(user_id):
            return
        admin_states[user_id] = "awaiting_admin_id"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "➕ <b>Adicionar Admin Secundario</b>\n\nDigite o ID do usuario:", parse_mode='HTML')
    
    elif action.startswith("remove_"):
        if not is_super_admin(user_id):
            return
        target_id = action.replace("remove_", "")
        if remove_secondary_admin(int(target_id)):
            bot.answer_callback_query(call.id, "Admin removido!")
            try:
                bot.send_message(int(target_id), "⚠️ Voce foi removido como administrador do Remake Pixel.")
            except:
                pass
        # Recarregar painel
        msg = "✅ Admin removido! Clique em Voltar."
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_manage_admins"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif action == "toggle_pause":
        # 🆕 Pausar/Despausar Bot
        global bot_paused, pause_message
        bot_paused = not bot_paused
        
        if bot_paused:
            msg = "⏸️ <b>BOT PAUSADO!</b>\n\n"
            msg += "✅ Bot em modo manutenção\n"
            msg += "📢 Todos os usuários serão notificados\n\n"
            msg += f"💬 Mensagem:\n<code>{pause_message}</code>"
            
            # Notificar todos os usuários
            try:
                data = load_json(CREDITS_FILE)
                for user_id_str in data.keys():
                    try:
                        bot.send_message(int(user_id_str), pause_message)
                    except:
                        pass
            except:
                pass
        else:
            msg = "▶️ <b>BOT DESPAUSADO!</b>\n\n"
            msg += "✅ Bot voltou ao normal\n"
            msg += "📢 Usuários podem usar normalmente"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "security":
        # 🆕 Segurança
        msg = "🔒 <b>SEGURANÇA E PROTEÇÕES</b>\n\n"
        msg += "✅ <b>Ativo:</b>\n"
        msg += "• Rate limiting (5 imgs/min, 30 msgs/min)\n"
        msg += "• Validação de créditos\n"
        msg += "• Lock em arquivos JSON\n"
        msg += "• Backup automático desativado\n"
        msg += "• Proteção contra comandos inválidos\n\n"
        msg += "🛡️ <b>Recomendações:</b>\n"
        msg += "• Mantenha tokens seguros\n"
        msg += "• Monitore logs regularmente\n"
        msg += "• Revise lista de admins\n"
        msg += "• Backup manual periódico"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action == "advanced":
        # 🆕 Configurações Avançadas
        msg = "⚙️ <b>CONFIGURAÇÕES AVANÇADAS</b>\n\n"
        msg += f"🔧 <b>Status:</b>\n"
        msg += f"• Bot pausado: {'✅ Sim' if bot_paused else '❌ Não'}\n"
        msg += f"• Usuários ativos: {len(load_json(CREDITS_FILE))}\n"
        msg += f"• Wizard ativo: {len(wizard_states)}\n"
        msg += f"• Rate limiter ativo: ✅\n\n"
        msg += "💡 <b>Ações disponíveis:</b>\n"
        msg += "• Pausar/despausar bot\n"
        msg += "• Ver ngrok URL\n"
        msg += "• Monitorar segurança\n"
        msg += "• Broadcast para todos"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action.startswith("users_page_"):
        # Navegação de páginas
        page = int(action.replace("users_page_", ""))
        msg = f"👥 <b>USUÁRIOS CADASTRADOS</b>\n\nPágina {page + 1}\n\nSelecione um usuário:"
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=users_list_keyboard(page), parse_mode='HTML')
    
    elif action.startswith("select_user_"):
        # Usuário selecionado para dar créditos
        selected_user_id = action.replace("select_user_", "")
        
        msg = f"💳 <b>DAR CRÉDITOS</b>\n\n"
        msg += f"👤 Usuário: <code>{selected_user_id}</code>\n\n"
        msg += "Selecione a quantidade de créditos para adicionar:"
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=credit_amounts_keyboard(selected_user_id), parse_mode='HTML')
    
    elif action.startswith("add_"):
        # Adicionar créditos
        parts = action.replace("add_", "").split("_")
        target_user_id = int(parts[0])
        amount = int(parts[1])
        
        # Adicionar créditos
        new_total = add_credits(target_user_id, amount, "admin")
        
        msg = f"✅ <b>CRÉDITOS ADICIONADOS!</b>\n\n"
        msg += f"👤 Usuário: <code>{target_user_id}</code>\n"
        msg += f"➕ Adicionado: <code>{amount}</code> créditos\n"
        msg += f"💳 Novo total: <code>{new_total}</code> créditos\n\n"
        msg += "✨ Usuário notificado!"
        
        # Notificar usuário
        try:
            bot.send_message(target_user_id, 
                           f"🎁 <b>VOCÊ RECEBEU CRÉDITOS!</b>\n\n"
                           f"➕ <code>{amount}</code> créditos adicionados\n"
                           f"💳 Novo saldo: <code>{new_total}</code>\n\n"
                           f"✨ Aproveite para criar imagens incríveis!",
                           parse_mode='HTML')
        except:
            pass
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Dar mais créditos", callback_data="admin_give_credits"),
            telebot.types.InlineKeyboardButton("◀️ Painel", callback_data="admin_panel")
        )
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')
    
    elif action.startswith("custom_"):
        # Quantidade personalizada
        target_user_id = action.replace("custom_", "")
        admin_states[user_id] = f"awaiting_custom_amount_{target_user_id}"
        
        msg = f"✏️ <b>QUANTIDADE PERSONALIZADA</b>\n\n"
        msg += f"👤 Usuário: <code>{target_user_id}</code>\n\n"
        msg += "Digite a quantidade de créditos que deseja adicionar:\n\n"
        msg += "<i>Exemplo: 250</i>"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="admin_panel"))
        
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, 
                            reply_markup=markup, parse_mode='HTML')

# ==================== COMANDOS ====================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Sem username"
    first_name = message.from_user.first_name or "Usuário"
    user_states.pop(user_id, None)
    wizard_states.pop(user_id, None)
    
    # Verificar se é novo usuário para notificar admin
    is_new_user = False
    credits_data = load_json(CREDITS_FILE)
    if str(user_id) not in credits_data:
        is_new_user = True
        # Notificar admin sobre novo usuário
        notify_admin(
            f"👤 <b>NOVO USUÁRIO!</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Nome: {first_name}\n"
            f"📱 Username: @{username}\n"
            f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "info"
        )
    
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        
        if param.startswith('ref_'):
            code = param.replace('ref_', '')
            try:
                referrer_id = int(base64.b64decode(code.encode()).decode())
                if referrer_id != user_id:
                    success, msg = process_referral(referrer_id, user_id)
                    if success:
                        # NAO dar creditos agora - so quando o amigo COMPRAR 5EUR+
                        try:
                            bot.send_message(referrer_id, 
                                "🎁 <b>Alguem usou seu link!</b>\n\n"
                                "Voce recebera <b>10 créditos grátis</b> quando essa pessoa fizer uma compra de pelo menos 5EUR!",
                                parse_mode='HTML')
                        except:
                            pass
            except:
                pass
        
        elif param.startswith('view_'):
            share_id = param.replace('view_', '')
            shared = get_shared_creation(share_id)
            if shared:
                try:
                    bot.send_photo(message.chat.id, shared['url'], 
                                 caption=f"🔗 <b>Criação Compartilhada</b>\n\n{shared['prompt']}\n\n👁️ Views: {shared['views']}", 
                                 parse_mode='HTML')
                except:
                    pass
    
    logger.info(f"User {user_id} iniciou {'(NOVO)' if is_new_user else ''}")
    
    # /start SEMPRE mostra idioma e onboarding
    bot.send_message(
        message.chat.id, 
        "🌍 <b>Welcome! / Bem-vindo!</b>\n\nChoose language:", 
        reply_markup=language_keyboard(), 
        parse_mode='HTML'
    )
    
    # Enviar teclado fixo inferior (Reply Keyboard)
    bot.send_message(
        message.chat.id,
        "👇 Use os botões abaixo para acessar o menu:",
        reply_markup=get_main_reply_keyboard(user_id)
    )

@bot.message_handler(commands=['idioma', 'lang', 'language'])
def cmd_idioma(message):
    bot.send_message(message.chat.id, "🌍 <b>Choose:</b>", reply_markup=language_keyboard(), parse_mode='HTML')

@bot.message_handler(commands=['creditos', 'credits'])
def cmd_creditos(message):
    user_id = message.from_user.id
    creditos = get_user_credits(user_id)
    bot.send_message(message.chat.id, f"💳 <code>{creditos}</code> créditos", parse_mode='HTML')

@bot.message_handler(commands=['wizard'])
def cmd_wizard(message):
    """Assistente de criação guiado"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    question = start_wizard(user_id, lang)
    user_states[user_id] = "in_wizard"
    bot.send_message(message.chat.id, f"🧙 <b>Assistente de Criação</b>\n\n{question}", reply_markup=cancel_keyboard(lang), parse_mode='HTML')

@bot.message_handler(commands=['help', 'ajuda'])
def cmd_help(message):
    bot.send_message(message.chat.id, "❓ Use /start para o menu")

@bot.message_handler(commands=['termos', 'terms', 'tos'])
def cmd_termos(message):
    """Termos de uso e disclaimer"""
    lang = get_user_lang(message.from_user.id)
    terms = {
        "pt": ("📋 <b>TERMOS DE USO - Remake Pixel</b>\n\n"
               "<b>1. Servico</b>\n"
               "O Remake Pixel e um bot de geracao e edicao de imagens usando inteligencia artificial.\n\n"
               "<b>2. Responsabilidade</b>\n"
               "O usuario e inteiramente responsavel pelo conteudo que gera. O Remake Pixel nao se responsabiliza por imagens criadas pelos usuarios.\n\n"
               "<b>3. Creditos</b>\n"
               "Creditos comprados NAO sao reembolsaveis. Os creditos sao consumidos ao gerar/editar imagens.\n\n"
               "<b>4. Uso Proibido</b>\n"
               "E proibido usar o bot para:\n"
               "• Gerar conteudo ilegal\n"
               "• Difamacao ou assedio\n"
               "• Violacao de direitos autorais\n"
               "• Qualquer atividade ilicita\n\n"
               "<b>5. Privacidade</b>\n"
               "Armazenamos apenas dados necessarios para o funcionamento (ID, creditos, historico). Fotos enviadas sao processadas e NAO armazenadas.\n\n"
               "<b>6. Denuncias</b>\n"
               "Denuncias falsas ou abusivas resultarao em banimento permanente.\n\n"
               "<b>7. Modificacoes</b>\n"
               "Reservamos o direito de modificar o servico a qualquer momento.\n\n"
               f"📞 Suporte: {SUPORTE_TELEGRAM}"),
        "en": ("📋 <b>TERMS OF USE - Remake Pixel</b>\n\n"
               "By using Remake Pixel you agree: user is responsible for all generated content, credits are non-refundable, prohibited to generate illegal content.\n\n"
               f"Support: {SUPORTE_TELEGRAM}"),
    }
    bot.send_message(message.chat.id, terms.get(lang, terms["pt"]), parse_mode='HTML')

@bot.message_handler(commands=['reiniciar', 'restart', 'reset'])
def cmd_reiniciar(message):
    """Reinicia o bot para o usuário (limpa histórico e estado)"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # Limpar estados e contextos
    user_states.pop(user_id, None)
    chat_contexts.pop(user_id, None)
    
    texts = {
        "pt": "🔄 Bot reiniciado com sucesso!\n\nSeu histórico de chat foi limpo. Use /start para ver o menu principal.",
        "en": "🔄 Bot restarted successfully!\n\nYour chat history has been cleared. Use /start to see the main menu.",
        "es": "🔄 ¡Bot reiniciado con éxito!\n\nTu historial de chat ha sido limpiado. Usa /start para ver el menú principal."
    }
    
    bot.reply_to(message, texts.get(lang, texts["pt"]))
    logger.info(f"Usuário {user_id} reiniciou o bot")

@bot.message_handler(commands=['aceitar'])
def cmd_aceitar(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            # Mostrar pedidos pendentes para facilitar
            pending = load_json(PENDING_FILE)
            pending_list = [k for k, v in pending.items() if v.get('status') == 'pendente']
            if pending_list:
                msg = "⚠️ <b>Use:</b> /aceitar ID\n\n<b>Pedidos pendentes:</b>\n\n"
                for req_id in pending_list[:5]:
                    req = pending[req_id]
                    msg += f"👤 {req.get('first_name', 'N/A')} (@{req.get('username', 'N/A')})\n"
                    msg += f"📦 {req['pacote_nome']}\n"
                    msg += f"➡️ <code>/aceitar {req_id}</code>\n\n"
                bot.reply_to(message, msg, parse_mode='HTML')
            else:
                bot.reply_to(message, "✅ Nenhum pedido pendente!")
            return
        request_id = parts[1]
        pending = load_json(PENDING_FILE)
        if request_id not in pending or pending[request_id]['status'] != 'pendente':
            bot.reply_to(message, "❌ Pedido nao encontrado ou ja processado!")
            return
        sol = pending[request_id]
        pacote = PACOTES[sol['pacote_id']]
        checkout = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"Remake Pixel - {pacote['nome']}"},
                    'unit_amount': pacote['preco']
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
            metadata={
                'user_id': str(sol['user_id']),
                'creditos': str(pacote['creditos']),
                'pacote_nome': pacote['nome']
            }
        )
        pending[request_id]['status'] = 'aprovada'
        save_json(PENDING_FILE, pending, PENDING_LOCK)
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("💳 Pagar", url=checkout.url))
        first_name = sol.get('first_name', 'Usuario')
        bot.send_message(sol['user_id'], f"✅ <b>Compra aprovada!</b>\n\n📦 {pacote['nome']}\n💶 €{pacote['preco']/100:.2f}\n\nClique para pagar:", reply_markup=markup, parse_mode='HTML')
        bot.reply_to(message, f"✅ Link enviado para {first_name} (@{sol.get('username', 'N/A')})!")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {e}")
        logger.error(f"Erro ao aceitar compra: {e}")

@bot.message_handler(commands=['addcreditos'])
def cmd_add(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        if len(parts) >= 3:
            novo = add_credits(int(parts[1]), int(parts[2]), "admin")
            bot.reply_to(message, f"✅ Total: {novo}")
    except:
        pass

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = load_json(CREDITS_FILE)
    bot.reply_to(message, f"📊 Usuários: {len(data)}")

@bot.message_handler(commands=['painel', 'admin', 'panel'])
def cmd_painel(message):
    """Painel de Controle Administrativo"""
    user_id = message.from_user.id
    
    if not is_any_admin(user_id):
        bot.reply_to(message, "❌ Acesso negado! Comando exclusivo para administradores.")
        return
    
    if is_super_admin(user_id):
        msg = "🎛️ <b>PAINEL DE CONTROLE</b> 👑\n\n"
        msg += "Admin Principal - Acesso Total\n\n"
        msg += "Use os botoes abaixo para gerenciar o bot:"
    else:
        msg = "🎛️ <b>PAINEL ADMIN SECUNDARIO</b>\n\n"
        msg += "Acesso limitado: Estatísticas, Broadcast, Financeiro"
    
    bot.send_message(message.chat.id, msg, reply_markup=admin_panel_keyboard(user_id), parse_mode='HTML')
    logger.info(f"Admin {user_id} acessou o painel")

@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "").startswith('awaiting_broadcast'))
def handle_broadcast(message):
    """Handler para broadcast"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    admin_states.pop(user_id, None)
    broadcast_msg = message.text.strip()
    
    # Enviar para todos os usuários
    data = load_json(CREDITS_FILE)
    total = len(data)
    success = 0
    failed = 0
    
    status_msg = bot.reply_to(message, f"📢 Enviando broadcast para {total} usuários...")
    
    for user_id_str in data.keys():
        try:
            bot.send_message(int(user_id_str), 
                           f"📢 <b>MENSAGEM DO ADMINISTRADOR</b>\n\n{broadcast_msg}", 
                           parse_mode='HTML')
            success += 1
        except:
            failed += 1
        
        # Atualizar status a cada 10 usuários
        if (success + failed) % 10 == 0:
            try:
                bot.edit_message_text(
                    f"📢 Enviando... {success + failed}/{total}\n✅ {success} enviados\n❌ {failed} falhas",
                    status_msg.chat.id,
                    status_msg.message_id
                )
            except:
                pass
    
    # Resultado final
    result_msg = f"✅ <b>BROADCAST CONCLUÍDO!</b>\n\n"
    result_msg += f"📊 Total: {total} usuários\n"
    result_msg += f"✅ Enviados: {success}\n"
    result_msg += f"❌ Falhas: {failed}\n\n"
    result_msg += f"📈 Taxa de sucesso: {(success/total*100):.1f}%"
    
    bot.edit_message_text(result_msg, status_msg.chat.id, status_msg.message_id, parse_mode='HTML')
    logger.info(f"Broadcast realizado: {success}/{total} enviados")

@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "") == 'awaiting_admin_id')
def handle_add_admin(message):
    """Handler para adicionar admin secundario"""
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        return
    admin_states.pop(user_id, None)
    
    try:
        target_id = int(message.text.strip())
        if target_id in SUPER_ADMIN_IDS:
            bot.reply_to(message, "❌ Este ja e o admin principal!")
            return
        
        # Tentar obter info do usuario
        try:
            chat_info = bot.get_chat(target_id)
            name = chat_info.first_name or "N/A"
            username = chat_info.username or "sem_username"
        except:
            name = "Desconhecido"
            username = "sem_username"
        
        add_secondary_admin(target_id, name, username)
        
        bot.reply_to(message, f"✅ <b>Admin adicionado!</b>\n\n👤 {name} (@{username})\n🆔 <code>{target_id}</code>\n\nEste usuario agora pode ver estatísticas, broadcast e financeiro.", parse_mode='HTML')
        
        try:
            bot.send_message(target_id, "👑 <b>Voce foi adicionado como administrador do Remake Pixel!</b>\n\nUse /painel para acessar o painel.", parse_mode='HTML')
        except:
            pass
        
        logger.info(f"Admin secundario adicionado: {target_id} ({name})")
    except ValueError:
        bot.reply_to(message, "❌ ID invalido! Digite apenas numeros.")

@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "").startswith('awaiting_custom_amount_'))
def handle_custom_amount(message):
    """Handler para quantidade personalizada de créditos"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    state = admin_states.pop(user_id, "")
    target_user_id = int(state.replace("awaiting_custom_amount_", ""))
    
    try:
        amount = int(message.text.strip())
        
        if amount <= 0:
            bot.reply_to(message, "❌ A quantidade deve ser maior que zero!")
            return
        
        if amount > 100000:
            bot.reply_to(message, "❌ Quantidade muito alta! Máximo: 100.000 créditos")
            return
        
        # Adicionar créditos
        new_total = add_credits(target_user_id, amount, "admin")
        
        msg = f"✅ <b>CRÉDITOS ADICIONADOS!</b>\n\n"
        msg += f"👤 Usuário: <code>{target_user_id}</code>\n"
        msg += f"➕ Adicionado: <code>{amount}</code> créditos\n"
        msg += f"💳 Novo total: <code>{new_total}</code> créditos\n\n"
        msg += "✨ Usuário notificado!"
        
        # Notificar usuário
        try:
            bot.send_message(target_user_id, 
                           f"🎁 <b>VOCÊ RECEBEU CRÉDITOS!</b>\n\n"
                           f"➕ <code>{amount}</code> créditos adicionados pelo administrador\n"
                           f"💳 Novo saldo: <code>{new_total}</code>\n\n"
                           f"✨ Aproveite para criar imagens incríveis!",
                           parse_mode='HTML')
        except:
            pass
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Dar mais créditos", callback_data="admin_give_credits"),
            telebot.types.InlineKeyboardButton("◀️ Painel", callback_data="admin_panel")
        )
        
        bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode='HTML')
        logger.info(f"Admin adicionou {amount} créditos para user {target_user_id}")
        
    except ValueError:
        bot.reply_to(message, "❌ Digite apenas números!\n\nExemplo: 250")

@bot.message_handler(func=lambda m: m.text == "📋 Menu")
def handle_menu_button(message):
    """Handler para o botão Menu fixo"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    show_main_menu(message.chat.id, user_id, lang)

@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    """Comando /menu - mostra menu sem reiniciar"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    show_main_menu(message.chat.id, user_id, lang)


# ==================== HANDLER DE FOTOS (MELHORADO) ====================
# Sistema para coletar múltiplas fotos
photo_collections = {}  # {user_id: {"photos": [...], "caption": "...", "timestamp": ...}}
processed_media_groups = set()  # Evitar processar o mesmo grupo duas vezes

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Handler para processar fotos enviadas pelo usuario - Suporta 1-5 fotos"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    caption = message.caption or ""
    
    # BLOQUEAR se onboarding não completo
    if not is_onboarded(user_id):
        bot.reply_to(message, "👋 Envie /start para começar!")
        return
    
    # Se usuario esta a esperar imagem para video, redirecionar
    if user_states.get(user_id) == 'awaiting_video_image':
        handle_video_image(message)
        return
    
    # Se usuario esta no wizard, redirecionar foto como referencia
    if user_states.get(user_id) == 'in_wizard':
        handle_wizard(message)
        return
    
    # Se tem media_group_id, sao multiplas fotos enviadas juntas
    if message.media_group_id:
        mg_id = message.media_group_id
        
        # Ignorar se este grupo ja foi processado
        if mg_id in processed_media_groups:
            return
        
        # Inicializar colecao se nao existir
        if user_id not in photo_collections or photo_collections[user_id].get("media_group_id") != mg_id:
            photo_collections[user_id] = {
                "photos": [],
                "caption": caption if caption else "",
                "media_group_id": mg_id,
                "timestamp": time.time(),
                "processing": False
            }
        
        # Adicionar foto a colecao
        photo_collections[user_id]["photos"].append(message.photo[-1].file_id)
        
        # Guardar caption se vier com alguma foto
        if caption and not photo_collections[user_id]["caption"]:
            photo_collections[user_id]["caption"] = caption
        
        # Limite maximo de 5 fotos
        if len(photo_collections[user_id]["photos"]) > 5:
            return
        
        # Processar imediatamente se ja tem 5
        if len(photo_collections[user_id]["photos"]) >= 5:
            if not photo_collections[user_id].get("processing", False):
                photo_collections[user_id]["processing"] = True
                processed_media_groups.add(mg_id)
                Thread(target=process_multiple_photos, args=(user_id, lang, photo_collections[user_id]["caption"])).start()
        else:
            # Aguardar mais fotos - so iniciar timer na PRIMEIRA foto
            if len(photo_collections[user_id]["photos"]) == 1:
                def delayed_process(uid, lng, mgid):
                    time.sleep(4)
                    if uid in photo_collections and not photo_collections[uid].get("processing", False) and photo_collections[uid].get("media_group_id") == mgid:
                        photo_collections[uid]["processing"] = True
                        processed_media_groups.add(mgid)
                        cap = photo_collections[uid].get("caption", "")
                        if len(photo_collections[uid]["photos"]) > 1:
                            process_multiple_photos(uid, lng, cap)
                        else:
                            photo_collections.pop(uid, None)
                
                Thread(target=delayed_process, args=(user_id, lang, mg_id)).start()
        return
    
    # Foto unica - mostrar opcoes de modelo
    # Guardar foto temporariamente para processar depois
    pending_photos[user_id] = {
        "file_id": message.photo[-1].file_id,
        "caption": caption,
        "chat_id": message.chat.id,
        "timestamp": time.time()
    }
    
    creditos = get_user_credits(user_id)
    
    # Se tem legenda, ir direto para edicao padrao
    if caption and len(caption.strip()) >= 3:
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        texts = {
            "pt": f"📸 <b>Foto recebida!</b>\n\n💬 Descrição: <i>{caption[:80]}</i>\n\n<b>Escolha o modelo:</b>\n\n🎨 <b>Padrão</b> (1 cred) — Edita conforme descrição\n✨ <b>Pro</b> (3 cred) — Melhoria fotorrealista automática\n🎭 <b>Artístico</b> (2 cred) — Transforma em estilos artísticos\n\n💳 Créditos: <code>{creditos}</code>",
            "en": f"📸 <b>Photo received!</b>\n\n💬 Description: <i>{caption[:80]}</i>\n\n<b>Choose model:</b>\n\n🎨 <b>Standard</b> (1 cred) — Edits by description\n✨ <b>Pro</b> (3 cred) — Auto photorealistic enhancement\n🎭 <b>Artistic</b> (2 cred) — Transform to art styles\n\n💳 Credits: <code>{creditos}</code>",
            "es": f"📸 <b>Foto recibida!</b>\n\n💬 Descripción: <i>{caption[:80]}</i>\n\n<b>Elige modelo:</b>\n\n🎨 <b>Estándar</b> (1 cred) — Edita según descripción\n✨ <b>Pro</b> (3 cred) — Mejora fotorrealista automática\n🎭 <b>Artístico</b> (2 cred) — Transforma en estilos artísticos\n\n💳 Créditos: <code>{creditos}</code>"
        }
        markup.add(
            telebot.types.InlineKeyboardButton("🎨 Padrao - 1 credito", callback_data="photo_model_padrao"),
            telebot.types.InlineKeyboardButton("✨ Pro - 3 creditos", callback_data="photo_model_pro"),
            telebot.types.InlineKeyboardButton("🎭 Artistico - 2 creditos", callback_data="photo_model_artistico"),
            telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="photo_model_cancel")
        )
        bot.reply_to(message, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
    else:
        # Sem legenda - mostrar opcoes com explicacao
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        texts = {
            "pt": f"📸 <b>Foto recebida!</b>\n\n<b>Escolha como deseja editar:</b>\n\n🎨 <b>Modelo Padrao</b> (1 credito)\nVocê descreve o que quer mudar\n\n✨ <b>Modelo Pro</b> (3 creditos)\nMelhoria fotorrealista automática\n\n🎭 <b>Modelo Artistico</b> (2 creditos)\nTransforma em anime, Disney, cyberpunk e mais!\n\n💳 Seus créditos: <code>{creditos}</code>\n\n💡 <b>Dica:</b> Envie 2-5 fotos juntas para combina-las!",
            "en": f"📸 <b>Photo received!</b>\n\n<b>Choose how to edit:</b>\n\n🎨 <b>Standard Model</b> (1 credit)\nYou describe what to change\n\n✨ <b>Pro Model</b> (3 credits)\nAutomatic photorealistic enhancement\n\n🎭 <b>Artistic Model</b> (2 credits)\nTransform to anime, Disney, cyberpunk and more!\n\n💳 Your credits: <code>{creditos}</code>\n\n💡 <b>Tip:</b> Send 2-5 photos together to combine them!",
            "es": f"📸 <b>Foto recibida!</b>\n\n<b>Elige como editar:</b>\n\n🎨 <b>Modelo Estandar</b> (1 credito)\nTu describes lo que quieres cambiar\n\n✨ <b>Modelo Pro</b> (3 creditos)\nMejora fotorrealista automatica\n\n🎭 <b>Modelo Artistico</b> (2 creditos)\nTransforma en anime, Disney, cyberpunk y mas!\n\n💳 Tus créditos: <code>{creditos}</code>\n\n💡 <b>Consejo:</b> Envia 2-5 fotos juntas para combinarlas!"
        }
        markup.add(
            telebot.types.InlineKeyboardButton("🎨 Padrao - 1 credito", callback_data="photo_model_padrao"),
            telebot.types.InlineKeyboardButton("✨ Pro - 3 creditos", callback_data="photo_model_pro"),
            telebot.types.InlineKeyboardButton("🎭 Artistico - 2 creditos", callback_data="photo_model_artistico"),
            telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="photo_model_cancel")
        )
        bot.reply_to(message, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')

# ==================== HANDLERS DE MODELO DE FOTO ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('terms_'))
def callback_terms(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('terms_', '')
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    if action == "accept":
        bot.send_message(call.message.chat.id, "🎨 <b>Bem-vindo ao Remake Pixel!</b>\n\nSou o seu assistente criativo com IA. Posso gerar imagens do zero, editar fotos, transformar em anime, arte digital e muito mais.\n\nVamos comecar!", parse_mode='HTML')
        time.sleep(1)
        show_main_menu(call.message.chat.id, user_id, lang)
    else:
        bot.send_message(call.message.chat.id, "❌ Termos recusados. Envie /start para tentar novamente.")

# ==================== PRESETS MODELO PADRAO ====================
PRESETS_PADRAO = {
    "default": {"nome": "✍️ Personalizado", "prompt": ""},
    "enhance": {"nome": "✨ Melhorar Qualidade", "prompt": "enhance image quality, sharpen details, improve colors, professional photography"},
    "bg_remove": {"nome": "🔲 Remover Fundo", "prompt": "remove background, isolate subject, clean transparent background"},
    "portrait": {"nome": "📷 Retrato Pro", "prompt": "professional portrait photography, studio lighting, bokeh background"},
    "3d_model": {"nome": "🎮 Modelo 3D", "prompt": "transform into 3D game character model, Unreal Engine 5 render, AAA quality"},
    "manipulation": {"nome": "🌸 Manipulação", "prompt": "creative photo manipulation, artistic composite, dreamy surreal environment"},
    "cinematic": {"nome": "🎬 Cinematográfico", "prompt": "cinematic movie still, dramatic lighting, film color grading"},
}

@bot.callback_query_handler(func=lambda call: call.data.startswith('quick_approve_'))
def callback_quick_approve(call):
    """Aprovacao rapida de compra com um clique"""
    user_id = call.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    request_id = call.data.replace('quick_approve_', '')
    pending = load_json(PENDING_FILE)
    
    if request_id not in pending or pending[request_id].get('status') != 'pendente':
        bot.answer_callback_query(call.id, "Pedido ja processado!")
        try:
            bot.edit_message_text("✅ Pedido ja foi processado!", call.message.chat.id, call.message.message_id)
        except:
            pass
        return
    
    try:
        sol = pending[request_id]
        pacote = PACOTES[sol['pacote_id']]
        checkout = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"Remake Pixel - {pacote['nome']}"},
                    'unit_amount': pacote['preco']
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
            metadata={
                'user_id': str(sol['user_id']),
                'creditos': str(pacote['creditos']),
                'pacote_nome': pacote['nome']
            }
        )
        pending[request_id]['status'] = 'aprovada'
        save_json(PENDING_FILE, pending, PENDING_LOCK)
        
        # Enviar link ao usuario
        markup_pay = telebot.types.InlineKeyboardMarkup()
        markup_pay.add(telebot.types.InlineKeyboardButton("💳 Pagar", url=checkout.url))
        first_name = sol.get('first_name', 'Usuario')
        bot.send_message(sol['user_id'], f"✅ <b>Compra aprovada!</b>\n\n📦 {pacote['nome']}\n💶 €{pacote['preco']/100:.2f}\n\nClique para pagar:", reply_markup=markup_pay, parse_mode='HTML')
        
        # Confirmar ao admin
        bot.edit_message_text(f"✅ Aprovado! Link enviado para {first_name} (@{sol.get('username', 'N/A')})", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Aprovado!")
    
    except Exception as e:
        bot.answer_callback_query(call.id, f"Erro: {str(e)[:50]}")
        bot.edit_message_text(f"❌ Erro: {e}", call.message.chat.id, call.message.message_id)
        logger.error(f"Erro quick_approve: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('multi_model_'))
def callback_multi_model(call):
    """Handler para escolha de modelo na combinacao de multiplas fotos"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('multi_model_', '')
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    if action == "cancel":
        photo_collections.pop(user_id, None)
        bot.send_message(call.message.chat.id, "❌ Combinação cancelada.")
        return
    
    if user_id not in photo_collections:
        bot.send_message(call.message.chat.id, "❌ Fotos expiradas! Envie novamente.")
        return
    
    caption = photo_collections[user_id].get("caption", "")
    
    if action == "padrao":
        Thread(target=execute_combine_padrao, args=(user_id, lang, caption)).start()
    elif action == "pro":
        Thread(target=execute_combine_pro, args=(user_id, lang, caption)).start()
    elif action == "artistico":
        # Mostrar estilos artisticos
        markup = telebot.types.InlineKeyboardMarkup(row_width=3)
        keys = list(ESTILOS_ARTISTICOS.keys())
        for i in range(0, len(keys), 3):
            row = []
            for key in keys[i:i+3]:
                row.append(telebot.types.InlineKeyboardButton(ESTILOS_ARTISTICOS[key]["nome"], callback_data=f"multistyle_{key}"))
            markup.row(*row)
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="multi_model_cancel"))
        bot.send_message(call.message.chat.id, "🎭 <b>Escolha o estilo:</b>", reply_markup=markup, parse_mode='HTML')
    
    elif action == "carousel":
        # Carrossel - pedir prompt para gerar imagens em sequencia
        if user_id not in photo_collections:
            bot.send_message(call.message.chat.id, "❌ Fotos expiradas!")
            return
        
        num_photos = len(photo_collections[user_id]["photos"])
        creditos = get_user_credits(user_id)
        custo = num_photos
        
        if creditos < custo:
            bot.send_message(call.message.chat.id, f"❌ Créditos insuficientes! Precisa de {custo} créditos ({num_photos} fotos).")
            photo_collections.pop(user_id, None)
            return
        
        # Guardar que e carousel e pedir prompt
        user_states[user_id] = "awaiting_carousel_prompt"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Mostrar estilos para escolher
        markup = telebot.types.InlineKeyboardMarkup(row_width=3)
        styles_carousel = {
            "livre": "Livre", "anime": "Anime", "disney_3d": "Disney 3D",
            "comic": "Comic", "cyberpunk": "Cyberpunk", "digital_art": "Digital Art",
            "watercolor": "Watercolor", "pop_art": "Pop Art", "vintage": "Vintage"
        }
        row = []
        for key, nome in styles_carousel.items():
            row.append(telebot.types.InlineKeyboardButton(nome, callback_data=f"carousel_style_{key}"))
            if len(row) == 3:
                markup.row(*row)
                row = []
        if row:
            markup.row(*row)
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="carousel_style_cancel"))
        
        bot.send_message(call.message.chat.id, 
            f"📱 <b>Carrossel ({num_photos} slides)</b>\n"
            f"💳 Custo: {custo} créditos\n\n"
            f"Escolha o estilo visual:",
            reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('carousel_num_'))
def callback_carousel_num(call):
    """Escolha do número de slides do carrossel"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    num = call.data.replace('carousel_num_', '')
    
    if num == "cancel":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return
    
    num_slides = int(num)
    creditos = get_user_credits(user_id)
    if creditos < num_slides:
        bot.answer_callback_query(call.id, "Créditos insuficientes!")
        return
    
    # Guardar estado do carrossel
    carousel_states[user_id] = {
        "num_slides": num_slides,
        "current_slide": 1,
        "descriptions": [],
        "style": "livre"
    }
    
    # Mostrar estilos
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    styles_list = [
        ("livre", "Livre"), ("anime", "Anime"), ("disney_3d", "Disney 3D"),
        ("comic", "Comic"), ("cyberpunk", "Cyberpunk"), ("digital_art", "Digital Art"),
        ("watercolor", "Watercolor"), ("pop_art", "Pop Art"), ("vintage", "Vintage")
    ]
    row = []
    for key, nome in styles_list:
        row.append(telebot.types.InlineKeyboardButton(nome, callback_data=f"cstyle_{key}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    
    bot.send_message(call.message.chat.id, f"📱 <b>Carrossel de {num_slides} slides</b>\n\nEscolha o estilo:", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('cstyle_'))
def callback_cstyle(call):
    """Estilo do carrossel escolhido - iniciar questionário"""
    user_id = call.from_user.id
    style = call.data.replace('cstyle_', '')
    
    if user_id not in carousel_states:
        bot.answer_callback_query(call.id, "Sessão expirada!")
        return
    
    carousel_states[user_id]["style"] = style
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    user_states[user_id] = "carousel_describing"
    bot.send_message(call.message.chat.id, 
        f"📱 <b>Slide 1 de {carousel_states[user_id]['num_slides']}</b>\n\n"
        f"Descreva o que deve aparecer no <b>slide 1</b>:",
        parse_mode='HTML')

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'carousel_describing')
def handle_carousel_description(message):
    """Recolhe descrição de cada slide"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    if user_id not in carousel_states:
        user_states.pop(user_id, None)
        bot.reply_to(message, "❌ Sessão expirada!")
        return
    
    state = carousel_states[user_id]
    state["descriptions"].append(message.text.strip())
    state["current_slide"] += 1
    
    if state["current_slide"] <= state["num_slides"]:
        # Pedir próximo slide
        bot.reply_to(message, 
            f"📱 <b>Slide {state['current_slide']} de {state['num_slides']}</b>\n\n"
            f"Descreva o que deve aparecer no <b>slide {state['current_slide']}</b>:",
            parse_mode='HTML')
    else:
        # Todas as descrições recolhidas - gerar!
        user_states.pop(user_id, None)
        num_slides = state["num_slides"]
        
        creditos = get_user_credits(user_id)
        if creditos < num_slides:
            bot.reply_to(message, "❌ Créditos insuficientes!")
            carousel_states.pop(user_id, None)
            return
        
        if not use_credit(user_id, num_slides):
            carousel_states.pop(user_id, None)
            return
        
        proc_msg = bot.reply_to(message, f"📱 Gerando {num_slides} slides...\nIsto pode demorar.")
        
        try:
            style_suffix = VISUAL_STYLES.get(state["style"], VISUAL_STYLES["livre"])["suffix"]
            
            style_settings = get_user_style_settings(user_id)
            aspect_ratio = style_settings.get("aspect_ratio", "square")
            if aspect_ratio not in ASPECT_RATIOS:
                aspect_ratio = "square"
            ratio = ASPECT_RATIOS[aspect_ratio]["ratio"]
            
            # Gerar cada slide com a descrição do utilizador
            media_group = []
            for i, desc in enumerate(state["descriptions"]):
                try:
                    slide_prompt = improve_prompt_auto(f"Slide {i+1} of {num_slides} Instagram carousel: {desc}. Consistent visual style, connected composition")
                    slide_prompt += style_suffix
                    
                    urls = gerar_imagem_modelo(slide_prompt, ratio, num_outputs=1)
                    if urls:
                        img_data = requests.get(urls[0], timeout=60).content
                        cap = f"Slide {i+1}/{num_slides}" if i == 0 else ""
                        media_group.append(telebot.types.InputMediaPhoto(img_data, caption=cap))
                        add_to_history(user_id, "create", desc, urls[0])
                except Exception as e:
                    logger.error(f"Erro slide {i+1}: {e}")
                    continue
            
            bot.delete_message(message.chat.id, proc_msg.message_id)
            
            if media_group:
                bot.send_media_group(message.chat.id, media_group)
                cred_rest = get_user_credits(user_id)
                bot.send_message(message.chat.id,
                    f"✅ <b>Carrossel gerado!</b>\n📱 {len(media_group)} slides\n💳 Créditos: <code>{cred_rest}</code>",
                    parse_mode='HTML')
                update_user_stats(user_id, "total_creations")
            else:
                add_credits(user_id, num_slides, "reembolso")
                bot.send_message(message.chat.id, "❌ Erro. Créditos reembolsados.")
        
        except Exception as e:
            add_credits(user_id, num_slides, "reembolso")
            logger.error(f"Erro carrossel: {e}")
            try:
                bot.edit_message_text("❌ Erro. Créditos reembolsados.", message.chat.id, proc_msg.message_id)
            except:
                bot.send_message(message.chat.id, "❌ Erro. Créditos reembolsados.")
        finally:
            carousel_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('carousel_style_'))
def callback_carousel_style(call):
    """Escolha de estilo para carrossel"""
    user_id = call.from_user.id
    style_key = call.data.replace('carousel_style_', '')
    
    if style_key == "cancel":
        user_states.pop(user_id, None)
        photo_collections.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "❌ Cancelado.")
        return
    
    # Guardar estilo escolhido
    if user_id not in photo_collections:
        bot.answer_callback_query(call.id, "Fotos expiradas!")
        return
    
    photo_collections[user_id]["carousel_style"] = style_key
    user_states[user_id] = "awaiting_carousel_prompt"
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    bot.send_message(call.message.chat.id, 
        "📱 <b>Carrossel</b>\n\n"
        "Escreva o tema do carrossel:\n\n"
        "<b>Exemplos:</b>\n"
        "• 'Um cão a brincar no parque'\n"
        "• 'Paisagem de montanhas nas 4 estações'\n"
        "• 'Produto cosmético em diferentes cenários'\n"
        "• 'História de amor em sequência'",
        parse_mode='HTML')

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_carousel_prompt')
def handle_carousel_prompt(message):
    """Gera carrossel de imagens em sequência"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)
    
    if user_id not in photo_collections:
        bot.reply_to(message, "❌ Sessão expirada! Envie as fotos novamente.")
        return
    
    collection = photo_collections[user_id]
    num_slides = len(collection["photos"])
    style_key = collection.get("carousel_style", "livre")
    prompt = message.text.strip()
    
    # Verificar créditos
    creditos = get_user_credits(user_id)
    if creditos < num_slides:
        bot.reply_to(message, f"❌ Créditos insuficientes! Precisa de {num_slides}.")
        photo_collections.pop(user_id, None)
        return
    
    if not use_credit(user_id, num_slides):
        photo_collections.pop(user_id, None)
        return
    
    proc_msg = bot.reply_to(message, f"📱 Gerando carrossel de {num_slides} slides...\nIsto pode demorar.")
    
    try:
        # Obter sufixo de estilo
        style_suffix = VISUAL_STYLES.get(style_key, VISUAL_STYLES["livre"])["suffix"]
        
        # Obter formato das configurações
        style_settings = get_user_style_settings(user_id)
        aspect_ratio = style_settings.get("aspect_ratio", "square")
        if aspect_ratio not in ASPECT_RATIOS:
            aspect_ratio = "square"
        ratio = ASPECT_RATIOS[aspect_ratio]["ratio"]
        
        # Usar GPT para criar prompts conectados para cada slide
        slides_prompt = f"""Create {num_slides} connected image prompts for an Instagram carousel about: "{prompt}". 
Each slide must be visually connected, like a continuous panorama or a story in sequence.
Respond with ONLY the prompts, one per line, numbered 1-{num_slides}.
Each prompt should be detailed for AI image generation. English only."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": slides_prompt}],
            max_tokens=400,
            temperature=0.8
        )
        
        slide_prompts = []
        for line in response.choices[0].message.content.strip().split('\n'):
            line = line.strip()
            if line and len(line) > 5:
                # Remover numeracao
                import re
                clean = re.sub(r'^\d+[\.\)\-:\s]+', '', line).strip()
                if clean:
                    slide_prompts.append(clean + style_suffix)
        
        # Garantir que temos o numero certo de slides
        while len(slide_prompts) < num_slides:
            slide_prompts.append(f"{prompt}, slide {len(slide_prompts)+1} of {num_slides}{style_suffix}")
        slide_prompts = slide_prompts[:num_slides]
        
        # Gerar cada slide
        media_group = []
        for i, sp in enumerate(slide_prompts):
            try:
                urls = gerar_imagem_modelo(sp, ratio, num_outputs=1)
                if urls:
                    img_data = requests.get(urls[0], timeout=60).content
                    media_group.append(telebot.types.InputMediaPhoto(img_data, caption=f"Slide {i+1}/{num_slides}" if i == 0 else ""))
                    add_to_history(user_id, "create", sp, urls[0])
            except Exception as e:
                logger.error(f"Erro slide {i+1}: {e}")
                continue
        
        bot.delete_message(message.chat.id, proc_msg.message_id)
        
        if media_group:
            bot.send_media_group(message.chat.id, media_group)
            creditos_restantes = get_user_credits(user_id)
            bot.send_message(message.chat.id, 
                f"✅ <b>Carrossel gerado!</b>\n"
                f"📱 {len(media_group)} slides\n"
                f"💳 Créditos restantes: <code>{creditos_restantes}</code>",
                parse_mode='HTML')
            update_user_stats(user_id, "total_creations")
        else:
            add_credits(user_id, num_slides, "reembolso")
            bot.send_message(message.chat.id, "❌ Erro ao gerar. Créditos reembolsados.")
    
    except Exception as e:
        add_credits(user_id, num_slides, "reembolso")
        logger.error(f"Erro carrossel: {e}")
        try:
            bot.edit_message_text("❌ Erro ao gerar carrossel. Créditos reembolsados.", message.chat.id, proc_msg.message_id)
        except:
            bot.send_message(message.chat.id, "❌ Erro. Créditos reembolsados.")
    finally:
        photo_collections.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('multistyle_'))
def callback_multi_style(call):
    """Processa combinacao multi-foto com estilo artistico"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    estilo_key = call.data.replace('multistyle_', '')
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    if user_id not in photo_collections:
        bot.send_message(call.message.chat.id, "❌ Fotos expiradas! Envie novamente.")
        return
    
    photos = photo_collections[user_id]["photos"]
    creditos = get_user_credits(user_id)
    
    if creditos < MODELO_ARTISTICO["custo"]:
        photo_collections.pop(user_id, None)
        bot.send_message(call.message.chat.id, "❌ Créditos insuficientes!")
        return
    
    if not use_credit(user_id, MODELO_ARTISTICO["custo"]):
        photo_collections.pop(user_id, None)
        return
    
    estilo = ESTILOS_ARTISTICOS.get(estilo_key, ESTILOS_ARTISTICOS["anime"])
    bot.send_message(call.message.chat.id, f"🎭 Aplicando estilo {estilo['nome']}...")
    
    try:
        photo_data_urls = []
        for photo_id in photos[:5]:
            try:
                file_info = bot.get_file(photo_id)
                downloaded_file = bot.download_file(file_info.file_path)
                img_b64 = base64.b64encode(downloaded_file).decode('utf-8')
                photo_data_urls.append(f"data:image/jpeg;base64,{img_b64}")
            except:
                continue
        
        input_params = {
            "prompt": estilo["prompt"],
            "images": photo_data_urls,
            "safety_tolerance": 6,
            "disable_safety_checker": True
        }
        output = replicate.run(MODELO_ARTISTICO["replicate_id"], input=input_params)
        if isinstance(output, list):
            urls = [str(url) for url in output]
        else:
            urls = [str(output)]
        
        if urls:
            img_data = requests.get(urls[0], timeout=60).content
            creditos_restantes = get_user_credits(user_id)
            creation_id = add_to_history(user_id, "edit", estilo["prompt"], urls[0])
            bot.send_photo(call.message.chat.id, img_data,
                caption=f"🎭 <b>Estilo {estilo['nome']} aplicado!</b>\n💳 Créditos: <code>{creditos_restantes}</code>",
                reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            update_user_stats(user_id, "total_edits")
        else:
            add_credits(user_id, MODELO_ARTISTICO["custo"], "reembolso")
            bot.send_message(call.message.chat.id, "❌ Erro. Créditos reembolsados.")
    except Exception as e:
        add_credits(user_id, MODELO_ARTISTICO["custo"], "reembolso")
        logger.error(f"Erro artistico multi: {e}")
        bot.send_message(call.message.chat.id, "❌ Erro. Créditos reembolsados.")
    finally:
        photo_collections.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('photo_model_'))
def callback_photo_model(call):
    """Handler para escolha de modelo ao enviar foto"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('photo_model_', '')
    
    # Verificar se tem foto pendente
    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada! Envie novamente. Envie novamente.")
        return
    
    photo_data = pending_photos.pop(user_id)
    
    if action == "cancel":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        texts = {
            "pt": "❌ Edição cancelada.",
            "en": "❌ Editing cancelled.",
            "es": "❌ Edicion cancelada."
        }
        bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]))
        return
    
    if action == "pro":
        # Modelo Pro - 2 creditos, prompt fixo
        creditos = get_user_credits(user_id)
        if creditos < MODELO_PRO["custo"]:
            texts = {
                "pt": f"❌ Créditos insuficientes! Modelo Pro precisa de {MODELO_PRO['custo']} creditos.\n💳 Voce tem: {creditos}",
                "en": f"❌ Insufficient credits! Pro Model needs {MODELO_PRO['custo']} credits.\n💳 You have: {creditos}",
                "es": f"❌ Créditos insuficientes! Modelo Pro necesita {MODELO_PRO['custo']} creditos.\n💳 Tienes: {creditos}"
            }
            bot.answer_callback_query(call.id, "Créditos insuficientes!")
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, parse_mode='HTML')
            return
        
        if not use_credit(user_id, MODELO_PRO["custo"]):
            return
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        proc_texts = {
            "pt": "✨ <b>Modelo Pro ativado!</b>\nAplicando melhoria fotorrealista avancada...\nIsto pode demorar um pouco.",
            "en": "✨ <b>Pro Model activated!</b>\nApplying advanced photorealistic enhancement...\nThis may take a moment.",
            "es": "✨ <b>Modelo Pro activado!</b>\nAplicando mejora fotorrealista avanzada...\nEsto puede tardar un poco."
        }
        proc_msg = bot.send_message(call.message.chat.id, proc_texts.get(lang, proc_texts["pt"]), parse_mode='HTML')
        
        try:
            file_info = bot.get_file(photo_data["file_id"])
            downloaded_file = bot.download_file(file_info.file_path)
            image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{image_base64}"
            
            urls = gerar_imagem_pro(image_input=image_data_url)
            
            bot.delete_message(call.message.chat.id, proc_msg.message_id)
            
            for url in urls:
                img_data = requests.get(url, timeout=60).content
                creation_id = add_to_history(user_id, "edit", MODELO_PRO["prompt_fixo"], url)
                creditos_restantes = get_user_credits(user_id)
                
                caption_texts = {
                    "pt": f"✨ <b>Melhoria Pro aplicada!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B)\n💳 Créditos restantes: <code>{creditos_restantes}</code>",
                    "en": f"✨ <b>Pro enhancement applied!</b>\n🤖 Model: Pro (FLUX.2 Klein 9B)\n💳 Credits remaining: <code>{creditos_restantes}</code>",
                    "es": f"✨ <b>Mejora Pro aplicada!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B)\n💳 Créditos restantes: <code>{creditos_restantes}</code>"
                }
                bot.send_photo(call.message.chat.id, img_data, caption=caption_texts.get(lang, caption_texts["pt"]),
                             reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            
            update_user_stats(user_id, "total_edits")
            logger.info(f"Edicao Pro para user {user_id}")
            
        except Exception as e:
            add_credits(user_id, MODELO_PRO["custo"], "reembolso")
            save_user_error(user_id, "edicao_pro", str(e), "Edicao Pro")
            diagnose_and_notify(e, "edicao_pro")
            error_texts = {
                "pt": "❌ Erro ao processar com Modelo Pro. Créditos reembolsados.",
                "en": "❌ Pro Model processing error. Credits refunded.",
                "es": "❌ Error al procesar con Modelo Pro. Créditos reembolsados."
            }
            try:
                bot.edit_message_text(error_texts.get(lang, error_texts["pt"]), call.message.chat.id, proc_msg.message_id)
            except:
                bot.send_message(call.message.chat.id, error_texts.get(lang, error_texts["pt"]))
            logger.error(f"Erro Pro: {e}")
    
    elif action == "padrao":
        # Modelo Padrao - 1 credito
        caption_text = photo_data.get("caption", "")
        
        if not caption_text or len(caption_text.strip()) < 3:
            # Mostrar presets + opcao personalizada
            pending_photos[user_id] = photo_data
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            for key, preset in PRESETS_PADRAO.items():
                markup.add(telebot.types.InlineKeyboardButton(preset["nome"], callback_data=f"preset_{key}"))
            markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="preset_cancel"))
            bot.send_message(call.message.chat.id, "🎨 <b>Modelo Padrao</b> (1 cred)\n\nEscolha ou escreva o que deseja:", reply_markup=markup, parse_mode='HTML')
            user_states[user_id] = "awaiting_edit_prompt"
            return
        
        # Tem legenda, processar direto
        creditos = get_user_credits(user_id)
        if creditos < MODELO_PADRAO["custo"]:
            bot.answer_callback_query(call.id, "Créditos insuficientes!")
            return
        
        if not use_credit(user_id, MODELO_PADRAO["custo"]):
            return
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        proc_texts = {
            "pt": "🎨 Processando imagem...",
            "en": "🎨 Processing image...",
            "es": "🎨 Procesando imagen..."
        }
        proc_msg = bot.send_message(call.message.chat.id, proc_texts.get(lang, proc_texts["pt"]))
        
        try:
            file_info = bot.get_file(photo_data["file_id"])
            downloaded_file = bot.download_file(file_info.file_path)
            image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{image_base64}"
            
            prompt = caption_text.strip()
            style_settings = get_user_style_settings(user_id)
            aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
            urls = gerar_imagem_modelo(prompt, aspect_ratio, image_input=image_data_url, num_outputs=1)
            
            bot.delete_message(call.message.chat.id, proc_msg.message_id)
            
            for url in urls:
                img_data = requests.get(url, timeout=60).content
                creation_id = add_to_history(user_id, "edit", prompt, url)
                creditos_restantes = get_user_credits(user_id)
                
                caption_texts = {
                    "pt": f"✅ Imagem editada!\n🤖 Modelo: Padrao\n💳 Créditos restantes: <code>{creditos_restantes}</code>",
                    "en": f"✅ Image edited!\n🤖 Model: Standard\n💳 Credits remaining: <code>{creditos_restantes}</code>",
                    "es": f"✅ Imagen editada!\n🤖 Modelo: Estandar\n💳 Créditos restantes: <code>{creditos_restantes}</code>"
                }
                bot.send_photo(call.message.chat.id, img_data, caption=caption_texts.get(lang, caption_texts["pt"]),
                             reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            
            update_user_stats(user_id, "total_edits")
            logger.info(f"Edicao Padrao para user {user_id}")
            
        except Exception as e:
            add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
            save_user_error(user_id, "edicao_padrao", str(e), "Edicao Padrao")
            diagnose_and_notify(e, "edicao_padrao")
            error_texts = {
                "pt": "❌ Erro ao processar. Crédito reembolsado.",
                "en": "❌ Processing error. Credit refunded.",
                "es": "❌ Error al procesar. Crédito reembolsado."
            }
            try:
                bot.edit_message_text(error_texts.get(lang, error_texts["pt"]), call.message.chat.id, proc_msg.message_id)
            except:
                bot.send_message(call.message.chat.id, error_texts.get(lang, error_texts["pt"]))
    
    elif action == "artistico":
        # Modelo Artistico - mostrar estilos
        pending_photos[user_id] = photo_data  # Devolver foto
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        markup = telebot.types.InlineKeyboardMarkup(row_width=3)
        keys = list(ESTILOS_ARTISTICOS.keys())
        for i in range(0, len(keys), 3):
            row = []
            for key in keys[i:i+3]:
                row.append(telebot.types.InlineKeyboardButton(ESTILOS_ARTISTICOS[key]["nome"], callback_data=f"artstyle_{key}"))
            markup.row(*row)
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="artstyle_cancel"))
        bot.send_message(call.message.chat.id, "🎭 <b>Escolha o estilo:</b> (2 cred)", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('artstyle_'))
def callback_art_style(call):
    """Processa foto unica com estilo artistico"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    estilo_key = call.data.replace('artstyle_', '')
    
    if estilo_key == "cancel":
        pending_photos.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "❌ Cancelado.")
        return
    
    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada! Envie novamente. Envie novamente.")
        return
    
    photo_data = pending_photos.pop(user_id)
    creditos = get_user_credits(user_id)
    
    if creditos < MODELO_ARTISTICO["custo"]:
        bot.answer_callback_query(call.id, "Créditos insuficientes!")
        return
    
    if not use_credit(user_id, MODELO_ARTISTICO["custo"]):
        return
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    estilo = ESTILOS_ARTISTICOS.get(estilo_key, ESTILOS_ARTISTICOS["anime"])
    proc_msg = bot.send_message(call.message.chat.id, f"🎭 Aplicando estilo {estilo['nome']}...")
    
    try:
        file_info = bot.get_file(photo_data["file_id"])
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"
        
        urls = gerar_imagem_artistica(image_data_url, estilo_key)
        
        bot.delete_message(call.message.chat.id, proc_msg.message_id)
        
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "edit", estilo["prompt"], url)
            creditos_restantes = get_user_credits(user_id)
            bot.send_photo(call.message.chat.id, img_data,
                caption=f"🎭 <b>Estilo {estilo['nome']} aplicado!</b>\n💳 Créditos: <code>{creditos_restantes}</code>",
                reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
        
        update_user_stats(user_id, "total_edits")
    
    except Exception as e:
        add_credits(user_id, MODELO_ARTISTICO["custo"], "reembolso")
        logger.error(f"Erro artistico: {e}")
        diagnose_and_notify(e, "edicao_artistica")
        try:
            bot.edit_message_text("❌ Erro. Créditos reembolsados.", call.message.chat.id, proc_msg.message_id)
        except:
            bot.send_message(call.message.chat.id, "❌ Erro. Créditos reembolsados.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('preset_'))
def callback_preset(call):
    """Handler para presets do modelo padrao"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    preset_key = call.data.replace('preset_', '')
    
    if preset_key == "cancel":
        pending_photos.pop(user_id, None)
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "❌ Cancelado.")
        return
    
    if preset_key == "default":
        # Personalizado - aguardar prompt do usuario
        bot.answer_callback_query(call.id, "Escreva o que deseja!")
        try:
            bot.edit_message_text("✍️ Escreva o que deseja fazer com a imagem:", call.message.chat.id, call.message.message_id)
        except:
            pass
        return
    
    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada! Envie novamente.")
        return
    
    preset = PRESETS_PADRAO.get(preset_key)
    if not preset:
        return
    
    photo_data = pending_photos.pop(user_id)
    user_states.pop(user_id, None)
    
    creditos = get_user_credits(user_id)
    if creditos < MODELO_PADRAO["custo"]:
        bot.answer_callback_query(call.id, "Créditos insuficientes!")
        return
    
    if not use_credit(user_id, MODELO_PADRAO["custo"]):
        return
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    proc_msg = bot.send_message(call.message.chat.id, f"🎨 Aplicando {preset['nome']}...")
    
    try:
        file_info = bot.get_file(photo_data["file_id"])
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"
        
        style_settings = get_user_style_settings(user_id)
        aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
        urls = gerar_imagem_modelo(preset["prompt"], aspect_ratio, image_input=image_data_url, num_outputs=1)
        
        bot.delete_message(call.message.chat.id, proc_msg.message_id)
        
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "edit", preset["prompt"], url)
            creditos_restantes = get_user_credits(user_id)
            bot.send_photo(call.message.chat.id, img_data,
                caption=f"✅ {preset['nome']}\n💳 Créditos: <code>{creditos_restantes}</code>",
                reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
        update_user_stats(user_id, "total_edits")
    except Exception as e:
        add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
        logger.error(f"Erro preset: {e}")
        try:
            bot.edit_message_text("❌ Erro. Crédito reembolsado.", call.message.chat.id, proc_msg.message_id)
        except:
            bot.send_message(call.message.chat.id, "❌ Erro. Crédito reembolsado.")

# ==================== HANDLER PARA PROMPT DE EDICAO PADRAO ====================
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_edit_prompt')
def handle_edit_prompt(message):
    """Recebe prompt de edicao quando usuario escolheu Modelo Padrao sem legenda"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)
    
    if user_id not in pending_photos:
        bot.reply_to(message, "❌ Foto expirada! Envie novamente. Envie novamente.")
        return
    
    photo_data = pending_photos.pop(user_id)
    prompt = message.text.strip()
    
    is_valid, error = validate_prompt(prompt)
    if not is_valid:
        bot.reply_to(message, f"❌ {error}")
        return
    
    creditos = get_user_credits(user_id)
    if creditos < MODELO_PADRAO["custo"]:
        bot.reply_to(message, "❌ Créditos insuficientes!")
        return
    
    if not use_credit(user_id, MODELO_PADRAO["custo"]):
        return
    
    proc_msg = bot.reply_to(message, "🎨 Processando imagem...")
    
    try:
        file_info = bot.get_file(photo_data["file_id"])
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"
        
        style_settings = get_user_style_settings(user_id)
        aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
        urls = gerar_imagem_modelo(prompt, aspect_ratio, image_input=image_data_url, num_outputs=1)
        
        bot.delete_message(message.chat.id, proc_msg.message_id)
        
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "edit", prompt, url)
            creditos_restantes = get_user_credits(user_id)
            
            caption_texts = {
                "pt": f"✅ Imagem editada!\n🤖 Modelo: Padrao\n💳 Créditos restantes: <code>{creditos_restantes}</code>",
                "en": f"✅ Image edited!\n🤖 Model: Standard\n💳 Credits remaining: <code>{creditos_restantes}</code>",
                "es": f"✅ Imagen editada!\n🤖 Modelo: Estandar\n💳 Créditos restantes: <code>{creditos_restantes}</code>"
            }
            bot.send_photo(message.chat.id, img_data, caption=caption_texts.get(lang, caption_texts["pt"]),
                         reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
        
        update_user_stats(user_id, "total_edits")
        
    except Exception as e:
        add_credits(user_id, MODELO_PADRAO["custo"], "reembolso")
        save_user_error(user_id, "edicao_padrao", str(e), "Edicao Padrao")
        diagnose_and_notify(e, "edicao_padrao")
        bot.reply_to(message, "❌ Erro ao processar. Crédito reembolsado.")

# ==================== VIDEO EXCLUSIVO ADMIN ====================
@bot.message_handler(commands=['video'])
def cmd_video(message):
    """Geracao de video - EXCLUSIVO para super admin"""
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Funcionalidade exclusiva.")
        return
    
    lang = get_user_lang(user_id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("✍️ Texto para Vídeo", callback_data="video_text"),
        telebot.types.InlineKeyboardButton("📸 Imagem para Vídeo", callback_data="video_image"),
        telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="video_cancel")
    )
    bot.send_message(message.chat.id, "🎬 <b>Geração de Vídeo (Admin)</b>\n\nEscolha o modo:", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('video_'))
def callback_video(call):
    user_id = call.from_user.id
    if not is_super_admin(user_id):
        return
    
    action = call.data.replace('video_', '')
    
    if action == "cancel":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return
    
    if action == "text":
        user_states[user_id] = "awaiting_video_prompt"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🎬 Escreva a descrição do vídeo que deseja gerar:")
    
    elif action == "image":
        user_states[user_id] = "awaiting_video_image"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🎬 Envie a imagem que quer transformar em vídeo:")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_video_prompt')
def handle_video_prompt(message):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        return
    user_states.pop(user_id, None)
    prompt = message.text.strip()
    
    proc_msg = bot.reply_to(message, "🎬 Gerando vídeo... Isto pode demorar 30-60 segundos.")
    try:
        output = replicate.run("xai/grok-imagine-video", input={
            "prompt": prompt,
            "duration": 6
        })
        if isinstance(output, list):
            video_url = str(output[0])
        elif hasattr(output, 'url'):
            video_url = str(output.url)
        else:
            video_url = str(output)
        
        bot.delete_message(message.chat.id, proc_msg.message_id)
        video_data = requests.get(video_url, timeout=120).content
        bot.send_video(message.chat.id, video_data, caption=f"🎬 Vídeo gerado!\n💬 {prompt[:80]}")
    except Exception as e:
        bot.edit_message_text(f"❌ Erro: {str(e)[:200]}", message.chat.id, proc_msg.message_id)
        logger.error(f"Erro video: {e}")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_video_image', content_types=['photo'])
def handle_video_image(message):
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        return
    user_states.pop(user_id, None)
    
    proc_msg = bot.reply_to(message, "🎬 Transformando imagem em vídeo... 30-60 segundos.")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"
        
        caption = message.caption or "animate this image with subtle natural movement"
        
        output = replicate.run("xai/grok-imagine-video", input={
            "prompt": caption,
            "image": image_data_url,
            "duration": 6
        })
        if isinstance(output, list):
            video_url = str(output[0])
        elif hasattr(output, 'url'):
            video_url = str(output.url)
        else:
            video_url = str(output)
        
        bot.delete_message(message.chat.id, proc_msg.message_id)
        video_data = requests.get(video_url, timeout=120).content
        bot.send_video(message.chat.id, video_data, caption="🎬 Imagem animada!")
    except Exception as e:
        bot.edit_message_text(f"❌ Erro: {str(e)[:200]}", message.chat.id, proc_msg.message_id)
        logger.error(f"Erro video image: {e}")

# ==================== BLOQUEIO DE ARQUIVOS NAO SUPORTADOS ====================
@bot.message_handler(content_types=['video', 'video_note', 'animation'])
def handle_video_blocked(message):
    """Bloqueia envio de videos"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    texts = {
        "pt": "🚫 <b>⚠️ Apenas imagens!</b>\n\nEste bot aceita apenas fotos/imagens.\nVideos não são suportados.\n\n📸 Envie 1-5 fotos para editar ou combinar!",
        "en": "🚫 <b>Images only!</b>\n\nThis bot only accepts photos/images.\nVideos are not supported.\n\n📸 Send 1-5 photos to edit or combine!",
        "es": "🚫 <b>Solo imagenes!</b>\n\nEste bot solo acepta fotos/imagenes.\nLos videos no estan soportados.\n\n📸 Envia 1-5 fotos para editar o combinar!"
    }
    bot.reply_to(message, texts.get(lang, texts["pt"]), parse_mode='HTML')

@bot.message_handler(content_types=['audio', 'voice'])
def handle_audio_blocked(message):
    """Bloqueia envio de audios"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    texts = {
        "pt": "🚫 <b>⚠️ Apenas imagens!</b>\n\nEste bot aceita apenas fotos/imagens.\nAudios e musicas não são suportados.\n\n📸 Envie 1-5 fotos para editar ou combinar!",
        "en": "🚫 <b>Images only!</b>\n\nThis bot only accepts photos/images.\nAudio and music are not supported.\n\n📸 Send 1-5 photos to edit or combine!",
        "es": "🚫 <b>Solo imagenes!</b>\n\nEste bot solo acepta fotos/imagenes.\nAudios y musica no estan soportados.\n\n📸 Envia 1-5 fotos para editar o combinar!"
    }
    bot.reply_to(message, texts.get(lang, texts["pt"]), parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_document_blocked(message):
    """Bloqueia envio de documentos/arquivos"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    texts = {
        "pt": "🚫 <b>⚠️ Apenas imagens!</b>\n\nEste bot aceita apenas fotos/imagens.\nDocumentos e arquivos não são suportados.\n\n📸 Envie as fotos diretamente (nao como arquivo)!",
        "en": "🚫 <b>Images only!</b>\n\nThis bot only accepts photos/images.\nDocuments and files are not supported.\n\n📸 Send photos directly (not as files)!",
        "es": "🚫 <b>Solo imagenes!</b>\n\nEste bot solo acepta fotos/imagenes.\nDocumentos y archivos no estan soportados.\n\n📸 Envia las fotos directamente (no como archivo)!"
    }
    bot.reply_to(message, texts.get(lang, texts["pt"]), parse_mode='HTML')

@bot.message_handler(content_types=['sticker'])
def handle_sticker_blocked(message):
    """Bloqueia envio de stickers"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    texts = {
        "pt": "🚫 <b>⚠️ Apenas imagens!</b>\n\nStickers não são suportados.\n\n📸 Envie 1-5 fotos para editar ou combinar!",
        "en": "🚫 <b>Images only!</b>\n\nStickers are not supported.\n\n📸 Send 1-5 photos to edit or combine!",
        "es": "🚫 <b>Solo imagenes!</b>\n\nStickers no estan soportados.\n\n📸 Envia 1-5 fotos para editar o combinar!"
    }
    bot.reply_to(message, texts.get(lang, texts["pt"]), parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "🎛️ Painel Admin")
def handle_admin_panel_button(message):
    """Handler para o botão Painel Admin fixo"""
    user_id = message.from_user.id
    
    # Verificar se é admin
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Acesso negado!")
        return
    
    msg = "🎛️ <b>PAINEL DE CONTROLE ADMINISTRATIVO</b> 🔐\n\n"
    msg += "Bem-vindo ao painel de gerenciamento do Remake Pixel!\n\n"
    msg += "Use os botões abaixo para gerenciar o bot:\n\n"
    msg += "💳 <b>Dar Créditos</b> - Adicione créditos a usuários\n"
    msg += "📊 <b>Estatísticas</b> - Dados gerais do bot\n"
    msg += "👥 <b>Listar Usuários</b> - Todos os cadastrados\n"
    msg += "📢 <b>Broadcast</b> - Mensagens para todos\n"
    msg += "🌐 <b>Ver Ngrok</b> - URL pública\n"
    msg += "📈 <b>Status Bot</b> - Saúde e uptime\n"
    msg += "🛒 <b>Aprovar Compras</b> - Pagamentos pendentes\n\n"
    msg += "✨ Gerencie tudo sem parar o bot!"
    
    bot.send_message(message.chat.id, msg, reply_markup=admin_panel_keyboard(user_id), parse_mode='HTML')
    logger.info(f"Admin {user_id} acessou o painel via botão")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'in_wizard')
def handle_wizard(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        photo_data = bot.download_file(file_info.file_path)
        next_q, is_complete = process_wizard_step(user_id, "photo", photo_data)
    else:
        next_q, is_complete = process_wizard_step(user_id, message.text.strip())
    
    if is_complete:
        final_prompt = next_q
        user_states.pop(user_id, None)
        
        creditos = get_user_credits(user_id)
        if creditos < 1:
            texts = {"pt": "❌ Créditos insuficientes!", "en": "❌ Insufficient credits!", "es": "❌ ¡Créditos insuficientes!"}
            bot.reply_to(message, texts.get(lang, texts["pt"]))
            return
        
        if not use_credit(user_id, 1):
            return
        
        # Verificar se tem foto de referência do wizard
        ref_photo = None
        if user_id in wizard_states and "reference_photo" in wizard_states.get(user_id, {}).get("answers", {}):
            ref_photo = wizard_states[user_id]["answers"]["reference_photo"]
        
        # Tentar obter do state anterior (já foi popped)
        if not ref_photo and hasattr(handle_wizard, '_last_ref'):
            ref_photo = getattr(handle_wizard, '_last_ref', {}).get(user_id)
        
        if ref_photo:
            # Usar foto de referência como image_input
            proc_msg = bot.reply_to(message, "🎨 A gerar com foto de referência...")
            try:
                image_base64 = base64.b64encode(ref_photo).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{image_base64}"
                improved = improve_prompt_auto(final_prompt)
                
                style_settings = get_user_style_settings(user_id)
                aspect_ratio = style_settings.get("aspect_ratio", "square")
                if aspect_ratio not in ASPECT_RATIOS:
                    aspect_ratio = "square"
                ratio = ASPECT_RATIOS[aspect_ratio]["ratio"]
                
                urls = gerar_imagem_modelo(improved, ratio, image_input=image_data_url, num_outputs=1)
                bot.delete_message(message.chat.id, proc_msg.message_id)
                for url in urls:
                    img_data = requests.get(url, timeout=60).content
                    creation_id = add_to_history(user_id, "edit", final_prompt, url)
                    cred_rest = get_user_credits(user_id)
                    bot.send_photo(message.chat.id, img_data,
                        caption=f"✅ Gerado com referência!\n💳 Créditos: <code>{cred_rest}</code>",
                        reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
            except Exception as e:
                add_credits(user_id, 1, "reembolso")
                bot.reply_to(message, "❌ Erro. Crédito reembolsado.")
                logger.error(f"Erro wizard com ref: {e}")
        else:
            processar_criacao(message.chat.id, user_id, final_prompt, lang, auto_improve=True)
    elif next_q:
        bot.reply_to(message, next_q)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_prompt_create')
def handle_create(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    prompt = message.text.strip()
    user_states.pop(user_id, None)
    
    is_valid, error = validate_prompt(prompt)
    if not is_valid:
        bot.reply_to(message, f"❌ {error}")
        return
    
    allowed, remaining = rate_limiter.check_limit(user_id, 'images')
    if not allowed:
        wait = rate_limiter.get_wait_time(user_id, 'images')
        bot.reply_to(message, f"⚠️ Aguarde {wait}s")
        return
    
    if not use_credit(user_id, 1):
        texts = {"pt": "❌ Insuficiente!", "en": "❌ Insufficient!", "es": "❌ ¡Insuficiente!"}
        bot.reply_to(message, texts.get(lang, texts["pt"]))
        return
    
    processar_criacao(message.chat.id, user_id, prompt, lang)

def detect_image_intent(text):
    """Detecta se o usuário quer gerar uma imagem - MELHORADO"""
    # Palavras-chave FORTES
    strong_keywords = ["gera", "gere", "cria", "crie", "faça", "faz", "desenha", "desenhe",
                       "generate", "create", "make", "draw", "genera", "crea", "dibuja",
                       "imagem de", "foto de", "image of", "picture of", "imagen de"]
    
    text_lower = text.lower()
    
    # Se começa com palavra forte
    for keyword in strong_keywords:
        if text_lower.startswith(keyword):
            return True
    
    # Se contém imagem/foto E é maior que 10 caracteres
    if ("imagem" in text_lower or "foto" in text_lower or "image" in text_lower or 
        "picture" in text_lower or "imagen" in text_lower):
        if len(text) > 10:
            return True
    
    return False

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    # VERIFICAR SE BOT ESTÁ PAUSADO
    global bot_paused
    if bot_paused and user_id not in ADMIN_IDS:
        bot.reply_to(message, pause_message)
        return
    
    # IGNORAR se for foto
    if message.content_type == 'photo':
        return
    
    # IGNORAR se não tiver texto
    if not message.text:
        return
    
    text = message.text.strip()
    
    # NUNCA bloquear comandos essenciais
    if text.startswith('/'):
        return
    
    # BLOQUEAR se onboarding não completo
    if not is_onboarded(user_id):
        bot.reply_to(message, "⚠️ Complete o processo inicial. Use /start")
        return
    
    # REPLY PARA REEDITAR: se responder a uma foto do bot com texto
    if message.reply_to_message and message.reply_to_message.photo:
        # Usar a foto da resposta + texto como prompt
        creditos = get_user_credits(user_id)
        if creditos < 1:
            bot.reply_to(message, "❌ Créditos insuficientes!")
            return
        if not use_credit(user_id, 1):
            return
        proc_msg = bot.reply_to(message, "🎨 Reeditando imagem...")
        try:
            file_info = bot.get_file(message.reply_to_message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{image_base64}"
            style_settings = get_user_style_settings(user_id)
            aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
            urls = gerar_imagem_modelo(text, aspect_ratio, image_input=image_data_url, num_outputs=1)
            bot.delete_message(message.chat.id, proc_msg.message_id)
            for url in urls:
                img_data = requests.get(url, timeout=60).content
                creation_id = add_to_history(user_id, "edit", text, url)
                cred_rest = get_user_credits(user_id)
                bot.send_photo(message.chat.id, img_data,
                    caption=f"✅ Reeditado!\n💬 {text[:60]}\n💳 Créditos: <code>{cred_rest}</code>",
                    reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')
        except Exception as e:
            add_credits(user_id, 1, "reembolso")
            bot.reply_to(message, "❌ Erro. Crédito reembolsado.")
            logger.error(f"Erro reply edit: {e}")
        return
    
    # ⚠️ IGNORAR se for COMANDO (começa com /)
    if text.startswith('/'):
        print(f"⚠️ Comando '{text}' detectado - ignorando chat AI")
        return  # Deixa os handlers de comando processarem
    
    allowed, remaining = rate_limiter.check_limit(user_id, 'messages')
    if not allowed:
        wait = rate_limiter.get_wait_time(user_id, 'messages')
        bot.reply_to(message, f"⚠️ Aguarde {wait}s")
        return
    
    # DETECTAR INTENÇÃO DE GERAÇÃO DE IMAGEM
    if detect_image_intent(text):
        # Extrair o que o usuário quer gerar
        text_clean = text.lower()
        for prefix in ["gere", "gera", "crie", "cria", "faça", "faz", "desenhe", "desenha", "generate", "create", "make", "draw"]:
            if text_clean.startswith(prefix):
                text_clean = text_clean.replace(prefix, "", 1).strip()
                break
        
        for word in ["a imagem de", "uma imagem de", "imagem de", "a foto de", "uma foto de", "foto de", "an image of", "image of", "a picture of", "picture of"]:
            text_clean = text_clean.replace(word, "").strip()
        
        prompt = text_clean if text_clean else text
        
        # Verificar créditos
        creditos = get_user_credits(user_id)
        if creditos < 1:
            texts = {"pt": "❌ Créditos insuficientes! Use /start para comprar.", "en": "❌ Insufficient credits! Use /start to buy.", "es": "❌ ¡Créditos insuficientes! Usa /start para comprar."}
            bot.reply_to(message, texts.get(lang, texts["pt"]))
            return
        
        if not use_credit(user_id, 1):
            return
        
        # GERAR IMAGEM DIRETAMENTE
        processar_criacao(message.chat.id, user_id, prompt, lang)
        return
    
    # CHAT NORMAL
    resposta = get_smart_chat_response(user_id, text, lang)
    bot.reply_to(message, f"🤖 {resposta}")

# ==================== MONITORAMENTO ====================
bot_start_time = datetime.now()

def get_current_ngrok_url():
    """Obtém a URL atual do Ngrok"""
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
        tunnels = response.json().get('tunnels', [])
        for tunnel in tunnels:
            if tunnel.get('proto') == 'https':
                return tunnel.get('public_url')
        return None
    except:
        return None

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except:
        return 'Error', 400
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        meta = session.get('metadata', {})
        user_id = int(meta.get('user_id', 0))
        creditos = int(meta.get('creditos', 0))
        pacote = meta.get('pacote_nome', 'Pacote')
        amount_total = session.get('amount_total', 0)  # Em centimos
        
        if user_id:
            novo = add_credits(user_id, creditos, f"stripe_{pacote}")
            lang = get_user_lang(user_id)
            bot.send_message(user_id, f"🎉 +{creditos} creditos!\n💳 Total: <code>{novo}</code>", reply_markup=main_keyboard(lang), parse_mode='HTML')
            logger.info(f"Pagamento: {creditos} para {user_id} (EUR {amount_total/100:.2f})")
            
            # Referral bonus: se comprou 5EUR+ e foi indicado, dar 10 creditos ao referrer
            if amount_total >= 500:  # 500 centimos = 5 EUR
                ref_data = load_json(REFERRAL_FILE)
                referrer_id = ref_data.get("referred_by", {}).get(str(user_id))
                if referrer_id:
                    referrer_id = int(referrer_id)
                    add_credits(referrer_id, 10, "referral_bonus")
                    try:
                        bot.send_message(referrer_id, 
                            f"🎉 <b>BONUS REFERRAL!</b>\n\n"
                            f"Um amigo que voce indicou fez uma compra!\n"
                            f"➕ <code>10</code> creditos adicionados a sua conta!\n\n"
                            f"Continue a indicar amigos para ganhar mais creditos!",
                            parse_mode='HTML')
                    except:
                        pass
                    logger.info(f"Referral bonus: 10 creditos para {referrer_id} (indicou {user_id})")
            
            # Notificar admin
            # Calcular custos e lucro estimado
            # Custo medio por credito no Replicate:
            # Padrao (1 cred): ~EUR 0.005 | Pro (3 cred): ~EUR 0.025 | Artistico (2 cred): ~EUR 0.02
            # Media ponderada: ~EUR 0.008 por credito
            custo_replicate = round(creditos * 0.008, 2)
            lucro_estimado = round(amount_total/100 - custo_replicate, 2)
            percentagem_lucro = round((lucro_estimado / (amount_total/100)) * 100, 1) if amount_total > 0 else 0
            
            # Saldo Replicate recomendado para cobrir estes creditos
            saldo_replicate_necessario = round(custo_replicate * 1.2, 2)  # +20% margem
            
            notify_admin(
                f"💰 <b>PAGAMENTO RECEBIDO!</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📦 {pacote}\n"
                f"💳 {creditos} creditos\n\n"
                f"💶 <b>FINANCEIRO:</b>\n"
                f"├ Recebido: €{amount_total/100:.2f}\n"
                f"├ Custo Replicate: ~€{custo_replicate}\n"
                f"├ <b>Lucro: ~€{lucro_estimado}</b>\n"
                f"└ Margem: {percentagem_lucro}%\n\n"
                f"🔧 Replicate precisa ter: ~€{saldo_replicate_necessario} para cobrir",
                "money"
            )
    return jsonify({'status': 'success'}), 200

def run_webhook():
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    print("=" * 60)
    print("✨ Remake Pixel Bot - VERSÃO SUPREMA 👑")
    print("=" * 60)
    print("🧙 Prompt Wizard (Assistente Passo a Passo): ✅")
    print("🎨 Estilos Predefinidos (Perchance): ✅")
    print("🔢 Variações Configuráveis (1-4): ✅")
    print("🚀 Automatic Prompt Improver: ✅")
    print("⭐ Sistema de Favoritos: ✅")
    print("📊 Estatísticas de Usuário: ✅")
    print("🔗 Compartilhamento de Criações: ✅")
    print("🤖 Personalidades de IA: ✅")
    print("🖼️ Galeria de Exemplos: ✅")
    print("🧠 Chat IA com Memória: ✅")
    print("🎓 Onboarding Inteligente: ✅")
    print("🛡️  Rate Limiting: ✅")
    print("💾 Backup Automático: ✅")
    print("📝 Logging Profissional: ✅")
    print("🎁 Sistema Referral: ✅")
    print("🎛️  PAINEL DE CONTROLE ADMIN: ✅")
    print(f"📞 Suporte: {SUPORTE_TELEGRAM}")
    print("=" * 60)
    print("💡 NOVO: Use /painel para gerenciar o bot via Telegram!")
    print("=" * 60)
    
    for admin_id in ADMIN_IDS:
        if get_user_credits(admin_id) < 50:
            add_credits(admin_id, 50, "admin")
    
    # ==================== CONFIGURAR MENU NATIVO (FORÇADO!) ====================
    print("\n🔧 Configurando menu nativo do Telegram...")
    
    try:
        # Comandos usuários
        user_commands = [
            telebot.types.BotCommand("menu", "📋 Menu"),
            telebot.types.BotCommand("start", "🔄 Reiniciar"),
            telebot.types.BotCommand("wizard", "🧙 Assistente de Criação"),
            telebot.types.BotCommand("creditos", "💳 Ver Créditos"),
            telebot.types.BotCommand("idioma", "🌐 Mudar Idioma"),
            telebot.types.BotCommand("help", "❓ Ajuda")
        ]
        
        result = bot.set_my_commands(user_commands, scope=telebot.types.BotCommandScopeDefault())
        print(f"✅ Menu padrão: {result}")
        
        # Comandos admin
        admin_commands = [
            telebot.types.BotCommand("menu", "📋 Menu"),
            telebot.types.BotCommand("start", "🔄 Reiniciar"),
            telebot.types.BotCommand("video", "🎬 Gerar Vídeo"),
            telebot.types.BotCommand("painel", "🎛️ Painel Admin"),
            telebot.types.BotCommand("status", "📊 Status"),
            telebot.types.BotCommand("creditos", "💳 Ver Créditos"),
            telebot.types.BotCommand("idioma", "🌐 Mudar Idioma"),
            telebot.types.BotCommand("help", "❓ Ajuda")
        ]
        
        for admin_id in ADMIN_IDS:
            result_admin = bot.set_my_commands(admin_commands, scope=telebot.types.BotCommandScopeChat(chat_id=admin_id))
            print(f"✅ Menu admin {admin_id}: {result_admin}")
        
        print("✅ Menu configurado COM SUCESSO!\n")
    except Exception as e:
        print(f"❌ ERRO configurando menu: {e}\n")
    
    backup_manager.start()
    
    # Iniciar Flask (webhook + health check) em thread separada
    # DEVE iniciar ANTES do polling para o Render/UptimeRobot funcionar
    port = int(os.getenv("PORT", 10000))
    print(f"🌐 Flask a correr na porta {port}...")
    Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False), daemon=True).start()
    time.sleep(2)  # Esperar Flask arrancar
    
    print("=" * 60)
    print("🤖 Remake Pixel ONLINE")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE: FECHE e ABRA o Telegram para ver o menu\n")
    logger.info("Bot iniciado")
    
    # Anti-409: remover webhook antigo e limpar instâncias
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    # Auto-reconnect loop
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60, long_polling_timeout=60, allowed_updates=['message', 'callback_query'])
        except KeyboardInterrupt:
            logger.info("Bot parado manualmente.")
            break
        except Exception as e:
            error_msg = str(e)
            if "409" in error_msg or "terminated by other" in error_msg:
                print("⚠️ Erro 409 — outra instância ativa. A tentar novamente em 30s...")
                print("SOLUÇÃO: Para todas as outras instâncias do bot!")
                time.sleep(30)
            else:
                logger.error(f"Conexão perdida: {e}")
                print(f"\n⚠️ Conexão perdida. Reconectando em 10 segundos...")
                time.sleep(10)
            print("🔄 Reconectando...")
            continue
