import { NavLink } from 'react-router-dom'
  import { motion } from 'framer-motion'
  import {
    LayoutDashboard, Users, Mail, Send, PlayCircle, Inbox,
    Settings, Zap
  } from 'lucide-react'
  import { useEffect, useState } from 'react'
  import { api, type AppStatus } from '../api'

  const NAV = [
    { to: '/dashboard',  icon: LayoutDashboard, label: 'Дашборд' },
    { to: '/accounts',   icon: Users,           label: 'Аккаунты' },
    { to: '/recipients', icon: Mail,            label: 'Получатели' },
    { to: '/compose',    icon: Send,            label: 'Письмо' },
    { to: '/sending',    icon: PlayCircle,      label: 'Рассылка' },
    { to: '/inbox',      icon: Inbox,           label: 'Входящие' },
  ]

  function StatusDot({ state }: { state: string }) {
    const cls = state === 'running'
      ? 'bg-cyan animate-pulse'
      : state === 'done'   ? 'bg-success'
      : state === 'error'  ? 'bg-error'
      : state === 'paused' ? 'bg-warn'
      : 'bg-muted'
    return <span className={`inline-block w-2 h-2 rounded-full ${cls}`} />
  }

  export default function Layout({ children }: { children: React.ReactNode }) {
    const [status, setStatus] = useState<AppStatus | null>(null)

    useEffect(() => {
      const fetch = () => api.status().then(setStatus).catch(() => null)
      fetch()
      const id = setInterval(fetch, 3000)
      return () => clearInterval(id)
    }, [])

    return (
      <div className="flex h-full bg-base text-text">
        {/* ── Sidebar ───────────────────────────────────────── */}
        <aside className="w-56 flex-shrink-0 flex flex-col bg-surface border-r border-text-dim/20 py-4">
          {/* Logo */}
          <div className="px-5 pb-6 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple to-cyan flex items-center justify-center shadow-glow-sm">
              <Zap size={15} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-sm text-text leading-tight">FMail Sender</div>
              <div className="text-[10px] text-muted">v6.0 Pro</div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 px-2 space-y-0.5">
            {NAV.map(({ to, icon: Icon, label }) => (
              <NavLink key={to} to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                    isActive
                      ? 'bg-purple/20 text-purple border border-purple/30 shadow-glow-sm'
                      : 'text-muted hover:text-text hover:bg-surf2'
                  }`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* Status summary */}
          {status && (
            <div className="px-4 pt-4 border-t border-text-dim/20 space-y-2">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>Рассылка</span>
                <div className="flex items-center gap-1.5">
                  <StatusDot state={status.campaign.state} />
                  <span className="text-text capitalize">
                    {status.campaign.state === 'idle' ? 'Ожидание' :
                     status.campaign.state === 'running' ? 'Идёт' :
                     status.campaign.state === 'paused' ? 'Пауза' :
                     status.campaign.state === 'done' ? 'Готово' : status.campaign.state}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-1 text-xs">
                <div className="bg-surf2 rounded px-2 py-1 text-center">
                  <div className="text-success font-semibold">{status.accounts.valid}</div>
                  <div className="text-muted">аккаунтов</div>
                </div>
                <div className="bg-surf2 rounded px-2 py-1 text-center">
                  <div className="text-cyan font-semibold">{status.recipients}</div>
                  <div className="text-muted">получат.</div>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* ── Main ─────────────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="p-6 min-h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>
    )
  }
  