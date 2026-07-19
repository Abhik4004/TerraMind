// src/pages/Landing.jsx — separate marketing landing page with GSAP animations.
import React, { useLayoutEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { gsap, ScrollTrigger, prefersReducedMotion } from "../anim/gsap";
import "../App.css";

/* ── Inline SVG icons (vector, consistent stroke — no emoji) ──────────────── */
const svg = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};
const GlobeIcon = (p) => (
  <svg {...svg} width={p.size || 24} height={p.size || 24} aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
  </svg>
);
const MapIcon = () => (
  <svg {...svg} width="24" height="24" aria-hidden="true">
    <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
    <path d="M9 4v14M15 6v14" />
  </svg>
);
const SproutIcon = () => (
  <svg {...svg} width="24" height="24" aria-hidden="true">
    <path d="M12 21v-8" />
    <path d="M12 13c0-3 2-5 5-5-.2 3-2 5-5 5z" />
    <path d="M12 13c0-2.5-2-4.5-5-4.5.2 2.7 2 4.5 5 4.5z" />
  </svg>
);
const CloudIcon = () => (
  <svg {...svg} width="24" height="24" aria-hidden="true">
    <path d="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M18 3.5a3.5 3.5 0 1 1 0 7" />
    <path d="M7 20h9a3.5 3.5 0 0 0 .3-7A5 5 0 0 0 7 13.5 3.25 3.25 0 0 0 7 20z" />
  </svg>
);
const RouteIcon = () => (
  <svg {...svg} width="24" height="24" aria-hidden="true">
    <circle cx="6" cy="19" r="2" />
    <circle cx="18" cy="5" r="2" />
    <path d="M8 19h6a4 4 0 0 0 0-8H10a4 4 0 0 1 0-8h6" />
  </svg>
);
const ShieldIcon = () => (
  <svg {...svg} width="24" height="24" aria-hidden="true">
    <path d="M12 3 5 6v5c0 4.4 3 8.5 7 10 4-1.5 7-5.6 7-10V6l-7-3z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);
const SparkIcon = (p) => (
  <svg {...svg} width={p.size || 24} height={p.size || 24} aria-hidden="true">
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <path d="M12 8a4 4 0 0 0 4 4 4 4 0 0 0-4 4 4 4 0 0 0-4-4 4 4 0 0 0 4-4z" />
  </svg>
);
const ArrowIcon = () => (
  <svg {...svg} width="18" height="18" aria-hidden="true">
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

/* ── Terrain / land-analysis decorative SVGs (float on the sides) ─────────── */
const dsvg = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" };
const MountainsSvg = () => (
  <svg {...dsvg} width="120" height="120" viewBox="0 0 120 120" aria-hidden="true">
    <path d="M10 96 44 40l22 34 12-18 32 40z" />
    <path d="M44 40l10 16-8 12" opacity="0.6" />
    <path d="M6 96h108" opacity="0.5" />
  </svg>
);
const ContourSvg = () => (
  <svg {...dsvg} width="130" height="130" viewBox="0 0 130 130" aria-hidden="true">
    <path d="M65 20c26 0 44 18 44 45s-20 45-44 45-44-18-44-45 18-45 44-45z" opacity="0.5" />
    <path d="M65 38c17 0 28 12 28 27s-12 27-28 27-28-12-28-27 11-27 28-27z" opacity="0.7" />
    <path d="M65 56c8 0 12 6 12 12s-5 12-12 12-12-5-12-12 4-12 12-12z" />
  </svg>
);
const CompassSvg = () => (
  <svg {...dsvg} width="110" height="110" viewBox="0 0 110 110" aria-hidden="true">
    <circle cx="55" cy="55" r="44" opacity="0.6" />
    <path d="M55 22l12 33-12 33-12-33z" />
    <path d="M55 22v-8M55 96v8M22 55h-8M96 55h8" opacity="0.5" />
  </svg>
);
const LayersSvg = () => (
  <svg {...dsvg} width="120" height="120" viewBox="0 0 120 120" aria-hidden="true">
    <path d="M60 22 20 44l40 22 40-22z" />
    <path d="M20 60l40 22 40-22" opacity="0.7" />
    <path d="M20 76l40 22 40-22" opacity="0.5" />
  </svg>
);
const PinSvg = () => (
  <svg {...dsvg} width="90" height="90" viewBox="0 0 90 90" aria-hidden="true">
    <path d="M45 82s26-23 26-41a26 26 0 0 0-52 0c0 18 26 41 26 41z" />
    <circle cx="45" cy="41" r="10" />
  </svg>
);
const WavesSvg = () => (
  <svg {...dsvg} width="140" height="90" viewBox="0 0 140 90" aria-hidden="true">
    <path d="M6 26c14-12 28-12 42 0s28 12 42 0 28-12 42 0" opacity="0.7" />
    <path d="M6 50c14-12 28-12 42 0s28 12 42 0 28-12 42 0" />
    <path d="M6 74c14-12 28-12 42 0s28 12 42 0 28-12 42 0" opacity="0.5" />
  </svg>
);
const GridSvg = () => (
  <svg {...dsvg} width="110" height="110" viewBox="0 0 110 110" aria-hidden="true">
    <path d="M20 20h70v70H20z" opacity="0.5" />
    <path d="M20 43h70M20 66h70M43 20v70M66 20v70" opacity="0.7" />
  </svg>
);

// Side decorations: {Comp, side, top} — positioned in the page gutters.
const decorItems = [
  { Comp: ContourSvg, side: "left", top: "8%" },
  { Comp: MountainsSvg, side: "left", top: "42%" },
  { Comp: WavesSvg, side: "left", top: "74%" },
  { Comp: CompassSvg, side: "right", top: "12%" },
  { Comp: LayersSvg, side: "right", top: "40%" },
  { Comp: GridSvg, side: "right", top: "62%" },
  { Comp: PinSvg, side: "right", top: "84%" },
];

const features = [
  { Icon: MapIcon, title: "Interactive map", text: "Drop a pin or search any place — every answer is scoped to that exact location." },
  { Icon: SproutIcon, title: "Soil & terrain", text: "Soil type, terrain and land characteristics for construction, farming or planning." },
  { Icon: CloudIcon, title: "Weather & air", text: "Live and recent weather plus air quality, pulled for your selected coordinates." },
  { Icon: RouteIcon, title: "Roads & access", text: "Road networks, connectivity and infrastructure around any site." },
  { Icon: ShieldIcon, title: "Risk & suitability", text: "Flood risk and how suitable a plot is for building — grounded in real data." },
  { Icon: SparkIcon, title: "Transparent AI", text: "See the step-by-step reasoning and the exact sources behind every answer." },
];

const steps = [
  { n: "1", title: "Pick a location", text: "Click the map or search for any place." },
  { n: "2", title: "Ask a question", text: "Type what you want to know about the land." },
  { n: "3", title: "Get a sourced answer", text: "A location-aware, cited analysis in seconds." },
];

export default function Landing() {
  const root = useRef(null);

  useLayoutEffect(() => {
    if (prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      // Hero intro timeline (no ScrollTrigger — always plays)
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.from(".lp-nav", { y: -24, opacity: 0, duration: 0.6 })
        .from(".lp-badge", { y: 20, opacity: 0, duration: 0.5 }, "-=0.2")
        .from(".lp-hero-title", { y: 32, opacity: 0, duration: 0.7 }, "-=0.2")
        .from(".lp-hero-sub", { y: 24, opacity: 0, duration: 0.6 }, "-=0.4")
        .from(".lp-hero-cta .lp-btn", { y: 18, opacity: 0, stagger: 0.12, duration: 0.5 }, "-=0.3")
        .from(".lp-trust", { opacity: 0, duration: 0.5 }, "-=0.2")
        .from(".lp-hero-glow", { opacity: 0, scale: 0.85, duration: 1.2 }, 0);

      // Scroll reveals via batch — robust against StrictMode / stale positions.
      // Batch's onEnter fires for in-view elements on refresh AND on scroll,
      // so cards never get stranded at opacity 0.
      const revealGroup = (selector, vars) => {
        gsap.set(selector, { opacity: 0, y: vars.y ?? 36 });
        ScrollTrigger.batch(selector, {
          start: "top 88%",
          once: true,
          onEnter: (els) =>
            gsap.to(els, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out", stagger: vars.stagger ?? 0.1 }),
        });
      };
      revealGroup(".lp-eyebrow, .lp-section-title, .lp-section-lead", { y: 22, stagger: 0.08 });
      revealGroup(".lp-feature", { y: 42, stagger: 0.12 });
      revealGroup(".lp-step", { y: 32, stagger: 0.15 });
      revealGroup(".lp-cta-inner", { y: 30, stagger: 0 });

      // Floating side decorations — gentle drift + slow rotation.
      gsap.to(".lp-decor-item", {
        y: "+=16",
        duration: 3.5,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        stagger: { each: 0.5, from: "random" },
      });
      gsap.to(".lp-decor-item", {
        rotation: "+=8",
        duration: 9,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        stagger: { each: 0.7, from: "random" },
      });

      // Recompute trigger positions once layout/fonts settle.
      ScrollTrigger.refresh();
      requestAnimationFrame(() => ScrollTrigger.refresh());
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => ScrollTrigger.refresh());
      }
    }, root);

    return () => ctx.revert();
  }, []);

  return (
    <div className="lp" ref={root}>
      {/* Floating terrain / land-analysis decorations in the side gutters */}
      <div className="lp-decor" aria-hidden="true">
        {decorItems.map((d, i) => {
          const DecorSvg = d.Comp;
          return (
            <span
              key={i}
              className={`lp-decor-item lp-decor-${d.side}`}
              style={{ top: d.top }}
            >
              <DecorSvg />
            </span>
          );
        })}
      </div>

      {/* ── Hero ── */}
      <section className="lp-hero">
        <header className="lp-nav">
          <div className="lp-brand">
            <GlobeIcon size={26} />
            <span>TerraMind</span>
          </div>
          <nav className="lp-nav-actions">
            <a href="#overview" className="lp-nav-link lp-hide-sm">Features</a>
            <Link to="/login" className="lp-nav-link">Log in</Link>
            <Link to="/signup" className="lp-btn lp-btn-solid">Get started</Link>
          </nav>
        </header>

        <div className="lp-hero-inner">
          <span className="lp-badge">
            <SparkIcon size={15} />
            AI-powered geospatial intelligence
          </span>
          <h1 className="lp-hero-title">Understand any piece of land in seconds</h1>
          <p className="lp-hero-sub">
            TerraMind turns maps, live weather, soil and infrastructure data into
            clear, location-aware answers — grounded in real sources, and always
            about the exact place you choose.
          </p>
          <div className="lp-hero-cta">
            <Link to="/signup" className="lp-btn lp-btn-solid lp-btn-lg">
              Get started free <ArrowIcon />
            </Link>
            <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-lg">Log in</Link>
          </div>
          <p className="lp-trust">No setup required · Free to try · Built on open data sources</p>
        </div>

        <div className="lp-hero-glow" aria-hidden="true" />
      </section>

      {/* ── Features ── */}
      <section className="lp-section" id="overview">
        <div className="lp-container">
          <p className="lp-eyebrow">What it does</p>
          <h2 className="lp-section-title">Everything you need to read the land</h2>
          <p className="lp-section-lead">
            An expert land analyst in your browser. Ask in plain language and
            TerraMind combines geospatial records, live data and AI to answer —
            never describing somewhere else.
          </p>

          <div className="lp-features">
            {features.map((f) => {
              const FeatureIcon = f.Icon;
              return (
                <article className="lp-feature" key={f.title}>
                  <div className="lp-feature-icon">
                    <FeatureIcon />
                  </div>
                  <h3 className="lp-feature-title">{f.title}</h3>
                  <p className="lp-feature-text">{f.text}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="lp-section lp-section-alt">
        <div className="lp-container">
          <p className="lp-eyebrow">How it works</p>
          <h2 className="lp-section-title">Three steps to an answer</h2>

          <div className="lp-steps">
            {steps.map((s, i) => (
              <div className="lp-step" key={s.n}>
                <div className="lp-step-num">{s.n}</div>
                <h4 className="lp-step-title">{s.title}</h4>
                <p className="lp-step-text">{s.text}</p>
                {i < steps.length - 1 && <div className="lp-step-line" aria-hidden="true" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="lp-cta">
        <div className="lp-cta-inner">
          <h2 className="lp-cta-title">Ready to explore your land?</h2>
          <p className="lp-cta-text">
            Create a free account or log in to start analyzing any location.
          </p>
          <div className="lp-hero-cta">
            <Link to="/signup" className="lp-btn lp-btn-solid lp-btn-lg">
              Get started free <ArrowIcon />
            </Link>
            <Link to="/login" className="lp-btn lp-btn-ghost lp-btn-lg">Log in</Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lp-footer">
        <div className="lp-brand">
          <GlobeIcon size={22} />
          <span>TerraMind</span>
        </div>
        <span className="lp-footer-copy">© 2026 TerraMind · Team Mischief Managed</span>
      </footer>
    </div>
  );
}
