/**
 * StartupOverlay — loading screen + license activation.
 *
 * v6.8.2 startup flow:
 *   1. Tauri spawns fmail-core (background thread — window opens IMMEDIATELY)
 *   2. Rust emits core://status events → we show real-time progress
 *   3. Python starts, uvicorn ready → port opens
 *   4. StatusContext detects backend online (polls /api/status every 500ms)
 *   5. UI calls GET /api/license → returns LOCAL CACHE instantly
 *      - valid=true  → overlay dismissed
 *      - valid=false → activation screen shown
 *
 * AV cold-start retry:
 *   - Rust retries spawn up to 25 times if AV kills the process immediately
 *   - UI shows real-time stage messages from Rust
 *   - After WARN_SECS: "still working..." message (not an error)
 *   - After TIMEOUT_SECS: show "Перезапустить ядро" button + advisory
 *   - StatusContext continues polling FOREVER — auto-recovers when core starts
 */
import { useEffect, useRef, useState } from 'react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'
import { FRONTEND_VERSION } from '../version'

// Show "still scanning" advisory after this many seconds
const WARN_SECS    = 45
// After this many seconds, show the manual retry button
const TIMEOUT_SECS = 120

interface CoreStatus {
  stage:   string
  message: string
  attempt: number
}

// Safe Tauri event listener — works in Tauri runtime, no-ops in browser
async function listenCoreStatus(
  cb: (payload: CoreStatus) => void
): Promise<(() => void) | null> {
  try {
    // Tauri v2 injects window.__TAURI_INTERNALS__ in the WebView
    const tauri = (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ as
      { invoke?: unknown; event?: { listen?: (evt: string, cb: (e: { payload: unknown }) => void) => Promise<() => void> } } | undefined
    const listen = tauri?.event?.listen
    if (typeof listen !== 'function') return null
    const unlisten = await listen('core://status', (e) => cb(e.payload as CoreStatus))
    return unlisten
  } catch {
    return null
  }
}

// Safe Tauri invoke — works in Tauri runtime, no-ops in browser
async function invokeTauri(cmd: string): Promise<void> {
  try {
    const tauri = (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ as
      { invoke?: (cmd: string) => Promise<void> } | undefined
    if (typeof tauri?.invoke === 'function') await tauri.invoke(cmd)
  } catch { /* not in Tauri context */ }
}

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
        width: size, height: size, borderRadius: '50%', objectFit: 'cover',
        flexShrink: 0, border: '1.5px solid rgba(139,92,246,0.5)',
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
  // Real-time message from Rust core://status events
  const [coreStage,   setCoreStage]   = useState('')
  const [coreMsg,     setCoreMsg]     = useState('')
  const [restarting,  setRestarting]  = useState(false)

  const startedAt    = useRef(Date.now())
  const onlineRef    = useRef(false)
  const licenseOkRef = useRef<boolean | null>(null)

  useEffect(() => { onlineRef.current   = online    }, [online])
  useEffect(() => { licenseOkRef.current = licenseOk }, [licenseOk])

  // ── Listen to Tauri core://status events ──────────────────────────────────
  useEffect(() => {
    let unlisten: (() => void) | null = null
    listenCoreStatus((payload) => {
      setCoreStage(payload.stage)
      setCoreMsg(payload.message)
    }).then(fn => { unlisten = fn })
    return () => { unlisten?.() }
  }, [])

  // ── Step 1: fetch license the moment backend comes online ─────────────────
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
          setLicenseOk(false); setLicenseMsg('Не удалось получить статус лицензии'); return
        }
        setLicenseOk(lic.valid === true)
        setLicenseMsg(lic.message ?? '')
        setBgChecking(lic.background_checking === true)
      })
      .catch(() => { setLicenseOk(false); setLicenseMsg('Не удалось проверить лицензию.') })
  }, [online])

  // ── Step 2: poll /api/license/poll to catch background result ────────────
  useEffect(() => {
    if (!online || licenseOk === null) return
    const iv = setInterval(async () => {
      try {
        const s: { valid?: boolean; checking?: boolean } =
          await fetch(`${getBaseUrl()}/api/license/poll`).then(r => r.json())
        setBgChecking(s.checking === true)
        if (s.valid === false && licenseOkRef.current === true) {
          setLicenseOk(false); setLicenseMsg('Лицензия отозвана или истекла')
        } else if (s.valid === true && licenseOkRef.current === false) {
          setLicenseOk(true); setLicenseMsg('')
        }
      } catch { /* server temporarily unreachable */ }
    }, 10_000)
    return () => clearInterval(iv)
  }, [online, licenseOk])

  // Re-show overlay when license becomes invalid mid-session
  useEffect(() => {
    if (licenseOk === false) { setVisible(true); setFadeOut(false) }
  }, [licenseOk])

  // Timer — runs regardless of online state
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

  // Dismiss loading overlay when license confirmed valid
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
    setActivating(true); setActivateErr('')
    try {
      const res  = await fetch(`${getBaseUrl()}/api/license/activate`, {
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

  async function handleRestartCore() {
    setRestarting(true)
    setCoreMsg('Перезапуск Python ядра...')
    await invokeTauri('restart_core')
    // reset timer
    startedAt.current = Date.now()
    setElapsed(0)
    setProgress(0)
    setTimeout(() => setRestarting(false), 3000)
  }

  if (!visible) return null

  // ── License activation screen ─────────────────────────────────────────────
  if (online && licenseOk === false) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center"
        style={{ background: 'linear-gradient(160deg, #030308 0%, #08081e 55%, #040410 100%)', gap: '2rem' }}>
        <div style={{
          position: 'absolute', top: '38%', left: '50%',
          transform: 'translate(-50%, -50%)', width: 480, height: 480, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(139,92,246,0.09) 0%, transparent 72%)',
          pointerEvents: 'none',
        }} />
        <div className="relative flex flex-col items-center gap-3">
          <AppLogo size={88} />
          <div className="text-center mt-1">
            <h1 className="text-[1.5rem] font-bold tracking-tight" style={{ color: '#e8e8ff' }}>FMailSender</h1>
            <p className="text-[0.8rem] mt-0.5 font-medium" style={{ color: '#6b6baa' }}>Активация лицензии</p>
          </div>
        </div>
        <div className="relative w-full rounded-2xl p-6"
          style={{ maxWidth: 360, background: 'rgba(8,8,24,0.92)', border: '1px solid rgba(139,92,246,0.18)', boxShadow: '0 24px 64px rgba(0,0,0,0.55)' }}>
          {licenseMsg && (
            <p className="text-[0.82rem] mb-4 leading-snug" style={{ color: '#9090cc' }}>{licenseMsg}</p>
          )}
          {bgChecking && (
            <p className="text-[0.75rem] mb-3" style={{ color: '#5858aa' }}>Идёт проверка лицензии на сервере...</p>
          )}
          <input
            className="w-full rounded-xl px-4 py-3 font-mono text-[0.82rem] focus:outline-none"
            style={{ background: 'rgba(139,92,246,0.07)', border: '1px solid rgba(139,92,246,0.28)', color: '#e8e8ff', marginBottom: '0.75rem', transition: 'border-color 0.15s' }}
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
              background: activating || !licenseKey.trim() ? 'rgba(124,58,237,0.22)' : 'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)',
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
  const elapsedRound = Math.round(elapsed)
  const isTimeout    = elapsed > TIMEOUT_SECS && !online
  const isWarning    = elapsed > WARN_SECS    && !online

  // Priority: Rust event message > fallback text based on elapsed
  const fallbackMsg = elapsed < 3  ? 'Инициализация...'
                    : elapsed < 10 ? 'Запуск Python ядра...'
                    : elapsed < 20 ? 'Загрузка зависимостей...'
                    : elapsed < 35 ? 'Старт FastAPI сервера...'
                    : elapsed < 50 ? 'Антивирус сканирует ядро...'
                    :                'Ожидание антивируса...'

  const displayMsg   = online
    ? licenseOk === null ? 'Проверка лицензии...' : 'Готово'
    : coreMsg || fallbackMsg

  const dots = !online ? '.'.repeat(Math.floor(elapsed * 2) % 4) : ''

  // Stage-based color
  const msgColor = coreStage === 'killed'  ? '#f59e0b'   // amber — AV retry
                 : coreStage === 'failed'  ? '#ef4444'   // red
                 : coreStage === 'ready'   ? '#10b981'   // green
                 : online                  ? '#10b981'
                 : isTimeout               ? 'rgba(239,68,68,0.85)'
                 : isWarning               ? '#f59e0b'
                 : '#6666aa'

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ background: '#040410', opacity: fadeOut ? 0 : 1, transition: 'opacity 0.4s ease', pointerEvents: fadeOut ? 'none' : 'all' }}
    >
      <div className="mb-8 flex flex-col items-center gap-4">
        <AppLogo size={72} />
        <div className="text-center">
          <div className="text-xl font-semibold tracking-tight" style={{ color: '#e8e8ff' }}>FMail Sender</div>
          <div className="text-xs mt-1" style={{ color: '#6666aa' }}>{version || `v${FRONTEND_VERSION}`}</div>
        </div>
      </div>

      <div className="w-64 space-y-3">
        <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1a1a2e' }}>
          <div className="h-full rounded-full"
            style={{
              width: `${Math.round(progress)}%`,
              background: 'linear-gradient(90deg, #8b5cf6, #06b6d4)',
              transition: online ? 'width 0.3s ease-out' : 'width 0.2s linear',
            }}
          />
        </div>
        <div className="text-center text-xs min-h-[1rem]" style={{ color: msgColor }}>
          <span>{displayMsg}{dots}</span>
        </div>
      </div>

      {/* Timer — only show while waiting */}
      {elapsed > 5 && !online && (
        <div className="mt-4 text-[10px]" style={{ color: '#3a3a66' }}>
          {elapsedRound}с / {TIMEOUT_SECS}с
        </div>
      )}

      {/* AV scan advisory (not an error — just informational) */}
      {isWarning && !isTimeout && !online && coreStage !== 'failed' && (
        <div className="mt-5 max-w-xs text-center text-[11px] px-4 leading-relaxed"
          style={{ color: 'rgba(245,158,11,0.75)' }}>
          Антивирус сканирует ядро при первом запуске.<br />
          Это нормально — подождите ещё немного.
        </div>
      )}

      {/* Timeout advisory + retry button */}
      {isTimeout && !online && (
        <div className="mt-5 flex flex-col items-center gap-3 max-w-xs px-4">
          <p className="text-center text-xs leading-relaxed"
            style={{ color: 'rgba(239,68,68,0.8)' }}>
            {coreStage === 'failed'
              ? coreMsg
              : `Python ядро не ответило в течение ${TIMEOUT_SECS}с. ` +
                `Антивирус всё ещё может сканировать файл — ` +
                `приложение продолжает попытки автоматически.`
            }
          </p>

          {coreStage === 'failed' && (
            <p className="text-center text-[10px]" style={{ color: '#5858aa' }}>
              Добавьте %LOCALAPPDATA%\FMailSender в исключения антивируса,<br />
              затем нажмите «Перезапустить ядро».
            </p>
          )}

          <button
            onClick={handleRestartCore}
            disabled={restarting}
            className="rounded-xl px-5 py-2 text-xs font-semibold"
            style={{
              background: restarting ? 'rgba(124,58,237,0.22)' : 'rgba(124,58,237,0.35)',
              border: '1px solid rgba(139,92,246,0.45)',
              color: restarting ? 'rgba(232,232,255,0.4)' : '#e8e8ff',
              cursor: restarting ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {restarting ? 'Перезапуск...' : '↺ Перезапустить ядро'}
          </button>
        </div>
      )}

      <style>{GLOW_STYLES}</style>
    </div>
  )
}
