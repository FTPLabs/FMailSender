'use strict'
/**
 * FMailSender Proxy Manager — strict parsing, normalization and reachability checks.
 * Credentials are accepted only to establish a proxy connection and are never returned
 * in diagnostic messages.
 */
const net = require('net')
const url = require('url')

const HTTP_PORTS = new Set([80, 8080, 8088, 8118, 3128, 3129, 8443, 8888, 8889, 9999])
const SCHEMES = new Set(['http', 'https', 'socks4', 'socks5'])

function guessScheme(port) { return HTTP_PORTS.has(Number(port)) ? 'http' : 'socks5' }
function isPort(value) { const port = Number(value); return Number.isInteger(port) && port >= 1 && port <= 65535 }
function encodeCredential(value) { return encodeURIComponent(String(value ?? '')) }

/**
 * Normalise a supported proxy entry to scheme://[user:pass@]host:port.
 * Accepted input: URI, host:port, host:port:user:pass, user:pass:host:port,
 * host:port@user:pass, user:pass@host:port, and CSV/semicolon host,port,user,pass.
 */
function parseProxy(raw) {
  if (typeof raw !== 'string') return null
  raw = raw.trim().replace(/^\uFEFF/, '')
  if (!raw || raw.startsWith('#') || /[\r\n\0]/.test(raw)) return null

  let candidate = raw
  if (!raw.includes('://')) {
    // Common clipboard/export forms that unambiguously separate host and credentials.
    const atHostFirst = raw.match(/^([^:@\s]+):(\d{1,5})@([^:@\s]+):(.+)$/)
    const atUserFirst = raw.match(/^([^:@\s]+):([^@\s]+)@([^:@\s]+):(\d{1,5})$/)
    const separated = raw.split(/[;,]/).map(part => part.trim())
    if (atHostFirst && isPort(atHostFirst[2])) {
      const [, host, port, username, password] = atHostFirst
      candidate = `${guessScheme(port)}://${encodeCredential(username)}:${encodeCredential(password)}@${host}:${port}`
    } else if (atUserFirst && isPort(atUserFirst[4])) {
      const [, username, password, host, port] = atUserFirst
      candidate = `${guessScheme(port)}://${encodeCredential(username)}:${encodeCredential(password)}@${host}:${port}`
    } else if (separated.length === 2 && isPort(separated[1])) {
      candidate = `${guessScheme(separated[1])}://${separated[0]}:${separated[1]}`
    } else if (separated.length === 4 && isPort(separated[1])) {
      const [host, port, username, password] = separated
      candidate = `${guessScheme(port)}://${encodeCredential(username)}:${encodeCredential(password)}@${host}:${port}`
    } else {
      const parts = raw.split(':')
      if (parts.length === 2 && isPort(parts[1])) {
        candidate = `${guessScheme(parts[1])}://${parts[0]}:${parts[1]}`
      } else if (parts.length === 4 && isPort(parts[1])) {
        const [host, port, username, password] = parts
        candidate = `${guessScheme(port)}://${encodeCredential(username)}:${encodeCredential(password)}@${host}:${port}`
      } else if (parts.length === 4 && isPort(parts[3])) {
        const [username, password, host, port] = parts
        candidate = `${guessScheme(port)}://${encodeCredential(username)}:${encodeCredential(password)}@${host}:${port}`
      } else return null
    }
  }

  try {
    const parsed = new url.URL(candidate)
    const scheme = parsed.protocol.slice(0, -1).toLowerCase()
    const port = Number(parsed.port)
    if (!SCHEMES.has(scheme) || !parsed.hostname || !isPort(port)) return null
    parsed.protocol = `${scheme}:`
    parsed.hash = ''
    parsed.search = ''
    parsed.pathname = ''
    return parsed.toString()
  } catch {
    return null
  }
}

function normalizeProxyList(rawList) {
  const unique = new Set()
  let invalid = 0, duplicates = 0, ignored = 0
  for (const raw of Array.isArray(rawList) ? rawList : []) {
    const input = String(raw ?? '').trim()
    if (!input || input.startsWith('#')) { ignored++; continue }
    const parsed = parseProxy(input)
    if (!parsed) { invalid++; continue }
    if (unique.has(parsed)) { duplicates++; continue }
    unique.add(parsed)
  }
  return { proxies: [...unique], invalid, duplicates, ignored }
}

function publicProxyLabel(proxyUrl) {
  try {
    const parsed = new url.URL(proxyUrl)
    return `${parsed.protocol}//${parsed.hostname}:${parsed.port}`
  } catch { return 'proxy' }
}

/** Check proxy connectivity via raw socket; no SMTP transaction is attempted. */
function checkProxy(proxyUrl, timeout = 7000) {
  return new Promise(resolve => {
    let parsed
    try { parsed = new url.URL(proxyUrl) }
    catch { return resolve({ ok: false, error: 'Некорректный формат прокси.', ping_ms: 0 }) }

    const scheme = parsed.protocol.replace(':', '')
    const pxHost = parsed.hostname
    const pxPort = parseInt(parsed.port || '1080', 10)
    const username = decodeURIComponent(parsed.username || '')
    const password = decodeURIComponent(parsed.password || '')
    const started = Date.now()
    let settled = false
    const done = value => { if (!settled) { settled = true; resolve(value) } }
    const sock = new net.Socket()
    sock.setTimeout(timeout)
    sock.on('error', () => done({ ok: false, error: 'Соединение с прокси не установлено.', ping_ms: 0 }))
    sock.on('timeout', () => { sock.destroy(); done({ ok: false, error: 'Тайм-аут подключения к прокси.', ping_ms: 0 }) })

    sock.connect(pxPort, pxHost, () => {
      if (scheme !== 'socks5') {
        sock.destroy()
        return done({ ok: true, error: '', ping_ms: Date.now() - started })
      }
      const auth = username ? Buffer.from([5, 2, 0, 2]) : Buffer.from([5, 1, 0])
      sock.write(auth)
      sock.once('data', response => {
        if (response[0] !== 5) { sock.destroy(); return done({ ok: false, error: 'Ошибка SOCKS5-рукопожатия.', ping_ms: 0 }) }
        if (response[1] === 2 && username) {
          const user = Buffer.from(username)
          const pass = Buffer.from(password)
          if (user.length > 255 || pass.length > 255) { sock.destroy(); return done({ ok: false, error: 'Учётные данные прокси слишком длинные.', ping_ms: 0 }) }
          sock.write(Buffer.concat([Buffer.from([1, user.length]), user, Buffer.from([pass.length]), pass]))
          sock.once('data', authResponse => {
            sock.destroy()
            done(authResponse[1] === 0
              ? { ok: true, error: '', ping_ms: Date.now() - started }
              : { ok: false, error: 'Аутентификация прокси не пройдена.', ping_ms: 0 })
          })
        } else {
          sock.destroy()
          done({ ok: true, error: '', ping_ms: Date.now() - started })
        }
      })
    })
  })
}

async function validateProxy(proxyUrl) {
  const normalized = parseProxy(proxyUrl)
  if (!normalized) return { id: '', proxy: publicProxyLabel(String(proxyUrl || '')), ok: false, smtp_ok: false, error: 'Некорректный формат прокси.', ping_ms: 0 }
  const { ok, error, ping_ms } = await checkProxy(normalized)
  return { id: normalized, proxy: publicProxyLabel(normalized), ok, smtp_ok: false, error, ping_ms, note: 'Проверено только соединение с прокси; SMTP не выполнялся.' }
}

class ProxyManager {
  constructor(rawList, mode = 'round_robin') {
    this._mode = mode
    this._index = 0
    this._proxies = normalizeProxyList(rawList).proxies
  }
  get proxies() { return [...this._proxies] }
  next() {
    if (!this._proxies.length) return null
    if (this._mode === 'random') return this._proxies[Math.floor(Math.random() * this._proxies.length)]
    return this._proxies[this._index++ % this._proxies.length]
  }
  distribute(accounts, startIndex = 0) {
    if (!this._proxies.length) return
    accounts.forEach((account, index) => {
      account.proxy = this._proxies[(startIndex + index) % this._proxies.length]
      account.proxy_list = [...this._proxies]
    })
  }
}

module.exports = { parseProxy, normalizeProxyList, publicProxyLabel, checkProxy, validateProxy, ProxyManager }
