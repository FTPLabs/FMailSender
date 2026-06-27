import { useEffect, useState } from 'react'
import { Play, Pause, Square, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { api, type AppStatus } from '../api'

function Ring({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const R = 52; const C = 2 * Math.PI * R
  return (
    <svg width="120" height="120" viewBox="0 0 120 120">
      <circle cx="60" cy="60" r={R} fill="none" stroke="#1c1c35" strokeWidth="10" />
      <circle cx="60" cy="60" r={R} fill="none" stroke="#8b5cf6" strokeWidth="10"
        strokeDasharray={`${pct * C} ${C}`} strokeLinecap="round"
        transform="rotate(-90 60 60)"
        style={{ transition: 'stroke-dasharray 0.6s ease' }} />
      <text x="60" y="55" textAnchor="middle" fill="#e8e8ff" fontSize="19"
        fontWeight="700" fontFamily="Inter,system-ui,sans-serif">
        {Math.round(pct * 100)}%
      </text>
      <text x="60" y="73" textAnchor="middle" fill="#6666aa" fontSize="10"
        fontFamily="Inter,system-ui,sans-serif">
        {value}/{max}
      </text>
    </svg>
  )
}

export default function Sending() {
  const [status, setStatus] = useState<AppStatus | null>(null)
  const [busy, setBusy]     = useState(false)

  useEffect(() => {
    api.status().then(setStatus).catch(() => {})
    const id = setInterval(() => api.status().then(setStatus).catch(() => {}), 1000)
    return () => clearInterval(id)
  }, [])

  const cp     = status?.campaign
  const state  = cp?.state ?? 'idle'
  const run    = state === 'running'
  const paused = state === 'paused'
  const done   = state === 'done'
  const err    = state === 'error'
  const ready  = status?.accounts.ready ?? 0
  const recs   = status?.recipients ?? 0

  async function act(fn: () => Promise<any>) {
    setBusy(true)
    try { await fn(); const s = await api.status(); setStatus(s) }
    catch (e: any) { alert(e.response?.data?.detail ?? e.message) }
    finally { setBusy(false) }
  }

  const elapsed = cp?.started_at
    ? Math.round((Date.now() / 1000 - cp.started_at) / 60)
    : 0
  const speed = elapsed > 0 && cp?.sent ? Math.round(cp.sent / elapsed) : 0

  const stateColor = run ? '#06b6d4' : done ? '#10b981' : err ? '#ef4444' : paused ? '#f59e0b' : '#6666aa'
  const stateLabel = run ? '▶ Отправка...' : paused ? '⏸ Пауза' : done ? '✓ Завершено' :
    err ? '✗ Ошибка' : '⏹ Ожидание'

  return (
    <div className="page max-w-2xl">
      <div>
        <h1 className="page-title">Рассылка</h1>
        <p className="page-sub">Запуск и мониторинг кампании</p>
      </div>

      {/* Readiness */}
      {!run && !paused && !done && (
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-[#e8e8ff]">Готовность</h2>
          <div className="space-y-2">
            {[
              { label: 'Аккаунтов готово',     ok: ready > 0, value: `${ready}` },
              { label: 'Получатели загружены', ok: recs > 0,  value: `${recs}` },
            ].map(row => (
              <div key={row.label} className="flex items-center gap-3 text-sm">
                {row.ok
                  ? <CheckCircle size={14} className="text-[#10b981] flex-shrink-0" />
                  : <XCircle size={14} className="text-[#ef4444] flex-shrink-0" />
                }
                <span className="text-[#6666aa] flex-1 text-xs">{row.label}</span>
                <span className={`text-sm font-semibold tabular-nums ${row.ok ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>
          {(ready === 0 || recs === 0) && (
            <p className="text-xs text-[#f59e0b] bg-[#f59e0b]/10 border border-[#f59e0b]/20 rounded-lg px-3 py-2">
              {ready === 0 ? 'Нет готовых аккаунтов. Добавьте и проверьте аккаунты.' :
               'Нет получателей. Загрузите список получателей.'}
            </p>
          )}
        </div>
      )}

      {/* Main control */}
      <div className="card flex flex-col items-center gap-6 py-10">
        <Ring value={cp?.sent ?? 0} max={cp?.total || recs || 1} />

        <div className="text-center">
          <div className="text-base font-semibold" style={{ color: stateColor }}>{stateLabel}</div>
          {cp?.current_email && (
            <div className="text-xs text-[#6666aa] mt-1 font-mono">
              → <span className="text-[#06b6d4]">{cp.current_email}</span>
              {cp.current_account && (
                <span> · <span className="text-[#8b5cf6]">{cp.current_account}</span></span>
              )}
            </div>
          )}
        </div>

        {(cp?.total ?? 0) > 0 && (
          <div className="grid grid-cols-4 gap-3 w-full text-center">
            {[
              { label: 'Отправлено', value: cp?.sent ?? 0,     color: '#10b981' },
              { label: 'Ошибок',     value: cp?.failed ?? 0,   color: '#ef4444' },
              { label: 'Осталось',   value: Math.max(0, (cp?.total ?? 0) - (cp?.sent ?? 0) - (cp?.failed ?? 0)), color: '#6666aa' },
              { label: 'Скорость',   value: `${speed}/м`,      color: '#06b6d4' },
            ].map(s => (
              <div key={s.label} className="card-inset py-3">
                <div className="text-base font-bold tabular-nums" style={{ color: s.color }}>{s.value}</div>
                <div className="text-[10px] text-[#6666aa] mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Buttons */}
        <div className="flex items-center gap-3">
          {!run && !paused && (
            <button onClick={() => act(api.campaign.start)}
              disabled={busy || ready === 0 || recs === 0}
              className="btn btn-primary px-8 py-2.5 text-sm">
              <Play size={16} /> Начать рассылку
            </button>
          )}
          {run && (
            <>
              <button onClick={() => act(api.campaign.pause)} disabled={busy}
                className="btn btn-secondary px-6">
                <Pause size={15} /> Пауза
              </button>
              <button onClick={() => act(api.campaign.stop)} disabled={busy}
                className="btn btn-danger px-6">
                <Square size={15} /> Стоп
              </button>
            </>
          )}
          {paused && (
            <>
              <button onClick={() => act(api.campaign.start)} disabled={busy}
                className="btn btn-primary px-6">
                <Play size={15} /> Продолжить
              </button>
              <button onClick={() => act(api.campaign.stop)} disabled={busy}
                className="btn btn-danger px-6">
                <Square size={15} /> Стоп
              </button>
            </>
          )}
          {(done || err) && (
            <button onClick={() => act(api.campaign.stop)} disabled={busy}
              className="btn btn-secondary px-6">
              <RefreshCw size={15} /> Сбросить
            </button>
          )}
        </div>
      </div>

      {/* Errors */}
      {cp?.errors && cp.errors.length > 0 && (
        <div className="card space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#f59e0b] uppercase tracking-wider">
            <AlertTriangle size={13} /> Ошибки отправки ({cp.errors.length})
          </div>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {cp.errors.slice(-20).map((e, i) => (
              <div key={i} className="text-xs font-mono text-[#ef4444]/80 bg-[#ef4444]/5 px-2.5 py-1 rounded">
                {e}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
