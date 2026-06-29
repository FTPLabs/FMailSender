import { useEffect, useState, useRef } from 'react'
import { Shield, Upload, RefreshCw, Trash2, Share2, CheckCircle, XCircle, Clock } from 'lucide-react'
import { api } from '../api'

interface ProxyResult {
  proxy: string
  ok: boolean
  smtp_ok: boolean
  error?: string
  ping_ms?: number
}

export default function Proxies() {
  const [proxies, setProxies]       = useState<string[]>([])
  const [results, setResults]       = useState<Record<string, ProxyResult>>({})
  const [textarea, setTextarea]     = useState('')
  const [loading, setLoading]       = useState(true)
  const [checking, setChecking]     = useState(false)
  const [distributing, setDist]     = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [info, setInfo]             = useState<string | null>(null)
  const fileRef                     = useRef<HTMLInputElement>(null)

  const load = async () => {
    try {
      const r = await api.proxies.list()
      setProxies(r.proxies ?? [])
      setTextarea((r.proxies ?? []).join('\n'))
    } catch { }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function save() {
    setError(null)
    const list = textarea.split('\n').map(s => s.trim()).filter(Boolean)
    try {
      await api.proxies.set(list)
      await load()
      setInfo(`Сохранено: ${list.length} прокси`)
      setTimeout(() => setInfo(null), 3000)
    } catch (e: any) { setError(e.response?.data?.detail ?? e.message) }
  }

  async function clear() {
    if (!confirm('Очистить список прокси?')) return
    await api.proxies.set([])
    setTextarea(''); setResults({}); load()
  }

  async function checkAll() {
    setChecking(true); setError(null)
    try {
      const r = await api.proxies.check()
      const map: Record<string, ProxyResult> = {}
      for (const item of (r.results ?? r ?? [])) {
        map[item.proxy] = item
      }
      setResults(map)
    } catch (e: any) { setError(e.response?.data?.detail ?? e.message) }
    finally { setChecking(false) }
  }

  async function distribute() {
    setDist(true)
    try {
      const r = await api.proxies.distribute()
      setInfo(r.message ?? 'Прокси распределены по аккаунтам')
      setTimeout(() => setInfo(null), 4000)
    } catch (e: any) { setError(e.response?.data?.detail ?? e.message) }
    finally { setDist(false) }
  }

  async function importFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    const text = await file.text()
    const lines = text.split(/\r?\n/).map(s => s.trim()).filter(Boolean)
    const merged = [...new Set([...proxies, ...lines])]
    setTextarea(merged.join('\n'))
    e.target.value = ''
  }

  const ok   = Object.values(results).filter(r => r.ok).length
  const fail = Object.values(results).filter(r => !r.ok).length

  const hasResults = Object.keys(results).length > 0

  return (
    <div className="page flex-1 flex flex-col">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Прокси</h1>
          <p className="page-sub">
            Всего: <span className="text-[#e8e8ff] font-medium">{proxies.length}</span>
            {hasResults && (
              <>
                {' · '}<span className="text-[#10b981]">{ok} ОК</span>
                {' · '}<span className="text-[#ef4444]">{fail} ошибок</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => fileRef.current?.click()} className="btn btn-secondary btn-sm">
            <Upload size={13} /> Импорт
          </button>
          <input ref={fileRef} type="file" accept=".txt" className="hidden" onChange={importFile} />
          <button onClick={distribute} disabled={distributing || proxies.length === 0}
            className="btn btn-secondary btn-sm">
            <Share2 size={13} className={distributing ? 'animate-spin' : ''} />
            Распределить
          </button>
          <button onClick={checkAll} disabled={checking || proxies.length === 0}
            className="btn btn-secondary btn-sm">
            <RefreshCw size={13} className={checking ? 'animate-spin' : ''} />
            Проверить
          </button>
          <button onClick={clear} disabled={proxies.length === 0}
            className="btn btn-danger btn-sm">
            <Trash2 size={13} /> Очистить
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg px-4 py-2">
          {error}
        </div>
      )}
      {info && (
        <div className="text-sm text-[#10b981] bg-[#10b981]/10 border border-[#10b981]/20 rounded-lg px-4 py-2">
          {info}
        </div>
      )}

      {/* Format hint */}
      <div className="card-inset text-xs text-[#6666aa]">
        <span className="text-[#e8e8ff] font-medium">Формат:</span>{' '}
        по одному прокси на строку.{' '}
        Поддерживается: <code className="text-[#8b5cf6]">socks5://user:pass@host:port</code>,{' '}
        <code className="text-[#8b5cf6]">http://host:port</code>,{' '}
        <code className="text-[#8b5cf6]">host:port:user:pass</code>
      </div>

      {/* Main layout: editor + results — column on small, row on lg+ when results exist */}
      <div className={`flex-1 flex min-h-0 ${hasResults ? 'flex-col lg:flex-row gap-5' : 'flex-col'}`}>
        {/* Textarea editor */}
        <div className={`card flex flex-col space-y-3 ${hasResults ? 'flex-1 min-w-0' : 'flex-1'}`}>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#e8e8ff]">Список прокси</h2>
            <button onClick={save} className="btn btn-primary btn-sm">
              Сохранить
            </button>
          </div>
          <textarea
            className="input font-mono text-xs leading-relaxed resize-none flex-1"
            style={{ minHeight: '200px' }}
            placeholder={'socks5://user:pass@1.2.3.4:1080\nhttp://1.2.3.5:8080\n1.2.3.6:1080:user:pass'}
            value={textarea}
            onChange={e => setTextarea(e.target.value)}
            spellCheck={false}
          />
          <p className="text-xs text-[#6666aa] flex-shrink-0">
            После редактирования нажмите <span className="text-[#e8e8ff]">Сохранить</span>.
            Кнопка <span className="text-[#e8e8ff]">Распределить</span> назначит прокси аккаунтам равномерно.
          </p>
        </div>

        {/* Check results — right column (responsive: full-width below lg) */}
        {hasResults && (
          <div className="card p-0 overflow-hidden flex flex-col w-full lg:w-96 lg:flex-shrink-0">
            <div className="px-4 py-2.5 border-b border-[#3a3a66]/30 bg-[#141424] flex-shrink-0">
              <h2 className="text-xs font-semibold text-[#6666aa] uppercase tracking-wider">
                Результаты проверки
              </h2>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-[#3a3a66]/20">
              {proxies.map(proxy => {
                const r = results[proxy]
                if (!r) return null
                return (
                  <div key={proxy} className="px-4 py-2.5 flex items-center gap-3 text-xs hover:bg-[#141424]/60">
                    {r.ok
                      ? <CheckCircle size={12} className="text-[#10b981] flex-shrink-0" />
                      : <XCircle size={12} className="text-[#ef4444] flex-shrink-0" />
                    }
                    <span className="font-mono text-[#e8e8ff] flex-1 truncate">{proxy}</span>
                    {r.ping_ms != null && (
                      <span className="text-[#6666aa] tabular-nums">{r.ping_ms}ms</span>
                    )}
                    {r.smtp_ok && (
                      <span className="badge badge-ok">SMTP</span>
                    )}
                    {!r.ok && r.error && (
                      <span className="text-[#ef4444]/80 max-w-[160px] truncate" title={r.error}>
                        {r.error}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Empty state */}
      {!loading && proxies.length === 0 && !hasResults && (
        <div className="empty flex-1">
          <Shield size={36} />
          <p className="font-medium text-sm text-[#e8e8ff] mb-1">Прокси не загружены</p>
          <p className="text-xs">Вставьте список выше или импортируйте .txt файл</p>
        </div>
      )}
    </div>
  )
}
