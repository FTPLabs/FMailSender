import { useState, useEffect, useRef } from "react";
import { C, Card, SectionHead, Dot, I } from "./shared";

function StatCard({ label, value, sub, color, icon }: { label: string; value: number; sub: string; color: string; icon: React.ReactNode }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const dur = 1200; const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - t0) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.floor(ease * value).toLocaleString("ru");
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, []); // ← fixed deps: only animate once on mount
  return (
    <div style={{ background: C.surface, border: `1px solid ${color}22`, borderRadius: 14, padding: "18px 20px", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at top left, ${color}08, transparent 60%)`, pointerEvents: "none" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: `${color}aa` }}>{label}</span>
        <span style={{ color, opacity: 0.6 }}>{icon}</span>
      </div>
      <div style={{ fontSize: 30, fontWeight: 700, color, fontVariantNumeric: "tabular-nums", marginBottom: 3 }}><span ref={ref}>0</span></div>
      <div style={{ fontSize: 11, color: C.textMuted }}>{sub}</div>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${color}55, transparent)` }} />
    </div>
  );
}

const LOG_ITEMS = [
  { ok: true,  to: "user@gmail.com",     from: "smtp1@fmail.shop", time: "14:22:03" },
  { ok: true,  to: "client@yandex.ru",   from: "smtp2@fmail.shop", time: "14:22:04" },
  { ok: false, to: "bad@@invalid.com",   from: "smtp3@fmail.shop", time: "14:22:05", err: "AUTH_FAIL" },
  { ok: true,  to: "work@outlook.com",   from: "smtp1@fmail.shop", time: "14:22:06" },
  { ok: true,  to: "info@company.ru",    from: "smtp4@fmail.shop", time: "14:22:07" },
  { ok: true,  to: "hello@mail.ru",      from: "smtp2@fmail.shop", time: "14:22:08" },
  { ok: false, to: "none@badhost.xyz",   from: "smtp3@fmail.shop", time: "14:22:09", err: "CONN_TIMEOUT" },
  { ok: true,  to: "order@shop.ru",      from: "smtp1@fmail.shop", time: "14:22:10" },
];

export function TabDashboard() {
  const [prog, setProg] = useState(37.4);
  // Slow update — every 3 seconds, +0.1%
  useEffect(() => {
    const id = setInterval(() => setProg(p => Math.min(p + 0.1, 100)), 3000);
    return () => clearInterval(id);
  }, []);

  const total = 12450;
  const sent  = Math.floor(prog / 100 * total);

  return (
    <div style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 14, height: "100%", overflowY: "auto" }}>
      {/* Stat cards — fixed values, animate only on mount */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
        <StatCard label="Всего отправлено" value={4607}  sub="сегодня"           color={C.purple} icon={I.lightning} />
        <StatCard label="Успешно"          value={4430}  sub="96.2% доставка"    color={C.green}  icon={I.check} />
        <StatCard label="Ошибок"           value={177}   sub="bounce + auth"      color={C.red}    icon={I.x} />
        <StatCard label="Скорость"         value={847}   sub="писем / мин"        color={C.blue}   icon={I.arrow} />
      </div>

      {/* Progress */}
      <Card>
        <SectionHead title="Прогресс рассылки" right={
          <span style={{ fontSize: 12, fontFamily: "monospace", color: C.purple }}>{prog.toFixed(1)}%</span>
        }/>
        <div style={{ padding: "14px 18px" }}>
          <div style={{ height: 6, borderRadius: 99, background: C.faint, overflow: "hidden", marginBottom: 8 }}>
            <div style={{ height: "100%", width: `${prog}%`, background: "linear-gradient(90deg,#7c3aed,#a78bfa)", borderRadius: 99, transition: "width 0.5s ease" }}/>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.textMuted }}>
            <span>{sent.toLocaleString("ru")} / {total.toLocaleString("ru")} писем</span>
            <span>~{Math.max(0, Math.ceil((total - sent) / 847))} мин. осталось</span>
          </div>
        </div>
      </Card>

      {/* Bottom 2-col */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, flex: 1 }}>
        {/* Accounts mini */}
        <Card>
          <SectionHead title="Аккаунты" />
          <div style={{ padding: "0 18px" }}>
            {[
              { e: "smtp1@fmail.shop", n: 1240, ok: true  },
              { e: "smtp2@fmail.shop", n: 983,  ok: true  },
              { e: "smtp3@fmail.shop", n: 756,  ok: true  },
              { e: "smtp4@fmail.shop", n: 312,  ok: false },
            ].map((a, i, arr) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <Dot color={a.ok ? C.green : C.amber} />
                <span style={{ flex: 1, fontSize: 11, color: C.text, fontFamily: "monospace" }}>{a.e}</span>
                <span style={{ fontSize: 11, color: C.purple, fontFamily: "monospace", fontWeight: 600 }}>{a.n.toLocaleString("ru")}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Live log */}
        <Card style={{ display: "flex", flexDirection: "column" }}>
          <SectionHead title="Лог" right={
            <span style={{ fontSize: 10, color: C.green, display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, display: "inline-block", animation: "blink 1.4s infinite" }}/>Live
            </span>
          }/>
          <div style={{ flex: 1, overflowY: "auto", padding: "8px 18px 14px" }}>
            {LOG_ITEMS.map((l, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 11, fontFamily: "monospace", borderBottom: i < LOG_ITEMS.length - 1 ? `1px solid ${C.border}44` : "none" }}>
                <span style={{ color: l.ok ? C.green : C.red, flexShrink: 0 }}>{l.ok ? I.check : I.x}</span>
                <span style={{ color: C.textMuted, flexShrink: 0 }}>{l.time}</span>
                <span style={{ flex: 1, color: l.ok ? C.text : C.red, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {l.ok ? `${l.to} ← ${l.from}` : `${l.to} × ${l.err}`}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
