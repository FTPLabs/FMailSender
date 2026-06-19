import { useState, useRef, useCallback } from "react";
import { C, Btn, Card, I } from "./shared";

/* ── Spam score modal ───────────────────────────────────────────────────── */
function SpamModal({ onClose }: { onClose: () => void }) {
  const score = 2.4;
  const color = score < 3 ? C.green : score < 6 ? C.amber : C.red;
  const label = score < 3 ? "Отлично" : score < 6 ? "Риск" : "Спам";
  const checks = [
    { name: "HTML-структура",       score: 0.2, max: 2.0, ok: true  },
    { name: "Спам-слова",           score: 0.8, max: 3.0, ok: true  },
    { name: "Количество ссылок",    score: 0.4, max: 1.5, ok: true  },
    { name: "Соотношение текст/HTML", score: 0.0, max: 1.0, ok: true },
    { name: "Заголовки письма",     score: 0.0, max: 1.0, ok: true  },
    { name: "SPF / DKIM",           score: 1.0, max: 1.5, ok: false },
  ];
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 16, padding: 28, width: 420, boxShadow: "0 8px 40px rgba(0,0,0,0.5)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: C.text }}>Спам-анализ</span>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: C.textMuted }}>{I.x}</button>
        </div>

        {/* Score ring */}
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center" }}>
            <svg width="80" height="80" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="34" fill="none" stroke={C.faint} strokeWidth="6"/>
              <circle cx="40" cy="40" r="34" fill="none" stroke={color} strokeWidth="6"
                strokeDasharray={`${(1 - score / 10) * 213.6} 213.6`}
                strokeLinecap="round" transform="rotate(-90 40 40)"
                style={{ transition: "stroke-dasharray 0.8s ease" }}/>
              <text x="40" y="38" textAnchor="middle" fill={color} fontSize="18" fontWeight="700">{score}</text>
              <text x="40" y="52" textAnchor="middle" fill={C.textMuted} fontSize="9">/10</text>
            </svg>
            <span style={{ fontSize: 13, fontWeight: 600, color, marginTop: 6 }}>{label}</span>
          </div>
        </div>

        {/* Breakdown */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {checks.map((c, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ color: c.ok ? C.green : C.amber, flexShrink: 0 }}>{c.ok ? I.check : I.spam}</span>
              <span style={{ flex: 1, fontSize: 12, color: C.text }}>{c.name}</span>
              <span style={{ fontSize: 11, fontFamily: "monospace", color: c.score > 0 ? C.amber : C.green }}>{c.score.toFixed(1)} / {c.max.toFixed(1)}</span>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 20, padding: "10px 14px", background: C.faint, borderRadius: 8, fontSize: 11, color: C.textMuted, lineHeight: 1.6 }}>
          Письмо хорошего качества. Настройте SPF/DKIM для улучшения доставляемости.
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
          <Btn onClick={onClose} accent>Закрыть</Btn>
        </div>
      </div>
    </div>
  );
}

/* ── Template modal ─────────────────────────────────────────────────────── */
const TEMPLATES = [
  { name: "Приветственное письмо",  subj: "Добро пожаловать, {{first_name}}!" },
  { name: "Спецпредложение",         subj: "Эксклюзивно для вас, {{first_name}}" },
  { name: "Напоминание",             subj: "Не забудьте о нашем предложении" },
];

function TemplateModal({ onLoad, onClose }: { onLoad: (t: { name: string; subj: string }) => void; onClose: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 16, padding: 28, width: 400 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: C.text }}>Загрузить шаблон</span>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: C.textMuted }}>{I.x}</button>
        </div>
        {TEMPLATES.map((t, i) => (
          <div key={i} onClick={() => { onLoad(t); onClose(); }} style={{
            padding: "12px 16px", borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 8,
            cursor: "pointer", background: C.faint, transition: "background 0.1s",
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 2 }}>{t.name}</div>
            <div style={{ fontSize: 11, color: C.textMuted }}>{t.subj}</div>
          </div>
        ))}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
          <Btn onClick={onClose}>Отмена</Btn>
        </div>
      </div>
    </div>
  );
}

/* ── Color picker ───────────────────────────────────────────────────────── */
function ColorPicker({ onColor }: { onColor: (c: string) => void }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState("#e2e8f0");
  const presets = ["#ef4444","#f59e0b","#22c55e","#3b82f6","#8b5cf6","#ec4899","#06b6d4","#ffffff","#000000","#e2e8f0"];
  return (
    <div style={{ position: "relative" }}>
      <button
        onMouseDown={e => { e.preventDefault(); setOpen(o => !o); }}
        title="Цвет текста"
        style={{
          width: 26, height: 26, border: `1px solid ${C.border}`, borderRadius: 5, cursor: "pointer",
          background: custom, flexShrink: 0, padding: 0,
        }}/>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 200,
          background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 12,
          display: "flex", flexDirection: "column", gap: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
        }}>
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", width: 162 }}>
            {presets.map(p => (
              <div key={p} onClick={() => { setCustom(p); onColor(p); setOpen(false); }} style={{
                width: 22, height: 22, borderRadius: 4, background: p, cursor: "pointer",
                border: `2px solid ${custom === p ? C.purple : "transparent"}`,
              }}/>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="color" value={custom} onChange={e => setCustom(e.target.value)}
              style={{ width: 32, height: 24, border: "none", padding: 0, cursor: "pointer", background: "none", borderRadius: 4 }}/>
            <input value={custom} onChange={e => setCustom(e.target.value)}
              style={{ flex: 1, background: C.faint, border: `1px solid ${C.border}`, borderRadius: 6, padding: "3px 8px", fontSize: 11, color: C.text, fontFamily: "monospace", outline: "none" }}/>
            <button onClick={() => { onColor(custom); setOpen(false); }} style={{
              padding: "4px 10px", borderRadius: 6, fontSize: 11, background: C.purple, border: "none", color: "#fff", cursor: "pointer", fontFamily: "inherit",
            }}>OK</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Variable picker ────────────────────────────────────────────────────── */
const VARS = ["first_name", "last_name", "email", "company", "date", "phone", "city"];

function VarPicker({ onInsert }: { onInsert: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button
        onMouseDown={e => { e.preventDefault(); setOpen(o => !o); }}
        style={{ padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer", background: C.purpleDim, border: `1px solid ${C.borderAccent}`, color: C.purple, fontFamily: "inherit" }}>
        {"{ }"} Переменная
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 200,
          background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 6,
          boxShadow: "0 8px 24px rgba(0,0,0,0.4)", minWidth: 160,
        }}>
          {VARS.map(v => (
            <div key={v} onMouseDown={e => { e.preventDefault(); onInsert(v); setOpen(false); }} style={{
              padding: "6px 10px", borderRadius: 6, fontSize: 12, fontFamily: "monospace", color: C.purple,
              cursor: "pointer", background: "transparent", transition: "background 0.1s",
            }}
              onMouseEnter={e => (e.currentTarget.style.background = C.purpleDim)}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
              {`{{${v}}}`}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Rich Text Toolbar ──────────────────────────────────────────────────── */
function Toolbar({ editorRef }: { editorRef: React.RefObject<HTMLDivElement | null> }) {
  const exec = (cmd: string, value?: string) => {
    editorRef.current?.focus();
    document.execCommand(cmd, false, value ?? undefined);
  };

  const insertVar = (v: string) => {
    editorRef.current?.focus();
    document.execCommand("insertText", false, `{{${v}}}`);
  };

  const btnStyle = (active = false): React.CSSProperties => ({
    width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center",
    border: `1px solid ${active ? C.borderAccent : C.border}`, borderRadius: 5, cursor: "pointer",
    background: active ? C.purpleDim : "transparent", color: active ? C.purple : C.textMuted,
    fontFamily: "inherit",
  });

  const Sep = () => <div style={{ width: 1, height: 20, background: C.border, margin: "0 3px" }}/>;

  const sizes = ["10", "12", "14", "16", "18", "20", "24", "28", "32"];

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap",
      padding: "8px 12px", borderBottom: `1px solid ${C.border}`, background: C.surface2,
    }}>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("bold"); }} title="Жирный"><b style={{ fontSize: 11 }}>B</b></button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("italic"); }} title="Курсив"><i style={{ fontSize: 11 }}>I</i></button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("underline"); }} title="Подчёркнутый"><u style={{ fontSize: 11 }}>U</u></button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("strikeThrough"); }} title="Зачёркнутый"><s style={{ fontSize: 11 }}>S</s></button>
      <Sep/>
      <select
        onChange={e => exec("fontSize", e.target.value)}
        defaultValue="3"
        style={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 5, color: C.textMuted, fontSize: 11, padding: "2px 4px", cursor: "pointer", height: 26 }}>
        <option value="1">10px</option>
        <option value="2">12px</option>
        <option value="3">14px</option>
        <option value="4">16px</option>
        <option value="5">18px</option>
        <option value="6">24px</option>
        <option value="7">32px</option>
      </select>
      <Sep/>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("justifyLeft"); }} title="Влево">⇤</button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("justifyCenter"); }} title="По центру">⇔</button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("justifyRight"); }} title="Вправо">⇥</button>
      <Sep/>
      <ColorPicker onColor={c => exec("foreColor", c)} />
      <Sep/>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("insertUnorderedList"); }} title="Список">≡</button>
      <button style={btnStyle()} onMouseDown={e => { e.preventDefault(); exec("createLink", prompt("URL ссылки:", "https://") || ""); }} title="Ссылка">{I.link}</button>
      <Sep/>
      <VarPicker onInsert={insertVar} />
    </div>
  );
}

/* ── Attachments panel ──────────────────────────────────────────────────── */
function AttachmentsTab() {
  const [files, setFiles] = useState<{ name: string; size: string }[]>([
    { name: "promo.pdf", size: "248 KB" },
  ]);
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{
        border: `2px dashed ${C.border}`, borderRadius: 12, padding: "32px 20px", textAlign: "center",
        cursor: "pointer", color: C.textMuted, fontSize: 12,
      }}>
        {I.attach}
        <p style={{ marginTop: 8 }}>Перетащите файлы сюда или <span style={{ color: C.purple }}>выберите</span></p>
        <p style={{ fontSize: 10, marginTop: 4 }}>Макс. 25 МБ · PDF, DOCX, PNG, JPG</p>
      </div>
      {files.map((f, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: C.faint, borderRadius: 8 }}>
          {I.attach}
          <span style={{ flex: 1, fontSize: 12, color: C.text }}>{f.name}</span>
          <span style={{ fontSize: 11, color: C.textMuted }}>{f.size}</span>
          <button onClick={() => setFiles(files.filter((_, j) => j !== i))} style={{ background: "none", border: "none", cursor: "pointer", color: C.red }}>{I.x}</button>
        </div>
      ))}
    </div>
  );
}

/* ── Main Compose ───────────────────────────────────────────────────────── */
export function TabCompose() {
  const [from, setFrom]     = useState("FMail Newsletter <smtp1@fmail.shop>");
  const [subj, setSubj]     = useState("Специальное предложение — {{first_name}}!");
  const [tab,  setTab]      = useState<"editor"|"html"|"preview"|"attachments">("editor");
  const [html, setHtml]     = useState(`<p>Привет, <b>{{first_name}}</b>!</p>\n<p>Мы рады сообщить вам об эксклюзивном предложении...</p>\n<p>С уважением,<br>Команда FMail</p>`);
  const [showSpam, setShowSpam]     = useState(false);
  const [showTpl,  setShowTpl]      = useState(false);
  const editorRef = useRef<HTMLDivElement>(null);

  const syncHtml = () => {
    if (editorRef.current) setHtml(editorRef.current.innerHTML);
  };

  const loadTemplate = (t: { name: string; subj: string }) => {
    setSubj(t.subj);
    if (editorRef.current) {
      editorRef.current.innerHTML = `<p>Привет, <b>{{first_name}}</b>!</p><p>Шаблон: ${t.name}</p>`;
      setHtml(editorRef.current.innerHTML);
    }
  };

  const TABS = [
    { id: "editor",      label: "Редактор" },
    { id: "html",        label: "HTML" },
    { id: "preview",     label: "Предпросмотр" },
    { id: "attachments", label: "Вложения" },
  ] as const;

  return (
    <div style={{ padding: "22px 26px", display: "flex", flexDirection: "column", gap: 12, height: "100%", overflowY: "auto", position: "relative" }}>
      {showSpam && <SpamModal onClose={() => setShowSpam(false)} />}
      {showTpl  && <TemplateModal onLoad={loadTemplate} onClose={() => setShowTpl(false)} />}

      {/* Fields */}
      {[
        { label: "От кого", value: from, set: setFrom },
        { label: "Тема",    value: subj, set: setSubj },
      ].map(f => (
        <div key={f.label}>
          <label style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: C.textMuted, display: "block", marginBottom: 5 }}>{f.label}</label>
          <input value={f.value} onChange={e => f.set(e.target.value)}
            style={{ width: "100%", padding: "9px 14px", borderRadius: 8, fontSize: 12, background: C.surface, border: `1px solid ${C.border}`, color: C.text, outline: "none", fontFamily: "inherit", boxSizing: "border-box" }}/>
        </div>
      ))}

      {/* Editor tabs */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        {/* Tab nav */}
        <div style={{ display: "flex", gap: 2, borderBottom: `1px solid ${C.border}`, marginBottom: 0 }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id as typeof tab)} style={{
              padding: "7px 14px", fontSize: 12, fontWeight: 500, cursor: "pointer", fontFamily: "inherit",
              background: "transparent", border: "none",
              borderBottom: tab === t.id ? `2px solid ${C.purple}` : "2px solid transparent",
              color: tab === t.id ? C.purple : C.textMuted, marginBottom: -1,
            }}>{t.label}</button>
          ))}
        </div>

        {/* Editor body */}
        <div style={{ flex: 1, background: C.surface, border: `1px solid ${C.border}`, borderTop: "none", borderRadius: "0 0 10px 10px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {tab === "editor" && (
            <>
              <Toolbar editorRef={editorRef} />
              <div
                ref={editorRef}
                contentEditable
                suppressContentEditableWarning
                onInput={syncHtml}
                dangerouslySetInnerHTML={{ __html: html }}
                style={{
                  flex: 1, padding: "16px 20px", overflowY: "auto", outline: "none",
                  fontSize: 13, color: C.text, lineHeight: 1.75, minHeight: 180,
                  caretColor: C.purple,
                }}
              />
            </>
          )}

          {tab === "html" && (
            <textarea
              value={html}
              onChange={e => setHtml(e.target.value)}
              style={{
                flex: 1, padding: "16px 20px", background: "transparent", border: "none", outline: "none",
                color: "#a78bfa", fontFamily: "monospace", fontSize: 12, lineHeight: 1.8, resize: "none",
              }}
            />
          )}

          {tab === "preview" && (
            <iframe
              srcDoc={`<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;padding:24px;background:#fff;color:#333;font-size:14px;line-height:1.7;max-width:600px;margin:0 auto}</style></head><body>${html}</body></html>`}
              style={{ flex: 1, border: "none", background: "#fff", borderRadius: "0 0 10px 10px" }}
              title="Email Preview"
              sandbox="allow-same-origin"
            />
          )}

          {tab === "attachments" && <AttachmentsTab />}
        </div>
      </div>

      {/* Bottom toolbar */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", paddingTop: 4 }}>
        <Btn onClick={() => {}}>{I.download} Сохранить шаблон</Btn>
        <Btn onClick={() => setShowTpl(true)}>{I.template} Загрузить шаблон</Btn>
        <Btn onClick={() => setShowSpam(true)}>{I.spam} Проверить спам-балл</Btn>
        <div style={{ flex: 1 }}/>
        <Btn accent onClick={() => {}}>{I.sending} Запустить рассылку</Btn>
      </div>
    </div>
  );
}
