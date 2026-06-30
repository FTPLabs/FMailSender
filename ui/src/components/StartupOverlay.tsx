/**
   * StartupOverlay — экран загрузки + активации лицензии.
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

  const TIMEOUT_SECS = 60

  const MESSAGES: Array<{ at: number; text: string }> = [
    { at: 0,  text: 'Инициализация...'         },
    { at: 3,  text: 'Запуск Python ядра...'    },
    { at: 8,  text: 'Загрузка зависимостей...' },
    { at: 14, text: 'Старт FastAPI сервера...' },
    { at: 20, text: 'Соединение с бэкендом...' },
    { at: 26, text: 'Почти готово...'          },
  ]

  // Логотип — встроен как base64 SVG-заглушка пока PNG не загрузится
  function LogoImage({ size = 64 }: { size?: number }) {
    const [imgOk, setImgOk] = useState(false)
    return (
      <div
        className="rounded-2xl flex items-center justify-center overflow-hidden"
        style={{
          width: size, height: size,
          background: 'linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%)',
          boxShadow: '0 0 40px rgba(139,92,246,0.45)',
          animation: 'pulse-glow 2s ease-in-out infinite',
        }}
      >
        {imgOk ? (
          <img src="/fmail_logo.png" alt="FMailSender" style={{ width: size - 12, height: size - 12, objectFit: 'contain' }} />
        ) : (
          <img
            src="/fmail_logo.png"
            alt="FMailSender"
            style={{ width: size - 12, height: size - 12, objectFit: 'contain', display: 'none' }}
            onLoad={() => setImgOk(true)}
            onError={() => {}}
          />
        )}
        {!imgOk && <Zap size={size * 0.44} className="text-white" />}
      </div>
    )
  }

  export default function StartupOverlay() {
    const { online } = useStatus()

    const [elapsed,  setElapsed]  = useState(0)
    const [progress, setProgress] = useState(0)
    const [visible,  setVisible]  = useState(true)
    const [fadeOut,  setFadeOut]  = useState(false)
    const [version,  setVersion]  = useState('')
    const [licenseOk,   setLicenseOk]   = useState<boolean | null>(null)
    const [licenseMsg,  setLicenseMsg]  = useState('')
    const [licenseKey,  setLicenseKey]  = useState('')
    const [activating,  setActivating]  = useState(false)
    const [activateErr, setActivateErr] = useState('')

    useEffect(() => {
      if (!online) return
      fetch(`${getBaseUrl()}/api/health`)
        .then(r => r.json())
        .then((d: { version?: string }) => {
          if (!d?.version) return
          setVersion(`v${d.version}`)

          fetch(`${getBaseUrl()}/api/license`)
            .then(r => r.json())
            .then((lic: { valid?: boolean; message?: string }) => {
              setLicenseOk(lic.valid !== false)
              setLicenseMsg(lic.message ?? '')
            })
            .catch(() => setLicenseOk(true))

          if (d.version !== FRONTEND_VERSION) {
            console.warn(`[FMailSender] Version mismatch: backend=${d.version} frontend=${FRONTEND_VERSION}. Reloading…`)
            setTimeout(() => window.location.reload(), 600)
          }
        })
        .catch(() => {})
    }, [online])

    const startedAt = useRef(Date.now())
    const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)

    async function activateLicense() {
      if (!licenseKey.trim()) return
      setActivating(true); setActivateErr('')
      try {
        const res = await fetch(`${getBaseUrl()}/api/license/activate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: licenseKey.trim() }),
        })
        const data = await res.json()
        if (data.success) setLicenseOk(true)
        else setActivateErr(data.message || data.error || 'Ключ недействителен')
      } catch (e: unknown) { setActivateErr((e as Error).message || 'Ошибка сети') }
      finally { setActivating(false) }
    }

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

    useEffect(() => {
      if (!online || !visible) return
      if (licenseOk === null) return
      if (licenseOk === false) return
      setProgress(100)
      const t = setTimeout(() => {
        setFadeOut(true)
        setTimeout(() => setVisible(false), 500)
      }, 350)
      return () => clearTimeout(t)
    }, [online, visible, licenseOk])

    if (!visible) return null

    // ── Экран активации лицензии ─────────────────────────────────────────────
    if (online && licenseOk === false) {
      return (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #040410 0%, #0d0d2b 50%, #0a0a1f 100%)' }}
        >
          {/* Фоновое свечение */}
          <div style={{
            position: 'absolute', top: '30%', left: '50%', transform: 'translate(-50%, -50%)',
            width: 400, height: 400, borderRadius: '50%',
            background: 'radial-gradient(ellipse, rgba(139,92,246,0.12) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />

          <div
            className="relative w-full max-w-md mx-4 rounded-2xl p-8"
            style={{
              background: 'rgba(13,13,30,0.95)',
              border: '1px solid rgba(139,92,246,0.25)',
              boxShadow: '0 0 60px rgba(139,92,246,0.15), 0 25px 50px rgba(0,0,0,0.6)',
            }}
          >
            {/* Заголовок */}
            <div className="flex items-center gap-4 mb-6">
              <LogoImage size={52} />
              <div>
                <h1 className="text-xl font-bold" style={{ color: '#e8e8ff' }}>FMailSender</h1>
                <p className="text-sm" style={{ color: '#6666aa' }}>Активация лицензии</p>
              </div>
            </div>

            {/* Статус */}
            <p className="text-sm mb-5" style={{ color: '#a0a0cc' }}>
              {licenseMsg || 'Лицензия не активирована. Введите ключ для продолжения.'}
            </p>

            {/* Поле ввода */}
            <input
              className="w-full rounded-xl px-4 py-3 font-mono text-sm mb-3 focus:outline-none transition-colors"
              style={{
                background: 'rgba(139,92,246,0.08)',
                border: '1px solid rgba(139,92,246,0.3)',
                color: '#e8e8ff',
              }}
              placeholder="FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
              value={licenseKey}
              onChange={e => { setLicenseKey(e.target.value); setActivateErr('') }}
              onKeyDown={e => e.key === 'Enter' && activateLicense()}
              onFocus={e => (e.target.style.borderColor = 'rgba(139,92,246,0.7)')}
              onBlur={e => (e.target.style.borderColor = 'rgba(139,92,246,0.3)')}
            />

            {/* Ошибка */}
            {activateErr && (
              <p className="text-sm mb-3" style={{ color: '#f87171' }}>{activateErr}</p>
            )}

            {/* Кнопка */}
            <button
              onClick={activateLicense}
              disabled={activating || !licenseKey.trim()}
              className="w-full rounded-xl px-4 py-3 font-semibold transition-all"
              style={{
                background: activating || !licenseKey.trim()
                  ? 'rgba(139,92,246,0.3)'
                  : 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                color: activating || !licenseKey.trim() ? 'rgba(232,232,255,0.4)' : '#fff',
                cursor: activating || !licenseKey.trim() ? 'not-allowed' : 'pointer',
                boxShadow: activating || !licenseKey.trim() ? 'none' : '0 0 20px rgba(139,92,246,0.4)',
              }}
            >
              {activating ? 'Проверка...' : 'Активировать'}
            </button>

            {/* Футер */}
            <p className="text-xs mt-4 text-center" style={{ color: '#3a3a66' }}>
              Ключ привязывается к этому устройству · Поддержка: fmail.shop
            </p>
          </div>

          <style>{`
            @keyframes pulse-glow {
              0%, 100% { box-shadow: 0 0 30px rgba(139,92,246,0.4); }
              50%       { box-shadow: 0 0 55px rgba(139,92,246,0.7), 0 0 20px rgba(6,182,212,0.3); }
            }
          `}</style>
        </div>
      )
    }

    // ── Экран загрузки ────────────────────────────────────────────────────────
    const msg  = [...MESSAGES].reverse().find(m => elapsed >= m.at)?.text ?? MESSAGES[0].text
    const dots = '.'.repeat(Math.floor(elapsed * 2) % 4)

    return (
      <div
        className="fixed inset-0 z-50 flex flex-col items-center justify-center"
        style={{
          background: '#040410',
          transition: 'opacity 0.5s ease',
          opacity: fadeOut ? 0 : 1,
          pointerEvents: fadeOut ? 'none' : 'all',
        }}
      >
        <div className="mb-8 flex flex-col items-center gap-4">
          <LogoImage size={64} />
          <div className="text-center">
            <div className="text-xl font-semibold tracking-tight" style={{ color: '#e8e8ff' }}>
              FMail Sender
            </div>
            <div className="text-xs mt-1" style={{ color: '#6666aa' }}>
              {version || `v${FRONTEND_VERSION}`}
            </div>
          </div>
        </div>

        <div className="w-64 space-y-3">
          <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1a1a2e' }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.round(progress)}%`,
                background: 'linear-gradient(90deg, #8b5cf6, #06b6d4)',
                transition: online ? 'width 0.3s ease-out' : 'width 0.2s linear',
              }}
            />
          </div>
          <div className="text-center text-xs min-h-[1rem]" style={{ color: '#6666aa' }}>
            {online
              ? <span style={{ color: '#10b981' }}>Готово</span>
              : <span>{msg}{dots}</span>
            }
          </div>
        </div>

        {elapsed > 5 && !online && (
          <div className="mt-4 text-[10px]" style={{ color: '#3a3a66' }}>
            {Math.round(elapsed)}с / {TIMEOUT_SECS}с
          </div>
        )}

        {elapsed > TIMEOUT_SECS + 2 && !online && (
          <div className="mt-6 max-w-xs text-center text-xs px-4" style={{ color: 'rgba(239,68,68,0.7)' }}>
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
  