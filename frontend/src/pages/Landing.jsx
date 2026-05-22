import { Link } from "react-router-dom";
import {
  Workflow,
  GitBranch,
  Zap,
  CheckCircle2,
  ArrowRight,
  ChevronsUp,
} from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-heading">
      {/* Nav */}
      <nav className="tf-marketing-nav sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <div className="w-7 h-7 rounded-sm bg-[#0055ff] grid place-items-center">
              <Workflow size={16} className="text-white" />
            </div>
            <span className="font-semibold tracking-tight text-[15px]">TaskFlow</span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm text-neutral-400">
            <a href="#product" className="hover:text-white transition">Product</a>
            <a href="#solutions" className="hover:text-white transition">Solutions</a>
            <a href="#pricing" className="hover:text-white transition">Pricing</a>
            <a href="#resources" className="hover:text-white transition">Resources</a>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-sm text-neutral-300 hover:text-white transition px-3 py-1.5"
              data-testid="landing-signin-link"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="tf-btn-primary text-sm font-medium px-4 py-2 rounded-md"
              data-testid="landing-get-started-btn"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 tf-dotgrid opacity-60 pointer-events-none" />
        <div className="absolute inset-x-0 -top-40 h-[500px] bg-[radial-gradient(ellipse_at_top,_rgba(0,85,255,0.18),_transparent_60%)] pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono tracking-wider uppercase px-3 py-1 rounded-full border border-[#262626] bg-[#111] text-neutral-300">
            <span className="tf-dot bg-[#0055ff]" /> v3.0 now live
          </span>
          <h1 className="font-heading mt-6 text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tighter leading-[1.02]">
            Manage projects with
            <br />
            <span className="text-[#0055ff]">ruthless efficiency.</span>
          </h1>
          <p className="mt-6 text-neutral-400 text-base sm:text-lg max-w-2xl mx-auto">
            The high-performance project management tool built for modern engineering teams.
            Zero fluff, absolute control.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/register"
              className="tf-btn-primary font-medium text-sm px-6 py-3 rounded-md inline-flex items-center justify-center gap-2"
              data-testid="hero-get-started-btn"
            >
              Get Started — Free <ArrowRight size={16} />
            </Link>
            <a
              href="#features"
              className="font-medium text-sm px-6 py-3 rounded-md border border-[#2a2a2a] hover:border-neutral-500 transition inline-flex items-center justify-center"
              data-testid="hero-book-demo-btn"
            >
              Book a Demo
            </a>
          </div>

          {/* Product mockup */}
          <div className="mt-16 mx-auto max-w-5xl">
            <ProductPreview />
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative border-t border-[#1a1a1a] bg-[#0a0a0a]">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-24">
          <div className="max-w-2xl">
            <h2 className="font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
              Engineering-first workflows
            </h2>
            <p className="text-neutral-400 mt-3 text-sm sm:text-base">
              Built by developers, for developers. Every feature is optimized for speed and clarity.
            </p>
          </div>

          <div className="mt-12 grid md:grid-cols-3 gap-px bg-[#1a1a1a] border border-[#1a1a1a] rounded-md overflow-hidden">
            <FeatureCard
              icon={<Workflow size={18} className="text-[#0055ff]" />}
              title="Kanban Boards"
              body="Visual flow for every phase of your project. High-density cards with inline editing and custom priority states."
              footer={
                <div className="flex items-center gap-1.5 mt-6">
                  <span className="h-1.5 w-8 rounded bg-neutral-700" />
                  <span className="h-1.5 w-8 rounded bg-[#0055ff]" />
                  <span className="h-1.5 w-8 rounded bg-[#10b981]" />
                </div>
              }
            />
            <FeatureCard
              icon={<GitBranch size={18} className="text-[#0055ff]" />}
              title="Sprint Tracking"
              body="Iteration management with automated burn-down charts and velocity tracking. Keep your cycle time under control."
              footer={
                <div className="mt-6 text-[11px] font-mono tracking-wider uppercase text-neutral-500">
                  98% on-time delivery
                </div>
              }
            />
            <FeatureCard
              icon={<Zap size={18} className="text-[#0055ff]" />}
              title="Real-time Sync"
              body="Multi-user collaboration with zero-latency synchronization. See changes as they happen across all devices instantly."
              footer={
                <div className="mt-6 inline-flex items-center gap-1.5 text-[11px] font-mono tracking-wider uppercase text-neutral-500">
                  <span className="tf-dot bg-[#10b981]" /> systems operational
                </div>
              }
            />
          </div>
        </div>
      </section>

      {/* CTA strip */}
      <section className="bg-[#06070a] border-t border-[#1a1a1a]">
        <div className="max-w-4xl mx-auto px-6 py-20 text-center">
          <h3 className="font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
            Ready to ship faster?
          </h3>
          <Link
            to="/register"
            className="tf-btn-primary mt-8 inline-flex items-center gap-2 font-medium px-7 py-3 rounded-md"
            data-testid="cta-join-teams-btn"
          >
            Join 10,000+ Teams <ArrowRight size={16} />
          </Link>
          <p className="text-neutral-500 text-xs mt-4 font-mono tracking-wide">
            No credit card required · 14-day free trial on Pro plans.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#1a1a1a]">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 flex flex-col sm:flex-row justify-between text-xs text-neutral-500 gap-3">
          <div className="flex items-center gap-3">
            <span className="font-mono">TaskFlow</span>
            <span>© 2026 TaskFlow Inc. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-neutral-300 transition">Privacy Policy</a>
            <a href="#" className="hover:text-neutral-300 transition">Terms of Service</a>
            <a href="#" className="hover:text-neutral-300 transition">Status</a>
            <a href="#" className="hover:text-neutral-300 transition">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, body, footer }) {
  return (
    <div className="bg-[#0a0a0a] p-7 lg:p-8 group hover:bg-[#0d0d0d] transition">
      <div className="w-9 h-9 grid place-items-center rounded-sm bg-[#0055ff]/10 border border-[#0055ff]/20">
        {icon}
      </div>
      <h4 className="font-heading text-lg font-medium mt-5 tracking-tight">{title}</h4>
      <p className="text-neutral-400 text-sm leading-relaxed mt-2">{body}</p>
      {footer}
    </div>
  );
}

function ProductPreview() {
  // A stylized mockup of the kanban board (so landing doesn't depend on a screenshot)
  return (
    <div className="relative rounded-lg border border-[#1f1f1f] bg-[#0d0d0d] overflow-hidden shadow-[0_30px_80px_-30px_rgba(0,85,255,0.4)]">
      <div className="h-9 flex items-center gap-1.5 px-4 border-b border-[#1f1f1f] bg-[#0a0a0a]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-4 font-mono text-[11px] text-neutral-500">linearsync / core-platform</span>
      </div>
      <div className="grid grid-cols-12 min-h-[360px]">
        <div className="col-span-3 border-r border-[#1f1f1f] bg-[#070707] p-4 hidden md:block">
          <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-600 mb-3">workspace</div>
          {["Home", "My Issues", "Projects", "Views", "Settings"].map((i, idx) => (
            <div
              key={i}
              className={`text-xs py-1.5 px-2 rounded-sm ${idx === 1 ? "bg-white/5 text-white" : "text-neutral-500"}`}
            >
              {i}
            </div>
          ))}
        </div>
        <div className="col-span-12 md:col-span-9 p-5 grid grid-cols-3 gap-3">
          {[
            { name: "Backlog", count: 12, color: "#9ca3af" },
            { name: "In Progress", count: 3, color: "#0055ff" },
            { name: "Done", count: 24, color: "#10b981" },
          ].map((c) => (
            <div key={c.name} className="min-w-0">
              <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-3">
                <span className="tf-dot" style={{ background: c.color }} /> {c.name} <span className="text-neutral-700">{c.count}</span>
              </div>
              <div className="space-y-2">
                <MockCard id="CORE-256" title="Optimize SVG rendering" tag="PERF" />
                <MockCard id="CORE-254" title="Webhooks for CI/CD" tag="FEATURE" urgent />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MockCard({ id, title, tag, urgent }) {
  return (
    <div className="rounded-md border border-[#1f1f1f] bg-[#0a0a0a] p-3 hover:border-[#2a2a2a] transition">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] tracking-wider text-neutral-500">{id}</span>
        {urgent ? <ChevronsUp size={12} className="text-[#ef4444]" /> : <CheckCircle2 size={12} className="text-neutral-700" />}
      </div>
      <div className="text-xs text-neutral-200 mt-1.5 leading-snug">{title}</div>
      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 rounded-sm bg-[#0055ff]/10 text-[#79a3ff]">{tag}</span>
        <span className="w-4 h-4 rounded-full bg-neutral-700" />
      </div>
    </div>
  );
}
