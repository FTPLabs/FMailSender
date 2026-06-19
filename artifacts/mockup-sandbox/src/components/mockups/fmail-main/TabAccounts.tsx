import { useState } from "react";
import { C, Card, Btn, Dot, Badge, I, SectionHead } from "./shared";

const ACCOUNTS = [
  { email: "smtp1@fmail.shop", host: "smtp.fmail.shop", port: 587, ssl: false, sent: 1240, limit: 2000, status: "ok"   },
  { email: "smtp2@fmail.shop", host: "smtp.fmail.shop", port: 465, ssl: true,  sent: 983,  limit: 2000, status: "ok"   },
  { email: "smtp3@fmail.shop", host: "smtp.fmail.shop", port: 587, ssl: false, sent: 756,  limit: 2000, status: "ok"   },
  { email: "smtp4@fmail.shop", host: "smtp.fmail.shop", port: 587, ssl: false, sent: 312,  limit: 2000, status: "warn" },
  { email: "info@myco.ru",     host: "smtp.mail.ru",    port: 465, ssl: true,  sent: 2100, limit: 5000, status: "ok"   },
];

type CheckState = Record<number, "idle" | "checking" | "ok" | "fail">;

export function TabAccounts() {
  const [sel, setSel] = useState<Set<number>>(new Set());
  const [checking, setChecking] = useState<CheckState>({});

  const allSelected = sel.size === ACCOUNTS.length;
  const toggleAll = () => setSel(allSelected ? new Set() : new Set(ACCOUNTS.map((_, i) => i)));
  const toggle = (i: number) => setSel(s => { const n = new Set(s); n.has(i) ? n.delete(i) : n.add(i); return n; });

  const checkSelected = (indices: number[]) => {
    const next: CheckState = {};
    indices.forEach(i => { next[i] = "checking"; });
    setChecking(next);
    indices.forEach(i => {
      const delay = 800 + Math.random() * 1200;
      setTimeout(() => {
        setChecking(prev => ({ ...prev, [i]: Math.random() > 0.15 ? "ok" : "fail" }));
      }, delay);
    });
  };

  const checkAll = () => checkSelected(ACCOUNTS.map((_, i) => i));
  const checkSel = () => checkSelected(Array.from(sel));

  return (
    <div style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 14, height: "100%", overflowY: "auto" }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Btn accent onClick={() => {}}>{I.plus} Добавить</Btn>
        <Btn onClick={() => {}}>{I.upload} Импорт .txt</Btn>
        <Btn onClick={checkAll}>{I.check} Проверить всё</Btn>
        {sel.size > 0 && <Btn onClick={checkSel}>{I.check} Проверить выбранные ({sel.size})</Btn>}
        {sel.size > 0 && <Btn danger onClick={() => setSel(new Set())}>{I.trash} Удалить ({sel.size})</Btn>}
      </div>

      <Card style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {/* Select-all checkbox */}
              <th style={{ padding: "10px 14px", width: 36 }}>
                <div
                  onClick={toggleAll}
                  style={{
                    width: 15, height: 15, borderRadius: 4, cursor: "pointer",
                    border: `1.5px solid ${allSelected ? C.purple : C.border}`,
                    background: allSelected ? C.purple : "transparent",
                    display: "flex", alignItems: "center", justifyContent: "center", color: "#fff",
                  }}
                >{allSelected && I.check}</div>
              </th>
              {["Email", "Хост", "Порт", "Тип", "Отправлено", "Статус", "Проверка"].map(h => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", color: C.textMuted, fontSize: 10, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ACCOUNTS.map((a, i) => {
              const chk = checking[i];
              return (
                <tr key={i} onClick={() => toggle(i)} style={{
                  borderBottom: i < ACCOUNTS.length - 1 ? `1px solid ${C.border}` : "none",
                  background: sel.has(i) ? C.purpleDim : "transparent",
                  cursor: "pointer", transition: "background 0.1s",
                }}>
                  <td style={{ padding: "10px 14px" }}>
                    <div style={{
                      width: 15, height: 15, borderRadius: 4,
                      border: `1.5px solid ${sel.has(i) ? C.purple : C.border}`,
                      background: sel.has(i) ? C.purple : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center", color: "#fff",
                    }}>{sel.has(i) && I.check}</div>
                  </td>
                  <td style={{ padding: "10px 12px", color: C.text, fontFamily: "monospace", fontSize: 11 }}>{a.email}</td>
                  <td style={{ padding: "10px 12px", color: C.textMuted, fontFamily: "monospace", fontSize: 11 }}>{a.host}</td>
                  <td style={{ padding: "10px 12px", color: C.textMuted }}>{a.port}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <Badge color={a.ssl ? C.blue : C.textMuted} bg={a.ssl ? C.blueDim : C.faint}>{a.ssl ? "SSL/TLS" : "STARTTLS"}</Badge>
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ fontSize: 10, color: C.text, marginBottom: 4 }}>{a.sent.toLocaleString("ru")} / {a.limit.toLocaleString("ru")}</div>
                    <div style={{ height: 3, borderRadius: 99, background: C.faint }}>
                      <div style={{ height: "100%", width: `${(a.sent / a.limit) * 100}%`, background: C.purple, borderRadius: 99 }}/>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>
                      <Dot color={a.status === "ok" ? C.green : C.amber} />
                      <span style={{ color: a.status === "ok" ? C.green : C.amber }}>{a.status === "ok" ? "Активен" : "Предупр."}</span>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    {chk === "checking" && <span style={{ fontSize: 10, color: C.textMuted, display: "flex", alignItems: "center", gap: 4 }}><span style={{ animation: "spin 0.7s linear infinite", display: "inline-block" }}>↻</span> Проверка…</span>}
                    {chk === "ok"       && <span style={{ fontSize: 10, color: C.green, display: "flex", alignItems: "center", gap: 4 }}>{I.check} OK</span>}
                    {chk === "fail"     && <span style={{ fontSize: 10, color: C.red, display: "flex", alignItems: "center", gap: 4 }}>{I.x} Ошибка</span>}
                    {!chk               && <span style={{ fontSize: 10, color: C.faint }}>—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <div style={{ fontSize: 11, color: C.textMuted }}>
        Всего: {ACCOUNTS.length} аккаунтов &nbsp;·&nbsp; Активных: {ACCOUNTS.filter(a => a.status === "ok").length} &nbsp;·&nbsp; Выбрано: {sel.size}
      </div>
    </div>
  );
}
