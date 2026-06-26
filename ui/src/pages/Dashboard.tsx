import { useEffect, useState } from 'react'
  import { motion } from 'framer-motion'
  import { Users, Mail, Send, Wifi, TrendingUp, CheckCircle, XCircle, Clock } from 'lucide-react'
  import { api, type AppStatus } from '../api'

  function StatCard({ label, value, sub, icon: Icon, color }: {
    label: string; value: string | number; sub?: string
    icon: React.ComponentType<any>; color: string
  }) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="card flex items-start gap-4"
      >
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0`}
          style={{ background: `${color}22`, border: `1px solid ${color}44` }}>
          <Icon size={18} style={{ color }} />
        </div>
        <div>
          <div className="text-2xl font-bold text-text">{value}</div>
          <div className="text-sm text-muted mt-0.5">{label}</div>
          {sub && <div className="text-xs text-muted/70 mt-1">{sub}</div>}
        </div>
      </motion.div>
    )
  }

  function ProgressBar({ value, max, color = '#8b5cf6' }: { value: number; max: number; color?: string }) {
    const pct = max > 0 ? Math.min(value / max * 100, 100) : 0
    return (
      <div className="h-2 bg-surf3 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    )
  }

  export default function Dashboard() {
    const [status, setStatus] = useState<AppStatus | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
      const load = () => api.status().then(s => { setStatus(s); setLoading(false) }).catch(() => setLoading(false))
      load()
      const id = setInterval(load, 2000)
      return () => clearInterval(id)
    }, [])

    if (loading) return (
      <div className="flex items-center justify-center h-64 text-muted text-sm">Загрузка...</div>
    )

    const s = status
    const campaign = s?.campaign

    return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-text">Дашборд</h1>
          <p className="text-muted text-sm mt-1">Состояние системы в реальном времени</p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard label="Аккаунтов готово" value={s?.accounts.ready ?? 0}
            sub={`из ${s?.accounts.total ?? 0} всего`} icon={Users} color="#8b5cf6" />
          <StatCard label="Получателей" value={s?.recipients ?? 0}
            icon={Mail} color="#06b6d4" />
          <StatCard label="Прокси загружено" value={s?.proxies ?? 0}
            icon={Wifi} color="#10b981" />
          <StatCard label="Отправлено" value={campaign?.sent ?? 0}
            sub={campaign?.total ? `из ${campaign.total}` : 'в этой кампании'} icon={Send} color="#f59e0b" />
        </div>

        {/* Campaign status */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-text">Текущая рассылка</h2>
            <span className={
              campaign?.state === 'running' ? 'badge-cyan' :
              campaign?.state === 'done'    ? 'badge-ok' :
              campaign?.state === 'error'   ? 'badge-error' :
              campaign?.state === 'paused'  ? 'badge-warn' : 'badge-idle'
            }>
              {campaign?.state === 'idle' ? '⏸ Ожидание' :
               campaign?.state === 'running' ? '▶ Отправка' :
               campaign?.state === 'paused' ? '⏸ Пауза' :
               campaign?.state === 'done' ? '✓ Завершено' :
               campaign?.state === 'error' ? '✗ Ошибка' : campaign?.state}
            </span>
          </div>

          {campaign && campaign.total > 0 && (
            <>
              <ProgressBar value={campaign.sent} max={campaign.total} />
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div className="text-center">
                  <div className="text-success font-bold text-xl">{campaign.sent}</div>
                  <div className="text-muted">Отправлено</div>
                </div>
                <div className="text-center">
                  <div className="text-error font-bold text-xl">{campaign.failed}</div>
                  <div className="text-muted">Ошибок</div>
                </div>
                <div className="text-center">
                  <div className="text-cyan font-bold text-xl">{campaign.progress_pct}%</div>
                  <div className="text-muted">Прогресс</div>
                </div>
              </div>
              {campaign.current_email && (
                <div className="text-xs text-muted bg-surf2 rounded px-3 py-2">
                  → Отправка: <span className="text-cyan font-mono">{campaign.current_email}</span>
                  {campaign.current_account && <span> через <span className="text-purple">{campaign.current_account}</span></span>}
                </div>
              )}
            </>
          )}
          {(!campaign || campaign.total === 0) && (
            <div className="text-sm text-muted text-center py-4">
              Нет активной рассылки. Перейдите в <span className="text-purple">Рассылку</span> для запуска.
            </div>
          )}
        </div>

        {/* Account breakdown */}
        <div className="card space-y-3">
          <h2 className="font-semibold text-text">Аккаунты</h2>
          <div className="space-y-2">
            {[
              { label: 'Активны и проверены', value: s?.accounts.valid ?? 0, icon: CheckCircle, color: '#10b981' },
              { label: 'Не прошли проверку',  value: s?.accounts.invalid ?? 0, icon: XCircle, color: '#ef4444' },
              { label: 'Не проверены',        value: s?.accounts.untested ?? 0, icon: Clock, color: '#6666aa' },
            ].map(row => (
              <div key={row.label} className="flex items-center gap-3 text-sm">
                <row.icon size={14} style={{ color: row.color }} className="flex-shrink-0" />
                <span className="text-muted flex-1">{row.label}</span>
                <span className="font-semibold" style={{ color: row.color }}>{row.value}</span>
              </div>
            ))}
          </div>
          <ProgressBar
            value={s?.accounts.valid ?? 0}
            max={s?.accounts.total ?? 1}
            color="#10b981"
          />
        </div>

        {/* Last errors */}
        {campaign?.errors && campaign.errors.length > 0 && (
          <div className="card space-y-2">
            <h2 className="font-semibold text-error text-sm">Последние ошибки</h2>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {campaign.errors.slice(-10).map((e, i) => (
                <div key={i} className="text-xs text-error/80 font-mono bg-error/5 px-2 py-1 rounded">{e}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }
  