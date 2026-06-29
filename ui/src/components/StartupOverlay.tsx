/**
 * StartupOverlay — экран загрузки, показывается пока Python core стартует.
 *
 * Логика:
 * - Показывается когда online=false.
 * - Прогресс-бар заполняется до ~90% за 30 секунд (реальный таймаут Tauri).
 * - При online=true: анимация заполнения до 100%, затем fadeOut.
 * - Сообщения меняются по elapsed-времени.
 * - Стабильность версий: если backend.version ≠ FRONTEND_VERSION,
 *   значит WebView2 загрузил старый index.html из кэша.
 *   Принудительный window.location.reload() исправит это.
 */
import { useEffect, useRef, useState } from 'react'
import { Zap } from 'lucide-react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'
import { FRONTEND_VERSION } from '../version'

const TIMEOUT_SECS = 30

const MESSAGES: Array<{ at: number; text: string }> = [
  { at: 0,  text: 'Инициализация...'         },
  { at: 3,  text: 'Запуск Python ядра...'    },
  { at: 8,  text: 'Загрузка зависимостей...' },
  { at: 14, text: 'Старт FastAPI сервера...' },
  { at: 20, text: 'Соединение с бэкендом...' },
  { at: 26, text: 'Почти готово...'          },
]

export default function StartupOverlay() {
  const { online } = useStatus()

  const [elapsed,  setElapsed]  = useState(0)
  const [progress, setProgress] = useState(0)
  const [visible,  setVisible]  = useState(true)
  const [fadeOut,  setFadeOut]  = useState(false)
  const [version,  setVersion]  = useState('')

  // Fetch backend version and check for stale WebView2 cache.
  useEffect(() => {
    if (!online) return
    fetch(`${getBaseUrl()}/api/health`)
      .then(r => r.json())
      .then((d: { version?: string }) => {
        if (!d?.version) return
        setVersion(`v${d.version}`)

        // Stale-cache guard: if the backend reports a different version than
        // what this JS bundle was built with, the old index.html was loaded
        // from WebView2's disk cache instead of the new bundle on disk.
        // A forced reload fetches a fresh index.html and picks up new JS chunks.
        if (d.version !== FRONTEND_VERSION) {
          console.warn(
            `[FMailSender] Version mismatch: backend=${d.version} frontend=${FRONTEND_VERSION}. Reloading…`
          )
          // Short delay so the user briefly sees the overlay before reload
          setTimeout(() => window.location.reload(), 600)
        }
      })
      .catch(() => {})
  }, [online])

  const startedAt = useRef(Date.now())
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  // Tick every 100ms
  useEffect(() => {
    if (!visible) return
    timerRef.current = setInterval(() => {
      const sec = (Date.now() - startedAt.current) / 1000
      setElapsed(sec)

      if (!online) {
        const target = Math.min(sec / TIMEOUT_SECS, 1) * 90
        setProgress(p => p + (target - p) * 0.15)
      }
    }, 100)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [visible, online])

  // When backend comes online: fill to 100% then fade out
  useEffect(() => {
    if (!online || !visible) return
    setProgress(100)
    const t = setTimeout(() => {
      setFadeOut(true)
      setTimeout(() => setVisible(false), 500)
    }, 350)
    return () => clearTimeout(t)
  }, [online, visible])

  if (!visible) return null

  const msg  = [...MESSAGES].reverse().find(m => elapsed >= m.at)?.text ?? MESSAGES[0].text
  const dots = '.'.repeat(Math.floor(elapsed * 2) % 4)

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#040410]"
      style={{
        transition: 'opacity 0.5s ease',
        opacity: fadeOut ? 0 : 1,
        pointerEvents: fadeOut ? 'none' : 'all',
      }}
    >
      {/* Logo */}
      <div className="mb-8 flex flex-col items-center gap-4">
        <div
          className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#8b5cf6] to-[#06b6d4]
                     flex items-center justify-center shadow-[0_0_40px_rgba(139,92,246,0.4)]"
          style={{ animation: 'pulse-glow 2s ease-in-out infinite' }}
        >
          <Zap size={28} className="text-white" />
        </div>
        <div className="text-center">
          <div className="text-xl font-semibold text-[#e8e8ff] tracking-tight">FMail Sender</div>
          <div className="text-xs text-[#6666aa] mt-1">{version || `v${FRONTEND_VERSION}`}</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-64 space-y-3">
        <div className="h-1 bg-[#1a1a2e] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#8b5cf6] to-[#06b6d4]"
            style={{
              width: `${Math.round(progress)}%`,
              transition: online ? 'width 0.3s ease-out' : 'width 0.2s linear',
            }}
          />
        </div>
        <div className="text-center text-xs text-[#6666aa] min-h-[1rem]">
          {online
            ? <span className="text-[#10b981]">Готово</span>
            : <span>{msg}{dots}</span>
          }
        </div>
      </div>

      {elapsed > 5 && !online && (
        <div className="mt-4 text-[10px] text-[#3a3a66]">
          {Math.round(elapsed)}с / {TIMEOUT_SECS}с
        </div>
      )}

      {elapsed > TIMEOUT_SECS + 2 && !online && (
        <div className="mt-6 max-w-xs text-center text-xs text-[#ef4444]/70 px-4">
          Python ядро не ответило в течение {TIMEOUT_SECS}с.
          Попробуйте перезапустить приложение.
        </div>
      )}

      <style>{`
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 30px rgba(139,92,246,0.35); }
          50%       { box-shadow: 0 0 50px rgba(139,92,246,0.65), 0 0 20px rgba(6,182,212,0.3); }
        }
      `}</style>
    </div>
  )
}
