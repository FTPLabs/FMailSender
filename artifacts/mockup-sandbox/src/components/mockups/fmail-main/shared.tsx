/* ── Design Tokens ─────────────────────────────────────────────────────── */
export const C = {
  bg: "#07090f",
  surface: "#0d1117",
  surface2: "#12171f",
  border: "rgba(255,255,255,0.07)",
  borderAccent: "rgba(139,92,246,0.35)",
  purple: "#8b5cf6",
  purpleDark: "#7c3aed",
  purpleLight: "#a78bfa",
  purpleDim: "rgba(139,92,246,0.12)",
  green: "#22c55e",
  greenDim: "rgba(34,197,94,0.10)",
  red: "#ef4444",
  redDim: "rgba(239,68,68,0.10)",
  blue: "#3b82f6",
  blueDim: "rgba(59,130,246,0.10)",
  amber: "#f59e0b",
  amberDim: "rgba(245,158,11,0.10)",
  text: "#e2e8f0",
  textMuted: "rgba(255,255,255,0.38)",
  textFaint: "rgba(255,255,255,0.15)",
  faint: "rgba(255,255,255,0.06)",
};

/* ── Shared Typography helpers ─────────────────────────────────────────── */
export const label = (txt: string) => (
  <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" as const, color: C.textMuted, marginBottom: 8 }}>{txt}</p>
);

/* ── Dot indicator ──────────────────────────────────────────────────────── */
export const Dot = ({ color, size = 7 }: { color: string; size?: number }) => (
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none" style={{ flexShrink: 0 }}>
    <circle cx={size / 2} cy={size / 2} r={size / 2 - 0.5} fill={color} />
  </svg>
);

/* ── Status badge ──────────────────────────────────────────────────────── */
export const Badge = ({ children, color, bg }: { children: React.ReactNode; color: string; bg: string }) => (
  <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 99, background: bg, color }}>{children}</span>
);

/* ── Pill tag ──────────────────────────────────────────────────────────── */
export const Pill = ({ children }: { children: React.ReactNode }) => (
  <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, background: C.faint, color: C.textMuted }}>{children}</span>
);

/* ── Button ────────────────────────────────────────────────────────────── */
export const Btn = ({
  children, onClick, accent = false, danger = false, small = false, disabled = false,
}: {
  children: React.ReactNode; onClick?: () => void; accent?: boolean; danger?: boolean; small?: boolean; disabled?: boolean;
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: small ? "5px 10px" : "7px 14px",
      borderRadius: 8, fontSize: small ? 11 : 12, fontWeight: 500, cursor: disabled ? "not-allowed" : "pointer",
      fontFamily: "inherit",
      background: accent ? C.purple : danger ? C.redDim : C.surface,
      border: `1px solid ${accent ? C.purple : danger ? "#ef444455" : C.border}`,
      color: accent ? "#fff" : danger ? C.red : C.textMuted,
      opacity: disabled ? 0.5 : 1,
      transition: "all 0.12s",
    }}
  >{children}</button>
);

/* ── Card ──────────────────────────────────────────────────────────────── */
export const Card = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) => (
  <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden", ...style }}>
    {children}
  </div>
);

/* ── Section header ─────────────────────────────────────────────────────── */
export const SectionHead = ({ title, right }: { title: string; right?: React.ReactNode }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: `1px solid ${C.border}` }}>
    <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted, letterSpacing: "0.07em", textTransform: "uppercase" }}>{title}</span>
    {right}
  </div>
);

/* ── Mini spinner ───────────────────────────────────────────────────────── */
export const Spinner = () => (
  <svg width="13" height="13" viewBox="0 0 13 13" fill="none" style={{ animation: "spin 0.7s linear infinite", flexShrink: 0 }}>
    <circle cx="6.5" cy="6.5" r="5" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5"/>
    <path d="M6.5 1.5A5 5 0 0 1 11.5 6.5" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

/* ── All SVG icons ──────────────────────────────────────────────────────── */
export const I = {
  dashboard: <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1" y="1" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="8.5" y="1" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="1" y="8.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><rect x="8.5" y="8.5" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/></svg>,
  accounts:  <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="7.5" cy="5" r="3" stroke="currentColor" strokeWidth="1.2"/><path d="M1.5 13c0-3.314 2.686-5.5 6-5.5s6 2.186 6 5.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  recipients:<svg width="15" height="15" viewBox="0 0 15 15" fill="none"><circle cx="4.5" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.2"/><circle cx="10.5" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.2"/><path d="M1 13c0-2.761 1.567-4 3.5-4s3.5 1.239 3.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M9 10.5c.6-.33 1.25-.5 1.5-.5 1.933 0 3.5 1.239 3.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  compose:   <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1" y="2.5" width="13" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M1 5.5l6.5 4.5 6.5-4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  sending:   <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M13.5 1.5L1 6l5 2.5 1.5 5.5 6-12.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/><path d="M6 8.5L9.5 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  inbox:     <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><rect x="1" y="2" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M1 9.5h3l1.5 2h4L11 9.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  plus:      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1.5v10M1.5 6.5h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
  upload:    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 8.5V2M4 4.5l2.5-2.5 2.5 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 10.5h9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>,
  check:     <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  x:         <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  trash:     <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2 4h9M5 4V2.5h3V4M4.5 6v4M8.5 6v4M3 4l.8 7.5h5.4L10 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  key:       <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="5" cy="7" r="3" stroke="currentColor" strokeWidth="1.2"/><path d="M8 7h4.5M10.5 5.5V7M12.5 5.5V7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  settings:  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="2" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 1v1.5M6.5 10.5V12M1 6.5h1.5M10.5 6.5H12M2.636 2.636l1.06 1.06M9.304 9.304l1.06 1.06M2.636 10.364l1.06-1.06M9.304 3.696l1.06-1.06" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  mail:      <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><rect x="2" y="4.5" width="16" height="11" rx="1.8" stroke="white" strokeWidth="1.5"/><path d="M2 8l8 5 8-5" stroke="white" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  bold:      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 2h4a2 2 0 0 1 0 4H3V2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/><path d="M3 6h4.5a2.5 2.5 0 0 1 0 5H3V6z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>,
  italic:    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M5 2h5M2 10h5M7 2L5 10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  underline: <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 2v4a3 3 0 0 0 6 0V2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M1.5 10.5h9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  link:      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M5 7a3 3 0 0 0 4.5.5l1.5-1.5A3 3 0 0 0 6.5 1.5L5.5 2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><path d="M7 5a3 3 0 0 0-4.5-.5L1 6a3 3 0 0 0 4.5 4.5L6.5 9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  image:     <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><circle cx="4" cy="4" r="1" fill="currentColor"/><path d="M1 9l3-3 2 2 1.5-2 3.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  attach:    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M11 6L6 11a3.5 3.5 0 0 1-5-5l5.5-5.5a2.5 2.5 0 0 1 3.5 3.5L5 9.5a1.5 1.5 0 0 1-2-2L8 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  template:  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="1" y="1" width="11" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.2"/><path d="M4 1v11M1 4.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  spam:      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 3.5v3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="6.5" cy="9.5" r="0.7" fill="currentColor"/></svg>,
  play:      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M3 2l8 4.5L3 11V2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>,
  pause:     <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M4 2.5v8M9 2.5v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  stop:      <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><rect x="2.5" y="2.5" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.2"/></svg>,
  clock:     <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6.5 3.5V7l2.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  reply:     <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M4 4L1 7l3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/><path d="M1 7h7a4 4 0 0 1 4 4v1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  filter:    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M1.5 3.5h10M3.5 6.5h6M5.5 9.5h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>,
  arrow:     <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6h7M6.5 3l3.5 3-3.5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  download:  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 2v7M4 7l2.5 2.5L9 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 10.5h9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>,
  lightning: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M8 1L2 8h5l-1 5 6-7H7L8 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>,
};
