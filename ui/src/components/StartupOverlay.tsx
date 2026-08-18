/**
 * StartupOverlay — loading screen + license activation.
 *
 * v7.1.4 fixes:
 *   - Failed state: немедленно показываем полную панель ошибки при coreStage='failed',
 *     не ждём 60 сек. Чёткий текст ошибки + большая кнопка перезапуска.
 *   - isTimeout порог: 300с (соответствует PORT_WAIT_SECS в main.rs v7.1.4).
 *   - Убран Nuitka hint (теперь используется PyInstaller + LOCALAPPDATA/pytemp кеш).
 *   - Hint для AV: "добавьте %LOCALAPPDATA%\FMailSender в исключения".
 *   - Retry кнопка видна сразу при failed (не через 60с).
 */
import { useEffect, useRef, useState } from 'react'
import { useStatus } from '../contexts/StatusContext'
import { getBaseUrl } from '../api'
import { FRONTEND_VERSION } from '../version'

// После этого времени показываем кнопку перезапуска (независимо от стадии)
const RETRY_AFTER_SECS = 60
// Подсказка про AV — через 20 сек
const DEFENDER_HINT_SECS = 20

interface CoreStatus {
  stage:   string
  message: string
  attempt: number
}

async function listenCoreStatus(
  cb: (payload: CoreStatus) => void
): Promise<(() => void) | null> {
  try {
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

async function invokeTauri(cmd: string): Promise<void> {
  try {
    const tauri = (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ as
      { invoke?: (cmd: string) => Promise<void> } | undefined
    if (typeof tauri?.invoke === 'function') await tauri.invoke(cmd)
  } catch { /* not in Tauri context */ }
}

const GLOW_STYLES = `
  @keyframes logo-glow {
    0%, 100% { box-shadow: 0 0 28px rgb(var(--c-accent) / .28), 0 0 60px rgb(var(--c-signal) / .08); }
    50%       { box-shadow: 0 0 42px rgb(var(--c-accent) / .46), 0 0 76px rgb(var(--c-signal) / .17); }
  }
`

function AppLogo({ size = 72 }: { size?: number }) {
  return (
    <img
      src="./fmail_nocturne_mark.png"
      alt="FMailSender"
      style={{
        width: size, height: size, borderRadius: '16px', objectFit: 'cover',
        flexShrink: 0, border: '1.5px solid rgb(var(--c-accent) / .55)',
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
  const [coreStage,   setCoreStage]   = useState('')
  const [coreMsg,     setCoreMsg]     = useState('')
  const [restarting,  setRestarting]  = useState(false)

  const startedAt    = useRef(Date.now())
  const onlineRef    = useRef(false)
  const licenseOkRef = useRef<boolean | null>(null)

  useEffect(() => { onlineRef.current    = online    }, [online])
  useEffect(() => { licenseOkRef.current = licenseOk }, [licenseOk])

  useEffect(() => {
    let unlisten: (() => void) | null = null
    listenCoreStatus((payload) => {
      setCoreStage(payload.stage)
      setCoreMsg(payload.message)
    }).then(fn => { unlisten = fn })
    return () => { unlisten?.() }
  }, [])

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

  useEffect(() => {
    if (licenseOk === false) { setVisible(true); setFadeOut(false) }
  }, [licenseOk])

  // Таймер — работает всегда
  useEffect(() => {
    if (!visible) return
    const timer = setInterval(() => {
      const sec = (Date.now() - startedAt.current) / 1000
      // Если ядро упало — останавливаем прогресс-бар на текущем значении
      if (coreStage === 'failed') return
      setElapsed(sec)
      if (!onlineRef.current) {
        const target = Math.min(sec / 300, 1) * 90  // PORT_WAIT_SECS=300
        setProgress(p => p + (target - p) * 0.12)
      }
    }, 100)
    return () => clearInterval(timer)
  }, [visible, coreStage])

  // Отдельный счётчик elapsed для отображения — всегда растёт
  const [displayElapsed, setDisplayElapsed] = useState(0)
  useEffect(() => {
    if (!visible) return
    const t = setInterval(() => {
      setDisplayElapsed(Math.round((Date.now() - startedAt.current) / 1000))
    }, 1000)
    return () => clearInterval(t)
  }, [visible])

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
      else setActivateErr(data.detail || data.message || data.error || 'Ключ недействителен')
    } catch (e: unknown) {
      setActivateErr('Сервер лицензий временно недоступен. Проверьте подключение и повторите попытку.')
    } finally {
      setActivating(false)
    }
  }

  async function handleRestartCore() {
    setRestarting(true)
    setCoreStage('')
    setCoreMsg('')
    startedAt.current = Date.now()
    setDisplayElapsed(0)
    setElapsed(0)
    setProgress(0)
    try {
      const bridge = (window as unknown as {
        fmailApp?: { restartApp?: () => Promise<boolean> }
      }).fmailApp
      if (typeof bridge?.restartApp === 'function') {
        await bridge.restartApp()
        return // Electron process exits immediately after scheduling relaunch.
      }
      window.location.reload()
    } catch (err) {
      setCoreStage('failed')
      setCoreMsg((err as Error).message || 'Не удалось перезапустить приложение')
      setRestarting(false)
    }
  }

  if (!visible) return null

  // ── License activation screen ─────────────────────────────────────────────
  if (online && licenseOk === false) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center"
        style={{ background: 'linear-gradient(160deg, rgb(var(--c-base)) 0%, rgb(var(--c-surf2)) 55%, rgb(var(--c-base)) 100%)', gap: '2rem' }}>
        <div style={{
          position: 'absolute', top: '38%', left: '50%',
          transform: 'translate(-50%, -50%)', width: 480, height: 480, borderRadius: '50%',
          background: 'radial-gradient(ellipse, rgba(139,92,246,0.09) 0%, transparent 72%)',
          pointerEvents: 'none',
        }} />
        <div className="relative flex flex-col items-center gap-3">
          <AppLogo size={88} />
          <div className="text-center mt-1">
            <h1 className="text-[1.5rem] font-bold tracking-tight" style={{ color: 'rgb(var(--c-text))' }}>FMAIL / NOCTURNE</h1>
            <p className="text-[0.8rem] mt-0.5 font-medium" style={{ color: 'rgb(var(--c-muted))' }}>Активация лицензии</p>
          </div>
        </div>
        <div className="relative w-full rounded-2xl p-6"
          style={{ maxWidth: 360, background: 'rgba(8,8,24,0.92)', border: '1px solid rgba(139,92,246,0.18)', boxShadow: '0 24px 64px rgba(0,0,0,0.55)' }}>
          {licenseMsg && (
            <p className="text-[0.82rem] mb-4 leading-snug" style={{ color: 'rgb(var(--c-muted))' }}>{licenseMsg}</p>
          )}
          {bgChecking && (
            <p className="text-[0.75rem] mb-3" style={{ color: 'rgb(var(--c-muted))' }}>Идёт проверка лицензии на сервере...</p>
          )}
          <input
            className="w-full rounded-xl px-4 py-3 font-mono text-[0.82rem] focus:outline-none"
            style={{ background: 'rgb(var(--c-accent) / .07)', border: '1px solid rgb(var(--c-accent) / .28)', color: 'rgb(var(--c-text))', marginBottom: '0.75rem', transition: 'border-color 0.15s' }}
            placeholder="FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
            value={licenseKey}
            onChange={e => { setLicenseKey(e.target.value); setActivateErr('') }}
            onKeyDown={e => e.key === 'Enter' && activateLicense()}
            onFocus={e  => (e.target.style.borderColor = 'rgba(139,92,246,0.65)')}
            onBlur={e   => (e.target.style.borderColor = 'rgb(var(--c-accent) / .28)')}
          />
          {activateErr && (
            <p className="text-[0.78rem] mb-3" style={{ color: 'rgb(var(--c-error))' }}>{activateErr}</p>
          )}
          <button
            onClick={activateLicense}
            disabled={activating || !licenseKey.trim()}
            className="w-full rounded-xl px-4 py-3 font-semibold text-[0.9rem]"
            style={{
              background: activating || !licenseKey.trim() ? 'rgb(var(--c-accent) / .22)' : 'linear-gradient(135deg, rgb(var(--c-accent-dark)) 0%, rgb(var(--c-accent-dark)) 100%)',
              color: activating || !licenseKey.trim() ? 'rgb(var(--c-text) / .32)' : '#fff',
              cursor: activating || !licenseKey.trim() ? 'not-allowed' : 'pointer',
              boxShadow: activating || !licenseKey.trim() ? 'none' : '0 0 22px rgba(124,58,237,0.38)',
              transition: 'all 0.15s',
            }}
          >
            {activating ? 'Проверка...' : 'Активировать'}
          </button>
        </div>
        <p className="relative text-[0.7rem]" style={{ color: 'rgb(var(--c-dim))' }}>
          Ключ привязывается к устройству · Поддержка: fmail.shop
        </p>
        <style>{GLOW_STYLES}</style>
      </div>
    )
  }

  // ── Loading screen ────────────────────────────────────────────────────────
  const isFailed = coreStage === 'failed'
  // Показываем кнопку перезапуска: немедленно при failed, или через 60 сек
  const showRetry = isFailed || (displayElapsed > RETRY_AFTER_SECS && !online)
  // Подсказка AV через 20 сек
  const showDefenderHint = displayElapsed > DEFENDER_HINT_SECS && !online && !isFailed

  const stageHint: Record<string, string> = {
    extracting: 'Извлечение ядра приложения...',
    av_wait:    'Запуск Python ядра...',
    spawning:   'Запуск Python ядра...',
    killed:     'Ядро перезапускается...',
    running:    'Ожидание ответа ядра...',
    ready:      'Готово',
    failed:     'Ошибка запуска ядра',
  }

  const fallbackMsg = displayElapsed < 3  ? 'Инициализация...'
                    : displayElapsed < 10 ? 'Запуск Python ядра...'
                    : displayElapsed < 20 ? 'Загрузка модулей...'
                    : displayElapsed < 40 ? 'Старт FastAPI сервера...'
                    : displayElapsed < 70 ? 'Ожидание сервера...'
                    : displayElapsed < 120 ? 'AV проверяет файлы...'
                    :                        'Ожидание ядра...'

  const displayMsg = online
    ? (licenseOk === null ? 'Проверка лицензии...' : 'Готово')
    : isFailed
    ? 'Ядро не запустилось'
    : (coreStage && stageHint[coreStage]) || coreMsg || fallbackMsg

  const dots = (!online && !isFailed) ? '.'.repeat(Math.floor(displayElapsed * 2) % 4) : ''

  const msgColor = isFailed                ? 'rgb(var(--c-error))'
                 : coreStage === 'ready'   ? 'rgb(var(--c-success))'
                 : online                  ? 'rgb(var(--c-success))'
                 : displayElapsed > 300    ? 'rgba(239,68,68,0.85)'
                 : 'rgb(var(--c-muted))'

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ background: 'rgb(var(--c-base))', opacity: fadeOut ? 0 : 1, transition: 'opacity 0.4s ease', pointerEvents: fadeOut ? 'none' : 'all' }}
    >
      <div className="mb-8 flex flex-col items-center gap-4">
        <AppLogo size={72} />
        <div className="text-center">
          <div className="text-xl font-semibold tracking-tight" style={{ color: 'rgb(var(--c-text))' }}>FMAIL / NOCTURNE</div>
        </div>
      </div>

      <div className="w-64 space-y-3">
        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'rgb(var(--c-surf2))' }}>
          <div className="h-full rounded-full"
            style={{
              width: `${Math.round(progress)}%`,
              background: isFailed ? 'rgb(var(--c-error))' : 'linear-gradient(90deg, rgb(var(--c-accent)), rgb(var(--c-signal)))',
              transition: online ? 'width 0.3s ease-out' : 'width 0.2s linear',
            }}
          />
        </div>
        <div className="text-center text-xs min-h-[1rem]" style={{ color: msgColor }}>
          <span>{displayMsg}{dots}</span>
        </div>
        {!online && displayElapsed > 5 && !isFailed && (
          <div className="text-center text-[0.68rem]" style={{ color: 'rgb(var(--c-muted))' }}>
            {displayElapsed} сек
          </div>
        )}
      </div>

      {/* AV hint — через 20 сек */}
      {showDefenderHint && (
        <div className="mt-4 max-w-xs px-4 text-center">
          <p className="text-[0.7rem] leading-relaxed" style={{ color: 'rgb(var(--c-muted))' }}>
            Антивирус проверяет файлы ядра при первом запуске (20–60 сек).
            Добавьте папку <code style={{ color: 'rgb(var(--c-muted))' }}>%LOCALAPPDATA%\FMailSender</code> в исключения.
          </p>
        </div>
      )}

      {/* Панель ошибки — показывается немедленно при failed */}
      {isFailed && (
        <div className="mt-5 max-w-sm px-4 w-full">
          <div className="rounded-xl p-4" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.22)' }}>
            <p className="text-[0.78rem] leading-relaxed mb-3" style={{ color: 'rgba(252,165,165,0.9)' }}>
              {coreMsg || 'Не удалось запустить локальное ядро.'}
            </p>
            <p className="text-[0.7rem] leading-relaxed" style={{ color: 'rgb(var(--c-muted))' }}>
              Добавьте <code>%LOCALAPPDATA%\FMailSender</code> в исключения антивируса и нажмите «Перезапустить».
            </p>
          </div>
        </div>
      )}

      {/* Кнопка перезапуска */}
      {showRetry && (
        <div className="mt-4 flex flex-col items-center gap-2">
          <button
            onClick={handleRestartCore}
            disabled={restarting}
            className="rounded-xl px-6 py-2.5 text-sm font-semibold"
            style={{
              background: restarting ? 'rgb(var(--c-accent) / .22)' : isFailed ? 'linear-gradient(135deg, rgb(var(--c-accent-dark)) 0%, rgb(var(--c-accent-dark)) 100%)' : 'rgb(var(--c-accent) / .35)',
              border: '1px solid rgba(139,92,246,0.45)',
              color: restarting ? 'rgb(var(--c-text) / .4)' : 'rgb(var(--c-text))',
              cursor: restarting ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
              boxShadow: isFailed && !restarting ? '0 0 18px rgba(124,58,237,0.3)' : 'none',
            }}
          >
            {restarting ? 'Перезапуск...' : '↺ Перезапустить ядро'}
          </button>
          {!isFailed && !restarting && (
            <p className="text-[0.65rem]" style={{ color: 'rgb(var(--c-muted))' }}>
              Запуск занимает 15–60 сек (первый раз дольше)
            </p>
          )}
        </div>
      )}

      <style>{GLOW_STYLES}</style>
    </div>
  )
}
