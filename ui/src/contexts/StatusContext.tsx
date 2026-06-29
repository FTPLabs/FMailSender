/**
 * StatusContext — единый real-time канал статуса для всего приложения.
 *
 * Стратегия:
 *  1. Открывает одно SSE-соединение /api/events (события от сервера).
 *  2. При 3+ ошибках подряд переключается на polling раз в 2с (fallback).
 *  3. Приостанавливает поток, когда вкладка скрыта (visibility API).
 *  4. Авто-реконнект с backoff до 5с.
 *
 * Использование:
 *   const { status, refresh } = useStatus()
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, type AppStatus } from '../api'

const SSE_URL = 'http://127.0.0.1:7531/api/events'

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
  const failCount    = useRef(0)
  const useSSE       = useRef(true)

  const refresh = useCallback(async () => {
    try { setStatus(await api.status()) } catch {}
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    refresh()
    pollRef.current = setInterval(refresh, 2000)
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

    es.onopen = () => { failCount.current = 0 }

    es.onmessage = (e) => {
      failCount.current = 0
      try { setStatus(JSON.parse(e.data)) } catch {}
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      failCount.current++

      if (failCount.current >= 3) {
        useSSE.current = false
        startPolling()
        return
      }

      const delay = Math.min(500 * failCount.current, 5000)
      reconnectRef.current = setTimeout(connectSSE, delay)
    }
  }, [closeSSE, startPolling])

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
