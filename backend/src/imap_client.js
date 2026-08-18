'use strict'
const tls = require('tls')

function quote(value) {
  return `"${String(value ?? '').replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/[\r\n]/g, '')}"`
}

function testImapLogin({ host, port = 993, secure = true, email, password, timeout = 15000 }) {
  if (!host || !email || !password) return Promise.resolve([false, 'IMAP: недостаточно данных для проверки.'])
  if (!secure) return Promise.resolve([false, 'IMAP: для этого preset требуется защищённый TLS-сеанс.'])
  return new Promise(resolve => {
    let settled = false
    let buffer = ''
    let tag = 'a' + Math.random().toString(36).slice(2, 8)
    const finish = (ok, message) => {
      if (settled) return
      settled = true
      try { socket.destroy() } catch {}
      resolve([ok, message])
    }
    const socket = tls.connect({ host, port: Number(port), servername: host, timeout, rejectUnauthorized: true })
    const timer = setTimeout(() => finish(false, 'IMAP: превышено время ожидания сервера.'), timeout + 1000)
    socket.setEncoding('utf8')
    socket.on('secureConnect', () => {
      socket.write(`${tag} LOGIN ${quote(email)} ${quote(password)}\r\n`)
    })
    socket.on('data', chunk => {
      buffer += chunk
      if (!buffer.includes(`${tag} `)) return
      clearTimeout(timer)
      const line = buffer.split(/\r?\n/).find(x => x.startsWith(`${tag} `)) || buffer
      const upper = line.toUpperCase()
      if (/\bOK\b/.test(upper)) finish(true, 'IMAP: авторизация успешна.')
      else if (/AUTHENTICATIONFAILED|AUTHENTICATION ERROR|LOGIN FAILED|INVALID CREDENTIAL/.test(upper)) finish(false, 'IMAP: авторизация не пройдена. Проверьте адрес и пароль приложения.')
      else finish(false, 'IMAP: сервер отклонил авторизацию.')
    })
    socket.on('timeout', () => { clearTimeout(timer); finish(false, 'IMAP: превышено время ожидания сервера.') })
    socket.on('error', err => {
      clearTimeout(timer)
      const raw = String(err?.message || err)
      if (/certificate|tls|ssl/i.test(raw)) finish(false, 'IMAP: ошибка TLS/сертификата. Проверьте host и порт.')
      else if (/ENOTFOUND|getaddrinfo/i.test(raw)) finish(false, 'IMAP: host не найден.')
      else finish(false, `IMAP: ${raw.slice(0, 180)}`)
    })
    socket.on('close', () => { clearTimeout(timer); if (!settled) finish(false, 'IMAP: сервер закрыл соединение до завершения авторизации.') })
  })
}

module.exports = { testImapLogin }
