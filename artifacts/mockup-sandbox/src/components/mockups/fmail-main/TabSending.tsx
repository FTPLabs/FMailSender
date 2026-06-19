import { useState, useEffect, useRef } from "react";
import { C, Card, Btn, Dot, SectionHead, I } from "./shared";

type LogEntry = { ok: boolean; time: string; msg: string };
type Status = "idle" | "running" | "paused";

function genTime() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2, "0")).join(":");
}
function genLog(i: number): LogEntry {
  const emails = ["user@gmail.com", "client@yandex.ru", "work@outlook.com", "order@shop.ru", "info@co.ru"];
  const accs   = ["smtp1@fmail.shop", "smtp2@fmail.shop", "smtp3@fmail.shop"];
  const ok     = Math.random() > 0.07;
  return {
    ok,
    time: genTime(),
    msg: ok
      ? `${emails[i % emails.length]} ← ${accs[i % accs.length]}`
      : `${emails[i % emails.length]} × AUTH_FAIL`,
  };
}

export function TabSending() {
  const [status, setStatus] = useState<Status>("paused");
  const [prog,   setProg]   = useState(37.4);
  const [logs,   setLogs]   = useState<LogEntry[]>([
    { ok: true,  time: "14:21:55", msg: "user@gmail.com ← smtp1@fmail.shop" },
    { ok: true,  time: "14:21:56", msg: "client@yandex.ru ← smtp2@fmail.shop" },
    { ok: false, time: "14:21:57", msg: "bad@host.xyz × CONN_TIMEOUT" },
    { ok: true,  time: "14:21:58", msg: "work@outlook.com ← smtp3@fmail.shop" },
  ]);
  const [filter, setFilter] = useState<"all" | "ok" | "err">("all");
  const [logI, setLogI]     = useState(4);

  /* Settings */
  const [threads,    setThreads]    = useState(8);
  const [delayMin,   setDelayMin]   = useState(500);
  const [delayMax,   setDelayMax]   = useState(2000);
  const [pauseEvery, setPauseEvery] = useState(50);
  const [pauseDur,   setPauseDur]   = useState(60);
  const [rotation,   setRotation]   = useState("round-robin");
  const [scheduled,  setScheduled]  = useState(false);
  const [schedTime,  setSchedTime]  = useState("2024-06-20T10:00");

  const logRef = useRef<HTMLDivElement>(null);

  // Live updates when running
  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => {
      setProg(p => Math.min(p + 0.15, 100));
      setLogs(l => { const n = [...l, genLog(logI)]; setLogI(i => i + 1); return n.slice(-50); });
    }, 800);
    return () => clearInterval(id);
  }, [status, logI]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const total = 12450;
  const sent  = Math.floor(prog / 100 * total);
  const rate  = status === "running" ? 847 : 0;

  const filtered = filter === "all" ? logs : filter === "ok" ? logs.filter(l => l.ok) : logs.filter(l => !l.ok);

  const Num = ({ label, val, set, unit, min = 1, max = 9999 }: { label: string; val: number; set: (n: number) => void; unit?: string; min?: number; max?: number }) => (
    <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px 16px" }}>
      <div style={{ fontSize: 10, color: C.textMuted, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button onClick={() => set(Math.max(min, val - 1))} style={{ width: 22, height: 22, borderRadius: 5, border: `1px solid ${C.border}`, background: C.faint, color: C.textMuted, cursor: "pointer", fontFamily: "inherit", fontSize: 14 }}>−</button>
        <input type="number" value={val} min={min} max={max}
          onChange={e => set(Number(e.target.value))}
          style={{ width: 60, textAlign: "center", background: "transparent", border: "none", color: C.text, fontSize: 18, fontWeight: 700, fontFamily: "monospace", outline: "none" }}/>
        <button onClick={() => set(Math.min(max, val + 1))} style={{ width: 22, height: 22, borderRadius: 5, border: `1px solid ${C.border}`, background: C.faint, color: C.textMuted, cursor: "pointer", fontFamily: "inherit", fontSize: 14 }}>+</button>
      </div>
      {unit && <div style={{ fontSize: 10, color: C.textFaint, marginTop: 4 }}>{unit}</div>}
    </div>
  );

  return (
    <div style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 14, height: "100%", overflowY: "auto" }}>

      {/* Settings grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
        <Num label="Потоков"        val={threads}    set={setThreads}    min={1} max={999} unit="одновременных соединений" />
        <Num label="Задержка мин."  val={delayMin}   set={setDelayMin}   min={0} max={60000} unit="мс между письмами" />
        <Num label="Задержка макс." val={delayMax}   set={setDelayMax}   min={0} max={60000} unit="мс (рандомизация)" />
        <Num label="Пауза каждые"   val={pauseEvery} set={setPauseEvery} min={1} max={9999} unit="писем" />
        <Num label="Длина паузы"    val={pauseDur}   set={setPauseDur}   min={1} max={3600} unit="секунд" />
        <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px 16px" }}>
          <div style={{ fontSize: 10, color: C.textMuted, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: 8 }}>Ротация SMTP</div>
          <select value={rotation} onChange={e => setRotation(e.target.value)} style={{ width: "100%", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontSize: 12, padding: "6px 8px", outline: "none" }}>
            <option value="round-robin">Round-robin</option>
            <option value="random">Случайный</option>
            <option value="sequential">Последовательный</option>
            <option value="least-used">Наименее используемый</option>
          </select>
        </div>
      </div>

      {/* Delayed start */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 18px", display: "flex", alignItems: "center", gap: 14 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", flexShrink: 0 }}>
          <input type="checkbox" checked={scheduled} onChange={e => setScheduled(e.target.checked)}
            style={{ width: 14, height: 14, accentColor: C.purple }}/>
          <span style={{ fontSize: 12, color: C.text, display: "flex", alignItems: "center", gap: 6 }}>{I.clock} Отложенный запуск</span>
        </label>
        {scheduled && (
          <input type="datetime-local" value={schedTime} onChange={e => setSchedTime(e.target.value)}
            style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 12, padding: "6px 12px", outline: "none" }}/>
        )}
        {!scheduled && <span style={{ fontSize: 11, color: C.textMuted }}>Запуск немедленно при нажатии «Старт»</span>}
      </div>

      {/* Progress */}
      <Card>
        <SectionHead title="Прогресс" right={
          <div style={{ display: "flex", gap: 14, fontSize: 11 }}>
            <span style={{ color: C.textMuted }}>Отправлено: <b style={{ color: C.text }}>{sent.toLocaleString("ru")}</b></span>
            <span style={{ color: C.textMuted }}>Скорость: <b style={{ color: C.purple }}>{rate}/мин</b></span>
          </div>
        }/>
        <div style={{ padding: "14px 18px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 12 }}>
            <span style={{ color: C.textMuted }}>{sent.toLocaleString("ru")} / {total.toLocaleString("ru")}</span>
            <span style={{ color: C.purple, fontFamily: "monospace" }}>{prog.toFixed(1)}%</span>
          </div>
          <div style={{ height: 8, borderRadius: 99, background: C.faint, overflow: "hidden", marginBottom: 12 }}>
            <div style={{ height: "100%", width: `${prog}%`, background: "linear-gradient(90deg,#7c3aed,#a78bfa)", borderRadius: 99, transition: "width 0.4s ease" }}/>
          </div>
          {/* Stats row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
            {[
              { label: "Успешно", val: Math.floor(sent * 0.962), color: C.green },
              { label: "Ошибок",  val: Math.floor(sent * 0.038), color: C.red   },
              { label: "Bounce",  val: Math.floor(sent * 0.02),  color: C.amber  },
              { label: "Осталось", val: total - sent,             color: C.textMuted },
            ].map(s => (
              <div key={s.label} style={{ background: C.faint, borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: s.color }}>{s.val.toLocaleString("ru")}</div>
                <div style={{ fontSize: 10, color: C.textMuted, marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Controls */}
      <div style={{ display: "flex", gap: 8 }}>
        {status !== "running"
          ? <button onClick={() => setStatus("running")} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "11px", borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: "pointer", background: "linear-gradient(135deg,#7c3aed,#4f46e5)", border: "1px solid #7c3aed55", color: "#fff", fontFamily: "inherit" }}>{I.play} Старт</button>
          : <button onClick={() => setStatus("paused")}  style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "11px", borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: "pointer", background: C.surface, border: `1px solid ${C.border}`, color: C.textMuted, fontFamily: "inherit" }}>{I.pause} Пауза</button>
        }
        <button onClick={() => { setStatus("idle"); setProg(0); setLogs([]); }} style={{ padding: "11px 20px", borderRadius: 10, fontSize: 13, fontWeight: 500, cursor: "pointer", background: C.redDim, border: `1px solid ${C.red}44`, color: C.red, fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6 }}>{I.stop} Стоп</button>
      </div>

      {/* Log */}
      <Card style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <SectionHead title="Лог событий" right={
          <div style={{ display: "flex", gap: 4 }}>
            {(["all", "ok", "err"] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                background: filter === f ? C.purpleDim : "transparent",
                border: `1px solid ${filter === f ? C.borderAccent : "transparent"}`,
                color: filter === f ? C.purple : C.textMuted,
              }}>{f === "all" ? "Все" : f === "ok" ? "✓ Успех" : "✗ Ошибки"}</button>
            ))}
          </div>
        }/>
        <div ref={logRef} style={{ flex: 1, overflowY: "auto", padding: "8px 18px 12px", minHeight: 120 }}>
          {filtered.map((l, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", fontSize: 11, fontFamily: "monospace", borderBottom: `1px solid ${C.border}44` }}>
              <span style={{ color: l.ok ? C.green : C.red, flexShrink: 0 }}>{l.ok ? "✓" : "✗"}</span>
              <span style={{ color: C.textMuted, flexShrink: 0, width: 54 }}>{l.time}</span>
              <span style={{ color: l.ok ? C.text : C.red, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.msg}</span>
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ textAlign: "center", padding: "24px 0", fontSize: 12, color: C.textMuted }}>Записей нет</div>
          )}
        </div>
      </Card>
    </div>
  );
}
