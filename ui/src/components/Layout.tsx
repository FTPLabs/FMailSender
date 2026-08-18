import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { GothicIcon, type GothicIconName } from './GothicIcon'
import { useStatus } from '../contexts/StatusContext'
import { useI18n, type AppLanguage } from '../i18n'

type ThemeMode = 'dark' | 'light' | 'system'

const NAV: { to: string; icon: GothicIconName; label: string }[] = [
  { to: '/dashboard',  icon: 'dashboard',  label: 'nav.dashboard' },
  { to: '/accounts',   icon: 'accounts',   label: 'nav.accounts' },
  { to: '/proxies',    icon: 'proxies',    label: 'nav.proxies' },
  { to: '/recipients', icon: 'recipients', label: 'nav.recipients' },
  { to: '/compose',    icon: 'compose',    label: 'nav.compose' },
  { to: '/sending',    icon: 'sending',    label: 'nav.sending' },
  { to: '/inbox',      icon: 'inbox',      label: 'nav.inbox' },
  { to: '/guide',      icon: 'guide',      label: 'nav.guide' },
  { to: '/settings',   icon: 'settings',   label: 'nav.settings' },
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
  const controls: { mode: ThemeMode; label: string; icon: GothicIconName }[] = [
    { mode: 'light', label: t('layout.light'), icon: 'light' },
    { mode: 'dark', label: t('layout.dark'), icon: 'dark' },
    { mode: 'system', label: t('layout.system'), icon: 'system' },
  ]
  return <div className="theme-switch" aria-label={t('layout.theme')}>
    {controls.map(({ mode: value, label, icon }) => <button key={value} type="button" title={label} aria-label={label} data-active={mode === value} onClick={() => onChange(value)}><GothicIcon name={icon} size={14} /></button>)}
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
  const { status, online } = useStatus()
  const { t, language } = useI18n()
  const [themeMode, setThemeMode] = useState<ThemeMode>(readThemeMode)
  const expiry = status?.license?.expires_at ? new Date(status.license.expires_at).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'en-US') : ''
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
        <div className="flex items-center gap-3"><div className="logo-shell h-11 w-11 flex-shrink-0"><img src="./fmail_nocturne_mark.png" alt="FMail" className="h-full w-full object-cover" /></div><div className="min-w-0"><div className="nocturne-brand text-[13px] leading-none text-text">FMAIL</div><div className="mt-1 flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-[.12em] text-muted"><GothicIcon name="key" size={10} /> {expiry ? `${t('layout.subscriptionUntil')}: ${expiry}` : t('layout.noSubscription')}</div></div></div>
      </div>
      <nav className="flex-1 space-y-1 p-3"><div className="nocturne-kicker px-2 pb-1.5">{t('layout.navigation')}</div>{NAV.map(({ to, icon, label }) => <NavLink key={to} to={to} className={({ isActive }) => `group flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm font-semibold transition-all duration-150 ${isActive ? 'border-purple/45 bg-purple/15 text-text shadow-glow-sm' : 'border-transparent text-muted hover:border-dim/55 hover:bg-surf2/70 hover:text-text'}`}><GothicIcon name={icon} size={16} className="flex-shrink-0 text-current" /><span>{t(label)}</span></NavLink>)}</nav>
      <div className="space-y-3 border-t border-dim/45 p-3"><div className="text-center text-[9px] text-muted/80">@ftpdev_sup</div>
        <div className="card-inset p-3"><div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[.12em] text-muted"><span>{t('layout.coreStatus')}</span><span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-success animate-pulse' : 'bg-error'}`} /></div><div className="mb-1 text-sm font-semibold text-text">{online ? t('layout.coreOnline') : t('layout.coreOffline')}</div><div className="mb-3 text-xs text-muted">{t(`state.${st?.state ?? 'idle'}`)}</div><div className="grid grid-cols-2 gap-2"><div className="rounded-md border border-dim/35 bg-surface/60 px-2 py-1.5 text-center"><div className="text-xs font-bold text-success">{status?.accounts.valid ?? 0}</div><div className="mt-0.5 text-[9px] uppercase tracking-wide text-muted">{t('layout.accounts')}</div></div><div className="rounded-md border border-dim/35 bg-surface/60 px-2 py-1.5 text-center"><div className="text-xs font-bold text-cyan">{status?.recipients ?? 0}</div><div className="mt-0.5 text-[9px] uppercase tracking-wide text-muted">{t('layout.recipients')}</div></div></div></div>
        <div className="flex items-center justify-between gap-2"><span className="nocturne-kicker">{t('layout.theme')}</span><ThemeSwitch mode={themeMode} onChange={setThemeMode} /></div>
        <div className="flex items-center justify-between gap-2"><span className="nocturne-kicker">{t('layout.language')}</span><LanguageSwitch /></div>
        <button type="button" onClick={() => window.dispatchEvent(new Event('fmail:tour:restart'))} className="btn btn-secondary btn-sm w-full justify-center"><GothicIcon name="tour" size={13} /> {t('layout.tour')}</button>
      </div>
    </aside>
    <main className="relative z-10 flex flex-1 flex-col overflow-y-auto"><div key={location.pathname} className="flex min-h-full flex-1 flex-col p-6 lg:p-8 animate-fade-in">{children}</div></main>
  </div>
}
