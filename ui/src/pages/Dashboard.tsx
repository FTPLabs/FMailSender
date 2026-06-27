import { useEffect, useState } from 'react'
import { Users, Mail, Shield, Send, CheckCircle, XCircle, Clock } from 'lucide-react'
import { api, type AppStatus } from '../api'

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>
  color: string
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
        <Icon size={17} style={{ color }} />
      </div>
      <div className="min-w-0">
        <div className="text-xl font-bold text-[#e8e8ff] tabular-nums">{value}</div>
        <div className="text-xs text-[#6666aa] mt-0.5 truncate">{label}</div>
        {sub && <div className="text-[10px] text-[#6666aa]/60 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

function Bar({ value, max, color = '#8b5cf6' }: { value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.min(value / max * 100, 100) : 0
  return (
    <div className="h-1.5 bg-[#1c1c35] rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

const STATE_BADGE: Record<string, string> = {
  idle:    'badge-idle',
  running: 'badge-cyan',
  paused:  'badge-warn',
  done:    'badge-ok',
  error:   'badge-error',
}
const STATE_LABEL: Record<string, string> = {
  idle: 'Ожидание', running: 'Отправка', paused: 'Пауза', done: 'Завершено', error: 'Ошибка',
}

export default function Dashboard() {
  const [status, setStatus] = useState<AppStatus | null>(null)

  useEffect(() => {
    api.status().then(setStatus).catch(() => {})
    const id = setInterval(() => api.status().then(setStatus).catch(() => {}), 2000)
    return () => clearInterval(id)
  }, [])

  const s  = status
  const cp = s?.campaign

  return (
    <div className="page max-w-4xl">
      <div className="page-header">
        <div>
          <h1 className="page-title">Дашборд</h1>
          <p className="page-sub">Состояние системы в реальном времени</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard label="Аккаунтов готово" value={s?.accounts.ready ?? 0}
          sub={s ? `из ${s.accounts.total} всего` : undefined} icon={Users} color="#8b5cf6" />
        <StatCard label="Получателей" value={s?.recipients ?? 0} icon={Mail} color="#06b6d4" />
        <StatCard label="Прокси" value={s?.proxies ?? 0} icon={Shield} color="#10b981" />
        <StatCard label="Отправлено" value={cp?.sent ?? 0}
          sub={cp?.total ? `из ${cp.total}` : 'в этой кампании'} icon={Send} color="#f59e0b" />
      </div>

      {/* Campaign */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#e8e8ff]">Текущая рассылка</h2>
          <span className={STATE_BADGE[cp?.state ?? 'idle'] ?? 'badge-idle'}>
            {STATE_LABEL[cp?.state ?? 'idle'] ?? cp?.state}
          </span>
        </div>

        {cp && cp.total > 0 ? (
          <div className="space-y-3">
            <Bar value={cp.sent} max={cp.total} />
            <div className="grid grid-cols-3 gap-3 text-center text-sm">
              <div className="card-inset py-3">
                <div className="text-lg font-bold text-[#10b981]">{cp.sent}</div>
                <div className="text-xs text-[#6666aa] mt-0.5">Отправлено</div>
              </div>
              <div className="card-inset py-3">
                <div className="text-lg font-bold text-[#ef4444]">{cp.failed}</div>
                <div className="text-xs text-[#6666aa] mt-0.5">Ошибок</div>
              </div>
              <div className="card-inset py-3">
                <div className="text-lg font-bold text-[#06b6d4]">{cp.progress_pct}%</div>
                <div className="text-xs text-[#6666aa] mt-0.5">Прогресс</div>
              </div>
            </div>
            {cp.current_email && (
              <div className="text-xs text-[#6666aa] bg-[#141424] rounded-lg px-3 py-2 font-mono">
                → <span className="text-[#06b6d4]">{cp.current_email}</span>
                {cp.current_account && (
                  <span className="text-[#6666aa]"> · <span className="text-[#8b5cf6]">{cp.current_account}</span></span>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-[#6666aa] text-center py-4">
            Нет активной рассылки.{' '}
            <span className="text-[#8b5cf6]">Запустите в разделе «Рассылка».</span>
          </p>
        )}
      </div>

      {/* Account health */}
      <div className="card space-y-3">
        <h2 className="text-sm font-semibold text-[#e8e8ff]">Аккаунты</h2>
        <div className="space-y-2">
          {[
            { label: 'Активны и проверены', value: s?.accounts.valid ?? 0,   icon: CheckCircle, color: '#10b981' },
            { label: 'Не прошли проверку',  value: s?.accounts.invalid ?? 0, icon: XCircle,     color: '#ef4444' },
            { label: 'Не проверены',        value: s?.accounts.untested ?? 0,icon: Clock,       color: '#6666aa' },
          ].map(row => (
            <div key={row.label} className="flex items-center gap-3 text-sm">
              <row.icon size={13} style={{ color: row.color }} className="flex-shrink-0" />
              <span className="text-[#6666aa] flex-1 text-xs">{row.label}</span>
              <span className="font-semibold text-sm tabular-nums" style={{ color: row.color }}>{row.value}</span>
            </div>
          ))}
        </div>
        <Bar value={s?.accounts.valid ?? 0} max={Math.max(s?.accounts.total ?? 1, 1)} color="#10b981" />
      </div>

      {/* Errors */}
      {cp?.errors && cp.errors.length > 0 && (
        <div className="card space-y-2">
          <h2 className="text-xs font-semibold text-[#ef4444] uppercase tracking-wider">Последние ошибки</h2>
          <div className="space-y-1 max-h-28 overflow-y-auto">
            {cp.errors.slice(-10).map((e, i) => (
              <div key={i} className="text-xs text-[#ef4444]/80 font-mono bg-[#ef4444]/5 px-2.5 py-1 rounded">{e}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
