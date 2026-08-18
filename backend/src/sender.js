'use strict'
/**
 * FMailSender SMTP Sending Engine — Node.js
 * Uses nodemailer for actual delivery.
 * Supports SSL/TLS/STARTTLS, SOCKS5 + HTTP proxies, OAuth2 (XOAUTH2),
 * per-account rate limiting (daily/hourly), parallel workers, pause/stop.
 */
const nodemailer = require('nodemailer')
const { SocksProxyAgent } = require('socks-proxy-agent')
const { HttpsProxyAgent } = require('hpagent')
const { getSmtpConfigForDomain } = require('./smtp_configs')

// ── Utilities ─────────────────────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms))


const HEADER_MAX = 180
function safeHeader(value, field, max = HEADER_MAX) {
  const text = String(value ?? '').trim()
  if (/[\r\n\0]/.test(text)) throw new Error(`${field} содержит недопустимый перенос строки.`)
  if (text.length > max) throw new Error(`${field} превышает допустимую длину.`)
  return text
}
function safeEmail(value, field) {
  const email = safeHeader(value, field, 254)
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error(`${field} имеет некорректный формат.`)
  return email
}

function randBetween(min, max) {
  return Math.random() * (max - min) + min
}

function spintax(text) {
  // Replace {opt1|opt2|...} with a random choice
  return text.replace(/\{([^{}]*)\}/g, (_, inner) => {
    const opts = inner.split('|')
    return opts[Math.floor(Math.random() * opts.length)]
  })
}

function substituteVars(template, recipient) {
  const vars = {
    '{{email}}':      recipient.email     || '',
    '{{name}}':       recipient.name      || '',
    '{{first_name}}': (recipient.name || '').split(' ')[0] || '',
    '{{last_name}}':  (recipient.name || '').split(' ').slice(1).join(' ') || '',
    '{{company}}':    recipient.variables?.company || '',
    '{{custom_1}}':   recipient.variables?.custom_1 || '',
    '{{custom_2}}':   recipient.variables?.custom_2 || '',
  }
  let result = template
  for (const [k, v] of Object.entries(vars)) result = result.replaceAll(k, v)
  return result
}

// ── Account rate limiting ─────────────────────────────────────────────────────
function dayKey(now = new Date()) { return now.toISOString().slice(0, 10) }
function hourKey(now = new Date()) { return now.toISOString().slice(0, 13) }

class AccountLimits {
  constructor(acc) {
    this.account = acc
    this.dailyLimit = Math.max(1, Number(acc.daily_limit || 500))
    this.hourlyLimit = Math.max(1, Number(acc.hourly_limit || 50))
    this.sentToday = acc._rate_day === dayKey() ? Number(acc.sent_today || 0) : 0
    this.sentHour = acc._rate_hour === hourKey() ? Number(acc.sent_this_hour || 0) : 0
    this._commit()
  }

  _commit() {
    this.account.sent_today = this.sentToday
    this.account.sent_this_hour = this.sentHour
    this.account._rate_day = dayKey()
    this.account._rate_hour = hourKey()
  }

  _tick() {
    if (this.account._rate_day !== dayKey()) { this.sentToday = 0; this.sentHour = 0 }
    else if (this.account._rate_hour !== hourKey()) this.sentHour = 0
    this._commit()
  }

  increment() {
    this._tick()
    if (this.sentToday >= this.dailyLimit || this.sentHour >= this.hourlyLimit) return false
    this.sentToday++; this.sentHour++
    this._commit()
    return true
  }

  rollback() {
    this._tick()
    this.sentToday = Math.max(0, this.sentToday - 1)
    this.sentHour = Math.max(0, this.sentHour - 1)
    this._commit()
  }
}

// ── Proxy agent factory ───────────────────────────────────────────────────────
function makeProxyAgent(proxyUrl, secure) {
  if (!proxyUrl) return undefined
  let u
  try { u = new URL(proxyUrl.includes('://') ? proxyUrl : 'socks5://' + proxyUrl) }
  catch { throw new Error('Некорректный формат proxy URL.') }
  const scheme = u.protocol.replace(':', '').toLowerCase()
  if (!u.hostname || !u.port) throw new Error('Proxy URL должен содержать host и port.')
  if (scheme === 'socks5' || scheme === 'socks4') return new SocksProxyAgent(u.toString())
  if (scheme === 'http' || scheme === 'https') {
    const Agent = secure ? HttpsProxyAgent : require('hpagent').HttpProxyAgent
    return new Agent({ proxy: u.toString() })
  }
  throw new Error('Поддерживаются только HTTP(S), SOCKS4 и SOCKS5 proxy.')
}

function normalizeBool(value, fallback = false) {
  if (typeof value === 'boolean') return value
  if (value == null) return fallback
  if (typeof value === 'string') return !['', '0', 'false', 'no', 'off'].includes(value.trim().toLowerCase())
  return Boolean(value)
}

function providerFromEmail(email) {
  const domain = String(email || '').trim().toLowerCase().split('@').pop() || ''
  if (domain === 'gmx.com' || domain.startsWith('gmx.')) return 'gmx'
  if (['rambler.ru', 'lenta.ru', 'ro.ru', 'autorambler.ru', 'myrambler.ru'].includes(domain)) return 'rambler'
  return ''
}

function sanitizedTransportError(err, email) {
  const message = String(err?.message || err || 'Неизвестная ошибка')
    .replaceAll(String(email || ''), '[account]')
    .replace(/\b(?:AUTH(?:\s+PLAIN)?|LOGIN|XOAUTH2)\b.*$/gim, '[auth data hidden]')
  return message.slice(0, 220)
}

/**
 * Produces a user-safe diagnostic. It deliberately does not disclose a supplied
 * password or server response credentials, and it never retries authentication.
 */
function isSpamRejectionError(err) {
  const responseCode = Number(err?.responseCode || 0)
  const raw = String(err?.message || err || '').toLowerCase()
  return (responseCode === 554 || /\b554\b/.test(raw)) && /5\.7\.1|spam|abuse|policy|content/.test(raw)
}

function classifySmtpError(err, account) {
  const provider = providerFromEmail(account?.email)
  const code = String(err?.code || '').toUpperCase()
  const responseCode = Number(err?.responseCode || 0)
  const raw = String(err?.message || err || '').toLowerCase()
  const authFailure = code === 'EAUTH' || [530, 534, 535, 538].includes(responseCode) ||
    /auth(?:entication)?\s+(?:failed|required)|invalid\s+(?:login|credential)|login\s+not\s+allowed|username and password/.test(raw)
  const networkFailure = ['ECONNREFUSED', 'ECONNRESET', 'EHOSTUNREACH', 'ENOTFOUND', 'ETIMEDOUT', 'ESOCKET'].includes(code) ||
    /timed?\s*out|connection\s+(?:refused|reset)|getaddrinfo/.test(raw)
  const tlsFailure = code === 'ETLS' || /certificate|tls|ssl|wrong version number/.test(raw)
  const temporaryFailure = [421, 450, 451, 452, 454].includes(responseCode) || /temporar|too many|rate.?limit|try again later/.test(raw)
  const spamRejection = (responseCode === 554 || /\b554\b/.test(raw)) && /5\.7\.1|spam|abuse|policy|content/i.test(raw)

  if (spamRejection && (provider === 'rambler' || /rambler|rambler-co\.ru/.test(raw))) {
    return 'Rambler: письмо отклонено антиспамом (554 5.7.1). Остановите повторные попытки, проверьте согласие получателя, SPF/DKIM/DMARC, List-Unsubscribe, ссылки и содержимое; при легитимной рассылке обратитесь в abuse Rambler.'
  }
  if (spamRejection) {
    return 'SMTP: письмо отклонено антиспам-политикой провайдера (554 5.7.1). Остановите повторы и проверьте согласие, аутентификацию домена, отписку, ссылки и содержимое.'
  }

  if (authFailure && provider === 'gmx') {
    return 'GMX: аутентификация не пройдена. Проверьте адрес и пароль. При 2FA используйте app password, а в GMX включите POP3/IMAP для внешних клиентов.'
  }
  if (authFailure && provider === 'rambler') {
    return 'Rambler: аутентификация не пройдена. Включите доступ почтовых клиентов в «Настройки → Программы». При 2FA создайте пароль для почтовых протоколов и используйте его вместо основного.'
  }
  if (authFailure) return 'SMTP: аутентификация не пройдена. Проверьте адрес, пароль приложения и настройки доступа внешнего клиента.'
  if (temporaryFailure) return 'SMTP: временное ограничение со стороны провайдера. Не повторяйте вход автоматически; проверьте уведомления в веб-почте и попробуйте позже.'
  if (tlsFailure) return 'SMTP: ошибка TLS/сертификата. Сверьте хост, порт и тип шифрования с официальной документацией провайдера.'
  if (networkFailure) return 'SMTP: сервер недоступен по сети. Проверьте хост, порт, firewall и proxy; учётные данные не проверялись.'
  return `SMTP: ${sanitizedTransportError(err, account?.email)}`
}

// ── SMTP connection test ──────────────────────────────────────────────────────
async function testSmtpConnection(account) {
  const domain = account.email.split('@')[1] || ''
  const cfg    = getSmtpConfigForDomain(domain)

  const host = String(account.host || cfg?.host || '').trim()
  const port = Number(account.port || cfg?.port || 587)
  const secure = normalizeBool(account.use_ssl != null ? account.use_ssl : (cfg?.secure ?? false), false)
  const requireTLS = secure ? false : normalizeBool(account.use_tls != null ? account.use_tls : (cfg?.requireTLS ?? true), true)

  if (!host) return [false, `Неизвестный провайдер: ${domain}. Укажите хост вручную.`]

  const proxy = account.proxy || ''
  let agent
  try { agent = proxy ? makeProxyAgent(proxy, secure) : undefined }
  catch (err) { return [false, err.message || String(err)] }

  const transportOpts = {
    host, port,
    secure,
    requireTLS,
    auth: { user: account.email, pass: account.password || account.access_token || '' },
    connectionTimeout: 15000,
    greetingTimeout:   10000,
    socketTimeout:     20000,
    ...(agent ? { socketOptions: { agent } } : {}),
  }

  // OAuth2 XOAUTH2
  if (account.access_token) {
    transportOpts.auth = { type: 'OAuth2', user: account.email, accessToken: account.access_token }
  }

  const transporter = nodemailer.createTransport(transportOpts)
  try {
    await transporter.verify()
    transporter.close()
    return [true, 'OK']
  } catch (err) {
    transporter.close()
    return [false, classifySmtpError(err, account)]
  }
}

// ── Sending Engine ────────────────────────────────────────────────────────────
class SendingEngine {
  constructor({ accounts, config, recipients, template, stopEvent }) {
    this.accounts   = accounts
    this.config     = config       // {min_delay_ms, max_delay_ms, max_threads, rotate_accounts, uniqueize}
    this.recipients = recipients   // [{email, name, variables}]
    this.template   = template     // {subject, body_html, body_text, reply_to}
    this.stopEvent  = stopEvent    // {set, isSet}
    this._paused    = false

    // callbacks set by server.js
    this.on_progress = null   // (sent, total, result) => void
    this.on_finished = null   // (results) => void

    this._limits = new Map(accounts.map(a => [a.email, new AccountLimits(a)]))
    this._accountIndex = 0
  }

  _nextAccount() {
    const active = this.accounts.filter(a => a.is_active && a.last_test_ok === true)
    if (!active.length) return null
    const acc = active[this._accountIndex % active.length]
    if (this.config.rotate_accounts) this._accountIndex++
    return acc
  }

  async _sendOne(acc, recipient) {
    const lim = this._limits.get(acc.email)
    if (!lim || !lim.increment()) return { success: false, error: 'Daily/hourly limit reached', account_used: acc.email, recipient_email: recipient.email }

    const domain   = acc.email.split('@')[1] || ''
    const cfg      = getSmtpConfigForDomain(domain)
    const host     = acc.host || cfg?.host || ''
    const port     = acc.port || cfg?.port || 587
    const secure   = acc.use_ssl != null ? acc.use_ssl  : (cfg?.secure ?? false)
    const requireTLS = acc.use_tls != null ? acc.use_tls : (cfg?.requireTLS ?? true)

    if (!host) {
      if (lim) lim.rollback()
      return { success: false, error: `Unknown provider: ${domain}`, account_used: acc.email, recipient_email: recipient.email }
    }

    let subject, bodyHtml, bodyText, fromName, recipientName, recipientEmail, replyTo, agent
    try {
      subject = safeHeader(spintax(substituteVars(this.template.subject || '', recipient)), 'Тема')
      bodyHtml = substituteVars(this.template.body_html || '', recipient)
      bodyText = substituteVars(this.template.body_text || '', recipient)
      fromName = safeHeader(acc.display_name || (this.template.from_name || ''), 'Имя отправителя', 120)
      recipientName = safeHeader(recipient.name || '', 'Имя получателя', 120)
      recipientEmail = safeEmail(recipient.email, 'Адрес получателя')
      replyTo = this.template.reply_to ? safeEmail(this.template.reply_to, 'Reply-To') : ''
      const proxy = acc.proxy || ''
      agent = proxy ? makeProxyAgent(proxy, secure) : undefined
    } catch (err) {
      if (lim) lim.rollback()
      return { success: false, error: classifySmtpError(err, acc), account_used: acc.email, recipient_email: recipient.email }
    }

    const transportOpts = {
      host, port, secure, requireTLS,
      auth: { user: acc.email, pass: acc.password || '' },
      connectionTimeout: 15000,
      greetingTimeout:   10000,
      socketTimeout:     30000,
      disableFileAccess: true,
      disableUrlAccess: true,
      tls: { rejectUnauthorized: true, minVersion: 'TLSv1.2' },
      ...(agent ? { socketOptions: { agent } } : {}),
    }
    if (acc.access_token) {
      transportOpts.auth = { type: 'OAuth2', user: acc.email, accessToken: acc.access_token }
    }

    const transporter = nodemailer.createTransport(transportOpts)
    try {
      await transporter.sendMail({
        from:    fromName ? `"${fromName}" <${acc.email}>` : acc.email,
        to:      recipientName ? `"${recipientName}" <${recipientEmail}>` : recipientEmail,
        subject,
        html:    bodyHtml || undefined,
        text:    bodyText || undefined,
        replyTo: replyTo || undefined,
      })
      transporter.close()
      return { success: true, account_used: acc.email, recipient_email: recipient.email }
    } catch (err) {
      transporter.close()
      if (lim) lim.rollback()
      const error = classifySmtpError(err, acc)
      const stopRetries = isSpamRejectionError(err)
      if (stopRetries) this.stopEvent.set()
      return { success: false, error, stop_retries: stopRetries, account_used: acc.email, recipient_email: recipient.email }
    }
  }

  async run() {
    const results = []
    const total   = this.recipients.length
    let   sent    = 0

    const maxWorkers = Math.min(this.config.max_threads || 4, 4, this.accounts.length || 1, total)
    const queue = [...this.recipients]

    const worker = async () => {
      while (queue.length > 0 && !this.stopEvent.isSet()) {
        while (this._paused && !this.stopEvent.isSet()) await sleep(300)
        if (this.stopEvent.isSet()) break

        const recipient = queue.shift()
        if (!recipient) break

        const acc = this._nextAccount()
        if (!acc) { results.push({ success: false, error: 'No available accounts', recipient_email: recipient.email }); sent++; continue }

        const result = await this._sendOne(acc, recipient)
        results.push(result)
        sent++

        if (this.on_progress) this.on_progress(sent, total, result)
        if (result.stop_retries) break

        const delay = randBetween(this.config.min_delay_ms || 1000, this.config.max_delay_ms || 3000)
        await sleep(delay)
      }
    }

    const workers = Array.from({ length: maxWorkers }, () => worker())
    await Promise.all(workers)

    if (this.on_finished) this.on_finished(results)
    return results
  }
}

module.exports = { testSmtpConnection, SendingEngine, getSmtpConfigForDomain, classifySmtpError }
