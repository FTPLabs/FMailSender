import { useState } from "react";
import { C, Card, Btn, Badge, I } from "./shared";

type MsgType = "bounce" | "reply" | "auto";

interface Msg {
  id: number;
  from: string;
  subj: string;
  type: MsgType;
  time: string;
  body: string;
}

const MSGS: Msg[] = [
  {
    id: 1, type: "bounce",
    from: "MAILER-DAEMON@mail.ru",
    subj: "Delivery Status Notification",
    time: "14:23",
    body: `Final-Recipient: rfc822; bad@invalid.com\nAction: failed\nStatus: 5.1.1\nDiagnostic-Code: smtp; 550 5.1.1 The email account that you tried to reach does not exist.`,
  },
  {
    id: 2, type: "bounce",
    from: "postmaster@gmail.com",
    subj: "Undelivered Mail Returned to Sender",
    time: "14:22",
    body: `Final-Recipient: rfc822; none@badhost.xyz\nAction: failed\nStatus: 5.4.4\nDiagnostic-Code: smtp; Host or domain name not found.`,
  },
  {
    id: 3, type: "reply",
    from: "reply@customer.com",
    subj: "Re: Специальное предложение",
    time: "14:20",
    body: `Добрый день!\n\nСпасибо за ваше предложение. Мы ознакомились с материалами и заинтересованы в сотрудничестве. Пожалуйста, свяжитесь с нами по телефону для обсуждения деталей.\n\nС уважением,\nАлексей, ООО Клиент`,
  },
  {
    id: 4, type: "auto",
    from: "noreply@yandex.ru",
    subj: "Out of Office: автоответ",
    time: "14:18",
    body: `Я нахожусь в отпуске до 25 июня 2024.\nВаше письмо будет рассмотрено после моего возвращения.\n\nПо срочным вопросам: deputy@yandex.ru`,
  },
  {
    id: 5, type: "reply",
    from: "info@partner.ru",
    subj: "Re: Интересное предложение!",
    time: "14:15",
    body: `Здравствуйте!\n\nПредложение интересное. Готовы обсудить условия партнёрства. Напишите нам удобное время для звонка.\n\nС уважением,\nПартнёр`,
  },
];

const typeColor: Record<MsgType, string> = { bounce: C.red, reply: C.green, auto: C.amber };
const typeLabel: Record<MsgType, string> = { bounce: "Bounce", reply: "Ответ", auto: "Авто" };
const typeBg: Record<MsgType, string>    = { bounce: C.redDim, reply: C.greenDim, auto: C.amberDim };

export function TabInbox() {
  const [sel,     setSel]     = useState(0);
  const [replying, setReplying] = useState(false);
  const [replyTxt, setReplyTxt] = useState("");
  const [sent,    setSent]    = useState<Set<number>>(new Set());

  const msg = MSGS[sel];

  const sendReply = () => {
    setSent(s => new Set([...s, msg.id]));
    setReplyTxt("");
    setReplying(false);
  };

  const bounces = MSGS.filter(m => m.type === "bounce").length;
  const replies = MSGS.filter(m => m.type === "reply").length;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Left panel — list */}
      <div style={{ width: 260, display: "flex", flexDirection: "column", borderRight: `1px solid ${C.border}` }}>
        {/* Stats */}
        <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}`, display: "flex", gap: 10 }}>
          <div style={{ flex: 1, textAlign: "center", background: C.redDim, borderRadius: 8, padding: "8px 0" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.red }}>{bounces}</div>
            <div style={{ fontSize: 10, color: C.textMuted }}>Bounce</div>
          </div>
          <div style={{ flex: 1, textAlign: "center", background: C.greenDim, borderRadius: 8, padding: "8px 0" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{replies}</div>
            <div style={{ fontSize: 10, color: C.textMuted }}>Ответы</div>
          </div>
          <div style={{ flex: 1, textAlign: "center", background: C.amberDim, borderRadius: 8, padding: "8px 0" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.amber }}>{MSGS.filter(m => m.type === "auto").length}</div>
            <div style={{ fontSize: 10, color: C.textMuted }}>Авто</div>
          </div>
        </div>

        {/* Message list */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {MSGS.map((m, i) => (
            <div key={m.id} onClick={() => { setSel(i); setReplying(false); }} style={{
              padding: "12px 16px", borderBottom: `1px solid ${C.border}`,
              background: sel === i ? C.purpleDim : "transparent",
              cursor: "pointer", transition: "background 0.1s",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {m.from.split("@")[0]}
                </span>
                <span style={{ fontSize: 10, color: C.textMuted, flexShrink: 0, marginLeft: 6 }}>{m.time}</span>
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.subj}</div>
              <Badge color={typeColor[m.type]} bg={typeBg[m.type]}>{typeLabel[m.type]}</Badge>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — message */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "16px 24px", borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 4 }}>{msg.subj}</div>
              <div style={{ fontSize: 11, color: C.textMuted }}>От: {msg.from}</div>
              <div style={{ fontSize: 11, color: C.textMuted }}>Время: {msg.time}</div>
            </div>
            <Badge color={typeColor[msg.type]} bg={typeBg[msg.type]}>{typeLabel[msg.type]}</Badge>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, padding: "20px 24px", overflowY: "auto" }}>
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "18px 20px", fontSize: 13, color: C.text, lineHeight: 1.8, fontFamily: "monospace", whiteSpace: "pre-wrap" }}>
            {msg.body}
          </div>

          {msg.type === "bounce" && (
            <div style={{ marginTop: 12, padding: "10px 16px", background: C.redDim, border: `1px solid ${C.red}33`, borderRadius: 10, fontSize: 11, color: C.red }}>
              ⚠ Адрес добавлен в чёрный список автоматически. Дальнейшая отправка на этот адрес невозможна.
            </div>
          )}
        </div>

        {/* Reply section */}
        <div style={{ padding: "14px 24px", borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
          {!replying ? (
            <div style={{ display: "flex", gap: 8 }}>
              {msg.type !== "bounce" && !sent.has(msg.id) && (
                <Btn onClick={() => setReplying(true)} accent>{I.reply} Ответить</Btn>
              )}
              {sent.has(msg.id) && (
                <span style={{ fontSize: 12, color: C.green, display: "flex", alignItems: "center", gap: 6 }}>{I.check} Ответ отправлен</span>
              )}
              {msg.type === "bounce" && (
                <Btn danger>{I.trash} Удалить из списка</Btn>
              )}
              <Btn>{I.trash} Удалить</Btn>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ fontSize: 11, color: C.textMuted }}>Ответ на: {msg.from}</div>
              <textarea
                value={replyTxt}
                onChange={e => setReplyTxt(e.target.value)}
                placeholder="Введите ответ…"
                style={{
                  width: "100%", height: 100, padding: "10px 14px", boxSizing: "border-box",
                  background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
                  color: C.text, fontSize: 13, fontFamily: "inherit", resize: "none", outline: "none", lineHeight: 1.6,
                }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <Btn accent onClick={sendReply} disabled={!replyTxt.trim()}>{I.sending} Отправить</Btn>
                <Btn onClick={() => setReplying(false)}>Отмена</Btn>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
