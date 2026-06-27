import { useEffect, useState, useRef } from 'react'
  import { motion, AnimatePresence } from 'framer-motion'
  import { Plus, Trash2, TestTube, Upload, CheckCircle, XCircle, Clock,
           ChevronDown, ChevronRight, RefreshCw, Globe, Users } from 'lucide-react'
  import { api, type Account } from '../api'

  const KNOWN_HOSTS: Record<string, {host: string; port: number; use_ssl: boolean}> = {
    'gmail.com':    { host: 'smtp.gmail.com',    port: 587, use_ssl: false },
    'outlook.com':  { host: 'smtp.live.com',     port: 587, use_ssl: false },
    'hotmail.com':  { host: 'smtp.live.com',     port: 587, use_ssl: false },
    'yahoo.com':    { host: 'smtp.mail.yahoo.com', port: 465, use_ssl: true },
    'mail.ru':      { host: 'smtp.mail.ru',      port: 465, use_ssl: true },
    'yandex.ru':    { host: 'smtp.yandex.ru',    port: 465, use_ssl: true },
  }

  function autoFillHost(email: string) {
    const domain = email.split('@')[1]?.toLowerCase()
    return domain ? (KNOWN_HOSTS[domain] ?? null) : null
  }

  function StatusIcon({ ok }: { ok: boolean | null }) {
    if (ok === true)  return <CheckCircle size={14} className="text-success" />
    if (ok === false) return <XCircle size={14} className="text-error" />
    return <Clock size={14} className="text-muted" />
  }

  interface AccountForm {
    email: string; password: string; host: string; port: number
    use_ssl: boolean; use_tls: boolean; display_name: string
    daily_limit: number; hourly_limit: number
    proxy: string; imap_host: string; imap_port: number
  }

  const EMPTY_FORM: AccountForm = {
    email: '', password: '', host: '', port: 465,
    use_ssl: true, use_tls: false, display_name: '',
    daily_limit: 500, hourly_limit: 50,
    proxy: '', imap_host: '', imap_port: 993,
  }

  export default function Accounts() {
    const [accounts, setAccounts] = useState<Account[]>([])
    const [loading, setLoading]   = useState(true)
    const [testing, setTesting]   = useState<string | null>(null)
    const [testingAll, setTestingAll] = useState(false)
    const [showForm, setShowForm] = useState(false)
    const [form, setForm]         = useState<AccountForm>(EMPTY_FORM)
    const [editEmail, setEditEmail] = useState<string | null>(null)
    const [error, setError]       = useState<string | null>(null)
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const fileRef = useRef<HTMLInputElement>(null)

    const load = () => api.accounts.list().then(setAccounts).finally(() => setLoading(false))
    useEffect(() => { load() }, [])

    function onEmailBlur() {
      if (!form.host && form.email.includes('@')) {
        const cfg = autoFillHost(form.email)
        if (cfg) setForm(f => ({ ...f, ...cfg }))
      }
    }

    async function save() {
      setError(null)
      try {
        if (editEmail) {
          await api.accounts.update(editEmail, { ...form, is_active: true, proxy_list: [] })
        } else {
          await api.accounts.add({ ...form, is_active: true, proxy_list: [] })
        }
        setShowForm(false); setForm(EMPTY_FORM); setEditEmail(null)
        load()
      } catch (e: any) {
        setError(e.response?.data?.detail ?? e.message)
      }
    }

    async function testOne(acc: Account) {
      setTesting(acc.email)
      try {
        await api.accounts.test({ ...acc })
        load()
      } finally { setTesting(null) }
    }

    async function testAll() {
      setTestingAll(true)
      try { await api.accounts.testAll(); load() }
      finally { setTestingAll(false) }
    }

    async function del(email: string) {
      if (!confirm(`Удалить ${email}?`)) return
      await api.accounts.delete(email); load()
    }

    async function delSelected() {
      if (!confirm(`Удалить ${selected.size} аккаунтов?`)) return
      await Promise.all([...selected].map(e => api.accounts.delete(e)))
      setSelected(new Set()); load()
    }

    async function importFile(e: React.ChangeEvent<HTMLInputElement>) {
      const file = e.target.files?.[0]; if (!file) return
      try {
        const result = await api.accounts.importTxt(file)
        alert(`Импортировано: ${result.imported}, пропущено: ${result.skipped}`)
        load()
      } catch(ex: any) { setError(ex.message) }
      e.target.value = ''
    }

    function editAcc(acc: Account) {
      setForm({
        email: acc.email, password: acc.password, host: acc.host, port: acc.port,
        use_ssl: acc.use_ssl, use_tls: acc.use_tls, display_name: acc.display_name,
        daily_limit: acc.daily_limit, hourly_limit: acc.hourly_limit,
        proxy: acc.proxy, imap_host: acc.imap_host, imap_port: acc.imap_port,
      })
      setEditEmail(acc.email); setShowForm(true)
    }

    const valid   = accounts.filter(a => a.last_test_ok === true).length
    const invalid = accounts.filter(a => a.last_test_ok === false).length

    return (
      <div className="space-y-5 animate-fade-in">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text">Аккаунты</h1>
            <p className="text-muted text-sm mt-1">
              Всего: <span className="text-text">{accounts.length}</span>
              {' · '}<span className="text-success">{valid} ОК</span>
              {' · '}<span className="text-error">{invalid} ошибок</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            {selected.size > 0 && (
              <button onClick={delSelected} className="btn-danger">
                <Trash2 size={14} /> Удалить {selected.size}
              </button>
            )}
            <button onClick={testAll} disabled={testingAll || accounts.length === 0} className="btn-secondary">
              <RefreshCw size={14} className={testingAll ? 'animate-spin' : ''} />
              Проверить все
            </button>
            <button onClick={() => fileRef.current?.click()} className="btn-secondary">
              <Upload size={14} /> Импорт
            </button>
            <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={importFile} />
            <button onClick={() => { setShowForm(true); setEditEmail(null); setForm(EMPTY_FORM) }} className="btn-primary">
              <Plus size={14} /> Добавить
            </button>
          </div>
        </div>

        {error && <div className="text-error text-sm bg-error/10 border border-error/20 rounded-lg px-4 py-2">{error}</div>}

        {/* Add/Edit form */}
        <AnimatePresence>
          {showForm && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <div className="card border-purple/30 space-y-4">
                <h2 className="font-semibold text-sm text-purple">
                  {editEmail ? `Редактировать: ${editEmail}` : 'Новый аккаунт'}
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="label">Email</label>
                    <input className="input" placeholder="user@gmail.com" value={form.email}
                      onChange={e => setForm(f => ({...f, email: e.target.value}))}
                      onBlur={onEmailBlur} disabled={!!editEmail} />
                  </div>
                  <div>
                    <label className="label">Пароль / App Password</label>
                    <input className="input" type="password" placeholder="••••••••" value={form.password}
                      onChange={e => setForm(f => ({...f, password: e.target.value}))} />
                  </div>
                  <div>
                    <label className="label">SMTP хост</label>
                    <input className="input" placeholder="smtp.gmail.com" value={form.host}
                      onChange={e => setForm(f => ({...f, host: e.target.value}))} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="label">Порт</label>
                      <input className="input" type="number" value={form.port}
                        onChange={e => setForm(f => ({...f, port: +e.target.value}))} />
                    </div>
                    <div>
                      <label className="label">Шифрование</label>
                      <select className="input" value={form.use_ssl ? 'ssl' : 'tls'}
                        onChange={e => setForm(f => ({...f, use_ssl: e.target.value==='ssl', use_tls: e.target.value==='tls'}))}>
                        <option value="ssl">SSL/465</option>
                        <option value="tls">TLS/587</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="label">Имя отправителя</label>
                    <input className="input" placeholder="John Doe" value={form.display_name}
                      onChange={e => setForm(f => ({...f, display_name: e.target.value}))} />
                  </div>
                  <div>
                    <label className="label">Прокси (необязательно)</label>
                    <input className="input" placeholder="socks5://user:pass@host:port" value={form.proxy}
                      onChange={e => setForm(f => ({...f, proxy: e.target.value}))} />
                  </div>
                  <div>
                    <label className="label">Дневной лимит</label>
                    <input className="input" type="number" value={form.daily_limit}
                      onChange={e => setForm(f => ({...f, daily_limit: +e.target.value}))} />
                  </div>
                  <div>
                    <label className="label">Часовой лимит</label>
                    <input className="input" type="number" value={form.hourly_limit}
                      onChange={e => setForm(f => ({...f, hourly_limit: +e.target.value}))} />
                  </div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button onClick={() => { setShowForm(false); setEditEmail(null) }} className="btn-secondary">Отмена</button>
                  <button onClick={save} className="btn-primary">
                    {editEmail ? 'Сохранить' : 'Добавить'}
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Account list */}
        {loading ? (
          <div className="text-muted text-sm text-center py-8">Загрузка...</div>
        ) : accounts.length === 0 ? (
          <div className="card text-center py-10 text-muted">
            <Users size={32} className="mx-auto mb-2 opacity-30" />
            <p>Нет аккаунтов. Добавьте или импортируйте.</p>
          </div>
        ) : (
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-text-dim/20 bg-surf2">
                  <th className="px-4 py-2 text-left">
                    <input type="checkbox" className="accent-purple"
                      checked={selected.size === accounts.length && accounts.length > 0}
                      onChange={e => setSelected(e.target.checked ? new Set(accounts.map(a=>a.email)) : new Set())} />
                  </th>
                  <th className="px-4 py-2 text-left text-muted font-medium">Email</th>
                  <th className="px-4 py-2 text-left text-muted font-medium">SMTP</th>
                  <th className="px-4 py-2 text-left text-muted font-medium">Прокси</th>
                  <th className="px-4 py-2 text-left text-muted font-medium">Лимит/д</th>
                  <th className="px-4 py-2 text-left text-muted font-medium">Статус</th>
                  <th className="px-4 py-2 text-right text-muted font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acc, i) => (
                  <tr key={acc.email}
                    className={`border-b border-text-dim/10 hover:bg-surf2/50 transition-colors
                      ${i % 2 === 0 ? '' : 'bg-surf2/20'}`}>
                    <td className="px-4 py-2">
                      <input type="checkbox" className="accent-purple"
                        checked={selected.has(acc.email)}
                        onChange={e => {
                          const s = new Set(selected)
                          e.target.checked ? s.add(acc.email) : s.delete(acc.email)
                          setSelected(s)
                        }} />
                    </td>
                    <td className="px-4 py-2">
                      <button onClick={() => editAcc(acc)} className="font-mono text-xs text-cyan hover:text-cyan-light">
                        {acc.email}
                      </button>
                      {acc.display_name && <div className="text-xs text-muted">{acc.display_name}</div>}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted">
                      {acc.host}:{acc.port}
                    </td>
                    <td className="px-4 py-2">
                      {acc.proxy ? (
                        <span className="badge-cyan flex items-center gap-1"><Globe size={10} />Прокси</span>
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-muted">{acc.daily_limit}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-1.5">
                        <StatusIcon ok={acc.last_test_ok} />
                        <span className={`text-xs ${
                          acc.last_test_ok === true  ? 'text-success' :
                          acc.last_test_ok === false ? 'text-error' : 'text-muted'
                        }`}>
                          {acc.last_test_ok === true  ? 'ОК' :
                           acc.last_test_ok === false ? 'Ошибка' : 'Не проверен'}
                        </span>
                      </div>
                      {acc.last_test_msg && acc.last_test_ok === false && (
                        <div className="text-xs text-error/70 mt-0.5 max-w-[150px] truncate" title={acc.last_test_msg}>
                          {acc.last_test_msg}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => testOne(acc)}
                          disabled={testing === acc.email}
                          title="Проверить"
                          className="p-1.5 rounded text-muted hover:text-cyan hover:bg-cyan/10 transition-colors">
                          <TestTube size={13} className={testing === acc.email ? 'animate-spin' : ''} />
                        </button>
                        <button onClick={() => del(acc.email)} title="Удалить"
                          className="p-1.5 rounded text-muted hover:text-error hover:bg-error/10 transition-colors">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }
  