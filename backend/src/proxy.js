'use strict'
/**
 * FMailSender Proxy Manager — Node.js port of core/proxy.py
 */
const net = require('net')
const url = require('url')

const HTTP_PORTS = new Set([80, 8080, 8088, 8118, 3128, 3129, 8443, 8888, 8889, 9999])

/**
 * Normalise proxy string → scheme://[user:pass@]host:port
 */
function parseProxy(raw) {
  if (typeof raw !== 'string') return null
  raw = raw.trim()
  if (!raw || raw.startsWith('#') || /[\r\n\0]/.test(raw)) return null

  let candidate = raw
  if (!raw.includes('://')) {
    const parts = raw.split(':')
    if (parts.length === 2) {
      const [host, portStr] = parts
      const port = Number(portStr)
      if (!Number.isInteger(port)) return null
      candidate = `${HTTP_PORTS.has(port) ? 'http' : 'socks5'}://${host}:${port}`
    } else if (parts.length === 4) {
      const portFirst = Number(parts[1])
      const portLast = Number(parts[3])
      if (Number.isInteger(portFirst)) {
        candidate = `${HTTP_PORTS.has(portFirst) ? 'http' : 'socks5'}://${encodeURIComponent(parts[2])}:${encodeURIComponent(parts[3])}@${parts[0]}:${portFirst}`
      } else if (Number.isInteger(portLast)) {
        candidate = `${HTTP_PORTS.has(portLast) ? 'http' : 'socks5'}://${encodeURIComponent(parts[0])}:${encodeURIComponent(parts[1])}@${parts[2]}:${portLast}`
      } else return null
    } else return null
  }

  try {
    const parsed = new url.URL(candidate)
    const scheme = parsed.protocol.slice(0, -1).toLowerCase()
    const port = Number(parsed.port)
    if (!['http', 'https', 'socks4', 'socks5'].includes(scheme) || !parsed.hostname || !Number.isInteger(port) || port < 1 || port > 65535) return null
    return parsed.toString()
  } catch {
    return null
  }
}

/**
 * Check proxy connectivity via raw socket (no external deps).
 * Returns {ok, error, ping_ms}
 */
function checkProxy(proxyUrl, timeout = 7000) {
  return new Promise(resolve => {
    const TEST_HOST = 'httpbin.org', TEST_PORT = 80
    let parsed
    try {
      parsed = new url.URL(proxyUrl.includes('://') ? proxyUrl : 'socks5://' + proxyUrl)
    } catch (e) {
      return resolve({ ok: false, error: 'Invalid proxy URL', ping_ms: 0 })
    }

    const scheme  = parsed.protocol.replace(':', '')
    const pxHost  = parsed.hostname
    const pxPort  = parseInt(parsed.port || '1080', 10)
    const uname   = parsed.username || ''
    const upass   = parsed.password || ''
    const t0 = Date.now()

    const sock = new net.Socket()
    sock.setTimeout(timeout)

    sock.on('error', err => resolve({ ok: false, error: err.message, ping_ms: 0 }))
    sock.on('timeout', () => { sock.destroy(); resolve({ ok: false, error: 'timeout', ping_ms: 0 }) })

    sock.connect(pxPort, pxHost, () => {
      if (scheme === 'socks5') {
        const auth = uname ? Buffer.from([5, 2, 0, 2]) : Buffer.from([5, 1, 0])
        sock.write(auth)
        sock.once('data', resp => {
          if (resp[0] !== 5) { sock.destroy(); return resolve({ ok: false, error: 'SOCKS5 handshake failed', ping_ms: 0 }) }
          if (resp[1] === 2 && uname) {
            const creds = Buffer.concat([
              Buffer.from([1, uname.length]), Buffer.from(uname),
              Buffer.from([upass.length]), Buffer.from(upass)
            ])
            sock.write(creds)
            sock.once('data', ar => {
              sock.destroy()
              if (ar[1] !== 0) return resolve({ ok: false, error: 'SOCKS5 auth failed', ping_ms: 0 })
              resolve({ ok: true, error: '', ping_ms: Date.now() - t0 })
            })
          } else {
            sock.destroy()
            resolve({ ok: true, error: '', ping_ms: Date.now() - t0 })
          }
        })
      } else {
        // HTTP CONNECT test
        sock.destroy()
        resolve({ ok: true, error: '', ping_ms: Date.now() - t0 })
      }
    })
  })
}

async function validateProxy(proxyUrl) {
  const normalized = parseProxy(proxyUrl)
  if (!normalized) {
    return { proxy: String(proxyUrl || ''), ok: false, smtp_ok: false, error: 'Некорректный формат proxy URL', ping_ms: 0 }
  }
  const { ok, error, ping_ms } = await checkProxy(normalized)
  // This is deliberately proxy reachability/authentication only. It does not
  // perform SMTP traffic and never claims delivery readiness.
  return { proxy: normalized, ok, smtp_ok: false, error, ping_ms, note: 'Проверено соединение proxy; SMTP не выполнялся.' }
}

class ProxyManager {
  constructor(rawList, mode = 'round_robin') {
    this._mode = mode
    this._index = 0
    this._proxies = rawList.map(parseProxy).filter(Boolean)
  }

  get proxies() { return [...this._proxies] }

  next() {
    if (!this._proxies.length) return null
    if (this._mode === 'random') {
      return this._proxies[Math.floor(Math.random() * this._proxies.length)]
    }
    return this._proxies[this._index++ % this._proxies.length]
  }

  distribute(accounts, startIndex = 0) {
    if (!this._proxies.length) return
    accounts.forEach((acc, i) => {
      acc.proxy      = this._proxies[(startIndex + i) % this._proxies.length]
      acc.proxy_list = [...this._proxies]
    })
  }
}

module.exports = { parseProxy, checkProxy, validateProxy, ProxyManager }
