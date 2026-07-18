'use strict'
// SMTP presets — ported from core/sender.py + core/smtp_configs_extra.py
// Key: lowercase domain  Value: {host, port, secure (SSL), requireTLS (STARTTLS)}

const SMTP_CONFIGS = {
  // Google
  'gmail.com':       { host: 'smtp.gmail.com',        port: 465, secure: true,  requireTLS: false },
  'googlemail.com':  { host: 'smtp.gmail.com',        port: 465, secure: true,  requireTLS: false },
  // Microsoft / Outlook family
  'outlook.com':     { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.de':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.fr':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.es':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.it':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.co.uk':   { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'outlook.jp':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.com':     { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.co.uk':   { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.de':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.fr':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.es':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.it':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'hotmail.ru':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'live.com':        { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'live.co.uk':      { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'live.de':         { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'live.fr':         { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'live.ru':         { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'msn.com':         { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  'windowslive.com': { host: 'smtp.office365.com',    port: 587, secure: false, requireTLS: true },
  // Yahoo family
  'yahoo.com':       { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.co.uk':     { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.de':        { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.fr':        { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.es':        { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.it':        { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'yahoo.co.jp':     { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'ymail.com':       { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  'rocketmail.com':  { host: 'smtp.mail.yahoo.com',   port: 465, secure: true,  requireTLS: false },
  // iCloud / Apple
  'icloud.com':      { host: 'smtp.mail.me.com',      port: 587, secure: false, requireTLS: true },
  'me.com':          { host: 'smtp.mail.me.com',      port: 587, secure: false, requireTLS: true },
  'mac.com':         { host: 'smtp.mail.me.com',      port: 587, secure: false, requireTLS: true },
  // GMX
  'gmx.com':         { host: 'mail.gmx.com',          port: 465, secure: true,  requireTLS: false },
  'gmx.net':         { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.de':          { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.at':          { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.ch':          { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.fr':          { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.es':          { host: 'mail.gmx.net',          port: 587, secure: false, requireTLS: true },
  'gmx.us':          { host: 'smtp.gmx.com',          port: 587, secure: false, requireTLS: true },
  // WEB.DE
  'web.de':          { host: 'smtp.web.de',            port: 587, secure: false, requireTLS: true },
  // Fastmail
  'fastmail.com':    { host: 'smtp.fastmail.com',      port: 465, secure: true,  requireTLS: false },
  'fastmail.fm':     { host: 'smtp.fastmail.com',      port: 465, secure: true,  requireTLS: false },
  'fastmail.net':    { host: 'smtp.fastmail.com',      port: 465, secure: true,  requireTLS: false },
  // Asian
  'qq.com':          { host: 'smtp.qq.com',            port: 465, secure: true,  requireTLS: false },
  '163.com':         { host: 'smtp.163.com',           port: 465, secure: true,  requireTLS: false },
  '126.com':         { host: 'smtp.126.com',           port: 465, secure: true,  requireTLS: false },
  'sina.com':        { host: 'smtp.sina.com',          port: 465, secure: true,  requireTLS: false },
  // Mail.ru
  'mail.ru':         { host: 'smtp.mail.ru',           port: 465, secure: true,  requireTLS: false },
  'inbox.ru':        { host: 'smtp.mail.ru',           port: 465, secure: true,  requireTLS: false },
  'list.ru':         { host: 'smtp.mail.ru',           port: 465, secure: true,  requireTLS: false },
  'bk.ru':           { host: 'smtp.mail.ru',           port: 465, secure: true,  requireTLS: false },
  // Yandex
  'yandex.ru':       { host: 'smtp.yandex.ru',         port: 465, secure: true,  requireTLS: false },
  'yandex.com':      { host: 'smtp.yandex.com',        port: 465, secure: true,  requireTLS: false },
  'ya.ru':           { host: 'smtp.yandex.ru',         port: 465, secure: true,  requireTLS: false },
  // AOL
  'aol.com':         { host: 'smtp.aol.com',           port: 465, secure: true,  requireTLS: false },
  'aim.com':         { host: 'smtp.aol.com',           port: 465, secure: true,  requireTLS: false },
  // Zoho
  'zoho.com':        { host: 'smtp.zoho.com',          port: 465, secure: true,  requireTLS: false },
  'zohomail.com':    { host: 'smtp.zoho.com',          port: 465, secure: true,  requireTLS: false },
  // Transactional
  'sendgrid':        { host: 'smtp.sendgrid.net',      port: 587, secure: false, requireTLS: true },
  'mailgun':         { host: 'smtp.mailgun.org',       port: 587, secure: false, requireTLS: true },
  'postmark':        { host: 'smtp.postmarkapp.com',   port: 587, secure: false, requireTLS: true },
  'brevo':           { host: 'smtp-relay.brevo.com',   port: 587, secure: false, requireTLS: true },
  'sendinblue':      { host: 'smtp-relay.brevo.com',   port: 587, secure: false, requireTLS: true },
  'mailjet':         { host: 'in-v3.mailjet.com',      port: 587, secure: false, requireTLS: true },
}

/**
 * Get SMTP config for a domain. Falls back to MX-based lookup if not in table.
 * Returns null if unknown.
 */
function getSmtpConfigForDomain(domain) {
  const d = (domain || '').toLowerCase().trim()
  if (SMTP_CONFIGS[d]) return { ...SMTP_CONFIGS[d] }

  // Pattern matching for common families
  if (d.startsWith('outlook.') || d.startsWith('hotmail.') || d.startsWith('live.')) {
    return { host: 'smtp.office365.com', port: 587, secure: false, requireTLS: true }
  }
  if (d.startsWith('yahoo.') || d.includes('ymail.')) {
    return { host: 'smtp.mail.yahoo.com', port: 465, secure: true, requireTLS: false }
  }
  if (d.endsWith('.mail.ru') || d.endsWith('.ru') && d.includes('mail')) {
    return { host: 'smtp.mail.ru', port: 465, secure: true, requireTLS: false }
  }
  return null
}

module.exports = { SMTP_CONFIGS, getSmtpConfigForDomain }
