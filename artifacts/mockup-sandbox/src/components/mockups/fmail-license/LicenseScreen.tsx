import { useState, useEffect, useRef } from "react";

/* ── SVG Icons ──────────────────────────────────────────────────────────── */
const MailIcon = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <rect x="2" y="5" width="18" height="13" rx="2" stroke="white" strokeWidth="1.5"/>
    <path d="M2 8.5l9 6 9-6" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const SpinnerIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ animation: "spin 0.7s linear infinite" }}>
    <circle cx="7" cy="7" r="5.5" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5"/>
    <path d="M7 1.5A5.5 5.5 0 0 1 12.5 7" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const CheckIcon = () => (
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
    <path
      d="M6 14l6 6 10-10"
      stroke="#22c55e"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray="36"
      style={{ animation: "drawCheck 0.5s ease 0.1s both" }}
    />
  </svg>
);

const KeyIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ opacity: 0.4 }}>
    <circle cx="5" cy="7" r="3" stroke="currentColor" strokeWidth="1.25"/>
    <path d="M8 7h4.5M10.5 5.5V7M12.5 5.5V7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/>
  </svg>
);

/* ── Types ──────────────────────────────────────────────────────────────── */
type Phase = "idle" | "loading" | "done";

/* ── Helpers ────────────────────────────────────────────────────────────── */
function formatKey(raw: string): string {
  const clean = raw.toUpperCase().replace(/[^A-Z0-9]/g, "");
  const prefix = "FMSND";
  const body = clean.startsWith(prefix) ? clean.slice(prefix.length) : clean;
  const chunks: string[] = [];
  for (let i = 0; i < Math.min(body.length, 24); i += 6) {
    chunks.push(body.slice(i, i + 6));
  }
  return chunks.length ? `${prefix}-${chunks.join("-")}` : prefix;
}

/* ── Component ──────────────────────────────────────────────────────────── */
export function LicenseScreen() {
  const [key, setKey] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [step, setStep] = useState("");
  const [prog, setProg] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const isValid = key.length >= 29; // FMSND-AAAAAA-BBBBBB-CCCCCC-DDDDDD = 29

  function handleActivate() {
    if (!isValid || phase !== "idle") return;
    setPhase("loading");
    setProg(0);

    const stages = [
      { t: 350,  p: 20,  msg: "Генерация HWID…" },
      { t: 850,  p: 50,  msg: "Проверка ключа…" },
      { t: 1500, p: 78,  msg: "Активация на сервере…" },
      { t: 2100, p: 95,  msg: "Сохранение лицензии…" },
      { t: 2600, p: 100, msg: "Готово" },
    ];
    stages.forEach(({ t, p, msg }) => {
      setTimeout(() => {
        setProg(p);
        setStep(msg);
        if (p === 100) setTimeout(() => setPhase("done"), 250);
      }, t);
    });
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleActivate();
  }

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    setKey(formatKey(e.target.value));
  }

  return (
    <div style={{
      height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "#080b14",
      fontFamily: "'Inter', system-ui, sans-serif",
    }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes drawCheck { from { stroke-dashoffset: 36; } to { stroke-dashoffset: 0; } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        input::placeholder { color: rgba(255,255,255,0.2); }
        input:focus { border-color: rgba(139,92,246,0.6) !important; outline: none; }
      `}</style>

      <div style={{
        width: 380,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 20,
        padding: "40px 36px",
        animation: "fadeUp 0.5s cubic-bezier(0.16,1,0.3,1)",
        backdropFilter: "blur(24px)",
      }}>
        {phase !== "done" ? (
          <>
            {/* Logo */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 32 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: "0 0 20px rgba(124,58,237,0.4)",
              }}>
                <MailIcon />
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0" }}>FMail Sender</div>
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>Активация лицензии</div>
              </div>
            </div>

            {/* Input */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 11, fontWeight: 500, color: "rgba(255,255,255,0.35)", letterSpacing: "0.07em", textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                Ключ
              </label>
              <div style={{ position: "relative" }}>
                <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "white", pointerEvents: "none" }}>
                  <KeyIcon />
                </span>
                <input
                  ref={inputRef}
                  value={key}
                  onChange={handleInput}
                  onKeyDown={handleKeyDown}
                  disabled={phase === "loading"}
                  placeholder="FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
                  spellCheck={false}
                  style={{
                    width: "100%", padding: "11px 14px 11px 34px",
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 10, color: "#e2e8f0",
                    fontSize: 13, fontFamily: "monospace",
                    letterSpacing: "0.04em",
                    transition: "border-color 0.15s",
                    opacity: phase === "loading" ? 0.5 : 1,
                  }}
                />
              </div>
            </div>

            {/* Progress */}
            {phase === "loading" && (
              <div style={{ marginBottom: 16, animation: "fadeIn 0.2s ease" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11 }}>
                  <span style={{ color: "rgba(255,255,255,0.35)" }}>{step}</span>
                  <span style={{ color: "#8b5cf6", fontFamily: "monospace" }}>{prog}%</span>
                </div>
                <div style={{ height: 3, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 99,
                    width: `${prog}%`,
                    background: "linear-gradient(90deg,#7c3aed,#a78bfa)",
                    transition: "width 0.4s cubic-bezier(0.4,0,0.2,1)",
                  }}/>
                </div>
              </div>
            )}

            {/* Button */}
            <button
              onClick={handleActivate}
              disabled={!isValid || phase === "loading"}
              style={{
                width: "100%", padding: "11px",
                borderRadius: 10, fontSize: 13, fontWeight: 600,
                cursor: isValid && phase === "idle" ? "pointer" : "not-allowed",
                background: isValid ? "linear-gradient(135deg,#7c3aed,#4f46e5)" : "rgba(255,255,255,0.05)",
                border: `1px solid ${isValid ? "rgba(139,92,246,0.5)" : "rgba(255,255,255,0.06)"}`,
                color: isValid ? "#fff" : "rgba(255,255,255,0.25)",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                transition: "all 0.15s",
                boxShadow: isValid && phase === "idle" ? "0 0 16px rgba(124,58,237,0.3)" : "none",
              }}
            >
              {phase === "loading" && <SpinnerIcon />}
              {phase === "loading" ? "Активация…" : "Активировать"}
            </button>

            <div style={{ marginTop: 20, textAlign: "center", fontSize: 11, color: "rgba(255,255,255,0.2)" }}>
              Нет ключа?{" "}
              <span style={{ color: "#8b5cf6", cursor: "pointer" }}>
                Купить на fmail.shop
              </span>
            </div>
          </>
        ) : (
          /* Success */
          <div style={{ textAlign: "center", animation: "fadeUp 0.4s ease" }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%", margin: "0 auto 20px",
              background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <CheckIcon />
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0", marginBottom: 6 }}>Лицензия активирована</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginBottom: 28 }}>
              Тариф: <span style={{ color: "#8b5cf6" }}>LIFETIME</span>
            </div>
            <button
              onClick={() => { setPhase("idle"); setKey(""); setProg(0); }}
              style={{
                padding: "10px 28px", borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: "pointer",
                background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                border: "1px solid rgba(139,92,246,0.5)", color: "#fff",
              }}
            >
              Войти →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
