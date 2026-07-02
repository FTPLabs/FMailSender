/**
 * StartupOverlay — loading screen + license activation.
 *
 * v6.8.0 startup flow (target: <10 s on warm start):
 *   1. Tauri spawns fmail-core (cached binary — no AV re-scan on warm start)
 *   2. Python starts, uvicorn ready → port opens (~4-7 s)
 *   3. UI calls GET /api/health → instant
 *   4. UI calls GET /api/license → returns LOCAL CACHE instantly (<5 ms)
 *      - valid=true  → overlay dismissed immediately, app shown
 *      - valid=false → activation screen shown immediately
 *   5. Background: full WMIC + HTTP validation runs concurrently
 *   6. UI polls GET /api/license/poll every 10 s
 *      - if status changes valid→false → activation screen (license revoked)
 *      - if status changes false→true  → overlay dismissed (rare: cached stale)
 */
import { useEffect, useRef, useState } from 'react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'
import { FRONTEND_VERSION } from '../version'

// Cold start (first-ever run, AV scan on extracted binary): up to 60 s.
// v6.8.1: Tauri setup() now runs in background thread → window opens IMMEDIATELY.
// Warm start (cached binary): 5-8 s. Background license check does NOT block.
const TIMEOUT_SECS = 60

const MESSAGES: Array<{ at: number; text: string }> = [
  { at: 0,  text: 'Инициализация...'         },
  { at: 3,  text: 'Запуск Python ядра...'    },
  { at: 10, text: 'Загрузка зависимостей...' },
  { at: 20, text: 'Старт FastAPI сервера...' },
  { at: 30, text: 'Соединение с бэкендом...' },
  { at: 50, text: 'Антивирус проверяет файл...(первый запуск)' },
]

const GLOW_STYLES = `
  @keyframes logo-glow {
    0%, 100% { box-shadow: 0 0 28px rgba(139,92,246,0.40), 0 0 60px rgba(6,182,212,0.08); }
    50%       { box-shadow: 0 0 52px rgba(139,92,246,0.70), 0 0 90px rgba(6,182,212,0.22); }
  }
`

function AppLogo({ size = 72 }: { size?: number }) {
  return (
    <img
      src="./fmail_logo.png"
      alt="FMailSender"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        objectFit: 'cover',
        flexShrink: 0,
        border: '1.5px solid rgba(139,92,246,0.5)',
        animation: 'logo-glow 2.5s ease-in-out infinite',
      }}
    />
  )
}

export default function StartupOverlay() {
  const { online } = useStatus()

  const [elapsed,     setElapsed]     = useState(0)
  const [progress,    setProgress]    = useState(0)
  const [visible,     setVisible]     = useState(true)
  const [fadeOut,     setFadeOut]     = useState(false)
  const [version,     setVersion]     = useState('')
  const [licenseOk,   setLicenseOk]   = useState<boolean | null>(null)
  const [licenseMsg,  setLicenseMsg]  = useState('')
  const [licenseKey,  setLicenseKey]  = useState('')
  const [activating,  setActivating]  = useState(false)
  const [activateErr, setActivateErr] = useState('')
  const [bgChecking,  setBgChecking]  = useState(false)

  const startedAt   = useRef(Date.now())
  const onlineRef   = useRef(false)
  const licenseOkRef = useRef<boolean | null>(null)

  useEffect(() => { onlineRef.current   = online    }, [online])
  useEffect(() => { licenseOkRef.current = licenseOk }, [licenseOk])

  // ── Step 1: fetch license from cache the moment backend comes online ────────
  // GET /api/license now returns the LOCAL cache instantly (<5 ms) and fires
  // background online validation concurrently.  We act on the cached result
  // immediately — the app appears without waiting for any network call.
  useEffect(() => {
    if (!online) return
    fetch(`${getBaseUrl()}/api/health`)
      .then(r => r.json())
      .then((d: { version?: string }) => {
        if (d?.version) setVersion(`v${d.version}`)
        return fetch(`${getBaseUrl()}/api/license`)
      })
      .then(r => r.json())
      .then((lic: { valid?: boolean; message?: string; background_checking?: boolean } | null) => {
        if (!lic || typeof lic !== 'object') {
          setLicenseOk(false)
          setLicenseMsg('Не удалось получить статус лицензии')
          return
        }
        setLicenseOk(lic.valid === true)
        setLicenseMsg(lic.message ?? '')
        setBgChecking(lic.background_checking === true)
      })
      .catch(() => {
        setLicenseOk(false)
        setLicenseMsg('Не удалось проверить лицензию. Повторите попытку.')
      })
  }, [online])

  // ── Step 2: poll /api/license/poll to catch background validation result ────
  // Polling interval: 10 s.  This detects:
  //   - License revoked mid-session (background check or periodic hourly check)
  //   - Rare case: cache said invalid but online check confirms valid
  useEffect(() => {
    if (!online || licenseOk === null) return
    const interval = setInterval(async () => {
      try {
        const status: { valid?: boolean; checking?: boolean } =
          await fetch(`${getBaseUrl()}/api/license/poll`).then(r => r.json())
        setBgChecking(status.checking === true)
        if (status.valid === false && licenseOkRef.current === true) {
          setLicenseOk(false)
          setLicenseMsg('Лицензия отозвана или истекла')
        } else if (status.valid === true && licenseOkRef.current === false) {
          // Background check passed (cached was stale/invalid)
          setLicenseOk(true)
          setLicenseMsg('')
        }
      } catch { /* server temporarily unreachable — keep current state */ }
    }, 10_000)
    return () => clearInterval(interval)
  }, [online, licenseOk])

  // Re-show overlay when license becomes invalid mid-session (revoked remotely)
  useEffect(() => {
    if (licenseOk === false) {
      setVisible(true)
      setFadeOut(false)
    }
  }, [licenseOk])

  // Timer — only depends on visible so it never restarts when online changes
  useEffect(() => {
    if (!visible) return
    const timer = setInterval(() => {
      const sec = (Date.now() - startedAt.current) / 1000
      setElapsed(sec)
      if (!onlineRef.current) {
        const target = Math.min(sec / TIMEOUT_SECS, 1) * 90
        setProgress(p => p + (target - p) * 0.15)
      }
    }, 100)
    return () => clearInterval(timer)
  }, [visible])

  // Dismiss loading overlay when cached license is confirmed valid
  useEffect(() => {
    if (!online || !visible || licenseOk === null || licenseOk === false) return
    setProgress(100)
    const t = setTimeout(() => {
      setFadeOut(true)
      setTimeout(() => setVisible(false), 400)
    }, 200)
    return () => clearTimeout(t)
  }, [online, visible, licenseOk])

  async function activateLicense() {
    if (!licenseKey.trim()) return
    setActivating(true)
    setActivateErr('')
    try {
      const res = await fetch(`${getBaseUrl()}/api/license/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: licenseKey.trim() }),
      })
      const data = await res.json()
      if (data.success) setLicenseOk(true)
      else setActivateErr(data.message || data.error || 'Ключ недействителен')
    } catch (e: unknown) {
      setActivateErr((e as Error).message || 'Ошибка сети')
    } finally {
      setActivating(false)
    }
  }

  if (!visible) return null

  // ── License activation screen ─────────────────────────────────────────────
  if (online && licenseOk === false) {
    return (
      <div
        className="fixed inset-0 z-50 flex flex-col items-center justify-center"
        style={{
          background: 'linear-gradient(160deg, #030308 0%, #08081e 55%, #040410 100%)',
          gap: '2rem',
        }}
      >
        <div style={{
          position: 'absolute', top: '38%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 480, height: 480, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(139,92,246,0.09) 0%, transparent 72%)',
          pointerEvents: 'none',
        }} />

        <div className="relative flex flex-col items-center gap-3">
          <AppLogo size={88} />
          <div className="text-center mt-1">
            <h1 className="text-[1.5rem] font-bold tracking-tight" style={{ color: '#e8e8ff' }}>
              FMailSender
            </h1>
            <p className="text-[0.8rem] mt-0.5 font-medium" style={{ color: '#6b6baa' }}>
              Активация лицензии
            </p>
          </div>
        </div>

        <div
          className="relative w-full rounded-2xl p-6"
          style={{
            maxWidth: 360,
            background: 'rgba(8,8,24,0.92)',
            border: '1px solid rgba(139,92,246,0.18)',
            boxShadow: '0 24px 64px rgba(0,0,0,0.55)',
          }}
        >
          {licenseMsg && (
            <p className="text-[0.82rem] mb-4 leading-snug" style={{ color: '#9090cc' }}>
              {licenseMsg}
            </p>
          )}

          {bgChecking && (
            <p className="text-[0.75rem] mb-3" style={{ color: '#5858aa' }}>
              Идёт проверка лицензии на сервере...
            </p>
          )}

          <input
            className="w-full rounded-xl px-4 py-3 font-mono text-[0.82rem] focus:outline-none"
            style={{
              background: 'rgba(139,92,246,0.07)',
              border: '1px solid rgba(139,92,246,0.28)',
              color: '#e8e8ff',
              marginBottom: '0.75rem',
              transition: 'border-color 0.15s',
            }}
            placeholder="FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
            value={licenseKey}
            onChange={e => { setLicenseKey(e.target.value); setActivateErr('') }}
            onKeyDown={e => e.key === 'Enter' && activateLicense()}
            onFocus={e  => (e.target.style.borderColor = 'rgba(139,92,246,0.65)')}
            onBlur={e   => (e.target.style.borderColor = 'rgba(139,92,246,0.28)')}
          />

          {activateErr && (
            <p className="text-[0.78rem] mb-3" style={{ color: '#f87171' }}>{activateErr}</p>
          )}

          <button
            onClick={activateLicense}
            disabled={activating || !licenseKey.trim()}
            className="w-full rounded-xl px-4 py-3 font-semibold text-[0.9rem]"
            style={{
              background: activating || !licenseKey.trim()
                ? 'rgba(124,58,237,0.22)'
                : 'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)',
              color: activating || !licenseKey.trim() ? 'rgba(232,232,255,0.32)' : '#fff',
              cursor: activating || !licenseKey.trim() ? 'not-allowed' : 'pointer',
              boxShadow: activating || !licenseKey.trim() ? 'none' : '0 0 22px rgba(124,58,237,0.38)',
              transition: 'all 0.15s',
            }}
          >
            {activating ? 'Проверка...' : 'Активировать'}
          </button>
        </div>

        <p className="relative text-[0.7rem]" style={{ color: '#252550' }}>
          Ключ привязывается к устройству · Поддержка: fmail.shop
        </p>

        <style>{GLOW_STYLES}</style>
      </div>
    )
  }

  // ── Loading screen ────────────────────────────────────────────────────────
  const msg  = [...MESSAGES].reverse().find(m => elapsed >= m.at)?.text ?? MESSAGES[0].text
  const dots = '.'.repeat(Math.floor(elapsed * 2) % 4)

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{
        background: '#040410',
        opacity: fadeOut ? 0 : 1,
        transition: 'opacity 0.4s ease',
        pointerEvents: fadeOut ? 'none' : 'all',
      }}
    >
      <div className="mb-8 flex flex-col items-center gap-4">
        <AppLogo size={72} />
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
          {!online
            ? <span>{msg}{dots}</span>
            : licenseOk === null
              ? <span style={{ color: '#a0a0dd' }}>Проверка лицензии...</span>
              : <span style={{ color: '#10b981' }}>Готово</span>
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

      <style>{GLOW_STYLES}</style>
    </div>
  )
}
