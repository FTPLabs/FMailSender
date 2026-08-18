'use strict'
/**
 * FMailSender License — Node.js port of core/license.py
 * HWID: Windows Registry MachineGuid → PowerShell fallback → MAC
 * Online validation: POST https://fmail.shop/v1/verify
 */
const crypto  = require('crypto')
const { execSync } = require('child_process')
const axios   = require('axios')
const storage = require('./storage')

const LICENSE_SERVER   = 'https://fmail.shop'
const VALIDATE_URL     = LICENSE_SERVER + '/v1/verify'
const ACTIVATE_URL     = LICENSE_SERVER + '/v1/activate'
const CACHE_TTL_MS     = 24 * 3600 * 1000
const RECHECK_INTERVAL = 3600 * 1000


const IPV4_OR_PORT_RE = /\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?::\d{1,5})?\b/g
const URL_RE = /\b(?:https?|wss?):\/\/[^\s<>()]+/gi
const IPV6_RE = /(?:^|[^0-9a-f])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?=$|[^0-9a-f])/gi

/**
 * Error text shown outside the licensing module. Raw transport errors often
 * embed a resolved IP, URL or proxy path; none of those are user-facing data.
 */
function publicLicenseError(input, fallback = 'Сервер лицензий временно недоступен. Проверьте подключение и повторите попытку.') {
  const raw = String(input?.message || input || '').trim()
  const code = String(input?.code || '').toUpperCase()
  const lower = raw.toLowerCase()
  const transportFailure = [
    'ECONNREFUSED', 'ECONNRESET', 'ECONNABORTED', 'EHOSTUNREACH',
    'ENETUNREACH', 'ENOTFOUND', 'ETIMEDOUT', 'ESOCKET', 'CERT_HAS_EXPIRED',
  ].includes(code) || /\b(connect|socket|network|timeout|timed out|certificate|tls|ssl|getaddrinfo|econnrefused)\b/.test(lower)
  if (transportFailure) return fallback

  const sanitized = raw.replace(URL_RE, '').replace(IPV4_OR_PORT_RE, '').replace(IPV6_RE, ' ').replace(/\s{2,}/g, ' ').trim()
  if (!sanitized || sanitized !== raw || sanitized.length > 220) return fallback
  return sanitized
}

let _hwidCache = null

// ── HWID ──────────────────────────────────────────────────────────────────────
function _getHwid() {
  if (_hwidCache) return _hwidCache

  let raw = null

  // 1. Windows Registry MachineGuid (fastest, most stable)
  if (process.platform === 'win32') {
    try {
      const out = execSync(
        'reg query "HKLM\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid',
        { timeout: 3000, windowsHide: true }
      ).toString()
      const m = out.match(/MachineGuid\s+REG_SZ\s+(\S+)/)
      if (m && m[1] && m[1].length > 8) raw = `mg:${m[1]}`
    } catch {}
  }

  // 2. PowerShell Win32_ComputerSystemProduct UUID
  if (!raw && process.platform === 'win32') {
    try {
      const out = execSync(
        'powershell -NoProfile -NonInteractive -Command "(Get-WmiObject Win32_ComputerSystemProduct).UUID"',
        { timeout: 8000, windowsHide: true }
      ).toString().trim()
      if (out && !out.toUpperCase().includes('FFFFFFFF') && out.length > 8) {
        raw = `mb:${out}`
      }
    } catch {}
  }

  // 3. node-machine-id fallback (cross-platform)
  if (!raw) {
    try {
      const { machineIdSync } = require('node-machine-id')
      raw = `mid:${machineIdSync({ original: true })}`
    } catch {}
  }

  // 4. MAC address fallback
  if (!raw) {
    const { networkInterfaces } = require('os')
    const ifaces = networkInterfaces()
    for (const iface of Object.values(ifaces)) {
      for (const i of iface) {
        if (!i.internal && i.mac && i.mac !== '00:00:00:00:00:00') {
          raw = `mac:${i.mac}`
          break
        }
      }
      if (raw) break
    }
  }

  if (!raw) raw = 'fallback'
  _hwidCache = crypto.createHash('sha256').update(raw).digest('hex').slice(0, 32)
  return _hwidCache
}

function _isValidKeyFormat(key) {
  const k = (key || '').toUpperCase().trim()
  return k.startsWith('FMSND-') || k.startsWith('FM-')
}

function _decodeJwtPayload(token) {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return {}
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(Buffer.from(b64, 'base64').toString('utf8'))
  } catch { return {} }
}

// ── Cache ─────────────────────────────────────────────────────────────────────
function getCachedLicenseStatus() {
  const hwid = _hwidCache || 'pending'
  const cached = storage.loadLicenseCache()
  if (!cached || !cached.key) {
    return { valid: false, hwid, message: 'Лицензия не активирована', requires_activation: true, from_cache: true }
  }
  return {
    valid: Boolean(cached.valid),
    plan: cached.plan,
    expires_at: cached.expires_at,
    hwid,
    key: cached.key.slice(0, 12) + '****',
    message: cached.message || '',
    from_cache: true,
  }
}

async function _validateOnline(key, hwid, timeout = 10000) {
  try {
    const resp = await axios.post(VALIDATE_URL, { key, hwid }, { timeout })
    return resp.data
  } catch (err) {
    if (err.response) {
      const rawDetail = err.response.data?.detail || err.response.data?.message || `HTTP ${err.response.status}`
      const detail = publicLicenseError(rawDetail, `Ошибка лицензии (HTTP ${err.response.status})`)
      if (err.response.status === 403) {
        const dl = detail.toLowerCase()
        if (dl.includes('hwid') || dl.includes('mismatch') || dl.includes('device')) {
          return { valid: false, error: detail, message: 'Этот ключ уже привязан к другому компьютеру. Обратитесь в поддержку.', hwid_mismatch: true }
        }
        return { valid: false, error: detail, message: `Лицензия недействительна: ${detail}` }
      }
      if (err.response.status === 404) {
        return { valid: false, error: detail, message: 'Лицензионный ключ не найден на сервере.' }
      }
      return { valid: false, error: detail }
    }
    return { valid: false, error: publicLicenseError(err), offline: true }
  }
}

async function validateOnStartup() {
  const hwid   = _getHwid()
  const cached = storage.loadLicenseCache()
  if (!cached || !cached.key) {
    return { valid: false, hwid, message: 'Лицензия не активирована', requires_activation: true }
  }
  const result = await _validateOnline(cached.key, hwid)
  if (!result.offline) {
    const isValid = Boolean(result.valid)
    const updated = {
      ...cached,
      valid: isValid,
      plan: result.plan || cached.plan,
      expires_at: result.expires_at || cached.expires_at,
      message: result.message || result.error || '',
      validated_at: Date.now(),
    }
    storage.saveLicenseCache(updated)
    return { valid: isValid, plan: updated.plan, expires_at: updated.expires_at, hwid, key: cached.key.slice(0, 12) + '****', message: updated.message, hwid_mismatch: result.hwid_mismatch || false }
  }
  return { valid: false, hwid, message: 'Нет связи с сервером лицензий. Проверьте подключение.', offline: true }
}

async function activateLicenseKey(key) {
  if (!_isValidKeyFormat(key)) throw new Error('Неверный формат ключа. Ожидается: FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX')
  const hwid = _getHwid()
  let result
  try {
    const resp = await axios.post(ACTIVATE_URL, { key, hwid }, { timeout: 15000 })
    result = resp.data
  } catch (err) {
    if (err.response) {
      const rawDetail = err.response.data?.detail || err.response.data?.message || `HTTP ${err.response.status}`
      const detail = publicLicenseError(rawDetail, `Ошибка активации (HTTP ${err.response.status})`)
      const dl = (detail || '').toLowerCase()
      if (dl.includes('hwid') || dl.includes('mismatch') || dl.includes('device')) {
        throw new Error('Этот ключ уже привязан к другому компьютеру. Обратитесь в поддержку.')
      }
      throw new Error(detail || 'Ключ недействителен')
    }
    throw new Error(publicLicenseError(err))
  }

  if (result.valid === false) {
    throw new Error(publicLicenseError(result.detail || result.error || result.message, 'Ключ недействителен'))
  }

  let { plan, expires_at } = result
  if (!plan || !expires_at) {
    const payload = _decodeJwtPayload(result.token || '')
    if (!plan) plan = payload.plan || 'unknown'
    if (!expires_at && payload.exp) {
      expires_at = new Date(payload.exp * 1000).toISOString()
    }
  }

  const cacheData = {
    key, valid: true, plan: plan || 'unknown', expires_at, hwid,
    message: result.message || 'Активировано',
    activated_at: Date.now(), validated_at: Date.now(),
  }
  storage.saveLicenseCache(cacheData)
  return { success: true, plan: cacheData.plan, expires_at: cacheData.expires_at, message: result.message || 'Лицензия успешно активирована' }
}

async function requestAiTemplate(input) {
  const cached = storage.loadLicenseCache()
  if (!cached?.key) throw new Error('Сначала активируйте лицензию.')
  const hwid = _getHwid()
  try {
    const resp = await axios.post(LICENSE_SERVER + '/v1/ai/templates', {
      key: cached.key, hwid, ...input,
    }, { timeout: 60_000 })
    return resp.data
  } catch (err) {
    if (err.response) {
      const detail = err.response.data?.detail || err.response.data?.message || `HTTP ${err.response.status}`
      throw new Error(detail)
    }
    throw new Error('Не удалось связаться с AI-сервисом. Проверьте подключение.')
  }
}

// ── Runtime state (mirrors server.js licenseOk) ───────────────────────────────
let _licenseOk = false
let _bgChecking = false

function setLicenseOk(v) { _licenseOk = v }
function getLicenseOk()  { return _licenseOk }
function setBgChecking(v) { _bgChecking = v }
function isBgChecking()   { return _bgChecking }

// ── Periodic re-check ─────────────────────────────────────────────────────────
let _recheckTimer = null

function startPeriodicCheck(onRevoke) {
  _recheckTimer = setInterval(async () => {
    try {
      const r = await validateOnStartup()
      setLicenseOk(Boolean(r.valid))
      if (!r.valid && onRevoke) onRevoke()
    } catch {}
  }, RECHECK_INTERVAL)
  if (_recheckTimer.unref) _recheckTimer.unref()
}

function stopPeriodicCheck() {
  if (_recheckTimer) { clearInterval(_recheckTimer); _recheckTimer = null }
}

module.exports = {
  _getHwid, _isValidKeyFormat,
  getCachedLicenseStatus, validateOnStartup, activateLicenseKey, requestAiTemplate, publicLicenseError,
  setLicenseOk, getLicenseOk, setBgChecking, isBgChecking,
  startPeriodicCheck, stopPeriodicCheck,
}
