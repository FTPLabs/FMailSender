import { useEffect, useState } from 'react'
  import { motion } from 'framer-motion'
  import { Play, Pause, Square, RefreshCw, AlertTriangle } from 'lucide-react'
  import { api, type AppStatus } from '../api'

  function RingProgress({ value, max }: { value: number; max: number }) {
    const pct = max > 0 ? Math.min(value / max, 1) : 0
    const R = 54, C = 2 * Math.PI * R
    const dash = pct * C
    return (
      <svg width="128" height="128" viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={R} fill="none" stroke="#1c1c35" strokeWidth="12" />
        <circle cx="64" cy="64" r={R} fill="none" stroke="#8b5cf6" strokeWidth="12"
          strokeDasharray={`${dash} ${C}`} strokeLinecap="round"
          transform="rotate(-90 64 64)"
          style={{ transition: 'stroke-dasharray 0.5s ease' }} />
        <text x="64" y="60" textAnchor="middle" fill="#e8e8ff" fontSize="20" fontWeight="bold" fontFamily="Inter">
          {Math.round(pct * 100)}%
        </text>
        <text x="64" y="80" textAnchor="middle" fill="#6666aa" fontSize="11" fontFamily="Inter">
          {value}/{max}
        </text>
      </svg>
    )
  }

  export default function Sending() {
    const [status, setStatus] = useState<AppStatus | null>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
      const poll = () => api.status().then(setStatus).catch(() => null)
      poll()
      const id = setInterval(poll, 1000)
      return () => clearInterval(id)
    }, [])

    const campaign = status?.campaign
    const state = campaign?.state ?? 'idle'
    const isRunning = state === 'running'
    const isPaused  = state === 'paused'
    const isDone    = state === 'done'
    const isError   = state === 'error'

    const accounts = status?.accounts
    const ready    = accounts?.ready ?? 0

    async function start() {
      setLoading(true)
      try { await api.campaign.start(); await api.status().then(setStatus) }
      catch(e: any) { alert(e.response?.data?.detail ?? e.message) }
      finally { setLoading(false) }
    }
    async function pause() { await api.campaign.pause(); api.status().then(setStatus) }
    async function stop()  { await api.campaign.stop(); api.status().then(setStatus) }

    const elapsedMin = campaign?.started_at
      ? Math.round((Date.now() / 1000 - campaign.started_at) / 60)
      : 0
    const speed = elapsedMin > 0 && campaign?.sent
      ? Math.round(campaign.sent / elapsedMin)
      : 0

    return (
      <div className="space-y-6 animate-fade-in max-w-3xl">
        <div>
          <h1 className="text-2xl font-bold text-text">Рассылка</h1>
          <p className="text-muted text-sm mt-1">Запуск, пауза и мониторинг кампании</p>
        </div>

        {/* Readiness check */}
        {!isRunning && !isPaused && !isDone && (
          <div className="card space-y-3">
            <h2 className="text-sm font-semibold text-text">Готовность</h2>
            <div className="space-y-2">
              {[
                { label: 'Аккаунтов готово',   ok: ready > 0,                  value: `${ready} аккаунтов` },
                { label: 'Получатели загружены', ok: (status?.recipients ?? 0) > 0, value: `${status?.recipients ?? 0} получателей` },
                { label: 'Тема письма',         ok: true,                       value: 'Проверьте во вкладке Письмо' },
              ].map(row => (
                <div key={row.label} className="flex items-center gap-3 text-sm">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
                    ${row.ok ? 'bg-success/20 text-success' : 'bg-error/20 text-error'}`}>
                    {row.ok ? '✓' : '✗'}
                  </span>
                  <span className="text-muted flex-1">{row.label}</span>
                  <span className="text-text text-xs">{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main control */}
        <div className="card flex flex-col items-center gap-6 py-8">
          {/* Ring */}
          <RingProgress value={campaign?.sent ?? 0} max={campaign?.total ?? (status?.recipients ?? 0)} />

          {/* State label */}
          <div className="text-center">
            <div className={`text-lg font-semibold ${
              isRunning ? 'text-cyan' : isDone ? 'text-success' : isError ? 'text-error' : isPaused ? 'text-warn' : 'text-muted'
            }`}>
              {isRunning ? '▶ Отправка...' :
               isPaused  ? '⏸ Пауза' :
               isDone    ? '✓ Завершено' :
               isError   ? '✗ Ошибка' : '⏹ Ожидание'}
            </div>
            {campaign?.current_email && (
              <div className="text-xs text-muted mt-1">
                → <span className="font-mono text-cyan">{campaign.current_email}</span>
                {campaign.current_account && <span className="text-muted"> · <span className="text-purple">{campaign.current_account}</span></span>}
              </div>
            )}
          </div>

          {/* Stats row */}
          {(campaign?.total ?? 0) > 0 && (
            <div className="grid grid-cols-4 gap-4 w-full text-center">
              {[
                { label: 'Отправлено', value: campaign?.sent ?? 0, color: 'text-success' },
                { label: 'Ошибок',     value: campaign?.failed ?? 0, color: 'text-error' },
                { label: 'Осталось',   value: (campaign?.total ?? 0) - (campaign?.sent ?? 0) - (campaign?.failed ?? 0), color: 'text-muted' },
                { label: 'Скорость',   value: `${speed}/мин`, color: 'text-cyan' },
              ].map(s => (
                <div key={s.label} className="bg-surf2 rounded-lg py-3">
                  <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
                  <div className="text-xs text-muted mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center gap-3">
            {!isRunning && !isPaused && (
              <button onClick={start} disabled={loading || ready === 0}
                className="btn-primary px-8 py-3 text-base">
                <Play size={18} />
                Начать рассылку
              </button>
            )}
            {isRunning && (
              <>
                <button onClick={pause} className="btn-secondary px-6 py-2.5">
                  <Pause size={16} /> Пауза
                </button>
                <button onClick={stop} className="btn-danger px-6 py-2.5">
                  <Square size={16} /> Стоп
                </button>
              </>
            )}
            {isPaused && (
              <>
                <button onClick={start} className="btn-primary px-6 py-2.5">
                  <Play size={16} /> Продолжить
                </button>
                <button onClick={stop} className="btn-danger px-6 py-2.5">
                  <Square size={16} /> Стоп
                </button>
              </>
            )}
            {(isDone || isError) && (
              <button onClick={stop} className="btn-secondary px-6 py-2.5">
                <RefreshCw size={16} /> Сбросить
              </button>
            )}
          </div>
        </div>

        {/* Errors */}
        {campaign?.errors && campaign.errors.length > 0 && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-warn">
              <AlertTriangle size={14} /> Ошибки отправки
            </div>
            <div className="max-h-40 overflow-y-auto space-y-1">
              {campaign.errors.slice(-20).map((e, i) => (
                <div key={i} className="text-xs font-mono text-error/80 bg-error/5 px-2 py-1 rounded">{e}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }
  