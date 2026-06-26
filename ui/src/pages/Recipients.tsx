import { useEffect, useState, useRef } from 'react'
  import { Upload, Trash2, Mail, Search, Plus } from 'lucide-react'
  import { api, type Recipient } from '../api'

  export default function Recipients() {
    const [recipients, setRecipients] = useState<Recipient[]>([])
    const [filter, setFilter]         = useState('')
    const [loading, setLoading]       = useState(true)
    const [adding, setAdding]         = useState(false)
    const [newEmail, setNewEmail]     = useState('')
    const [newName, setNewName]       = useState('')
    const fileRef = useRef<HTMLInputElement>(null)

    const load = () => api.recipients.list().then(r => { setRecipients(r.recipients); setLoading(false) })
    useEffect(() => { load() }, [])

    const filtered = filter
      ? recipients.filter(r =>
          r.email.toLowerCase().includes(filter.toLowerCase()) ||
          r.name.toLowerCase().includes(filter.toLowerCase()))
      : recipients

    async function importFile(e: React.ChangeEvent<HTMLInputElement>) {
      const file = e.target.files?.[0]; if (!file) return
      const result = await api.recipients.importTxt(file)
      alert(`Добавлено: ${result.added}, всего: ${result.total}`)
      load(); e.target.value = ''
    }

    async function clear() {
      if (!confirm('Очистить весь список получателей?')) return
      await api.recipients.clear(); load()
    }

    async function addOne() {
      if (!newEmail.includes('@')) return
      const cur = await api.recipients.list()
      const updated = [...cur.recipients, { email: newEmail, name: newName, variables: {} }]
      await api.recipients.set(updated)
      setNewEmail(''); setNewName(''); setAdding(false); load()
    }

    async function remove(email: string) {
      const cur = await api.recipients.list()
      await api.recipients.set(cur.recipients.filter(r => r.email !== email))
      load()
    }

    return (
      <div className="space-y-5 animate-fade-in">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text">Получатели</h1>
            <p className="text-muted text-sm mt-1">Всего: <span className="text-cyan font-semibold">{recipients.length}</span></p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={clear} disabled={recipients.length === 0} className="btn-danger">
              <Trash2 size={14} /> Очистить
            </button>
            <button onClick={() => fileRef.current?.click()} className="btn-secondary">
              <Upload size={14} /> Импорт .txt
            </button>
            <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={importFile} />
            <button onClick={() => setAdding(!adding)} className="btn-primary">
              <Plus size={14} /> Добавить
            </button>
          </div>
        </div>

        {adding && (
          <div className="card border-purple/30 flex items-end gap-3">
            <div className="flex-1">
              <label className="label">Email</label>
              <input className="input" placeholder="recipient@example.com" value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addOne()} />
            </div>
            <div className="w-40">
              <label className="label">Имя (необяз.)</label>
              <input className="input" placeholder="John Doe" value={newName}
                onChange={e => setNewName(e.target.value)} />
            </div>
            <button onClick={addOne} className="btn-primary">Добавить</button>
            <button onClick={() => setAdding(false)} className="btn-secondary">✕</button>
          </div>
        )}

        {/* Format hint */}
        <div className="card bg-surf2/50 py-3 text-xs text-muted">
          <strong className="text-text">Формат файла:</strong> каждая строка — email|имя или просто email
          <span className="mx-2 text-dim">·</span>
          Поддерживается: .txt, .csv
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input className="input pl-9" placeholder="Поиск по email или имени..."
            value={filter} onChange={e => setFilter(e.target.value)} />
        </div>

        {/* List */}
        {loading ? (
          <div className="text-muted text-sm text-center py-8">Загрузка...</div>
        ) : filtered.length === 0 ? (
          <div className="card text-center py-10 text-muted">
            <Mail size={32} className="mx-auto mb-2 opacity-30" />
            <p>{filter ? 'Нет совпадений' : 'Список пуст. Импортируйте файл.'}</p>
          </div>
        ) : (
          <div className="card p-0 overflow-hidden">
            <div className="px-4 py-2 border-b border-text-dim/20 bg-surf2 flex items-center text-xs text-muted font-medium gap-4">
              <span className="w-8">#</span>
              <span className="flex-1">Email</span>
              <span className="w-32">Имя</span>
              <span className="w-8"></span>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {filtered.slice(0, 500).map((r, i) => (
                <div key={r.email}
                  className="px-4 py-2 border-b border-text-dim/10 flex items-center gap-4 hover:bg-surf2/50 text-sm">
                  <span className="w-8 text-xs text-muted">{i + 1}</span>
                  <span className="flex-1 font-mono text-xs text-cyan">{r.email}</span>
                  <span className="w-32 text-xs text-muted truncate">{r.name || '—'}</span>
                  <button onClick={() => remove(r.email)}
                    className="w-8 flex justify-center text-muted hover:text-error transition-colors">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
              {filtered.length > 500 && (
                <div className="px-4 py-2 text-xs text-muted text-center">
                  Показано 500 из {filtered.length}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }
  