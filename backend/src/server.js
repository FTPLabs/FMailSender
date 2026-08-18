'use strict'
/**
 * FMailSender — Node.js Express Backend v7.5.6
 * Drop-in replacement for Python FastAPI core/server.py
 * All endpoints identical, port 7531.
 */
const express  = require('express')
const multer   = require('multer')
const path     = require('path')
const http     = require('http')

const storage  = require('./storage')
const proxy    = require('./proxy')
const sender   = require('./sender')
const license  = require('./license')
const { createTemplateWithPersonalKey } = require('./gemini_local')
const { getSmtpConfigForDomain, getSmtpPresetForEmail } = require('./smtp_configs')

const APP_VERSION = '7.5.6'
const PORT        = parseInt(process.env.FMAIL_PORT || '7531', 10)
const TEST_MODE   = process.argv.includes('--test')

// ── App state ─────────────────────────────────────────────────────────────────
let _accounts   = []
let _proxies    = []
let _recipients = []
let _campaignCfg = {}
let _campaignStatus = { state: 'idle', sent: 0, failed: 0, total: 0, current_email: '', current_account: '', started_at: 0, errors: [] }
let _engine     = null
let _stopEvent  = null
let _runId      = 0
let _accountsSaveTimer = null

// ── Load state on startup ─────────────────────────────────────────────────────
function _init() {
  _accounts    = storage.loadAccounts()
  _proxies     = storage.loadProxies()
  _recipients  = storage.loadRecipients()
  _campaignCfg = storage.loadCampaign()
}

function _scheduleAccountsSave() {
  if (_accountsSaveTimer) return
  _accountsSaveTimer = setTimeout(() => {
    _accountsSaveTimer = null
    storage.saveAccounts(_accounts)
  }, 500)
}

// ── Express setup ─────────────────────────────────────────────────────────────
const app    = express()
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } })

app.use(express.json({ limit: '50mb' }))
app.use(express.urlencoded({ extended: true }))
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  if (req.method === 'OPTIONS') return res.sendStatus(204)
  next()
})

// ── Serve React UI (built dist/) ──────────────────────────────────────────────
const uiDist = process.env.FMAIL_UI_DIST || path.join(__dirname, '..', '..', 'ui', 'dist')
app.use(express.static(uiDist))

// ── License guard middleware ──────────────────────────────────────────────────
const LICENSE_EXEMPT = new Set([
  '/api/health', '/api/license', '/api/license/activate', '/api/license/poll', '/api/events',
])

app.use((req, res, next) => {
  if (!req.path.startsWith('/api')) return next()   // static files pass through
  if (LICENSE_EXEMPT.has(req.path)) return next()
  if (!license.getLicenseOk()) {
    return res.status(403).json({ detail: 'Лицензия недействительна. Активируйте или продлите лицензию.' })
  }
  next()
})

// ── Health ────────────────────────────────────────────────────────────────────
app.get('/api/health', (req, res) => res.json({ ok: true, version: APP_VERSION }))

// ── Accounts ──────────────────────────────────────────────────────────────────
// Lookup never receives a password. It is the only SMTP preset source used by UI and import.
app.get('/api/accounts/smtp-preset', (req, res) => {
  const email = typeof req.query.email === 'string' ? req.query.email : ''
  res.json(getSmtpPresetForEmail(email))
})

app.get('/api/accounts', (req, res) => res.json(_accounts))

app.post('/api/accounts', (req, res) => {
  const body = req.body || {}
  if (!getSmtpPresetForEmail(body.email).domain) {
    return res.status(400).json({ detail: 'Введите корректный email-адрес.' })
  }
  if (_accounts.some(a => a.email.toLowerCase() === body.email.toLowerCase())) {
    return res.status(400).json({ detail: `Account ${body.email} already exists` })
  }
  const acc = _makeAccount(_applySmtpPreset(body))
  _accounts.push(acc)
  storage.saveAccounts(_accounts)
  res.json(acc)
})

app.put('/api/accounts/:email', (req, res) => {
  const idx = _accounts.findIndex(a => a.email.toLowerCase() === req.params.email.toLowerCase())
  if (idx === -1) return res.status(404).json({ detail: 'Account not found' })
  if (!getSmtpPresetForEmail(req.body?.email).domain) {
    return res.status(400).json({ detail: 'Введите корректный email-адрес.' })
  }
  _accounts[idx] = _makeAccount(_applySmtpPreset(req.body || {}))
  storage.saveAccounts(_accounts)
  res.json(_accounts[idx])
})

app.delete('/api/accounts/:email', (req, res) => {
  const before = _accounts.length
  _accounts = _accounts.filter(a => a.email.toLowerCase() !== req.params.email.toLowerCase())
  if (_accounts.length === before) return res.status(404).json({ detail: 'Account not found' })
  storage.saveAccounts(_accounts)
  res.json({ ok: true })
})

app.post('/api/accounts/test', async (req, res) => {
  const acc = _makeAccount(req.body)
  const [ok, msg] = await sender.testSmtpConnection(acc)
  const existing = _accounts.find(a => a.email.toLowerCase() === req.body.email.toLowerCase())
  if (existing) { existing.last_test_ok = ok; existing.last_test_msg = msg; storage.saveAccounts(_accounts) }
  res.json({ ok, message: msg })
})

app.post('/api/accounts/test-all', async (req, res) => {
  const sem = _semaphore(4)
  const results = await Promise.all(_accounts.map(async (acc, i) => {
    await sem.acquire()
    try {
      const [ok, msg] = await sender.testSmtpConnection(acc)
      acc.last_test_ok = ok; acc.last_test_msg = msg
      return { index: i, email: acc.email, ok, message: msg }
    } finally { sem.release() }
  }))
  storage.saveAccounts(_accounts)
  res.json({
    results: results.sort((a, b) => a.index - b.index),
    ok:     results.filter(r => r.ok).length,
    failed: results.filter(r => !r.ok).length,
    total:  results.length,
  })
})

// SSE: test-all stream
app.get('/api/accounts/test-all/stream', async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  res.flushHeaders()

  const snap  = [..._accounts]
  const total = snap.length

  if (!total) {
    res.write(`data: ${JSON.stringify({ complete: true, ok: 0, failed: 0, total: 0 })}\n\n`)
    return res.end()
  }

  let done = 0, ok_n = 0, fail_n = 0
  const sem = _semaphore(4)
  let aborted = false
  req.on('close', () => { aborted = true })

  await Promise.all(snap.map(async (acc, i) => {
    if (aborted) return
    await sem.acquire()
    if (aborted) { sem.release(); return }
    try {
      const [ok, msg] = await sender.testSmtpConnection(acc)
      acc.last_test_ok = ok; acc.last_test_msg = msg
      done++
      ok ? ok_n++ : fail_n++
      res.write(`data: ${JSON.stringify({ index: i, email: acc.email, ok, message: msg, done, total })}\n\n`)
    } catch (e) {
      done++; fail_n++
      res.write(`data: ${JSON.stringify({ index: i, email: acc.email, ok: false, message: String(e), done, total })}\n\n`)
    } finally { sem.release() }
  }))

  storage.saveAccounts(_accounts)
  res.write(`data: ${JSON.stringify({ complete: true, ok: ok_n, failed: fail_n, total })}\n\n`)
  res.end()
})

app.post('/api/accounts/import-txt', upload.single('file'), (req, res) => {
  if (!req.file?.buffer) return res.status(400).json({ detail: 'Файл импорта не выбран.' })
  const content = req.file.buffer.toString('utf8')
  const existing = new Set(_accounts.map(a => a.email.toLowerCase()))
  const added = []
  let imported = 0, skipped = 0, auto_configured = 0, manual_required = 0

  for (const rawLine of content.split(/\r?\n/)) {
    const line = String(rawLine || '').trim()
    if (!line || line.startsWith('#')) continue
    const parsed = _parseImportedCredential(line)
    if (!parsed || existing.has(parsed.email.toLowerCase())) { skipped++; continue }
    const preset = getSmtpPresetForEmail(parsed.email)
    const body = _applySmtpPreset({
      email: parsed.email,
      password: parsed.password,
      refresh_token: '',
    })
    _accounts.push(_makeAccount(body))
    added.push(_accounts[_accounts.length - 1])
    existing.add(parsed.email.toLowerCase())
    imported++
    preset.known ? auto_configured++ : manual_required++
  }

  if (_proxies.length && added.length) {
    new proxy.ProxyManager(_proxies).distribute(added, _accounts.length - added.length)
  }
  storage.saveAccounts(_accounts)
  res.json({ imported, skipped, auto_configured, manual_required, total: _accounts.length })
})

// ── Proxies ───────────────────────────────────────────────────────────────────
app.get('/api/proxies', (req, res) => res.json({ proxies: _proxies, count: _proxies.length }))

app.post('/api/proxies', (req, res) => {
  const normalized = proxy.normalizeProxyList(req.body?.proxies || [])
  _proxies = normalized.proxies
  storage.saveProxies(_proxies)
  res.json({ count: _proxies.length, imported: _proxies.length, invalid: normalized.invalid, duplicates: normalized.duplicates, ignored: normalized.ignored })
})

app.post('/api/proxies/check', async (req, res) => {
  const raw = req.body?.proxies || _proxies
  const toCheck = proxy.normalizeProxyList(raw).proxies
  const sem = _semaphore(4)
  const results = await Promise.all(toCheck.map(async item => {
    await sem.acquire()
    try { return await proxy.validateProxy(item) }
    finally { sem.release() }
  }))
  res.json({ results, valid: results.filter(r => r.ok).length, smtp_ok: results.filter(r => r.smtp_ok).length, total: toCheck.length })
})

app.post('/api/proxies/distribute', (req, res) => {
  if (!_proxies.length) return res.status(400).json({ detail: 'No proxies loaded' })
  new proxy.ProxyManager(_proxies).distribute(_accounts)
  storage.saveAccounts(_accounts)
  res.json({ distributed: _accounts.length, proxies: _proxies.length })
})

// ── Recipients ────────────────────────────────────────────────────────────────
app.get('/api/recipients', (req, res) => res.json({ recipients: _recipients, count: _recipients.length }))

app.post('/api/recipients', (req, res) => {
  _recipients = req.body.recipients || []
  storage.saveRecipients(_recipients)
  res.json({ count: _recipients.length })
})

app.post('/api/recipients/import-txt', upload.single('file'), (req, res) => {
  const content  = req.file.buffer.toString('utf8')
  const existing = new Set(_recipients.map(r => r.email.toLowerCase()))
  let added = 0
  for (let line of content.split('\n')) {
    line = line.trim()
    if (!line || line.startsWith('#')) continue
    const parts = line.split('|')
    const email = parts[0].trim()
    const name  = parts[1]?.trim() || ''
    if (!email.includes('@') || existing.has(email.toLowerCase())) continue
    _recipients.push({ email, name, variables: {} })
    existing.add(email.toLowerCase())
    added++
  }
  storage.saveRecipients(_recipients)
  res.json({ added, total: _recipients.length })
})

app.delete('/api/recipients', (req, res) => {
  _recipients = []
  storage.saveRecipients(_recipients)
  res.json({ ok: true })
})

// ── AI templates ──────────────────────────────────────────────────────────────
app.post('/api/ai/template', async (req, res) => {
  const body = req.body || {}
  const mode = body.mode === 'refine' ? 'refine' : body.mode === 'generate' ? 'generate' : ''
  const brief = typeof body.brief === 'string' ? body.brief.trim() : ''
  const subject = typeof body.subject === 'string' ? body.subject.trim() : ''
  const bodyHtml = typeof body.body_html === 'string' ? body.body_html : ''
  const bodyText = typeof body.body_text === 'string' ? body.body_text : ''
  // A personal key is request-scoped only: it is never persisted, logged, or sent to the license server.
  const personalApiKey = typeof body.personal_api_key === 'string' ? body.personal_api_key.trim() : ''
  if (personalApiKey.length > 256) return res.status(400).json({ detail: 'Некорректная длина Gemini API-ключа.' })
  if (!mode) return res.status(400).json({ detail: 'Неизвестный режим AI-операции.' })
  if (brief.length > 1200 || subject.length > 180 || bodyHtml.length > 20_000 || bodyText.length > 8_000) {
    return res.status(413).json({ detail: 'Превышен допустимый размер запроса AI.' })
  }
  try {
    const result = personalApiKey
      ? await createTemplateWithPersonalKey({ apiKey: personalApiKey, mode, brief, subject, body_html: bodyHtml, body_text: bodyText })
      : await license.requestAiTemplate({ mode, brief, subject, body_html: bodyHtml, body_text: bodyText })
    res.json(result)
  } catch (err) {
    const detail = err instanceof Error ? err.message : 'Не удалось выполнить AI-операцию.'
    // Do not log request content or a user-supplied API key.
    console.warn(`[ai] template request failed: ${detail}`)
    res.status(502).json({ detail })
  }
})

// ── Campaign ──────────────────────────────────────────────────────────────────
app.get('/api/campaign', (req, res) => res.json({ ..._campaignCfg, status: _campaignStatus }))

app.post('/api/campaign', (req, res) => {
  _campaignCfg = { ...storage.loadCampaign(), ...req.body }
  storage.saveCampaign(_campaignCfg)
  res.json({ ok: true })
})

function _campaignReadiness() {
  const errors = []
  const warnings = []
  const active = _accounts.filter(a => a.is_active && a.last_test_ok === true)
  const subject = String(_campaignCfg.subject || '').trim()
  const bodyHtml = String(_campaignCfg.body_html || '').trim()
  const bodyText = String(_campaignCfg.body_text || '').trim()
  const replyTo = String(_campaignCfg.reply_to || '').trim()
  const delayMin = Number(_campaignCfg.delay_min || 1)
  const availableDaily = active.reduce((sum, account) => sum + Math.max(0, Number(account.daily_limit || 0) - Number(account.sent_today || 0)), 0)
  if (!active.length) errors.push('no_ready_accounts')
  if (!_recipients.length) errors.push('no_recipients')
  if (!subject) errors.push('missing_subject')
  if (!bodyHtml && !bodyText) errors.push('missing_body')
  if (!replyTo) warnings.push('missing_reply_to')
  if (!bodyText) warnings.push('missing_text_version')
  if (!/unsubscribe|отпис/i.test(`${bodyHtml} ${bodyText}`)) warnings.push('missing_unsubscribe')
  if (delayMin < 30) warnings.push('short_delay')
  if (availableDaily > 0 && _recipients.length > availableDaily) warnings.push('daily_capacity')
  return { ready: errors.length === 0, errors, warnings, active_accounts: active.length, recipients: _recipients.length, available_daily: availableDaily }
}

app.get('/api/campaign/readiness', (req, res) => res.json(_campaignReadiness()))

app.post('/api/campaign/start', (req, res) => {
  if (_campaignStatus.state === 'running') return res.status(400).json({ detail: 'Campaign already running' })
  const readiness = _campaignReadiness()
  if (!readiness.ready) return res.status(400).json({ detail: 'Campaign is not ready. Review the readiness panel.', readiness })

  const active = _accounts.filter(a => a.is_active && a.last_test_ok === true)

  _runId++
  const currentRun = _runId
  _campaignStatus  = { state: 'running', sent: 0, failed: 0, total: _recipients.length, current_email: '', current_account: '', started_at: Date.now() / 1000, errors: [] }

  const stop = { _flag: false, isSet() { return this._flag }, set() { this._flag = true } }
  _stopEvent = stop

  _engine = new sender.SendingEngine({
    accounts:  active,
    config:    {
      min_delay_ms:    (_campaignCfg.delay_min || 1.0) * 1000,
      max_delay_ms:    (_campaignCfg.delay_max || 3.0) * 1000,
      max_threads:     Math.min(active.length, 10),
      rotate_accounts: true,
      uniqueize:       false, // quality variants are created explicitly in Compose AI and reviewed by the user
    },
    recipients: _recipients.map(r => ({ email: r.email, name: r.name || '', variables: r.variables || {} })),
    template:  {
      subject:   _campaignCfg.subject   || '',
      body_html: _campaignCfg.body_html || '',
      body_text: _campaignCfg.body_text || '',
      reply_to:  _campaignCfg.reply_to  || '',
      from_name: _campaignCfg.from_name || '',
    },
    stopEvent: stop,
  })

  _engine.on_progress = (sent, total, result) => {
    if (_runId !== currentRun) return
    _campaignStatus.sent  = sent
    _campaignStatus.total = total
    if (result && !result.success) {
      _campaignStatus.failed++
      if (result.error) _campaignStatus.errors.push(`${result.recipient_email}: ${result.error}`)
    }
    if (result?.success) _scheduleAccountsSave()
    _campaignStatus.current_email   = result?.recipient_email || ''
    _campaignStatus.current_account = result?.account_used    || ''
  }

  _engine.on_finished = results => {
    if (_runId !== currentRun) return
    _campaignStatus.state  = 'done'
    _campaignStatus.sent   = results.filter(r => r.success).length
    _campaignStatus.failed = results.filter(r => !r.success).length
    if (_accountsSaveTimer) { clearTimeout(_accountsSaveTimer); _accountsSaveTimer = null }
    storage.saveAccounts(_accounts)
  }

  _engine.run().catch(err => {
    if (_runId === currentRun) { _campaignStatus.state = 'error'; _campaignStatus.errors.push(String(err)) }
  })

  res.json({ ok: true, total: _recipients.length, accounts: active.length })
})

app.post('/api/campaign/pause', (req, res) => {
  if (_engine && _campaignStatus.state === 'running') { _engine._paused = true; _campaignStatus.state = 'paused' }
  res.json(_campaignStatus)
})

app.post('/api/campaign/resume', (req, res) => {
  if (_engine && _campaignStatus.state === 'paused') { _engine._paused = false; _campaignStatus.state = 'running' }
  res.json(_campaignStatus)
})

app.post('/api/campaign/stop', (req, res) => {
  _runId++
  if (_stopEvent) _stopEvent.set()
  if (_engine) _engine._paused = false
  _campaignStatus.state = 'idle'
  res.json({ ok: true })
})

// ── Status ────────────────────────────────────────────────────────────────────
function _buildStatus() {
  const ok_cnt   = _accounts.filter(a => a.last_test_ok === true).length
  const fail_cnt = _accounts.filter(a => a.last_test_ok === false).length
  return {
    campaign:   { ..._campaignStatus, progress_pct: Math.round(_campaignStatus.sent / Math.max(_campaignStatus.total, 1) * 1000) / 10, errors: (_campaignStatus.errors || []).slice(-20) },
    accounts:   { total: _accounts.length, valid: ok_cnt, invalid: fail_cnt, untested: _accounts.length - ok_cnt - fail_cnt, ready: _accounts.filter(a => a.is_active && a.last_test_ok === true).length },
    recipients: _recipients.length,
    proxies:    _proxies.length,
  }
}

app.get('/api/status', (req, res) => res.json(_buildStatus()))

// SSE: /api/events
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no')
  res.flushHeaders()

  let aborted = false
  req.on('close', () => { aborted = true })

  const tick = () => {
    if (aborted) return
    try { res.write(`data: ${JSON.stringify(_buildStatus())}\n\n`) } catch {}
    const interval = _campaignStatus.state === 'running' ? 800 : 2000
    setTimeout(tick, interval)
  }
  tick()
})

// ── License ────────────────────────────────────────────────────────────────────
app.get('/api/license', async (req, res) => {
  const cached = license.getCachedLicenseStatus()
  license.setLicenseOk(Boolean(cached.valid))

  // fire background validation (non-blocking)
  if (!license.isBgChecking()) {
    license.setBgChecking(true)
    license.validateOnStartup()
      .then(r => { license.setLicenseOk(Boolean(r.valid)); if (!r.valid) _stopCampaign() })
      .finally(() => license.setBgChecking(false))
      .catch(() => {})
  }

  res.json({ ...cached, background_checking: true })
})

app.get('/api/license/poll', (req, res) => {
  res.json({ valid: license.getLicenseOk(), checking: license.isBgChecking() })
})

app.post('/api/license/activate', async (req, res) => {
  const { key } = req.body
  if (!key) return res.status(400).json({ detail: 'Лицензионный ключ не указан' })
  try {
    const result = await license.activateLicenseKey(key.trim())
    if (result.success) license.setLicenseOk(true)
    res.json(result)
  } catch (err) {
    const detail = license.publicLicenseError(err, 'Не удалось активировать ключ. Повторите попытку позже.')
    console.warn(`[license] activation failed: ${detail}`)
    res.status(400).json({ detail })
  }
})

// ── DKIM (stub — optional in Node version) ────────────────────────────────────
app.get('/api/dkim', (req, res) => res.json({ available: false, configs: [], message: 'DKIM not yet available in Node.js core. Coming soon.' }))
app.post('/api/dkim', (req, res) => res.status(400).json({ detail: 'DKIM not yet available in Node.js core. Coming soon.' }))

// ── SPA fallback ──────────────────────────────────────────────────────────────
app.get('*', (req, res) => {
  const index = path.join(uiDist, 'index.html')
  if (require('fs').existsSync(index)) res.sendFile(index)
  else res.status(404).send('UI not built. Run: cd ui && npm run build')
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function _applySmtpPreset(body) {
  const input = body && typeof body === 'object' ? body : {}
  const preset = getSmtpPresetForEmail(input.email)
  if (!preset.known) return input
  const output = { ...input }
  if (!String(output.host || '').trim()) {
    output.host = preset.host
    output.port = preset.port
    output.use_ssl = preset.use_ssl
    output.use_tls = preset.use_tls
  }
  // IMAP is filled only from a verified provider preset; unknown domains remain manual.
  if (!String(output.imap_host || '').trim() && preset.imap_host) {
    output.imap_host = preset.imap_host
    output.imap_port = preset.imap_port
    output.imap_ssl = preset.imap_ssl
  }
  return output
}

function _parseImportedCredential(rawLine) {
  const line = String(rawLine || '').trim()
  if (!line || line.startsWith('#')) return null
  // Delimit only once. This preserves ':' inside passwords and avoids logging them.
  const match = line.match(/^([^\s|;:]+@[^\s|;:]+)[|;:](.+)$/)
  if (!match) return null
  const email = match[1].trim().toLowerCase()
  const password = match[2].trim()
  if (!getSmtpPresetForEmail(email).domain || !password) return null
  return { email, password }
}

function _makeAccount(body) {
  return {
    email: body.email || '', password: body.password || '',
    host: body.host || '', port: body.port || 587,
    use_ssl: body.use_ssl ?? false, use_tls: body.use_tls ?? true,
    display_name: body.display_name || '',
    daily_limit: body.daily_limit || 500, hourly_limit: body.hourly_limit || 50,
    is_active: body.is_active ?? true,
    proxy: body.proxy || '', proxy_list: body.proxy_list || [],
    access_token: body.access_token || '', refresh_token: body.refresh_token || '',
    token_expires_at: body.token_expires_at || 0,
    imap_host: body.imap_host || '', imap_port: body.imap_port || 993, imap_ssl: body.imap_ssl ?? true,
    last_test_ok: body.last_test_ok ?? null, last_test_msg: body.last_test_msg || '',
    sent_today: body.sent_today || 0, sent_this_hour: body.sent_this_hour || 0,
  }
}

function _stopCampaign() {
  if (_stopEvent) _stopEvent.set()
  _campaignStatus.state = 'idle'
}

function _semaphore(n) {
  let count = 0
  const queue = []
  return {
    acquire() {
      return new Promise(resolve => {
        if (count < n) { count++; resolve() }
        else queue.push(resolve)
      })
    },
    release() {
      if (queue.length > 0) queue.shift()()
      else count--
    },
  }
}

// ── Start ─────────────────────────────────────────────────────────────────────
if (TEST_MODE) {
  console.log(`FMailSender Node.js backend v${APP_VERSION} — import test OK`)
  process.exit(0)
}
_init()
license.startPeriodicCheck(_stopCampaign)

const server = http.createServer(app)
server.listen(PORT, '127.0.0.1', () => {
  console.log(`FMailSender backend v${APP_VERSION} listening on http://127.0.0.1:${PORT}`)
})

// Graceful shutdown
process.on('SIGTERM', () => { license.stopPeriodicCheck(); server.close(() => process.exit(0)) })
process.on('SIGINT',  () => { license.stopPeriodicCheck(); server.close(() => process.exit(0)) })

module.exports = { app }
