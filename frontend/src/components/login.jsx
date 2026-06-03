import { useState, useEffect, useRef } from "react";

const VALID_USER = "juhisaxena";
const VALID_PASS = "Abc12345";

const DataParticle = ({ style }) => (
  <div style={style} className="data-particle" />
);

export default function VDFLogin({ onLoginSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [focused, setFocused] = useState(null);
  const [particles, setParticles] = useState([]);
  const [typedText, setTypedText] = useState("");
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);

  const taglines = [
    "Synthesize Reality.",
    "Generate at Scale.",
    "Stream. Shape. Ship.",
    "Data, Reimagined.",
  ];
  const [tagIdx, setTagIdx] = useState(0);

  // Typewriter effect
  useEffect(() => {
    let i = 0;
    const target = taglines[tagIdx];
    setTypedText("");
    const interval = setInterval(() => {
      setTypedText(target.slice(0, i + 1));
      i++;
      if (i >= target.length) {
        clearInterval(interval);
        setTimeout(() => setTagIdx((t) => (t + 1) % taglines.length), 2000);
      }
    }, 60);
    return () => clearInterval(interval);
  }, [tagIdx]);

  // Floating particles
  useEffect(() => {
    const p = Array.from({ length: 28 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 20 + 15,
      opacity: Math.random() * 0.4 + 0.08,
      color: i % 3 === 0 ? "#f97316" : i % 3 === 1 ? "#fb923c" : "#d1d5db",
      delay: Math.random() * 5,
    }));
    setParticles(p);
  }, []);

  // Mouse parallax
  useEffect(() => {
    const handler = (e) => {
      setMousePos({
        x: (e.clientX / window.innerWidth - 0.5) * 20,
        y: (e.clientY / window.innerHeight - 0.5) * 20,
      });
    };
    window.addEventListener("mousemove", handler);
    return () => window.removeEventListener("mousemove", handler);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1200));
    if (username === VALID_USER && password === VALID_PASS) {
  setSuccess(true);

  setTimeout(() => {
    onLoginSuccess();
  }, 1500);
} else {
      setError("Invalid credentials. Access denied.");
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          background: #0d0d0d;
          font-family: 'Syne', sans-serif;
          overflow: hidden;
          height: 100vh;
        }

        .vdf-root {
          min-height: 100vh;
          background: #0d0d0d;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          overflow: hidden;
        }

        /* Animated grid background */
        .grid-bg {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(249,115,22,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(249,115,22,0.06) 1px, transparent 1px);
          background-size: 48px 48px;
          animation: gridDrift 12s linear infinite;
        }
        @keyframes gridDrift {
          0% { transform: translate(0,0); }
          100% { transform: translate(48px, 48px); }
        }

        /* Radial glow */
        .glow-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          pointer-events: none;
        }
        .glow-orb-1 {
          width: 500px; height: 500px;
          background: radial-gradient(circle, rgba(249,115,22,0.18) 0%, transparent 70%);
          top: -120px; left: -100px;
          animation: orbFloat1 8s ease-in-out infinite;
        }
        .glow-orb-2 {
          width: 400px; height: 400px;
          background: radial-gradient(circle, rgba(251,146,60,0.12) 0%, transparent 70%);
          bottom: -100px; right: -80px;
          animation: orbFloat2 10s ease-in-out infinite;
        }
        @keyframes orbFloat1 {
          0%,100% { transform: translate(0,0); }
          50% { transform: translate(30px, 40px); }
        }
        @keyframes orbFloat2 {
          0%,100% { transform: translate(0,0); }
          50% { transform: translate(-20px, -30px); }
        }

        /* Floating data particles */
        .data-particle {
          position: absolute;
          border-radius: 50%;
          pointer-events: none;
          animation: floatUp linear infinite;
        }
        @keyframes floatUp {
          0% { transform: translateY(100vh) scale(0); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateY(-100px) scale(1); opacity: 0; }
        }

        /* Main card */
        .login-card {
          position: relative;
          z-index: 10;
          width: 460px;
          padding: 52px 48px 44px;
          background: rgba(17,17,17,0.92);
          border: 1px solid rgba(249,115,22,0.2);
          border-radius: 24px;
          backdrop-filter: blur(20px);
          box-shadow:
            0 0 0 1px rgba(249,115,22,0.08),
            0 32px 80px rgba(0,0,0,0.6),
            inset 0 1px 0 rgba(255,255,255,0.04);
          animation: cardIn 0.7s cubic-bezier(0.16,1,0.3,1) both;
          transition: transform 0.1s ease;
        }
        @keyframes cardIn {
          0% { opacity: 0; transform: translateY(32px) scale(0.96); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }

        /* Top badge */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: rgba(249,115,22,0.12);
          border: 1px solid rgba(249,115,22,0.3);
          border-radius: 999px;
          padding: 4px 12px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          color: #f97316;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          margin-bottom: 28px;
          animation: fadeIn 0.5s 0.3s both;
        }
        .badge-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: #f97316;
          animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
          0%,100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.8); }
        }

        /* Logo */
        .logo-row {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 8px;
          animation: fadeIn 0.5s 0.4s both;
        }
        .logo-icon {
          width: 48px; height: 48px;
          background: linear-gradient(135deg, #f97316, #ea580c);
          border-radius: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 20px;
          color: #fff;
          letter-spacing: -1px;
          box-shadow: 0 8px 24px rgba(249,115,22,0.4);
          position: relative;
          overflow: hidden;
        }
        .logo-icon::after {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg, rgba(255,255,255,0.2), transparent);
          border-radius: inherit;
        }
        .logo-text {
          font-size: 28px;
          font-weight: 800;
          color: #fff;
          letter-spacing: -0.5px;
        }
        .logo-text span { color: #f97316; }

        /* Tagline */
        .tagline {
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          color: #6b7280;
          margin-bottom: 36px;
          min-height: 20px;
          animation: fadeIn 0.5s 0.5s both;
        }
        .tagline .cursor {
          display: inline-block;
          width: 2px; height: 13px;
          background: #f97316;
          margin-left: 2px;
          vertical-align: middle;
          animation: blink 0.8s step-end infinite;
        }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

        /* Section label */
        .section-label {
          font-size: 11px;
          font-weight: 600;
          color: #4b5563;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          font-family: 'JetBrains Mono', monospace;
          margin-bottom: 20px;
          animation: fadeIn 0.5s 0.55s both;
        }

        /* Input group */
        .input-group {
          margin-bottom: 16px;
          animation: fadeIn 0.5s both;
        }
        .input-group:nth-child(1) { animation-delay: 0.6s; }
        .input-group:nth-child(2) { animation-delay: 0.65s; }

        .input-label {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: #6b7280;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          font-family: 'JetBrains Mono', monospace;
          margin-bottom: 8px;
        }

        .input-wrap {
          position: relative;
        }
        .input-wrap input {
          width: 100%;
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(75,85,99,0.5);
          border-radius: 12px;
          padding: 13px 44px 13px 16px;
          color: #f9fafb;
          font-family: 'JetBrains Mono', monospace;
          font-size: 14px;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
        }
        .input-wrap input:focus {
          border-color: rgba(249,115,22,0.6);
          background: rgba(249,115,22,0.04);
          box-shadow: 0 0 0 3px rgba(249,115,22,0.1);
        }
        .input-wrap input::placeholder { color: #374151; }
        .input-icon {
          position: absolute;
          right: 14px;
          top: 50%;
          transform: translateY(-50%);
          color: #4b5563;
          cursor: pointer;
          transition: color 0.2s;
          font-size: 16px;
          line-height: 1;
        }
        .input-icon:hover { color: #f97316; }

        /* Focused indicator */
        .input-focused-bar {
          position: absolute;
          bottom: 0;
          left: 50%;
          transform: translateX(-50%);
          height: 2px;
          border-radius: 0 0 12px 12px;
          background: linear-gradient(90deg, #f97316, #fb923c);
          transition: width 0.3s cubic-bezier(0.16,1,0.3,1);
          width: 0;
        }
        .input-focused-bar.active { width: 100%; }

        /* Error */
        .error-msg {
          display: flex;
          align-items: center;
          gap: 8px;
          background: rgba(239,68,68,0.08);
          border: 1px solid rgba(239,68,68,0.25);
          border-radius: 10px;
          padding: 10px 14px;
          color: #f87171;
          font-size: 12px;
          font-family: 'JetBrains Mono', monospace;
          margin-bottom: 16px;
          animation: shake 0.4s ease;
        }
        @keyframes shake {
          0%,100% { transform: translateX(0); }
          20% { transform: translateX(-6px); }
          40% { transform: translateX(6px); }
          60% { transform: translateX(-4px); }
          80% { transform: translateX(4px); }
        }

        /* Login button */
        .login-btn {
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, #f97316, #ea580c);
          border: none;
          border-radius: 12px;
          color: #fff;
          font-family: 'Syne', sans-serif;
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0.04em;
          cursor: pointer;
          position: relative;
          overflow: hidden;
          transition: transform 0.15s, box-shadow 0.15s;
          box-shadow: 0 8px 24px rgba(249,115,22,0.35);
          margin-bottom: 8px;
          animation: fadeIn 0.5s 0.75s both;
        }
        .login-btn::before {
          content: '';
          position: absolute;
          inset: 0;
          background: linear-gradient(135deg, rgba(255,255,255,0.15), transparent);
          transition: opacity 0.2s;
        }
        .login-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 32px rgba(249,115,22,0.45); }
        .login-btn:active { transform: translateY(0); }
        .login-btn:disabled { opacity: 0.7; cursor: not-allowed; transform: none; }

        .btn-content {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }

        .spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Footer */
        .card-footer {
          margin-top: 28px;
          padding-top: 20px;
          border-top: 1px solid rgba(255,255,255,0.05);
          display: flex;
          align-items: center;
          justify-content: space-between;
          animation: fadeIn 0.5s 0.8s both;
        }
        .footer-tag {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          color: #374151;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .footer-tag .dot { width: 5px; height: 5px; border-radius: 50%; background: #22c55e; }
        .footer-version {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          color: #374151;
        }

        /* Success overlay */
        .success-overlay {
          position: absolute;
          inset: 0;
          background: rgba(17,17,17,0.97);
          border-radius: 24px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          z-index: 20;
          animation: fadeIn 0.4s ease;
        }
        .success-icon {
          width: 64px; height: 64px;
          background: linear-gradient(135deg, #22c55e, #16a34a);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          box-shadow: 0 8px 32px rgba(34,197,94,0.4);
          animation: popIn 0.4s cubic-bezier(0.16,1,0.3,1);
        }
        @keyframes popIn {
          0% { transform: scale(0); }
          100% { transform: scale(1); }
        }
        .success-title {
          font-size: 22px;
          font-weight: 800;
          color: #fff;
        }
        .success-sub {
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          color: #6b7280;
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* Right side info panel */
        .side-panel {
          position: absolute;
          right: calc(50% - 440px);
          bottom: 40px;
          z-index: 5;
          display: flex;
          flex-direction: column;
          gap: 10px;
          animation: fadeIn 0.7s 1s both;
        }
        .side-stat {
          display: flex;
          align-items: center;
          gap: 10px;
          background: rgba(17,17,17,0.8);
          border: 1px solid rgba(75,85,99,0.3);
          border-radius: 10px;
          padding: 10px 16px;
          backdrop-filter: blur(10px);
        }
        .side-stat-num {
          font-family: 'JetBrains Mono', monospace;
          font-size: 18px;
          font-weight: 500;
          color: #f97316;
        }
        .side-stat-label {
          font-size: 11px;
          color: #6b7280;
          font-family: 'JetBrains Mono', monospace;
        }

        /* Top corner label */
        .top-label {
          position: absolute;
          top: 40px;
          left: 40px;
          z-index: 10;
          display: flex;
          align-items: center;
          gap: 10px;
          animation: fadeIn 0.6s 0.2s both;
        }
        .top-label-text {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #4b5563;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
      `}</style>

      <div className="vdf-root" ref={containerRef}>
        <div className="grid-bg" />
        <div className="glow-orb glow-orb-1" style={{ transform: `translate(${mousePos.x * 0.5}px, ${mousePos.y * 0.5}px)` }} />
        <div className="glow-orb glow-orb-2" style={{ transform: `translate(${-mousePos.x * 0.3}px, ${-mousePos.y * 0.3}px)` }} />

        {particles.map((p) => (
          <div
            key={p.id}
            className="data-particle"
            style={{
              left: `${p.x}%`,
              width: p.size,
              height: p.size,
              background: p.color,
              opacity: p.opacity,
              animationDuration: `${p.speed}s`,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}

        <div className="top-label">
          <span className="top-label-text">VDF // Virtual Data Factory</span>
        </div>

        <div
          className="login-card"
          style={{ transform: `perspective(1000px) rotateX(${mousePos.y * 0.02}deg) rotateY(${mousePos.x * 0.02}deg)` }}
        >
          {success && (
            <div className="success-overlay">
              <div className="success-icon">✓</div>
              <div className="success-title">Access Granted</div>
              <div className="success-sub">Welcome back, {VALID_USER}</div>
            </div>
          )}

          <div className="badge">
            <div className="badge-dot" />
            Secure Access Portal
          </div>

          <div className="logo-row">
            <div className="logo-icon">VDF</div>
            <div className="logo-text">Virtual<span>Data</span></div>
          </div>

          <div className="tagline">
            {typedText}<span className="cursor" />
          </div>

          <div className="section-label">— Authenticate</div>

          <form onSubmit={handleLogin}>
            <div className="input-group">
              <div className="input-label">
                <span>⊙</span> Username
              </div>
              <div className="input-wrap">
                <input
                  type="text"
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onFocus={() => setFocused("user")}
                  onBlur={() => setFocused(null)}
                  autoComplete="username"
                />
                <span className="input-icon">◈</span>
                <div className={`input-focused-bar ${focused === "user" ? "active" : ""}`} />
              </div>
            </div>

            <div className="input-group">
              <div className="input-label">
                <span>⊛</span> Password
              </div>
              <div className="input-wrap">
                <input
                  type={showPass ? "text" : "password"}
                  placeholder="Enter password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocused("pass")}
                  onBlur={() => setFocused(null)}
                  autoComplete="current-password"
                />
                <span className="input-icon" onClick={() => setShowPass(!showPass)}>
                  {showPass ? "◉" : "◎"}
                </span>
                <div className={`input-focused-bar ${focused === "pass" ? "active" : ""}`} />
              </div>
            </div>

            {error && (
              <div className="error-msg">
                <span>⚠</span> {error}
              </div>
            )}

            <button className="login-btn" type="submit" disabled={loading}>
              <div className="btn-content">
                {loading ? (
                  <><div className="spinner" /> Authenticating…</>
                ) : (
                  <><span>⟶</span> Enter the Factory</>
                )}
              </div>
            </button>
          </form>

          <div className="card-footer">
            <div className="footer-tag">
              <div className="dot" />
              System Online
            </div>
            <div className="footer-version">v2.4.1 · SDK Studio</div>
          </div>
        </div>

        <div className="side-panel">
          {[
            { num: "10M+", label: "Records generated" },
            { num: "4", label: "Connectors active" },
          ].map((s) => (
            <div className="side-stat" key={s.label}>
              <div className="side-stat-num">{s.num}</div>
              <div className="side-stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
