import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Users, Mail, FileText, Send, Shield, Inbox as InboxIcon, Monitor, Moon, Sun, Sparkles, BookOpen } from 'lucide-react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'
import { useI18n, type AppLanguage } from '../i18n'

type ThemeMode = 'dark' | 'light' | 'system'

const NAV = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'nav.dashboard' },
  { to: '/accounts',   icon: Users,           label: 'nav.accounts' },
  { to: '/proxies',    icon: Shield,          label: 'nav.proxies' },
  { to: '/recipients', icon: Mail,            label: 'nav.recipients' },
  { to: '/compose',    icon: FileText,        label: 'nav.compose' },
  { to: '/sending',    icon: Send,            label: 'nav.sending' },
  { to: '/inbox',      icon: InboxIcon,       label: 'nav.inbox' },
  { to: '/guide',      icon: BookOpen,        label: 'nav.guide' },
]

const STATE_DOT: Record<string, string> = {
  running: 'bg-cyan animate-pulse', done: 'bg-success', error: 'bg-error', paused: 'bg-warn',
}

function readThemeMode(): ThemeMode {
  const stored = localStorage.getItem('fmail-theme')
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
}

function ThemeSwitch({ mode, onChange }: { mode: ThemeMode; onChange: (next: ThemeMode) => void }) {
  const { t } = useI18n()
  const controls: { mode: ThemeMode; label: string; Icon: typeof Sun }[] = [
    { mode: 'light', label: t('layout.light'), Icon: Sun },
    { mode: 'dark', label: t('layout.dark'), Icon: Moon },
    { mode: 'system', label: t('layout.system'), Icon: Monitor },
  ]
  return <div className="theme-switch" aria-label={t('layout.theme')}>
    {controls.map(({ mode: value, label, Icon }) => <button key={value} type="button" title={label} aria-label={label} data-active={mode === value} onClick={() => onChange(value)}><Icon size={14} strokeWidth={1.8} /></button>)}
  </div>
}

function LanguageSwitch() {
  const { language, setLanguage, t } = useI18n()
  return <div className="flex rounded-md border border-dim/55 overflow-hidden" aria-label={t('layout.language')}>
    {(['ru', 'en'] as AppLanguage[]).map(value => <button key={value} type="button" aria-label={value.toUpperCase()} onClick={() => setLanguage(value)} className={`px-2 py-1 text-[10px] font-bold tracking-wide ${language === value ? 'bg-purple/20 text-text' : 'text-muted hover:bg-surf2/70'}`}>{value.toUpperCase()}</button>)}
  </div>
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { status } = useStatus()
  const { t } = useI18n()
  const [version, setVersion] = useState('')
  const [themeMode, setThemeMode] = useState<ThemeMode>(readThemeMode)

  useEffect(() => { fetch(`${getBaseUrl()}/api/health`).then(r => r.json()).then((d: { version?: string }) => { if (d?.version) setVersion(`v${d.version}`) }).catch(() => {}) }, [])
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: light)')
    const apply = () => { const resolved = themeMode === 'system' ? (media.matches ? 'light' : 'dark') : themeMode; document.documentElement.dataset.theme = resolved; document.documentElement.style.colorScheme = resolved }
    localStorage.setItem('fmail-theme', themeMode); apply(); media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [themeMode])

  const st = status?.campaign
  return <div className="nocturne-shell flex h-full">
    <aside className="relative z-10 flex w-64 flex-shrink-0 flex-col border-r border-dim/60 bg-surface/95 shadow-nocturne">
      <div className="border-b border-dim/45 px-4 py-4">
        <div className="flex items-center gap-3"><div className="logo-shell h-11 w-11 flex-shrink-0"><img src="./fmail_nocturne_mark.png" alt="FMail Nocturne" className="h-full w-full object-cover" /></div><div className="min-w-0"><div className="nocturne-brand text-[13px] leading-none text-text">FMAIL</div><div className="mt-1 flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-[.18em] text-purple-light"><Sparkles size={10} strokeWidth={1.6} /> NOCTURNE</div></div></div>
        <div className="mt-3 flex items-center justify-between border-t border-dim/30 pt-3"><span className="nocturne-kicker">campaign console</span><span className="font-mono text-[10px] text-muted">{version || '—'}</span></div>
      </div>
      <nav className="flex-1 space-y-1 p-3"><div className="nocturne-kicker px-2 pb-1.5">{t('layout.navigation')}</div>{NAV.map(({ to, icon: Icon, label }) => <NavLink key={to} to={to} className={({ isActive }) => `group flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm font-semibold transition-all duration-150 ${isActive ? 'border-purple/45 bg-purple/15 text-text shadow-glow-sm' : 'border-transparent text-muted hover:border-dim/55 hover:bg-surf2/70 hover:text-text'}`}><Icon size={16} strokeWidth={1.65} className="flex-shrink-0 text-current" /><span>{t(label)}</span></NavLink>)}</nav>
      <div className="space-y-3 border-t border-dim/45 p-3">
        <div className="card-inset p-3"><div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[.12em] text-muted"><span>{t('layout.coreStatus')}</span><span className={`h-1.5 w-1.5 rounded-full ${STATE_DOT[st?.state ?? ''] ?? 'bg-muted'}`} /></div><div className="mb-3 text-sm font-semibold text-text">{t(`state.${st?.state ?? 'idle'}`)}</div><div className="grid grid-cols-2 gap-2"><div className="rounded-md border border-dim/35 bg-surface/60 px-2 py-1.5 text-center"><div className="text-xs font-bold text-success">{status?.accounts.valid ?? 0}</div><div className="mt-0.5 text-[9px] uppercase tracking-wide text-muted">{t('layout.accounts')}</div></div><div className="rounded-md border border-dim/35 bg-surface/60 px-2 py-1.5 text-center"><div className="text-xs font-bold text-cyan">{status?.recipients ?? 0}</div><div className="mt-0.5 text-[9px] uppercase tracking-wide text-muted">{t('layout.recipients')}</div></div></div></div>
        <div className="flex items-center justify-between gap-2"><span className="nocturne-kicker">{t('layout.theme')}</span><ThemeSwitch mode={themeMode} onChange={setThemeMode} /></div>
        <div className="flex items-center justify-between gap-2"><span className="nocturne-kicker">{t('layout.language')}</span><LanguageSwitch /></div>
      </div>
    </aside>
    <main className="relative z-10 flex flex-1 flex-col overflow-y-auto"><div key={location.pathname} className="flex min-h-full flex-1 flex-col p-6 lg:p-8 animate-fade-in">{children}</div></main>
  </div>
}
