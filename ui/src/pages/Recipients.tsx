import { useEffect, useState, useRef } from 'react'
import { GothicIcon } from '../components/GothicIcon'
import { api, type Recipient } from '../api'
import { useI18n } from '../i18n'

export default function Recipients() {
  const { language } = useI18n()
  const [recipients, setRecipients] = useState<Recipient[]>([])
  const [filter, setFilter]         = useState('')
  const [loading, setLoading]       = useState(true)
  const [adding, setAdding]         = useState(false)
  const [newEmail, setNewEmail]     = useState('')
  const [newName, setNewName]       = useState('')
  const [error, setError]           = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => api.recipients.list()
    .then(r => { setRecipients(r.recipients); setLoading(false) })
    .catch(() => setLoading(false))
  useEffect(() => { load() }, [])

  const filtered = filter
    ? recipients.filter(r =>
        r.email.toLowerCase().includes(filter.toLowerCase()) ||
        r.name.toLowerCase().includes(filter.toLowerCase()))
    : recipients

  async function importFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    setError(null)
    try {
      const r = await api.recipients.importTxt(file)
      alert(`Добавлено: ${r.added}, всего: ${r.total}`)
      load()
    } catch (ex: any) { setError(ex.response?.data?.detail ?? ex.message) }
    e.target.value = ''
  }

  async function clear() {
    if (!confirm('Очистить весь список получателей?')) return
    await api.recipients.clear(); load()
  }

  async function addOne() {
    if (!newEmail.includes('@')) return
    setError(null)
    try {
      const cur = await api.recipients.list()
      const exists = cur.recipients.some(r => r.email === newEmail)
      if (exists) { setError(`${newEmail} уже в списке`); return }
      const updated = [...cur.recipients, { email: newEmail, name: newName, variables: {} }]
      await api.recipients.set(updated)
      setNewEmail(''); setNewName(''); setAdding(false); load()
    } catch (ex: any) { setError(ex.response?.data?.detail ?? ex.message) }
  }

  async function remove(email: string) {
    const cur = await api.recipients.list()
    await api.recipients.set(cur.recipients.filter(r => r.email !== email))
    load()
  }

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Получатели</h1>
          <p className="page-sub">
            Всего: <span className="text-[#06b6d4] font-semibold">{recipients.length}</span>
            {filter && <span> · найдено: {filtered.length}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clear} disabled={recipients.length === 0}
            className="btn btn-danger btn-sm">
            <GothicIcon name="delete" size={13} /> Очистить
          </button>
          <button onClick={() => fileRef.current?.click()} className="btn btn-secondary btn-sm">
            <GothicIcon name="import" size={13} /> Импорт .txt
          </button>
          <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={importFile} />
          <button onClick={() => setAdding(!adding)} className="btn btn-primary btn-sm">
            <GothicIcon name="add" size={13} /> Добавить
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {/* Quick add */}
      {adding && (
        <div className="card border-[#8b5cf6]/25 flex items-end gap-3">
          <div className="flex-1">
            <label className="label">Email</label>
            <input className="input" placeholder="recipient@example.com" value={newEmail}
              onChange={e => setNewEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addOne()} autoFocus />
          </div>
          <div className="w-40">
            <label className="label">Имя (необязательно)</label>
            <input className="input" placeholder="John Doe" value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addOne()} />
          </div>
          <button onClick={addOne} className="btn btn-primary btn-sm">Добавить</button>
          <button onClick={() => { setAdding(false); setNewEmail(''); setNewName('') }}
            className="btn btn-ghost btn-sm">✕</button>
        </div>
      )}

      {/* Format hint */}
      <div className="card-inset text-xs text-muted">
        {language === 'en' ? <><span className="text-text font-medium">File format:</span>{' '}one line — <code className="text-purple-light">email|name</code> or simply <code className="text-purple-light">email</code>. Supports .txt and .csv.</> : <><span className="text-text font-medium">Формат файла:</span>{' '}каждая строка — <code className="text-purple-light">email|имя</code> или просто <code className="text-purple-light">email</code>. Поддерживается: .txt, .csv</>}
      </div>

      {/* Search */}
      <div className="relative">
        <GothicIcon name="search" size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
        <input className="input pl-9" placeholder="Поиск по email или имени..."
          value={filter} onChange={e => setFilter(e.target.value)} />
      </div>

      {/* List */}
      {loading ? (
        <div className="empty"><GothicIcon name="refresh" size={24} className="animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <div className="empty">
          <GothicIcon name="recipients" size={36} />
          <p className="font-medium text-sm text-[#e8e8ff] mb-1">
            {filter ? 'Нет совпадений' : 'Список пуст'}
          </p>
          <p className="text-xs">
            {filter ? `По запросу «${filter}» ничего не найдено` : 'Импортируйте .txt файл или добавьте вручную'}
          </p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#3a3a66]/30 bg-[#141424]
                          flex items-center text-xs text-[#6666aa] font-medium gap-4">
            <span className="w-10 tabular-nums">#</span>
            <span className="flex-1">Email</span>
            <span className="w-40">Имя</span>
            <span className="w-8" />
          </div>
          <div className="max-h-[480px] overflow-y-auto divide-y divide-[#3a3a66]/15">
            {filtered.slice(0, 1000).map((r, i) => (
              <div key={r.email}
                className="px-4 py-2 flex items-center gap-4 hover:bg-[#141424]/60 transition-colors text-sm">
                <span className="w-10 text-xs text-[#6666aa] tabular-nums">{i + 1}</span>
                <span className="flex-1 font-mono text-xs text-[#06b6d4] truncate">{r.email}</span>
                <span className="w-40 text-xs text-[#6666aa] truncate">{r.name || '—'}</span>
                <button onClick={() => remove(r.email)}
                  className="w-8 flex justify-center text-[#6666aa] hover:text-[#ef4444] transition-colors">
                  <GothicIcon name="delete" size={12} />
                </button>
              </div>
            ))}
          </div>
          {filtered.length > 1000 && (
            <div className="px-4 py-2.5 text-xs text-[#6666aa] text-center bg-[#141424] border-t border-[#3a3a66]/30">
              Показано 1000 из {filtered.length}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
