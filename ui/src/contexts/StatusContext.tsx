/**
 * StatusContext — единый real-time канал статуса для всего приложения.
 *
 * Стратегия:
 *  1. Быстрый startup polling (500 мс) до первого успешного ответа → online=true.
 *  2. После online: открывает SSE /api/events.
 *  3. При 3+ ошибках SSE подряд → fallback polling 2с.
 *  4. Каждые 60с в режиме fallback пробует восстановить SSE (re-probe).
 *  5. Pause при скрытой вкладке (Page Visibility API), resume при возврате.
 *  6. Экспоненциальный backoff реконнекта до 5с.
 *  7. Валидация payload перед setStatus.
 *
 * Экспортирует:
 *   const { status, online, refresh } = useStatus()
 *   - online: true после первого успешного ответа от backend
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'
import { api, type AppStatus } from '../api'

const SSE_URL             = 'http://127.0.0.1:7531/api/events'
const STARTUP_POLL_MS     = 500     // агрессивный polling до первого ответа
const IDLE_POLL_MS        = 2000    // fallback polling после деградации SSE
const SSE_REPROBE_MS      = 60_000  // re-probe SSE после деградации

function isValidStatus(data: unknown): data is AppStatus {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return (
    'campaign'   in d &&
    'accounts'   in d &&
    'recipients' in d &&
    'proxies'    in d &&
    typeof d.accounts === 'object' && d.accounts !== null
  )
}

interface StatusCtx {
  status:  AppStatus | null
  online:  boolean
  refresh: () => Promise<void>
}

const Ctx = createContext<StatusCtx>({
  status: null, online: false, refresh: async () => {},
})

export const useStatus = () => useContext(Ctx)

export function StatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AppStatus | null>(null)
  const [online, setOnline] = useState(false)

  const esRef        = useRef<EventSource | null>(null)
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reprobeRef   = useRef<ReturnType<typeof setInterval> | null>(null)
  const failCount    = useRef(0)
  const useSSE       = useRef(false)    // start false — SSE opens only after online
  const isOnline     = useRef(false)    // sync mirror of online state

  const markOnline = useCallback(() => {
    if (!isOnline.current) {
      isOnline.current = true
      setOnline(true)
    }
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await api.status()
      if (isValidStatus(data)) {
        markOnline()
        setStatus(data)
      }
    } catch {}
  }, [markOnline])

  const stopPolling = useCallback(() => {
    if (pollRef.current)   { clearInterval(pollRef.current);   pollRef.current   = null }
    if (reprobeRef.current){ clearInterval(reprobeRef.current); reprobeRef.current = null }
  }, [])

  const connectSSERef = useRef<() => void>(() => {})

  const startPolling = useCallback((intervalMs = IDLE_POLL_MS) => {
    stopPolling()
    refresh()
    pollRef.current = setInterval(refresh, intervalMs)

    if (intervalMs !== STARTUP_POLL_MS) {
      // Re-probe SSE periodically after fallback
      reprobeRef.current = setInterval(() => {
        if (document.hidden) return
        useSSE.current    = true
        failCount.current = 0
        connectSSERef.current()
      }, SSE_REPROBE_MS)
    }
  }, [refresh, stopPolling])

  const closeSSE = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    if (reconnectRef.current) { clearTimeout(reconnectRef.current); reconnectRef.current = null }
  }, [])

  const connectSSE = useCallback(() => {
    closeSSE()
    if (!useSSE.current || document.hidden) return

    const es = new EventSource(SSE_URL)
    esRef.current = es

    es.onopen = () => {
      failCount.current = 0
      stopPolling()   // SSE восстановлено — останавливаем fallback polling
    }

    es.onmessage = (e) => {
      failCount.current = 0
      try {
        const parsed = JSON.parse(e.data)
        if (isValidStatus(parsed)) {
          markOnline()
          setStatus(parsed)
        }
      } catch {}
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      failCount.current++

      if (failCount.current >= 3) {
        useSSE.current = false
        startPolling(IDLE_POLL_MS)
        return
      }

      const delay = Math.min(500 * failCount.current, 5000)
      reconnectRef.current = setTimeout(connectSSE, delay)
    }
  }, [closeSSE, markOnline, startPolling, stopPolling])

  useEffect(() => { connectSSERef.current = connectSSE }, [connectSSE])

  useEffect(() => {
    // Phase 1: fast startup polling until first backend response
    startPolling(STARTUP_POLL_MS)

    // Phase 2: as soon as backend is online, switch to SSE
    const checkOnline = setInterval(() => {
      if (!isOnline.current) return
      clearInterval(checkOnline)
      stopPolling()
      useSSE.current = true
      connectSSE()
    }, 200)

    const onVisibility = () => {
      if (document.hidden) {
        closeSSE()
        stopPolling()
        clearInterval(checkOnline)
      } else {
        if (!isOnline.current) {
          startPolling(STARTUP_POLL_MS)
        } else if (useSSE.current) {
          connectSSE()
        } else {
          startPolling(IDLE_POLL_MS)
        }
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      closeSSE()
      stopPolling()
      clearInterval(checkOnline)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [connectSSE, closeSSE, startPolling, stopPolling])

  return (
    <Ctx.Provider value={{ status, online, refresh }}>
      {children}
    </Ctx.Provider>
  )
}
