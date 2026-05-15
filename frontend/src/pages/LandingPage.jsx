import { useState, useEffect, useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import axios from "axios";
import {
  Zap, Sparkles, Image as ImageIcon, Send, Check, Loader2,
  ArrowRight, Wand2, Layers, Film, Crown, Shield, ChevronRight
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TELEGRAM_LINK = "https://t.me/RemakePix_bot";

// ============== HELPERS ==============
const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

// ============== CYBERPUNK GRID BG ==============
const GridBackground = () => (
  <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
    <div
      className="absolute inset-0 opacity-[0.12]"
      style={{
        backgroundImage: `
          linear-gradient(rgba(236, 72, 153, 0.5) 1px, transparent 1px),
          linear-gradient(90deg, rgba(6, 182, 212, 0.5) 1px, transparent 1px)
        `,
        backgroundSize: "60px 60px",
        transform: "perspective(600px) rotateX(60deg) translateY(-20%)",
        transformOrigin: "center top",
      }}
    />
    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/40 to-black" />
    <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full bg-pink-600/20 blur-[120px] animate-pulse" />
    <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full bg-cyan-500/20 blur-[120px] animate-pulse" style={{ animationDelay: "1s" }} />
  </div>
);

// ============== NAV ==============
const Nav = () => (
  <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-black/40 border-b border-pink-500/20">
    <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-2 font-mono">
        <span className="text-pink-500 text-2xl">▮</span>
        <span className="text-white font-bold tracking-wider text-lg" data-testid="nav-brand">
          REMAKE<span className="text-pink-500">_</span>PIXEL
        </span>
      </div>
      <div className="hidden md:flex items-center gap-8 text-sm font-mono text-zinc-400">
        <button onClick={() => scrollTo("demo")} className="hover:text-cyan-400 transition" data-testid="nav-demo">DEMO</button>
        <button onClick={() => scrollTo("features")} className="hover:text-cyan-400 transition" data-testid="nav-features">FEATURES</button>
        <button onClick={() => scrollTo("pricing")} className="hover:text-cyan-400 transition" data-testid="nav-pricing">PRICING</button>
        <a href="/kit" className="hover:text-pink-400 transition" data-testid="nav-kit">MEDIA KIT</a>
      </div>
      <a
        href={TELEGRAM_LINK}
        target="_blank"
        rel="noreferrer"
        className="relative group px-5 py-2 bg-pink-500 text-black font-mono font-bold text-sm hover:bg-cyan-400 transition-colors"
        style={{ clipPath: "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)" }}
        data-testid="nav-cta-telegram"
      >
        OPEN BOT →
      </a>
    </div>
  </nav>
);

// ============== HERO ==============
const Hero = () => {
  const [stats, setStats] = useState({ users: 0, creations: 0, models: 4 });

  useEffect(() => {
    axios.get(`${API}/public/stats`).then((r) => setStats(r.data)).catch(() => {});
  }, []);

  return (
    <section className="relative min-h-screen flex items-center justify-center px-6 pt-20 z-10">
      <div className="max-w-6xl w-full">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="space-y-8"
        >
          {/* Status bar */}
          <div className="inline-flex items-center gap-2 px-4 py-2 border border-pink-500/30 bg-pink-500/5 text-pink-400 font-mono text-xs uppercase tracking-widest">
            <div className="w-2 h-2 rounded-full bg-pink-500 animate-pulse" />
            SYSTEM ONLINE • NEURAL AI READY
          </div>

          {/* Main title with glitch effect */}
          <h1 className="font-mono font-black text-white leading-[0.9] tracking-tight">
            <div className="text-5xl sm:text-7xl lg:text-8xl">
              EDIT YOUR
            </div>
            <div className="text-5xl sm:text-7xl lg:text-8xl relative inline-block mt-2">
              <span className="bg-gradient-to-r from-pink-500 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
                REALITY_
              </span>
              <span className="absolute -top-1 -left-1 text-cyan-400/30 blur-sm" aria-hidden>
                REALITY_
              </span>
            </div>
          </h1>

          <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl font-light leading-relaxed">
            AI-powered photo & video editing bot running on <span className="text-pink-400 font-mono">FLUX.2</span>,{" "}
            <span className="text-cyan-400 font-mono">GROK</span> and custom diffusion models.{" "}
            Combine faces. Transform styles. Generate the impossible.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-wrap gap-4 pt-4">
            <button
              onClick={() => scrollTo("demo")}
              className="group relative px-8 py-4 bg-gradient-to-r from-pink-500 to-fuchsia-500 text-black font-mono font-bold text-sm uppercase tracking-wider hover:scale-105 transition-transform"
              style={{ clipPath: "polygon(12px 0, 100% 0, calc(100% - 12px) 100%, 0 100%)" }}
              data-testid="hero-try-free-btn"
            >
              <span className="flex items-center gap-2">
                <Wand2 className="w-4 h-4" /> TRY 1 FREE
              </span>
            </button>
            <a
              href={TELEGRAM_LINK}
              target="_blank"
              rel="noreferrer"
              className="group px-8 py-4 border-2 border-cyan-400/60 text-cyan-300 font-mono font-bold text-sm uppercase tracking-wider hover:bg-cyan-400/10 transition"
              data-testid="hero-open-bot-btn"
            >
              <span className="flex items-center gap-2">
                <Send className="w-4 h-4" /> OPEN TELEGRAM BOT
              </span>
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 sm:gap-8 pt-12 max-w-2xl border-t border-zinc-800">
            {[
              { label: "USERS", val: stats.users.toLocaleString() },
              { label: "CREATIONS", val: stats.creations.toLocaleString() },
              { label: "AI MODELS", val: stats.models },
            ].map((s) => (
              <div key={s.label} className="pt-6" data-testid={`stat-${s.label.toLowerCase()}`}>
                <div className="font-mono text-3xl sm:text-4xl text-white font-bold">{s.val}</div>
                <div className="font-mono text-xs text-zinc-500 uppercase tracking-widest mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
};

// ============== DEMO ==============
const Demo = () => {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const examples = [
    "cyberpunk neon samurai, raining night",
    "astronaut relaxing on a tropical beach",
    "vintage 1970s rock band on stage",
    "surreal dreamscape with floating islands",
  ];

  const submit = async () => {
    if (loading || prompt.trim().length < 5) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const r = await axios.post(`${API}/demo/generate`, { prompt });
      if (r.data.success) {
        setResult(r.data.image_url);
      } else {
        setError(r.data.error || "Generation failed");
      }
    } catch (e) {
      setError("Network error. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="demo" className="relative py-24 px-6 z-10">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="space-y-8"
        >
          <div>
            <div className="inline-flex items-center gap-2 text-cyan-400 font-mono text-xs uppercase tracking-widest mb-4">
              <span className="w-6 h-px bg-cyan-400" /> // 01 — LIVE DEMO
            </div>
            <h2 className="font-mono text-4xl sm:text-5xl font-black text-white">
              TEST THE <span className="text-cyan-400">NEURAL_ENGINE</span>
            </h2>
            <p className="text-zinc-400 mt-3 font-light">One free generation. No signup required.</p>
          </div>

          <div className="relative border border-zinc-800 bg-zinc-950/60 backdrop-blur-sm p-6 sm:p-8">
            {/* corner accents */}
            <div className="absolute -top-px -left-px w-6 h-6 border-t-2 border-l-2 border-pink-500" />
            <div className="absolute -bottom-px -right-px w-6 h-6 border-b-2 border-r-2 border-cyan-400" />

            <div className="space-y-4">
              <div className="flex items-center gap-2 font-mono text-xs text-zinc-500 uppercase">
                <span className="text-pink-500">▸</span> INPUT PROMPT
              </div>
              <div className="relative">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe your vision..."
                  rows={3}
                  maxLength={300}
                  disabled={loading}
                  className="w-full bg-black/60 border border-zinc-800 focus:border-pink-500 focus:outline-none text-white font-mono text-sm p-4 resize-none transition placeholder:text-zinc-600"
                  data-testid="demo-prompt-input"
                />
                <span className="absolute bottom-2 right-3 text-xs text-zinc-600 font-mono">
                  {prompt.length}/300
                </span>
              </div>

              {/* Examples */}
              <div className="flex flex-wrap gap-2">
                {examples.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setPrompt(ex)}
                    className="text-xs px-3 py-1 border border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:border-cyan-400/60 hover:text-cyan-300 font-mono transition"
                    data-testid={`demo-example-${ex.slice(0, 10).replace(/\s/g, "-")}`}
                  >
                    {ex}
                  </button>
                ))}
              </div>

              <button
                onClick={submit}
                disabled={loading || prompt.trim().length < 5}
                className="w-full py-4 bg-gradient-to-r from-pink-500 to-fuchsia-500 text-black font-mono font-bold uppercase tracking-wider hover:from-cyan-400 hover:to-pink-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                data-testid="demo-generate-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    GENERATING...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    GENERATE FREE
                  </>
                )}
              </button>

              {error && (
                <div className="p-3 border border-red-500/40 bg-red-500/10 text-red-400 text-sm font-mono" data-testid="demo-error">
                  ⚠ {error}
                </div>
              )}

              {result && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-4"
                >
                  <div className="relative border-2 border-cyan-400/40 overflow-hidden" data-testid="demo-result">
                    <img src={result} alt="Generated" className="w-full" />
                    <div className="absolute top-2 left-2 px-2 py-1 bg-black/80 font-mono text-xs text-cyan-400">
                      ◉ GENERATED
                    </div>
                  </div>
                  <a
                    href={TELEGRAM_LINK}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-center py-3 border border-cyan-400 text-cyan-300 font-mono text-sm hover:bg-cyan-400/10 transition"
                    data-testid="demo-open-bot-after"
                  >
                    WANT MORE? OPEN BOT FOR UNLIMITED → 
                  </a>
                </motion.div>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

// ============== FEATURES ==============
const features = [
  {
    icon: Sparkles,
    title: "PRO MODEL",
    subtitle: "FLUX.2 KLEIN 9B",
    desc: "Photorealistic enhancement with preset menus: Original, Expression, Softer Realism. Preserves identity while upgrading quality.",
    color: "pink",
  },
  {
    icon: Wand2,
    title: "STANDARD MODEL",
    subtitle: "GROK IMAGINE",
    desc: "Text-to-image + photo editing. Change hairstyles, backgrounds, clothing. Natural language instructions.",
    color: "cyan",
  },
  {
    icon: Layers,
    title: "COMBINE FACES",
    subtitle: "MULTI-PHOTO AI",
    desc: "Upload 2-5 photos. AI combines subjects into a cohesive scene. Perfect for group shots, couples, family edits.",
    color: "fuchsia",
  },
  {
    icon: Film,
    title: "ARTISTIC STYLES",
    subtitle: "33 PRESETS",
    desc: "Anime, Ghibli, Disney 3D, Cyberpunk, Oil painting, Pixel art, Tattoo, Manga, and 25 more styles.",
    color: "cyan",
  },
  {
    icon: ImageIcon,
    title: "CAROUSEL MODE",
    subtitle: "SEQUENTIAL AI",
    desc: "Generate coherent image sequences. Storytelling, product showcase, before/after reveals.",
    color: "pink",
  },
  {
    icon: Crown,
    title: "VIP ACCESS",
    subtitle: "UNLOCKED FEATURES",
    desc: "Premium models, priority queue, exclusive prompts, bonus credits. Monthly subscription.",
    color: "fuchsia",
  },
];

const Features = () => (
  <section id="features" className="relative py-24 px-6 z-10">
    <div className="max-w-7xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
      >
        <div className="inline-flex items-center gap-2 text-pink-400 font-mono text-xs uppercase tracking-widest mb-4">
          <span className="w-6 h-px bg-pink-400" /> // 02 — CAPABILITIES
        </div>
        <h2 className="font-mono text-4xl sm:text-5xl font-black text-white mb-3">
          FULL <span className="text-pink-400">ARSENAL_</span>
        </h2>
        <p className="text-zinc-400 font-light">Every model, every style, every format.</p>
      </motion.div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-zinc-800 mt-12 border border-zinc-800">
        {features.map((f, i) => {
          const Icon = f.icon;
          const colorMap = {
            pink: "text-pink-400 border-pink-500",
            cyan: "text-cyan-400 border-cyan-500",
            fuchsia: "text-fuchsia-400 border-fuchsia-500",
          };
          return (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="group relative bg-black p-8 hover:bg-zinc-950 transition"
              data-testid={`feature-${f.title.toLowerCase().replace(/\s/g, "-")}`}
            >
              <Icon className={`w-8 h-8 ${colorMap[f.color].split(" ")[0]}`} />
              <div className="mt-6 space-y-1">
                <div className={`font-mono text-xs uppercase tracking-widest ${colorMap[f.color].split(" ")[0]}`}>
                  {f.subtitle}
                </div>
                <h3 className="font-mono font-bold text-xl text-white">{f.title}</h3>
                <p className="text-zinc-400 text-sm leading-relaxed pt-2">{f.desc}</p>
              </div>
              <div className={`absolute top-0 left-0 h-1 w-0 group-hover:w-full bg-gradient-to-r from-pink-500 to-cyan-400 transition-all duration-500`} />
            </motion.div>
          );
        })}
      </div>
    </div>
  </section>
);

// ============== PRICING ==============
const plans = [
  { name: "BASIC", price: "5", credits: "120", features: ["Standard Model", "Basic edits", "5 combine photos"], color: "cyan" },
  { name: "MEDIUM", price: "12", credits: "350", features: ["All models", "Priority queue", "Carousel mode", "Artistic styles"], color: "pink", popular: true },
  { name: "PRO", price: "22", credits: "800", features: ["Everything in MEDIUM", "Pro FLUX.2 presets", "Bulk generations", "VIP-ready"], color: "fuchsia" },
];

const Pricing = () => (
  <section id="pricing" className="relative py-24 px-6 z-10">
    <div className="max-w-6xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
      >
        <div className="inline-flex items-center gap-2 text-fuchsia-400 font-mono text-xs uppercase tracking-widest mb-4">
          <span className="w-6 h-px bg-fuchsia-400" /> // 03 — CREDITS
        </div>
        <h2 className="font-mono text-4xl sm:text-5xl font-black text-white mb-3">
          FUEL YOUR <span className="text-fuchsia-400">CREATIONS_</span>
        </h2>
        <p className="text-zinc-400 font-light">Pay once. Use forever. No subscription trap.</p>
      </motion.div>

      <div className="grid md:grid-cols-3 gap-6 mt-12">
        {plans.map((p, i) => (
          <motion.div
            key={p.name}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className={`relative border-2 p-8 ${p.popular ? "border-pink-500 bg-pink-500/5" : "border-zinc-800 bg-zinc-950/40"} hover:border-cyan-400 transition group`}
            data-testid={`pricing-${p.name.toLowerCase()}`}
          >
            {p.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-pink-500 text-black font-mono text-xs font-bold tracking-wider">
                ◉ POPULAR
              </div>
            )}
            <div className="font-mono text-xs text-zinc-500 uppercase tracking-widest">{p.name}</div>
            <div className="flex items-baseline gap-1 mt-2">
              <span className="text-5xl font-mono font-black text-white">€{p.price}</span>
            </div>
            <div className="font-mono text-lg text-cyan-400 mt-2">{p.credits} credits</div>
            <ul className="space-y-3 mt-6">
              {p.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                  <Check className="w-4 h-4 text-pink-400 shrink-0 mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <a
              href={TELEGRAM_LINK}
              target="_blank"
              rel="noreferrer"
              className={`mt-8 block text-center py-3 font-mono text-sm font-bold uppercase tracking-wider transition ${
                p.popular
                  ? "bg-pink-500 text-black hover:bg-cyan-400"
                  : "border border-zinc-700 text-white hover:border-pink-500 hover:text-pink-400"
              }`}
              data-testid={`pricing-buy-${p.name.toLowerCase()}`}
            >
              GET {p.name} →
            </a>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

// ============== CTA / EMAIL ==============
const EmailCTA = () => {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done

  const submit = async () => {
    if (!email.match(/^[^@\s]+@[^@\s]+\.[^@\s]+$/)) return;
    setStatus("loading");
    try {
      await axios.post(`${API}/leads/subscribe`, { email, name, source: "landing" });
      setStatus("done");
      setTimeout(() => window.open(TELEGRAM_LINK, "_blank"), 800);
    } catch {
      setStatus("idle");
    }
  };

  return (
    <section className="relative py-24 px-6 z-10">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="relative border-2 border-pink-500 bg-gradient-to-br from-pink-500/10 via-black to-cyan-500/10 p-8 sm:p-12 text-center overflow-hidden"
        >
          {/* Glow */}
          <div className="absolute inset-0 bg-gradient-to-r from-pink-500/20 to-cyan-500/20 blur-3xl -z-10" />

          <Shield className="w-12 h-12 text-pink-500 mx-auto" />
          <h2 className="font-mono text-3xl sm:text-5xl font-black text-white mt-6">
            READY TO <span className="text-cyan-400">JACK_IN</span>?
          </h2>
          <p className="text-zinc-400 mt-3 font-light">Get 5 bonus credits. Join 1000+ creators.</p>

          {status === "done" ? (
            <div className="mt-8 p-6 border border-cyan-400 bg-cyan-400/10 text-cyan-300 font-mono">
              ✓ SUBSCRIBED. REDIRECTING TO TELEGRAM...
            </div>
          ) : (
            <div className="mt-8 flex flex-col sm:flex-row gap-3 max-w-2xl mx-auto">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name (optional)"
                className="flex-1 bg-black/60 border border-zinc-800 focus:border-pink-500 focus:outline-none text-white font-mono text-sm px-4 py-3 transition placeholder:text-zinc-600"
                data-testid="cta-name-input"
              />
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                type="email"
                className="flex-1 bg-black/60 border border-zinc-800 focus:border-cyan-400 focus:outline-none text-white font-mono text-sm px-4 py-3 transition placeholder:text-zinc-600"
                data-testid="cta-email-input"
              />
              <button
                onClick={submit}
                disabled={status === "loading"}
                className="px-6 py-3 bg-pink-500 text-black font-mono font-bold text-sm uppercase tracking-wider hover:bg-cyan-400 disabled:opacity-40 transition flex items-center justify-center gap-2"
                data-testid="cta-submit-btn"
              >
                {status === "loading" ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                GET ACCESS
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </section>
  );
};

// ============== FOOTER ==============
const Footer = () => (
  <footer className="relative border-t border-zinc-800 py-10 px-6 z-10">
    <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-500 font-mono">
      <div>
        © 2026 REMAKE_PIXEL <span className="text-pink-500">//</span> ALL SYSTEMS OPERATIONAL
      </div>
      <div className="flex gap-6">
        <a href={TELEGRAM_LINK} target="_blank" rel="noreferrer" className="hover:text-cyan-400" data-testid="footer-telegram">TELEGRAM</a>
        <a href="#" className="hover:text-cyan-400" data-testid="footer-terms">TERMS</a>
        <a href="#" className="hover:text-cyan-400" data-testid="footer-privacy">PRIVACY</a>
      </div>
    </div>
  </footer>
);

// ============== MAIN ==============
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-black text-white relative overflow-x-hidden">
      <GridBackground />
      <Nav />
      <Hero />
      <Demo />
      <Features />
      <Pricing />
      <EmailCTA />
      <Footer />
    </div>
  );
}
