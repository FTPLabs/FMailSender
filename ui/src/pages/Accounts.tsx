import { useEffect, useState, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Plus, Trash2, RefreshCw, Upload, CheckCircle, XCircle, Clock, Globe, Users, Loader2 } from 'lucide-react'
import { api, getBaseUrl, type Account } from '../api'

const KNOWN_HOSTS: Record<string, { host: string; port: number; use_ssl: boolean }> = {
  'gmail.com':    { host: 'smtp.gmail.com',       port: 587, use_ssl: false },
  'outlook.com':  { host: 'smtp.office365.com',   port: 587, use_ssl: false },
  'hotmail.com':  { host: 'smtp.office365.com',   port: 587, use_ssl: false },
  'live.com':     { host: 'smtp.office365.com',   port: 587, use_ssl: false },
  'yahoo.com':    { host: 'smtp.mail.yahoo.com',  port: 465, use_ssl: true  },
  'mail.ru':      { host: 'smtp.mail.ru',         port: 465, use_ssl: true  },
  'yandex.ru':    { host: 'smtp.yandex.ru',       port: 465, use_ssl: true  },
  'rambler.ru':   { host: 'smtp.rambler.ru',      port: 465, use_ssl: true  },
  // FIX v6.1: smtp.gmx.com → mail.gmx.net (официальный SMTP-хост для gmx.com)
  'gmx.com':      { host: 'mail.gmx.net',          port: 587, use_ssl: false },
  'gmx.net':      { host: 'mail.gmx.net',         port: 587, use_ssl: false },
  'gmx.de':       { host: 'mail.gmx.net',         port: 587, use_ssl: false },
}

function autofill(email: string) {
  const domain = email.split('@')[1]?.toLowerCase()
  return domain ? (KNOWN_HOSTS[domain] ?? null) : null
}

function StatusIcon({ ok, testing }: { ok: boolean | null; testing?: boolean }) {
  if (testing) return <Loader2 size={13} className="text-[#a78bfa] animate-spin" />
  if (ok === true)  return <CheckCircle size={13} className="text-[#10b981]" />
  if (ok === false) return <XCircle size={13} className="text-[#ef4444]" />
  return <Clock size={13} className="text-[#6666aa]" />
}

interface Frm {
  email: string; password: string; host: string; port: number
  use_ssl: boolean; use_tls: boolean; display_name: string
  daily_limit: number; hourly_limit: number
  proxy: string; imap_host: string; imap_port: number
  refresh_token: string
}

const EMPTY: Frm = {
  email: '', password: '', host: '', port: 587,
  use_ssl: false, use_tls: true, display_name: '',
  daily_limit: 500, hourly_limit: 50,
  proxy: '', imap_host: '', imap_port: 993,
  refresh_token: '',
}

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading]   = useState(true)
  const [testing, setTesting]   = useState<string | null>(null)
  const [testAll, setTestAll]   = useState(false)
  const [testProgress, setTestProgress] = useState<{ done: number; total: number } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState<Frm>(EMPTY)
  const [editEmail, setEditEmail] = useState<string | null>(null)
  const [error, setError]       = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const fileRef = useRef<HTMLInputElement>(null)
  const esRef   = useRef<EventSource | null>(null)

  const load = () => api.accounts.list().then(setAccounts).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => {
    load()
    return () => { esRef.current?.close() }
  }, [])

  function set(k: keyof Frm, v: any) { setForm(f => ({ ...f, [k]: v })) }

  function onEmailBlur() {
    if (!form.host && form.email.includes('@')) {
      const cfg = autofill(form.email)
      if (cfg) setForm(f => ({ ...f, ...cfg }))
    }
  }

  async function save() {
    setError(null)
    try {
      const payload = { ...form, is_active: true, proxy_list: [], access_token: '' }
      if (editEmail) await api.accounts.update(editEmail, payload)
      else           await api.accounts.add(payload)
      setShowForm(false); setForm(EMPTY); setEditEmail(null); load()
    } catch (e: any) { setError(e.response?.data?.detail ?? e.message) }
  }

  async function testOne(acc: Account) {
    setTesting(acc.email)
    setAccounts(prev => prev.map(a =>
      a.email === acc.email ? { ...a, last_test_ok: null, last_test_msg: '' } : a
    ))
    try {
      const result = await api.accounts.test({ ...acc })
      setAccounts(prev => prev.map(a =>
        a.email === acc.email
          ? { ...a, last_test_ok: result.ok, last_test_msg: result.message ?? '' }
          : a
      ))
    } catch (e: any) {
      setAccounts(prev => prev.map(a =>
        a.email === acc.email
          ? { ...a, last_test_ok: false, last_test_msg: e.message ?? 'Ошибка' }
          : a
      ))
    } finally {
      setTesting(null)
    }
  }

  function testAllFn() {
    if (accounts.length === 0 || testAll) return

    esRef.current?.close()
    setTestAll(true)
    setTestProgress({ done: 0, total: accounts.length })

    const es = new EventSource(`${getBaseUrl()}/api/accounts/test-all/stream`)
    esRef.current = es

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.complete) {
          es.close()
          esRef.current = null
          load()
          setTestAll(false)
          setTestProgress(null)
          return
        }

        const { email, ok, message, done, total } = data
        setTestProgress({ done, total })
        setAccounts(prev => prev.map(a =>
          a.email === email
            ? { ...a, last_test_ok: ok, last_test_msg: message ?? '' }
            : a
        ))
      } catch {}
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      load()
      setTestAll(false)
      setTestProgress(null)
    }
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
      const r = await api.accounts.importTxt(file)
      alert(`Импортировано: ${r.imported}, пропущено: ${r.skipped}`)
      load()
    } catch (ex: any) { setError(ex.message) }
    e.target.value = ''
  }

  function editAcc(acc: Account) {
    setForm({
      email: acc.email, password: acc.password, host: acc.host, port: acc.port,
      use_ssl: acc.use_ssl, use_tls: acc.use_tls, display_name: acc.display_name,
      daily_limit: acc.daily_limit, hourly_limit: acc.hourly_limit,
      proxy: acc.proxy, imap_host: acc.imap_host, imap_port: acc.imap_port,
      refresh_token: acc.refresh_token ?? '',
    })
    setEditEmail(acc.email); setShowForm(true)
  }

  const allChecked = accounts.length > 0 && selected.size === accounts.length
  const enc = String(form.use_ssl ? 'ssl' : 'tls')

  const okCount   = accounts.filter(a => a.last_test_ok === true).length
  const failCount = accounts.filter(a => a.last_test_ok === false).length

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Аккаунты</h1>
          <p className="page-sub">
            Всего: <span className="text-[#e8e8ff]">{accounts.length}</span>
            {' · '}<span className="text-[#10b981]">{okCount} ОК</span>
            {' · '}<span className="text-[#ef4444]">{failCount} ошибок</span>
            {testProgress && (
              <span className="text-[#a78bfa]">
                {' · '}Проверяется {testProgress.done}/{testProgress.total}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {selected.size > 0 && (
            <button onClick={delSelected} className="btn btn-danger btn-sm">
              <Trash2 size={13} /> Удалить {selected.size}
            </button>
          )}
          <button
            onClick={testAll ? () => { esRef.current?.close(); esRef.current = null; setTestAll(false); setTestProgress(null) } : testAllFn}
            disabled={accounts.length === 0}
            className={`btn btn-sm ${testAll ? 'btn-danger' : 'btn-secondary'}`}
          >
            {testAll
              ? <><Loader2 size={13} className="animate-spin" /> Стоп ({testProgress?.done ?? 0}/{testProgress?.total ?? accounts.length})</>
              : <><RefreshCw size={13} /> Проверить все</>
            }
          </button>
          <button onClick={() => fileRef.current?.click()} className="btn btn-secondary btn-sm">
            <Upload size={13} /> Импорт
          </button>
          <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={importFile} />
          <button onClick={() => { setShowForm(true); setEditEmail(null); setForm(EMPTY) }}
            className="btn btn-primary btn-sm">
            <Plus size={13} /> Добавить
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {/* Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div key="form" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>
            <div className="card border-[#8b5cf6]/25 space-y-4">
              <h2 className="text-sm font-semibold text-[#a78bfa]">
                {editEmail ? `Редактировать: ${editEmail}` : 'Новый аккаунт'}
              </h2>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Email</label>
                  <input className="input" placeholder="user@gmail.com" value={form.email}
                    onChange={e => set('email', e.target.value)}
                    onBlur={onEmailBlur} disabled={!!editEmail} />
                </div>
                <div>
                  <label className="label">Пароль / App Password</label>
                  <input className="input" type="password" placeholder="••••••••" value={form.password}
                    onChange={e => set('password', e.target.value)} />
                </div>
                <div>
                  <label className="label">Refresh Token <span className="text-xs text-gray-400">(OAuth2 — Outlook/Hotmail/JMX через Office365)</span></label>
                  <input className="input" type="text"
                    placeholder="Оставьте пустым если аккаунт не Microsoft/JMX"
                    value={form.refresh_token}
                    onChange={e => set('refresh_token', e.target.value)} />
                </div>
                <div>
                  <label className="label">SMTP хост</label>
                  <input className="input" placeholder="smtp.gmail.com" value={form.host}
                    onChange={e => set('host', e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="label">Порт</label>
                    <input className="input" type="number" value={form.port}
                      onChange={e => set('port', +e.target.value)} />
                  </div>
                  <div>
                    <label className="label">Шифрование</label>
                    <select className="input" value={enc}
                      onChange={e => setForm(f => ({
                        ...f,
                        use_ssl: e.target.value === 'ssl',
                        use_tls: e.target.value === 'tls',
                      }))}>
                      <option value="tls">TLS / 587</option>
                      <option value="ssl">SSL / 465</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="label">Имя отправителя</label>
                  <input className="input" placeholder="John Doe" value={form.display_name}
                    onChange={e => set('display_name', e.target.value)} />
                </div>
                <div>
                  <label className="label">Прокси (необязательно)</label>
                  <input className="input" placeholder="socks5://user:pass@host:port" value={form.proxy}
                    onChange={e => set('proxy', e.target.value)} />
                </div>
                <div>
                  <label className="label">Дневной лимит</label>
                  <input className="input" type="number" value={form.daily_limit}
                    onChange={e => set('daily_limit', +e.target.value)} />
                </div>
                <div>
                  <label className="label">Часовой лимит</label>
                  <input className="input" type="number" value={form.hourly_limit}
                    onChange={e => set('hourly_limit', +e.target.value)} />
                </div>
              </div>
              <div className="flex gap-2 justify-end pt-1">
                <button onClick={() => { setShowForm(false); setEditEmail(null) }} className="btn btn-secondary btn-sm">
                  Отмена
                </button>
                <button onClick={save} className="btn btn-primary btn-sm">
                  {editEmail ? 'Сохранить' : 'Добавить'}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* List */}
      {loading ? (
        <div className="empty"><RefreshCw size={24} className="animate-spin" /></div>
      ) : accounts.length === 0 ? (
        <div className="empty">
          <Users size={36} />
          <p className="font-medium text-sm text-[#e8e8ff] mb-1">Нет аккаунтов</p>
          <p className="text-xs">Добавьте вручную или импортируйте .txt файл</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="tbl">
            <thead>
              <tr>
                <th className="w-10">
                  <input type="checkbox" className="accent-[#8b5cf6]"
                    checked={allChecked}
                    onChange={e => setSelected(e.target.checked ? new Set(accounts.map(a => a.email)) : new Set())} />
                </th>
                <th>Email</th>
                <th>SMTP</th>
                <th>Прокси</th>
                <th>Лимит/д</th>
                <th>Статус</th>
                <th className="text-right pr-4">Действия</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map(acc => {
                const isTesting = testing === acc.email
                return (
                  <tr key={acc.email}>
                    <td className="w-10">
                      <input type="checkbox" className="accent-[#8b5cf6]"
                        checked={selected.has(acc.email)}
                        onChange={e => {
                          const s = new Set(selected)
                          e.target.checked ? s.add(acc.email) : s.delete(acc.email)
                          setSelected(s)
                        }} />
                    </td>
                    <td>
                      <button onClick={() => editAcc(acc)}
                        className="font-mono text-xs text-[#06b6d4] hover:text-[#22d3ee] transition-colors">
                        {acc.email}
                      </button>
                      {acc.display_name && (
                        <div className="text-xs text-[#6666aa] mt-0.5">{acc.display_name}</div>
                      )}
                    </td>
                    <td className="text-xs text-[#6666aa] font-mono">
                      {acc.host}:{acc.port}
                    </td>
                    <td>
                      {acc.proxy
                        ? <span className="badge badge-cyan"><Globe size={9} /> Прокси</span>
                        : <span className="text-xs text-[#6666aa]">—</span>
                      }
                    </td>
                    <td className="text-xs text-[#6666aa] tabular-nums">{acc.daily_limit}</td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <StatusIcon ok={acc.last_test_ok} testing={isTesting} />
                        <span className={`text-xs ${
                          isTesting              ? 'text-[#a78bfa]'  :
                          acc.last_test_ok === true  ? 'text-[#10b981]' :
                          acc.last_test_ok === false ? 'text-[#ef4444]' : 'text-[#6666aa]'
                        }`}>
                          {isTesting             ? 'Проверка...' :
                           acc.last_test_ok === true  ? 'ОК' :
                           acc.last_test_ok === false ? 'Ошибка' : 'Не проверен'}
                        </span>
                      </div>
                      {!isTesting && acc.last_test_ok === false && acc.last_test_msg && (
                        <div className="text-[10px] text-[#ef4444]/70 mt-0.5 max-w-[160px] truncate"
                          title={acc.last_test_msg}>{acc.last_test_msg}</div>
                      )}
                    </td>
                    <td className="text-right pr-2">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => testOne(acc)}
                          disabled={isTesting || testAll}
                          title="Проверить SMTP"
                          className="btn btn-ghost btn-sm p-1.5"
                        >
                          <RefreshCw size={12} className={isTesting ? 'animate-spin' : ''} />
                        </button>
                        <button onClick={() => del(acc.email)} title="Удалить"
                          className="btn btn-ghost btn-sm p-1.5 hover:text-[#ef4444]">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
