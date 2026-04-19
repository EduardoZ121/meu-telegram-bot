# 🚀 GROWTH ENGINE — Remake_Pixel Bot
Sistema de crescimento automatico: Reddit → Bot → Canal Galeria → Viral

---

## 📋 ÍNDICE

1. [Como funciona o ciclo viral](#ciclo)
2. [Parte 1 — Canal Galeria no Telegram](#canal)
3. [Parte 2 — Botão "Publicar na Galeria" (já implementado no bot)](#botao)
4. [Parte 3 — Reddit Auto-Poster](#reddit)
5. [Parte 4 — Automação com cron](#cron)
6. [Testes e troubleshooting](#testes)

---

<a id="ciclo"></a>
## 🔄 COMO FUNCIONA O CICLO VIRAL

```
  [1] Reddit auto-post (2x/dia)
           ↓
  [2] Pessoas veem imagem → clicam link → entram no bot
           ↓
  [3] Geram imagens → clicam "📢 Publicar na Galeria" (+2 créd bónus)
           ↓
  [4] Criação aparece no @RemakePixel_Gallery com link "Criar o meu →"
           ↓
  [5] Seguidores do canal veem → clicam → entram no bot
           ↓
  (volta ao passo 3, crescendo exponencialmente)
```

---

<a id="canal"></a>
## 📢 PARTE 1 — CANAL GALERIA NO TELEGRAM

### 1.1 Cria o canal

1. Abre Telegram → Menu ☰ → **Criar Canal**
2. Nome: **Remake Pixel Gallery** (ou o que quiseres)
3. Descrição sugerida:
   > 🎨 AI art gallery powered by @RemakePix_bot
   > Create yours: t.me/RemakePix_bot
4. Tipo: **Público**
5. Username: `RemakePixel_Gallery` (ou outro disponível)
6. Clica ✅

### 1.2 Adiciona o bot como admin

1. No canal, toca no nome → **Administradores**
2. **Adicionar Administrador** → procura `@RemakePix_bot`
3. Permissões que o bot precisa:
   - ✅ **Publicar Mensagens**
   - ✅ **Editar Mensagens do Canal**
   - ✅ **Apagar Mensagens**
   - (desliga "Adicionar Administradores" — não precisa)
4. Confirma.

### 1.3 Configura a env var no Render

1. Vai a https://dashboard.render.com → teu serviço do bot
2. **Environment** → **Add Environment Variable**
3. Adiciona:
   ```
   GALLERY_CHANNEL = @RemakePixel_Gallery
   ```
   (ou o username do teu canal, com `@` à frente)
4. Save. O Render faz rebuild automático (~1 min).

### 1.4 Posta uma mensagem inicial manual

Abre o canal e posta algo tipo:
```
🎨 Welcome to Remake Pixel Gallery
AI-generated art by our community

Want to create yours? → t.me/RemakePix_bot
```
(Isso dá primeira prova social; canais vazios dão má impressão.)

---

<a id="botao"></a>
## 🤖 PARTE 2 — BOTÃO "PUBLICAR NA GALERIA" (já implementado)

✅ **O código já está no `bot.py`!** Quando fizeres push da versão atualizada (com `curl` ou GitHub), o bot passa a mostrar um novo botão **"📢 Publicar na Galeria"** debaixo de cada criação.

### Comportamento:
- User clica → a imagem é publicada anonimamente no teu canal com caption:
  ```
  ✨ [prompt da criação]
  Criado com @RemakePix_bot — gera o teu: t.me/RemakePix_bot
  ```
- Botão inline: **🤖 Criar o meu →**
- User ganha **+2 créditos bónus** por publicar (incentivo viral)
- Cada criação só pode ser publicada **1 vez** (previne spam)

### Teste manual (após deploy):
1. Gera uma imagem no bot
2. Debaixo do resultado vais ver 3 botões (Favoritar / Compartilhar / Publicar na Galeria)
3. Clica Publicar → deve aparecer no canal em 2-3 segundos
4. Se der erro "Canal não configurado", verifica `GALLERY_CHANNEL` no Render

---

<a id="reddit"></a>
## 🟠 PARTE 3 — REDDIT AUTO-POSTER

### 3.1 Cria App Reddit

1. Acede a https://www.reddit.com/prefs/apps (logged in)
2. Scroll até baixo → **are you a developer? create an app**
3. Preenche:
   - **name**: `remakepixel-poster`
   - **type**: ⚪ **script**
   - **description**: `AI art auto-poster`
   - **redirect uri**: `http://localhost:8080`
4. Clica **create app**
5. Copia:
   - **client_id** (14 caracteres abaixo de "personal use script")
   - **secret** (string comprida)

### 3.2 Instala dependências (no teu servidor/Userland)

```bash
pip install praw requests
```

### 3.3 Configura as env vars

Adiciona ao `.env` do bot (ou no Render como variáveis):
```
REDDIT_CLIENT_ID=o_teu_client_id_aqui
REDDIT_CLIENT_SECRET=o_teu_secret_aqui
REDDIT_USERNAME=o_teu_user_reddit
REDDIT_PASSWORD=a_tua_password_reddit
```

### 3.4 Testa o script

No teu Userland ou servidor:

```bash
cd ~/meu-telegram-bot   # ou onde tens o bot.py
curl -o reddit_poster.py https://telegram-photo-tool-1.preview.emergentagent.com/api/download/reddit_poster.py

# Carrega env vars
export $(cat .env | xargs)

# Corre
python reddit_poster.py
```

### Output esperado:
```
🤖 Reddit Auto-Poster — 2026-02-20 14:30
============================================================
📸 Prompt: cyberpunk samurai in neon city...
🔗 URL: https://replicate.delivery/...
⏳ Comportamento humano: a aguardar 12 min antes de postar...
  → Subreddit: r/aiArt
  → Title: Latest generation — cyberpunk scene
  → Post feito. A aguardar 47s antes do comentario...
  → Comentario adicionado: For anyone curious about the tool: https://t.me/RemakePix_bot
✅ Sucesso! https://reddit.com/r/aiArt/comments/xxx
```

### 3.5 Regras anti-ban implementadas

✅ Máximo **2 posts/dia** (forçado pelo script)
✅ Gap mínimo **6h** entre posts
✅ Delay humano **0-45 min** antes de postar (aleatório)
✅ Delay **30s-2min** entre post e comentário
✅ Titulos **naturais** (10 templates, sem spam words)
✅ Link **só no comentário**, nunca no título
✅ Subreddit **aleatório** (5 opções, rotação)
✅ Log de posts em `reddit_post_log.json`

---

<a id="cron"></a>
## ⏰ PARTE 4 — AUTOMAÇÃO COM CRON

### Opção A: Cron no teu servidor Linux/Android Userland

```bash
crontab -e
```

Adiciona (2 posts/dia: 10h e 20h):
```
0 10 * * * cd /home/user/meu-telegram-bot && /usr/bin/python reddit_poster.py >> reddit.log 2>&1
0 20 * * * cd /home/user/meu-telegram-bot && /usr/bin/python reddit_poster.py >> reddit.log 2>&1
```

### Opção B: Render (se o bot já corre lá)

1. Render dashboard → teu serviço → **Settings** → **Cron Jobs**
2. Adiciona 2 cron jobs:
   - Schedule: `0 10 * * *` → Command: `python reddit_poster.py`
   - Schedule: `0 20 * * *` → Command: `python reddit_poster.py`

### Opção C: Termux/Userland (Android)

Se corres o bot no telemóvel:

```bash
pkg install cronie
crond
crontab -e
# adiciona as linhas acima
```

---

<a id="testes"></a>
## 🧪 TESTES E TROUBLESHOOTING

### Erro: "401 Unauthorized" (Reddit)
→ Credenciais erradas. Confirma client_id/secret/user/pass.

### Erro: "403 Forbidden" no subreddit
→ Subreddit bloqueou o teu user novo (karma baixo). Soluções:
- Posta manualmente 3-5x ao longo de 1-2 semanas para ganhar karma
- Começa só com r/aiArt e r/AIgenerated (mais permissivos)
- Usa conta Reddit com >30 dias e >50 karma

### Erro: "Canal não configurado" (botão Galeria)
→ Verifica:
1. `GALLERY_CHANNEL` está no Render env vars?
2. O bot é admin do canal?
3. Tem permissão "Publicar mensagens"?

### Imagem não aparece no canal
→ Verifica logs do bot: `/painel → Logs` ou `heroku logs`. Procura "gallery_publish_fail".

### Banimento no Reddit
→ **NÃO desativar o rate limit do script**. As regras são:
- Max 2/dia (nunca subas isto)
- Variar subreddits
- Conta Reddit com histórico humano (comenta em outros posts também, não só auto-posts)

---

## 📊 ESTIMATIVAS REALISTAS

Se correr diariamente durante **30 dias**:

| Fonte | Visitas/mês | Conversão | Novos users |
|-------|-------------|-----------|-------------|
| Reddit (2 posts/dia × 30) | ~3000 views | 3-5% | 90-150 |
| Canal Galeria (viral) | cresce 20-40/mês no início | 15-20% | 3-8 |
| **TOTAL** | | | **~100-160 novos users/mês** |

Conversão para pagantes: ~3-5% → **3-8 pagamentos/mês** extra = **€15-80 extra/mês**.

Após 6 meses de consistência: **500-1000 users/mês**, €100-400/mês orgânico.

---

## ⚠️ REGRAS DE OURO

1. **Nunca aumentar posts/dia acima de 2** (ban garantido)
2. **Nunca pôr link no título** (auto-remoção Reddit)
3. **Usa conta Reddit com histórico** (conta nova = banida)
4. **Varia conteúdo** (não postes a mesma imagem 2x)
5. **Engage com comentários** (responde a quem comentar)
6. **Respeita regras de cada sub** (lê o sidebar primeiro)
