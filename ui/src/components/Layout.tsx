import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Users, Mail, FileText, Send, Shield, Zap, Inbox as InboxIcon } from 'lucide-react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'

const NAV = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Дашборд' },
  { to: '/accounts',   icon: Users,           label: 'Аккаунты' },
  { to: '/proxies',    icon: Shield,          label: 'Прокси' },
  { to: '/recipients', icon: Mail,            label: 'Получатели' },
  { to: '/compose',    icon: FileText,        label: 'Письмо' },
  { to: '/sending',    icon: Send,            label: 'Рассылка' },
  { to: '/inbox',      icon: InboxIcon,       label: 'Входящие' },
]

const STATE_LABEL: Record<string, string> = {
  idle: 'Ожидание', running: 'Отправка',
  paused: 'Пауза',  done: 'Завершено', error: 'Ошибка',
}
const STATE_DOT: Record<string, string> = {
  running: 'bg-cyan animate-pulse', done: 'bg-success',
  error: 'bg-error', paused: 'bg-warn',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { status } = useStatus()
  const [version, setVersion] = useState('')

  useEffect(() => {
    fetch(`${getBaseUrl()}/api/health`)
      .then(r => r.json())
      .then((d: { version?: string }) => { if (d?.version) setVersion(`v${d.version}`) })
      .catch(() => {})
  }, [])

  const st = status?.campaign

  return (
    <div className="flex h-full overflow-hidden bg-[#040410] text-[#e8e8ff]">
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-52 flex-shrink-0 flex flex-col bg-[#0d1117] border-r border-[#3a3a66]/40">
        {/* Logo */}
        <div className="px-4 py-5 flex items-center gap-3 border-b border-[#3a3a66]/30">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#8b5cf6] to-[#06b6d4]
                          flex items-center justify-center flex-shrink-0">
            <Zap size={13} className="text-white" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-[#e8e8ff] leading-tight">FMail Sender</div>
            <div className="text-[10px] text-[#6666aa]">{version || 'v6.0'}</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-100 ${
                  isActive
                    ? 'bg-[#8b5cf6]/15 text-[#a78bfa] border border-[#8b5cf6]/25'
                    : 'text-[#6666aa] hover:text-[#e8e8ff] hover:bg-[#141424]'
                }`
              }
            >
              <Icon size={15} className="flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Status */}
        <div className="p-3 border-t border-[#3a3a66]/30 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#6666aa]">Статус</span>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATE_DOT[st?.state ?? ''] ?? 'bg-[#6666aa]'}`} />
              <span className="text-[#e8e8ff]">{STATE_LABEL[st?.state ?? 'idle'] ?? st?.state}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <div className="bg-[#141424] rounded-lg px-2 py-1.5 text-center">
              <div className="text-xs font-semibold text-[#10b981]">{status?.accounts.valid ?? 0}</div>
              <div className="text-[10px] text-[#6666aa] mt-0.5">аккаунтов</div>
            </div>
            <div className="bg-[#141424] rounded-lg px-2 py-1.5 text-center">
              <div className="text-xs font-semibold text-[#06b6d4]">{status?.recipients ?? 0}</div>
              <div className="text-[10px] text-[#6666aa] mt-0.5">получат.</div>
            </div>
          </div>
          {status && (status.proxies ?? 0) > 0 && (
            <div className="bg-[#141424] rounded-lg px-2 py-1.5 text-center">
              <div className="text-xs font-semibold text-[#8b5cf6]">{status.proxies}</div>
              <div className="text-[10px] text-[#6666aa] mt-0.5">прокси</div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        <div key={location.pathname}
          className="p-6 flex-1 flex flex-col animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  )
}

