import { useState } from "react";
import { C, I } from "./shared";
import { TabDashboard  } from "./TabDashboard";
import { TabAccounts   } from "./TabAccounts";
import { TabRecipients } from "./TabRecipients";
import { TabCompose    } from "./TabCompose";
import { TabSending    } from "./TabSending";
import { TabInbox      } from "./TabInbox";

type TabId = "dashboard" | "accounts" | "recipients" | "compose" | "sending" | "inbox";

const TABS: { id: TabId; label: string; icon: React.ReactNode; badge?: number }[] = [
  { id: "dashboard",  label: "Дашборд",    icon: I.dashboard  },
  { id: "accounts",   label: "Аккаунты",   icon: I.accounts,   badge: 5     },
  { id: "recipients", label: "Получатели", icon: I.recipients, badge: 12450 },
  { id: "compose",    label: "Письмо",     icon: I.compose    },
  { id: "sending",    label: "Рассылка",   icon: I.sending    },
  { id: "inbox",      label: "Входящие",   icon: I.inbox,      badge: 5     },
];

function NavItem({ id, label, icon, badge, active, onClick }: { id: string; label: string; icon: React.ReactNode; badge?: number; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 9,
      padding: "8px 12px", borderRadius: 9, width: "100%", textAlign: "left",
      background: active ? C.purpleDim : "transparent",
      border: `1px solid ${active ? C.borderAccent : "transparent"}`,
      color: active ? C.purple : C.textMuted,
      cursor: "pointer", fontSize: 13, fontWeight: active ? 600 : 400,
      fontFamily: "inherit", transition: "all 0.12s ease",
    }}>
      <span style={{ flexShrink: 0 }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge !== undefined && badge > 0 && (
        <span style={{
          fontSize: 10, fontWeight: 700, minWidth: 18, textAlign: "center",
          padding: "1px 5px", borderRadius: 20,
          background: active ? C.purple : C.faint,
          color: active ? "#fff" : C.textMuted,
        }}>
          {badge > 9999 ? "10k+" : badge}
        </span>
      )}
    </button>
  );
}

export function MainApp() {
  const [tab, setTab] = useState<TabId>("dashboard");

  const content: Record<TabId, React.ReactNode> = {
    dashboard:  <TabDashboard />,
    accounts:   <TabAccounts />,
    recipients: <TabRecipients />,
    compose:    <TabCompose />,
    sending:    <TabSending />,
    inbox:      <TabInbox />,
  };

  const currentTab = TABS.find(t => t.id === tab)!;

  return (
    <div style={{
      display: "flex", height: "100vh", overflow: "hidden",
      background: C.bg, color: C.text,
      fontFamily: "'Inter', system-ui, -apple-system, sans-serif", fontSize: 13,
    }}>
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 99px; }
        button { font-family: inherit; }
        input, textarea, select { font-family: inherit; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.15} }
        @keyframes spin   { to { transform: rotate(360deg); } }
      `}</style>

      {/* ── Sidebar ─────────────────────────────────────── */}
      <div style={{
        width: 204, display: "flex", flexDirection: "column", flexShrink: 0,
        background: C.surface, borderRight: `1px solid ${C.border}`,
      }}>
        {/* Logo */}
        <div style={{ padding: "18px 14px 14px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 18px rgba(124,58,237,0.45)",
          }}>
            {I.mail}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, letterSpacing: "-0.01em" }}>FMail Sender</div>
            <div style={{ fontSize: 10, color: C.textMuted }}>v3.5.5</div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {TABS.map(t => (
            <NavItem key={t.id} {...t} active={tab === t.id} onClick={() => setTab(t.id)} />
          ))}
        </nav>

        {/* License badge */}
        <div style={{ padding: "10px 8px 14px" }}>
          <div style={{
            background: C.purpleDim, border: `1px solid ${C.borderAccent}`, borderRadius: 10,
            padding: "10px 12px", display: "flex", alignItems: "center", gap: 8,
          }}>
            <span style={{ color: C.purple }}>{I.key}</span>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.purple, letterSpacing: "0.04em" }}>LIFETIME</div>
              <div style={{ fontSize: 10, color: C.textMuted }}>Безлимит · HWID привязан</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Main area ───────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
        {/* Topbar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 24px", height: 52, flexShrink: 0,
          background: C.surface, borderBottom: `1px solid ${C.border}`,
        }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: "-0.01em" }}>
            {currentTab.label}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 5, color: C.green }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, display: "inline-block", boxShadow: `0 0 5px ${C.green}`, animation: "blink 1.6s infinite" }}/>
              Рассылка активна
            </span>
            <button style={{ width: 30, height: 30, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 8, background: "transparent", border: `1px solid ${C.border}`, color: C.textMuted, cursor: "pointer" }}>
              {I.settings}
            </button>
          </div>
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {content[tab]}
        </div>
      </div>
    </div>
  );
}
