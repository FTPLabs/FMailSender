/**
 * StatusContext — единый real-time канал статуса для всего приложения.
 *
 * Стратегия:
 *  1. Открывает одно SSE-соединение /api/events.
 *  2. При 3+ ошибках подряд → fallback на polling 2с.
 *  3. Каждые 60с в режиме fallback пробует восстановить SSE (re-probe).
 *  4. Pause при скрытой вкладке (Page Visibility API), resume при возврате.
 *  5. Экспоненциальный backoff реконнекта до 5с.
 *  6. Валидация payload перед setStatus — защита от невалидного JSON.
 *
 * Использование:
 *   const { status, refresh } = useStatus()
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, type AppStatus } from '../api'

const SSE_URL = 'http://127.0.0.1:7531/api/events'
const SSE_REPROBE_INTERVAL = 60_000  // пробуем вернуться на SSE каждые 60с

/** Минимальная проверка: payload содержит ожидаемые ключи верхнего уровня. */
function isValidStatus(data: unknown): data is AppStatus {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return (
    'campaign' in d &&
    'accounts' in d &&
    'recipients' in d &&
    'proxies' in d &&
    typeof d.accounts === 'object' && d.accounts !== null
  )
}

interface StatusCtx {
  status: AppStatus | null
  refresh: () => Promise<void>
}

const Ctx = createContext<StatusCtx>({ status: null, refresh: async () => {} })

export const useStatus = () => useContext(Ctx)

export function StatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AppStatus | null>(null)

  const esRef        = useRef<EventSource | null>(null)
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reprobeRef   = useRef<ReturnType<typeof setInterval> | null>(null)
  const failCount    = useRef(0)
  const useSSE       = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.status()
      if (isValidStatus(data)) setStatus(data)
    } catch {}
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current)  { clearInterval(pollRef.current);  pollRef.current  = null }
    if (reprobeRef.current){ clearInterval(reprobeRef.current); reprobeRef.current = null }
  }, [])

  // Forward declaration — connectSSE is defined below but referenced in startPolling
  const connectSSERef = useRef<() => void>(() => {})

  const startPolling = useCallback(() => {
    stopPolling()
    refresh()
    pollRef.current = setInterval(refresh, 2000)

    // Периодически пробуем вернуться на SSE
    reprobeRef.current = setInterval(() => {
      if (document.hidden) return
      useSSE.current = true
      failCount.current = 0
      connectSSERef.current()
    }, SSE_REPROBE_INTERVAL)
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
      // SSE восстановлено — останавливаем fallback polling
      stopPolling()
    }

    es.onmessage = (e) => {
      failCount.current = 0
      try {
        const parsed = JSON.parse(e.data)
        if (isValidStatus(parsed)) setStatus(parsed)
      } catch {}
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      failCount.current++

      if (failCount.current >= 3) {
        // SSE недоступен — деградируем в polling (с re-probe через 60с)
        useSSE.current = false
        startPolling()
        return
      }

      // Реконнект с backoff
      const delay = Math.min(500 * failCount.current, 5000)
      reconnectRef.current = setTimeout(connectSSE, delay)
    }
  }, [closeSSE, startPolling, stopPolling])

  // Синхронизируем ref для использования внутри setInterval выше
  useEffect(() => { connectSSERef.current = connectSSE }, [connectSSE])

  useEffect(() => {
    connectSSE()

    const onVisibility = () => {
      if (document.hidden) {
        closeSSE()
        stopPolling()
      } else {
        failCount.current = 0
        if (useSSE.current) connectSSE()
        else startPolling()
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      closeSSE()
      stopPolling()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [connectSSE, closeSSE, stopPolling, startPolling])

  return <Ctx.Provider value={{ status, refresh }}>{children}</Ctx.Provider>
}
