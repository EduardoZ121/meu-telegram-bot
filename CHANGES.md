# Remake Pixel Bot — Mudancas

## Iteracao 3 (atual) — 50 creditos + persistencia anti-redeploy

### 💰 Creditos gratis: 30 → 50
Alterado em todos os locais visiveis ao user (mensagem de tutorial, get_user_credits, share_text, notificacao admin, etc.).

### 🛡️ Anti-abuso: o bot NUNCA da creditos gratis duas vezes ao mesmo user_id
**Causa raiz do problema reportado:** o filesystem do Render (e a maioria dos PaaS gratuitos) e EFFEMERAL — em cada redeploy, os ficheiros .json sao apagados. O bot via cada user como "novo" e dava 30/50 creditos outra vez.

**Solucao implementada (sem precisares de pagar Render Disk nem MongoDB):**

1. **Novo ficheiro** `users_ever_seen.json` que regista <b>cada user_id que ja recebeu creditos gratis</b> + timestamp.
2. `get_user_credits` foi modificado para verificar este ficheiro ANTES de dar 50 creditos:
   - Se o user_id ja esta em `users_ever_seen.json` → cria entrada com **0 creditos**
   - Se nao → da **50 creditos** + marca como ever_seen
3. **Migracao automatica** no boot: ao arrancar, todos os users ja existentes em `user_credits.json` sao automaticamente marcados como ever_seen (idempotente).
4. **Auto-backup para o teu Telegram (DM admin)**: cada vez que entra um user novo, o bot manda os ficheiros JSON criticos como documents para o teu chat (`SUPER_ADMIN_IDS[0]`). Throttle de 60s para nao spam.
5. **Comandos novos** (admin only):
   - `/backup` — forca backup imediato (envia todos os JSON criticos para a tua DM)
   - `/restore` — instrucoes para restaurar apos redeploy
6. **Restauro automatico**: o admin reenvia o ficheiro JSON na DM → bot detecta o nome, valida JSON, sobrescreve. Funciona para qualquer um destes ficheiros:
   - user_credits.json, user_modes.json, user_languages.json, user_onboarding.json, users_ever_seen.json, user_settings.json, user_history.json, user_favorites.json, referrals.json, secondary_admins.json

### Como usar (fluxo completo)
**Apos cada redeploy:**
1. Vai ao teu chat com o bot, ve o ultimo backup que recebeste (foi enviado automaticamente).
2. Reenvia <b>cada ficheiro</b> .json para o bot.
3. O bot responde "✅ Ficheiro restaurado: user_credits.json (1234 bytes)"
4. Pronto — todos os users mantem os seus creditos, modo, idioma, etc.

**Em qualquer momento:**
- `/backup` → forca novo backup imediato
- `/restore` → mostra a lista de ficheiros aceites

### Testado
- ✅ User novo recebe 50 creditos
- ✅ Mesmo user_id apos "redeploy simulado" (apagar user_credits.json) recebe 0 — bloqueado pelo ever_seen
- ✅ User genuinamente novo recebe 50 creditos
- ✅ Imports e syntax OK

### Limitacoes / nota importante
- O ficheiro `users_ever_seen.json` TAMBEM e apagado em cada redeploy. **Por isso o auto-backup para Telegram e essencial** — apos o redeploy tens de reenviar esse ficheiro tambem. Se nao reenviares, o bot vai voltar a dar 50 creditos (porque o ever_seen ficou vazio).
- **Solucao definitiva (recomendada a longo prazo):** Render Disk persistente ($1/mes) ou MongoDB Atlas (gratis 512MB) — mas exigem setup teu. O fluxo atual e gratis e funciona se fizeres /restore apos cada deploy.

---

## Iteracoes anteriores
- Iter 1: Modos Fast/Advanced + I18N PT/EN/ES/FR
- Iter 2: 🎨 Posters Pro (44 templates dos 5 .txt) + bug do Trocar Modo corrigido
