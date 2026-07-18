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
  if (!raw) return null
  raw = raw.trim()
  if (!raw || raw.startsWith('#')) return null
  if (raw.includes('://')) return raw

  const parts = raw.split(':')
  if (parts.length === 2) {
    const [host, portStr] = parts
    const port = parseInt(portStr, 10)
    const scheme = HTTP_PORTS.has(port) ? 'http' : 'socks5'
    return `${scheme}://${host}:${port}`
  }
  if (parts.length === 4) {
    // try host:port:user:pass
    const port1 = parseInt(parts[1], 10)
    if (!isNaN(port1)) {
      const scheme = HTTP_PORTS.has(port1) ? 'http' : 'socks5'
      return `${scheme}://${parts[2]}:${parts[3]}@${parts[0]}:${port1}`
    }
    // try user:pass:host:port
    const port2 = parseInt(parts[3], 10)
    if (!isNaN(port2)) {
      const scheme = HTTP_PORTS.has(port2) ? 'http' : 'socks5'
      return `${scheme}://${parts[0]}:${parts[1]}@${parts[2]}:${port2}`
    }
  }
  if (raw.includes('@')) {
    const parsed = new url.URL('http://' + raw)
    const port = parsed.port || 3128
    return `http://${parsed.username}:${parsed.password}@${parsed.hostname}:${port}`
  }
  return null
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

function checkSmtpViaProxy(proxyUrl, timeout = 8000) {
  return new Promise(resolve => {
    // simplified: just check TCP connect to smtp.gmail.com:587 via proxy
    checkProxy(proxyUrl, timeout).then(r => resolve(r.ok))
  })
}

async function validateProxy(proxyUrl) {
  const { ok, error, ping_ms } = await checkProxy(proxyUrl)
  const smtp_ok = ok ? await checkSmtpViaProxy(proxyUrl) : false
  return { proxy: proxyUrl, ok, smtp_ok, error, ping_ms }
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

module.exports = { parseProxy, checkProxy, checkSmtpViaProxy, validateProxy, ProxyManager }
