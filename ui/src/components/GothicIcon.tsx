import type { CSSProperties } from 'react'

export type GothicIconName = 'dashboard' | 'accounts' | 'proxies' | 'recipients' | 'compose' | 'sending' | 'inbox' | 'guide' | 'settings' | 'light' | 'dark' | 'system' | 'tour' | 'back' | 'next' | 'close' | 'add' | 'import' | 'refresh' | 'delete' | 'distribute' | 'check' | 'error' | 'waiting' | 'play' | 'pause' | 'stop' | 'warning' | 'info' | 'search' | 'save' | 'eye' | 'eyeoff' | 'ai' | 'key' | 'external' | 'spark'

type Props = { name: GothicIconName; size?: number; className?: string; title?: string; style?: CSSProperties }

const PATHS: Record<GothicIconName, JSX.Element> = {
  dashboard: <><path d="M12 2 20 7v10l-8 5-8-5V7l8-5Z"/><path d="M12 6v12M7 9l5 3 5-3"/></>,
  accounts: <><path d="M12 2 19 6v7c0 4.3-2.6 7.2-7 9-4.4-1.8-7-4.7-7-9V6l7-4Z"/><circle cx="12" cy="10" r="2.2"/><path d="M8.5 17c.7-2.2 2-3.3 3.5-3.3s2.8 1.1 3.5 3.3"/></>,
  proxies: <><path d="M12 2 20 12 12 22 4 12 12 2Z"/><path d="M12 6v12M8 12h8"/><circle cx="12" cy="12" r="2.2"/></>,
  recipients: <><path d="M4 6 12 2l8 4v12l-8 4-8-4V6Z"/><path d="m6.5 8.5 5.5 3.2 5.5-3.2M12 12v7"/></>,
  compose: <><path d="M5 3h10l4 4v14H5V3Z"/><path d="M15 3v5h5M8 13h8M8 17h5"/><path d="m16 11 2 2-4.5 4.5-2.4.6.6-2.4L16 11Z"/></>,
  sending: <><path d="M3 11.5 21 3l-6.7 18-2.6-7-8.7-2.5Z"/><path d="m11.7 14 3.8-5.1M11.7 14l.1 5.1"/></>,
  inbox: <><path d="M4 4h16v12l-3 4H7l-3-4V4Z"/><path d="M4 15h5l1.5 2h3L15 15h5"/></>,
  guide: <><path d="M4 4.5c3.2-1.3 5.8-.7 8 1.4 2.2-2.1 4.8-2.7 8-1.4v14c-3-1.1-5.6-.6-8 1.4-2.4-2-5-2.5-8-1.4v-14Z"/><path d="M12 6v14M7 9h2.5M14.5 9H17"/></>,
  settings: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="4.2"/><path d="M12 8.5v1.2M12 14.3v1.2M8.5 12h1.2M14.3 12h1.2"/></>,
  light: <><circle cx="12" cy="12" r="3.4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></>,
  dark: <><path d="M19.5 15.2A8.4 8.4 0 0 1 8.8 4.5 8.4 8.4 0 1 0 19.5 15.2Z"/><path d="m16.8 4 .5 1.2L18.5 6l-1.2.5-.5 1.2-.5-1.2L15 6l1.3-.8.5-1.2Z"/></>,
  system: <><path d="M4 5h16v11H4V5Z"/><path d="M9 20h6M12 16v4"/><path d="M7 8h10"/></>,
  tour: <><path d="M12 2 20 7v8l-8 7-8-7V7l8-5Z"/><path d="m8 14 2.3-3 2.1 1.4L16 8"/><circle cx="8" cy="7.5" r=".8"/><circle cx="16" cy="7.5" r=".8"/></>,
  back: <><path d="m14.5 5-7 7 7 7"/><path d="M8 12h9"/></>,
  next: <><path d="m9.5 5 7 7-7 7"/><path d="M16 12H7"/></>,
  add: <><path d="M12 2 20 12 12 22 4 12 12 2Z"/><path d="M12 8v8M8 12h8"/></>,
  import: <><path d="M5 4h14v16H5V4Z"/><path d="M12 7v7M9 11l3 3 3-3M8 17h8"/></>,
  refresh: <><path d="M19 8V4l-2.1 2.1A7 7 0 1 0 19 12"/><path d="M19 4h-4M5 16v4l2.1-2.1A7 7 0 0 0 5 12"/><path d="M5 20h4"/></>,
  delete: <><path d="M7 7h10l-1 14H8L7 7Z"/><path d="M9 7V4h6v3M5 7h14M10 11v6M14 11v6"/></>,
  distribute: <><circle cx="12" cy="5" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M12 7v4M12 11l-6 5M12 11l6 5"/></>,
  check: <><path d="M12 2 20 7v10l-8 5-8-5V7l8-5Z"/><path d="m8 12 2.5 2.5L16.5 9"/></>,
  error: <><path d="M12 2 20 7v10l-8 5-8-5V7l8-5Z"/><path d="m9 9 6 6m0-6-6 6"/></>,
  waiting: <><path d="M7 3h10M7 21h10M8 3v5l4 4 4-4V3M8 21v-5l4-4 4 4v5"/></>,
  play: <><path d="M6 3v18l13-9L6 3Z"/></>,
  pause: <><path d="M7 4h3v16H7V4ZM14 4h3v16h-3V4Z"/></>,
  stop: <><path d="M6 6h12v12H6V6Z"/></>,
  warning: <><path d="M12 3 21 20H3L12 3Z"/><path d="M12 9v5M12 17h.01"/></>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></>,
  search: <><circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 5 5"/></>,
  save: <><path d="M5 3h12l3 3v15H5V3Z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/></>,
  eye: <><path d="M3 12s3.2-5 9-5 9 5 9 5-3.2 5-9 5-9-5-9-5Z"/><circle cx="12" cy="12" r="2.2"/></>,
  eyeoff: <><path d="M4 4 20 20M10 7.3A9.8 9.8 0 0 1 12 7c5.8 0 9 5 9 5a16 16 0 0 1-3.1 3.4M14.1 16.4A9.8 9.8 0 0 1 12 17c-5.8 0-9-5-9-5a16 16 0 0 1 3.3-3.5"/><circle cx="12" cy="12" r="2.2"/></>,
  ai: <><path d="M12 2 14 8l6 2-6 2-2 6-2-6-6-2 6-2 2-6Z"/><path d="m18 16 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z"/></>,
  key: <><circle cx="8" cy="12" r="3.5"/><path d="M11.5 12H21M17 12v3M14 12v2"/></>,
  external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5H4V6h5"/></>,
  spark: <><path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z"/></>,
  close: <><path d="m7 7 10 10M17 7 7 17"/><path d="M12 2 20 7v10l-8 5-8-5V7l8-5Z"/></>,
}

export function GothicIcon({ name, size = 16, className = '', title, style: suppliedStyle }: Props) {
  const style: CSSProperties = { width: size, height: size, flexShrink: 0, ...suppliedStyle }
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className={`gothic-icon ${className}`} style={style} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>{title ? <title>{title}</title> : null}{PATHS[name]}</svg>
}
