# -*- coding: utf-8 -*-
"""
Remake7 Pixel Bot - VERSÃO SUPREMA 👑
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
import traceback
import secrets

# ==================== CONFIGURAÇÕES ====================
SUPER_ADMIN_IDS = [6936852095]  # Admin principal - NUNCA pode ser removido
ADMIN_IDS = [6936852095]  # Sera atualizado com admins secundarios
BOT_USERNAME = "RemakePix_bot"
SUPORTE_TELEGRAM = "@Remake_Pixel_adm"
SECONDARY_ADMINS_FILE = "secondary_admins.json"

# Canal público para galeria automatica (ex: @RemakePixel_Gallery ou -1001234567890)
GALLERY_CHANNEL = os.getenv("GALLERY_CHANNEL", "@RemakePixel_Gallery")

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

# CORS: permite landing em Vercel chamar o backend
@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/")
def home():
    return "OK", 200

@app.route("/health")
def health():
    return {"status": "online", "bot": "Remake Pixel"}, 200


# ==================== ENDPOINTS LANDING PAGE ====================
_LANDING_DEMO_IP = {}  # ip -> [timestamps] para rate limit da demo
_LANDING_NSFW_RE = re.compile(
    r'\b(nude|naked|nsfw|porn|sex|sexy|erotic|hentai|topless|boobs|breasts|'
    r'nipples|penis|vagina|dick|pussy|cum|nudez|pelado|pelada|nu|nua|'
    r'peito|seios|buceta|gozar|desnudo|desnuda|tetas)\b',
    re.IGNORECASE
)


def _landing_client_ip():
    from flask import request
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route("/api/public/stats", methods=["GET", "OPTIONS"])
def landing_public_stats():
    """Estatísticas publicas da landing."""
    if request.method == "OPTIONS":
        return "", 204
    users = 0
    creations = 0
    try:
        credits = load_json(CREDITS_FILE)
        users = len(credits)
        stats = load_json(STATISTICS_FILE)
        for u in stats.values():
            creations += int(u.get("total_creations", 0)) + int(u.get("total_edits", 0))
    except Exception:
        pass
    from flask import jsonify
    return jsonify({
        "users": max(users, 1247),
        "creations": max(creations, 8432),
        "models": 4
    })


@app.route("/api/leads/subscribe", methods=["POST", "OPTIONS"])
def landing_lead_subscribe():
    """Captura lead (email/nome) para marketing futuro."""
    if request.method == "OPTIONS":
        return "", 204
    from flask import jsonify
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        name = (data.get("name") or "").strip()
        source = (data.get("source") or "landing").strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return jsonify({"success": False, "error": "Invalid email"}), 400

        leads = load_json("landing_leads.json")
        if email not in leads:
            leads[email] = {
                "email": email,
                "name": name,
                "source": source,
                "ip": _landing_client_ip(),
                "ts": int(time.time())
            }
            save_json("landing_leads.json", leads, Lock())
            log_system_event("info", "lead_capture", f"new lead: {email}", None)
        return jsonify({"success": True, "telegram_link": f"https://t.me/{BOT_USERNAME}"})
    except Exception as e:
        logger.error(f"lead err: {e}")
        return jsonify({"success": True, "telegram_link": f"https://t.me/{BOT_USERNAME}"})


@app.route("/api/demo/generate", methods=["POST", "OPTIONS"])
def landing_demo_generate():
    """Gera 1 imagem grátis para visitante da landing (rate-limited por IP)."""
    if request.method == "OPTIONS":
        return "", 204
    from flask import jsonify
    try:
        data = request.get_json(silent=True) or {}
        prompt = (data.get("prompt") or "").strip()
        if len(prompt) < 5 or len(prompt) > 300:
            return jsonify({"success": False, "error": "Prompt must be 5-300 chars"})

        # NSFW landing block REMOVIDO — filtro desativado
        # if _LANDING_NSFW_RE.search(prompt):
        #     log_system_event("nsfw", "landing_blocked", prompt[:100], None)
        #     return jsonify({"success": False, "error": "Prompt contains blocked content."})

        # Rate limit: 1 por IP / 24h
        ip = _landing_client_ip()
        now = time.time()
        cutoff = now - 86400
        log = [t for t in _LANDING_DEMO_IP.get(ip, []) if t > cutoff]
        if len(log) >= 1:
            return jsonify({"success": False, "error": "Free limit reached. Use our Telegram bot for more!",
                            "telegram_link": f"https://t.me/{BOT_USERNAME}"})

        # Gera via Replicate (Grok)
        replicate_token = os.environ.get("REPLICATE_API_TOKEN")
        if not replicate_token:
            return jsonify({"success": False, "error": "Service temporarily unavailable."})

        client = replicate.Client(api_token=replicate_token)
        output = client.run(
            "xai/grok-imagine-image",
            input={
                "prompt": prompt + ", high quality, cinematic",
                "aspect_ratio": "1:1",
                "num_outputs": 1
            }
        )
        if isinstance(output, list) and output:
            url = str(output[0])
        elif hasattr(output, "url"):
            url = str(output.url)
        else:
            url = str(output)

        log.append(now)
        _LANDING_DEMO_IP[ip] = log
        log_system_event("info", "landing_demo", f"ip={ip} prompt={prompt[:60]}", None)

        return jsonify({
            "success": True,
            "image_url": url,
            "telegram_link": f"https://t.me/{BOT_USERNAME}"
        })
    except Exception as e:
        logger.error(f"landing demo err: {e}")
        return jsonify({"success": False, "error": "Generation failed. Please try the Telegram bot."})

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

# ==================== SISTEMA DE CONTROLO ADMIN (NOVOS) ====================
USER_FLAGS_FILE = "user_flags.json"           # ban, shadowban, mute, tags, nsfw_allowed
REPORTS_FILE = "reports.json"                 # reports de utilizadores
SYSTEM_LOGS_FILE = "system_logs.json"         # eventos/erros internos
SYSTEM_CONFIG_FILE = "system_config.json"     # flags globais (nsfw, maintenance, etc.)

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
FLAGS_LOCK = Lock()
REPORTS_LOCK = Lock()
SYSLOGS_LOCK = Lock()
SYSCFG_LOCK = Lock()

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

# ==================== SISTEMA GOD-MODE ADMIN (CONFIG GLOBAL) ====================
DEFAULT_SYSTEM_CONFIG = {
    "nsfw_enabled": True,           # SEMPRE permitido — Replicate decide
    "maintenance_mode": False,
    "generation_disabled": False,
    "safe_mode": False,
    "rate_limit_per_min": 10,
    "nsfw_keywords": []             # VAZIO — sem filtro de palavras-chave
}

def get_system_config():
    """Carrega config do sistema com defaults."""
    cfg = load_json(SYSTEM_CONFIG_FILE)
    if not cfg:
        cfg = dict(DEFAULT_SYSTEM_CONFIG)
        save_json(SYSTEM_CONFIG_FILE, cfg, SYSCFG_LOCK)
        return cfg
    # Mergeia defaults para novas keys
    merged = dict(DEFAULT_SYSTEM_CONFIG)
    merged.update(cfg)
    return merged

def set_system_config(key, value):
    cfg = get_system_config()
    cfg[key] = value
    save_json(SYSTEM_CONFIG_FILE, cfg, SYSCFG_LOCK)
    return cfg

# ==================== FLAGS DE UTILIZADORES ====================
def get_user_flags(user_id):
    """Retorna flags do user (ban, shadowban, mute, tags, nsfw_allowed)."""
    data = load_json(USER_FLAGS_FILE)
    uid = str(user_id)
    if uid not in data:
        return {
            "banned": False,
            "shadowbanned": False,
            "muted_until": 0,
            "tags": [],
            "nsfw_allowed": False,
            "last_activity": 0,
            "reports_count": 0
        }
    f = data[uid]
    # Defaults para keys em falta
    f.setdefault("banned", False)
    f.setdefault("shadowbanned", False)
    f.setdefault("muted_until", 0)
    f.setdefault("tags", [])
    f.setdefault("nsfw_allowed", False)
    f.setdefault("last_activity", 0)
    f.setdefault("reports_count", 0)
    return f

def set_user_flag(user_id, key, value):
    data = load_json(USER_FLAGS_FILE)
    uid = str(user_id)
    if uid not in data:
        data[uid] = {}
    data[uid][key] = value
    save_json(USER_FLAGS_FILE, data, FLAGS_LOCK)

def add_user_tag(user_id, tag):
    flags = get_user_flags(user_id)
    tags = flags.get("tags", [])
    if tag not in tags:
        tags.append(tag)
    set_user_flag(user_id, "tags", tags)

def remove_user_tag(user_id, tag):
    flags = get_user_flags(user_id)
    tags = [t for t in flags.get("tags", []) if t != tag]
    set_user_flag(user_id, "tags", tags)

def has_tag(user_id, tag):
    return tag in get_user_flags(user_id).get("tags", [])

def is_vip(user_id):
    return has_tag(user_id, "VIP")

def touch_user_activity(user_id):
    set_user_flag(user_id, "last_activity", int(time.time()))

# ==================== RATE LIMITING (IN-MEMORY SLIDING WINDOW) ====================
_rate_buckets = {}  # {user_id: [timestamps]}
_rate_lock = Lock()

def check_rate_limit(user_id):
    """Retorna (allowed, remaining). Admin ignora."""
    if is_any_admin(user_id):
        return True, 999
    cfg = get_system_config()
    limit = int(cfg.get("rate_limit_per_min", 10))
    if cfg.get("safe_mode"):
        limit = max(3, limit // 2)
    now = time.time()
    cutoff = now - 60
    with _rate_lock:
        bucket = _rate_buckets.get(user_id, [])
        bucket = [t for t in bucket if t > cutoff]
        if len(bucket) >= limit:
            _rate_buckets[user_id] = bucket
            return False, 0
        bucket.append(now)
        _rate_buckets[user_id] = bucket
        return True, limit - len(bucket)

# ==================== NSFW FILTER ====================
# DESATIVADO - O Grok ja faz a sua propria moderacao do lado da Replicate.
# Nao bloqueamos por palavras-chave do nosso lado para nao bloquear NSFW leve
# que o modelo de facto aceita gerar.
def check_nsfw_prompt(prompt):
    """Sempre permite. A moderacao fica a cargo do modelo (Replicate)."""
    return False, None

# ==================== LOGS DE SISTEMA ====================
MAX_SYSTEM_LOGS = 500

def log_system_event(level, category, message, user_id=None):
    """Adiciona evento aos logs do sistema (rolling)."""
    try:
        data = load_json(SYSTEM_LOGS_FILE)
        logs = data.get("logs", [])
        logs.insert(0, {
            "ts": int(time.time()),
            "level": level,  # info, warn, error, payment, nsfw, ban
            "category": category,
            "message": str(message)[:500],
            "user_id": user_id
        })
        logs = logs[:MAX_SYSTEM_LOGS]
        data["logs"] = logs
        save_json(SYSTEM_LOGS_FILE, data, SYSLOGS_LOCK)
    except Exception as _e:
        pass

# ==================== REPORTS ====================
def add_report(reporter_id, reported_user_id, reason):
    data = load_json(REPORTS_FILE)
    reports = data.get("reports", [])
    report_id = f"r{int(time.time()*1000)}"
    reports.insert(0, {
        "id": report_id,
        "reporter_id": reporter_id,
        "reported_user_id": reported_user_id,
        "reason": str(reason)[:500],
        "ts": int(time.time()),
        "status": "pending"  # pending, banned, ignored, safe
    })
    data["reports"] = reports[:1000]
    save_json(REPORTS_FILE, data, REPORTS_LOCK)
    # incrementa contador no user reportado
    flags = get_user_flags(reported_user_id)
    set_user_flag(reported_user_id, "reports_count", int(flags.get("reports_count", 0)) + 1)
    return report_id

def update_report_status(report_id, status):
    data = load_json(REPORTS_FILE)
    for r in data.get("reports", []):
        if r.get("id") == report_id:
            r["status"] = status
            break
    save_json(REPORTS_FILE, data, REPORTS_LOCK)

def get_pending_reports(limit=20):
    data = load_json(REPORTS_FILE)
    return [r for r in data.get("reports", []) if r.get("status") == "pending"][:limit]

# ==================== SAFETY GATE (CHAMADO EM TODA A GERACAO) ====================
def check_user_allowed(user_id, prompt=None, check_rate=True):
    """Verifica se o user pode gerar. ADMIN IGNORA TUDO.
    Retorna (allowed: bool, reason: str, extra: dict).
    reason pode ser:
      - 'ok' (pode continuar)
      - 'admin_bypass' (admin, ignora tudo)
      - 'maintenance' | 'generation_off' | 'banned' | 'shadowban'
      - 'rate_limit' | 'nsfw_blocked' (com extra.keyword)
    extra: {'keyword': str} se nsfw, {'retry_in': int} se rate_limit
    """
    # Admin = GOD MODE
    if is_any_admin(user_id):
        touch_user_activity(user_id)
        return True, "admin_bypass", {}

    cfg = get_system_config()

    if cfg.get("maintenance_mode"):
        return False, "maintenance", {}

    if cfg.get("generation_disabled"):
        return False, "generation_off", {}

    flags = get_user_flags(user_id)

    if flags.get("banned"):
        return False, "banned", {}

    # Rate limit
    if check_rate:
        ok, remaining = check_rate_limit(user_id)
        if not ok:
            return False, "rate_limit", {"retry_in": 60}

    # NSFW check - DESATIVADO. A moderacao fica do lado da Replicate (modelo decide).
    # if prompt:
    #     is_nsfw, kw = check_nsfw_prompt(prompt)
    #     ...

    # Shadowban: deixa passar mas sinaliza (caller decide ignorar/fake)
    if flags.get("shadowbanned"):
        touch_user_activity(user_id)
        return True, "shadowban", {}

    touch_user_activity(user_id)
    return True, "ok", {}

def deny_message(lang, reason, extra=None):
    """Mensagem traduzida para bloquear o user."""
    extra = extra or {}
    msgs = {
        "maintenance": {
            "pt": "🛠️ O bot está em <b>modo manutenção</b>. Volta mais tarde.",
            "en": "🛠️ Bot is in <b>maintenance mode</b>. Please try later.",
            "es": "🛠️ El bot está en <b>modo mantenimiento</b>. Vuelve más tarde."
        },
        "generation_off": {
            "pt": "⛔ Geração de imagens temporariamente desativada pelo admin.",
            "en": "⛔ Image generation temporarily disabled by admin.",
            "es": "⛔ Generación de imágenes desactivada por el admin."
        },
        "banned": {
            "pt": "🚫 A tua conta foi <b>banida</b>. Contacta o suporte se achas que foi um erro.",
            "en": "🚫 Your account has been <b>banned</b>. Contact support if you think this is a mistake.",
            "es": "🚫 Tu cuenta fue <b>baneada</b>. Contacta al soporte si crees que es un error."
        },
        "rate_limit": {
            "pt": "⏳ Muitos pedidos! Aguarda 1 minuto e tenta novamente.",
            "en": "⏳ Too many requests! Wait 1 minute and try again.",
            "es": "⏳ ¡Demasiados pedidos! Espera 1 minuto e intenta de nuevo."
        },
        "nsfw_blocked": {
            "pt": f"🔞 Prompt bloqueado pelo filtro de conteúdo (palavra: <code>{extra.get('keyword','')}</code>).",
            "en": f"🔞 Prompt blocked by content filter (word: <code>{extra.get('keyword','')}</code>).",
            "es": f"🔞 Prompt bloqueado por el filtro (palabra: <code>{extra.get('keyword','')}</code>)."
        }
    }
    m = msgs.get(reason, {"pt": "❌ Operação não permitida.", "en": "❌ Not allowed.", "es": "❌ No permitido."})
    return m.get(lang, m["pt"])



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
    3: {"nome": "Pacote Pro", "creditos": 600, "preco": 2200}
}

def get_user_credits(user_id):
    data = load_json(CREDITS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            "creditos": 30,
            "total_usado": 0,
            "historico": [],
            "created_at": datetime.now().isoformat()
        }
        save_json(CREDITS_FILE, data, CREDITS_LOCK)
        logger.info(f"Novo usuário {user_id} com 30 créditos")
        
        # 🆕 NOTIFICAÇÃO INSTANTÂNEA
        try:
            for admin_id in ADMIN_IDS:
                bot.send_message(
                    admin_id,
                    f"🎉 <b>NOVO USUÁRIO!</b>\n\n"
                    f"👤 ID: <code>{user_id}</code>\n"
                    f"💳 Créditos iniciais: 30\n"
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
    # 🔓 Hook: qualquer compra paga (não reembolso/bonus) desbloqueia/renova premium
    try:
        if tipo in ("compra", "purchase", "stripe", "stripe_purchase", "manual_admin"):
            grant_premium_access(user_id)
    except Exception as _e:
        logger.warning(f"Falha ao conceder premium em add_credits: {_e}")
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
    "nome": "🎨 Modelo Padrão",
    "desc": "Criação e edição de imagens (Grok)",
    "replicate_id": "xai/grok-imagine-image",
    "custo": 10
}

MODELO_PRO = {
    "nome": "✨ Modelo Pro",
    "desc": "Edição fotorrealista avançada (Qwen / FLUX.2 Klein 9B)",
    "replicate_id": "black-forest-labs/flux-2-klein-9b",
    "custo": 18,
    "prompt_fixo": "make it more realistic"
}

PRO_PRESETS = {
    "original": {
        "nome": "📷 Original",
        "prompt": "You are an AI that specializes in image editing descriptions that emphasize photorealism and focuses on edits to look like real life photographic images. You convert editing requests into one concise instruction as structured responses. You focus on adhering to photorealistic style and realistic details while ensuring the importance of keeping the composition and structure of the image same as reference. Ensure subjects are accurately represented and that their identity is maintained. You focus on photography with emphasis on details while ensuring the importance of keeping the structure of the image intact as well and not changing the positioning of subjects in image while managing to modify the style to look real. Reference actual image elements. Make abstractions concrete. Follow edit requests without hesitation. Keep pose. Keep angle. Keep colors. Keep composition. Keep viewing direction. Modify any subjects appearance to show real details while keeping colors the same. Make the it look like a professional photograph. Keep subject position and their pose the same as the reference. Ensure image looks real. Make sure anatomy is accurately represented. Normal anatomy. Keep body color. Keep subject position and their pose the same as the reference. Make sure the subject is in the same position. Keep pose. Keep lighting direction accurate for the scene. Keep shadows accurate for the scene. Keep in focus. The result should be a professional photograph."
    },
    "expression": {
        "nome": "🎭 Expressao Fiel",
        "prompt": "You are an AI that specializes in image editing descriptions for photorealistic results while strictly preserving the original subject and scene. Create concise edit instructions that make the image look like a real-life professional photograph without changing the identity or core appearance of the subject. Preserve exactly: facial expression, emotional tone and mood, apparent age, facial structure, identity, gaze direction, head angle, pose, body proportions, camera angle, framing, composition, subject position, hairstyle and hair length, skin tone, lighting direction, shadows, color relationships. Keep the same expression as the reference image. Do not invent a new expression. Do not change mouth shape, smile intensity, eyebrow position, eyelid tension, cheek tension, or eye openness unless explicitly requested. Keep the subject looking the same age as in the reference. Do not add age. Do not make the subject look older or younger. Avoid exaggerated pores, wrinkles, smile lines, crows feet, forehead lines, under-eye hollows, skin roughness, or other age-related detail unless clearly visible in the original and necessary to preserve likeness. Enhance realism through natural photographic detail, believable skin texture, accurate anatomy, and realistic lighting, but do not introduce extra facial detail that changes perceived age, mood, or identity. The output should look like a realistic photograph of the same person in the same moment, with the same expression, same age, and same overall appearance as the reference."
    },
    "softer": {
        "nome": "✨ Realismo Suave",
        "prompt": "You are an AI that converts edit requests into concise photorealistic image editing instructions. Make the image look like a real professional photograph while preserving the original subject exactly. Preserve identity, facial expression, emotional tone, apparent age, facial structure, gaze direction, head angle, pose, composition, framing, subject position, hairstyle, skin tone, lighting direction, shadows, and colors. Keep the exact same expression as the reference image. Do not invent a new expression. Do not change the mouth shape, smile, eyebrows, eyelids, cheeks, or eye openness unless explicitly requested. Keep the exact same apparent age. Do not make the subject older or younger. Avoid adding extra wrinkles, pores, skin roughness, smile lines, forehead lines, crows feet, or under-eye detail that changes age or likeness. Increase realism without changing the person, the moment, or the mood."
    }
}

MODELO_ARTISTICO = {
    "nome": "🎭 Modelo Artistico",
    "desc": "Transforma fotos em diferentes estilos artisticos",
    "replicate_id": "black-forest-labs/flux-2-klein-9b",
    "custo": 13
}


# ==================== NOVOS PRESETS DE REALISMO ====================
# Adicionados ao submenu "📷 Deixa mais realista" do Modelo Pro
PRO_REALISM_EXTRA = {
    "cinematic": {
        "nome": "🔥 Realismo Cinematográfico",
        "prompt": "Transform this photo into a cinematic masterpiece with hyper-realistic detail. Apply dramatic cinematic lighting with strong key light and soft fill, deep shadows, anamorphic lens flares, shallow depth of field, teal-and-orange color grading, film grain, 35mm cinematic look, ultra-sharp focus on the subject. Render the skin with realistic micro-texture, lifelike pores, natural subsurface scattering, accurate eye reflections and catchlights. Preserve the exact identity, facial structure, expression, pose, hairstyle, body proportions, framing, composition and camera angle of the original. Do not invent new features. The final result must look like a still frame from a high-budget Hollywood film, photorealistic, 8k, masterpiece."
    },
    "ultra_real": {
        "nome": "🌟 Ultra Realista (Fotografia Profissional)",
        "prompt": "Convert this image into ultra-photorealistic professional photography. Use a full-frame DSLR aesthetic, 85mm f/1.4 lens, perfect natural lighting, true-to-life colors, accurate white balance, razor-sharp focus on the eyes, ultra-detailed skin texture with realistic pores, fine hair strands, natural skin tones, lifelike eye reflections. Avoid plastic or AI-looking skin. Preserve identity, facial features, expression, age, pose, hairstyle, outfit, body proportions, framing and composition exactly as the reference. The result must look like a real photograph taken by a professional photographer, high resolution, 8k, masterpiece quality."
    },
    "iphone": {
        "nome": "📸 Estilo iPhone / Selfie Natural",
        "prompt": "Transform this photo to look like a natural high-quality smartphone selfie shot on a modern iPhone. Apply soft natural daylight, realistic skin tones, slight HDR, mild lens distortion typical of a front camera, natural ambient lighting, true-to-life colors, candid casual feel. Keep skin texture realistic with subtle pores and natural softness — never plastic or over-smoothed. Preserve identity, expression, pose, hairstyle, age and composition exactly. The result must look like a real, casual, authentic selfie/phone photo, photorealistic and believable, sharp but not over-processed."
    },
    "studio": {
        "nome": "🖼️ Estilo Studio / Retrato Profissional",
        "prompt": "Transform this image into a professional studio portrait. Apply soft three-point studio lighting with a large key softbox, gentle fill, subtle rim/hair light, clean seamless backdrop, perfectly balanced exposure, gentle catchlights in the eyes, beautifully sharp focus on the face. Render skin with high-end retouching realism: natural pores, smooth but not plastic texture, perfect color grading, magazine-quality finish. Preserve identity, facial structure, expression, age, pose, hairstyle, outfit, framing and composition exactly as the reference. The result must look like a high-end editorial studio portrait shot by a top photographer, photorealistic, 8k, masterpiece."
    },
}


# ==================== ESTILO & HUMOR (PRO) ====================
PRO_STYLE_MOOD = {
    "smile": {
        "nome": "😊 Sorriso Natural",
        "prompt": "Adjust the subject's expression to a warm, natural, genuine smile with soft eye crinkle (Duchenne smile). Slightly lift the corners of the mouth, show a hint of teeth naturally, relaxed eyes, friendly warm vibe, authentic and effortless feel. Keep skin texture realistic, photorealistic rendering. Preserve identity, facial structure, age, hairstyle, pose, body, framing, lighting and composition exactly as the reference. The result must look like a real photograph with a believable, natural smile, ultra-detailed, 8k, professional photography quality."
    },
    "seductive": {
        "nome": "😉 Olhar Sedutor / Confiante",
        "prompt": "Adjust the subject's expression to a confident, subtly seductive look. Slight smolder, softly parted lips, relaxed jaw, intense focused gaze toward the camera, one eyebrow very slightly raised, calm self-assured energy. Keep it elegant and tasteful, never exaggerated. Preserve identity, facial structure, age, hairstyle, pose, body proportions, outfit, lighting, framing and composition exactly. Photorealistic skin with realistic texture, sharp eyes with natural catchlights, high-end editorial quality, 8k, masterpiece."
    },
    "model": {
        "nome": "😎 Pose de Modelo / Fashion",
        "prompt": "Restyle this photo into a high-fashion model shot. Apply confident editorial pose energy, strong jawline emphasis, sharp cheekbones lighting, fashion magazine attitude, aloof and powerful expression, clean styling. Use high-end fashion photography lighting (Vogue / Harper's Bazaar style), professional color grading, ultra-sharp details, perfect skin texture, lifelike pores. Preserve identity, facial features, age, hairstyle, outfit, body proportions, framing and composition exactly. Photorealistic, 8k, masterpiece editorial quality."
    },
    "intense": {
        "nome": "🔥 Expressão Intensa / Dramática",
        "prompt": "Transform the subject's expression into an intense, dramatic look. Slightly furrowed brow, focused piercing gaze, lips closed or slightly tense, strong emotional presence, brooding cinematic energy. Apply dramatic chiaroscuro lighting with deep shadows and strong highlights, moody atmosphere, cinematic color grading. Keep skin photorealistic with natural texture and pores, sharp eyes with catchlights. Preserve identity, facial structure, age, hairstyle, pose, framing and composition exactly. 8k, ultra-detailed, masterpiece cinematic photography."
    },
    "romantic": {
        "nome": "❤️ Vibe Romântica / Suave",
        "prompt": "Restyle this photo with a soft, romantic and dreamy vibe. Apply warm golden-hour lighting, soft diffused glow, gentle bokeh, pastel romantic color grading, soft skin glow while keeping realistic pores and texture. The expression should be calm, soft, slightly smiling, eyes warm and tender. Preserve identity, facial structure, age, hairstyle, pose, outfit, framing and composition exactly. Photorealistic, lifelike, ultra-detailed, 8k, fine-art portrait quality."
    },
    "fun": {
        "nome": "😂 Expressão Divertida / Memes",
        "prompt": "Adjust the subject's expression to a fun, playful, slightly exaggerated meme-style look — laughing out loud, big genuine smile with visible teeth, eyes squinting from laughter or wide in surprise, energetic happy vibe, candid spontaneous feel. Keep it natural and authentic, not creepy. Vivid colors, sharp focus, photorealistic skin texture. Preserve identity, facial features, age, hairstyle, pose, outfit, framing and composition exactly. 8k, ultra-detailed, real photograph look."
    },
    "fullbody": {
        "nome": "🕴️ Pose Full Body Profissional",
        "prompt": "Restyle this image into a professional full-body editorial shot. If needed, extend the framing to show the entire body in a confident standing pose, weight on one leg, relaxed shoulders, hands placed naturally, strong posture, modeling stance. Apply professional studio or location lighting, balanced exposure, high-end fashion photography aesthetic, ultra-sharp focus, photorealistic skin and fabric textures. Preserve identity, facial features, age, hairstyle, outfit and overall look exactly as the reference. 8k, masterpiece editorial photography quality."
    },
}


# ==================== ENHANCEMENTS AVANÇADOS (PRO) ====================
PRO_ENHANCEMENTS = {
    "lighting": {
        "nome": "🔦 Melhorar Iluminação e Sombras",
        "prompt": "Dramatically enhance the lighting and shadows of this image while preserving the subject exactly. Apply professional photography lighting: balanced key light, soft fill, subtle rim light, natural directional shadows, accurate light falloff, beautiful highlight rolloff, deep but detailed shadows, perfectly exposed midtones, cinematic atmosphere. Maintain the existing scene, mood and color palette but make the lighting look intentional, professional and three-dimensional. Preserve identity, facial features, expression, age, pose, hairstyle, outfit, framing and composition exactly. Photorealistic, ultra-detailed, 8k, masterpiece."
    },
    "skin_hair": {
        "nome": "💇 Melhorar Cabelo, Pele e Textura",
        "prompt": "Enhance the skin, hair and natural textures with photorealistic quality. Render skin with realistic pores, subtle micro-texture, natural subsurface scattering, healthy glow, even tone, no plastic/AI look. Render hair with individually defined strands, natural shine, realistic flow, accurate roots and ends, true-to-life color depth. Preserve identity, facial structure, age, expression, pose, hairstyle shape, outfit, lighting and composition exactly as the reference. The result must look like a high-end retouched professional portrait — refined but believable, never over-smoothed. 8k, ultra-detailed, masterpiece."
    },
    "outfit": {
        "nome": "👔 Melhorar Roupa e Detalhes da Vestimenta",
        "prompt": "Enhance the clothing and outfit details with photorealistic precision. Render fabric with accurate weave, realistic folds, natural drape, subtle wrinkles, true material textures (cotton, denim, leather, silk, knit, etc.), accurate stitching, buttons, zippers, logos and small details. Improve color depth, contrast and material finish for a high-end fashion look. Preserve the exact same outfit type, color, cut and style as the reference — do NOT change the clothes. Preserve identity, facial features, expression, age, hairstyle, pose, body proportions, framing, lighting and composition exactly. 8k, ultra-detailed, editorial fashion photography quality."
    },
    "color": {
        "nome": "🌈 Cores Vibrantes e Correção de Cor",
        "prompt": "Apply professional color grading and color correction. Boost color vibrancy without oversaturating, achieve perfectly balanced white balance, true-to-life skin tones, rich blacks, clean whites, beautiful tonal contrast, cinematic palette. Make colors pop with depth and harmony, like a professional photo edit in Lightroom/Capture One. Preserve identity, facial features, expression, age, pose, hairstyle, outfit, framing and composition exactly. Keep the scene realistic and the lighting natural. Photorealistic, 8k, ultra-detailed, masterpiece quality."
    },
    "eyes": {
        "nome": "🧿 Olhos Mais Vivos e Expressivos",
        "prompt": "Enhance the eyes with photorealistic detail and life. Render irises with rich color depth, fine radial fiber detail, natural variations, sharp pupils, beautiful clean catchlights matching the scene's lighting, realistic moisture and reflections, well-defined eyelashes, natural eyelid shape. Make the gaze feel alive, expressive and emotionally engaging while preserving the exact same eye color, eye shape and direction of look as the reference. Preserve identity, facial structure, expression, age, pose, hairstyle, outfit, framing and composition exactly. 8k, ultra-detailed, masterpiece portrait photography."
    },
    "max": {
        "nome": "✨ Geral + Detalhes Máximos",
        "prompt": "Apply a complete top-tier professional enhancement to this image. Maximize realism and detail across the entire photo: ultra-sharp focus, photorealistic skin with natural pores, lifelike hair with individual strands, expressive eyes with perfect catchlights, realistic fabric and outfit textures, professional cinematic lighting, accurate balanced color grading, deep tonal range, perfect exposure, fine micro-details everywhere, high dynamic range, magazine-cover finish. Preserve identity, facial features, expression, age, pose, hairstyle, outfit, framing and composition exactly. The final result must look like a flawless high-end professional photograph, photorealistic, 8k, ultra-detailed, masterpiece quality."
    },
}


# ==================== ESTILOS DO MODELO PADRÃO (Grok) ====================
# Estilos com prompt fixo aplicados quando o user envia foto + descrição
# e clica em "🎨 Escolher Estilo" no Modelo Padrão.
# {subject_token} é substituído pelo género de referência (the man / the woman / the person).
# A descrição do user é anexada no fim como reforço.

# Tag "preserve identity" usada como trailer comum
_IDENT_TRAIL = "preserve identity, keep same face, keep facial structure, keep skin tone, maintain original identity, do not change person, realistic face consistency, preserve original facial expression, keep same emotion, keep same eye expression, keep same pose"


PADRAO_STYLES = {
    # ===== HOMENS (5) =====
    "men_underwater": {
        "nome": "🌊 Submerso Cinematográfico",
        "cat": "men",
        "subject": "the man",
        "prompt": "Edit This close-up photograph of [subject] submerged underwater, half of the body exposed from chest to head, occupies the center frame. With a serious expression. Eyes open and directed towards the viewer. Appears shirtless. The water's surface, with its manipulated light, creates caustic patterns on the skin. Slightly suspended water droplets and bubbles add depth. Cinematic lighting with soft shadows and sharp highlights, and realistic textures create an intricate pattern of light and shadow on the face and upper body. The background is a color gradient between greenish-blue and dark blue, with scattered air bubbles, suggesting a deep environment. The lighting is diffused, casting soft shadows, enhancing the underwater atmosphere. The overall style of the image is photographic and realistic, with an emphasis on capturing the details of the water's effect on the person in 4k resolution, " + _IDENT_TRAIL,
    },
    "men_luxury": {
        "nome": "🕶️ Luxury Glamour Dourado",
        "cat": "men",
        "subject": "the man",
        "prompt": "Edit this image to show a [subject] positioned in a close-up portrait shot, face tilted slightly upward at approximately 15–20 degrees with the chin gently lifted, creating a confident, aspirational angle. The head is centered in the frame with the gaze directed straight toward the camera from behind the sunglasses. Wearing vintage-inspired round eye sunglasses with molten black-to-grey gradient lenses and matte black frames with delicate etched details, positioned perfectly on the bridge of the nose. The body is angled slightly (about 30 degrees) to create dimension, with shoulders relaxed and one shoulder subtly closer to the camera. Exuding magnetic confidence with a sultry pout. Wearing a luxurious black blazer. The background is a rich, saturated golden-yellow that transitions to deeper amber tones at the edges. Dramatic directional lighting from above-left creates sculptural shadows along the neck and cheekbones, with warm backlighting creating a subtle halo effect. The composition is a style/fashion portrait with the face taking up roughly 60% of the frame, " + _IDENT_TRAIL,
    },
    "men_lowkey": {
        "nome": "🖤 Low-Key Profissional",
        "cat": "men",
        "subject": "the man",
        "prompt": "professional studio portrait, [subject], confident and determined expression, head slightly tilted down, wearing a black V-neck t-shirt. Using a low-key photography setup with butterfly lighting (key light from front above), a hair rim light from behind, and a faint background light. The atmosphere is filled with a subtle haze or smoke. Shot on a medium format camera, high contrast, cinematic, sharp focus, soft shadows. The atmosphere has a subtle haze. Hyper-realistic, shot on a 85mm lens, sharp focus on eyes, detailed facial features. --ar 4:5 --style raw, " + _IDENT_TRAIL,
    },
    "men_redstudio": {
        "nome": "🔴 Don Vermelho (Estúdio)",
        "cat": "men",
        "subject": "the man",
        "prompt": "Usando a imagem de referência e preservando a fisionomia, crie uma imagem com os seguintes parâmetros: Retrato ultrarrealista de estúdio, 4K, detalhes nítidos, iluminação cinematográfica, alto contraste. [subject] usando óculos de sol pretos retangulares, um terno preto impecável com uma camisa social preta por baixo (sem gravata), correntes de prata grossas no pescoço com pingentes (um medalhão e outro redondo/moeda), brincos de diamante redondos pequenos, uma pulseira de corrente de prata grossa e anéis de prata grossos nos dedos. Expressão facial séria e confiante. O fundo é uma parede vermelha sólida e vibrante, com um efeito de desfoque de movimento horizontal na cor vermelha, criando dinamismo. A câmera está em um ângulo frontal, meio diagonal, ligeiramente alto, lente de 50mm, abertura f/1.8, ISO 200, foco no modelo e desfoque de fundo, " + _IDENT_TRAIL,
    },
    "men_darkhero": {
        "nome": "🦸 Herói Sombrio Editorial",
        "cat": "men",
        "subject": "the man",
        "prompt": "Um retrato editorial de alta costura em 8K altamente detalhado, apresentando [subject]. Use o rosto da imagem de referência com total fidelidade. NÃO mudar o rosto. Figura masculina com presença poderosa, vestindo um traje escuro com um símbolo vermelho estilizado no peito, em uma pose confiante com braços cruzados e olhar direto. Fundo com gradiente em tons avermelhados, do vermelho escuro nas bordas para tons mais brilhantes no centro, destacando a figura. Iluminação dramática com jogo de luz e sombra enfatizando volume, textura e contornos do traje. Estilo inspirado em arte de super-heróis e editorial de moda. Atmosfera intensa, misteriosa e poderosa. " + _IDENT_TRAIL,
    },

    # ===== MULHERES (4) =====
    "wom_baton": {
        "nome": "💄 Baton Rouge Editorial",
        "cat": "women",
        "subject": "the woman",
        "prompt": "Use the reference photo and make an ultra-realistic close-up portrait, [subject] wearing an elegant strapless black suit, seductive and confident expression, striking red lipstick, dramatic fashion lighting with a soft circular spotlight in the background, cinematic aesthetic of beauty editorial photography, ultra HD, " + _IDENT_TRAIL,
    },
    "wom_coffee": {
        "nome": "☕ Café Editorial Bege",
        "cat": "women",
        "subject": "the woman",
        "prompt": "A full-length studio photograph with a professional and elegant aesthetic. It captures [subject] seated in a light wooden chair with a seat and back upholstered in light fabric and straw accents. The subject sits in a confident and relaxed pose, slightly turned toward the camera, with a gentle smile. One hand rests on the arm of the chair, and the legs are crossed at the ankles. Wearing a suit (blazer and pants) in a neutral tone (light beige or gray-green) over a white or cream top. On the feet are light-colored high-heeled shoes with ankle straps. Wearing delicate jewelry: a necklace with a pendant, earrings, and rings. Nails painted a vibrant red. Hair styled medium-length with soft waves, combed to the side. The background is a solid-colored studio backdrop in a uniform, light brown tone. The lighting is studio-style, soft, and directional, coming from a frontal-upward angle. Captured with a prime portrait lens (85mm) on a full-frame camera, f/4.5, ISO 100, 1/200s. Studio lighting with a large softbox as the main light. " + _IDENT_TRAIL,
    },
    "wom_mirror": {
        "nome": "📱 Selfie Espelho Confiante",
        "cat": "women",
        "subject": "the woman",
        "prompt": "A full-length mirror or selfie photograph with a casual, modern aesthetic, featuring [subject] standing against a dark wall, looking at the camera with a serious, confident expression. One hand raised holding a cell phone taking the photo, the other playing with the hair. Wearing a black cropped top with a red print and short tight denim shorts. Discreet tattoos visible on the abdomen. Wearing a necklace with a heart pendant. Hair long, dark, styled with straight bangs and two thick braids over the shoulders. Dramatic makeup with winged eyeliner and lipstick. Background minimal dark wall. Lighting diffuse and soft from the front, highlighting face and clothing without harsh shadows. Camera: high-quality phone selfie, 24-35mm equivalent, f/1.8, ISO 200, 1/125s. " + _IDENT_TRAIL,
    },
    "wom_softselfie": {
        "nome": "✨ Selfie Suave & Glow",
        "cat": "women",
        "subject": "the woman",
        "prompt": "Create a soft aesthetic selfie featuring [subject] with a gentle confident expression. Lighting warmer and softer, dreamy glow on the skin. Background is a smooth dark wall. Outfit casual modern. Soft natural makeup. Overall mood calm, refined, and gentle while keeping a believable phone-selfie look. Camera: phone selfie, 35mm, f/2.0, ISO 200. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Retratos Clássicos (4) =====
    "u_joker": {
        "nome": "🃏 Joker Dualidade",
        "cat": "unisex", "grp": "classic",
        "subject": "the person",
        "prompt": "Generate a striking portrait with a central theme of duality and hidden identity. The image should feature [subject] holding a Joker-style clown mask in front of the face. The subject should be depicted in grayscale, suggesting a somber or desaturated reality, with a thoughtful or melancholic expression in the visible eye. The hand, holding the mask, should be detailed and possibly gloved or armored, also in grayscale. The clown mask, however, should be in vibrant color, with its classic red smile, red nose, and blue markings around the eyes, appearing vivid and unsettlingly cheerful. The background should be dark and minimalistic to emphasize the contrast between the subject and the mask. " + _IDENT_TRAIL,
    },
    "u_rembrandt": {
        "nome": "🎨 Rembrandt Clássico",
        "cat": "unisex", "grp": "classic",
        "subject": "the person",
        "prompt": "Generate a realistic portrait styled after a 17th-century Dutch oil painting, [subject], with classic Rembrandt lighting (Chiaroscuro), a single soft light source illuminating one side of the face against a dark, moody background. The final image should have the rich color palette, deep shadows, and subtle texture of an oil painting on canvas, with fine, visible brushstrokes. Calm and introspective expression, capturing a quiet, timeless moment, " + _IDENT_TRAIL,
    },
    "u_facepost": {
        "nome": "🖼️ Pôster Tinta Editorial",
        "cat": "unisex", "grp": "classic",
        "subject": "the person",
        "prompt": "Convert this image into an editorial art-poster in extreme close-up, half-frame composition; [subject]; thick impasto oil-paint texture with palette-knife strokes forming realistic features, teal-green iris with sharp catchlight, lips and skin rendered in layered paint ridges; abstract paint blocks in matte black and deep yellow overlapping the left side like chipped panels; subtle paper grain and micro-cracks; clean poster edges, deep vignette and soft studio background blur for focus; lighting: soft museum key light from upper left with gentle speculars on paint peaks, HDR exposure, high local contrast; optical language: 85mm portrait look, f/2.8, ISO 100, 1/160s, shallow depth isolating the eye; output intent: ultra-sharp, high-frequency paint detail, print-ready, " + _IDENT_TRAIL,
    },
    "u_corporate": {
        "nome": "📰 Corporativo P&B",
        "cat": "unisex", "grp": "classic",
        "subject": "the person",
        "prompt": "Black and white editorial magazine portrait, focus on [subject] seated on a sofa, confident introspective expression, direct gaze to camera, relaxed pose with hand supporting the chin, light dress shirt with a few buttons open, soft side lighting creating contrast and depth, sophisticated interior with curtains and modern decor in the background, realistic skin and fabric texture, high sharpness, professional photographic quality, 85mm f/1.8 lens, cinematic monochrome style. Negative: blurry, cartoonish, oversaturated, smiling, colored image, low contrast. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Trilogia Leão (3) =====
    "u_lion_winter": {
        "nome": "❄️ Conexão Inverno",
        "cat": "unisex", "grp": "lion",
        "subject": "the person",
        "prompt": "Create a realistic and emotional scene showing [subject] and a lion face to face in a moment of connection and respect. Eyes closed, with a serene expression, while the lion gently rests its forehead and muzzle against the subject, conveying trust and a spiritual bond. Both are standing on ground covered in light snow, with snowflakes gently falling. Wearing a dark coat, hair slightly tousled by the wind, and the lion displays a thick, majestic mane. In the background, a cold, misty natural landscape with blurred mountains and gray tones reinforces the calm and powerful atmosphere. Soft diffuse natural winter light, ultra-realistic cinematic 8K. " + _IDENT_TRAIL,
    },
    "u_lion_desert": {
        "nome": "🏜️ Rei do Deserto",
        "cat": "unisex", "grp": "lion",
        "subject": "the person",
        "prompt": "Create a powerful cinematic scene showing [subject] and a lion face to face in a warm desert environment, symbolizing dominance and unity. Calm and confident expression, eyes slightly closed, while the lion stands firmly with its mane flowing in the wind. Golden sand dunes stretch across the background with a glowing sunset horizon. Warm orange and gold tones dominate the scene. Strong directional lighting from the side creates dramatic shadows and highlights on the face and lion's fur. Ultra-realistic, cinematic, 8K, golden hour. " + _IDENT_TRAIL,
    },
    "u_lion_shadow": {
        "nome": "🌑 Espírito Sombra",
        "cat": "unisex", "grp": "lion",
        "subject": "the person",
        "prompt": "Create a dark cinematic scene showing [subject] and a lion in a mysterious connection within a shadowy environment. Eyes closed, deep introspective expression, while the lion appears partially hidden in darkness. Background filled with fog, dark tones, and minimal light. A single soft light source illuminates the faces, creating strong contrast and chiaroscuro effect. The atmosphere should feel spiritual, intense, and symbolic. Ultra-realistic, dark cinematic, 8K, low-key lighting. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Music Phone (4) =====
    "u_phone_spotify": {
        "nome": "🎧 Spotify Gigante",
        "cat": "unisex", "grp": "phone",
        "subject": "the person",
        "prompt": "Create a stylish, modern photo in vertical 9:16 format using the reference image, featuring [subject] standing confidently on the giant screen of an iPhone 16 lying on the floor. The screen displays a Spotify playlist with the song 'Enter Sandman - Metallica.' Wearing AirPods Max, an oversized white hoodie, black pants, and crisp white Air Jordans. The scene is shot from a high angle, top-down, to emphasize the scale of the phone. Minimalist, stylish, futuristic vibe. " + _IDENT_TRAIL,
    },
    "u_phone_neon": {
        "nome": "🟣 Neon Music World",
        "cat": "unisex", "grp": "phone",
        "subject": "the person",
        "prompt": "Create a futuristic neon-style scene in vertical 9:16 format featuring [subject] standing on a giant smartphone screen displaying a music interface. The environment glows with purple and blue neon lights. Wearing headphones, oversized hoodie, and streetwear outfit. High-angle top-down shot emphasizing scale. Cyberpunk aesthetic with glowing reflections. " + _IDENT_TRAIL,
    },
    "u_phone_apple": {
        "nome": "🍏 Apple Minimal Luxo",
        "cat": "unisex", "grp": "phone",
        "subject": "the person",
        "prompt": "Create a clean luxury Apple-style photo in vertical 9:16 featuring [subject] standing on a giant smartphone screen in a minimalist white environment. The interface is sleek and modern with music playing. Wearing premium streetwear with a refined aesthetic. Shot from a high top-down angle with soft shadows and clean lighting. " + _IDENT_TRAIL,
    },
    "u_phone_street": {
        "nome": "🏙️ Street Music Energy",
        "cat": "unisex", "grp": "phone",
        "subject": "the person",
        "prompt": "Create a street-style scene in vertical 9:16 featuring [subject] standing on a giant phone screen placed on an urban ground surface. The screen shows a music player interface. Background includes subtle street textures like concrete and graffiti. Outfit is casual streetwear with strong attitude. Shot from top-down angle. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Editorial Fashion Pôster (2) =====
    "u_ed_future": {
        "nome": "🌸 Future Vision Pôster",
        "cat": "unisex", "grp": "editorial",
        "subject": "the person",
        "prompt": "Fashion editorial poster featuring [subject] in modern Japanese streetwear, standing against a minimal gradient background. Oversized typography at the top spells 'FUTURE VISION' in English, with smaller Japanese katakana characters beneath. Monochrome palette in neon pink. Ultra-modern, high-fashion poster design. " + _IDENT_TRAIL,
    },
    "u_ed_modern": {
        "nome": "🌷 Modern Edge Pôster",
        "cat": "unisex", "grp": "editorial",
        "subject": "the person",
        "prompt": "Fashion editorial poster featuring [subject] in modern streetwear with a luxury minimalist approach, standing against a soft neutral gradient background. Clean oversized typography reading 'MODERN EDGE' with subtle Japanese characters. Soft monochrome tones with light pink accents. Clean and elegant composition. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — B&W Studio Portraits (3) =====
    "u_bw_chiar": {
        "nome": "⚫ Chiaroscuro P&B",
        "cat": "unisex", "grp": "bw",
        "subject": "the person",
        "prompt": "Create a high-contrast black and white portrait based on the uploaded image, featuring [subject], keeping all facial features intact. Dramatic artistic studio photoshoot style. Use chiaroscuro lighting with a single strong key light from the side to create a Rembrandt lighting effect. Wearing a simple black turtleneck. Background is a dark, subtly textured studio canvas. The final image should feel intensely moody, powerful, and like a professionally captured photographic artwork. " + _IDENT_TRAIL,
    },
    "u_bw_hard": {
        "nome": "⬛ Sombras Duras",
        "cat": "unisex", "grp": "bw",
        "subject": "the person",
        "prompt": "Create a high-contrast black and white portrait featuring [subject] with extremely strong directional lighting casting deep, sharp shadows across the face. Dramatic studio setup with intense contrast and minimal fill light. Black background fading into darkness. Powerful and bold artistic mood. " + _IDENT_TRAIL,
    },
    "u_bw_soft": {
        "nome": "🌫️ Rembrandt Suave",
        "cat": "unisex", "grp": "bw",
        "subject": "the person",
        "prompt": "Create a black and white portrait featuring [subject] with classic Rembrandt lighting but softened for a more elegant and timeless look. Gentle shadow transitions, subtle highlights, and a refined artistic tone. Background remains dark with a soft texture. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Hacker Noir (3) =====
    "u_hk_noir": {
        "nome": "💻 Hacker Noir",
        "cat": "unisex", "grp": "hacker",
        "subject": "the person",
        "prompt": "A portrait using the reference image, featuring [subject] depicted as a hacker in a dark, rainy urban environment. Wearing a large hooded sweatshirt covering the head while keeping the face visible, looking directly at the camera. A computer screen reflects soft green code onto the face. Dramatic low-contrast lighting, with illumination mainly from the monitor and blurred streetlights in the background. Strong sense of isolation and paranoia. Grainy cinematic aesthetic, modern noir style, focus on technology and surveillance. " + _IDENT_TRAIL,
    },
    "u_hk_surv": {
        "nome": "🛰️ Estado de Vigilância",
        "cat": "unisex", "grp": "hacker",
        "subject": "the person",
        "prompt": "Create a dark cyber surveillance portrait featuring [subject] in a hooded outfit surrounded by subtle digital overlays and screen reflections. Green and blue code reflections illuminate the face. Background filled with blurred security cameras and digital noise. Low light, tense atmosphere, cinematic grain. " + _IDENT_TRAIL,
    },
    "u_hk_rain": {
        "nome": "🌧️ Hacker na Chuva",
        "cat": "unisex", "grp": "hacker",
        "subject": "the person",
        "prompt": "Create a rainy night portrait featuring [subject] wearing a hood, standing under light rain with water droplets visible. Streetlights reflect softly in the background. Face illuminated by a faint screen glow. Moody, cinematic, dark tones, subtle reflections on skin and clothing. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Trilogia Carmesim (3) =====
    "u_cr_dom": {
        "nome": "🔴 Domínio Carmesim",
        "cat": "unisex", "grp": "crimson",
        "subject": "the person",
        "prompt": "Create a vertical portrait shot in 1080x1920 format using the reference image, featuring [subject] with exact facial features preserved. Stark cinematic lighting with intense contrast. Captured from a slightly low, upward-facing angle emphasizing the jawline and neck, creating a sense of dominance and sculptural elegance. Background is a deep, saturated crimson red, contrasting strongly with luminous skin and dark wardrobe. " + _IDENT_TRAIL,
    },
    "u_cr_shad": {
        "nome": "🩸 Sombra Carmesim",
        "cat": "unisex", "grp": "crimson",
        "subject": "the person",
        "prompt": "Create a vertical cinematic portrait featuring [subject] with deep shadows covering part of the face. Low upward angle with dramatic contrast. Background remains deep crimson red but darker toward edges. Lighting sharper with stronger shadow cuts, creating a mysterious and intense presence. " + _IDENT_TRAIL,
    },
    "u_cr_glow": {
        "nome": "🌹 Brilho Carmesim Suave",
        "cat": "unisex", "grp": "crimson",
        "subject": "the person",
        "prompt": "Create a vertical portrait featuring [subject] with softer cinematic lighting and smoother transitions between light and shadow. Slight upward angle maintained. Background is a gradient crimson red with subtle glow. More elegant and refined mood. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Neon Warrior (3) =====
    "u_nw_warrior": {
        "nome": "⚡ Guerreiro Neon",
        "cat": "unisex", "grp": "neon",
        "subject": "the person",
        "prompt": "Edit this image featuring [subject] standing with one shoulder slightly forward, relaxed but commanding posture. Wearing an oversized black leather jacket with purple neon zipper details over a deep plum hoodie. Fitted black tech-fabric pants with silver piping down the sides, paired with matte black combat boots with electric purple soles. Surrounded by a glowing electric aura in shades of violet, magenta, and deep blue, with crackling energy particles around the silhouette. Background with dynamic angular brushstrokes in charcoal and purple creating depth. Expression intense and focused, with shadows accentuating facial features. Dark, moody, futuristic cinematic lighting with swirling particles and light wisps. " + _IDENT_TRAIL,
    },
    "u_nw_pulse": {
        "nome": "🌐 Pulso de Energia",
        "cat": "unisex", "grp": "neon",
        "subject": "the person",
        "prompt": "Edit this image featuring [subject] in a futuristic cyberpunk environment, standing confidently with subtle forward posture. Outfit remains dark techwear with glowing purple accents. Energy aura becomes more digital, with glitch particles and neon lines flowing around the body. Background includes abstract digital grids and light distortions. Mood intense and high-tech. " + _IDENT_TRAIL,
    },
    "u_nw_arcane": {
        "nome": "🔮 Poder Arcano",
        "cat": "unisex", "grp": "neon",
        "subject": "the person",
        "prompt": "Edit this image featuring [subject] surrounded by mystical purple energy resembling magical aura. Clothing remains dark but slightly more textured and arcane-inspired. Floating particles resemble sparks and smoke. Background darker with shadowy gradients. Expression serious and powerful, mystical atmosphere. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Trilogia Emoção (3) =====
    "u_em_break": {
        "nome": "😔 Esgotamento Editorial",
        "cat": "unisex", "grp": "emotion",
        "subject": "the person",
        "prompt": "Use the uploaded face and identity with high similarity, featuring [subject]. Do not change the face. Black-and-white dramatic editorial portrait. Expression tired and emotionally drained, with slightly heavy eyelids and subtly parted lips. Long wavy hair messy and unkempt, with strands falling over the forehead and framing the face. Both hands lifted into the hair, fingers tangled, gently pulling upward to enhance exhaustion and vulnerability. Wearing a black high-neck knit sweater with visible texture emphasized in grayscale. Directional lighting from the right creating strong highlights and deep shadows across the face. Background minimal and out of focus. Hyperrealistic detail in skin, hair, and fabric textures with shallow depth of field. 8K. " + _IDENT_TRAIL,
    },
    "u_em_hard": {
        "nome": "🖤 Sombra de Emoção",
        "cat": "unisex", "grp": "emotion",
        "subject": "the person",
        "prompt": "Create a high-contrast black and white portrait featuring [subject] with intense dramatic lighting. Expression exhausted and emotionally heavy. Strong shadows cut across the face creating a harsh, cinematic mood. Hair messy with hands gripping it more tightly. Background dark and minimal. " + _IDENT_TRAIL,
    },
    "u_em_analog": {
        "nome": "📻 Emoção Analógica",
        "cat": "unisex", "grp": "emotion",
        "subject": "the person",
        "prompt": "Create a black and white portrait featuring [subject] with a vintage analog film aesthetic. Expression tired and vulnerable. Add subtle grain, film texture, and slight imperfections. Lighting medium contrast with natural falloff. Background soft and blurred. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Pele Extrema (5) =====
    "u_sk_extreme": {
        "nome": "🔬 Pele Extrema",
        "cat": "unisex", "grp": "skin",
        "subject": "the person",
        "prompt": "Create an extreme close-up portrait based on the reference image, featuring [subject], using exact same facial features with maximum fidelity. Capture intense skin texture and moisture details. Dewy skin glistening with natural shine, wet hair strands partially covering the eye area. The eye is in sharp focus with high clarity, showing subtle redness for raw realism. Harsh directional studio lighting from a side angle emphasizing pores, highlights, and micro-shadows on the skin. Hyper-realistic, raw, detailed composition. " + _IDENT_TRAIL,
    },
    "u_sk_dew": {
        "nome": "💧 Brilho de Orvalho Suave",
        "cat": "unisex", "grp": "skin",
        "subject": "the person",
        "prompt": "Create an extreme close-up portrait featuring [subject] with softer moisture detail and smoother skin transitions. Dewy skin with subtle shine, wet strands lightly touching the face. Lighting softer but still directional, creating gentle highlights and refined shadows. Focus remains on the eye with high clarity. " + _IDENT_TRAIL,
    },
    "u_sk_raw": {
        "nome": "🩹 Textura Crua",
        "cat": "unisex", "grp": "skin",
        "subject": "the person",
        "prompt": "Create an extreme close-up portrait featuring [subject] with very harsh studio lighting. Strong side light exaggerating skin pores, imperfections, and texture. Wet skin appears more reflective with high contrast highlights. Eye remains the focal point with intense sharpness. " + _IDENT_TRAIL,
    },
    "u_sk_cine": {
        "nome": "🎬 Foco Cinemático",
        "cat": "unisex", "grp": "skin",
        "subject": "the person",
        "prompt": "Create a cinematic extreme close-up portrait featuring [subject] with controlled lighting and dramatic depth. Moist skin with subtle glow, wet hair partially covering the eye. Lighting more cinematic with shadow gradients and controlled highlights. Eye sharply focused with emotional depth. " + _IDENT_TRAIL,
    },
    "u_sk_dark": {
        "nome": "🌒 Atmosfera Húmida Escura",
        "cat": "unisex", "grp": "skin",
        "subject": "the person",
        "prompt": "Create a dark extreme close-up portrait featuring [subject] with low-key lighting. Wet skin glistening under minimal light. Hair strands more prominent across the face. Background fades into darkness. Eye still sharply focused with subtle redness, creating a moody and intense atmosphere. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Olhar Submerso (2) =====
    "u_se_eye": {
        "nome": "👁️ Olhar Submerso",
        "cat": "unisex", "grp": "submerged",
        "subject": "the person",
        "prompt": "Hyper-realistic black and white portrait featuring [subject] in an extreme close-up with the face partially submerged in water. Only one eye fully visible above the surface, with an intense and focused expression conveying strength, mystery, and introspection. Skin highly detailed with visible pores and water droplets, eyelashes and eyebrows sharply defined. Soft side lighting creating dramatic contrast between light and shadow, highlighting the depth of the gaze and reflective water texture. Water surface with gentle ripples and bubbles. Macro lens, ultra-high definition, shallow depth of field with focus entirely on the eye. " + _IDENT_TRAIL,
    },
    "u_se_dark": {
        "nome": "🌊 Profundidade Sombria",
        "cat": "unisex", "grp": "submerged",
        "subject": "the person",
        "prompt": "Create a darker black and white extreme close-up featuring [subject] with deeper shadows and more dramatic contrast. Water appears darker and heavier, with fewer reflections. Eye illuminated more selectively, creating a mysterious and intense mood. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Vintage Beetle (4) =====
    "u_vb_autumn": {
        "nome": "🍂 Outono Vintage",
        "cat": "unisex", "grp": "vintage",
        "subject": "the person",
        "prompt": "Side-angle photorealistic cinematic shot featuring [subject] sitting on the floor and leaning next to a classic vintage white Volkswagen Beetle parked on a city street with autumn leaves. Sunlight filters through trees, casting warm dappled light on the subject and the car. Wearing a crisp white shirt, black jacket, light blue jeans, small black leather bag, and black boots. Cinematic mood with soft depth of field and subtle film grain. Aspect ratio 9:16. " + _IDENT_TRAIL,
    },
    "u_vb_golden": {
        "nome": "🌅 Luz Dourada Urbana",
        "cat": "unisex", "grp": "vintage",
        "subject": "the person",
        "prompt": "Create a cinematic side-angle shot featuring [subject] in the same pose next to a vintage white Volkswagen Beetle during golden hour. Strong warm sunlight with long shadows. Autumn leaves glowing in golden tones. Slight lens flare and cinematic softness. Crisp white shirt, black jacket, light blue jeans. " + _IDENT_TRAIL,
    },
    "u_vb_rainy": {
        "nome": "💧 Mood Vintage Chuvoso",
        "cat": "unisex", "grp": "vintage",
        "subject": "the person",
        "prompt": "Create a moody rainy version featuring [subject] sitting beside a vintage white Volkswagen Beetle on a wet street. Reflections on the ground, soft mist in the air. Lighting dim and cinematic with cool tones. Subtle rain droplets visible. Crisp white shirt, black jacket, light blue jeans. " + _IDENT_TRAIL,
    },
    "u_vb_film": {
        "nome": "🎞️ Estética Filme Urbana",
        "cat": "unisex", "grp": "vintage",
        "subject": "the person",
        "prompt": "Create a cinematic street photography version featuring [subject] with a film-like look. Slight grain, muted tones, and natural lighting. Background with urban textures and autumn leaves. Same pose next to a vintage white Volkswagen Beetle. Strong documentary vibe. " + _IDENT_TRAIL,
    },

    # ===== UNISSEX — Hero Frame (1, complementar do Men) =====
    "u_he_cine": {
        "nome": "🎥 Frame Cinematográfico Herói",
        "cat": "unisex", "grp": "hero",
        "subject": "the person",
        "prompt": "Retrato editorial cinematográfico em 8K apresentando [subject] com estética de super-herói moderno. Fundo vermelho com luz difusa e partículas leves. Iluminação suave porém dramática com highlights no rosto e traje. Pose firme com braços cruzados e expressão determinada. Estilo realista próximo de filme. " + _IDENT_TRAIL,
    },

    # ===== FLYERS RECRUTAMENTO (6) =====
    "fl_general": {
        "nome": "💼 Flyer Geral 'WE WANT YOU'",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a creative recruitment poster featuring [subject] positioned on the right side, arms crossed, smiling naturally while facing slightly to the left. Radiating confidence and warmth, wearing a stylish red blazer over a white blouse. Maintain a red, black, and white geometric background, with circular and linear design elements framing the figure. On the left, display the bold headline: 'WE WANT YOU!' with 'WE' in white on a red block, 'WANT' in black on white, and 'YOU!' in red. Beneath that 'Join Our Professionals Team.' Add a 'WE'RE HIRING' section with: Graphic Designer, Marketing Staff, Finance Accountant, Operational Staff. Include an 'Apply Now!' button. Contact: company@gmail.com. Energetic, professional, inviting design. " + _IDENT_TRAIL,
    },
    "fl_tech": {
        "nome": "💻 Flyer Tech Futurista",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a modern tech recruitment poster featuring [subject] standing confidently slightly to the left side, holding a tablet, with a focused and professional expression. Wearing a smart casual outfit (dark blazer over a neutral shirt). Background with futuristic blue and purple gradient, subtle grid lines and glowing UI elements. Headline on the right: 'JOIN OUR TEAM' in bold futuristic font. Subtext: 'Build the Future With Us.' Add: 'WE'RE HIRING' - Software Engineer - UI/UX Designer - Data Analyst - Product Manager. Glowing 'Apply Now' button. Contact: careers@techvision.com. Lighting slightly neon, high contrast, modern startup aesthetic. " + _IDENT_TRAIL,
    },
    "fl_corporate": {
        "nome": "🏢 Flyer Corporativo Limpo",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a corporate recruitment flyer featuring [subject] seated at a desk, hands gently crossed, calm and confident expression. Wearing formal attire (blazer or suit). Background clean white with subtle grey lines and minimal design. Headline: 'WE ARE HIRING'. Subtext: 'Join Our Professional Team'. Open roles: Administrative Assistant, HR Manager, Accountant, Office Coordinator. 'Apply Today' button in blue. Contact: hr@companygroup.com. Soft studio lighting, clean layout, professional and trustworthy feel. " + _IDENT_TRAIL,
    },
    "fl_fitness": {
        "nome": "💪 Flyer Fitness Power",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a fitness recruitment poster featuring [subject] in a strong confident pose, arms slightly flexed or hands on hips, energetic expression. Wearing athletic outfit (gym wear). Background dark with red and black tones, smoke effects and light streaks. Headline: 'WE'RE BUILDING CHAMPIONS'. Subtext: 'Join Our Fitness Team'. Hiring: Personal Trainer, Fitness Coach, Nutrition Specialist, Gym Assistant. Bold 'JOIN NOW' button. Contact: fitness@powergym.com. High contrast lighting, dramatic shadows, intense gym vibe. " + _IDENT_TRAIL,
    },
    "fl_restaurant": {
        "nome": "🍷 Flyer Restaurante Acolhedor",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a restaurant hiring flyer featuring [subject] standing slightly sideways holding a tray or menu, friendly and welcoming smile. Wearing hospitality uniform or elegant outfit. Warm background with golden lighting, restaurant ambiance blur. Headline: 'JOIN OUR TEAM'. Subtext: 'We're Hiring Passionate People'. Positions: Waiter / Waitress, Chef Assistant, Bartender, Kitchen Staff. 'Apply Now' button. Contact: jobs@finebistro.com. Warm lighting, inviting atmosphere, soft glow. " + _IDENT_TRAIL,
    },
    "fl_creative": {
        "nome": "🎨 Flyer Agência Criativa",
        "cat": "flyer",
        "subject": "the person",
        "prompt": "Edit this image into a creative agency recruitment poster featuring [subject] in a relaxed artistic pose, slightly leaning, confident and creative expression. Wearing stylish modern outfit. Background with abstract shapes, colorful gradients (purple, orange, blue), paint strokes and design elements. Headline: 'CREATIVITY WANTED'. Subtext: 'Join Our Creative Studio'. Hiring: Graphic Designer, Video Editor, Social Media Manager, Content Creator. 'Let's Work Together' button. Contact: hello@creativelab.com. Vibrant colors, artistic layout, modern design style. " + _IDENT_TRAIL,
    },

    # ===== CASAIS — Story "Polaroid Romance" (3 cenas) =====
    "co_polaroid_classic": {
        "nome": "🎞️ Polaroid Clássico",
        "cat": "couple", "story": "polaroid",
        "subject": "the person",
        "prompt": "Take a photo taken with a Polaroid camera. The photo should look like an ordinary photograph, without an explicit subject or property. Slight blur and a consistent light source like a flash from a dark room scattered throughout the image. Do not change the face. Change the background behind [subject] and the other person to white curtains. Create cute poses between both. The other person is holding a red Coca-Cola can and [subject] is holding a burger. Natural interaction, relaxed and candid feel. Polaroid candid style, flash low-light environment, indoor with white curtain background. " + _IDENT_TRAIL,
    },
    "co_polaroid_romantic": {
        "nome": "❤️ Momento Romântico",
        "cat": "couple", "story": "polaroid",
        "subject": "the person",
        "prompt": "Create a soft romantic Polaroid-style photo of [subject] and the other person standing close together with gentle affectionate poses. Slight blur and flash lighting effect in a dim room. Background replaced with soft white curtains. The other person holds a red Coca-Cola can and [subject] holds a burger. Both smiling naturally with subtle warmth. Polaroid romantic style, soft flash, close shot, warm intimate gentle mood. " + _IDENT_TRAIL,
    },
    "co_polaroid_playful": {
        "nome": "😂 Diversão a Dois",
        "cat": "couple", "story": "polaroid",
        "subject": "the person",
        "prompt": "Create a playful Polaroid-style photo of [subject] and the other person making fun poses. Slight blur with flash lighting in a dark environment. Background changed to white curtains. The other person holding a red Coca-Cola can while [subject] holds a burger. Both laughing or doing exaggerated expressions, energetic and fun. Polaroid playful style, flash, slight angle snapshot. " + _IDENT_TRAIL,
    },

    # ===== COMICS — Story A "Sombras do Cemitério" (2 páginas) =====
    "x_a_p1": {
        "nome": "📖 Cena 1 — Cemitério Emocional",
        "cat": "comic", "story": "shadows", "scene": 1,
        "subject": "the person",
        "prompt": "Comic book page in realistic American comic style like The Walking Dead (Charlie Adlard / Tony Moore influence), detailed ink lines, muted earth tones, dramatic lighting, cinematic panel layout, 3 rows of panels on a single page. Top row (3 panels): Left panel (medium shot): [subject] kneeling devastated in front of a wooden cross grave in a foggy cemetery at dusk, one hand on the cross, crying with tears, speech bubble: 'I'LL ALWAYS LOVE YOU, TRISH.' Middle panel (extreme close-up): [subject]'s tearful face in profile, intense emotional expression, small speech bubble above: 'COLE?' Right panel (medium shot): another character standing nearby, looking at [subject], speech bubbles: 'THE WARDEN'S A GOOD MAN. STUCK AROUND WHEN THE S*** HIT THE FAN.' 'YOU ALL RIGHT?' 'I DON'T THINK SO.' 'I KNOW THAT FEELING.' Middle row (large wide panel): Two characters standing in overgrown cemetery with trees and ruined buildings in background at sunset. Left: [subject] looking serious. Right: second character pointing right with determined expression. Speech bubbles: 'HE'S ABOUT THE ONLY PERSON AROUND I STILL TRUST.' 'MY GRANDKIDS USED TO PLAY IN THIS PARK. YOU KNOW, BEFORE ALL OF THIS.' 'I ALWAYS LIKED IT HERE, ESPECIALLY IN THE FALL WHEN THE TREES TURNED.' Bottom row (large horizontal panel, close-up): Extreme close-up of both faces side by side, serious and emotional expressions. Speech bubble: 'THIS IS A GOOD PLACE, COLE. SHE'LL FIND PEACE HERE.' Overall atmosphere: somber, melancholic, post-apocalyptic, soft golden hour light mixed with cool shadows, detailed cross graves, tombstones, trees with autumn leaves, high detail, sharp linework, comic book coloring with strong blacks, full page layout, no text outside speech bubbles, 8k comic page --ar 3:4 --stylize 750. preserve identity, keep same face, keep facial structure, maintain original identity, do not change person, comic style face adaptation with identity consistency.",
    },
    "x_a_p2": {
        "nome": "📖 Cena 2 — Conflito & Poder",
        "cat": "comic", "story": "shadows", "scene": 2,
        "subject": "the person",
        "prompt": "American comic book page in realistic gritty style like The Walking Dead (Charlie Adlard influence), detailed black ink lines, muted earth tones, dramatic cinematic lighting, full page layout with multiple panels. Top row - large horizontal panel on the left + 2 small vertical panels on the right: Left large panel: [subject] and another character walking side by side through an overgrown cemetery at dusk. Speech bubbles: 'YOU TRACK DOWN THE FIRST SONS?' and 'LAST OF 'EM ARE DUG IN OVER BY PIER 12. GOING TO BE A BITCH FLUSHING THEM OUT, BUT ONCE THEY'RE DEALT WITH, WE CAN START RESTORING SOME ORDER AROUND HERE.' 'I'LL DEAL WITH THEM.' Right column (4 small close-up panels stacked): Top: Close-up of the second character looking serious. 'YOU'RE NOT THE ONLY ONE IN THIS FIGHT, COLE.' Next: Extreme close-up of [subject]'s eyes, intense expression. Next: Close-up of [subject]'s angry face, eyes narrowed. Bottom: [subject] shouting with mouth open, furious expression. 'MAYBE NOT. BUT THAT DOESN'T CHANGE WHAT HAPPENED.' 'NOTHING WILL CHANGE WHAT HAPPENED.' 'YOU DIDN'T SEE... WHAT HE DID TO HER...' Middle large panel: Close-up of [subject] looking down with intense grief and anger, glowing bright blue electric energy crackling around the hands and the gun being held. Blue lightning effects. 'NO, I DIDN'T.' 'BUT I KNOW WHAT IT'S LIKE TO HAVE SOMEONE STOLEN FROM YOU.' Bottom right panel: Two characters walking away through the cemetery path, sunset light. 'AND I KNOW WHAT GRIEF CAN DO TO A MAN. TRUST ME, YOU DON'T WANT TO GO DOWN THAT ROAD.' Overall style: post-apocalyptic, somber, detailed linework, strong shadows, golden hour mixed with cool tones, high contrast comic coloring, 8k comic page --ar 3:4 --stylize 650. preserve identity, keep same face, keep facial structure, maintain original identity, do not change person, comic style face adaptation with identity consistency.",
    },

    # ===== COMICS — Story B "A Jornada do Herói" (5 páginas) =====
    "x_b_p1": {
        "nome": "📕 Página 1 — A Perda",
        "cat": "comic", "story": "journey", "scene": 1,
        "subject": "the person",
        "prompt": "Comic book page in realistic American comic style like The Walking Dead, detailed ink lines, muted earth tones, cinematic panel layout. Top panels: [subject] kneeling in a foggy cemetery at dusk, hand on a wooden cross grave, crying. Speech: 'I'LL ALWAYS LOVE YOU...' Close-up of [subject]'s tearful face. Speech: 'WHY...' Another character standing nearby. Speech: 'YOU CAN'T STAY HERE FOREVER.' 'IT'S NOT SAFE.' Middle panel: Wide shot of cemetery with broken tombstones and trees. [subject] standing slowly, grief visible. Bottom panel: Close-up of [subject]'s face, eyes filled with pain. Speech: 'I LOST EVERYTHING.' Atmosphere: somber, fog, cold tones, emotional grief, post-apocalyptic. preserve identity, keep same face, maintain facial structure, do not change person, comic style face adaptation.",
    },
    "x_b_p2": {
        "nome": "📕 Página 2 — A Raiva",
        "cat": "comic", "story": "journey", "scene": 2,
        "subject": "the person",
        "prompt": "Comic book page in gritty realistic style. Top panel: [subject] walking through ruins with another character. Speech: 'WHO DID THIS?' Close-up: [subject]'s eyes intense and filled with anger. Panels: Flashback silhouettes of chaos and violence. Speech: 'THEY TOOK HER FROM ME.' Bottom large panel: [subject] clenching fists, slight energy crackling around hands. Speech: 'I'M GOING TO END THIS.' Atmosphere: tension, anger, darker shadows. preserve identity, keep same face, maintain facial structure, do not change person, comic style face adaptation.",
    },
    "x_b_p3": {
        "nome": "📕 Página 3 — O Confronto",
        "cat": "comic", "story": "journey", "scene": 3,
        "subject": "the person",
        "prompt": "Comic page cinematic layout. Top: [subject] confronting a group of enemies in abandoned urban ruins. Speech: 'THIS ENDS NOW.' Action panels: Combat scenes, dynamic movement, impacts. Close-up: [subject] bleeding slightly but still standing strong. Enemy speech: 'YOU SHOULD HAVE STAYED BURIED.' Bottom: [subject] overpowering opponent. Atmosphere: action, chaos, dust, debris. preserve identity, keep same face, maintain facial structure, do not change person, comic style face adaptation.",
    },
    "x_b_p4": {
        "nome": "📕 Página 4 — Despertar de Poder",
        "cat": "comic", "story": "journey", "scene": 4,
        "subject": "the person",
        "prompt": "Comic book page with strong visual effects. Top: [subject] standing alone, wounded, breathing heavily. Middle: Energy begins to glow around hands, subtle at first. Close-ups: Eyes glowing slightly, determination. Speech: 'I WON'T BREAK.' Large panel: Full-body shot with visible energy aura forming around [subject]. Atmosphere: transformation, power, dramatic lighting. preserve identity, keep same face, maintain facial structure, do not change person, comic style face adaptation.",
    },
    "x_b_p5": {
        "nome": "📕 Página 5 — Resolução",
        "cat": "comic", "story": "journey", "scene": 5,
        "subject": "the person",
        "prompt": "Final comic page. Top: [subject] standing victorious in silence, battlefield behind. Middle: Second character approaches. Speech: 'IT'S OVER.' Close-up: [subject] calmer, eyes heavy but peaceful. Speech: 'NOTHING WILL BRING HER BACK...' Final panel: [subject] walking away into the distance at sunset. Speech: 'BUT I WON'T LET IT HAPPEN AGAIN.' Atmosphere: calm, bittersweet, golden light, closure. preserve identity, keep same face, maintain facial structure, do not change person, comic style face adaptation.",
    },

    # ===== NOVOS — Iteração 5 =====
    # ▼ UNISSEX — sub-grupo "bw" (variação)
    "u_bw_intro": {
        "nome": "🌃 Introspecção Cinemática",
        "cat": "unisex", "grp": "bw",
        "subject": "the person",
        "prompt": "Cinematic introspective black and white portrait featuring [subject] with stronger contrast between window light and deep shadows. Slightly darker environment, sense of deep reflection. Sharper marked shadows, film-noir style. Subtle cinematic film grain, deeper color grading. " + _IDENT_TRAIL,
    },

    # ▼ UNISSEX — novo sub-grupo "lifestyle" (4 estilos)
    "u_ls_mirror": {
        "nome": "🪞 Mirror Selfie Concrete",
        "cat": "unisex", "grp": "lifestyle",
        "subject": "the person",
        "prompt": "Cinematic portrait using the reference image as identity anchor, of [subject] with short curly dark hair leaning against a textured concrete wall, wearing a loose white button-down shirt and layered gold necklaces. Warm golden hour sunlight coming through a window creates dramatic shadow patterns on the wall. Soft natural light on the face, thoughtful expression looking sideways, minimal aesthetic, shallow depth of field, film photography style, 85mm lens, ultra realistic, warm tones, high detail, moody atmosphere. " + _IDENT_TRAIL,
    },
    "u_ls_cafe": {
        "nome": "☕ Urban Café Layered",
        "cat": "unisex", "grp": "lifestyle",
        "subject": "the person",
        "prompt": "Portrait of [subject] in a stylish, layered outfit sitting at a wooden table in a street cafe. Wearing a brown oversized jacket with a light yellow jumper draped over the shoulders, light blue oversized loose-fitting jeans with cuffs, a pale yellow cap with a small logo, and narrow oval glasses with clear lenses and dark frames. Long dark hair, calm makeup, tanned skin. Plastic cup of green smoothie nearby, large bouquet of yellow tulips. Soft daylight, urban lifestyle aesthetic. Color scheme: chocolate, lemon yellow, denim. Relaxed pose, resting chin on hand. Background: city cafe window with evening lights. High resolution, realistic, professional portrait photography, warm toning, vibrant color correction. " + _IDENT_TRAIL,
    },
    "u_ls_chibi": {
        "nome": "🧸 Wellness Chibi Meditation",
        "cat": "unisex", "grp": "lifestyle",
        "subject": "the person",
        "prompt": "A calm [subject] sitting cross-legged on a bed in a cozy minimal bedroom, meditating with eyes closed, wearing an oversized light grey sweatshirt and matching grey joggers. Soft natural morning light from the side window. Around the subject are tiny cute chibi versions of the same identity sitting on shoulders, knees and around, doing activities like reading, meditating, stretching and dancing. Hand-drawn pastel doodles and speech bubbles floating around the head with words like 'Content', 'Focus', 'Growth', 'Sleep', 'Work', 'Recharge'. Cute pastel hearts, stars, smiley faces and sparkles around the scene. Style: soft pastel illustration + realistic photography mix, dreamy wellness vibe, cozy aesthetic, ultra detailed, 4k. " + _IDENT_TRAIL,
    },
    "u_ls_wellness": {
        "nome": "🪷 Wellness Editorial Calm",
        "cat": "unisex", "grp": "lifestyle",
        "subject": "the person",
        "prompt": "Editorial wellness scene featuring [subject] sitting sideways in a wooden chair with terracotta upholstery, relaxed posture, looking towards a window with soft natural light entering. Hair tied back naturally, comfortable outfit in neutral tones (beige sweatshirt and light pants), realistic fabric texture. Soft natural side light with light diffusion, creating delicate shadows. Out-of-focus plants in foreground creating depth, cinematic framing, rule of thirds, minimalist cozy environment. Calm introspective atmosphere, self-care aesthetic. Ultra-realistic photography, 8k, natural skin texture, warm soft color grading, premium editorial style. " + _IDENT_TRAIL,
    },

    # ▼ UNISSEX — novo sub-grupo "epic" (5 estilos premium 🔒)
    "u_ep_sorcerer": {
        "nome": "🔮 Fantasy Sorcerer Poster",
        "cat": "unisex", "grp": "epic", "locked": True,
        "subject": "the person",
        "prompt": "Hyper-realistic cinematic movie poster of [subject] as a powerful sorcerer bursting through a cracked Queen of Spades playing card. The card explodes outward with stone fragments, dust, and debris frozen mid-air. Wearing an ornate royal maroon and gold embroidered medieval fantasy jacket, rich fabric textures, intricate detailing, regal and mystical. The subject extends one hand forward, fingers glowing with intense magical energy, subtle golden sparks and dark arcane aura. Intense piercing gaze, confident dominant expression, cinematic hero framing. Dramatic chiaroscuro lighting, dark moody background, volumetric light rays, ultra-detailed textures, photorealistic face, epic fantasy realism, movie poster composition, high contrast, dynamic motion, dust particles, 8K. " + _IDENT_TRAIL,
    },
    "u_ep_grid_classic": {
        "nome": "🎬 Editorial Grid — Classic",
        "cat": "unisex", "grp": "epic", "locked": True,
        "subject": "the person",
        "prompt": "Professional studio fashion photoshoot in a 2×2 grid collage showing four poses of [subject] wearing black sunglasses. Outfit: deep emerald green tailored blazer, cream/off-white dress shirt, black slim trousers, burgundy tie, silver watch. Blazer appears differently across frames (worn, draped over shoulder, partially removed, held). Background: clean teal-to-turquoise gradient studio. Poses: 1. Close portrait adjusting tie. 2. Seated editorial pose leaning forward elbow on knee. 3. Relaxed pose with vintage camera around neck. 4. Stylish pose running hand through hair while holding blazer. Lighting: three-point studio lighting — softbox key 45° camera left, soft fill camera right, subtle rim light. 85mm f/2.2 ISO 100 1/160s. Ultra-realistic GQ/Vogue editorial, sharp 4K, clean 2×2 grid. " + _IDENT_TRAIL,
    },
    "u_ep_grid_dark": {
        "nome": "🎬 Editorial Grid — Dark Mode",
        "cat": "unisex", "grp": "epic", "locked": True,
        "subject": "the person",
        "prompt": "Same 2×2 grid editorial of [subject] with sunglasses, identical outfit and poses, but darker teal gradient with subtle vignette, stronger contrast, deeper shadows, cinematic moody tone. Editorial high contrast, 4K, 2×2 grid. " + _IDENT_TRAIL,
    },
    "u_ep_grid_lux": {
        "nome": "🎬 Editorial Grid — Soft Luxury",
        "cat": "unisex", "grp": "epic", "locked": True,
        "subject": "the person",
        "prompt": "Same 2×2 grid editorial of [subject] with sunglasses, identical outfit and poses, but soft pastel teal gradient cleaner luxury look, softer diffusion, more even highlights, luxury fashion tone. Clean Vogue-style, 4K, 2×2 grid. " + _IDENT_TRAIL,
    },
    "u_ep_grid_street": {
        "nome": "🎬 Editorial Grid — Street Edge",
        "cat": "unisex", "grp": "epic", "locked": True,
        "subject": "the person",
        "prompt": "Same 2×2 grid editorial of [subject] with sunglasses, identical outfit and poses, but teal gradient with subtle texture, slightly harsher lighting, sharper shadows, street-fashion tone. Edgy editorial sharper contrast, 4K, 2×2 grid. " + _IDENT_TRAIL,
    },

    # ▼ UNISSEX — novo sub-grupo "scifi" (2 estilos premium 🔒)
    "u_sf_cyber": {
        "nome": "🔬 Cyber Science Portrait",
        "cat": "unisex", "grp": "scifi", "locked": True,
        "subject": "the person",
        "prompt": "Cinematic close-up portrait of [subject] in side profile, wet hair strands on the skin, intense reflective eyes, mathematical formulas and scientific equations projected across the face and neck, glowing white handwritten symbols, physics diagrams and abstract calculations overlay, futuristic holographic projection, dark moody background, dramatic lighting, high contrast, detailed skin texture, cyberpunk science aesthetic, shallow depth of field, volumetric lighting, photorealistic, 8k, film still, sci-fi atmosphere. " + _IDENT_TRAIL,
    },
    "u_sf_cybergoth": {
        "nome": "💜 Cybergoth Neon Portrait",
        "cat": "unisex", "grp": "scifi", "locked": True,
        "subject": "the person",
        "prompt": "Cyberpunk portrait of [subject] with pale synthetic complexion, dark metallic lipstick, intense gaze directed at viewer. Vivid holographic glow with magenta and cyan edge lighting. Captured on a mirrorless 85mm f/1.2, deep atmospheric bokeh. Cyberpunk portraiture, techno-goth aesthetic, high-contrast digital realism, ultra high resolution, hyper-detailed textures, cinematic sci-fi realism. " + _IDENT_TRAIL,
    },

    # ▼ MULHERES — novos
    "wom_mirror_concrete": {
        "nome": "🪞 Mirror Bedroom Selfie",
        "cat": "women",
        "subject": "the woman",
        "prompt": "Cinematic portrait of [subject] with short curly dark hair leaning against a textured concrete wall, wearing a loose white button-down shirt and layered gold necklaces. Warm golden hour sunlight through a window creates dramatic shadow patterns. Soft natural light on the face, thoughtful sideways expression, minimal aesthetic, shallow depth of field, film photography style, 85mm lens, warm tones, high detail. " + _IDENT_TRAIL,
    },
    "wom_fitness_split": {
        "nome": "💪 Fitness Lifestyle Split",
        "cat": "women",
        "subject": "the woman",
        "prompt": "Modern lifestyle split composition poster combining a luxurious smartphone gym selfie with a healthy diet bowl. Top section: [subject] in a luxury gym taking a mirror selfie holding a smartphone, wearing stylish sports bra and high-waisted athletic shorts/leggings, healthy toned physique, post-workout glow, modern gym mirrors, soft natural window light. Bottom section: clean top-down food photography of healthy breakfast bowl with strawberries, blueberries, banana slices, granola, yogurt, on wooden table, with minimal nutrition infographic next to bowl labelled 'Banana 90 kcal / Strawberries 50 / Blueberries 60 / Granola 180 / Yogurt 120 / Total 500 kcal'. Soft neutrals, natural wood tones, fresh fruit colors. Photorealistic, high detail, fitness lifestyle aesthetic. " + _IDENT_TRAIL,
    },

    # ▼ STORIES — nova categoria "📱 Posts Instagram" (3 estilos)
    "st_awareness": {
        "nome": "📰 Editorial Awareness Post",
        "cat": "stories",
        "subject": "the person",
        "prompt": "Cinematic editorial portrait of [subject] in profile, long wavy dark brown hair, wearing beige blazer over white top. Background: classic old building staircase, slightly blurred for architectural depth. Side natural light with dramatic contrast highlighting facial contours and hair texture, soft refined shadows. Minimalist elegant framing, focus on profile, clean sophisticated aesthetic. Integrated text on image: 'JÁ PULOU UM POST SÓ PORQUE ALGO TE INCOMODOU NO VISUAL? ACONTECE MAIS DO QUE VOCÊ IMAGINA.' Modern sans-serif typography, white, with bold parts for emphasis, balanced spacing, professional feed style. Neutral sophisticated color grading, light contrast, premium look. Ultra-realistic 8K editorial photography. --ar 4:5. " + _IDENT_TRAIL,
    },
    "st_testimonial": {
        "nome": "💼 Professional Testimonial Post",
        "cat": "stories",
        "subject": "the person",
        "prompt": "Professional personal-marketing portrait of [subject] sitting in natural posture, genuine smile, wearing a white blouse and jeans. Modern bright office environment with soft natural lighting, minimal blurred elements in background. Soft diffused warm-toned light highlighting the face. Clean framing, balanced background. Graphic element: rounded testimonial bubble with a small circular photo of the same subject inside. Text inside bubble: 'O meu sucesso profissional nunca seria alcançado se não houvessem pessoas incríveis ao meu lado...' Generic professional name + @grandesite below. Modern clean sans-serif typography. Light warm welcoming color grading. Ultra-realistic 8K editorial photography. --ar 4:5. " + _IDENT_TRAIL,
    },
    "st_wellness": {
        "nome": "🪷 Wellness Editorial Post",
        "cat": "stories",
        "subject": "the person",
        "prompt": "Editorial wellness scene of [subject] sitting sideways in a wooden chair with terracotta upholstery, relaxed posture, looking toward a window with soft natural light. Hair naturally tied, comfortable neutral-toned outfit. Soft side natural light with delicate shadows. Out-of-focus plants in foreground for depth. Calm cozy minimalist atmosphere. Integrated text on image: 'Você não precisa estar em alerta o tempo todo.' followed by 'Às vezes descansar também é um ato de cuidado.' Modern elegant white serif typography, well-spaced, naturally integrated into scene. Warm soft color grading, premium editorial style. Ultra-realistic 8K. --ar 4:5. " + _IDENT_TRAIL,
    },

    # ▼ SENSUAL — nova categoria 🔒 (11 estilos: 2 free + 9 locked)
    "sn_postshower": {
        "nome": "🚿 Post-Shower iPhone Candid",
        "cat": "sensual",
        "subject": "the woman",
        "prompt": "Ultra photorealistic iPhone-style candid photo of [subject], 35mm look, 4:3 ratio, slight handheld motion, mobile HDR. 11:36 PM, warm bedside lamp 3200K, bedroom near unmade bed, intimate quiet night atmosphere. Subject stands near bed, one hand lightly holding hoodie hem slightly lifting it, hip subtly shifted, relaxed stance, calm confident eye contact. Natural beauty, hazel eyes, soft feminine features, curvy realistic silhouette, dark brunette damp loose waves from shower. Outfit: oversized light grey hoodie soft cotton subtly clinging to damp skin, bare legs visible naturally. Realistic skin pores, post-shower glow on shoulders/collarbones/neck, slight moisture sheen, fabric gently following body contours. Mood: intimate, confident, slightly seductive but natural, candid spontaneous. Avoid: explicit nudity, graphic exposure, distortion, artificial skin. " + _IDENT_TRAIL,
    },
    "sn_bedroom": {
        "nome": "🛏️ Bedroom iPhone Candid",
        "cat": "sensual",
        "subject": "the woman",
        "prompt": "Ultra photorealistic iPhone-style candid of [subject], 35mm look, 4:3 ratio. Bedroom near unmade bed, warm bedside lamp 3200K, soft shadows, late night. Subject stands near bed in relaxed posture, hip slightly shifted, calm confident eye contact. Outfit: oversized light grey hoodie naturally draped, subtly contouring silhouette, bare legs visible casually. Natural skin pores, post-shower glow, slight damp sheen on collarbones/neck, damp loose waves. Mood: candid, soft indoor realism, slightly sensual but natural, cinematic yet grounded. Avoid: explicit nudity, distortion, artificial skin. " + _IDENT_TRAIL,
    },
    "sn_dark_asteric": {
        "nome": "🌒 Dark Asteric",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Ultra photorealistic iPhone-style candid of [subject], 4:3 ratio, 35mm look. Dim bedroom, minimal lighting, stronger shadows, warm bedside light mixed with darker ambient tones. Subject stands near bed slightly leaning, one hand holding hoodie hem, posture relaxed but more intense. Direct eye contact with deeper mysterious expression. Damp brunette hair messier waves. Outfit: oversized grey hoodie falling naturally, bare legs partially visible in shadow. Visible skin texture stronger contrast, deeper shadows across face/body, light catching moisture, cinematic shadow gradients. Mood: moody intimate slightly edgy, late-night raw aesthetic. Avoid: explicit nudity. " + _IDENT_TRAIL,
    },
    "sn_minimal": {
        "nome": "🤍 Minimalist Lifestyle Portrait",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Modern minimalist lifestyle portrait of [subject] standing leaning against a clean white desk in a contemporary room, relaxed posture, calm direct gaze. Natural facial features with soft makeup, clean realistic skin texture, hair in simple ponytail. Outfit: light gray long-sleeved form-fitting ribbed knit lounge set. Minimalist room with soft off-white walls, clean desk with dual monitors PC tower accessories, subtle tech atmosphere without clutter. Soft even lighting, gentle shadows, clean natural indoor tones. Calm confident modern lifestyle aesthetic, contemporary editorial look, ultra photorealistic. " + _IDENT_TRAIL,
    },
    "sn_mirror_gaming": {
        "nome": "🎮 Mirror Selfie Gaming Room",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Ultra photorealistic mirror selfie of [subject], 8k, raw style, 35mm equivalent. Vibrant indoor RGB lighting with soft pink tones and warm ambient glow, influencer aesthetic, cozy gaming room. White wood-paneled walls, white shelving with gaming items and colorful accessories, plush pink gaming chair with soft cushion, decorative ivy vines, small ornamental tree. Slim fit physique with realistic proportions, positioned in crouching squat on a soft rug, body in side profile relative to mirror. Long hair with soft bangs, dark-framed glasses, confident focused gaze through mirror reflection. Outfit: fitted long-sleeve crop top, short pleated skirt, over-the-knee socks, smartphone in one hand. Vertical 9:16 full-body. " + _IDENT_TRAIL,
    },
    "sn_actress": {
        "nome": "🎬 Cinematic Actress Concepts",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Ultra-detailed cinematic portrait of [subject] in a versatile aesthetic. Concept: blend of sport-minimal energy (vibrant athletic outfit, sunglasses, high-angle shot interacting with reflective metallic sphere, strong color contrast background, sharp lighting), urban glamour (rooftop overlooking city, elegant gown with subtle shine, accessories, city lights bokeh), lifestyle mirror (casual athletic outfit indoor mirror), and character-inspired fashion (playful themed outfit clean studio). Combination of natural studio and cinematic lighting, soft controlled shadows. Confident expressive modern, mix of playful elegant cinematic. Editorial fashion 8k sharp textures. " + _IDENT_TRAIL,
    },
    "sn_lux_mirror": {
        "nome": "💎 Luxury Mirror Editorial",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Editorial fashion portrait of [subject] with naturally curvy toned body, voluminous dark curly hair, wearing a long beige body-fitting shape dress with realistic drape and detailed texture. Pose: back to camera, hands behind head, looking over shoulder toward a large round mirror, frontal reflection visible. Modern clean interior, light floor, contrasting dark rug, softly translucent white curtains. Soft natural light through window creating delicate highlights and gentle shadows, refined cinematic aesthetic. Composition: balance between body and reflection, light depth of field, elegant minimal framing. Sophisticated sensual atmosphere, luxury editorial, no exaggeration. Warm neutral color grading, ultra-realistic, 8k, sharp focus, natural fabric and skin texture. --ar 4:5. " + _IDENT_TRAIL,
    },
    "sn_softglam": {
        "nome": "💖 Mirror Selfie Soft Glam",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Fashion/lifestyle portrait of [subject] with voluminous dark curly hair, naturally curvy silhouette, wearing a long light-pink strapless body-fitting dress with soft texture and subtle slight transparency. Pose: taking a mirror selfie with phone in hand, natural confident posture, slight body lean for composition, relaxed expression. Modern apartment with wooden door and wall mirror, clean contemporary aesthetic. Soft natural light entering, refined editorial atmosphere. Ultra-realistic 8k, sharp focus, natural fabric and skin texture. --ar 4:5. " + _IDENT_TRAIL,
    },
    "sn_clean_jumpsuit": {
        "nome": "🤍 Editorial Sensual Clean",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Editorial fashion portrait of [subject], long wavy black hair, wearing white sleeveless high-neck jumpsuit, slightly shiny fabric with side cutouts and crossed straps at the hip. Three-quarter pose, one hand on waist and the other resting on the leg, slight hip tilt, direct gaze with confident expression. Elegant background: white framed wall, crystal chandelier in the back, vase of red roses on the floor, bare feet. Soft cinematic lighting with moderate contrast highlighting silhouette and fabric details. Sophisticated editorial fashion aesthetic, hyperrealistic, 8k, sharp focus. --ar 4:5. " + _IDENT_TRAIL,
    },
    "sn_high_impact": {
        "nome": "🔥 High Impact Sensual Editorial",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Editorial fashion portrait of [subject], well-defined curvy silhouette, long wavy black hair flowing down the back, wearing tight white high-neck jumpsuit, slightly translucent satin-finish fabric with deep side cutouts and crossed straps along the hip contour. Three-quarter pose, one hand firm on waist and the other gliding lightly along thigh, hip projected to one side, confident provocative posture, intense direct gaze. Elegant environment: white framed wall, crystal chandelier, vase of red roses, contrast between classical setting and striking presence. Cinematic side soft light with marked highlights, shadows emphasizing silhouette and fabric texture. Slightly translucent fabric subtly revealing contours, natural skin glow, hyperrealistic detail. High-fashion editorial framing, focus on form attitude presence. Strong sensual sophisticated provocative atmosphere, bold fashion campaign style. 8k ultra realistic sharp focus cinematic color grading. --ar 4:5. " + _IDENT_TRAIL,
    },
    "sn_street_edge": {
        "nome": "🎯 Street Edge Sensual",
        "cat": "sensual", "locked": True,
        "subject": "the woman",
        "prompt": "Fashion/lifestyle portrait of [subject] with voluminous curly hair, wearing oversized red streetwear hoodie (no visible brand) combined with fitted bottom piece in light leopard texture print, following body curves naturally. Pose: side position with hip projected, well-marked body line, looking over shoulder with intense confident expression. Outfit interaction: hoodie slightly displaced by body movement, contrast between volume on top and fitted bottom. Modern apartment with large mirror in background, clean contemporary aesthetic. Side natural lighting with moderate contrast, shadows highlighting silhouette and contours. Realistic fabric and skin texture, natural shine, clear shape definition without exaggeration. Editorial framing with mirror presence for depth. Strong sensual marked atmosphere, modern street-fashion attitude. Ultra-realistic 8k sharp focus cinematic color grading. --ar 4:5. " + _IDENT_TRAIL,
    },

    # ▼ Marca os estilos PREMIUM existentes como locked (motivar compra)
    # NOTA: estes estão definidos acima sem 'locked', vamos adicionar via _LOCKED_KEYS abaixo
}


# Lista de chaves de estilos PREMIUM existentes que devem aparecer trancados 🔒
# (separado para permitir override fácil sem editar cada dict)
_LOCKED_PREMIUM_KEYS = {
    "men_underwater", "men_darkhero",  # Men premium
    "u_lion_winter", "u_lion_desert", "u_lion_shadow",  # Lion trilogy
    "u_phone_spotify", "u_phone_neon", "u_phone_apple", "u_phone_street",  # Phone series
    "u_nw_warrior", "u_nw_pulse", "u_nw_arcane",  # Neon warrior
    "u_he_cine",  # Hero frame
    "x_a_p1", "x_a_p2",  # Comic story 1 — Sombras
    "x_b_p1", "x_b_p2", "x_b_p3", "x_b_p4", "x_b_p5",  # Comic story 2 — Jornada
    "co_polaroid_classic", "co_polaroid_romantic", "co_polaroid_playful",  # Couples
}
# Aplicar locked=True aos estilos premium acima (e os ja com 'locked': True ficam)
for _k in _LOCKED_PREMIUM_KEYS:
    if _k in PADRAO_STYLES:
        PADRAO_STYLES[_k]["locked"] = True
del _k


# Sub-grupos da categoria Unissex (para evitar 1 mega-lista)
PADRAO_UNISEX_GROUPS = {
    "classic":   {"nome": "🎭 Retratos Clássicos"},
    "lion":      {"nome": "🦁 Trilogia Leão"},
    "phone":     {"nome": "📱 Music Phone Series"},
    "editorial": {"nome": "🌸 Editorial Pôster"},
    "bw":        {"nome": "⚫ B&W Studio Portraits"},
    "hacker":    {"nome": "💻 Hacker Noir"},
    "crimson":   {"nome": "🔴 Trilogia Carmesim"},
    "neon":      {"nome": "⚡ Guerreiro Neon"},
    "emotion":   {"nome": "😔 Trilogia Emoção"},
    "skin":      {"nome": "🔬 Pele & Detalhes"},
    "submerged": {"nome": "👁️ Olhar Submerso"},
    "vintage":   {"nome": "🍂 Vintage Beetle"},
    "hero":      {"nome": "🦸 Hero Frame"},
    "lifestyle": {"nome": "☕ Lifestyle Editorial"},
    "epic":      {"nome": "🎬 Editorial Premium"},
    "scifi":     {"nome": "🔬 Sci-Fi / Cyber"},
}


# Histórias (para Casais e Comics)
PADRAO_STORIES = {
    "polaroid": {
        "cat": "couple",
        "nome": "🎞️ Polaroid Romance",
        "scenes": ["co_polaroid_classic", "co_polaroid_romantic", "co_polaroid_playful"],
    },
    "shadows": {
        "cat": "comic",
        "nome": "🦇 Sombras do Cemitério (2 páginas)",
        "scenes": ["x_a_p1", "x_a_p2"],
    },
    "journey": {
        "cat": "comic",
        "nome": "⚔️ A Jornada do Herói (5 páginas)",
        "scenes": ["x_b_p1", "x_b_p2", "x_b_p3", "x_b_p4", "x_b_p5"],
    },
}


def build_padrao_final_prompt(style_key, user_caption=""):
    """Combina o prompt fixo do estilo com a descrição do user.
    Substitui [subject] pelo género de referência (the man / the woman / the person)
    e anexa a descrição do user no fim."""
    style = PADRAO_STYLES.get(style_key)
    if not style:
        return None
    subject = style.get("subject", "the person")
    base = style["prompt"].replace("[subject]", subject)
    user_caption = (user_caption or "").strip()
    if user_caption:
        base = f"{base} Additional user request: {user_caption}"
    return base


# ==================== SISTEMA DE ACESSO PREMIUM (Sensual + Premium locks) ====================
# Plano: 2 estilos sensuais ficam livres. Resto + estilos premium ficam 🔒
# Desbloqueado quando o user faz a 1ª compra de créditos (qualquer pacote).
# Nessa altura, fica unlocked PERMANENTE para todos os estilos atuais e
# tem +30 dias para receber novos estilos lançados depois.
# Após 30d: nova compra renova os 30 dias para os novos estilos.

PREMIUM_ACCESS_FILE = "premium_access.json"
PREMIUM_ACCESS_LOCK = Lock()
ADMIN_PREMIUM_BLOCK_FILE = "admin_premium_block.json"  # admins secundários trancados
ADMIN_PREMIUM_BLOCK_LOCK = Lock()

# Estilos sensuais SEMPRE livres (sem 🔒)
FREE_SENSUAL_KEYS = {"sn_postshower", "sn_bedroom"}


def is_style_locked(style_key):
    """True se o estilo tem flag locked=True nas suas definições."""
    st = PADRAO_STYLES.get(style_key)
    if not st:
        return False
    return bool(st.get("locked"))


def grant_premium_access(user_id, snapshot_keys=None):
    """Concede acesso premium ao user. Guarda snapshot dos estilos atuais e
    janela de 30 dias para novos estilos.
    Idempotente: se já existir, atualiza updates_until (renova 30d) e adiciona
    novos estilos ao snapshot."""
    data = load_json(PREMIUM_ACCESS_FILE)
    uid = str(user_id)
    now = datetime.now()
    new_updates_until = (now + timedelta(days=30)).isoformat()
    if snapshot_keys is None:
        # Tudo o que está locked AGORA fica disponível para o user
        snapshot_keys = [k for k, v in PADRAO_STYLES.items() if v.get("locked")]

    if uid not in data:
        data[uid] = {
            "unlocked_at": now.isoformat(),
            "updates_until": new_updates_until,
            "base_keys": list(snapshot_keys),
        }
    else:
        # Renova janela de 30d e adiciona quaisquer estilos que entretanto apareceram
        data[uid]["updates_until"] = new_updates_until
        existing = set(data[uid].get("base_keys", []))
        existing.update(snapshot_keys)
        data[uid]["base_keys"] = sorted(existing)

    save_json(PREMIUM_ACCESS_FILE, data, PREMIUM_ACCESS_LOCK)
    logger.info(f"Premium access granted/renewed for user {user_id}")


def has_premium_access(user_id, style_key):
    """Verifica se o user tem acesso ao estilo (ignorando o lock).
    Regras:
      - SUPER admin (principal) = sempre acesso total
      - Admin secundário: acesso a não ser que esteja na lista de bloqueio
      - VIP: acesso total
      - User com premium ativo: tem acesso aos estilos do snapshot dele +
        novos estilos enquanto updates_until > now
      - Senão: sem acesso
    """
    # 1) Super admin (principal) — sempre tem tudo
    if is_super_admin(user_id):
        return True

    # 2) Admin secundário — tem por padrão, mas super admin pode trancar individualmente
    if is_any_admin(user_id):
        block_data = load_json(ADMIN_PREMIUM_BLOCK_FILE)
        if str(user_id) not in block_data:
            return True
        # caso esteja trancado, segue para regras normais

    # 3) VIPs sempre desbloqueados
    if is_vip(user_id):
        return True

    # 4) Premium adquirido?
    data = load_json(PREMIUM_ACCESS_FILE)
    entry = data.get(str(user_id))
    if not entry:
        return False

    # Estilo está no snapshot original do user?
    if style_key in (entry.get("base_keys") or []):
        return True

    # Estilo é novo (lançado depois) → só se ainda dentro dos 30 dias
    try:
        upd = datetime.fromisoformat(entry.get("updates_until", ""))
        if datetime.now() <= upd:
            # Adiciona automaticamente ao snapshot do user para reuso futuro
            entry.setdefault("base_keys", []).append(style_key)
            save_json(PREMIUM_ACCESS_FILE, data, PREMIUM_ACCESS_LOCK)
            return True
    except Exception:
        pass

    return False


def is_locked_for_user(user_id, style_key):
    """Conveniência: True se este estilo deve aparecer 🔒 trancado para este user."""
    if not is_style_locked(style_key):
        return False
    if style_key in FREE_SENSUAL_KEYS:
        return False
    return not has_premium_access(user_id, style_key)


def admin_toggle_secondary_premium_block(user_id, blocked):
    """Super admin tranca (blocked=True) ou destranca (blocked=False) acesso premium
    de um admin secundário."""
    data = load_json(ADMIN_PREMIUM_BLOCK_FILE)
    uid = str(user_id)
    if blocked:
        data[uid] = {"blocked_at": datetime.now().isoformat()}
    else:
        data.pop(uid, None)
    save_json(ADMIN_PREMIUM_BLOCK_FILE, data, ADMIN_PREMIUM_BLOCK_LOCK)


def is_secondary_admin_blocked(user_id):
    return str(user_id) in load_json(ADMIN_PREMIUM_BLOCK_FILE)





# ==================== GALLERY PROMPT CACHE (Ver Prompt no canal) ====================
GALLERY_PROMPTS_FILE = "gallery_prompts.json"
GALLERY_PROMPTS_LOCK = Lock()


def save_gallery_prompt(prompt_text, style_key=None):
    """Guarda o prompt completo associado a um ID curto. Retorna o ID.
    Se style_key pertencer a um estilo locked, marca o entry como locked
    (para o botão 🔒 Prompt Premium / waitlist do eBook)."""
    pid = secrets.token_urlsafe(6)  # ~8 chars
    data = load_json(GALLERY_PROMPTS_FILE)
    locked = bool(style_key and is_style_locked(style_key))
    data[pid] = {
        "prompt": prompt_text,
        "style_key": style_key,
        "locked": locked,
        "timestamp": datetime.now().isoformat()
    }
    # Mantém só os 5000 mais recentes para não inflacionar
    if len(data) > 5000:
        sorted_keys = sorted(data.keys(), key=lambda k: data[k].get("timestamp", ""), reverse=True)
        data = {k: data[k] for k in sorted_keys[:5000]}
    save_json(GALLERY_PROMPTS_FILE, data, GALLERY_PROMPTS_LOCK)
    return pid


def get_gallery_prompt_entry(pid):
    """Versão completa que devolve o entry inteiro (prompt + locked + style_key)."""
    if not pid:
        return None
    data = load_json(GALLERY_PROMPTS_FILE)
    return data.get(pid)


def get_gallery_prompt(pid):
    data = load_json(GALLERY_PROMPTS_FILE)
    entry = data.get(pid)
    if not entry:
        return None
    return entry.get("prompt")


# ==================== eBOOK WAITLIST ====================
EBOOK_WAITLIST_FILE = "ebook_waitlist.json"
EBOOK_WAITLIST_LOCK = Lock()


def add_to_ebook_waitlist(user_id, lang="pt"):
    """Regista user_id na lista de espera do eBook 'Remake Pixel Prompt Vault'.
    Idempotente — se já existir, atualiza só timestamp."""
    data = load_json(EBOOK_WAITLIST_FILE)
    uid = str(user_id)
    is_new = uid not in data
    data[uid] = {
        "lang": lang,
        "joined_at": datetime.now().isoformat() if is_new else data[uid].get("joined_at"),
        "updated_at": datetime.now().isoformat(),
    }
    save_json(EBOOK_WAITLIST_FILE, data, EBOOK_WAITLIST_LOCK)
    return is_new


def get_ebook_waitlist_count():
    return len(load_json(EBOOK_WAITLIST_FILE))


def get_ebook_waitlist_users():
    """Devolve lista de (user_id, lang) tuples — útil para broadcast admin."""
    data = load_json(EBOOK_WAITLIST_FILE)
    return [(int(uid), v.get("lang", "pt")) for uid, v in data.items()]


# ==================== STYLE PREVIEWS (auto-coleta da galeria) ====================
# Mapeia creation_id → style_key (escrito quando um estilo é aplicado).
# Usado depois pelo handler de publicação para guardar a preview real do canal.
STYLE_CREATION_MAP_FILE = "style_creation_map.json"
STYLE_CREATION_MAP_LOCK = Lock()

# Previews oficiais por estilo: {style_key: {file_id, channel_msg_id, updated_at}}
STYLE_PREVIEWS_FILE = "style_previews.json"
STYLE_PREVIEWS_LOCK = Lock()


def link_creation_to_style(creation_id, style_key):
    """Guarda o mapping creation_id → style_key (para poder recuperar
    quando a imagem for publicada na galeria)."""
    if not creation_id or not style_key:
        return
    data = load_json(STYLE_CREATION_MAP_FILE)
    data[creation_id] = {
        "style_key": style_key,
        "timestamp": datetime.now().isoformat()
    }
    # Limita a 5000 entradas mais recentes
    if len(data) > 5000:
        sorted_keys = sorted(data.keys(), key=lambda k: data[k].get("timestamp", ""), reverse=True)
        data = {k: data[k] for k in sorted_keys[:5000]}
    save_json(STYLE_CREATION_MAP_FILE, data, STYLE_CREATION_MAP_LOCK)


def get_style_for_creation(creation_id):
    if not creation_id:
        return None
    data = load_json(STYLE_CREATION_MAP_FILE)
    entry = data.get(creation_id)
    return entry.get("style_key") if entry else None


def save_style_preview(style_key, file_id, channel_msg_id=None):
    """Guarda/atualiza a preview oficial de um estilo (a mais recente vence)."""
    if not style_key or not file_id:
        return
    data = load_json(STYLE_PREVIEWS_FILE)
    data[style_key] = {
        "file_id": file_id,
        "channel_msg_id": channel_msg_id,
        "updated_at": datetime.now().isoformat()
    }
    save_json(STYLE_PREVIEWS_FILE, data, STYLE_PREVIEWS_LOCK)


def get_style_preview(style_key):
    if not style_key:
        return None
    data = load_json(STYLE_PREVIEWS_FILE)
    return data.get(style_key)




# ==================== NOVO SISTEMA DE MODELOS (v2) ====================
# Marca limpa, precos premium, mesmo backend AI (2 modelos por tras)
MODELS_V2 = {
    "snap_fast": {
        "nome": "⚡ Snap Fast",
        "desc": "Rápido e simples — perfeito para testar ideias",
        "replicate_id": "xai/grok-imagine-image",
        "custo": 3,
        "backend": "grok",
        "prompt_boost": "",
    },
    "creative_flow": {
        "nome": "🎨 Creative Flow",
        "desc": "Equilíbrio entre criatividade e qualidade (⭐ Default)",
        "replicate_id": "black-forest-labs/flux-2-klein-9b",
        "custo": 5,
        "backend": "flux",
        "prompt_boost": ", creative composition, beautiful lighting, high quality",
        "default": True,
    },
    "pro_vision": {
        "nome": "🔥 Pro Vision",
        "desc": "Detalhe profissional, alta resolução",
        "replicate_id": "black-forest-labs/flux-2-klein-9b",
        "custo": 7,
        "backend": "flux",
        "prompt_boost": ", professional photography, ultra detailed, 8k, sharp focus, cinematic lighting, masterpiece",
    },
    "ultra_real": {
        "nome": "💎 Ultra Real",
        "desc": "Realismo máximo — escolhe estilo de realismo",
        "replicate_id": "black-forest-labs/flux-2-klein-9b",
        "custo": 10,
        "backend": "flux",
        "prompt_boost": "",
        "uses_realism_presets": True,  # ativa submenu Original/Expressao/Suave
    },
    "edit_master": {
        "nome": "✂️ Edit Master",
        "desc": "Edição inteligente de imagens existentes",
        "replicate_id": "black-forest-labs/flux-2-klein-9b",
        "custo": 4,
        "backend": "flux",
        "prompt_boost": "",
        "editing_only": True,
    },
}

DEFAULT_MODEL_V2 = "creative_flow"


def get_model_v2(key):
    return MODELS_V2.get(key, MODELS_V2[DEFAULT_MODEL_V2])


def get_user_model_v2(user_id):
    """Modelo selecionado pelo user (guardado em settings)."""
    data = load_json("user_settings.json")
    return data.get(str(user_id), {}).get("model_v2", DEFAULT_MODEL_V2)


def set_user_model_v2(user_id, model_key):
    data = load_json("user_settings.json")
    uid = str(user_id)
    if uid not in data:
        data[uid] = {}
    data[uid]["model_v2"] = model_key
    save_json("user_settings.json", data, Lock())


# ==================== NOVOS TAMANHOS (4 apenas) ====================
SIZES_V2 = {
    "square":    {"nome": "⬛ Square (1:1)",     "ar": "1:1"},
    "portrait":  {"nome": "📱 Portrait (4:5)",   "ar": "4:5"},
    "story":     {"nome": "📸 Story (9:16)",     "ar": "9:16"},
    "landscape": {"nome": "🖼️ Landscape (16:9)", "ar": "16:9"},
}
DEFAULT_SIZE_V2 = "square"


def get_user_size_v2(user_id):
    data = load_json("user_settings.json")
    return data.get(str(user_id), {}).get("size_v2", DEFAULT_SIZE_V2)


def set_user_size_v2(user_id, size_key):
    data = load_json("user_settings.json")
    uid = str(user_id)
    if uid not in data:
        data[uid] = {}
    data[uid]["size_v2"] = size_key
    save_json("user_settings.json", data, Lock())


# ==================== ESTILOS UNIFICADOS V2 (43 — merge dos antigos + novos) ====================
STYLES_V2 = {
    "anime":          {"nome": "Anime",          "suffix": ", anime style, manga aesthetic"},
    "realistic":      {"nome": "Realistic",      "suffix": ", photorealistic, realistic photography"},
    "cinematic":      {"nome": "Cinematic",      "suffix": ", cinematic lighting, movie scene, film still"},
    "cyberpunk":      {"nome": "Cyberpunk",      "suffix": ", cyberpunk, neon, futuristic city, blade runner aesthetic"},
    "fantasy":        {"nome": "Fantasy",        "suffix": ", fantasy art, magical, ethereal"},
    "dark":           {"nome": "Dark",           "suffix": ", dark moody atmosphere, low-key lighting, shadows"},
    "minimalist":     {"nome": "Minimalist",     "suffix": ", minimalist composition, clean, simple"},
    "3d_render":      {"nome": "3D Render",      "suffix": ", 3D render, octane render, blender style"},
    "pixel_art":      {"nome": "Pixel Art",      "suffix": ", pixel art, 16-bit, retro game"},
    "oil_painting":   {"nome": "Oil Painting",   "suffix": ", oil painting, thick brushstrokes, classical art"},
    "watercolor":     {"nome": "Watercolor",     "suffix": ", watercolor painting, soft washes, paper texture"},
    "sketch":         {"nome": "Sketch",         "suffix": ", pencil sketch, hand drawn, graphite"},
    "cartoon":        {"nome": "Cartoon",        "suffix": ", cartoon style, bold outlines, vibrant colors"},
    "comic":          {"nome": "Comic",          "suffix": ", comic book style, halftone, ink lines"},
    "futuristic":     {"nome": "Futuristic",     "suffix": ", futuristic, sci-fi design, sleek tech"},
    "vintage":        {"nome": "Vintage",        "suffix": ", vintage, retro, film grain, 70s aesthetic"},
    "neon":           {"nome": "Neon",           "suffix": ", neon lighting, vibrant neon colors"},
    "sci_fi":         {"nome": "Sci-Fi",         "suffix": ", science fiction, space, futuristic technology"},
    "portrait":       {"nome": "Portrait",       "suffix": ", portrait photography, studio lighting, bokeh"},
    "studio_lighting":{"nome": "Studio Light",   "suffix": ", studio lighting, softbox, professional"},
    "hdr":            {"nome": "HDR",            "suffix": ", HDR, high dynamic range, rich details"},
    "dreamy":         {"nome": "Dreamy",         "suffix": ", dreamy, soft focus, ethereal atmosphere"},
    "surreal":        {"nome": "Surreal",        "suffix": ", surreal, dreamlike, impossible composition"},
    "abstract":       {"nome": "Abstract",       "suffix": ", abstract art, non-representational"},
    "game_art":       {"nome": "Game Art",       "suffix": ", video game concept art, AAA game style"},
    "illustration":   {"nome": "Illustration",   "suffix": ", digital illustration, editorial art"},
    "fashion":        {"nome": "Fashion",        "suffix": ", fashion photography, vogue style, high-fashion"},
    "street_style":   {"nome": "Street Style",   "suffix": ", street photography, candid, urban aesthetic"},
    "luxury":         {"nome": "Luxury",         "suffix": ", luxury aesthetic, gold accents, premium feel"},
    "soft_light":     {"nome": "Soft Light",     "suffix": ", soft natural light, gentle shadows"},
    "hard_light":     {"nome": "Hard Light",     "suffix": ", hard directional lighting, strong shadows"},
    "ghibli":         {"nome": "Ghibli Style",   "suffix": ", Studio Ghibli style, Miyazaki, soft painterly anime"},
    "disney":         {"nome": "Disney Style",   "suffix": ", Disney animation style, 3D animated character"},
    "photorealistic": {"nome": "Photorealistic", "suffix": ", photorealistic, hyper-realistic, DSLR photo"},
    "concept_art":    {"nome": "Concept Art",    "suffix": ", concept art, matte painting, movie concept"},
    "low_poly":       {"nome": "Low Poly",       "suffix": ", low poly 3D art, geometric, flat shading"},
    "high_detail":    {"nome": "High Detail",    "suffix": ", ultra high detail, intricate, 8k"},
    "epic_scene":     {"nome": "Epic Scene",     "suffix": ", epic scene, grand scale, dramatic"},
    "nature":         {"nome": "Nature",         "suffix": ", nature photography, natural environment"},
    "urban":          {"nome": "Urban",          "suffix": ", urban environment, city scene"},
    "night_mode":     {"nome": "Night Mode",     "suffix": ", night scene, dark atmosphere, moon light"},
    "golden_hour":    {"nome": "Golden Hour",    "suffix": ", golden hour, warm sunset light"},
    "bw":             {"nome": "Black & White",  "suffix": ", black and white, monochrome, high contrast"},
}


def get_user_styles_v2(user_id):
    """Estilos selecionados (lista). Permite multiplos."""
    data = load_json("user_settings.json")
    return data.get(str(user_id), {}).get("styles_v2", [])


def set_user_styles_v2(user_id, styles_list):
    data = load_json("user_settings.json")
    uid = str(user_id)
    if uid not in data:
        data[uid] = {}
    data[uid]["styles_v2"] = styles_list[:5]  # max 5
    save_json("user_settings.json", data, Lock())


def toggle_user_style_v2(user_id, style_key):
    cur = get_user_styles_v2(user_id)
    if style_key in cur:
        cur = [s for s in cur if s != style_key]
    else:
        cur.append(style_key)
    set_user_styles_v2(user_id, cur[:5])
    return cur


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
            "num_outputs": num_outputs,
            "disable_safety_checker": True
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

def gerar_imagem_pro(image_input, prompt_override=None):
    """Melhora imagem usando Modelo Pro (FLUX.2 Klein 9B).
    Se prompt_override for fornecido, usa-o em vez do prompt_fixo."""
    try:
        prompt_final = prompt_override if prompt_override else MODELO_PRO["prompt_fixo"]
        input_params = {
            "prompt": prompt_final,
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

def execute_pro_single(chat_id, user_id, lang, photo_data, prompt_override, preset_nome=None):
    """Executa edicao Pro numa foto unica.
    prompt_override: prompt final enviado ao FLUX.2 (custom do user ou de um preset).
    preset_nome: nome legivel do preset (opcional, para mostrar no caption).
    Debita creditos, processa e faz refund em caso de falha.
    """
    if not use_credit(user_id, MODELO_PRO["custo"]):
        bot.send_message(chat_id, "❌ Créditos insuficientes!")
        return

    proc_texts = {
        "pt": "✨ <b>Modelo Pro ativado!</b>\nAplicando melhoria fotorrealista avancada...\nIsto pode demorar um pouco.",
        "en": "✨ <b>Pro Model activated!</b>\nApplying advanced photorealistic enhancement...\nThis may take a moment.",
        "es": "✨ <b>Modelo Pro activado!</b>\nAplicando mejora fotorrealista avanzada...\nEsto puede tardar un poco."
    }
    proc_msg = bot.send_message(chat_id, proc_texts.get(lang, proc_texts["pt"]), parse_mode='HTML')

    try:
        file_info = bot.get_file(photo_data["file_id"])
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"

        urls = gerar_imagem_pro(image_input=image_data_url, prompt_override=prompt_override)

        try:
            bot.delete_message(chat_id, proc_msg.message_id)
        except:
            pass

        preset_line = f"\n🎯 Preset: {preset_nome}" if preset_nome else ""
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "edit", prompt_override, url)
            creditos_restantes = get_user_credits(user_id)

            caption_texts = {
                "pt": f"✨ <b>Melhoria Pro aplicada!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B){preset_line}\n💳 Créditos restantes: <code>{creditos_restantes}</code>",
                "en": f"✨ <b>Pro enhancement applied!</b>\n🤖 Model: Pro (FLUX.2 Klein 9B){preset_line}\n💳 Credits remaining: <code>{creditos_restantes}</code>",
                "es": f"✨ <b>Mejora Pro aplicada!</b>\n🤖 Modelo: Pro (FLUX.2 Klein 9B){preset_line}\n💳 Créditos restantes: <code>{creditos_restantes}</code>"
            }
            bot.send_photo(chat_id, img_data, caption=caption_texts.get(lang, caption_texts["pt"]),
                           reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')

        update_user_stats(user_id, "total_edits")
        logger.info(f"Edicao Pro para user {user_id} (preset={preset_nome or 'custom'})")

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
            bot.edit_message_text(error_texts.get(lang, error_texts["pt"]), chat_id, proc_msg.message_id)
        except:
            bot.send_message(chat_id, error_texts.get(lang, error_texts["pt"]))
        logger.error(f"Erro Pro: {e}")



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
refine_states = {}  # {user_id: {"creation_id":..., "base_prompt":..., "ts":...}}
carousel_states = {}
bot_paused = False
pause_message = ""

def detect_image_intent(text):
    """Deteta se user quer GERAR imagem do zero (sem foto).
    VERSAO CONSERVADORA: so dispara em frases que pedem CLARAMENTE
    uma geracao direta, nao em descricoes ambiguas.
    Casos ambiguos -> retorna False, o chat IA decide.
    """
    if not text:
        return False
    text_lower = text.lower().strip()

    # Patterns que claramente indicam geracao direta
    # (precisam ter verbo imperativo + objeto imagem)
    import re as _re
    direct_patterns = [
        r'^(gera|gere|gerar|cria|crie|criar|faca|faz|faça|desenha|desenhe|generate|create|make|draw|dibuja|crea|dame|give me|show me)\s+(uma|um|a|an|a |an )?\s*(imagem|foto|picture|image|imagen|photo|pic|flyer|flayer|poster|cartaz)\s',
        r'^(uma|um|a|an)\s+(imagem|foto|picture|image|imagen)\s+de\s+',
        r'^(imagine|imagina|imagina|visualize)\s+',
        r'^(quero|queria|preciso|i want|need)\s+(uma|um|a|an)\s+(imagem|foto|picture|image)\b',
    ]
    for pat in direct_patterns:
        if _re.search(pat, text_lower):
            return True

    # Se for muito curto (<5 palavras) e so descritivo — ambiguo, deixa chat decidir
    return False


def classify_user_intent_ai(text, lang="pt"):
    """Classifica intent usando AI: 'chat', 'generate', 'edit_help', 'idea_help'.
    Usa GPT-4o-mini (barato). Retorna dict {intent, reasoning, suggested_prompt}
    """
    try:
        system = (
            "You are an intent classifier for a Telegram AI photo bot. "
            "Classify the user message into ONE of these intents:\n"
            "- 'chat': casual conversation, greetings, questions about bot\n"
            "- 'generate': user wants to GENERATE a NEW image from scratch RIGHT NOW with clear description\n"
            "- 'edit_help': user has photos to edit/merge and needs guidance\n"
            "- 'idea_help': user needs creative ideas, is stuck, wants suggestions\n"
            "Return ONLY valid JSON: {\"intent\": \"...\", \"ready_to_generate\": true/false, \"clean_prompt\": \"...\"}\n"
            "'ready_to_generate' = true ONLY if user gave a detailed enough description (>5 meaningful words).\n"
            "'clean_prompt' = extracted visual description in English (empty if not ready)."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text[:500]}
            ],
            max_tokens=150,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        import json as _json
        result = _json.loads(resp.choices[0].message.content)
        return result
    except Exception as e:
        logger.warning(f"intent classify err: {e}")
        return {"intent": "chat", "ready_to_generate": False, "clean_prompt": ""}


def get_smart_chat_response(user_id, message, lang="pt"):
    """Chat IA — assistente criativo proativo.
    Sabe pedir fotos, sugerir ideias, guiar o utilizador."""
    try:
        if user_id not in chat_contexts:
            chat_contexts[user_id] = []

        chat_contexts[user_id].append({"role": "user", "content": message})
        if len(chat_contexts[user_id]) > 12:
            chat_contexts[user_id] = chat_contexts[user_id][-12:]

        creditos = get_user_credits(user_id)
        personality = get_user_personality(user_id)
        personality_info = AI_PERSONALITIES[personality]

        lang_names = {"pt": "Português", "en": "English", "es": "Español", "fr": "Français"}

        assistant_prompt = f"""{personality_info['system']}

LÍNGUA: Responde SEMPRE em {lang_names.get(lang, 'Português')}.

ÉS O ASSISTENTE CRIATIVO do Remake_Pixel (bot Telegram de edição de fotos IA).

🎨 QUANDO O UTILIZADOR ESTÁ SEM IDEIAS:
- Faz 2-3 perguntas curtas para perceber o estilo dele (moderno/retro, cores, mood)
- Sugere 3 ideias concretas e diferentes
- Oferece gerar uma delas (10 créditos)

📸 QUANDO QUER EDITAR/COMBINAR FOTOS (ex: flyer, juntar 2 pessoas):
- NÃO gera imagem aleatória! Pede: "Envia-me as fotos aqui no chat (podes enviar 2 a 5 juntas)."
- Explica: "Depois escolhe 'Modelo Pro' para qualidade máxima ou 'Padrão' para rápido."
- Se for flyer: pergunta texto/cores/estilo DEPOIS das fotos chegarem.

💡 QUANDO PEDE QUESTIONÁRIO/HELP PARA CRIAR:
- NÃO gera imagem! Guia passo a passo:
  1. "Que tipo de imagem? (retrato / paisagem / flyer / arte / outro)"
  2. "Estilo? (realista / anime / cyberpunk / minimalista / etc)"
  3. "Cores principais?"
  4. "Algum elemento obrigatório?"
- Depois: "Posso gerar agora — confirmas com 'sim'?"

🚫 NUNCA:
- Gerar imagem sem o user confirmar explicitamente
- Ignorar quando o user menciona que tem fotos
- Fazer perguntas demasiado longas (max 3 perguntas por mensagem)

✅ SEMPRE:
- Mensagens curtas (2-4 frases)
- Emojis com moderação
- Perguntas abertas se user está indeciso
- Sugestões concretas se pedem ajuda

INFO DO USER:
• Créditos: {creditos}
• Modelos: Padrão (10c — com legenda direto, sem legenda 65+ estilos prontos), Pro (18c), Artístico (13c), Carrossel (N c)
• Envia fotos → ofereço 3 modelos; envia texto descritivo → ofereço gerar
• Menu: "Gerar Fotos" (criar do zero) / "Editar Fotos" (enviar foto) / "Carrossel" (série)

SE O USER DISSER ALGO AMBÍGUO, PERGUNTA. NÃO ASSUMAS."""

        messages = [{"role": "system", "content": assistant_prompt}]
        messages.extend(chat_contexts[user_id])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=280,
            temperature=0.8
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
               "🎁 Indicar", "❓ Ajuda", "🤖 Assistente IA (grátis)", "🎬 Vídeo (20 cr)", "💡 Sugerir Prompt"],
        "en": ["🎨 Generate", "📸 Edit Photos", "📱 Carousel", "💳 Credits", "🛒 Buy", 
               "📚 History", "⭐ Favorites", "📊 Stats", "⚙️ Settings", 
               "🎁 Refer", "❓ Help", "🤖 AI Assistant (free)", "🎬 Video (20 cr)", "💡 Suggest Prompt"],
        "es": ["🎨 Generar", "📸 Editar Fotos", "📱 Carrusel", "💳 Créditos", "🛒 Comprar", 
               "📚 Historial", "⭐ Favoritos", "📊 Stats", "⚙️ Config", 
               "🎁 Referir", "❓ Ayuda", "🤖 Asistente IA (gratis)", "🎬 Video (20 cr)", "💡 Sugerir Prompt"],
    }
    t = texts.get(lang, texts["pt"])
    # ⭐ NOVO MENU v2 — 5 seccoes principais + IA chat em destaque
    markup.add(telebot.types.InlineKeyboardButton(t[11], callback_data="action_ai_chat"))
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data="action_create"),
        telebot.types.InlineKeyboardButton(t[1], callback_data="action_edit_photos")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[12], callback_data="action_video"),
        telebot.types.InlineKeyboardButton(t[13], callback_data="action_suggest")
    )
    # Estilos (shortcut direto, nao duplicado com Settings)
    styles_label = {"pt": "🎭 Estilos", "en": "🎭 Styles", "es": "🎭 Estilos"}
    markup.add(
        telebot.types.InlineKeyboardButton(styles_label.get(lang, "🎭 Estilos"), callback_data="v2_styles_menu"),
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
        "pt": ["⭐ Favoritar", "🔗 Partilhar", "🔁 Gerar outra", "✨ Refinar", "📢 Publicar na Galeria"],
        "en": ["⭐ Favorite", "🔗 Share", "🔁 Generate again", "✨ Refine", "📢 Publish to Gallery"],
        "es": ["⭐ Favorito", "🔗 Compartir", "🔁 Generar otra", "✨ Refinar", "📢 Publicar en Galería"],
        "fr": ["⭐ Favori", "🔗 Partager", "🔁 Régénérer", "✨ Affiner", "📢 Publier à la Galerie"]
    }
    t = texts.get(lang, texts["pt"])
    markup.add(
        telebot.types.InlineKeyboardButton(t[0], callback_data=f"fav_{creation_id}"),
        telebot.types.InlineKeyboardButton(t[1], callback_data=f"share_{creation_id}")
    )
    markup.add(
        telebot.types.InlineKeyboardButton(t[2], callback_data=f"regen_{creation_id}"),
        telebot.types.InlineKeyboardButton(t[3], callback_data=f"refine_{creation_id}")
    )
    markup.add(telebot.types.InlineKeyboardButton(t[4], callback_data=f"gallery_{creation_id}"))
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
            "pt": f"📸 <b>{len(photos)} fotos recebidas!</b>\n\n<b>Escolha o modelo:</b>\n\n🎨 <b>Modelo Padrão</b> ({MODELO_PADRAO['custo']} créditos)\nCombina as fotos conforme descrição\n\n✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créditos)\nCombina com melhoria fotorrealista\n\n💳 Seus créditos: <code>{creditos}</code>",
            "en": f"📸 <b>{len(photos)} photos received!</b>\n\n<b>Choose model:</b>\n\n🎨 <b>Standard</b> ({MODELO_PADRAO['custo']} credits)\nCombine photos as described\n\n✨ <b>Pro Model</b> ({MODELO_PRO['custo']} credits)\nCombine with photorealistic enhancement\n\n💳 Your credits: <code>{creditos}</code>",
            "es": f"📸 <b>{len(photos)} fotos recibidas!</b>\n\n<b>Elige modelo:</b>\n\n🎨 <b>Modelo Estandar</b> ({MODELO_PADRAO['custo']} créditos)\nCombina las fotos segun descripcion\n\n✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créditos)\nCombina con mejora fotorrealista\n\n💳 Tus créditos: <code>{creditos}</code>"
        }
        markup.add(
            telebot.types.InlineKeyboardButton(f"🎨 Padrão · {MODELO_PADRAO['custo']} créditos", callback_data="multi_model_padrao"),
            telebot.types.InlineKeyboardButton(f"✨ Pro · {MODELO_PRO['custo']} créditos", callback_data="multi_model_pro"),
            telebot.types.InlineKeyboardButton(f"🎭 Artístico · {MODELO_ARTISTICO['custo']} créditos", callback_data="multi_model_artistico"),
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


def execute_combine_pro(user_id, lang, caption, prompt_override=None):
    """Executa combinacao com modelo Pro.
    Se prompt_override for fornecido, substitui o prompt base (ex: preset de realismo)."""
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
        
        if prompt_override:
            enhanced_prompt = prompt_override
        elif caption:
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
    # GATE DE SEGURANCA (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=True)
    if not allowed:
        bot.send_message(chat_id, deny_message(lang, reason, extra), parse_mode='HTML')
        return
    if reason == "shadowban":
        log_system_event("info", "shadowban_drop", f"Criacao dropada user {user_id}", user_id)
        return

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
        bot.send_message(call.message.chat.id, "🎨 <b>Bem-vindo ao Remake Pixel!</b>\n\nCrie e edite imagens com IA.\n30 créditos grátis para experimentar!", parse_mode='HTML')
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
        # ⭐ NOVO FLOW V2: prompt → confirm model → generate
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        user_states[user_id] = "v2_awaiting_prompt"
        v2_flows[user_id] = {"step": "awaiting_prompt", "is_edit": False}
        txt = {
            "pt": ("🎨 <b>Criar Imagem</b>\n\n"
                   "Descreve a imagem que queres gerar:\n"
                   "<i>Ex: 'um gato cyberpunk num telhado à noite'</i>\n\n"
                   f"🎭 Usa '🎭 Estilos' no menu para escolher estilos antes."),
            "en": ("🎨 <b>Create Image</b>\n\nDescribe the image:\n"
                   "<i>Ex: 'cyberpunk cat on a rooftop at night'</i>"),
            "es": ("🎨 <b>Crear Imagen</b>\n\nDescribe la imagen:\n"
                   "<i>Ej: 'gato cyberpunk en un tejado de noche'</i>"),
        }
        bot.send_message(call.message.chat.id, txt.get(lang, txt["pt"]), parse_mode='HTML')
        return

    elif action == "create_legacy":  # desabilitado
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
                   "Envia 1 a 5 imagens no chat.\n\n"
                   "<b>3 modos disponíveis:</b>\n\n"
                   f"🎨 <b>Padrão</b> ({MODELO_PADRAO['custo']} cred)\n"
                   "→ Com legenda: edita conforme a tua descrição (direto)\n"
                   "→ Sem legenda: 🎨 escolhe entre <b>65+ estilos prontos</b> (Homens, Mulheres, Unissex, Flyers, Casais, Comics)\n"
                   "→ Ex: 'Mais qualidade', 'Remove o fundo' ou um estilo pré-feito\n\n"
                   f"✨ <b>Pro</b> ({MODELO_PRO['custo']} cred)\n"
                   "→ Melhoria fotorrealista (FLUX.2 Klein 9B)\n"
                   "→ Submenus: Personalizar, Deixa mais realista (7 presets), 🎭 Estilo & Humor (7), ✨ Enhancements Avançados (6)\n\n"
                   f"🎭 <b>Artístico</b> ({MODELO_ARTISTICO['custo']} cred)\n"
                   "→ Transforma em 33 estilos (anime, Disney, etc.)\n"
                   "→ Prompt opcional\n\n"
                   "💡 <b>Dica:</b> Envia 2-5 fotos juntas para combinar (ou 2 fotos para estilos de 'Casais')!"),
            "en": ("📸 <b>Edit Photos</b>\n\n"
                   "Send 1 to 5 images in the chat.\n\n"
                   "<b>3 modes available:</b>\n\n"
                   f"🎨 <b>Standard</b> ({MODELO_PADRAO['custo']} cred)\n"
                   "→ With caption: edits using your description (direct)\n"
                   "→ Without caption: 🎨 pick from <b>65+ ready styles</b> (Men, Women, Unisex, Flyers, Couples, Comics)\n\n"
                   f"✨ <b>Pro</b> ({MODELO_PRO['custo']} cred)\n"
                   "→ Photorealistic enhancement (FLUX.2 Klein 9B)\n"
                   "→ Submenus: Custom, Make it Realistic (7 presets), 🎭 Style & Mood (7), ✨ Advanced Enhancements (6)\n\n"
                   f"🎭 <b>Artistic</b> ({MODELO_ARTISTICO['custo']} cred) — 33 art styles, optional prompt\n\n"
                   "💡 Send 2-5 photos together to combine (or 2 photos for 'Couples' styles)!"),
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
        # REMOVIDO: feature desativada
        bot.answer_callback_query(call.id, "Feature removida.", show_alert=False)
        return

    elif action == "video":
        # Atalho para /video
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        # Reaproveita a logica do /video
        cmd_video(call.message)
        return

    elif action == "suggest":
        # Atalho para /sugerir
        user_states[user_id] = "awaiting_suggest_topic"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        ask_texts = {
            "pt": ("💡 <b>Sugestões de Prompt</b>\n\n"
                   "Escreve um <b>tema curto</b> e eu sugiro 3 prompts profissionais para usares.\n\n"
                   "<i>Ex: \"praia ao pôr do sol\", \"retrato cyberpunk\", \"comida japonesa\"</i>"),
            "en": ("💡 <b>Prompt Suggestions</b>\n\n"
                   "Type a <b>short topic</b> and I'll suggest 3 pro prompts.\n\n"
                   "<i>Ex: \"sunset beach\", \"cyberpunk portrait\", \"japanese food\"</i>"),
            "es": ("💡 <b>Sugerencias de Prompt</b>\n\n"
                   "Escribe un <b>tema corto</b> y te sugiero 3 prompts pro.\n\n"
                   "<i>Ej: \"playa al atardecer\", \"retrato cyberpunk\", \"comida japonesa\"</i>")
        }
        bot.send_message(call.message.chat.id, ask_texts.get(lang, ask_texts["pt"]),
                         reply_markup=cancel_keyboard(lang), parse_mode='HTML')
        return

    elif action == "ai_chat":
        # Ativa modo assistente IA: reseta contexto e mostra intro
        chat_contexts[user_id] = []
        intro_texts = {
            "pt": ("🤖 <b>Assistente IA — Grátis!</b>\n\n"
                   "Eu sou o teu assistente criativo. Posso ajudar-te a:\n\n"
                   "✨ <b>Tirar ideias do zero</b> — sem inspiração? Pergunto-te 3 coisas e sugiro\n"
                   "📸 <b>Preparar uma edição</b> — dizes-me o que queres, eu guio-te passo a passo\n"
                   "🎨 <b>Escolher o modelo certo</b> — Padrão? Pro? Artístico? Eu explico\n"
                   "💡 <b>Melhorar um prompt</b> — dás-me a ideia, transformo num prompt top\n\n"
                   "<i>Escreve no chat qualquer coisa — eu respondo!</i>\n"
                   "<i>Ex: \"quero um flyer mas estou sem ideias\"</i>"),
            "en": ("🤖 <b>AI Assistant — Free!</b>\n\n"
                   "I'm your creative helper. I can:\n\n"
                   "✨ <b>Give you ideas</b> — stuck? I ask 3 things and suggest\n"
                   "📸 <b>Prepare an edit</b> — tell me what you want, I guide\n"
                   "🎨 <b>Choose the right model</b> — Standard? Pro? I explain\n"
                   "💡 <b>Improve a prompt</b> — rough idea → perfect prompt\n\n"
                   "<i>Just type anything — I'll reply!</i>"),
            "es": ("🤖 <b>Asistente IA — ¡Gratis!</b>\n\n"
                   "Soy tu ayudante creativo. Puedo:\n\n"
                   "✨ <b>Darte ideas</b> — ¿sin inspiración? Pregunto 3 cosas y sugiero\n"
                   "📸 <b>Preparar edición</b> — dime qué quieres, yo te guío\n"
                   "🎨 <b>Elegir modelo</b> — ¿Estándar? ¿Pro? Yo explico\n"
                   "💡 <b>Mejorar prompt</b> — idea → prompt perfecto\n\n"
                   "<i>Solo escribe — te respondo!</i>"),
        }
        bot.send_message(call.message.chat.id, intro_texts.get(lang, intro_texts["pt"]), parse_mode='HTML')
        return

    elif action == "help":
        texts = {
            "pt": (f"❓ <b>Ajuda - Remake Pixel</b>\n\n"
                   f"<b>🎨 GERAR IMAGENS</b>\n"
                   f"No menu, clica em 'Gerar Fotos' e descreve o que queres criar.\n\n"
                   f"<b>📸 EDITAR FOTOS</b>\n"
                   f"Envia 1 a 5 fotos no chat.\n"
                   f"🎨 <b>Padrão</b> ({MODELO_PADRAO['custo']} cred) — Com legenda: edita direto pela tua descrição. <b>Sem legenda: 65+ estilos prontos</b> (Homens, Mulheres, Unissex, Flyers, Casais, Comics)\n"
                   f"✨ <b>Pro</b> ({MODELO_PRO['custo']} cred) — Melhoria fotorrealista. Submenus: Personalizar, 📷 Realista (7), 🎭 Estilo & Humor (7), ✨ Enhancements Avançados (6)\n"
                   f"🎭 <b>Artístico</b> ({MODELO_ARTISTICO['custo']} cred) — 33 estilos artísticos\n"
                   f"💑 <b>Casais</b> — Envia 2 fotos juntas (ou 1 dos dois) e usa o estilo 'Casais' do Padrão\n"
                   f"📚 <b>Comics</b> — Páginas de banda desenhada estilo Walking Dead (cenas com diálogo)\n\n"
                   f"<b>📱 CARROSSEL</b>\n"
                   f"Gera 2-4 imagens em sequência para Instagram.\n\n"
                   f"<b>⚙️ CONFIGURAÇÕES</b>\n"
                   f"Estilos visuais (33 opções), formato (Instagram, TikTok, etc.), variações e personalidade da IA.\n\n"
                   f"<b>💬 CHAT IA</b>\n"
                   f"Escreve qualquer mensagem para conversar com a IA. Grátis!\n\n"
                   f"<b>🖼️ GALERIA @RemakePixel_Gallery</b>\n"
                   f"Cada imagem partilhada tem agora <b>📋 Ver Prompt</b> — clica para receberes o prompt completo em DM e reutilizares.\n\n"
                   f"<b>📋 COMANDOS</b>\n"
                   f"/menu — Menu principal\n"
                   f"/start — Reiniciar bot\n"
                   f"/wizard — Assistente de criação\n"
                   f"/estilos — Catálogo dos 65+ estilos do Padrão (com previews reais)\n"
                   f"/creditos — Ver saldo\n"
                   f"/idioma — Mudar idioma\n"
                   f"/termos — Termos de uso\n\n"
                   f"Dúvidas? Clica abaixo para falar com o suporte!"),
            "en": (f"❓ <b>Help - Remake Pixel</b>\n\n"
                   f"<b>🎨 GENERATE</b> — Click 'Generate' and describe what you want.\n"
                   f"<b>📸 EDIT PHOTOS</b> — Send 1-5 photos.\n"
                   f"🎨 <b>Standard</b> ({MODELO_PADRAO['custo']} cred) — With caption: direct edit. Without caption: <b>65+ ready styles</b> (Men, Women, Unisex, Flyers, Couples, Comics)\n"
                   f"✨ <b>Pro</b> ({MODELO_PRO['custo']} cred) — Photorealistic. Submenus: Custom, 📷 Realistic (7), 🎭 Style & Mood (7), ✨ Advanced Enhancements (6)\n"
                   f"🎭 <b>Artistic</b> ({MODELO_ARTISTICO['custo']} cred) — 33 art styles\n"
                   f"💑 <b>Couples</b> — Send 2 photos and pick a 'Couples' style under Standard\n"
                   f"📚 <b>Comics</b> — Walking-Dead-style comic pages with dialogue\n\n"
                   f"<b>📱 CAROUSEL</b> — Generate 2-4 sequential images.\n"
                   f"<b>⚙️ SETTINGS</b> — 33 styles, formats, variations.\n"
                   f"<b>💬 AI CHAT</b> — Free, just type!\n"
                   f"<b>🖼️ GALLERY</b> — Each shared image now has <b>📋 View Prompt</b> button.\n\n"
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
        
        share_text = "Experimenta o Remake Pixel! Cria e edita imagens com IA no Telegram. 30 créditos grátis!"
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('regen_'))
def callback_regen(call):
    """Regenera uma criacao com o MESMO prompt usando Modelo Padrao."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    creation_id = call.data.replace('regen_', '')
    creation = get_creation_by_id(user_id, creation_id)
    if not creation:
        bot.answer_callback_query(call.id, "❌ Criação não encontrada.", show_alert=True)
        return
    prompt = (creation.get("prompt") or "").strip()
    if not prompt:
        bot.answer_callback_query(call.id, "❌ Prompt indisponível.", show_alert=True)
        return

    creditos = get_user_credits(user_id)
    if not is_any_admin(user_id) and creditos < MODELO_PADRAO["custo"]:
        bot.answer_callback_query(call.id, f"❌ Precisa de {MODELO_PADRAO['custo']} créd. Tens {creditos}.", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🔁 A regenerar...")

    def _do_regen():
        if not is_any_admin(user_id) and not use_credit(user_id, MODELO_PADRAO["custo"]):
            return
        proc = bot.send_message(call.message.chat.id, "🔁 A regenerar imagem...")
        try:
            style_settings = get_user_style_settings(user_id)
            aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
            urls = gerar_imagem_modelo(prompt, aspect_ratio, num_outputs=1)
            try:
                bot.delete_message(call.message.chat.id, proc.message_id)
            except:
                pass
            for url in urls:
                img_data = requests.get(url, timeout=60).content
                cid = add_to_history(user_id, "create", prompt, url)
                creditos_restantes = get_user_credits(user_id)
                cap = {
                    "pt": f"🔁 Nova versão!\n💬 <i>{prompt[:120]}</i>\n💳 Restam: <code>{creditos_restantes}</code>",
                    "en": f"🔁 New version!\n💬 <i>{prompt[:120]}</i>\n💳 Left: <code>{creditos_restantes}</code>",
                    "es": f"🔁 Nueva versión!\n💬 <i>{prompt[:120]}</i>\n💳 Quedan: <code>{creditos_restantes}</code>"
                }
                bot.send_photo(call.message.chat.id, img_data, caption=cap.get(lang, cap["pt"]),
                               reply_markup=creation_actions_keyboard(cid, lang), parse_mode='HTML')
        except Exception as e:
            if not is_any_admin(user_id):
                add_credits(user_id, MODELO_PADRAO["custo"], "reembolso_regen")
            try:
                bot.edit_message_text(f"❌ Erro ao regenerar. Créditos reembolsados.", call.message.chat.id, proc.message_id)
            except:
                pass
            logger.error(f"Erro regen: {e}")

    Thread(target=_do_regen).start()


@bot.callback_query_handler(func=lambda call: call.data.startswith('refine_'))
def callback_refine(call):
    """Permite ao user escrever um ajuste para refinar a criacao."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    creation_id = call.data.replace('refine_', '')
    creation = get_creation_by_id(user_id, creation_id)
    if not creation:
        bot.answer_callback_query(call.id, "❌ Criação não encontrada.", show_alert=True)
        return

    refine_states[user_id] = {
        "creation_id": creation_id,
        "base_prompt": creation.get("prompt") or "",
        "ts": time.time()
    }
    user_states[user_id] = "awaiting_refine_text"
    bot.answer_callback_query(call.id)
    ask_texts = {
        "pt": ("✨ <b>Refinar criação</b>\n\n"
               "Escreve agora o que queres <b>ajustar</b> (ex: \"mais brilhante\", \"fundo branco\", "
               "\"em estilo cinematográfico\")."),
        "en": ("✨ <b>Refine creation</b>\n\nType what you want to adjust."),
        "es": ("✨ <b>Refinar creación</b>\n\nEscribe el ajuste que quieres.")
    }
    bot.send_message(call.message.chat.id, ask_texts.get(lang, ask_texts["pt"]),
                     reply_markup=cancel_keyboard(lang), parse_mode='HTML')


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_refine_text')
def handle_refine_text(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)
    state = refine_states.pop(user_id, None)
    if not state:
        return
    adjustment = (message.text or "").strip()
    if len(adjustment) < 2:
        bot.reply_to(message, "❌ Ajuste muito curto.")
        return
    base = state.get("base_prompt", "")
    new_prompt = f"{base}, {adjustment}" if base else adjustment

    creditos = get_user_credits(user_id)
    if not is_any_admin(user_id) and creditos < MODELO_PADRAO["custo"]:
        bot.reply_to(message, f"❌ Precisa de {MODELO_PADRAO['custo']} créditos. Tens {creditos}.")
        return
    if not is_any_admin(user_id) and not use_credit(user_id, MODELO_PADRAO["custo"]):
        bot.reply_to(message, "❌ Erro ao debitar créditos.")
        return

    proc = bot.reply_to(message, "✨ A refinar imagem...")
    try:
        style_settings = get_user_style_settings(user_id)
        aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
        urls = gerar_imagem_modelo(new_prompt, aspect_ratio, num_outputs=1)
        bot.delete_message(message.chat.id, proc.message_id)
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            cid = add_to_history(user_id, "create", new_prompt, url)
            creditos_restantes = get_user_credits(user_id)
            cap = f"✨ <b>Refinada!</b>\n💬 <i>{new_prompt[:140]}</i>\n💳 Restam: <code>{creditos_restantes}</code>"
            bot.send_photo(message.chat.id, img_data, caption=cap,
                           reply_markup=creation_actions_keyboard(cid, lang), parse_mode='HTML')
    except Exception as e:
        if not is_any_admin(user_id):
            add_credits(user_id, MODELO_PADRAO["custo"], "reembolso_refine")
        bot.edit_message_text(f"❌ Erro ao refinar. Créditos reembolsados.", message.chat.id, proc.message_id)
        logger.error(f"Erro refine: {e}")


# ==================== GALERIA PUBLICA (VIRAL LOOP) ====================
# Publica criacao anonima no canal publico + CTA para o bot
def _already_published_gallery(user_id, creation_id):
    data = load_json("gallery_published.json")
    key = f"{user_id}_{creation_id}"
    return key in data

def _mark_published_gallery(user_id, creation_id):
    data = load_json("gallery_published.json")
    key = f"{user_id}_{creation_id}"
    data[key] = {"ts": int(time.time())}
    save_json("gallery_published.json", data, Lock())


@bot.callback_query_handler(func=lambda call: call.data.startswith('gallery_'))
def callback_gallery(call):
    """Publica criacao no canal publico (galeria)"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    creation_id = call.data.replace('gallery_', '')

    # Gate de seguranca (admin bypassa)
    allowed, reason, extra = check_user_allowed(user_id, prompt=None, check_rate=False)
    if not allowed and reason != "shadowban":
        bot.answer_callback_query(call.id, "❌ Não permitido no momento.", show_alert=True)
        return

    if _already_published_gallery(user_id, creation_id):
        bot.answer_callback_query(call.id, "✅ Já publicado anteriormente.")
        return

    creation = get_creation_by_id(user_id, creation_id)
    if not creation:
        bot.answer_callback_query(call.id, "❌ Criação não encontrada.")
        return

    image_url = creation.get("image_url") or creation.get("url")
    prompt_text = (creation.get("prompt") or "")[:180]
    if not image_url:
        bot.answer_callback_query(call.id, "❌ Imagem indisponível.")
        return

    # Caption anonima + CTA
    cta_texts = {
        "pt": "Criado com @{u} — gera o teu: t.me/{u}",
        "en": "Created with @{u} — make yours: t.me/{u}",
        "es": "Creado con @{u} — haz el tuyo: t.me/{u}"
    }
    cta = cta_texts.get(lang, cta_texts["pt"]).format(u=BOT_USERNAME)
    caption = f"✨ <i>{prompt_text}</i>\n\n{cta}" if prompt_text else cta

    # Guarda o prompt completo (não truncado) para o botão "📋 Ver Prompt".
    # Se este creation foi feito com um estilo locked, o botão muda para "🔒 Prompt Premium"
    full_prompt = creation.get("prompt") or ""
    style_key_for_creation = get_style_for_creation(creation_id)
    is_locked_creation = bool(style_key_for_creation and is_style_locked(style_key_for_creation))
    prompt_id = save_gallery_prompt(full_prompt, style_key=style_key_for_creation) if full_prompt else None

    # Botões inline: "Criar o meu →" + ("📋 Ver Prompt" OU "🔒 Prompt Premium")
    ikm = telebot.types.InlineKeyboardMarkup(row_width=2)
    ikm.add(telebot.types.InlineKeyboardButton("🤖 Criar o meu →", url=f"https://t.me/{BOT_USERNAME}"))
    if prompt_id:
        if is_locked_creation:
            ikm.add(telebot.types.InlineKeyboardButton("🔒 Prompt Premium", callback_data=f"vp_{prompt_id}"))
        else:
            ikm.add(telebot.types.InlineKeyboardButton("📋 Ver Prompt", callback_data=f"vp_{prompt_id}"))

    try:
        # Descarrega imagem e envia para o canal
        img_bytes = requests.get(image_url, timeout=60).content
        sent_msg = bot.send_photo(GALLERY_CHANNEL, img_bytes, caption=caption,
                                  reply_markup=ikm, parse_mode='HTML')
        _mark_published_gallery(user_id, creation_id)

        # 🎨 Auto-coleta de preview de estilo (Opção 3): se este creation foi feito
        # com um estilo do Modelo Padrão, guarda o file_id do canal como preview oficial.
        try:
            style_key_for_preview = get_style_for_creation(creation_id)
            if style_key_for_preview and sent_msg and sent_msg.photo:
                # Pega no maior tamanho da foto enviada ao canal
                preview_file_id = sent_msg.photo[-1].file_id
                save_style_preview(style_key_for_preview, preview_file_id, sent_msg.message_id)
                logger.info(f"Preview do estilo {style_key_for_preview} atualizada via galeria (creation={creation_id})")
        except Exception as _e:
            logger.warning(f"Falha a auto-guardar preview de estilo: {_e}")

        # Contador de publicacoes do user + bonus a cada 10 (anti-prejuizo)
        pub_data = load_json("gallery_publish_count.json")
        uid = str(user_id)
        pub_data[uid] = int(pub_data.get(uid, 0)) + 1
        save_json("gallery_publish_count.json", pub_data, Lock())
        total_pubs = pub_data[uid]

        bonus_msg = ""
        if total_pubs % 10 == 0:
            add_credits(user_id, 2, "gallery_milestone_10")
            bonus_msg = " +2 créditos bónus 🎁"

        log_system_event("info", "gallery_publish", f"u={user_id} c={creation_id} n={total_pubs}", user_id)
        success_texts = {
            "pt": f"✅ Publicado na galeria! ({total_pubs} total){bonus_msg}",
            "en": f"✅ Published! ({total_pubs} total){bonus_msg}",
            "es": f"✅ ¡Publicado! ({total_pubs} total){bonus_msg}"
        }
        bot.answer_callback_query(call.id, success_texts.get(lang, success_texts["pt"]), show_alert=True)
    except Exception as e:
        err = str(e).lower()
        log_system_event("error", "gallery_publish_fail", str(e), user_id)
        if "chat not found" in err or "bot is not a member" in err:
            bot.answer_callback_query(call.id, "⚠️ Canal não configurado. Avisa o admin.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ Erro: {str(e)[:80]}", show_alert=True)



@bot.callback_query_handler(func=lambda call: call.data.startswith('vp_'))
def callback_view_prompt(call):
    """Handler do botão '📋 Ver Prompt' / '🔒 Prompt Premium' do canal da galeria."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id) or "pt"
    pid = call.data.replace('vp_', '')
    entry = get_gallery_prompt_entry(pid)

    if not entry:
        bot.answer_callback_query(call.id, "❌ Prompt não encontrado ou expirou.", show_alert=True)
        return

    full_prompt = entry.get("prompt") or ""
    is_locked_prompt = bool(entry.get("locked"))

    # Se for de estilo PREMIUM (locked) → mostra CTA com waitlist do eBook
    if is_locked_prompt:
        msg_l = {
            "pt": ("🔒 <b>Prompt Premium</b>\n\n"
                   "Este prompt faz parte da coleção exclusiva do <b>Modelo Padrão Premium</b>.\n\n"
                   "🎨 <b>Para usares este estilo no bot:</b>\n"
                   f"Faz qualquer compra de créditos em @{BOT_USERNAME} e desbloqueias <b>todos os 37+ estilos premium</b>, incluindo a categoria 🔥 Sensual.\n\n"
                   "📖 <b>Para teres o prompt completo:</b>\n"
                   "Estamos a preparar o eBook <b>Remake Pixel Prompt Vault</b> 📚 — uma compilação dos prompts dos estilos premium para usares onde quiseres (Midjourney, ChatGPT, FLUX, etc.).\n\n"
                   "👇 Clica em <b>🔔 Avisar-me</b> para entrares na lista de espera (vais receber notificação grátis quando o eBook lançar)."),
            "en": ("🔒 <b>Premium Prompt</b>\n\n"
                   "This prompt is part of the exclusive <b>Standard Model Premium</b> collection.\n\n"
                   "🎨 <b>To use this style in the bot:</b>\n"
                   f"Make any credit purchase at @{BOT_USERNAME} and unlock <b>all 37+ premium styles</b>, including 🔥 Sensual.\n\n"
                   "📖 <b>To get the full prompt:</b>\n"
                   "We're preparing the eBook <b>Remake Pixel Prompt Vault</b> 📚 — a compilation of premium-style prompts to use anywhere (Midjourney, ChatGPT, FLUX, etc.).\n\n"
                   "👇 Tap <b>🔔 Notify me</b> to join the waitlist (free notification when it launches)."),
            "es": ("🔒 <b>Prompt Premium</b>\n\n"
                   "Este prompt es parte de la colección <b>Modelo Estándar Premium</b>.\n\n"
                   "🎨 <b>Para usar este estilo en el bot:</b>\n"
                   f"Haz cualquier compra de créditos en @{BOT_USERNAME} y desbloquea <b>todos los estilos premium</b>.\n\n"
                   "📖 <b>Para tener el prompt completo:</b>\n"
                   "Estamos preparando el eBook <b>Remake Pixel Prompt Vault</b> 📚.\n\n"
                   "👇 Toca <b>🔔 Avisarme</b> para entrar en la lista de espera."),
        }
        notify_label = {"pt": "🔔 Avisar-me quando lançar", "en": "🔔 Notify me at launch", "es": "🔔 Avisarme al lanzar"}
        bot_label = {"pt": "🤖 Abrir o bot", "en": "🤖 Open the bot", "es": "🤖 Abrir el bot"}
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        mk.add(telebot.types.InlineKeyboardButton(notify_label.get(lang, notify_label["pt"]), callback_data="ebook_join"))
        mk.add(telebot.types.InlineKeyboardButton(bot_label.get(lang, bot_label["pt"]), url=f"https://t.me/{BOT_USERNAME}"))
        try:
            bot.send_message(user_id, msg_l.get(lang, msg_l["pt"]), reply_markup=mk, parse_mode='HTML')
            bot.answer_callback_query(call.id, "📩 Detalhes enviados em DM!")
        except Exception:
            try:
                bot.answer_callback_query(
                    call.id,
                    f"⚠️ Inicia primeiro o bot @{BOT_USERNAME} e clica novamente.",
                    show_alert=True
                )
            except Exception:
                pass
        return

    # Estilo desbloqueado / sem estilo → revela prompt completo (comportamento original)
    if not full_prompt:
        bot.answer_callback_query(call.id, "❌ Prompt vazio.", show_alert=True)
        return

    header = "📋 <b>Prompt completo desta imagem</b>\n\n<i>Copia e cola para reutilizar no @" + BOT_USERNAME + "</i>\n\n"
    body = full_prompt
    msg = header + "<code>" + (body.replace("<", "&lt;").replace(">", "&gt;")[:3500]) + "</code>"

    try:
        bot.send_message(user_id, msg, parse_mode='HTML')
        bot.answer_callback_query(call.id, "📩 Prompt enviado em DM!")
    except Exception:
        try:
            bot.answer_callback_query(
                call.id,
                f"⚠️ Inicia primeiro o bot @{BOT_USERNAME} e clica novamente.",
                show_alert=True
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data == 'ebook_join')
def callback_ebook_join(call):
    """Adiciona user à waitlist do eBook 'Remake Pixel Prompt Vault'."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id) or "pt"
    is_new = add_to_ebook_waitlist(user_id, lang)
    msg = {
        "pt": ("✅ Estás na lista de espera do <b>Remake Pixel Prompt Vault</b>! 📚\n\n"
               "🔔 Vais receber uma notificação assim que o eBook estiver disponível.\n"
               "🎁 Os primeiros da lista terão desconto de lançamento.") if is_new else
              "✅ Já estavas na lista! Vais ser notificado no lançamento. 🔔",
        "en": ("✅ You're on the <b>Remake Pixel Prompt Vault</b> waitlist! 📚\n\n"
               "🔔 You'll get a free notification when the eBook is ready.\n"
               "🎁 First on the list = launch discount.") if is_new else
              "✅ Already on the list! You'll be notified. 🔔",
        "es": ("✅ Estás en la lista de espera del <b>Remake Pixel Prompt Vault</b>! 📚\n"
               "🔔 Te avisaremos al lanzar.") if is_new else
              "✅ Ya estabas en la lista. Te avisaremos. 🔔",
    }
    try:
        bot.answer_callback_query(call.id, "🔔 Adicionado à lista!" if is_new else "✅ Já estavas registado.", show_alert=False)
        bot.send_message(user_id, msg.get(lang, msg["pt"]), parse_mode='HTML')
    except Exception:
        pass



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
    """Teclado do painel administrativo - organizado por seccoes"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    is_super = is_super_admin(user_id) if user_id else True

    if is_super:
        # Super admin - acesso total, organizado por seccoes
        markup.add(
            telebot.types.InlineKeyboardButton("👥 Utilizadores", callback_data="admin_sec_users"),
            telebot.types.InlineKeyboardButton("💰 Finanças", callback_data="admin_sec_finance")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("🛡️ Segurança", callback_data="admin_sec_security"),
            telebot.types.InlineKeyboardButton("📊 Analytics", callback_data="admin_sec_analytics")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("🚨 Reports", callback_data="admin_sec_reports"),
            telebot.types.InlineKeyboardButton("🧾 Logs", callback_data="admin_sec_logs")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("⚙️ Sistema", callback_data="admin_sec_system"),
            telebot.types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("🛒 Aprovar Compras", callback_data="admin_pending"),
            telebot.types.InlineKeyboardButton("👑 Gerir Admins", callback_data="admin_manage_admins")
        )
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

# ==================== KEYBOARDS DE SECCOES DO PAINEL (NOVOS) ====================
def admin_section_users_kb():
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("🔍 Procurar User", callback_data="admin_user_search"),
        telebot.types.InlineKeyboardButton("📋 Listar Users", callback_data="admin_list_users")
    )
    m.add(
        telebot.types.InlineKeyboardButton("💳 Dar Créditos", callback_data="admin_give_credits"),
        telebot.types.InlineKeyboardButton("💎 Lista VIPs", callback_data="admin_list_vips")
    )
    m.add(
        telebot.types.InlineKeyboardButton("🚫 Lista Banidos", callback_data="admin_list_banned"),
        telebot.types.InlineKeyboardButton("👻 Shadowbans", callback_data="admin_list_shadow")
    )
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
    return m

def admin_section_security_kb():
    cfg = get_system_config()
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    nsfw_txt = "🔞 NSFW: ✅ ON (permitido)" if cfg.get("nsfw_enabled") else "🔞 NSFW: ❌ OFF (bloqueado)"
    safe_txt = "🛡️ Safe Mode: ✅ ON" if cfg.get("safe_mode") else "🛡️ Safe Mode: ❌ OFF"
    gen_txt = "⛔ Geração: DESLIGADA" if cfg.get("generation_disabled") else "✅ Geração: LIGADA"
    maint_txt = "🛠️ Manutenção: ON" if cfg.get("maintenance_mode") else "🛠️ Manutenção: OFF"
    m.add(telebot.types.InlineKeyboardButton(nsfw_txt, callback_data="admin_toggle_nsfw"))
    m.add(telebot.types.InlineKeyboardButton(safe_txt, callback_data="admin_toggle_safe"))
    m.add(telebot.types.InlineKeyboardButton(gen_txt, callback_data="admin_toggle_gen"))
    m.add(telebot.types.InlineKeyboardButton(maint_txt, callback_data="admin_toggle_maint"))
    m.add(telebot.types.InlineKeyboardButton("🔑 Editar NSFW keywords", callback_data="admin_nsfw_kw"))
    m.add(telebot.types.InlineKeyboardButton(f"⚡ Rate-limit: {cfg.get('rate_limit_per_min',10)}/min", callback_data="admin_ratelimit"))
    m.add(telebot.types.InlineKeyboardButton("🚨 EMERGÊNCIA - Desligar tudo", callback_data="admin_emergency_confirm"))
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
    return m

def admin_section_system_kb():
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📈 Status Bot", callback_data="admin_bot_status"),
        telebot.types.InlineKeyboardButton("🔄 Soft Restart", callback_data="admin_soft_restart")
    )
    m.add(
        telebot.types.InlineKeyboardButton("🧹 Clear Cache", callback_data="admin_clear_cache"),
        telebot.types.InlineKeyboardButton("📥 Reload Config", callback_data="admin_reload_cfg")
    )
    m.add(
        telebot.types.InlineKeyboardButton("🎯 Broadcast Segmentado", callback_data="admin_broadcast_seg"),
        telebot.types.InlineKeyboardButton("🌐 Ngrok URL", callback_data="admin_ngrok")
    )
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
    return m

def admin_section_analytics_kb():
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(telebot.types.InlineKeyboardButton("📊 Estatísticas Gerais", callback_data="admin_stats"))
    m.add(telebot.types.InlineKeyboardButton("🔥 Uso diário/semanal", callback_data="admin_usage_period"))
    m.add(telebot.types.InlineKeyboardButton("💎 Top Spenders", callback_data="admin_top_spenders"))
    m.add(telebot.types.InlineKeyboardButton("🔁 Retenção (7d)", callback_data="admin_retention"))
    m.add(telebot.types.InlineKeyboardButton("🤖 Features mais usadas", callback_data="admin_top_features"))
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
    return m

def admin_section_logs_kb(page=0):
    logs = load_json(SYSTEM_LOGS_FILE).get("logs", [])
    per_page = 10
    total = len(logs)
    start = page * per_page
    end = min(start + per_page, total)
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    nav = []
    if page > 0:
        nav.append(telebot.types.InlineKeyboardButton("◀️ Anterior", callback_data=f"admin_logs_page_{page-1}"))
    if end < total:
        nav.append(telebot.types.InlineKeyboardButton("Próxima ▶️", callback_data=f"admin_logs_page_{page+1}"))
    if nav:
        m.row(*nav)
    m.add(
        telebot.types.InlineKeyboardButton("🧹 Limpar logs", callback_data="admin_logs_clear"),
        telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel")
    )
    return m

def admin_section_reports_kb():
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    reports = get_pending_reports(limit=20)
    if not reports:
        m.add(telebot.types.InlineKeyboardButton("(Sem reports pendentes)", callback_data="admin_noop"))
    else:
        for r in reports[:10]:
            label = f"🚨 {r['reported_user_id']} — {r['reason'][:40]}"
            m.add(telebot.types.InlineKeyboardButton(label, callback_data=f"admin_report_view_{r['id']}"))
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_panel"))
    return m

def user_profile_kb(target_id):
    flags = get_user_flags(target_id)
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    ban_txt = "✅ Desbanir" if flags.get("banned") else "🚫 Banir"
    shadow_txt = "✅ Tirar Shadowban" if flags.get("shadowbanned") else "👻 Shadowban"
    nsfw_txt = "🔞 NSFW: ON" if flags.get("nsfw_allowed") else "🔞 NSFW: OFF"
    vip_txt = "💎 Remover VIP" if has_tag(target_id, "VIP") else "💎 Tornar VIP"
    m.add(
        telebot.types.InlineKeyboardButton(ban_txt, callback_data=f"admin_u_ban_{target_id}"),
        telebot.types.InlineKeyboardButton(shadow_txt, callback_data=f"admin_u_shadow_{target_id}")
    )
    m.add(
        telebot.types.InlineKeyboardButton(vip_txt, callback_data=f"admin_u_vip_{target_id}"),
        telebot.types.InlineKeyboardButton(nsfw_txt, callback_data=f"admin_u_nsfw_{target_id}")
    )
    m.add(
        telebot.types.InlineKeyboardButton("💳 +Créditos", callback_data=f"admin_select_user_{target_id}"),
        telebot.types.InlineKeyboardButton("➖ -Créditos", callback_data=f"admin_u_rm_{target_id}")
    )
    m.add(
        telebot.types.InlineKeyboardButton("🏷️ Tag Spammer", callback_data=f"admin_u_tag_{target_id}_spammer"),
        telebot.types.InlineKeyboardButton("🏷️ Tag Suspeito", callback_data=f"admin_u_tag_{target_id}_suspicious")
    )
    m.add(telebot.types.InlineKeyboardButton("🧹 Reset Data", callback_data=f"admin_u_reset_{target_id}"))
    m.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_users"))
    return m

def render_user_profile(target_id):
    """Devolve texto HTML com perfil completo do user."""
    credits_data = load_json(CREDITS_FILE)
    user_credits = credits_data.get(str(target_id), {}).get("creditos", 0)
    flags = get_user_flags(target_id)
    stats = load_json(STATISTICS_FILE).get(str(target_id), {})
    tags = flags.get("tags", [])
    tags_str = ", ".join(tags) if tags else "—"
    last_act = flags.get("last_activity", 0)
    last_str = datetime.fromtimestamp(last_act).strftime("%Y-%m-%d %H:%M") if last_act else "nunca"
    try:
        info = bot.get_chat(int(target_id))
        uname = f"@{info.username}" if getattr(info, "username", None) else info.first_name
    except:
        uname = "—"

    status_icons = []
    if flags.get("banned"): status_icons.append("🚫BANIDO")
    if flags.get("shadowbanned"): status_icons.append("👻SHADOW")
    if flags.get("nsfw_allowed"): status_icons.append("🔞NSFW-OK")
    if has_tag(target_id, "VIP"): status_icons.append("💎VIP")
    status_str = " | ".join(status_icons) if status_icons else "✅ OK"

    msg = (
        f"👤 <b>Perfil — {uname}</b>\n"
        f"🆔 <code>{target_id}</code>\n"
        f"💳 Créditos: <b>{user_credits}</b>\n"
        f"📊 Total edits: {stats.get('total_edits',0)} | criações: {stats.get('total_creations',0)}\n"
        f"🏷️ Tags: {tags_str}\n"
        f"🚨 Reports recebidos: {flags.get('reports_count',0)}\n"
        f"⏰ Última atividade: {last_str}\n"
        f"📌 Status: {status_str}"
    )
    return msg



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
        msg += "Ou use: <code>/addadmin ID_DO_USUARIO</code>\n\n"
        msg += "🔒 <b>Trancar/Destrancar Premium:</b> controla se cada admin secundário tem acesso aos estilos sensuais e premium do Modelo Padrão. Tu (super admin) tens sempre acesso total."
        
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            telebot.types.InlineKeyboardButton("➕ Adicionar Admin (por ID)", callback_data="admin_add_secondary"),
        )
        if secondary:
            for uid in secondary:
                info = secondary[uid]
                # Estado do acesso premium do admin secundário
                is_blocked = is_secondary_admin_blocked(uid)
                lock_emoji = "🔒" if is_blocked else "🔓"
                lock_action = "unlock" if is_blocked else "lock"
                lock_label = f"{lock_emoji} {'Destrancar' if is_blocked else 'Trancar'} Premium {info.get('name', uid)}"
                markup.add(
                    telebot.types.InlineKeyboardButton(f"🗑️ Remover {info.get('name', uid)}", callback_data=f"admin_remove_{uid}"),
                )
                markup.add(
                    telebot.types.InlineKeyboardButton(lock_label, callback_data=f"admin_premlock_{lock_action}_{uid}")
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
    
    elif action.startswith("premlock_"):
        # Super admin tranca/destranca premium de admin secundário
        if not is_super_admin(user_id):
            bot.answer_callback_query(call.id, "Apenas o admin principal!")
            return
        parts = action.replace("premlock_", "").split("_", 1)
        if len(parts) != 2:
            return
        sub_action, target_uid = parts
        try:
            target_id = int(target_uid)
        except Exception:
            return
        block = (sub_action == "lock")
        admin_toggle_secondary_premium_block(target_id, block)
        bot.answer_callback_query(
            call.id,
            f"{'🔒 Trancado' if block else '🔓 Destrancado'}: admin {target_id}",
            show_alert=False
        )
        # Re-render painel chamando manage_admins
        try:
            new_call = call
            new_call.data = "admin_manage_admins"
            callback_admin_panel(new_call)
        except Exception:
            pass

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

    # ==================== NOVOS HANDLERS — SECCOES ====================
    elif action == "sec_users":
        msg = "👥 <b>UTILIZADORES</b>\n\nEscolhe uma ação:"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_users_kb(), parse_mode='HTML')

    elif action == "sec_security":
        cfg = get_system_config()
        msg = "🛡️ <b>SEGURANÇA</b>\n\n"
        msg += f"🔞 NSFW: <b>{'LIGADO' if cfg.get('nsfw_enabled') else 'BLOQUEADO'}</b>\n"
        msg += f"🛡️ Safe Mode: <b>{'ON' if cfg.get('safe_mode') else 'OFF'}</b>\n"
        msg += f"⛔ Geração: <b>{'DESLIGADA' if cfg.get('generation_disabled') else 'LIGADA'}</b>\n"
        msg += f"🛠️ Manutenção: <b>{'ON' if cfg.get('maintenance_mode') else 'OFF'}</b>\n"
        msg += f"⚡ Rate limit: <b>{cfg.get('rate_limit_per_min',10)}/min</b>\n"
        msg += f"🔑 NSFW keywords: <b>{len(cfg.get('nsfw_keywords',[]))}</b>\n\n"
        msg += "<i>Admin IGNORA todas as restrições.</i>"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_security_kb(), parse_mode='HTML')

    elif action == "sec_system":
        msg = "⚙️ <b>SISTEMA</b>\n\nControle avançado:"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_system_kb(), parse_mode='HTML')

    elif action == "sec_analytics":
        msg = "📊 <b>ANALYTICS</b>\n\nEscolhe uma métrica:"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_analytics_kb(), parse_mode='HTML')

    elif action == "sec_logs":
        logs = load_json(SYSTEM_LOGS_FILE).get("logs", [])
        page = 0
        per_page = 10
        page_logs = logs[page*per_page:(page+1)*per_page]
        if not page_logs:
            body = "<i>(Sem logs ainda)</i>"
        else:
            lines = []
            for l in page_logs:
                ts = datetime.fromtimestamp(l.get("ts", 0)).strftime("%m-%d %H:%M")
                uid_s = f" u={l['user_id']}" if l.get("user_id") else ""
                lines.append(f"[{ts}] {l.get('level','?').upper()} {l.get('category','?')}{uid_s}: {l.get('message','')[:120]}")
            body = "\n".join(lines)
        msg = f"🧾 <b>LOGS DO SISTEMA</b> (últimos {len(page_logs)}/{len(logs)})\n\n<pre>{body}</pre>"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_logs_kb(page), parse_mode='HTML')

    elif action.startswith("logs_page_"):
        page = int(action.replace("logs_page_", ""))
        logs = load_json(SYSTEM_LOGS_FILE).get("logs", [])
        per_page = 10
        page_logs = logs[page*per_page:(page+1)*per_page]
        if not page_logs:
            body = "<i>(sem mais logs)</i>"
        else:
            lines = []
            for l in page_logs:
                ts = datetime.fromtimestamp(l.get("ts", 0)).strftime("%m-%d %H:%M")
                uid_s = f" u={l['user_id']}" if l.get("user_id") else ""
                lines.append(f"[{ts}] {l.get('level','?').upper()} {l.get('category','?')}{uid_s}: {l.get('message','')[:120]}")
            body = "\n".join(lines)
        msg = f"🧾 <b>LOGS</b> (pag {page+1})\n\n<pre>{body}</pre>"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_logs_kb(page), parse_mode='HTML')

    elif action == "logs_clear":
        save_json(SYSTEM_LOGS_FILE, {"logs": []}, SYSLOGS_LOCK)
        bot.answer_callback_query(call.id, "Logs limpos!")
        bot.edit_message_text("🧹 Logs limpos.\n\n<i>(Sem logs ainda)</i>", call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_logs_kb(0), parse_mode='HTML')

    elif action == "sec_reports":
        pending = get_pending_reports(20)
        msg = f"🚨 <b>REPORTS PENDENTES ({len(pending)})</b>\n\nClica para ver detalhes:"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_reports_kb(), parse_mode='HTML')

    elif action.startswith("report_view_"):
        rid = action.replace("report_view_", "")
        data = load_json(REPORTS_FILE)
        r = next((x for x in data.get("reports", []) if x.get("id") == rid), None)
        if not r:
            bot.answer_callback_query(call.id, "Report não encontrado.")
            return
        ts = datetime.fromtimestamp(r.get("ts", 0)).strftime("%Y-%m-%d %H:%M")
        msg = (f"🚨 <b>Report {rid}</b>\n\n"
               f"Reporter: <code>{r['reporter_id']}</code>\n"
               f"Reportado: <code>{r['reported_user_id']}</code>\n"
               f"Razão: {r['reason']}\n"
               f"Data: {ts}\n"
               f"Status: {r['status']}")
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            telebot.types.InlineKeyboardButton("🚫 Banir", callback_data=f"admin_r_ban_{rid}"),
            telebot.types.InlineKeyboardButton("👻 Shadow", callback_data=f"admin_r_shadow_{rid}")
        )
        mk.add(
            telebot.types.InlineKeyboardButton("✅ Marcar safe", callback_data=f"admin_r_safe_{rid}"),
            telebot.types.InlineKeyboardButton("🙈 Ignorar", callback_data=f"admin_r_ignore_{rid}")
        )
        mk.add(telebot.types.InlineKeyboardButton("👤 Ver perfil", callback_data=f"admin_u_view_{r['reported_user_id']}"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_reports"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action.startswith("r_"):
        # Ações sobre reports: r_ban_<id>, r_shadow_<id>, r_safe_<id>, r_ignore_<id>
        parts = action.split("_")
        sub = parts[1]
        rid = "_".join(parts[2:])
        data = load_json(REPORTS_FILE)
        r = next((x for x in data.get("reports", []) if x.get("id") == rid), None)
        if not r:
            bot.answer_callback_query(call.id, "Report não encontrado.")
            return
        target = int(r["reported_user_id"])
        if sub == "ban":
            set_user_flag(target, "banned", True)
            update_report_status(rid, "banned")
            log_system_event("ban", "report_action", f"User {target} banned via report {rid}", target)
            bot.answer_callback_query(call.id, f"✅ User {target} banido.")
        elif sub == "shadow":
            set_user_flag(target, "shadowbanned", True)
            update_report_status(rid, "banned")
            log_system_event("ban", "report_action", f"User {target} shadowbanned via report {rid}", target)
            bot.answer_callback_query(call.id, f"✅ User {target} shadowbanned.")
        elif sub == "safe":
            update_report_status(rid, "safe")
            bot.answer_callback_query(call.id, "Marcado como safe.")
        elif sub == "ignore":
            update_report_status(rid, "ignored")
            bot.answer_callback_query(call.id, "Ignorado.")
        bot.edit_message_text("✅ Ação aplicada.", call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_reports_kb(), parse_mode='HTML')

    # ==================== TOGGLES DE SEGURANCA ====================
    elif action in ("toggle_nsfw", "toggle_safe", "toggle_gen", "toggle_maint"):
        cfg = get_system_config()
        key_map = {
            "toggle_nsfw": ("nsfw_enabled", "NSFW"),
            "toggle_safe": ("safe_mode", "Safe Mode"),
            "toggle_gen": ("generation_disabled", "Geração"),
            "toggle_maint": ("maintenance_mode", "Manutenção"),
        }
        cfg_key, label = key_map[action]
        new_val = not cfg.get(cfg_key, False)
        set_system_config(cfg_key, new_val)
        log_system_event("info" if cfg_key != "generation_disabled" else "warn",
                         "cfg_change", f"{cfg_key}={new_val}", user_id)
        # Mostrar bar invertida para generation_disabled (desligada = ruim)
        state_str = "ON" if new_val else "OFF"
        if cfg_key == "generation_disabled":
            state_str = "DESLIGADA" if new_val else "LIGADA"
        bot.answer_callback_query(call.id, f"{label}: {state_str}")
        # Re-renderiza seccao
        cfg = get_system_config()
        msg = "🛡️ <b>SEGURANÇA</b>\n\n"
        msg += f"🔞 NSFW: <b>{'LIGADO' if cfg.get('nsfw_enabled') else 'BLOQUEADO'}</b>\n"
        msg += f"🛡️ Safe Mode: <b>{'ON' if cfg.get('safe_mode') else 'OFF'}</b>\n"
        msg += f"⛔ Geração: <b>{'DESLIGADA' if cfg.get('generation_disabled') else 'LIGADA'}</b>\n"
        msg += f"🛠️ Manutenção: <b>{'ON' if cfg.get('maintenance_mode') else 'OFF'}</b>\n"
        msg += f"⚡ Rate limit: <b>{cfg.get('rate_limit_per_min',10)}/min</b>\n"
        msg += f"🔑 NSFW keywords: <b>{len(cfg.get('nsfw_keywords',[]))}</b>\n\n"
        msg += "<i>Admin IGNORA todas as restrições.</i>"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_security_kb(), parse_mode='HTML')

    elif action == "emergency_confirm":
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🚨 SIM, desligar TUDO", callback_data="admin_emergency_go"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Não, cancelar", callback_data="admin_sec_security"))
        bot.edit_message_text(
            "🚨 <b>CONFIRMAÇÃO EMERGÊNCIA</b>\n\nVai:\n• Desligar geração globalmente\n• Ligar modo manutenção\n• Ligar safe mode\n\n<i>Admin continua a ter acesso total.</i>",
            call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "emergency_go":
        set_system_config("generation_disabled", True)
        set_system_config("maintenance_mode", True)
        set_system_config("safe_mode", True)
        log_system_event("error", "emergency", "EMERGENCY activated — all generation disabled", user_id)
        bot.answer_callback_query(call.id, "🚨 Emergência ativada!")
        bot.edit_message_text("🚨 <b>MODO EMERGÊNCIA ATIVADO</b>\n\n✅ Geração desligada\n✅ Manutenção on\n✅ Safe mode on",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_security_kb(), parse_mode='HTML')

    elif action == "nsfw_kw":
        cfg = get_system_config()
        kws = cfg.get("nsfw_keywords", [])
        msg = f"🔑 <b>NSFW keywords ({len(kws)})</b>\n\n"
        msg += ", ".join(kws[:60])
        msg += "\n\n<i>Envia a nova lista (palavras separadas por vírgula) para substituir. Ou /cancel.</i>"
        admin_states[user_id] = "awaiting_nsfw_kw"
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_security"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "ratelimit":
        admin_states[user_id] = "awaiting_ratelimit"
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_security"))
        bot.edit_message_text("⚡ <b>Rate Limit</b>\n\nEnvia o novo valor (pedidos/min, ex: 10):",
                              call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    # ==================== SYSTEM ACTIONS ====================
    elif action == "soft_restart":
        global _rate_buckets
        _rate_buckets = {}
        user_states.clear()
        log_system_event("info", "system", "Soft restart — caches limpos", user_id)
        bot.answer_callback_query(call.id, "🔄 Restart suave feito!", show_alert=True)
        bot.edit_message_text("⚙️ <b>SISTEMA</b>\n\nControle avançado:\n\n✅ Restart suave aplicado.",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=admin_section_system_kb(), parse_mode='HTML')

    elif action == "clear_cache":
        pending_photos.clear()
        photo_collections.clear()
        _rate_buckets.clear()
        log_system_event("info", "system", "Cache limpo", user_id)
        bot.answer_callback_query(call.id, "🧹 Cache limpo.", show_alert=True)

    elif action == "reload_cfg":
        load_secondary_admins()
        get_system_config()
        log_system_event("info", "system", "Configs recarregadas", user_id)
        bot.answer_callback_query(call.id, "📥 Configs recarregadas.", show_alert=True)

    elif action == "broadcast_seg":
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        mk.add(telebot.types.InlineKeyboardButton("📢 Todos (bd completa)", callback_data="admin_bseg_all"))
        mk.add(telebot.types.InlineKeyboardButton("🔥 Ativos (últimos 7d)", callback_data="admin_bseg_active"))
        mk.add(telebot.types.InlineKeyboardButton("💎 Só VIPs", callback_data="admin_bseg_vip"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_system"))
        bot.edit_message_text("🎯 <b>Broadcast Segmentado</b>\n\nEscolhe o público:",
                              call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action.startswith("bseg_"):
        segment = action.replace("bseg_", "")  # all, active, vip
        admin_states[user_id] = f"awaiting_broadcast_{segment}"
        bot.edit_message_text(f"📢 <b>Broadcast → {segment.upper()}</b>\n\nEscreve a mensagem:",
                              call.message.chat.id, call.message.message_id, parse_mode='HTML')

    # ==================== USER MANAGEMENT ====================
    elif action == "user_search":
        admin_states[user_id] = "awaiting_user_search"
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_users"))
        bot.edit_message_text("🔍 <b>Procurar User</b>\n\nEnvia o ID ou @username:",
                              call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action.startswith("u_view_"):
        target = int(action.replace("u_view_", ""))
        try:
            bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                                  reply_markup=user_profile_kb(target), parse_mode='HTML')
        except Exception as e:
            bot.send_message(call.message.chat.id, f"Erro: {e}")

    elif action.startswith("u_ban_"):
        target = int(action.replace("u_ban_", ""))
        flags = get_user_flags(target)
        new_val = not flags.get("banned", False)
        set_user_flag(target, "banned", new_val)
        log_system_event("ban", "user_action", f"User {target} banned={new_val}", target)
        bot.answer_callback_query(call.id, f"{'🚫 Banido' if new_val else '✅ Desbanido'}")
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action.startswith("u_shadow_"):
        target = int(action.replace("u_shadow_", ""))
        flags = get_user_flags(target)
        new_val = not flags.get("shadowbanned", False)
        set_user_flag(target, "shadowbanned", new_val)
        log_system_event("ban", "user_action", f"User {target} shadow={new_val}", target)
        bot.answer_callback_query(call.id, f"{'👻 Shadow on' if new_val else '✅ Shadow off'}")
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action.startswith("u_vip_"):
        target = int(action.replace("u_vip_", ""))
        if has_tag(target, "VIP"):
            remove_user_tag(target, "VIP")
            bot.answer_callback_query(call.id, "VIP removido.")
        else:
            add_user_tag(target, "VIP")
            # VIPs ganham +10 créditos grátis como bónus
            add_credits(target, 10, "vip_bonus")
            try:
                bot.send_message(target, "💎 <b>Foste promovido a VIP!</b>\n\n+10 créditos de bónus. Obrigado por apoiares o Remake_Pixel!", parse_mode='HTML')
            except:
                pass
            bot.answer_callback_query(call.id, "💎 Agora é VIP (+10 créd).")
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action.startswith("u_nsfw_"):
        target = int(action.replace("u_nsfw_", ""))
        flags = get_user_flags(target)
        new_val = not flags.get("nsfw_allowed", False)
        set_user_flag(target, "nsfw_allowed", new_val)
        log_system_event("info", "user_action", f"User {target} nsfw_allowed={new_val}", target)
        bot.answer_callback_query(call.id, f"NSFW {'ON' if new_val else 'OFF'}")
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action.startswith("u_rm_"):
        target = int(action.replace("u_rm_", ""))
        admin_states[user_id] = f"awaiting_rm_credits_{target}"
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data=f"admin_u_view_{target}"))
        bot.edit_message_text(f"➖ <b>Remover créditos</b>\n\nUser: <code>{target}</code>\n\nQuantos remover? (envia número)",
                              call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action.startswith("u_tag_"):
        # admin_u_tag_<uid>_<tag>
        rest = action.replace("u_tag_", "")
        parts = rest.rsplit("_", 1)
        target = int(parts[0])
        tag = parts[1]
        if has_tag(target, tag):
            remove_user_tag(target, tag)
            bot.answer_callback_query(call.id, f"Tag '{tag}' removida.")
        else:
            add_user_tag(target, tag)
            bot.answer_callback_query(call.id, f"Tag '{tag}' adicionada.")
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action.startswith("u_reset_"):
        target = int(action.replace("u_reset_", ""))
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🚨 Sim, reset", callback_data=f"admin_u_resetgo_{target}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Não", callback_data=f"admin_u_view_{target}"))
        bot.edit_message_text(f"⚠️ <b>Reset User {target}</b>\n\nVai apagar créditos, flags, tags e histórico.\nContinuar?",
                              call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action.startswith("u_resetgo_"):
        target = int(action.replace("u_resetgo_", ""))
        # Reset flags
        data = load_json(USER_FLAGS_FILE)
        data.pop(str(target), None)
        save_json(USER_FLAGS_FILE, data, FLAGS_LOCK)
        # Reset credits to 0
        c = load_json(CREDITS_FILE)
        if str(target) in c:
            c[str(target)]["creditos"] = 0
            save_json(CREDITS_FILE, c, CREDITS_LOCK)
        # Reset stats & history
        s = load_json(STATISTICS_FILE)
        s.pop(str(target), None)
        save_json(STATISTICS_FILE, s, STATS_LOCK)
        h = load_json(HISTORY_FILE)
        h.pop(str(target), None)
        save_json(HISTORY_FILE, h, HISTORY_LOCK)
        log_system_event("warn", "user_reset", f"User {target} reset by admin {user_id}", target)
        bot.answer_callback_query(call.id, "🧹 User resetado.", show_alert=True)
        bot.edit_message_text(render_user_profile(target), call.message.chat.id, call.message.message_id,
                              reply_markup=user_profile_kb(target), parse_mode='HTML')

    elif action == "list_banned":
        flags_data = load_json(USER_FLAGS_FILE)
        banned = [(uid, f) for uid, f in flags_data.items() if f.get("banned")]
        msg = f"🚫 <b>BANIDOS ({len(banned)})</b>\n\n"
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        if not banned:
            msg += "<i>(ninguém banido)</i>"
        for uid, _ in banned[:20]:
            mk.add(telebot.types.InlineKeyboardButton(f"👤 {uid}", callback_data=f"admin_u_view_{uid}"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_users"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "list_shadow":
        flags_data = load_json(USER_FLAGS_FILE)
        shadowed = [(uid, f) for uid, f in flags_data.items() if f.get("shadowbanned")]
        msg = f"👻 <b>SHADOWBANNED ({len(shadowed)})</b>\n\n"
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        if not shadowed:
            msg += "<i>(ninguém shadowed)</i>"
        for uid, _ in shadowed[:20]:
            mk.add(telebot.types.InlineKeyboardButton(f"👤 {uid}", callback_data=f"admin_u_view_{uid}"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_users"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "list_vips":
        flags_data = load_json(USER_FLAGS_FILE)
        vips = [(uid, f) for uid, f in flags_data.items() if "VIP" in f.get("tags", [])]
        msg = f"💎 <b>VIPs ({len(vips)})</b>\n\n"
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        if not vips:
            msg += "<i>(sem VIPs)</i>"
        for uid, _ in vips[:20]:
            mk.add(telebot.types.InlineKeyboardButton(f"💎 {uid}", callback_data=f"admin_u_view_{uid}"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_users"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    # ==================== ANALYTICS ====================
    elif action == "top_spenders":
        stats_data = load_json(STATISTICS_FILE)
        pairs = []
        for uid, s in stats_data.items():
            total = int(s.get("total_creations", 0)) + int(s.get("total_edits", 0))
            pairs.append((uid, total, s.get("total_spent", 0)))
        pairs.sort(key=lambda x: (x[2], x[1]), reverse=True)
        lines = ["💎 <b>TOP 10 SPENDERS</b>\n"]
        for i, (uid, uses, spent) in enumerate(pairs[:10], 1):
            lines.append(f"{i}. <code>{uid}</code> — €{spent/100 if spent else 0:.2f} | {uses} usos")
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_analytics"))
        bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "retention":
        flags_data = load_json(USER_FLAGS_FILE)
        now = int(time.time())
        d7 = now - 7*86400
        d1 = now - 86400
        active_7d = sum(1 for _, f in flags_data.items() if f.get("last_activity", 0) > d7)
        active_1d = sum(1 for _, f in flags_data.items() if f.get("last_activity", 0) > d1)
        total_users = len(load_json(CREDITS_FILE))
        msg = (f"🔁 <b>RETENÇÃO</b>\n\n"
               f"👥 Total users: <b>{total_users}</b>\n"
               f"🔥 Ativos últimas 24h: <b>{active_1d}</b>\n"
               f"📈 Ativos últimos 7d: <b>{active_7d}</b>\n"
               f"📊 Retenção 7d: <b>{(active_7d/total_users*100 if total_users else 0):.1f}%</b>")
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_analytics"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "top_features":
        stats_data = load_json(STATISTICS_FILE)
        total_creations = sum(int(s.get("total_creations", 0)) for s in stats_data.values())
        total_edits = sum(int(s.get("total_edits", 0)) for s in stats_data.values())
        msg = (f"🤖 <b>FEATURES MAIS USADAS</b>\n\n"
               f"🎨 Criações (text→image): <b>{total_creations}</b>\n"
               f"✏️ Edições (Pro/Padrão/Art): <b>{total_edits}</b>\n"
               f"📊 Total: <b>{total_creations + total_edits}</b>")
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_analytics"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "usage_period":
        # Usa SYSTEM_LOGS para estimar atividade recente (gen/edit events)
        logs = load_json(SYSTEM_LOGS_FILE).get("logs", [])
        now = int(time.time())
        d1 = now - 86400
        d7 = now - 7*86400
        last_24h = sum(1 for l in logs if l.get("ts", 0) > d1)
        last_7d = sum(1 for l in logs if l.get("ts", 0) > d7)
        msg = (f"🔥 <b>USO (via logs)</b>\n\n"
               f"Eventos 24h: <b>{last_24h}</b>\n"
               f"Eventos 7d: <b>{last_7d}</b>\n"
               f"Total logs: <b>{len(logs)}</b>")
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="admin_sec_analytics"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode='HTML')

    elif action == "noop":
        bot.answer_callback_query(call.id, "—")

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

@bot.message_handler(commands=['sugerir', 'suggest', 'sugerencia'])
def cmd_sugerir(message):
    """Sugere 3 prompts a partir de um tema. Uso: /sugerir <tema>"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or len(parts[1].strip()) < 2:
        user_states[user_id] = "awaiting_suggest_topic"
        ask_texts = {
            "pt": "💡 <b>Sugestões de Prompt</b>\n\nEscreve um tema curto e eu sugiro 3 prompts.\n<i>Ex: \"retrato cyberpunk\"</i>",
            "en": "💡 <b>Prompt Suggestions</b>\n\nType a short topic and I'll suggest 3 prompts.",
            "es": "💡 <b>Sugerencias de Prompt</b>\n\nEscribe un tema corto y sugiero 3 prompts."
        }
        bot.reply_to(message, ask_texts.get(lang, ask_texts["pt"]), parse_mode='HTML')
        return
    topic = parts[1].strip()
    _send_prompt_suggestions(message.chat.id, user_id, lang, topic)

def _send_prompt_suggestions(chat_id, user_id, lang, topic):
    """Gera 3 sugestoes de prompts via OpenAI a partir de um tema."""
    proc = bot.send_message(chat_id, "💡 A pensar em 3 prompts...")
    try:
        sys_prompt = (
            "You are a senior prompt engineer for AI image generation. "
            "Given a short topic, return EXACTLY 3 distinct, high-quality English prompts, "
            "each on a separate line, numbered 1., 2., 3. — no extra text, no markdown. "
            "Each prompt should be 15-35 words, vivid, with concrete details (lighting, mood, "
            "style, camera, composition). Make them varied (e.g. one cinematic, one artistic, one minimalist)."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Topic: {topic}"}
            ],
            temperature=0.9,
            max_tokens=400,
        )
        text = (resp.choices[0].message.content or "").strip()
        try:
            bot.delete_message(chat_id, proc.message_id)
        except:
            pass
        header = {
            "pt": f"💡 <b>3 sugestões para</b> «{topic}»\n\n",
            "en": f"💡 <b>3 suggestions for</b> «{topic}»\n\n",
            "es": f"💡 <b>3 sugerencias para</b> «{topic}»\n\n"
        }
        footer = {
            "pt": "\n\n<i>Copia uma e usa em 🎨 Gerar Fotos.</i>",
            "en": "\n\n<i>Copy one and use it in 🎨 Generate.</i>",
            "es": "\n\n<i>Copia uno y úsalo en 🎨 Generar.</i>"
        }
        bot.send_message(chat_id, header.get(lang, header["pt"]) + f"<code>{text}</code>" + footer.get(lang, footer["pt"]), parse_mode='HTML')
    except Exception as e:
        try:
            bot.delete_message(chat_id, proc.message_id)
        except:
            pass
        bot.send_message(chat_id, f"❌ Não consegui gerar sugestões agora. Tenta de novo.\n<code>{str(e)[:120]}</code>", parse_mode='HTML')

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_suggest_topic')
def handle_suggest_topic(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)
    topic = (message.text or "").strip()
    if len(topic) < 2:
        bot.reply_to(message, "❌ Tema muito curto. Tenta de novo com /sugerir <tema>.")
        return
    _send_prompt_suggestions(message.chat.id, user_id, lang, topic)

@bot.message_handler(commands=['creditos', 'credits'])
def cmd_creditos(message):
    user_id = message.from_user.id
    creditos = get_user_credits(user_id)
    bot.send_message(message.chat.id, f"💳 <code>{creditos}</code> créditos", parse_mode='HTML')


@bot.message_handler(commands=['ebook_waitlist', 'ebook_lista'])
def cmd_ebook_waitlist(message):
    """Admin: ver tamanho/estatísticas da waitlist do eBook."""
    user_id = message.from_user.id
    if not is_any_admin(user_id):
        return
    count = get_ebook_waitlist_count()
    bot.send_message(message.chat.id,
                     f"📚 <b>Lista de espera — Remake Pixel Prompt Vault</b>\n\n"
                     f"🔔 <b>{count}</b> users registados.\n\n"
                     f"Para fazer broadcast quando lançares: <code>/ebook_broadcast &lt;mensagem&gt;</code>\n"
                     f"Exemplo: <code>/ebook_broadcast O eBook está disponível! Compra com 30% desconto: https://...</code>",
                     parse_mode='HTML')


@bot.message_handler(commands=['ebook_broadcast'])
def cmd_ebook_broadcast(message):
    """Super admin: faz broadcast da mensagem a toda a waitlist do eBook."""
    user_id = message.from_user.id
    if not is_super_admin(user_id):
        bot.reply_to(message, "❌ Apenas super admin.")
        return
    text = message.text.replace("/ebook_broadcast", "", 1).strip()
    if not text:
        bot.reply_to(message, "Uso: <code>/ebook_broadcast &lt;mensagem para todos&gt;</code>", parse_mode='HTML')
        return
    users = get_ebook_waitlist_users()
    if not users:
        bot.reply_to(message, "📭 Lista de espera vazia.")
        return
    bot.reply_to(message, f"📤 A enviar para {len(users)} users... aguarda.")
    ok, fail = 0, 0
    body = f"📚 <b>Remake Pixel Prompt Vault</b>\n\n{text}"
    for uid, _lang in users:
        try:
            bot.send_message(uid, body, parse_mode='HTML', disable_web_page_preview=False)
            ok += 1
            time.sleep(0.05)  # respeita rate-limit
        except Exception:
            fail += 1
    bot.send_message(message.chat.id, f"✅ Broadcast concluído: {ok} entregue / {fail} falhas.")




@bot.message_handler(commands=['estilos', 'styles', 'catalogo'])
def cmd_estilos(message):
    """Mostra o catálogo de estilos do Modelo Padrão (com previews reais coletadas da galeria)."""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    title = {
        "pt": ("🎨 <b>Catálogo de Estilos — Modelo Padrão</b>\n\n"
               "Vê todos os estilos disponíveis (com previews reais de utilizadores que publicaram na galeria).\n\n"
               "💡 <i>Para usar um estilo: envia uma foto sem legenda, clica em Padrão e escolhe.</i>"),
        "en": ("🎨 <b>Style Catalog — Standard Model</b>\n\n"
               "Browse all available styles (with real previews from users who published to the gallery).\n\n"
               "💡 <i>To use a style: send a photo without caption, tap Standard and pick one.</i>"),
        "es": ("🎨 <b>Catálogo de Estilos — Modelo Estándar</b>\n\n"
               "Ve todos los estilos (con previews reales de usuarios que publicaron en la galería).\n\n"
               "💡 <i>Para usar un estilo: envía una foto sin descripción, toca Estándar y elige.</i>"),
    }
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    cats = {
        "pt": [("👨 Para Homens", "men"), ("👩 Para Mulheres", "women"), ("👤 Unissex", "unisex"),
               ("📋 Flyers Recrutamento", "flyer"), ("💑 Casais", "couple"), ("📚 Comics / Histórias", "comic"),
               ("📱 Posts Instagram", "stories"), ("🔥 Sensual", "sensual")],
        "en": [("👨 For Men", "men"), ("👩 For Women", "women"), ("👤 Unisex", "unisex"),
               ("📋 Recruitment Flyers", "flyer"), ("💑 Couples", "couple"), ("📚 Comics / Stories", "comic"),
               ("📱 Instagram Posts", "stories"), ("🔥 Sensual", "sensual")],
        "es": [("👨 Para Hombres", "men"), ("👩 Para Mujeres", "women"), ("👤 Unisex", "unisex"),
               ("📋 Flyers Reclutamiento", "flyer"), ("💑 Parejas", "couple"), ("📚 Comics / Historias", "comic"),
               ("📱 Posts Instagram", "stories"), ("🔥 Sensual", "sensual")],
    }
    # Conta quantos estilos por categoria + quantos têm preview
    previews = load_json(STYLE_PREVIEWS_FILE)
    cat_counts = {}
    for k, st in PADRAO_STYLES.items():
        c = st.get("cat", "unisex")
        cat_counts.setdefault(c, [0, 0])
        cat_counts[c][0] += 1
        if k in previews:
            cat_counts[c][1] += 1
    for label, cat_key in cats.get(lang, cats["pt"]):
        total, with_prev = cat_counts.get(cat_key, [0, 0])
        suffix = f" ({with_prev}/{total} previews)" if total > 0 else ""
        mk.add(telebot.types.InlineKeyboardButton(label + suffix, callback_data=f"est_cat_{cat_key}"))

    bot.send_message(message.chat.id, title.get(lang, title["pt"]), reply_markup=mk, parse_mode='HTML')


def _est_styles_keyboard(cat, lang):
    """Lista os estilos de uma categoria. Para 'unisex' mostra sub-grupos.
    Para 'couple'/'comic' mostra histórias. Outras categorias mostram estilos
    diretamente. Cada estilo tem um ✅ se já existe preview, ou ⚪ se ainda não."""
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    previews = load_json(STYLE_PREVIEWS_FILE)

    if cat == "unisex":
        # Conta previews por grupo
        for grp_key, grp in PADRAO_UNISEX_GROUPS.items():
            total, with_prev = 0, 0
            for k, st in PADRAO_STYLES.items():
                if st.get("cat") == "unisex" and st.get("grp") == grp_key:
                    total += 1
                    if k in previews:
                        with_prev += 1
            mk.add(telebot.types.InlineKeyboardButton(
                f"{grp['nome']} ({with_prev}/{total})",
                callback_data=f"est_grp_{grp_key}"
            ))
    elif cat in ("couple", "comic"):
        for story_key, story in PADRAO_STORIES.items():
            if story["cat"] == cat:
                mk.add(telebot.types.InlineKeyboardButton(story["nome"], callback_data=f"est_sto_{story_key}"))
    else:
        for k, st in PADRAO_STYLES.items():
            if st.get("cat") == cat:
                icon = "✅" if k in previews else "⚪"
                mk.add(telebot.types.InlineKeyboardButton(f"{icon} {st['nome']}", callback_data=f"est_view_{k}"))

    back_label = {"pt": "⬅️ Voltar ao catálogo", "en": "⬅️ Back to catalog", "es": "⬅️ Volver al catálogo"}.get(lang, "⬅️ Voltar")
    mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data="est_home"))
    return mk


@bot.callback_query_handler(func=lambda call: call.data.startswith("est_"))
def callback_estilos(call):
    """Navegação do catálogo /estilos."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    data = call.data

    if data == "est_home":
        # Recria o menu inicial editando a mensagem
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        # Re-envia (simplificado, reutiliza cmd_estilos com mensagem fake)
        class _FakeMsg:
            chat = call.message.chat
            from_user = call.from_user
        cmd_estilos(_FakeMsg)
        return

    if data.startswith("est_cat_"):
        cat = data.replace("est_cat_", "")
        titles = {
            "men":     {"pt": "👨 <b>Para Homens</b>", "en": "👨 <b>For Men</b>", "es": "👨 <b>Para Hombres</b>"},
            "women":   {"pt": "👩 <b>Para Mulheres</b>", "en": "👩 <b>For Women</b>", "es": "👩 <b>Para Mujeres</b>"},
            "unisex":  {"pt": "👤 <b>Unissex</b> — escolhe o tema:", "en": "👤 <b>Unisex</b> — pick a theme:", "es": "👤 <b>Unisex</b> — elige el tema:"},
            "flyer":   {"pt": "📋 <b>Flyers Recrutamento</b>", "en": "📋 <b>Recruitment Flyers</b>", "es": "📋 <b>Flyers Reclutamiento</b>"},
            "couple":  {"pt": "💑 <b>Casais</b>", "en": "💑 <b>Couples</b>", "es": "💑 <b>Parejas</b>"},
            "comic":   {"pt": "📚 <b>Comics / Histórias</b>", "en": "📚 <b>Comics / Stories</b>", "es": "📚 <b>Comics / Historias</b>"},
            "stories": {"pt": "📱 <b>Posts Instagram</b>", "en": "📱 <b>Instagram Posts</b>", "es": "📱 <b>Posts Instagram</b>"},
            "sensual": {"pt": "🔥 <b>Sensual</b>", "en": "🔥 <b>Sensual</b>", "es": "🔥 <b>Sensual</b>"},
        }
        title = titles.get(cat, titles["men"]).get(lang, titles.get(cat, titles["men"])["pt"])
        legend = {
            "pt": "\n\n✅ Já tem preview real · ⚪ Ainda sem preview",
            "en": "\n\n✅ Has real preview · ⚪ No preview yet",
            "es": "\n\n✅ Tiene preview real · ⚪ Sin preview aún",
        }
        try:
            bot.edit_message_text(title + legend.get(lang, legend["pt"]),
                                  call.message.chat.id, call.message.message_id,
                                  reply_markup=_est_styles_keyboard(cat, lang), parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, title + legend.get(lang, legend["pt"]),
                             reply_markup=_est_styles_keyboard(cat, lang), parse_mode='HTML')
        return

    if data.startswith("est_grp_"):
        grp_key = data.replace("est_grp_", "")
        grp = PADRAO_UNISEX_GROUPS.get(grp_key)
        if not grp:
            bot.answer_callback_query(call.id, "Grupo inválido.")
            return
        previews = load_json(STYLE_PREVIEWS_FILE)
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        for k, st in PADRAO_STYLES.items():
            if st.get("cat") == "unisex" and st.get("grp") == grp_key:
                icon = "✅" if k in previews else "⚪"
                mk.add(telebot.types.InlineKeyboardButton(f"{icon} {st['nome']}", callback_data=f"est_view_{k}"))
        back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
        mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data="est_cat_unisex"))
        try:
            bot.edit_message_text(f"{grp['nome']}", call.message.chat.id, call.message.message_id,
                                  reply_markup=mk, parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, grp['nome'], reply_markup=mk, parse_mode='HTML')
        return

    if data.startswith("est_sto_"):
        story_key = data.replace("est_sto_", "")
        story = PADRAO_STORIES.get(story_key)
        if not story:
            bot.answer_callback_query(call.id, "História inválida.")
            return
        previews = load_json(STYLE_PREVIEWS_FILE)
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        for sk in story["scenes"]:
            st = PADRAO_STYLES.get(sk)
            if st:
                icon = "✅" if sk in previews else "⚪"
                mk.add(telebot.types.InlineKeyboardButton(f"{icon} {st['nome']}", callback_data=f"est_view_{sk}"))
        back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
        mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data=f"est_cat_{story['cat']}"))
        try:
            bot.edit_message_text(story['nome'], call.message.chat.id, call.message.message_id,
                                  reply_markup=mk, parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, story['nome'], reply_markup=mk, parse_mode='HTML')
        return

    if data.startswith("est_view_"):
        style_key = data.replace("est_view_", "")
        style = PADRAO_STYLES.get(style_key)
        if not style:
            bot.answer_callback_query(call.id, "Estilo inválido.")
            return
        preview = get_style_preview(style_key)

        # Determina para onde voltar
        cat = style.get("cat", "men")
        if cat == "unisex" and style.get("grp"):
            back_cb = f"est_grp_{style['grp']}"
        elif cat in ("couple", "comic") and style.get("story"):
            back_cb = f"est_sto_{style['story']}"
        else:
            back_cb = f"est_cat_{cat}"

        cap_lines = {
            "pt": [
                f"🎨 <b>{style['nome']}</b>",
                "",
                f"Categoria: <i>{cat}</i>" + (f" / {PADRAO_UNISEX_GROUPS[style['grp']]['nome']}" if style.get('grp') and style.get('grp') in PADRAO_UNISEX_GROUPS else ""),
                f"💳 Custo: {MODELO_PADRAO['custo']} créditos",
                "",
                "💡 Para usar este estilo: envia uma foto <b>sem legenda</b> no chat, clica em <b>Padrão</b> e escolhe esta opção.",
            ],
            "en": [
                f"🎨 <b>{style['nome']}</b>",
                "",
                f"Category: <i>{cat}</i>",
                f"💳 Cost: {MODELO_PADRAO['custo']} credits",
                "",
                "💡 To use: send a photo <b>without caption</b>, tap <b>Standard</b> and pick this style.",
            ],
            "es": [
                f"🎨 <b>{style['nome']}</b>",
                "",
                f"Categoría: <i>{cat}</i>",
                f"💳 Costo: {MODELO_PADRAO['custo']} créditos",
                "",
                "💡 Para usar: envía una foto <b>sin descripción</b>, toca <b>Estándar</b> y elige.",
            ],
        }
        caption = "\n".join(cap_lines.get(lang, cap_lines["pt"]))

        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
        mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data=back_cb))

        # Apaga a mensagem de menu antes de enviar foto/preview
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        if preview and preview.get("file_id"):
            try:
                bot.send_photo(call.message.chat.id, preview["file_id"],
                               caption=caption, reply_markup=mk, parse_mode='HTML')
                return
            except Exception as e:
                logger.warning(f"Falha a enviar preview file_id ({style_key}): {e}")

        # Sem preview → mensagem de placeholder
        nopreview = {
            "pt": "\n\n📭 <i>Ainda sem preview real. Sê o primeiro a publicar este estilo na galeria <b>@RemakePixel_Gallery</b> e a tua imagem fica aqui!</i>",
            "en": "\n\n📭 <i>No real preview yet. Be the first to publish this style to <b>@RemakePixel_Gallery</b> and your image will appear here!</i>",
            "es": "\n\n📭 <i>Sin preview real aún. ¡Sé el primero en publicar este estilo en <b>@RemakePixel_Gallery</b>!</i>",
        }
        bot.send_message(call.message.chat.id, caption + nopreview.get(lang, nopreview["pt"]),
                         reply_markup=mk, parse_mode='HTML')



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

# ==================== FLOW V2 — CREATE / EDIT / STYLES / SIZE / MODEL ====================
# Estado de criacao v2 em memoria
v2_flows = {}  # user_id -> {"step": "...", "prompt": "...", "is_edit": False, "photo_id": "..."}


def _v2_model_picker_kb(lang, current=None):
    """Mostra todos os 5 modelos com preços."""
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, m in MODELS_V2.items():
        # skip edit_master em generation (so aparece em edit)
        marker = " ✓" if key == current else ""
        label = f"{m['nome']} — {m['custo']}c{marker}"
        mk.add(telebot.types.InlineKeyboardButton(label, callback_data=f"v2_pickmodel_{key}"))
    back = {"pt": "◀️ Voltar", "en": "◀️ Back", "es": "◀️ Volver"}
    mk.add(telebot.types.InlineKeyboardButton(back.get(lang, back["pt"]), callback_data="v2_model_back"))
    return mk


def _v2_size_picker_kb(lang, current=None):
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    rows = []
    for key, s in SIZES_V2.items():
        marker = " ✓" if key == current else ""
        rows.append(telebot.types.InlineKeyboardButton(s["nome"] + marker, callback_data=f"v2_picksize_{key}"))
    for i in range(0, len(rows), 2):
        mk.row(*rows[i:i+2])
    return mk


def _v2_styles_picker_kb(user_id, lang, page=0):
    """Grelha de estilos com paginacao (10 por pagina). Multi-select."""
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    selected = get_user_styles_v2(user_id)
    keys = list(STYLES_V2.keys())
    per_page = 10
    start = page * per_page
    page_keys = keys[start:start+per_page]
    for key in page_keys:
        s = STYLES_V2[key]
        marker = "✅ " if key in selected else ""
        mk.add(telebot.types.InlineKeyboardButton(f"{marker}{s['nome']}", callback_data=f"v2_togglestyle_{key}_{page}"))
    # Nav
    nav = []
    if page > 0:
        nav.append(telebot.types.InlineKeyboardButton("◀️", callback_data=f"v2_stylesp_{page-1}"))
    if start + per_page < len(keys):
        nav.append(telebot.types.InlineKeyboardButton("▶️", callback_data=f"v2_stylesp_{page+1}"))
    if nav:
        mk.row(*nav)
    clear = {"pt": "🗑 Limpar", "en": "🗑 Clear", "es": "🗑 Limpiar"}
    done = {"pt": "✅ Pronto", "en": "✅ Done", "es": "✅ Listo"}
    mk.row(
        telebot.types.InlineKeyboardButton(clear.get(lang, clear["pt"]), callback_data="v2_stylesclear"),
        telebot.types.InlineKeyboardButton(done.get(lang, done["pt"]), callback_data="v2_stylesdone")
    )
    return mk


def _v2_show_model_confirm(chat_id, user_id, lang):
    """Mostra 'Using Creative Flow (5c). Change?' antes de gerar."""
    model_key = get_user_model_v2(user_id)
    m = get_model_v2(model_key)
    styles = get_user_styles_v2(user_id)
    styles_str = ", ".join([STYLES_V2[s]["nome"] for s in styles]) if styles else "—"
    size = SIZES_V2[get_user_size_v2(user_id)]["nome"]
    creds = get_user_credits(user_id)

    texts = {
        "pt": (f"⚡ <b>Pronto para gerar!</b>\n\n"
               f"🤖 Modelo: <b>{m['nome']}</b> — {m['custo']} créditos\n"
               f"🎭 Estilos: {styles_str}\n"
               f"📐 Tamanho: {size}\n"
               f"💳 Saldo: {creds}\n\n"
               f"Confirmar?"),
        "en": (f"⚡ <b>Ready to generate!</b>\n\n"
               f"🤖 Model: <b>{m['nome']}</b> — {m['custo']} credits\n"
               f"🎭 Styles: {styles_str}\n"
               f"📐 Size: {size}\n"
               f"💳 Balance: {creds}\n\n"
               f"Confirm?"),
        "es": (f"⚡ <b>¡Listo para generar!</b>\n\n"
               f"🤖 Modelo: <b>{m['nome']}</b> — {m['custo']} créditos\n"
               f"🎭 Estilos: {styles_str}\n"
               f"📐 Tamaño: {size}\n"
               f"💳 Saldo: {creds}\n\n"
               f"¿Confirmar?"),
    }
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    gen_txt = {"pt": "✅ Gerar", "en": "✅ Generate", "es": "✅ Generar"}
    change_txt = {"pt": "🔄 Mudar Modelo", "en": "🔄 Change Model", "es": "🔄 Cambiar Modelo"}
    mk.add(
        telebot.types.InlineKeyboardButton(gen_txt.get(lang, gen_txt["pt"]), callback_data="v2_gen_go"),
        telebot.types.InlineKeyboardButton(change_txt.get(lang, change_txt["pt"]), callback_data="v2_gen_changemodel")
    )
    cancel_txt = {"pt": "❌ Cancelar", "en": "❌ Cancel", "es": "❌ Cancelar"}
    mk.add(telebot.types.InlineKeyboardButton(cancel_txt.get(lang, cancel_txt["pt"]), callback_data="v2_gen_cancel"))
    bot.send_message(chat_id, texts.get(lang, texts["pt"]), reply_markup=mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda c: c.data.startswith('v2_'))
def callback_v2(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data

    # Menu estilos (a partir do botao 🎭 Estilos)
    if action == "v2_styles_menu":
        txt = {
            "pt": "🎭 <b>Seleciona estilos</b> (podes escolher vários, max 5):",
            "en": "🎭 <b>Pick styles</b> (multi-select, max 5):",
            "es": "🎭 <b>Elige estilos</b> (multi, max 5):"
        }
        try:
            bot.edit_message_text(txt.get(lang, txt["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=_v2_styles_picker_kb(user_id, lang, 0), parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, txt.get(lang, txt["pt"]),
                             reply_markup=_v2_styles_picker_kb(user_id, lang, 0), parse_mode='HTML')
        return

    if action.startswith("v2_stylesp_"):
        page = int(action.replace("v2_stylesp_", ""))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=_v2_styles_picker_kb(user_id, lang, page))
        return

    if action.startswith("v2_togglestyle_"):
        rest = action.replace("v2_togglestyle_", "")
        parts = rest.rsplit("_", 1)
        style_key = parts[0]
        page = int(parts[1]) if len(parts) > 1 else 0
        toggle_user_style_v2(user_id, style_key)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=_v2_styles_picker_kb(user_id, lang, page))
        return

    if action == "v2_stylesclear":
        set_user_styles_v2(user_id, [])
        bot.answer_callback_query(call.id, "Estilos limpos")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=_v2_styles_picker_kb(user_id, lang, 0))
        return

    if action == "v2_stylesdone":
        sel = get_user_styles_v2(user_id)
        msg = f"✅ {len(sel)} estilo(s) ativo(s). Volta ao menu e cria!"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, msg)
        return

    # Tamanho
    if action == "v2_size_menu":
        cur = get_user_size_v2(user_id)
        txt = {"pt": "📐 <b>Tamanho:</b>", "en": "📐 <b>Size:</b>", "es": "📐 <b>Tamaño:</b>"}
        bot.edit_message_text(txt.get(lang, txt["pt"]), call.message.chat.id, call.message.message_id,
                              reply_markup=_v2_size_picker_kb(lang, cur), parse_mode='HTML')
        return

    if action.startswith("v2_picksize_"):
        size_key = action.replace("v2_picksize_", "")
        if size_key in SIZES_V2:
            set_user_size_v2(user_id, size_key)
            bot.answer_callback_query(call.id, f"Tamanho: {SIZES_V2[size_key]['nome']}")

    # Modelo picker
    if action == "v2_gen_changemodel":
        cur = get_user_model_v2(user_id)
        txt = {"pt": "🤖 <b>Escolhe o modelo:</b>", "en": "🤖 <b>Pick model:</b>", "es": "🤖 <b>Elige modelo:</b>"}
        bot.edit_message_text(txt.get(lang, txt["pt"]), call.message.chat.id, call.message.message_id,
                              reply_markup=_v2_model_picker_kb(lang, cur), parse_mode='HTML')
        return

    if action.startswith("v2_pickmodel_"):
        model_key = action.replace("v2_pickmodel_", "")
        if model_key in MODELS_V2:
            set_user_model_v2(user_id, model_key)
            m = MODELS_V2[model_key]
            bot.answer_callback_query(call.id, f"Modelo: {m['nome']} ({m['custo']}c)")
            # Volta ao confirm
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            _v2_show_model_confirm(call.message.chat.id, user_id, lang)
        return

    if action == "v2_model_back" or action == "v2_gen_cancel":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        v2_flows.pop(user_id, None)
        return

    # Gerar (text-to-image)
    if action == "v2_gen_go":
        flow = v2_flows.get(user_id)
        if not flow:
            bot.answer_callback_query(call.id, "Sessão expirada. Começa de novo.")
            return
        model_key = get_user_model_v2(user_id)
        m = get_model_v2(model_key)
        creds = get_user_credits(user_id)
        if creds < m["custo"]:
            txt = {"pt": f"❌ Créditos insuficientes! Precisas de {m['custo']}, tens {creds}.",
                   "en": f"❌ Not enough credits! Need {m['custo']}, have {creds}.",
                   "es": f"❌ Créditos insuficientes! Necesitas {m['custo']}, tienes {creds}."}
            bot.answer_callback_query(call.id, txt.get(lang, txt["pt"]), show_alert=True)
            return

        # Se é Ultra Real, mostrar submenu realismo primeiro
        if m.get("uses_realism_presets"):
            mk = telebot.types.InlineKeyboardMarkup(row_width=1)
            for pk, preset in PRO_PRESETS.items():
                mk.add(telebot.types.InlineKeyboardButton(preset["nome"], callback_data=f"v2_realism_{pk}"))
            txt = {"pt": "📸 <b>Tipo de realismo:</b>", "en": "📸 <b>Realism type:</b>", "es": "📸 <b>Tipo realismo:</b>"}
            try:
                bot.edit_message_text(txt.get(lang, txt["pt"]), call.message.chat.id, call.message.message_id,
                                      reply_markup=mk, parse_mode='HTML')
            except Exception:
                bot.send_message(call.message.chat.id, txt.get(lang, txt["pt"]), reply_markup=mk, parse_mode='HTML')
            return

        # Caso geral — debita e gera
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        if not use_credit(user_id, m["custo"]):
            bot.send_message(call.message.chat.id, "❌ Falha ao debitar.")
            return
        bot.send_message(call.message.chat.id, f"⚡ {m['custo']} créditos usados. A gerar...")
        _v2_execute_generation(call.message.chat.id, user_id, lang, flow, model_key)
        return

    if action.startswith("v2_realism_"):
        preset_key = action.replace("v2_realism_", "")
        preset = PRO_PRESETS.get(preset_key)
        flow = v2_flows.get(user_id)
        if not preset or not flow:
            bot.answer_callback_query(call.id, "Erro. Recomeça.")
            return
        model_key = "ultra_real"
        m = MODELS_V2[model_key]
        if not use_credit(user_id, m["custo"]):
            return
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, f"⚡ {m['custo']} créditos usados. A gerar (Ultra Real)...")
        _v2_execute_generation(call.message.chat.id, user_id, lang, flow, model_key, realism_preset=preset)
        return


def _v2_execute_generation(chat_id, user_id, lang, flow, model_key, realism_preset=None):
    """Executa geracao text-to-image (nao edicao) com settings v2."""
    m = get_model_v2(model_key)
    prompt = flow.get("prompt", "").strip()

    # Aplica boost do modelo
    if m.get("prompt_boost"):
        prompt += m["prompt_boost"]

    # Aplica estilos
    styles = get_user_styles_v2(user_id)
    for s in styles:
        if s in STYLES_V2:
            prompt += STYLES_V2[s]["suffix"]

    # Aplica realism preset (Ultra Real)
    if realism_preset:
        prompt = realism_preset["prompt"] + "\n\nTarget: " + prompt

    # Tamanho (aspect_ratio)
    ar = SIZES_V2[get_user_size_v2(user_id)]["ar"]

    try:
        if m["backend"] == "grok":
            output = replicate.run(m["replicate_id"], input={
                "prompt": prompt,
                "aspect_ratio": ar,
                "num_outputs": 1
            })
        else:  # flux
            output = replicate.run(m["replicate_id"], input={
                "prompt": prompt,
                "aspect_ratio": ar,
                "safety_tolerance": 6,
                "disable_safety_checker": True
            })

        if isinstance(output, list) and output:
            url = str(output[0])
        elif hasattr(output, "url"):
            url = str(output.url)
        else:
            url = str(output)

        img_bytes = requests.get(url, timeout=60).content
        cid = add_to_history(user_id, "create_v2", prompt[:200], url)
        creds = get_user_credits(user_id)

        caption = (f"✨ <b>{m['nome']}</b>\n"
                   f"📐 {SIZES_V2[get_user_size_v2(user_id)]['nome']} | "
                   f"🎭 {len(styles)} estilo(s)\n"
                   f"💳 {creds} créditos restantes")
        bot.send_photo(chat_id, img_bytes, caption=caption,
                       reply_markup=creation_actions_keyboard(cid, lang), parse_mode='HTML')
        update_user_stats(user_id, "total_creations")
        log_system_event("info", "v2_gen_ok", f"model={model_key} user={user_id}", user_id)
    except Exception as e:
        # refund
        add_credits(user_id, m["custo"], "refund_v2_fail")
        log_system_event("error", "v2_gen_fail", str(e), user_id)
        bot.send_message(chat_id, f"❌ Erro: {str(e)[:120]}. Créditos reembolsados.")

    v2_flows.pop(user_id, None)


# ==================== FLOW V2 — handler do Create (a partir de action_create) ====================
# Intercepta action_create/action_edit_photos para iniciar flow v2 (novo menu)
@bot.callback_query_handler(func=lambda c: c.data == "v2_create_start")
def v2_create_start_handler(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    v2_flows[user_id] = {"step": "awaiting_prompt", "is_edit": False}
    user_states[user_id] = "v2_awaiting_prompt"
    txt = {
        "pt": ("🎨 <b>Criar Imagem</b>\n\n"
               "Descreve a imagem que queres gerar.\n"
               "<i>Ex: 'um gato cyberpunk num telhado à noite'</i>"),
        "en": ("🎨 <b>Create Image</b>\n\n"
               "Describe the image you want.\n"
               "<i>Ex: 'a cyberpunk cat on a rooftop at night'</i>"),
        "es": ("🎨 <b>Crear Imagen</b>\n\n"
               "Describe la imagen que quieres.\n"
               "<i>Ej: 'un gato cyberpunk en un tejado de noche'</i>"),
    }
    bot.send_message(call.message.chat.id, txt.get(lang, txt["pt"]), parse_mode='HTML')


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'v2_awaiting_prompt')
def v2_awaiting_prompt_handler(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)

    prompt = (message.text or "").strip()
    if len(prompt) < 3:
        bot.reply_to(message, "❌ Prompt muito curto. Tenta novamente.")
        return

    # Safety gate
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=True)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        return

    v2_flows[user_id] = {"step": "ready", "prompt": prompt, "is_edit": False}
    _v2_show_model_confirm(message.chat.id, user_id, lang)



@bot.message_handler(commands=['report', 'denunciar'])
def cmd_report(message):
    """User reporta outro user: /report <user_id> <razao>"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Uso: <code>/report &lt;user_id&gt; &lt;razão&gt;</code>", parse_mode='HTML')
        return
    try:
        target = int(parts[1])
    except:
        bot.reply_to(message, "❌ user_id inválido.")
        return
    if target == message.from_user.id:
        bot.reply_to(message, "❌ Não te podes reportar a ti próprio.")
        return
    rid = add_report(message.from_user.id, target, parts[2])
    log_system_event("warn", "user_report", f"{message.from_user.id} -> {target}: {parts[2][:80]}", target)
    bot.reply_to(message, f"✅ Report enviado (ID: <code>{rid}</code>). Obrigado!", parse_mode='HTML')
    # Notificar admin
    for aid in ADMIN_IDS:
        try:
            bot.send_message(aid, f"🚨 <b>Novo Report</b>\nDe: {message.from_user.id}\nContra: {target}\nRazão: {parts[2][:200]}", parse_mode='HTML')
        except:
            pass


# ==================== INSTAGRAM AUTOPOSTER — ADMIN ====================
IG_QUEUE_FILE = "ig_queue.json"
IG_TIPOS = ["criativo", "reflexao", "motivacao", "sentimentos", "humor", "simples"]


def _ig_queue_load():
    return load_json(IG_QUEUE_FILE).get("queue", [])


def _ig_queue_save(queue):
    save_json(IG_QUEUE_FILE, {"queue": queue}, Lock())


@bot.message_handler(commands=['ig'])
def cmd_ig_admin(message):
    """Admin-only: menu para adicionar criacoes a fila Instagram."""
    user_id = message.from_user.id
    if not is_any_admin(user_id):
        return  # silent deny para nao-admin

    # Lista ultimas 8 criacoes do admin
    history = load_json(HISTORY_FILE).get(str(user_id), [])
    if not history:
        bot.reply_to(message, "📭 Sem criações no teu histórico. Gera algo primeiro.")
        return

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for c in history[:8]:
        cid = c.get("id", "?")
        prompt = (c.get("prompt") or "")[:40]
        markup.add(telebot.types.InlineKeyboardButton(
            f"📸 {prompt}...", callback_data=f"ig_pick_{cid}"
        ))

    # Fila atual
    queue = _ig_queue_load()
    markup.add(telebot.types.InlineKeyboardButton(
        f"📬 Fila atual ({len(queue)})", callback_data="ig_showq"
    ))
    markup.add(telebot.types.InlineKeyboardButton("❌ Fechar", callback_data="ig_close"))

    bot.send_message(message.chat.id,
        "📱 <b>Instagram Auto-Poster</b>\n\nEscolhe uma criação para adicionar à fila de publicação:",
        reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda c: c.data.startswith('ig_'))
def callback_ig(call):
    user_id = call.from_user.id
    if not is_any_admin(user_id):
        bot.answer_callback_query(call.id, "Apenas admin.")
        return

    action = call.data

    if action == "ig_close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if action == "ig_showq":
        queue = _ig_queue_load()
        if not queue:
            bot.answer_callback_query(call.id, "Fila vazia.")
            return
        lines = [f"<b>Fila Instagram ({len(queue)})</b>\n"]
        for item in queue[:10]:
            tipo = item.get("tipo", "?")
            lines.append(f"• #{item.get('id','?')} [{tipo}] — {item.get('prompt','')[:40]}")
        lines.append(f"\n<i>No teu PC, corre:</i>\n<code>python instagram_poster.py queue {os.getenv('RENDER_EXTERNAL_URL','https://TEU-BOT.onrender.com')}</code>")
        bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, parse_mode='HTML')
        return

    if action.startswith("ig_pick_"):
        creation_id = action.replace("ig_pick_", "")
        # Mostra tipos de legenda
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        for t in IG_TIPOS:
            mk.add(telebot.types.InlineKeyboardButton(t.capitalize(), callback_data=f"ig_type_{creation_id}_{t}"))
        mk.add(telebot.types.InlineKeyboardButton("◀️ Voltar", callback_data="ig_back"))
        bot.edit_message_text(
            f"📝 <b>Estilo da legenda:</b>\n\nEscolhe o tom da legenda para esta criação.",
            call.message.chat.id, call.message.message_id,
            reply_markup=mk, parse_mode='HTML'
        )
        return

    if action == "ig_back":
        # volta ao menu
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        fake_msg = type('obj', (), {'chat': call.message.chat, 'from_user': call.from_user})
        cmd_ig_admin(fake_msg)
        return

    if action.startswith("ig_type_"):
        # ig_type_<creation_id>_<tipo>
        rest = action.replace("ig_type_", "")
        parts = rest.rsplit("_", 1)
        creation_id = parts[0]
        tipo = parts[1]

        # Busca criacao
        history = load_json(HISTORY_FILE).get(str(user_id), [])
        creation = next((c for c in history if c.get("id") == creation_id), None)
        if not creation:
            bot.answer_callback_query(call.id, "Criação não encontrada.")
            return

        image_url = creation.get("image_url") or creation.get("url")
        prompt = creation.get("prompt", "")

        # Adiciona a fila
        queue = _ig_queue_load()
        new_id = f"ig{int(time.time())}"
        queue.append({
            "id": new_id,
            "creation_id": creation_id,
            "image_url": image_url,
            "prompt": prompt,
            "tipo": tipo,
            "ts": int(time.time()),
            "status": "pending"
        })
        _ig_queue_save(queue)
        log_system_event("info", "ig_queue_add", f"#{new_id} tipo={tipo}", user_id)

        bot.edit_message_text(
            f"✅ <b>Adicionado à fila!</b>\n\n"
            f"📝 Tipo: <b>{tipo}</b>\n"
            f"📬 Fila agora tem <b>{len(queue)}</b> posts\n\n"
            f"<b>No teu PC:</b>\n"
            f"<code>python instagram_poster.py queue {os.getenv('RENDER_EXTERNAL_URL','https://TEU-BOT.onrender.com')}</code>",
            call.message.chat.id, call.message.message_id, parse_mode='HTML'
        )


# Endpoints Flask para o script IG consultar/limpar fila
@app.route("/api/ig_queue", methods=["GET"])
def ig_queue_get():
    q = _ig_queue_load()
    pending = [x for x in q if x.get("status") == "pending"]
    return {"queue": pending[:20]}, 200


@app.route("/api/ig_queue/<item_id>/ack", methods=["POST"])
def ig_queue_ack(item_id):
    q = _ig_queue_load()
    status = (request.get_json(silent=True) or {}).get("status", "ok")
    for item in q:
        if item.get("id") == item_id:
            item["status"] = "published" if status == "ok" else "failed"
            item["published_ts"] = int(time.time())
            break
    _ig_queue_save(q)
    return {"success": True}, 200



@bot.message_handler(commands=['perfil'])
def cmd_perfil(message):
    """Admin: /perfil <user_id> | User: ver proprio perfil resumido"""
    user_id = message.from_user.id
    parts = message.text.split()

    if len(parts) > 1:
        if not is_any_admin(user_id):
            bot.reply_to(message, "❌ So admin pode ver perfil de outros.")
            return
        try:
            target = int(parts[1])
            bot.send_message(message.chat.id, render_user_profile(target),
                             reply_markup=user_profile_kb(target), parse_mode='HTML')
        except:
            bot.reply_to(message, "❌ user_id invalido.")
        return

    credits = get_user_credits(user_id)
    stats = load_json(STATISTICS_FILE).get(str(user_id), {})
    flags = get_user_flags(user_id)
    tags_str = ", ".join(flags.get("tags", [])) or "—"
    msg = (f"👤 <b>O teu perfil</b>\n\n"
           f"🆔 <code>{user_id}</code>\n"
           f"💳 Creditos: <b>{credits}</b>\n"
           f"🎨 Criacoes: {stats.get('total_creations',0)}\n"
           f"✏️ Edicoes: {stats.get('total_edits',0)}\n"
           f"🏷️ Tags: {tags_str}")
    bot.reply_to(message, msg, parse_mode='HTML')



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

# ==================== HANDLERS DE INPUT ADMIN (NOVOS) ====================
@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "") == 'awaiting_user_search')
def handle_admin_user_search(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    admin_states.pop(user_id, None)
    query = message.text.strip().lstrip("@")
    target = None
    try:
        target = int(query)
    except ValueError:
        # Procurar por username em CREDITS_FILE via bot.get_chat
        credits = load_json(CREDITS_FILE)
        for uid_s in credits.keys():
            try:
                info = bot.get_chat(int(uid_s))
                if getattr(info, "username", None) and info.username.lower() == query.lower():
                    target = int(uid_s)
                    break
            except:
                continue
    if not target:
        bot.reply_to(message, f"❌ User não encontrado: {query}")
        return
    bot.send_message(message.chat.id, render_user_profile(target),
                     reply_markup=user_profile_kb(target), parse_mode='HTML')


@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "") == 'awaiting_nsfw_kw')
def handle_admin_nsfw_kw(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    admin_states.pop(user_id, None)
    if message.text.strip().lower() in ("/cancel", "cancel", "cancelar"):
        bot.reply_to(message, "❌ Cancelado.")
        return
    new_kws = [k.strip().lower() for k in message.text.split(",") if k.strip()]
    set_system_config("nsfw_keywords", new_kws)
    log_system_event("info", "cfg_change", f"NSFW keywords atualizadas ({len(new_kws)})", user_id)
    bot.reply_to(message, f"✅ {len(new_kws)} NSFW keywords guardadas.")


@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "") == 'awaiting_ratelimit')
def handle_admin_ratelimit(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    admin_states.pop(user_id, None)
    try:
        val = int(message.text.strip())
        if val < 1 or val > 1000:
            raise ValueError
        set_system_config("rate_limit_per_min", val)
        log_system_event("info", "cfg_change", f"rate_limit={val}/min", user_id)
        bot.reply_to(message, f"✅ Rate limit = {val}/min.")
    except:
        bot.reply_to(message, "❌ Número inválido (1-1000).")


@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "").startswith('awaiting_rm_credits_'))
def handle_admin_rm_credits(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    state = admin_states.pop(user_id, "")
    try:
        target = int(state.replace("awaiting_rm_credits_", ""))
        amount = int(message.text.strip())
        c = load_json(CREDITS_FILE)
        cur = c.get(str(target), {}).get("creditos", 0)
        new_total = max(0, cur - amount)
        if str(target) not in c:
            c[str(target)] = {"creditos": 0}
        c[str(target)]["creditos"] = new_total
        save_json(CREDITS_FILE, c, CREDITS_LOCK)
        log_system_event("info", "user_action", f"Admin removed {amount} credits from {target}", target)
        bot.reply_to(message, f"✅ Removidos {amount} créd. Novo saldo: {new_total}")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {e}")


@bot.message_handler(func=lambda m: admin_states.get(m.from_user.id, "").startswith('awaiting_broadcast_'))
def handle_admin_broadcast_seg(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    state = admin_states.pop(user_id, "")
    segment = state.replace("awaiting_broadcast_", "")  # all, active, vip
    text = message.text

    credits_data = load_json(CREDITS_FILE)
    flags_data = load_json(USER_FLAGS_FILE)
    now = int(time.time())

    if segment == "all":
        targets = list(credits_data.keys())
    elif segment == "active":
        d7 = now - 7*86400
        targets = [uid for uid, f in flags_data.items() if f.get("last_activity", 0) > d7]
    elif segment == "vip":
        targets = [uid for uid, f in flags_data.items() if "VIP" in f.get("tags", [])]
    else:
        targets = []

    sent = 0
    failed = 0
    for uid_s in targets:
        try:
            bot.send_message(int(uid_s), text, parse_mode='HTML')
            sent += 1
        except:
            failed += 1
    log_system_event("info", "broadcast", f"Segment={segment} sent={sent} failed={failed}", user_id)
    bot.reply_to(message, f"📢 Broadcast enviado.\n✅ {sent} OK | ❌ {failed} falhas\nSegmento: {segment}")



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

    # GATE DE SEGURANCA (admin ignora tudo)
    allowed, reason, extra = check_user_allowed(user_id, prompt=caption, check_rate=True)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        return
    if reason == "shadowban":
        log_system_event("info", "shadowban_drop", f"Photo dropped for shadowbanned user {user_id}", user_id)
        return  # engole silenciosamente
    
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
            "pt": f"📸 <b>Foto recebida!</b>\n\n💬 Descrição: <i>{caption[:80]}</i>\n\n<b>Escolha o modelo:</b>\n\n🎨 <b>Padrão</b> ({MODELO_PADRAO['custo']} cred) — Edita conforme descrição\n✨ <b>Pro</b> ({MODELO_PRO['custo']} cred) — Melhoria fotorrealista automática\n🎭 <b>Artístico</b> ({MODELO_ARTISTICO['custo']} cred) — Transforma em estilos artísticos\n\n💳 Créditos: <code>{creditos}</code>",
            "en": f"📸 <b>Photo received!</b>\n\n💬 Description: <i>{caption[:80]}</i>\n\n<b>Choose model:</b>\n\n🎨 <b>Standard</b> ({MODELO_PADRAO['custo']} cred) — Edits by description\n✨ <b>Pro</b> ({MODELO_PRO['custo']} cred) — Auto photorealistic enhancement\n🎭 <b>Artistic</b> ({MODELO_ARTISTICO['custo']} cred) — Transform to art styles\n\n💳 Credits: <code>{creditos}</code>",
            "es": f"📸 <b>Foto recibida!</b>\n\n💬 Descripción: <i>{caption[:80]}</i>\n\n<b>Elige modelo:</b>\n\n🎨 <b>Estándar</b> ({MODELO_PADRAO['custo']} cred) — Edita según descripción\n✨ <b>Pro</b> ({MODELO_PRO['custo']} cred) — Mejora fotorrealista automática\n🎭 <b>Artístico</b> ({MODELO_ARTISTICO['custo']} cred) — Transforma en estilos artísticos\n\n💳 Créditos: <code>{creditos}</code>"
        }
        markup.add(
            telebot.types.InlineKeyboardButton(f"🎨 Padrão · {MODELO_PADRAO['custo']} créditos", callback_data="photo_model_padrao"),
            telebot.types.InlineKeyboardButton(f"✨ Pro · {MODELO_PRO['custo']} créditos", callback_data="photo_model_pro"),
            telebot.types.InlineKeyboardButton(f"🎭 Artístico · {MODELO_ARTISTICO['custo']} créditos", callback_data="photo_model_artistico"),
            telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="photo_model_cancel")
        )
        bot.reply_to(message, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
    else:
        # Sem legenda — pedir explicitamente legenda primeiro
        # Reutiliza o estado/handler ja existente do Modelo Padrao
        user_states[user_id] = "awaiting_edit_prompt"
        ask_texts = {
            "pt": ("📸 <b>Foto recebida!</b>\n\n"
                   "✍️ Escreve <b>como queres editar a foto</b>\n"
                   "<i>Ex: \"remover o fundo\", \"transformar em anime\", \"melhorar qualidade\"...</i>\n\n"
                   f"🎨 <b>Ou clica em Padrão</b> para escolher entre <b>65+ estilos prontos</b> (Homens, Mulheres, Unissex, Flyers, Casais, Comics)\n"
                   "✨ <b>Ou clica em Pro</b> para melhoria fotorrealista automática"),
            "en": ("📸 <b>Photo received!</b>\n\n"
                   "✍️ Type <b>how you want to edit the photo</b>\n"
                   "<i>Ex: \"remove background\", \"make it anime\", \"enhance quality\"...</i>\n\n"
                   f"🎨 <b>Or tap Standard</b> to pick from <b>65+ ready styles</b> (Men, Women, Unisex, Flyers, Couples, Comics)\n"
                   "✨ <b>Or tap Pro</b> for automatic photorealistic enhancement"),
            "es": ("📸 <b>Foto recibida!</b>\n\n"
                   "✍️ Escribe <b>cómo quieres editar la foto</b>\n"
                   "<i>Ej: \"quitar fondo\", \"convertir en anime\", \"mejorar calidad\"...</i>\n\n"
                   f"🎨 <b>O toca Estándar</b> para elegir entre <b>65+ estilos listos</b> (Hombres, Mujeres, Unisex, Flyers, Parejas, Comics)\n"
                   "✨ <b>O toca Pro</b> para mejora fotorrealista automática")
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        padrao_label = {"pt": f"🎨 Padrão · 65+ estilos ({MODELO_PADRAO['custo']} cred)",
                        "en": f"🎨 Standard · 65+ styles ({MODELO_PADRAO['custo']} cred)",
                        "es": f"🎨 Estándar · 65+ estilos ({MODELO_PADRAO['custo']} cred)"}
        skip_label = {"pt": f"✨ Pro · sem descrição ({MODELO_PRO['custo']} cred)",
                      "en": f"✨ Pro · no description ({MODELO_PRO['custo']} cred)",
                      "es": f"✨ Pro · sin descripción ({MODELO_PRO['custo']} cred)"}
        artistico_label = {"pt": f"🎭 Artístico · 33 estilos ({MODELO_ARTISTICO['custo']} cred)",
                           "en": f"🎭 Artistic · 33 styles ({MODELO_ARTISTICO['custo']} cred)",
                           "es": f"🎭 Artístico · 33 estilos ({MODELO_ARTISTICO['custo']} cred)"}
        cancel_label = {"pt": "❌ Cancelar", "en": "❌ Cancel", "es": "❌ Cancelar"}
        markup.add(telebot.types.InlineKeyboardButton(padrao_label.get(lang, padrao_label["pt"]), callback_data="photo_model_padrao"))
        markup.add(telebot.types.InlineKeyboardButton(skip_label.get(lang, skip_label["pt"]), callback_data="photo_model_pro"))
        markup.add(telebot.types.InlineKeyboardButton(artistico_label.get(lang, artistico_label["pt"]), callback_data="photo_model_artistico"))
        markup.add(telebot.types.InlineKeyboardButton(cancel_label.get(lang, cancel_label["pt"]), callback_data="photo_model_cancel"))
        bot.reply_to(message, ask_texts.get(lang, ask_texts["pt"]), reply_markup=markup, parse_mode='HTML')

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
        # Modelo Pro combinar - mostrar submenu (Personalizar | Deixa mais realista)
        creditos = get_user_credits(user_id)
        if creditos < MODELO_PRO["custo"]:
            texts = {
                "pt": f"❌ Créditos insuficientes! Modelo Pro precisa de {MODELO_PRO['custo']} créditos.\n💳 Tens: {creditos}",
                "en": f"❌ Insufficient credits! Pro Model needs {MODELO_PRO['custo']} credits.\n💳 You have: {creditos}",
                "es": f"❌ Créditos insuficientes! Modelo Pro necesita {MODELO_PRO['custo']} créditos.\n💳 Tienes: {creditos}"
            }
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]))
            photo_collections.pop(user_id, None)
            return

        menu_texts = {
            "pt": f"✨ <b>Modelo Pro — Combinar fotos</b> ({MODELO_PRO['custo']} créd)\n\nEscolha como queres combinar:",
            "en": f"✨ <b>Pro Model — Combine photos</b> ({MODELO_PRO['custo']} cr)\n\nChoose how to combine:",
            "es": f"✨ <b>Modelo Pro — Combinar fotos</b> ({MODELO_PRO['custo']} créd)\n\nElige cómo combinar:"
        }
        btn_texts = {
            "pt": ("✏️ Personalizar", "📷 Deixa mais realista", "🎭 Estilo & Humor", "✨ Enhancements Avançados", "❌ Cancelar"),
            "en": ("✏️ Custom prompt", "📷 Make it more realistic", "🎭 Style & Mood", "✨ Advanced Enhancements", "❌ Cancel"),
            "es": ("✏️ Personalizar", "📷 Hazlo más realista", "🎭 Estilo y Humor", "✨ Enhancements Avanzados", "❌ Cancelar")
        }
        b1, b2, b3, b4, b5 = btn_texts.get(lang, btn_texts["pt"])
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(b1, callback_data="pro_m_custom"))
        markup.add(telebot.types.InlineKeyboardButton(b2, callback_data="pro_m_realista"))
        markup.add(telebot.types.InlineKeyboardButton(b3, callback_data="pro_m_styles"))
        markup.add(telebot.types.InlineKeyboardButton(b4, callback_data="pro_m_enh"))
        markup.add(telebot.types.InlineKeyboardButton(b5, callback_data="pro_m_cancel"))
        bot.send_message(call.message.chat.id, menu_texts.get(lang, menu_texts["pt"]), reply_markup=markup, parse_mode='HTML')
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

    # GATE NSFW (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=False)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        photo_collections.pop(user_id, None)
        return
    if reason == "shadowban":
        photo_collections.pop(user_id, None)
        return
    
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
        # Modelo Pro - mostrar submenu (Personalizar | Deixa mais realista)
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

        # Guardar foto de volta para proxima etapa
        pending_photos[user_id] = photo_data

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        menu_texts = {
            "pt": f"✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créd)\n\nEscolha como queres editar:",
            "en": f"✨ <b>Pro Model</b> ({MODELO_PRO['custo']} cr)\n\nChoose how to edit:",
            "es": f"✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créd)\n\nElige cómo editar:"
        }
        btn_texts = {
            "pt": ("✏️ Personalizar", "📷 Deixa mais realista", "🎭 Estilo & Humor", "✨ Enhancements Avançados", "❌ Cancelar"),
            "en": ("✏️ Custom prompt", "📷 Make it more realistic", "🎭 Style & Mood", "✨ Advanced Enhancements", "❌ Cancel"),
            "es": ("✏️ Personalizar", "📷 Hazlo más realista", "🎭 Estilo y Humor", "✨ Enhancements Avanzados", "❌ Cancelar")
        }
        b1, b2, b3, b4, b5 = btn_texts.get(lang, btn_texts["pt"])
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(b1, callback_data="pro_s_custom"))
        markup.add(telebot.types.InlineKeyboardButton(b2, callback_data="pro_s_realista"))
        markup.add(telebot.types.InlineKeyboardButton(b3, callback_data="pro_s_styles"))
        markup.add(telebot.types.InlineKeyboardButton(b4, callback_data="pro_s_enh"))
        markup.add(telebot.types.InlineKeyboardButton(b5, callback_data="pro_s_cancel"))
        bot.send_message(call.message.chat.id, menu_texts.get(lang, menu_texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return
    
    elif action == "padrao":
        # Modelo Padrao - 10 creditos
        caption_text = photo_data.get("caption", "")

        if caption_text and len(caption_text.strip()) >= 3:
            # COM legenda → processa direto, sem menu adicional
            if get_user_credits(user_id) < MODELO_PADRAO["custo"]:
                bot.answer_callback_query(call.id, "Créditos insuficientes!", show_alert=True)
                return
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            Thread(target=execute_padrao,
                   args=(call.message.chat.id, user_id, lang, photo_data, caption_text.strip(), None)).start()
            return

        # SEM legenda → mostra menu com presets rápidos + botão "🎨 Escolher Estilo"
        pending_photos[user_id] = photo_data
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        title_texts = {
            "pt": (f"🎨 <b>Modelo Padrão</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"Como queres editar a foto?\n\n"
                   f"• Toca num <b>preset rápido</b> abaixo\n"
                   f"• Ou clica em <b>🎨 Escolher Estilo</b> para 65+ estilos prontos\n"
                   f"• Ou escreve tu mesmo o prompt no chat"),
            "en": (f"🎨 <b>Standard Model</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"How do you want to edit the photo?\n\n"
                   f"• Tap a <b>quick preset</b> below\n"
                   f"• Or tap <b>🎨 Choose Style</b> for 65+ ready styles\n"
                   f"• Or just type your own prompt"),
            "es": (f"🎨 <b>Modelo Estándar</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"¿Cómo quieres editar la foto?\n\n"
                   f"• Toca un <b>preset rápido</b> abajo\n"
                   f"• O toca <b>🎨 Elegir Estilo</b> para 65+ estilos listos\n"
                   f"• O escribe tu propio prompt"),
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        # Botão de destaque "🎨 Escolher Estilo" no topo
        styles_label = {"pt": "🎨 Escolher Estilo (65+)", "en": "🎨 Choose Style (65+)", "es": "🎨 Elegir Estilo (65+)"}.get(lang, "🎨 Escolher Estilo (65+)")
        markup.add(telebot.types.InlineKeyboardButton(styles_label, callback_data="padflow_styles"))
        # Presets rápidos
        for key, preset in PRESETS_PADRAO.items():
            markup.add(telebot.types.InlineKeyboardButton(preset["nome"], callback_data=f"preset_{key}"))
        markup.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="preset_cancel"))
        bot.send_message(call.message.chat.id, title_texts.get(lang, title_texts["pt"]),
                         reply_markup=markup, parse_mode='HTML')
        user_states[user_id] = "awaiting_edit_prompt"
        return
    
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
        bot.send_message(call.message.chat.id, f"🎭 <b>Escolha o estilo:</b> ({MODELO_ARTISTICO['custo']} cred)", reply_markup=markup, parse_mode='HTML')



# ==================== MODELO PADRÃO — FLUXO COM ESCOLHER ESTILO ====================
def execute_padrao(chat_id, user_id, lang, photo_data, prompt_text, style_nome=None, style_key=None):
    """Executa edição com Modelo Padrão (Grok). Debita 10 cred, processa, refund em falha.
    style_key: chave do estilo aplicado (ex: 'u_joker') — usado para guardar preview ao publicar."""
    if not use_credit(user_id, MODELO_PADRAO["custo"]):
        bot.send_message(chat_id, "❌ Créditos insuficientes!")
        return

    proc_texts = {
        "pt": "🎨 Processando imagem...",
        "en": "🎨 Processing image...",
        "es": "🎨 Procesando imagen..."
    }
    proc_msg = bot.send_message(chat_id, proc_texts.get(lang, proc_texts["pt"]))

    try:
        file_info = bot.get_file(photo_data["file_id"])
        downloaded_file = bot.download_file(file_info.file_path)
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_base64}"

        style_settings = get_user_style_settings(user_id)
        aspect_ratio = ASPECT_RATIOS[style_settings["aspect_ratio"]]["ratio"]
        urls = gerar_imagem_modelo(prompt_text, aspect_ratio, image_input=image_data_url, num_outputs=1)

        try:
            bot.delete_message(chat_id, proc_msg.message_id)
        except Exception:
            pass

        style_line = f"\n🎯 Estilo: {style_nome}" if style_nome else ""
        for url in urls:
            img_data = requests.get(url, timeout=60).content
            creation_id = add_to_history(user_id, "edit", prompt_text, url)
            # Linka este creation_id ao estilo aplicado (para auto-coleta de preview na galeria)
            if style_key:
                link_creation_to_style(creation_id, style_key)
            creditos_restantes = get_user_credits(user_id)
            caption_texts = {
                "pt": f"✅ <b>Imagem editada!</b>\n🤖 Modelo: Padrão{style_line}\n💳 Créditos restantes: <code>{creditos_restantes}</code>",
                "en": f"✅ <b>Image edited!</b>\n🤖 Model: Standard{style_line}\n💳 Credits remaining: <code>{creditos_restantes}</code>",
                "es": f"✅ <b>Imagen editada!</b>\n🤖 Modelo: Estándar{style_line}\n💳 Créditos restantes: <code>{creditos_restantes}</code>"
            }
            bot.send_photo(chat_id, img_data, caption=caption_texts.get(lang, caption_texts["pt"]),
                           reply_markup=creation_actions_keyboard(creation_id, lang), parse_mode='HTML')

        update_user_stats(user_id, "total_edits")
        logger.info(f"Edicao Padrao user {user_id} (estilo={style_nome or 'direto'})")
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
            bot.edit_message_text(error_texts.get(lang, error_texts["pt"]), chat_id, proc_msg.message_id)
        except Exception:
            bot.send_message(chat_id, error_texts.get(lang, error_texts["pt"]))


def _padrao_categories_markup(lang):
    cat_texts = {
        "pt": [("👨 Para Homens", "padcat_men"), ("👩 Para Mulheres", "padcat_women"),
               ("👤 Unissex", "padcat_unisex"), ("📋 Flyers Recrutamento", "padcat_flyer"),
               ("💑 Casais (envia 2 fotos)", "padcat_couple"), ("📚 Comics / Histórias", "padcat_comic"),
               ("📱 Posts Instagram", "padcat_stories"), ("🔥 Sensual", "padcat_sensual"),
               ("⬅️ Voltar", "padflow_back")],
        "en": [("👨 For Men", "padcat_men"), ("👩 For Women", "padcat_women"),
               ("👤 Unisex", "padcat_unisex"), ("📋 Recruitment Flyers", "padcat_flyer"),
               ("💑 Couples (send 2 photos)", "padcat_couple"), ("📚 Comics / Stories", "padcat_comic"),
               ("📱 Instagram Posts", "padcat_stories"), ("🔥 Sensual", "padcat_sensual"),
               ("⬅️ Back", "padflow_back")],
        "es": [("👨 Para Hombres", "padcat_men"), ("👩 Para Mujeres", "padcat_women"),
               ("👤 Unisex", "padcat_unisex"), ("📋 Flyers Reclutamiento", "padcat_flyer"),
               ("💑 Parejas (envía 2 fotos)", "padcat_couple"), ("📚 Comics / Historias", "padcat_comic"),
               ("📱 Posts Instagram", "padcat_stories"), ("🔥 Sensual", "padcat_sensual"),
               ("⬅️ Volver", "padflow_back")],
    }
    items = cat_texts.get(lang, cat_texts["pt"])
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    for label, cb in items:
        mk.add(telebot.types.InlineKeyboardButton(label, callback_data=cb))
    return mk


def _padrao_styles_markup_for_cat(cat, lang, user_id=None):
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    if cat == "unisex":
        for grp_key, grp in PADRAO_UNISEX_GROUPS.items():
            mk.add(telebot.types.InlineKeyboardButton(grp["nome"], callback_data=f"padgrp_{grp_key}"))
    elif cat in ("couple", "comic"):
        for story_key, story in PADRAO_STORIES.items():
            if story["cat"] == cat:
                mk.add(telebot.types.InlineKeyboardButton(story["nome"], callback_data=f"padsto_{story_key}"))
    else:
        for key, st in PADRAO_STYLES.items():
            if st.get("cat") == cat:
                lock_prefix = "🔒 " if (user_id and is_locked_for_user(user_id, key)) else ""
                mk.add(telebot.types.InlineKeyboardButton(f"{lock_prefix}{st['nome']}", callback_data=f"padst_{key}"))
    back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
    mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data="padflow_styles"))
    return mk


@bot.callback_query_handler(func=lambda call: call.data.startswith("padflow_"))
def callback_padflow(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace("padflow_", "")

    if action == "cancel":
        pending_photos.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, {"pt": "❌ Cancelado.", "en": "❌ Cancelled.", "es": "❌ Cancelado."}.get(lang, "❌ Cancelado."))
        return

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada!")
        return

    photo_data = pending_photos[user_id]
    caption = (photo_data.get("caption") or "").strip()

    if action == "back":
        # Voltar ao menu Padrão (presets rápidos + Escolher Estilo)
        title_texts = {
            "pt": (f"🎨 <b>Modelo Padrão</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"Como queres editar a foto?\n\n"
                   f"• Toca num <b>preset rápido</b> abaixo\n"
                   f"• Ou clica em <b>🎨 Escolher Estilo</b> para 65+ estilos prontos\n"
                   f"• Ou escreve tu mesmo o prompt no chat"),
            "en": (f"🎨 <b>Standard Model</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"How do you want to edit the photo?\n\n"
                   f"• Tap a <b>quick preset</b> below\n"
                   f"• Or tap <b>🎨 Choose Style</b> for 65+ ready styles\n"
                   f"• Or just type your own prompt"),
            "es": (f"🎨 <b>Modelo Estándar</b> ({MODELO_PADRAO['custo']} cred)\n\n"
                   f"¿Cómo quieres editar la foto?\n\n"
                   f"• Toca un <b>preset rápido</b> abajo\n"
                   f"• O toca <b>🎨 Elegir Estilo</b> para 65+ estilos listos\n"
                   f"• O escribe tu propio prompt"),
        }
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        styles_label = {"pt": "🎨 Escolher Estilo (65+)", "en": "🎨 Choose Style (65+)", "es": "🎨 Elegir Estilo (65+)"}.get(lang, "🎨 Escolher Estilo (65+)")
        mk.add(telebot.types.InlineKeyboardButton(styles_label, callback_data="padflow_styles"))
        for key, preset in PRESETS_PADRAO.items():
            mk.add(telebot.types.InlineKeyboardButton(preset["nome"], callback_data=f"preset_{key}"))
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="preset_cancel"))
        try:
            bot.edit_message_text(title_texts.get(lang, title_texts["pt"]),
                                  call.message.chat.id, call.message.message_id,
                                  reply_markup=mk, parse_mode='HTML')
        except Exception:
            pass
        user_states[user_id] = "awaiting_edit_prompt"
        return

    if action == "direct":
        # (Legado) Continuar com descrição — mantido para back-compat se houver mensagens antigas
        photo_data = pending_photos.get(user_id)
        if not photo_data:
            return
        caption = (photo_data.get("caption") or "").strip()
        if not caption:
            bot.answer_callback_query(call.id, "Sem descrição para usar.")
            return
        if get_user_credits(user_id) < MODELO_PADRAO["custo"]:
            bot.answer_callback_query(call.id, "Créditos insuficientes!", show_alert=True)
            return
        pending_photos.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        Thread(target=execute_padrao,
               args=(call.message.chat.id, user_id, lang, photo_data, caption, None)).start()
        return

    if action == "styles":
        title = {
            "pt": "🎨 <b>Escolher Estilo</b>\n\nEscolhe a categoria:",
            "en": "🎨 <b>Choose Style</b>\n\nPick a category:",
            "es": "🎨 <b>Elegir Estilo</b>\n\nElige la categoría:",
        }
        try:
            bot.edit_message_text(title.get(lang, title["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=_padrao_categories_markup(lang), parse_mode='HTML')
        except Exception:
            bot.send_message(call.message.chat.id, title.get(lang, title["pt"]),
                             reply_markup=_padrao_categories_markup(lang), parse_mode='HTML')
        return


@bot.callback_query_handler(func=lambda call: call.data.startswith("padcat_"))
def callback_padcat(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    cat = call.data.replace("padcat_", "")

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada!")
        return

    if cat == "couple":
        warn = {
            "pt": "💑 <b>Casais</b>\n\n💡 Para o melhor resultado, envia <b>2 fotos juntas</b> (tu + a outra pessoa) ou <b>1 foto dos dois</b>. Caso contrário a imagem pode sair incompleta.\n\nEscolhe a história:",
            "en": "💑 <b>Couples</b>\n\n💡 For the best result, send <b>2 photos together</b> (you + the other person) or <b>1 photo of both</b>. Otherwise the image may come out incomplete.\n\nPick the story:",
            "es": "💑 <b>Parejas</b>\n\n💡 Para el mejor resultado, envía <b>2 fotos juntas</b> (tú + la otra persona) o <b>1 foto de ambos</b>. De lo contrario la imagen puede salir incompleta.\n\nElige la historia:",
        }
        title = warn.get(lang, warn["pt"])
    else:
        titles = {
            "men":     {"pt": "👨 <b>Para Homens</b>\n\nEscolhe o estilo:", "en": "👨 <b>For Men</b>\n\nPick a style:", "es": "👨 <b>Para Hombres</b>\n\nElige el estilo:"},
            "women":   {"pt": "👩 <b>Para Mulheres</b>\n\nEscolhe o estilo:", "en": "👩 <b>For Women</b>\n\nPick a style:", "es": "👩 <b>Para Mujeres</b>\n\nElige el estilo:"},
            "unisex":  {"pt": "👤 <b>Unissex</b>\n\nEscolhe o tema:", "en": "👤 <b>Unisex</b>\n\nPick a theme:", "es": "👤 <b>Unisex</b>\n\nElige el tema:"},
            "flyer":   {"pt": "📋 <b>Flyers Recrutamento</b>\n\nEscolhe o flyer:", "en": "📋 <b>Recruitment Flyers</b>\n\nPick the flyer:", "es": "📋 <b>Flyers Reclutamiento</b>\n\nElige el flyer:"},
            "comic":   {"pt": "📚 <b>Comics / Histórias</b>\n\nEscolhe a história:", "en": "📚 <b>Comics / Stories</b>\n\nPick the story:", "es": "📚 <b>Comics / Historias</b>\n\nElige la historia:"},
            "stories": {"pt": "📱 <b>Posts Instagram</b>\n\nEscolhe o post:", "en": "📱 <b>Instagram Posts</b>\n\nPick the post:", "es": "📱 <b>Posts Instagram</b>\n\nElige el post:"},
            "sensual": {"pt": "🔥 <b>Sensual</b>\n\n2 estilos grátis · resto trancado 🔒\n💎 Faz qualquer compra para desbloqueares todos.", "en": "🔥 <b>Sensual</b>\n\n2 free styles · rest locked 🔒\n💎 Make any purchase to unlock all.", "es": "🔥 <b>Sensual</b>\n\n2 estilos gratis · resto bloqueado 🔒\n💎 Haz cualquier compra para desbloquear."},
        }
        title = titles.get(cat, titles["men"]).get(lang, titles.get(cat, titles["men"])["pt"])

    try:
        bot.edit_message_text(title, call.message.chat.id, call.message.message_id,
                              reply_markup=_padrao_styles_markup_for_cat(cat, lang, user_id), parse_mode='HTML')
    except Exception:
        bot.send_message(call.message.chat.id, title,
                         reply_markup=_padrao_styles_markup_for_cat(cat, lang, user_id), parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith("padgrp_"))
def callback_padgrp(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    grp_key = call.data.replace("padgrp_", "")

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada!")
        return

    grp = PADRAO_UNISEX_GROUPS.get(grp_key)
    if not grp:
        bot.answer_callback_query(call.id, "Grupo inválido.")
        return

    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, st in PADRAO_STYLES.items():
        if st.get("cat") == "unisex" and st.get("grp") == grp_key:
            lock_prefix = "🔒 " if is_locked_for_user(user_id, key) else ""
            mk.add(telebot.types.InlineKeyboardButton(f"{lock_prefix}{st['nome']}", callback_data=f"padst_{key}"))
    back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
    mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data="padcat_unisex"))

    title = f"{grp['nome']}\n\n" + {"pt": "Escolhe o estilo:", "en": "Pick a style:", "es": "Elige el estilo:"}.get(lang, "Escolhe o estilo:")
    try:
        bot.edit_message_text(title, call.message.chat.id, call.message.message_id,
                              reply_markup=mk, parse_mode='HTML')
    except Exception:
        bot.send_message(call.message.chat.id, title, reply_markup=mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith("padsto_"))
def callback_padsto(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    story_key = call.data.replace("padsto_", "")

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada!")
        return

    story = PADRAO_STORIES.get(story_key)
    if not story:
        bot.answer_callback_query(call.id, "História inválida.")
        return

    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    for sk in story["scenes"]:
        st = PADRAO_STYLES.get(sk)
        if st:
            lock_prefix = "🔒 " if is_locked_for_user(user_id, sk) else ""
            mk.add(telebot.types.InlineKeyboardButton(f"{lock_prefix}{st['nome']}", callback_data=f"padst_{sk}"))
    back_label = {"pt": "⬅️ Voltar", "en": "⬅️ Back", "es": "⬅️ Volver"}.get(lang, "⬅️ Voltar")
    mk.add(telebot.types.InlineKeyboardButton(back_label, callback_data=f"padcat_{story['cat']}"))

    cost_note = {
        "pt": f"\n\n💳 Cada cena custa {MODELO_PADRAO['custo']} créditos (gera 1 imagem por clique).",
        "en": f"\n\n💳 Each scene costs {MODELO_PADRAO['custo']} credits (generates 1 image per click).",
        "es": f"\n\n💳 Cada escena cuesta {MODELO_PADRAO['custo']} créditos (genera 1 imagen por clic).",
    }
    title = f"{story['nome']}\n\n" + {"pt": "Escolhe a cena:", "en": "Pick the scene:", "es": "Elige la escena:"}.get(lang, "Escolhe a cena:") + cost_note.get(lang, cost_note["pt"])
    try:
        bot.edit_message_text(title, call.message.chat.id, call.message.message_id,
                              reply_markup=mk, parse_mode='HTML')
    except Exception:
        bot.send_message(call.message.chat.id, title, reply_markup=mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith("padst_"))
def callback_padst(call):
    """Aplica um estilo escolhido: combina prompt fixo + descrição user e gera com Modelo Padrão."""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    style_key = call.data.replace("padst_", "")

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada!")
        return

    style = PADRAO_STYLES.get(style_key)
    if not style:
        bot.answer_callback_query(call.id, "Estilo inválido.")
        return

    # 🔒 Bloqueio: estilo trancado e user sem premium
    if is_locked_for_user(user_id, style_key):
        paywall = {
            "pt": ("🔒 <b>Estilo Premium</b>\n\n"
                   "Este estilo está trancado.\n\n"
                   "✨ <b>Como desbloquear:</b>\n"
                   f"Faz qualquer compra de créditos (qualquer pacote) e desbloqueias automaticamente <b>todos os {sum(1 for k,v in PADRAO_STYLES.items() if v.get('locked'))}+ estilos trancados</b>, incluindo a categoria 🔥 Sensual.\n\n"
                   "🎁 <b>Bónus:</b> 30 dias de acesso a novos estilos exclusivos lançados depois.\n\n"
                   "👉 Clica em /comprar ou no menu 💰 Comprar Créditos."),
            "en": ("🔒 <b>Premium Style</b>\n\n"
                   "This style is locked.\n\n"
                   "✨ <b>How to unlock:</b>\n"
                   "Make any credit purchase (any pack) and you'll automatically unlock <b>all locked styles</b>, including 🔥 Sensual category.\n\n"
                   "🎁 <b>Bonus:</b> 30 days of access to new exclusive styles released after.\n\n"
                   "👉 Tap /comprar or 💰 Buy Credits."),
            "es": ("🔒 <b>Estilo Premium</b>\n\n"
                   "Este estilo está bloqueado.\n\n"
                   "✨ Haz cualquier compra de créditos y desbloqueas <b>todos los estilos bloqueados</b>, incluyendo 🔥 Sensual.\n\n"
                   "🎁 <b>Bono:</b> 30 días de acceso a estilos nuevos exclusivos.\n\n"
                   "👉 /comprar"),
        }
        try:
            bot.answer_callback_query(call.id, "🔒 Estilo Premium — faz uma compra para desbloquear.", show_alert=False)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, paywall.get(lang, paywall["pt"]), parse_mode='HTML')
        return

    if get_user_credits(user_id) < MODELO_PADRAO["custo"]:
        bot.answer_callback_query(call.id, "Créditos insuficientes!", show_alert=True)
        return

    photo_data = pending_photos.pop(user_id)
    caption = (photo_data.get("caption") or "").strip()

    allowed, reason, extra = check_user_allowed(user_id, prompt=caption, check_rate=False)
    if not allowed:
        bot.answer_callback_query(call.id, "Não permitido.", show_alert=True)
        return

    final_prompt = build_padrao_final_prompt(style_key, caption)
    if not final_prompt:
        bot.answer_callback_query(call.id, "Erro a montar o prompt.")
        return

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    Thread(target=execute_padrao,
           args=(call.message.chat.id, user_id, lang, photo_data, final_prompt, style["nome"], style_key)).start()




# ==================== MODELO PRO — SUBMENU (FOTO UNICA) ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('pro_s_'))
def callback_pro_single(call):
    """Handler do submenu do Modelo Pro para foto unica"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('pro_s_', '')

    if action == "cancel":
        pending_photos.pop(user_id, None)
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        cancel_texts = {"pt": "❌ Cancelado.", "en": "❌ Cancelled.", "es": "❌ Cancelado."}
        bot.send_message(call.message.chat.id, cancel_texts.get(lang, cancel_texts["pt"]))
        return

    if user_id not in pending_photos:
        bot.answer_callback_query(call.id, "Foto expirada! Envie novamente.")
        return

    if action == "custom":
        # Pedir prompt customizado ao usuario
        bot.answer_callback_query(call.id, "Escreva o que deseja!")
        user_states[user_id] = "awaiting_pro_s_prompt"
        texts = {
            "pt": "✍️ <b>Modelo Pro — Personalizar</b>\n\nEscreve o que queres fazer na imagem (ex: <i>remove o fundo, adiciona oculos, muda cor do cabelo</i>):",
            "en": "✍️ <b>Pro Model — Custom</b>\n\nWrite what you want to do to the image (e.g., <i>remove background, add glasses, change hair color</i>):",
            "es": "✍️ <b>Modelo Pro — Personalizar</b>\n\nEscribe lo que quieres hacer en la imagen (ej: <i>quita el fondo, añade gafas, cambia color del pelo</i>):"
        }
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), parse_mode='HTML')
        return

    if action == "realista":
        # Mostrar submenu com presets de realismo (3 originais + 4 novos)
        texts = {
            "pt": "📷 <b>Escolhe o tipo de realismo:</b>",
            "en": "📷 <b>Choose the realism type:</b>",
            "es": "📷 <b>Elige el tipo de realismo:</b>"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["original"]["nome"], callback_data="pro_s_p_original"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["expression"]["nome"], callback_data="pro_s_p_expression"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["softer"]["nome"], callback_data="pro_s_p_softer"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["cinematic"]["nome"], callback_data="pro_s_r_cinematic"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["ultra_real"]["nome"], callback_data="pro_s_r_ultra_real"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["iphone"]["nome"], callback_data="pro_s_r_iphone"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["studio"]["nome"], callback_data="pro_s_r_studio"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_s_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "styles":
        # Submenu Estilo & Humor
        texts = {
            "pt": "🎭 <b>Estilo & Humor</b>\n\nEscolhe a vibe:",
            "en": "🎭 <b>Style & Mood</b>\n\nPick the vibe:",
            "es": "🎭 <b>Estilo y Humor</b>\n\nElige la vibe:"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for k, item in PRO_STYLE_MOOD.items():
            markup.add(telebot.types.InlineKeyboardButton(item["nome"], callback_data=f"pro_s_st_{k}"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_s_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "enh":
        # Submenu Enhancements Avançados
        texts = {
            "pt": "✨ <b>Enhancements Avançados</b>\n\nEscolhe o tipo de melhoria:",
            "en": "✨ <b>Advanced Enhancements</b>\n\nPick the enhancement:",
            "es": "✨ <b>Enhancements Avanzados</b>\n\nElige la mejora:"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for k, item in PRO_ENHANCEMENTS.items():
            markup.add(telebot.types.InlineKeyboardButton(item["nome"], callback_data=f"pro_s_en_{k}"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_s_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "back":
        # Voltar para o menu Pro principal
        menu_texts = {
            "pt": f"✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créd)\n\nEscolha como queres editar:",
            "en": f"✨ <b>Pro Model</b> ({MODELO_PRO['custo']} cr)\n\nChoose how to edit:",
            "es": f"✨ <b>Modelo Pro</b> ({MODELO_PRO['custo']} créd)\n\nElige cómo editar:"
        }
        btn_texts = {
            "pt": ("✏️ Personalizar", "📷 Deixa mais realista", "🎭 Estilo & Humor", "✨ Enhancements Avançados", "❌ Cancelar"),
            "en": ("✏️ Custom prompt", "📷 Make it more realistic", "🎭 Style & Mood", "✨ Advanced Enhancements", "❌ Cancel"),
            "es": ("✏️ Personalizar", "📷 Hazlo más realista", "🎭 Estilo y Humor", "✨ Enhancements Avanzados", "❌ Cancelar")
        }
        b1, b2, b3, b4, b5 = btn_texts.get(lang, btn_texts["pt"])
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(b1, callback_data="pro_s_custom"))
        markup.add(telebot.types.InlineKeyboardButton(b2, callback_data="pro_s_realista"))
        markup.add(telebot.types.InlineKeyboardButton(b3, callback_data="pro_s_styles"))
        markup.add(telebot.types.InlineKeyboardButton(b4, callback_data="pro_s_enh"))
        markup.add(telebot.types.InlineKeyboardButton(b5, callback_data="pro_s_cancel"))
        try:
            bot.edit_message_text(menu_texts.get(lang, menu_texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            pass
        return

    if action.startswith("r_") or action.startswith("st_") or action.startswith("en_"):
        # Preset extra: realismo / estilo & humor / enhancements
        if action.startswith("r_"):
            preset_key = action[2:]
            preset = PRO_REALISM_EXTRA.get(preset_key)
        elif action.startswith("st_"):
            preset_key = action[3:]
            preset = PRO_STYLE_MOOD.get(preset_key)
        else:  # en_
            preset_key = action[3:]
            preset = PRO_ENHANCEMENTS.get(preset_key)

        if not preset:
            bot.answer_callback_query(call.id, "Preset invalido.")
            return

        photo_data = pending_photos.pop(user_id)
        user_states.pop(user_id, None)

        # Combina prompt fixo com a descrição do usuário (se houver)
        caption = (photo_data.get("caption") or "").strip()
        if caption:
            final_prompt = f"{preset['prompt']} Additional user request: {caption}"
        else:
            final_prompt = preset["prompt"]

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        Thread(target=execute_pro_single,
               args=(call.message.chat.id, user_id, lang, photo_data, final_prompt, preset["nome"])).start()
        return

    if action.startswith("p_"):
        # Preset de realismo escolhido
        preset_key = action.replace("p_", "")
        preset = PRO_PRESETS.get(preset_key)
        if not preset:
            bot.answer_callback_query(call.id, "Preset invalido.")
            return

        photo_data = pending_photos.pop(user_id)
        user_states.pop(user_id, None)

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        Thread(target=execute_pro_single,
               args=(call.message.chat.id, user_id, lang, photo_data, preset["prompt"], preset["nome"])).start()
        return


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_pro_s_prompt')
def handle_pro_single_custom_prompt(message):
    """Recebe o prompt custom para Modelo Pro em foto unica"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)

    if user_id not in pending_photos:
        bot.reply_to(message, "❌ Foto expirada! Envia novamente.")
        return

    prompt = (message.text or "").strip()
    is_valid, error = validate_prompt(prompt)
    if not is_valid:
        bot.reply_to(message, f"❌ {error}")
        pending_photos.pop(user_id, None)
        return

    # GATE NSFW (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=False)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        pending_photos.pop(user_id, None)
        return
    if reason == "shadowban":
        pending_photos.pop(user_id, None)
        return

    photo_data = pending_photos.pop(user_id)
    Thread(target=execute_pro_single,
           args=(message.chat.id, user_id, lang, photo_data, prompt, None)).start()


# ==================== MODELO PRO — SUBMENU (COMBINAR FOTOS) ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('pro_m_'))
def callback_pro_multi(call):
    """Handler do submenu do Modelo Pro para combinar varias fotos"""
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    action = call.data.replace('pro_m_', '')

    if action == "cancel":
        photo_collections.pop(user_id, None)
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        cancel_texts = {"pt": "❌ Cancelado.", "en": "❌ Cancelled.", "es": "❌ Cancelado."}
        bot.send_message(call.message.chat.id, cancel_texts.get(lang, cancel_texts["pt"]))
        return

    if user_id not in photo_collections:
        bot.answer_callback_query(call.id, "Fotos expiradas! Envia novamente.")
        return

    if action == "custom":
        bot.answer_callback_query(call.id, "Escreve o que queres!")
        user_states[user_id] = "awaiting_pro_m_prompt"
        texts = {
            "pt": "✍️ <b>Modelo Pro — Combinar (Personalizar)</b>\n\nEscreve o que queres fazer com as fotos (ex: <i>coloca todos numa praia ao por do sol</i>):",
            "en": "✍️ <b>Pro Model — Combine (Custom)</b>\n\nWrite what you want to do with the photos (e.g., <i>put everyone on a beach at sunset</i>):",
            "es": "✍️ <b>Modelo Pro — Combinar (Personalizar)</b>\n\nEscribe lo que quieres hacer con las fotos (ej: <i>ponlos a todos en una playa al atardecer</i>):"
        }
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), parse_mode='HTML')
        return

    if action == "realista":
        texts = {
            "pt": "📷 <b>Escolhe o tipo de realismo:</b>",
            "en": "📷 <b>Choose the realism type:</b>",
            "es": "📷 <b>Elige el tipo de realismo:</b>"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["original"]["nome"], callback_data="pro_m_p_original"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["expression"]["nome"], callback_data="pro_m_p_expression"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_PRESETS["softer"]["nome"], callback_data="pro_m_p_softer"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["cinematic"]["nome"], callback_data="pro_m_r_cinematic"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["ultra_real"]["nome"], callback_data="pro_m_r_ultra_real"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["iphone"]["nome"], callback_data="pro_m_r_iphone"))
        markup.add(telebot.types.InlineKeyboardButton(PRO_REALISM_EXTRA["studio"]["nome"], callback_data="pro_m_r_studio"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_m_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "styles":
        texts = {
            "pt": "🎭 <b>Estilo & Humor</b>\n\nEscolhe a vibe:",
            "en": "🎭 <b>Style & Mood</b>\n\nPick the vibe:",
            "es": "🎭 <b>Estilo y Humor</b>\n\nElige la vibe:"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for k, item in PRO_STYLE_MOOD.items():
            markup.add(telebot.types.InlineKeyboardButton(item["nome"], callback_data=f"pro_m_st_{k}"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_m_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "enh":
        texts = {
            "pt": "✨ <b>Enhancements Avançados</b>\n\nEscolhe o tipo de melhoria:",
            "en": "✨ <b>Advanced Enhancements</b>\n\nPick the enhancement:",
            "es": "✨ <b>Enhancements Avanzados</b>\n\nElige la mejora:"
        }
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        for k, item in PRO_ENHANCEMENTS.items():
            markup.add(telebot.types.InlineKeyboardButton(item["nome"], callback_data=f"pro_m_en_{k}"))
        back_label = "⬅️ Voltar" if lang == "pt" else ("⬅️ Back" if lang == "en" else "⬅️ Volver")
        markup.add(telebot.types.InlineKeyboardButton(back_label, callback_data="pro_m_back"))
        try:
            bot.edit_message_text(texts.get(lang, texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, texts.get(lang, texts["pt"]), reply_markup=markup, parse_mode='HTML')
        return

    if action == "back":
        menu_texts = {
            "pt": f"✨ <b>Modelo Pro — Combinar fotos</b> ({MODELO_PRO['custo']} créd)\n\nEscolha como queres combinar:",
            "en": f"✨ <b>Pro Model — Combine photos</b> ({MODELO_PRO['custo']} cr)\n\nChoose how to combine:",
            "es": f"✨ <b>Modelo Pro — Combinar fotos</b> ({MODELO_PRO['custo']} créd)\n\nElige cómo combinar:"
        }
        btn_texts = {
            "pt": ("✏️ Personalizar", "📷 Deixa mais realista", "🎭 Estilo & Humor", "✨ Enhancements Avançados", "❌ Cancelar"),
            "en": ("✏️ Custom prompt", "📷 Make it more realistic", "🎭 Style & Mood", "✨ Advanced Enhancements", "❌ Cancel"),
            "es": ("✏️ Personalizar", "📷 Hazlo más realista", "🎭 Estilo y Humor", "✨ Enhancements Avanzados", "❌ Cancelar")
        }
        b1, b2, b3, b4, b5 = btn_texts.get(lang, btn_texts["pt"])
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        markup.add(telebot.types.InlineKeyboardButton(b1, callback_data="pro_m_custom"))
        markup.add(telebot.types.InlineKeyboardButton(b2, callback_data="pro_m_realista"))
        markup.add(telebot.types.InlineKeyboardButton(b3, callback_data="pro_m_styles"))
        markup.add(telebot.types.InlineKeyboardButton(b4, callback_data="pro_m_enh"))
        markup.add(telebot.types.InlineKeyboardButton(b5, callback_data="pro_m_cancel"))
        try:
            bot.edit_message_text(menu_texts.get(lang, menu_texts["pt"]), call.message.chat.id, call.message.message_id,
                                  reply_markup=markup, parse_mode='HTML')
        except:
            pass
        return

    if action.startswith("r_") or action.startswith("st_") or action.startswith("en_"):
        # Preset extra: realismo / estilo & humor / enhancements (combinar fotos)
        if action.startswith("r_"):
            preset_key = action[2:]
            preset = PRO_REALISM_EXTRA.get(preset_key)
        elif action.startswith("st_"):
            preset_key = action[3:]
            preset = PRO_STYLE_MOOD.get(preset_key)
        else:  # en_
            preset_key = action[3:]
            preset = PRO_ENHANCEMENTS.get(preset_key)

        if not preset:
            bot.answer_callback_query(call.id, "Preset invalido.")
            return

        caption = photo_collections[user_id].get("caption", "")
        user_states.pop(user_id, None)

        # Combina prompt fixo com a descrição do usuário (se houver)
        if caption:
            final_prompt = f"{preset['prompt']} Additional user request: {caption}"
        else:
            final_prompt = preset["prompt"]

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        Thread(target=execute_combine_pro,
               args=(user_id, lang, caption, final_prompt)).start()
        return

    if action.startswith("p_"):
        preset_key = action.replace("p_", "")
        preset = PRO_PRESETS.get(preset_key)
        if not preset:
            bot.answer_callback_query(call.id, "Preset invalido.")
            return

        caption = photo_collections[user_id].get("caption", "")
        user_states.pop(user_id, None)

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

        Thread(target=execute_combine_pro,
               args=(user_id, lang, caption, preset["prompt"])).start()
        return


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_pro_m_prompt')
def handle_pro_multi_custom_prompt(message):
    """Recebe prompt custom para Modelo Pro combinar varias fotos"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)

    if user_id not in photo_collections:
        bot.reply_to(message, "❌ Fotos expiradas! Envia novamente.")
        return

    prompt = (message.text or "").strip()
    is_valid, error = validate_prompt(prompt)
    if not is_valid:
        bot.reply_to(message, f"❌ {error}")
        photo_collections.pop(user_id, None)
        return

    # GATE NSFW (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=False)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        photo_collections.pop(user_id, None)
        return
    if reason == "shadowban":
        photo_collections.pop(user_id, None)
        return

    caption = photo_collections[user_id].get("caption", "")
    Thread(target=execute_combine_pro,
           args=(user_id, lang, caption, prompt)).start()


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

    # GATE NSFW (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=prompt, check_rate=False)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        return
    if reason == "shadowban":
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

# ==================== VIDEO PUBLICO ====================
VIDEO_CUSTO = 20

@bot.message_handler(commands=['video'])
def cmd_video(message):
    """Geracao de video - publico, custa VIDEO_CUSTO creditos"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)

    # Gate de seguranca (admin ignora)
    allowed, reason, extra = check_user_allowed(user_id, prompt=None, check_rate=False)
    if not allowed:
        bot.reply_to(message, deny_message(lang, reason, extra), parse_mode='HTML')
        return

    creditos = get_user_credits(user_id)
    if not is_any_admin(user_id) and creditos < VIDEO_CUSTO:
        bot.reply_to(message, f"❌ Créditos insuficientes! Vídeo custa <b>{VIDEO_CUSTO}</b> créditos.\n💳 Tens: <code>{creditos}</code>", parse_mode='HTML')
        return

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("✍️ Texto → Vídeo", callback_data="video_text"),
        telebot.types.InlineKeyboardButton("📸 Imagem → Vídeo", callback_data="video_image"),
        telebot.types.InlineKeyboardButton("❌ Cancelar", callback_data="video_cancel")
    )
    bot.send_message(
        message.chat.id,
        f"🎬 <b>Geração de Vídeo</b>\n\n💰 Custo: <b>{VIDEO_CUSTO} créditos</b> por vídeo (~6s)\n💳 Teus créditos: <code>{creditos}</code>\n\nEscolhe o modo:",
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('video_'))
def callback_video(call):
    user_id = call.from_user.id
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
        bot.send_message(call.message.chat.id, "🎬 Escreve a descrição do vídeo que queres gerar:")

    elif action == "image":
        user_states[user_id] = "awaiting_video_image"
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, "🎬 Envia a imagem que queres transformar em vídeo (com legenda opcional descrevendo o movimento):")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_video_prompt')
def handle_video_prompt(message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    user_states.pop(user_id, None)
    prompt = message.text.strip()

    if len(prompt) < 5:
        bot.reply_to(message, "❌ Descrição muito curta. Tenta novamente com /video.")
        return

    creditos = get_user_credits(user_id)
    if not is_any_admin(user_id):
        if creditos < VIDEO_CUSTO:
            bot.reply_to(message, f"❌ Créditos insuficientes! Vídeo custa <b>{VIDEO_CUSTO}</b>.", parse_mode='HTML')
            return
        if not use_credit(user_id, VIDEO_CUSTO):
            bot.reply_to(message, "❌ Erro ao debitar créditos.")
            return

    proc_msg = bot.reply_to(message, f"🎬 A gerar vídeo... isto pode demorar 30-60 segundos.\n💰 Custo: {VIDEO_CUSTO} créd")
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
        creditos_restantes = get_user_credits(user_id)
        bot.send_video(message.chat.id, video_data,
                       caption=f"🎬 <b>Vídeo gerado!</b>\n💬 <i>{prompt[:120]}</i>\n💳 Restam: <code>{creditos_restantes}</code> créd",
                       parse_mode='HTML')
    except Exception as e:
        if not is_any_admin(user_id):
            add_credits(user_id, VIDEO_CUSTO, "reembolso_video")
        bot.edit_message_text(f"❌ Erro ao gerar vídeo. Créditos reembolsados.\n<code>{str(e)[:160]}</code>", message.chat.id, proc_msg.message_id, parse_mode='HTML')
        logger.error(f"Erro video: {e}")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'awaiting_video_image', content_types=['photo'])
def handle_video_image(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)

    creditos = get_user_credits(user_id)
    if not is_any_admin(user_id):
        if creditos < VIDEO_CUSTO:
            bot.reply_to(message, f"❌ Créditos insuficientes! Vídeo custa <b>{VIDEO_CUSTO}</b>.", parse_mode='HTML')
            return
        if not use_credit(user_id, VIDEO_CUSTO):
            bot.reply_to(message, "❌ Erro ao debitar créditos.")
            return

    proc_msg = bot.reply_to(message, f"🎬 A transformar imagem em vídeo... 30-60 segundos.\n💰 Custo: {VIDEO_CUSTO} créd")
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
        creditos_restantes = get_user_credits(user_id)
        bot.send_video(message.chat.id, video_data,
                       caption=f"🎬 <b>Imagem animada!</b>\n💳 Restam: <code>{creditos_restantes}</code> créd",
                       parse_mode='HTML')
    except Exception as e:
        if not is_any_admin(user_id):
            add_credits(user_id, VIDEO_CUSTO, "reembolso_video")
        bot.edit_message_text(f"❌ Erro ao gerar vídeo. Créditos reembolsados.\n<code>{str(e)[:160]}</code>", message.chat.id, proc_msg.message_id, parse_mode='HTML')
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

def _legacy_detect_image_intent_DISABLED(text):
    """DEPRECATED — substituido pela versao conservadora em cima."""
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
    
    # DETECTAR INTENÇÃO DE GERAÇÃO DE IMAGEM (AI-powered)
    # Primeiro filtro: keyword conservadora (evita false positives)
    if detect_image_intent(text):
        # Pedido DIRETO e explicito detectado. Confirma via AI se deve gerar ja
        intent_result = classify_user_intent_ai(text, lang)
        if intent_result.get("intent") == "generate" and intent_result.get("ready_to_generate"):
            prompt = intent_result.get("clean_prompt") or text
            creditos = get_user_credits(user_id)
            if creditos < 1:
                texts = {"pt": "❌ Créditos insuficientes! Use /start para comprar.",
                         "en": "❌ Insufficient credits! Use /start to buy.",
                         "es": "❌ ¡Créditos insuficientes! Usa /start para comprar."}
                bot.reply_to(message, texts.get(lang, texts["pt"]))
                return
            if not use_credit(user_id, 1):
                return
            processar_criacao(message.chat.id, user_id, prompt, lang)
            return
        # Se AI diz que nao esta pronto, cai para chat (pede mais detalhes)

    # CHAT NORMAL (IA responde de forma inteligente, pede fotos/ideias quando preciso)
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
    # ====================================================================
    # RENDER-SAFE STARTUP SEQUENCE
    # 1º Flask arranca IMEDIATAMENTE (abre $PORT -> Render não mata o processo)
    # 2º Resto da init acontece com try/except individuais (não bloqueia)
    # 3º Polling em loop infinito com reconnect
    # Wrap global apanha qualquer exceção para log visível no Render
    # ====================================================================
    try:
        # ---------- [1/6] FLASK PRIMEIRO (port binding imediato) ----------
        port = int(os.getenv("PORT", 10000))
        print(f"[BOOT 1/6] 🌐 A iniciar Flask na porta {port}...", flush=True)
        Thread(
            target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False),
            daemon=True,
            name="FlaskThread"
        ).start()
        time.sleep(1)  # dar tempo ao Flask para bind
        print(f"[BOOT 1/6] ✅ Flask a escutar em 0.0.0.0:{port}", flush=True)

        # ---------- [2/6] HEADERS / INFO ----------
        print("=" * 60, flush=True)
        print("✨ Remake Pixel Bot - VERSÃO SUPREMA 👑", flush=True)
        print("=" * 60, flush=True)
        print(f"📞 Suporte: {SUPORTE_TELEGRAM}", flush=True)
        print(f"🤖 Bot: @{BOT_USERNAME}", flush=True)
        print("=" * 60, flush=True)

        # ---------- [3/6] REMOVER WEBHOOK ANTIGO (anti-409) ----------
        print("[BOOT 2/6] 🔌 A remover webhook antigo (anti-409)...", flush=True)
        try:
            bot.remove_webhook()
            time.sleep(1)
            print("[BOOT 2/6] ✅ Webhook removido", flush=True)
        except Exception as e:
            print(f"[BOOT 2/6] ⚠️ remove_webhook falhou (continuo): {e}", flush=True)

        # ---------- [4/6] CRÉDITOS ADMIN (não-bloqueante) ----------
        print("[BOOT 3/6] 👑 A garantir créditos de admin...", flush=True)
        try:
            for admin_id in ADMIN_IDS:
                if get_user_credits(admin_id) < 50:
                    add_credits(admin_id, 50, "admin")
            print("[BOOT 3/6] ✅ Créditos admin OK", flush=True)
        except Exception as e:
            print(f"[BOOT 3/6] ⚠️ Créditos admin falhou (continuo): {e}", flush=True)

        # ---------- [5/6] MENU NATIVO TELEGRAM (não-bloqueante) ----------
        print("[BOOT 4/6] 🔧 A configurar menu nativo do Telegram...", flush=True)
        try:
            user_commands = [
                telebot.types.BotCommand("menu", "📋 Menu"),
                telebot.types.BotCommand("start", "🔄 Reiniciar"),
                telebot.types.BotCommand("wizard", "🧙 Assistente de Criação"),
                telebot.types.BotCommand("creditos", "💳 Ver Créditos"),
                telebot.types.BotCommand("idioma", "🌐 Mudar Idioma"),
                telebot.types.BotCommand("help", "❓ Ajuda")
            ]
            bot.set_my_commands(user_commands, scope=telebot.types.BotCommandScopeDefault())
            print("[BOOT 4/6] ✅ Menu padrão configurado", flush=True)

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
                try:
                    bot.set_my_commands(
                        admin_commands,
                        scope=telebot.types.BotCommandScopeChat(chat_id=admin_id)
                    )
                except Exception as ea:
                    print(f"[BOOT 4/6] ⚠️ Menu admin {admin_id} falhou: {ea}", flush=True)
            print("[BOOT 4/6] ✅ Menu admin configurado", flush=True)
        except Exception as e:
            print(f"[BOOT 4/6] ⚠️ set_my_commands falhou (continuo): {e}", flush=True)

        # ---------- [6/6] BACKUP MANAGER (não-bloqueante) ----------
        print("[BOOT 5/6] 💾 A iniciar backup manager...", flush=True)
        try:
            backup_manager.start()
            print("[BOOT 5/6] ✅ Backup manager OK", flush=True)
        except Exception as e:
            print(f"[BOOT 5/6] ⚠️ Backup manager falhou (continuo): {e}", flush=True)

        # ---------- ONLINE ----------
        print("=" * 60, flush=True)
        print("🤖 Remake Pixel ONLINE", flush=True)
        print("=" * 60, flush=True)
        logger.info("Bot iniciado")

        # ---------- POLLING LOOP (RESILIENTE) ----------
        print("[BOOT 6/6] 📡 A iniciar long polling...", flush=True)
        while True:
            try:
                bot.polling(
                    none_stop=True,
                    interval=1,
                    timeout=60,
                    long_polling_timeout=60,
                    allowed_updates=['message', 'callback_query']
                )
            except KeyboardInterrupt:
                logger.info("Bot parado manualmente.")
                print("👋 Shutdown manual.", flush=True)
                break
            except Exception as e:
                error_msg = str(e)
                if "409" in error_msg or "terminated by other" in error_msg:
                    print("⚠️ Erro 409 — outra instância ativa. A tentar em 30s...", flush=True)
                    time.sleep(30)
                else:
                    logger.error(f"Conexão perdida: {e}")
                    print(f"⚠️ Polling crashed: {e}. Reconectando em 10s...", flush=True)
                    time.sleep(10)
                print("🔄 Reconectando...", flush=True)
                continue

    except Exception as fatal:
        # Qualquer exceção inesperada no arranque -> log completo + mantém processo vivo
        # para o Render não marcar "exited early" e para debug ficar visível
        print("=" * 60, flush=True)
        print(f"💀 FATAL NO ARRANQUE: {fatal}", flush=True)
        print(traceback.format_exc(), flush=True)
        print("=" * 60, flush=True)
        print("⏳ A manter processo vivo para debug (sleep infinito)...", flush=True)
        while True:
            time.sleep(60)
