import { useState } from "react";
import { C, Card, Btn, Dot, Badge, I, SectionHead } from "./shared";

const ROWS = [
  { email: "user@gmail.com",   name: "Иван Петров",    valid: true  },
  { email: "client@yandex.ru", name: "Мария Сидорова", valid: true  },
  { email: "bad@@invalid",     name: "",               valid: false },
  { email: "work@outlook.com", name: "Alexey K.",       valid: true  },
  { email: "info@company.ru",  name: "ООО Компания",   valid: true  },
  { email: "hello@mail.ru",    name: "Виктор Н.",       valid: true  },
  { email: "not_email",        name: "",               valid: false },
  { email: "sales@shop.com",   name: "Shop Sales",     valid: true  },
];

export function TabRecipients() {
  const [rows, setRows] = useState(ROWS);
  const valid   = rows.filter(r => r.valid).length;
  const invalid = rows.filter(r => !r.valid).length;

  const dedup = () => {
    const seen = new Set<string>();
    setRows(rows.filter(r => { if (seen.has(r.email)) return false; seen.add(r.email); return true; }));
  };
  const clearInvalid = () => setRows(rows.filter(r => r.valid));

  return (
    <div style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 14, height: "100%", overflowY: "auto" }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <Btn accent>{I.upload} Импорт CSV / TXT</Btn>
        <Btn onClick={() => {}}>{I.plus} Добавить вручную</Btn>
        <Btn onClick={dedup}>{I.filter} Удалить дубли</Btn>
        <Btn onClick={clearInvalid} danger>{I.trash} Удалить невалидные</Btn>
        <div style={{ flex: 1 }}/>
        <div style={{ display: "flex", gap: 12, fontSize: 11, alignItems: "center" }}>
          <span style={{ color: C.textMuted }}>Всего: <b style={{ color: C.text }}>{rows.length}</b></span>
          <span style={{ color: C.green }}>Валидных: <b>{valid}</b></span>
          <span style={{ color: C.red }}>Ошибок: <b>{invalid}</b></span>
        </div>
      </div>

      {/* Summary bar */}
      <div style={{ height: 4, borderRadius: 99, background: C.faint, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(valid / rows.length) * 100}%`, background: C.green, borderRadius: 99, transition: "width 0.3s" }}/>
      </div>

      <Card style={{ flex: 1 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {["#", "Email", "Имя / Компания", "Статус"].map(h => (
                <th key={h} style={{ padding: "10px 14px", textAlign: "left", color: C.textMuted, fontSize: 10, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ borderBottom: i < rows.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <td style={{ padding: "9px 14px", color: C.textMuted, width: 36 }}>{i + 1}</td>
                <td style={{ padding: "9px 14px", color: r.valid ? C.text : C.red, fontFamily: "monospace", fontSize: 11 }}>{r.email}</td>
                <td style={{ padding: "9px 14px", color: C.textMuted, fontSize: 11 }}>{r.name || <span style={{ color: C.faint }}>—</span>}</td>
                <td style={{ padding: "9px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>
                    <Dot color={r.valid ? C.green : C.red} size={6} />
                    <span style={{ color: r.valid ? C.green : C.red }}>{r.valid ? "Валидный" : "Ошибка"}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
