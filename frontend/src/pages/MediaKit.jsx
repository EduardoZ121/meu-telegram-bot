import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Download, Check, ArrowLeft, ExternalLink } from "lucide-react";

const TELEGRAM_LINK = "https://t.me/RemakePix_bot";

// ==================== CONTENT ====================
const content = {
  tagline: {
    short: {
      pt: "IA para editar e combinar fotos no Telegram",
      en: "AI photo editing & merging bot on Telegram",
      es: "IA para editar y combinar fotos en Telegram",
    },
    medium: {
      pt: "Bot Telegram com IA: edita fotos, combina rostos, aplica 33 estilos artísticos (anime, Disney, cyberpunk). FLUX.2 + Grok. 5 créditos grátis.",
      en: "Telegram bot with AI: edit photos, merge faces, 33 artistic styles (anime, Disney, cyberpunk). FLUX.2 + Grok. 5 free credits.",
      es: "Bot Telegram con IA: edita fotos, combina rostros, 33 estilos artísticos. FLUX.2 + Grok. 5 créditos gratis.",
    },
    long: {
      pt: "Remake_Pixel é um bot Telegram com inteligência artificial que transforma fotos em minutos. Edita, combina até 5 rostos, aplica 33 estilos artísticos (anime, Ghibli, Disney 3D, cyberpunk, pixel art, comic). Usa modelos topo: FLUX.2 Klein 9B e Grok Imagine. Créditos a partir de €5. Suporte PT/EN/ES.",
      en: "Remake_Pixel is a Telegram bot with AI that transforms photos in minutes. Edits, merges up to 5 faces, applies 33 artistic styles (anime, Ghibli, Disney 3D, cyberpunk, pixel art, comic). Uses top models: FLUX.2 Klein 9B and Grok Imagine. Credits from €5. Multi-language support.",
      es: "Remake_Pixel es un bot Telegram con IA que transforma fotos en minutos. Edita, combina hasta 5 rostros, aplica 33 estilos artísticos. Usa FLUX.2 Klein 9B y Grok Imagine. Créditos desde €5.",
    },
  },
  keywords: [
    "ai photo editor", "photo editing bot", "telegram bot ai",
    "face merge", "ai art generator", "flux 2 bot", "grok imagine",
    "anime generator", "photo to anime", "ai combine photos",
    "editar fotos ia", "combinar rostos ia", "bot telegram ia",
    "gerador imagens ia", "ai image edit", "photo ai telegram",
  ],
  categories: [
    "AI Image Generation", "Photo Editing", "Telegram Bots",
    "Creative Tools", "Art & Design", "AI-Powered Tools",
  ],
  features: [
    "33 artistic styles (Anime, Disney, Cyberpunk, Pixel Art...)",
    "Combine up to 5 faces into one photo",
    "Photo-realistic enhancement (FLUX.2)",
    "Text-to-image generation (Grok)",
    "Custom prompts in 4 languages",
    "Credit-based pricing (€5 = 120 credits)",
    "Referral program (earn 10 credits per friend)",
    "Carousel mode (sequential AI images)",
  ],
  stats: {
    users: "1,200+",
    creations: "8,400+",
    languages: "PT / EN / ES / FR",
    response: "< 30 seconds",
  },
};

// ==================== COMPONENT ====================
const CopyBox = ({ label, text, testid }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative border border-zinc-800 bg-zinc-950/60 group">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-black/40">
        <span className="font-mono text-xs text-zinc-500 uppercase tracking-widest">{label}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-xs font-mono text-cyan-400 hover:text-pink-400 transition"
          data-testid={testid}
        >
          {copied ? <><Check className="w-3 h-3" /> COPIED</> : <><Copy className="w-3 h-3" /> COPY</>}
        </button>
      </div>
      <pre className="px-4 py-3 text-sm text-zinc-200 whitespace-pre-wrap break-words font-mono">{text}</pre>
    </div>
  );
};

export default function MediaKit() {
  return (
    <div className="min-h-screen bg-black text-white relative">
      {/* BG grid */}
      <div className="fixed inset-0 pointer-events-none z-0 opacity-[0.06]"
        style={{
          backgroundImage: `linear-gradient(rgba(236,72,153,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.5) 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }} />

      <div className="relative max-w-5xl mx-auto px-6 py-16 z-10 space-y-16">
        {/* HEADER */}
        <div>
          <a href="/" className="inline-flex items-center gap-2 text-zinc-500 hover:text-cyan-400 font-mono text-sm mb-6" data-testid="kit-back-btn">
            <ArrowLeft className="w-4 h-4" /> BACK
          </a>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="inline-flex items-center gap-2 px-3 py-1 border border-pink-500/30 bg-pink-500/5 text-pink-400 font-mono text-xs uppercase tracking-widest mb-4">
              <div className="w-2 h-2 rounded-full bg-pink-500 animate-pulse" />
              MEDIA KIT v1.0
            </div>
            <h1 className="font-mono text-4xl sm:text-6xl font-black">
              SUBMIT <span className="bg-gradient-to-r from-pink-500 to-cyan-400 bg-clip-text text-transparent">PACK_</span>
            </h1>
            <p className="text-zinc-400 mt-3 font-light">
              Copy-paste ready texts for AI directories, bot catalogs, Product Hunt, and cross-promotion.
            </p>
          </motion.div>
        </div>

        {/* BRAND */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-cyan-400">// 01 — BRAND</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <CopyBox label="Name" text="Remake_Pixel" testid="kit-copy-name" />
            <CopyBox label="Telegram Username" text="@RemakePix_bot" testid="kit-copy-username" />
            <CopyBox label="Telegram Link" text={TELEGRAM_LINK} testid="kit-copy-link" />
            <CopyBox label="Website" text="https://t.me/RemakePix_bot" testid="kit-copy-website" />
          </div>
        </section>

        {/* TAGLINES */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-pink-400">// 02 — TAGLINES (3 sizes × 3 languages)</h2>

          {["short", "medium", "long"].map((size) => (
            <div key={size} className="space-y-2">
              <div className="font-mono text-xs text-zinc-500 uppercase">{size.toUpperCase()} ({size === "short" ? "≤60 chars" : size === "medium" ? "≤160 chars" : "≤500 chars"})</div>
              {["pt", "en", "es"].map((lang) => (
                <CopyBox
                  key={`${size}-${lang}`}
                  label={`${size.toUpperCase()} / ${lang.toUpperCase()}`}
                  text={content.tagline[size][lang]}
                  testid={`kit-copy-${size}-${lang}`}
                />
              ))}
            </div>
          ))}
        </section>

        {/* KEYWORDS */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-fuchsia-400">// 03 — SEO KEYWORDS</h2>
          <CopyBox
            label="Keywords (comma-separated)"
            text={content.keywords.join(", ")}
            testid="kit-copy-keywords"
          />
        </section>

        {/* CATEGORIES */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-cyan-400">// 04 — CATEGORIES</h2>
          <CopyBox
            label="Suggested categories"
            text={content.categories.join("\n")}
            testid="kit-copy-categories"
          />
        </section>

        {/* FEATURES */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-pink-400">// 05 — FEATURE LIST</h2>
          <CopyBox
            label="Bullet features"
            text={content.features.map((f) => `• ${f}`).join("\n")}
            testid="kit-copy-features"
          />
        </section>

        {/* STATS */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-fuchsia-400">// 06 — QUICK STATS</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Object.entries(content.stats).map(([k, v]) => (
              <div key={k} className="border border-zinc-800 bg-zinc-950/40 p-4">
                <div className="font-mono text-2xl text-white font-bold">{v}</div>
                <div className="font-mono text-xs text-zinc-500 uppercase tracking-widest mt-1">{k}</div>
              </div>
            ))}
          </div>
        </section>

        {/* DIRECTORIES CHECKLIST */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-cyan-400">// 07 — SUBMISSION CHECKLIST</h2>
          <div className="border border-zinc-800 bg-zinc-950/40 p-6 space-y-3">
            <div className="font-mono text-sm text-pink-400 mb-4">🎯 AI DIRECTORIES (grátis, 5-10 min cada):</div>
            {[
              ["theresanaiforthat.com", "https://theresanaiforthat.com/submit/"],
              ["futuretools.io", "https://www.futuretools.io/submit-a-tool"],
              ["aitools.fyi", "https://aitools.fyi/submit"],
              ["toolify.ai", "https://www.toolify.ai/submit"],
              ["topai.tools", "https://topai.tools/submit"],
              ["aiexplorer.com", "https://aiexplorer.com/submit"],
              ["aiof.com", "https://aiof.com/submit"],
            ].map(([n, url]) => (
              <a key={n} href={url} target="_blank" rel="noreferrer"
                 className="flex items-center justify-between p-3 border border-zinc-800 hover:border-pink-500 transition group"
                 data-testid={`kit-dir-${n.split('.')[0]}`}>
                <span className="font-mono text-sm text-white">{n}</span>
                <ExternalLink className="w-4 h-4 text-zinc-500 group-hover:text-pink-400" />
              </a>
            ))}

            <div className="font-mono text-sm text-cyan-400 mt-6 mb-4">🤖 TELEGRAM BOT DIRECTORIES:</div>
            {[
              ["@storebot (Official)", "https://t.me/storebot"],
              ["telega.io", "https://telega.io/"],
              ["tgstat.com", "https://tgstat.com/"],
              ["combot.org", "https://combot.org/"],
              ["botostore.com", "https://botostore.com/"],
            ].map(([n, url]) => (
              <a key={n} href={url} target="_blank" rel="noreferrer"
                 className="flex items-center justify-between p-3 border border-zinc-800 hover:border-cyan-400 transition group"
                 data-testid={`kit-tg-${n.split(' ')[0].replace(/[@.]/g, '')}`}>
                <span className="font-mono text-sm text-white">{n}</span>
                <ExternalLink className="w-4 h-4 text-zinc-500 group-hover:text-cyan-400" />
              </a>
            ))}
          </div>
        </section>

        {/* DOWNLOAD GUIDES */}
        <section className="space-y-4">
          <h2 className="font-mono text-xs uppercase tracking-widest text-pink-400">// 08 — FULL GUIDES</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <a
              href="/api/download/telegram_sponsored_guide.md"
              className="border-2 border-cyan-400 p-6 hover:bg-cyan-400/10 transition block"
              data-testid="kit-dl-telegram"
            >
              <Download className="w-6 h-6 text-cyan-400 mb-3" />
              <div className="font-mono font-bold text-white">TELEGRAM SPONSORED POSTS</div>
              <div className="text-sm text-zinc-400 mt-2">Lista de 10+ canais AI art para comprar posts. €5-20 → 100-300 users</div>
            </a>
            <a
              href="/api/download/product_hunt_guide.md"
              className="border-2 border-pink-500 p-6 hover:bg-pink-500/10 transition block"
              data-testid="kit-dl-producthunt"
            >
              <Download className="w-6 h-6 text-pink-500 mb-3" />
              <div className="font-mono font-bold text-white">PRODUCT HUNT LAUNCH</div>
              <div className="text-sm text-zinc-400 mt-2">Checklist completo, timing, templates. Potencial: 2000-10000 visitas/dia</div>
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}
