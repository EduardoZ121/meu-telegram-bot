#!/usr/bin/env python3
"""
Reddit Auto-Poster para @RemakePix_bot
=====================================
Corre 1-2 vezes por dia (via cron) e publica as melhores criacoes do bot
em subreddits relevantes, com titulo natural + link nos comentarios.

Evita spam: horarios aleatorios, delays humanos, max 1-2 posts/dia.

Usage:
    python reddit_poster.py

Setup:
    1. pip install praw
    2. Cria app Reddit em https://www.reddit.com/prefs/apps
       - Tipo: "script"
       - Redirect URI: http://localhost:8080
    3. Preenche as env vars abaixo no .env ou no cron
    4. Cron: "0 10,20 * * *  cd /path && python reddit_poster.py"
"""
import os
import json
import random
import time
import sys
from datetime import datetime
from pathlib import Path

try:
    import praw
    import requests
except ImportError as e:
    print(f"❌ Missing dependency: {e}. Run: pip install praw requests")
    sys.exit(1)

# ==================== CONFIG ====================
BOT_USERNAME = "RemakePix_bot"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"
HISTORY_FILE = Path(__file__).parent / "user_history.json"
POST_LOG_FILE = Path(__file__).parent / "reddit_post_log.json"

# Subreddits permissivos para arte IA (ordenados por receptividade)
SUBREDDITS = [
    "aiArt",             # ~80k members, muito recetivo a IA
    "StableDiffusion",   # ~400k members
    "MediaSynthesis",    # foco em IA generativa
    "AIgenerated",       # aberto
    "deepdream",         # arte experimental
]

# Max 2 posts/dia TOTAL (regra anti-ban)
MAX_POSTS_PER_DAY = 2
# Gap minimo entre posts (horas)
MIN_GAP_HOURS = 6

# Templates naturais (sem palavras de spam tipo "FREE!!!", "CLICK HERE")
TITLE_TEMPLATES = [
    "Made this with AI today — thoughts?",
    "Experimenting with diffusion models — {style}",
    "Tried a new prompt today — {style}",
    "Latest generation — {style}",
    "Playing with AI — feedback welcome",
    "Quick experiment: {style}",
    "Happy with this result",
    "{style} — AI-generated",
    "Generated this earlier today",
    "Testing new prompts — {style}",
]

COMMENT_TEMPLATES = [
    "Generated this using a Telegram bot I built. If anyone wants to try: {link}",
    "For anyone curious about the tool: {link}",
    "Made via {link} — works on Telegram, happy to answer questions",
    "Here's the tool I used: {link} (Telegram)",
    "Made with my bot: {link}",
]

STYLE_HINTS = [
    "cyberpunk scene", "portrait experiment", "fantasy landscape",
    "retro aesthetic", "minimalist composition", "surreal concept",
    "anime-inspired", "photorealistic attempt", "abstract piece",
]


# ==================== UTILS ====================
def load_post_log():
    if POST_LOG_FILE.exists():
        try:
            return json.loads(POST_LOG_FILE.read_text())
        except Exception:
            return {"posts": []}
    return {"posts": []}


def save_post_log(log):
    POST_LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False))


def check_rate_limit(log):
    """Retorna True se podemos postar, False se devemos saltar hoje."""
    now = time.time()
    today_cutoff = now - 86400
    posts_today = [p for p in log.get("posts", []) if p["ts"] > today_cutoff]

    if len(posts_today) >= MAX_POSTS_PER_DAY:
        return False, f"Limite diario atingido ({MAX_POSTS_PER_DAY} posts em 24h)"

    # Gap minimo desde o ultimo post
    if posts_today:
        last = max(p["ts"] for p in posts_today)
        if now - last < MIN_GAP_HOURS * 3600:
            mins_left = int((MIN_GAP_HOURS * 3600 - (now - last)) / 60)
            return False, f"Aguarda mais {mins_left} min (gap minimo {MIN_GAP_HOURS}h)"

    return True, "OK"


def pick_best_creation():
    """Escolhe uma criacao aleatoria das ultimas 50 do bot (com URL http)."""
    if not HISTORY_FILE.exists():
        return None
    try:
        data = json.loads(HISTORY_FILE.read_text())
    except Exception:
        return None

    pool = []
    for uid, items in data.items():
        for item in items[:20]:  # ultimas 20 por user
            url = item.get("image_url") or item.get("url")
            prompt = (item.get("prompt") or "").strip()
            if url and url.startswith("http") and len(prompt) > 10:
                pool.append({"url": url, "prompt": prompt})

    if not pool:
        return None

    # Mistura para nao ser sempre o mesmo
    random.shuffle(pool)
    return pool[0]


def extract_style_hint(prompt):
    """Analisa o prompt e devolve um hint curto (ou random fallback)."""
    lower = prompt.lower()
    keywords = {
        "cyberpunk": "cyberpunk scene",
        "anime": "anime-inspired",
        "portrait": "portrait experiment",
        "landscape": "landscape",
        "fantasy": "fantasy landscape",
        "retro": "retro aesthetic",
        "minimalist": "minimalist",
        "surreal": "surreal concept",
    }
    for k, v in keywords.items():
        if k in lower:
            return v
    return random.choice(STYLE_HINTS)


def post_to_reddit(reddit, subreddit_name, image_url, prompt):
    """Posta no Reddit e adiciona comentario com o link."""
    sub = reddit.subreddit(subreddit_name)
    style = extract_style_hint(prompt)
    title = random.choice(TITLE_TEMPLATES).format(style=style)

    print(f"  → Subreddit: r/{subreddit_name}")
    print(f"  → Title: {title}")

    # Submeter como link/image post
    submission = sub.submit_image(title=title, image_path=None, without_websockets=True, image_url=image_url) \
        if hasattr(sub, "submit_image") else sub.submit(title=title, url=image_url)

    # Delay humano antes do comentario (30s-2min)
    delay = random.randint(30, 120)
    print(f"  → Post feito. A aguardar {delay}s antes do comentario...")
    time.sleep(delay)

    # Comentario com link (regra: link apenas no comentario, nunca no titulo)
    comment_text = random.choice(COMMENT_TEMPLATES).format(link=BOT_LINK)
    submission.reply(comment_text)
    print(f"  → Comentario adicionado: {comment_text}")

    return submission.permalink


def random_delay_human():
    """Simula comportamento humano: espera 0-45 min aleatorio."""
    delay = random.randint(0, 2700)
    if delay > 60:
        print(f"⏳ Comportamento humano: a aguardar {delay//60} min antes de postar...")
        time.sleep(delay)


# ==================== MAIN ====================
def main():
    print(f"🤖 Reddit Auto-Poster — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Carrega env vars
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")
    user_agent = os.getenv("REDDIT_USER_AGENT", f"script:remakepixel-poster:v1.0 (by /u/{username})")

    if not all([client_id, client_secret, username, password]):
        print("❌ Env vars em falta: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD")
        sys.exit(1)

    # Rate limit
    log = load_post_log()
    can_post, reason = check_rate_limit(log)
    if not can_post:
        print(f"⏸️  A saltar: {reason}")
        sys.exit(0)

    # Escolhe criacao
    creation = pick_best_creation()
    if not creation:
        print("❌ Nenhuma criacao disponivel em user_history.json")
        sys.exit(0)

    print(f"📸 Prompt: {creation['prompt'][:80]}...")
    print(f"🔗 URL: {creation['url']}")

    # Random subreddit
    subreddit_name = random.choice(SUBREDDITS)

    # Delay humano
    random_delay_human()

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
        )
        reddit.validate_on_submit = True

        permalink = post_to_reddit(reddit, subreddit_name, creation["url"], creation["prompt"])

        # Log
        log["posts"].append({
            "ts": int(time.time()),
            "subreddit": subreddit_name,
            "prompt": creation["prompt"][:100],
            "permalink": f"https://reddit.com{permalink}",
        })
        save_post_log(log)
        print(f"✅ Sucesso! https://reddit.com{permalink}")

    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
