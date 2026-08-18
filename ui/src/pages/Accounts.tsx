import { useEffect, useState, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { GothicIcon } from '../components/GothicIcon'
import { api, getBaseUrl, type Account, type SmtpPreset } from '../api'

function StatusIcon({ ok, testing }: { ok: boolean | null; testing?: boolean }) {
  if (testing) return <GothicIcon name="waiting" size={13} className="text-purple-light animate-spin" />
  if (ok === true)  return <GothicIcon name="check" size={13} className="text-success" />
  if (ok === false) return <GothicIcon name="error" size={13} className="text-error" />
  return <GothicIcon name="waiting" size={13} className="text-muted" />
}

interface Frm {
  email: string; password: string; host: string; port: number
  use_ssl: boolean; use_tls: boolean; display_name: string
  daily_limit: number; hourly_limit: number
  proxy: string; imap_host: string; imap_port: number; imap_ssl: boolean
  refresh_token: string
}

const EMPTY: Frm = {
  email: '', password: '', host: '', port: 587,
  use_ssl: false, use_tls: true, display_name: '',
  daily_limit: 500, hourly_limit: 50,
  proxy: '', imap_host: '', imap_port: 993, imap_ssl: true,
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
  const [smtpPreset, setSmtpPreset] = useState<SmtpPreset | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const fileRef = useRef<HTMLInputElement>(null)
  const esRef   = useRef<EventSource | null>(null)

  const load = () => api.accounts.list().then(setAccounts).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => {
    load()
    return () => { esRef.current?.close() }
  }, [])

  function set(k: keyof Frm, v: any) { setForm(f => ({ ...f, [k]: v })) }

  function applySmtpPreset(preset: SmtpPreset, force = false) {
    setSmtpPreset(preset)
    if (!preset.known) return
    setForm(f => ({
      ...f,
      ...((force || !f.host.trim()) ? {
        host: preset.host,
        port: preset.port,
        use_ssl: preset.use_ssl,
        use_tls: preset.use_tls,
      } : {}),
      ...((force || !f.imap_host.trim()) && preset.imap_host ? {
        imap_host: preset.imap_host,
        imap_port: preset.imap_port,
        imap_ssl: preset.imap_ssl,
      } : {}),
    }))
  }

  async function lookupSmtp(email: string, force = false) {
    try {
      const preset = await api.accounts.smtpPreset(email)
      applySmtpPreset(preset, force)
    } catch {
      setSmtpPreset(null)
    }
  }

  function onEmailBlur() {
    if (form.email.includes('@')) void lookupSmtp(form.email)
  }

  function onEmailPaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const value = e.clipboardData.getData('text').trim()
    // Only the first separator is structural. Colons remain valid inside a password.
    const match = value.match(/^([^\s|;:]+@[^\s|;:]+)[|;:](.+)$/)
    if (!match) return
    const email = match[1].trim()
    const password = match[2].trim()
    if (!password) return
    e.preventDefault()
    setForm(f => ({ ...f, email, password, refresh_token: '' }))
    void lookupSmtp(email, true)
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
      alert(`Импортировано: ${r.imported}; автозаполнено: ${r.auto_configured}; ручная настройка нужна: ${r.manual_required}; пропущено: ${r.skipped}`)
      load()
    } catch (ex: any) { setError(ex.message) }
    e.target.value = ''
  }

  function editAcc(acc: Account) {
    setForm({
      email: acc.email, password: acc.password, host: acc.host, port: acc.port,
      use_ssl: acc.use_ssl, use_tls: acc.use_tls, display_name: acc.display_name,
      daily_limit: acc.daily_limit, hourly_limit: acc.hourly_limit,
      proxy: acc.proxy, imap_host: acc.imap_host, imap_port: acc.imap_port, imap_ssl: acc.imap_ssl,
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
              <GothicIcon name="delete" size={13} /> Удалить {selected.size}
            </button>
          )}
          <button
            onClick={testAll ? () => { esRef.current?.close(); esRef.current = null; setTestAll(false); setTestProgress(null) } : testAllFn}
            disabled={accounts.length === 0}
            className={`btn btn-sm ${testAll ? 'btn-danger' : 'btn-secondary'}`}
          >
            {testAll
              ? <><GothicIcon name="waiting" size={24} className="animate-spin" /> Стоп ({testProgress?.done ?? 0}/{testProgress?.total ?? accounts.length})</>
              : <><GothicIcon name="refresh" size={13} /> Проверить все</>
            }
          </button>
          <button onClick={() => fileRef.current?.click()} className="btn btn-secondary btn-sm">
            <GothicIcon name="import" size={13} /> Импорт
          </button>
          <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={importFile} />
          <button onClick={() => { setShowForm(true); setEditEmail(null); setForm(EMPTY) }}
            className="btn btn-primary btn-sm">
            <GothicIcon name="add" size={13} /> Добавить
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
              {!editEmail && (
                <p className="text-xs text-[#6666aa]">Вставьте в поле Email строку <code>email|пароль</code>, <code>email;пароль</code> или <code>email:пароль</code>: SMTP и IMAP заполнятся из проверенного каталога. Для неизвестного домена укажите SMTP вручную.</p>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Email</label>
                  <input className="input" placeholder="user@gmail.com или user@mail.com|app-password" value={form.email}
                    onChange={e => { set('email', e.target.value); setSmtpPreset(null) }}
                    onPaste={onEmailPaste}
                    onBlur={onEmailBlur} disabled={!!editEmail} />
                  {smtpPreset && (
                    <p className={`mt-1 text-[11px] ${smtpPreset.known ? 'text-[#10b981]' : 'text-[#f59e0b]'}`}>
                      {smtpPreset.message}{smtpPreset.password_hint ? ` ${smtpPreset.password_hint}` : ''}
                    </p>
                  )}
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
                      onChange={e => {
                        const p = +e.target.value
                        setForm(f => ({ ...f, port: p, use_ssl: p === 465, use_tls: p !== 465 }))
                      }} />
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
                  <label className="label">IMAP хост</label>
                  <input className="input" placeholder="imap.gmail.com" value={form.imap_host}
                    onChange={e => set('imap_host', e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="label">IMAP порт</label>
                    <input className="input" type="number" value={form.imap_port}
                      onChange={e => set('imap_port', +e.target.value)} />
                  </div>
                  <div>
                    <label className="label">IMAP TLS</label>
                    <select className="input" value={form.imap_ssl ? 'ssl' : 'plain'}
                      onChange={e => set('imap_ssl', e.target.value === 'ssl')}>
                      <option value="ssl">SSL / 993</option>
                      <option value="plain">Без SSL</option>
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
        <div className="empty"><GothicIcon name="refresh" size={24} className="animate-spin" /></div>
      ) : accounts.length === 0 ? (
        <div className="empty">
          <GothicIcon name="accounts" size={36} />
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
                        ? <span className="badge badge-cyan"><GothicIcon name="proxies" size={9} /> Прокси</span>
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
                          <GothicIcon name="refresh" size={12} className={isTesting ? 'animate-spin' : ''} />
                        </button>
                        <button onClick={() => del(acc.email)} title="Удалить"
                          className="btn btn-ghost btn-sm p-1.5 hover:text-[#ef4444]">
                          <GothicIcon name="delete" size={12} />
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
