'use strict'
/**
 * FMailSender Storage — Node.js backend
 * AES-256-GCM encryption for passwords/tokens.
 * Data: %APPDATA%/FMailSender/ (Windows) or ~/FMailSender/ (other)
 */
const fs   = require('fs')
const path = require('path')
const crypto = require('crypto')

// ── Data directory ────────────────────────────────────────────────────────────
function getDataDir() {
  if (process.env.FMAIL_DATA_DIR) return process.env.FMAIL_DATA_DIR
  const base = process.env.APPDATA || require('os').homedir()
  return path.join(base, 'FMailSender')
}

const DATA_DIR      = getDataDir()
const KEY_FILE      = path.join(DATA_DIR, '.aes_key')
const ACCOUNTS_FILE = path.join(DATA_DIR, 'accounts.json')
const PROXIES_FILE  = path.join(DATA_DIR, 'global_proxies.json')
const RECIPIENTS_FILE = path.join(DATA_DIR, 'recipients.json')
const CAMPAIGN_FILE = path.join(DATA_DIR, 'campaign.json')
const LICENSE_FILE  = path.join(DATA_DIR, 'license.json')

fs.mkdirSync(DATA_DIR, { recursive: true })

// ── Encryption (AES-256-GCM) ──────────────────────────────────────────────────
let _keyCache = null

function _getKey() {
  if (_keyCache) return _keyCache
  if (fs.existsSync(KEY_FILE)) {
    _keyCache = fs.readFileSync(KEY_FILE)
    return _keyCache
  }
  const key = crypto.randomBytes(32)
  fs.writeFileSync(KEY_FILE, key, { mode: 0o600 })
  _keyCache = key
  return key
}

function encrypt(plaintext) {
  if (!plaintext) return plaintext
  try {
    const key = _getKey()
    const iv  = crypto.randomBytes(12)
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv)
    const enc  = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()])
    const tag  = cipher.getAuthTag()
    return Buffer.concat([iv, tag, enc]).toString('base64')
  } catch (e) {
    return plaintext
  }
}

function decrypt(ciphertext) {
  if (!ciphertext) return ciphertext
  try {
    const buf  = Buffer.from(ciphertext, 'base64')
    const key  = _getKey()
    const iv   = buf.slice(0, 12)
    const tag  = buf.slice(12, 28)
    const enc  = buf.slice(28)
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv)
    decipher.setAuthTag(tag)
    return Buffer.concat([decipher.update(enc), decipher.final()]).toString('utf8')
  } catch (e) {
    // possibly plain text (legacy / migration)
    return ciphertext
  }
}

// ── Safe JSON read/write ──────────────────────────────────────────────────────
function readJson(file, fallback) {
  try {
    if (!fs.existsSync(file)) return fallback
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch { return fallback }
}

function writeJson(file, data) {
  const tmp = file + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8')
  fs.renameSync(tmp, file)
}

// ── Accounts ──────────────────────────────────────────────────────────────────
function saveAccounts(accounts) {
  const data = accounts.map(a => {
    const d = { ...a }
    if (d.password)      d.password      = encrypt(d.password)
    if (d.access_token)  d.access_token  = encrypt(d.access_token)
    if (d.refresh_token) d.refresh_token = encrypt(d.refresh_token)
    return d
  })
  writeJson(ACCOUNTS_FILE, data)
}

function loadAccounts() {
  const data = readJson(ACCOUNTS_FILE, [])
  return data.map(d => {
    const a = { ...d }
    a.password      = decrypt(a.password || '')
    if (a.access_token)  a.access_token  = decrypt(a.access_token)
    if (a.refresh_token) a.refresh_token = decrypt(a.refresh_token)
    return a
  })
}

// ── Proxies ───────────────────────────────────────────────────────────────────
let _proxyCache = null

function saveProxies(proxies) {
  _proxyCache = [...proxies]
  writeJson(PROXIES_FILE, proxies)
}

function loadProxies() {
  if (_proxyCache) return [..._proxyCache]
  const data = readJson(PROXIES_FILE, [])
  _proxyCache = data.filter(Boolean)
  return [..._proxyCache]
}

// ── Recipients ────────────────────────────────────────────────────────────────
function saveRecipients(recipients) { writeJson(RECIPIENTS_FILE, recipients) }
function loadRecipients()           { return readJson(RECIPIENTS_FILE, []) }

// ── Campaign config ───────────────────────────────────────────────────────────
const CAMPAIGN_DEFAULTS = {
  subject: '', body_html: '', body_text: '',
  from_name: '', reply_to: '',
  delay_min: 1.0, delay_max: 3.0,
  daily_limit_per_account: 500
}

function saveCampaign(cfg) { writeJson(CAMPAIGN_FILE, cfg) }
function loadCampaign()    { return { ...CAMPAIGN_DEFAULTS, ...readJson(CAMPAIGN_FILE, {}) } }

// ── License ───────────────────────────────────────────────────────────────────
function saveLicenseCache(data) { writeJson(LICENSE_FILE, data) }
function loadLicenseCache()     { return readJson(LICENSE_FILE, null) }

module.exports = {
  DATA_DIR, LICENSE_FILE,
  encrypt, decrypt,
  saveAccounts, loadAccounts,
  saveProxies,  loadProxies,
  saveRecipients, loadRecipients,
  saveCampaign,   loadCampaign,
  saveLicenseCache, loadLicenseCache,
}
