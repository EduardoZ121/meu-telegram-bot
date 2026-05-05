"""
Parser one-shot que converte os 5 .txt em /app/templates_raw/
para /app/poster_templates.json (formato estruturado usado pelo bot).

Uso:
    python /app/build_poster_templates.py

Gera /app/poster_templates.json com esta forma:
{
  "music":     { "emoji": "...", "name_pt": "...", "photo_required": True, "templates": [ {...}, {...} ] },
  "food":      { ... },
  "fitness":   { ... },
  "motivational": { ... },
  "flyers":    { ... }
}

Cada template:
{
  "id": "street_energy",
  "title": "STREET ENERGY",
  "subtag": "Mulher",          # label dentro do ficheiro (ex: Mulher, Unisex, etc)
  "prompt": "...",             # prompt completo SEM flags Midjourney
  "placeholders": ["LOREM IPSUM", "(11) 98765-4321", ...]  # strings em "" extraidas
}
"""
import os
import re
import json
import unicodedata

RAW_DIR = "/app/templates_raw"
OUT = "/app/poster_templates.json"

# Regex para flags Midjourney (removemos — gpt-image-1 nao usa)
MJ_FLAGS = re.compile(r'--(?:ar|stylize|v|chaos|weird|tile|niji|iw|seed|sref)\s+[^\s]+', re.IGNORECASE)

# Regex para extrair "strings" entre aspas (placeholders)
QUOTED = re.compile(r'"([^"\n]{1,120})"')

# Regex para telefone
PHONE_RE = re.compile(r'\(\d{1,3}\)\s?\d{4,5}-\d{4}')


def slugify(s, maxlen=36):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()
    return s[:maxlen] or "tpl"


def strip_mj(text):
    """Remove --ar 2:3 --stylize 300 --v 6 e limpa pontuacao final dupla."""
    t = MJ_FLAGS.sub('', text)
    # limpa pontuacao/espacos residuais
    t = re.sub(r'\s+([.,;:])', r'\1', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip().rstrip('.').strip() + '.'


def extract_placeholders(prompt):
    """Extrai strings entre aspas, telefones, e outros padroes editaveis."""
    ph = []
    for m in QUOTED.findall(prompt):
        mm = m.strip()
        if not mm:
            continue
        if len(mm) < 2:
            continue
        if mm not in ph:
            ph.append(mm)
    for m in PHONE_RE.findall(prompt):
        if m not in ph:
            ph.append(m)
    return ph


def split_by_title(text):
    """Divide um ficheiro em blocos comecando com 'TITLE: XXX'."""
    # Normaliza line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Split mantendo o separador
    parts = re.split(r'\n\s*TITLE:\s*([^\n]+)\n', '\n' + text)
    # parts: ['<intro>', 'TITLE1', 'body1', 'TITLE2', 'body2', ...]
    blocks = []
    i = 1
    while i + 1 < len(parts):
        title = parts[i].strip()
        body = parts[i + 1].strip()
        blocks.append({"title": title, "body": body, "subtag": ""})
        i += 2
    return blocks


def split_by_mj_flag(text):
    """Fallback para ficheiros sem TITLE (ex: comida.txt).
    Cada template termina numa linha que contem --ar X:Y ... --v N.
    Usamos esse marcador como FIM para fatiar.
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    end_re = re.compile(r'--ar\s+\d+:\d+[^\n]*--v\s+\d+\.?', re.IGNORECASE)
    blocks_raw = []
    last = 0
    for m in end_re.finditer(text):
        chunk = text[last:m.end()].strip()
        if len(chunk) > 60:
            blocks_raw.append(chunk)
        last = m.end()
    blocks = []
    idx = 1
    for rb in blocks_raw:
        # auto-title: usar primeira string em aspas, ou primeiras palavras
        qt = QUOTED.search(rb)
        if qt:
            title = qt.group(1).strip()[:40].upper()
        else:
            words = rb.split()
            title = " ".join(words[:4]).upper()[:40] or f"TEMPLATE {idx}"
        blocks.append({"title": title, "body": rb, "subtag": ""})
        idx += 1
    return blocks


def detect_subtags_in_title_blocks(raw_text, blocks):
    """Para music.txt/flyers.txt que tem 'Mulher:', 'Unisex:', 'Flayer unisex:', '(Azul — topo meio)'
    antes do TITLE:, captura isso como subtag do bloco seguinte."""
    # Re-split mantendo o contexto
    # Procura linhas curtas (<=40 chars) que terminem em ':' ou estejam entre ( ), imediatamente antes de TITLE:
    pattern = re.compile(
        r'(?:\n|^)([^\n]{2,60}:|\([^\n)]{2,60}\))[ \t]*\n[ \t]*TITLE:\s*([^\n]+)',
        re.IGNORECASE
    )
    tag_map = {}  # title (upper) -> subtag
    for m in pattern.finditer(raw_text):
        subtag = m.group(1).strip().strip('(').strip(')').strip(':').strip()
        tt = m.group(2).strip().upper()
        tag_map[tt] = subtag
    for b in blocks:
        key = b["title"].strip().upper()
        if key in tag_map:
            b["subtag"] = tag_map[key]
    return blocks


def parse_file(path, has_titles=True):
    raw = open(path, encoding='utf-8').read()
    if has_titles:
        blocks = split_by_title(raw)
        if not blocks:
            blocks = split_by_mj_flag(raw)
        else:
            blocks = detect_subtags_in_title_blocks(raw, blocks)
    else:
        blocks = split_by_mj_flag(raw)

    out = []
    seen_ids = set()
    for b in blocks:
        clean_prompt = strip_mj(b["body"])
        if len(clean_prompt) < 60:
            continue
        ph = extract_placeholders(clean_prompt)
        tid_base = slugify(b["title"]) or f"tpl_{len(out)+1}"
        tid = tid_base
        n = 1
        while tid in seen_ids:
            n += 1
            tid = f"{tid_base}_{n}"
        seen_ids.add(tid)
        out.append({
            "id": tid,
            "title": b["title"].strip(),
            "subtag": b.get("subtag", ""),
            "prompt": clean_prompt,
            "placeholders": ph,
        })
    return out


CATEGORIES = [
    {
        "key": "music",
        "file": "music.txt",
        "emoji": "🎵",
        "name_pt": "Música / DJ",
        "name_en": "Music / DJ",
        "name_es": "Música / DJ",
        "name_fr": "Musique / DJ",
        "photo_required": True,
        "has_titles": True,
    },
    {
        "key": "food",
        "file": "comida.txt",
        "emoji": "🍔",
        "name_pt": "Comida / Restaurante",
        "name_en": "Food / Restaurant",
        "name_es": "Comida / Restaurante",
        "name_fr": "Nourriture / Restaurant",
        "photo_required": True,
        "has_titles": False,
    },
    {
        "key": "fitness",
        "file": "fitness.txt",
        "emoji": "💪",
        "name_pt": "Fitness / Ginásio",
        "name_en": "Fitness / Gym",
        "name_es": "Fitness / Gimnasio",
        "name_fr": "Fitness / Salle",
        "photo_required": False,
        "has_titles": True,
    },
    {
        "key": "motivational",
        "file": "motivacionais.txt",
        "emoji": "✨",
        "name_pt": "Motivacional",
        "name_en": "Motivational",
        "name_es": "Motivacional",
        "name_fr": "Motivation",
        "photo_required": False,
        "has_titles": True,
    },
    {
        "key": "flyers",
        "file": "flyers.txt",
        "emoji": "📰",
        "name_pt": "Flyers / Editorial",
        "name_en": "Flyers / Editorial",
        "name_es": "Flyers / Editorial",
        "name_fr": "Flyers / Éditorial",
        "photo_required": False,
        "has_titles": True,
    },
]


def build():
    out = {}
    total = 0
    for cat in CATEGORIES:
        path = os.path.join(RAW_DIR, cat["file"])
        templates = parse_file(path, has_titles=cat["has_titles"])
        out[cat["key"]] = {
            "emoji": cat["emoji"],
            "name_pt": cat["name_pt"],
            "name_en": cat["name_en"],
            "name_es": cat["name_es"],
            "name_fr": cat["name_fr"],
            "photo_required": cat["photo_required"],
            "templates": templates,
        }
        total += len(templates)
        print(f"[{cat['key']:14}] parsed {len(templates):3d} templates ({cat['file']})")
    print(f"\nTotal: {total} templates")
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    build()
