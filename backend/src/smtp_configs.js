'use strict'

/**
 * Central SMTP preset catalogue.
 * The backend is the only source of truth; UI receives a public normalized copy
 * through /api/accounts/smtp-preset and never keeps a second provider table.
 */
const IMAP_BY_PROVIDER = Object.freeze({
  'Gmail': 'imap.gmail.com',
  'Outlook.com': 'imap-mail.outlook.com',
  'Yahoo Mail': 'imap.mail.yahoo.com',
  'AOL Mail': 'imap.aol.com',
  'iCloud Mail': 'imap.mail.me.com',
  'Telekom Mail': 'secureimap.t-online.de',
  'GMX': 'imap.gmx.com',
  'WEB.DE': 'imap.web.de',
  'Fastmail': 'imap.fastmail.com',
  'Mail': 'imap.mail.ru',
  'Rambler Mail': 'imap.rambler.ru',
  'Yandex Mail': 'imap.yandex.ru',
  'Zoho Mail': 'imap.zoho.com',
  'QQ Mail': 'imap.qq.com',
  'NetEase Mail': 'imap.163.com',
  'Sina Mail': 'imap.sina.com',
  'Mail.com': 'imap.mail.com',
  'Mailbox.org': 'imap.mailbox.org',
  'Posteo': 'posteo.de',
  'Seznam Email': 'imap.seznam.cz',
  'Runbox': 'mail.runbox.com',
})

function preset(provider, host, port, secure, passwordHint = '', authMode = 'password', imapHost = IMAP_BY_PROVIDER[provider] || '') {
  return Object.freeze({
    provider,
    host,
    port,
    secure,
    requireTLS: !secure,
    imapHost,
    imapPort: imapHost ? 993 : 0,
    imapSecure: Boolean(imapHost),
    passwordHint,
    authMode,
  })
}

const HINT_APP_PASSWORD = 'Используйте пароль приложения, если у аккаунта включена двухэтапная аутентификация.'

const SMTP_CONFIGS = Object.freeze({
  // Google: https://developers.google.com/workspace/gmail/imap/imap-smtp
  'gmail.com':      preset('Gmail', 'smtp.gmail.com', 465, true, HINT_APP_PASSWORD),
  'googlemail.com': preset('Gmail', 'smtp.gmail.com', 465, true, HINT_APP_PASSWORD),

  // Microsoft consumer mail: https://support.microsoft.com/en-us/outlook/pop-imap-and-smtp-settings-for-outlook-com
  'outlook.com':     preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.de':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.fr':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.es':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.it':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.co.uk':   preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'outlook.jp':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.com':     preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.co.uk':   preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.de':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.fr':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.es':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.it':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'hotmail.ru':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'live.com':        preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'live.co.uk':      preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'live.de':         preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'live.fr':         preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'live.ru':         preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'msn.com':         preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),
  'windowslive.com': preset('Outlook.com', 'smtp-mail.outlook.com', 587, false, 'Outlook.com использует Modern Auth/OAuth2; при парольном входе может потребоваться пароль приложения.', 'oauth2'),

  // Yahoo: https://help.yahoo.com/kb/pop-access-settings-instructions-yahoo-mail-sln4724.html
  'yahoo.com':      preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.co.uk':    preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.de':       preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.fr':       preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.es':       preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.it':       preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'yahoo.co.jp':    preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'ymail.com':      preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'rocketmail.com': preset('Yahoo Mail', 'smtp.mail.yahoo.com', 465, true, 'Нужен Yahoo App Password.'),
  'aol.com':        preset('AOL Mail', 'smtp.aol.com', 465, true, HINT_APP_PASSWORD),
  'aim.com':        preset('AOL Mail', 'smtp.aol.com', 465, true, HINT_APP_PASSWORD),

  // Apple: https://support.apple.com/en-us/102525
  'icloud.com': preset('iCloud Mail', 'smtp.mail.me.com', 587, false, 'Нужен пароль приложения Apple Account.'),
  'me.com':     preset('iCloud Mail', 'smtp.mail.me.com', 587, false, 'Нужен пароль приложения Apple Account.'),
  'mac.com':    preset('iCloud Mail', 'smtp.mail.me.com', 587, false, 'Нужен пароль приложения Apple Account.'),

  // Telekom: https://www.telekom.de/hilfe/apps-dienste/e-mail/posteingang-postausgang-server
  't-online.de': preset('Telekom Mail', 'securesmtp.t-online.de', 465, true, 'Используйте пароль для почтовых программ Telekom.'),
  'magenta.de':  preset('Telekom Mail', 'securesmtp.t-online.de', 465, true, 'Используйте пароль для почтовых программ Telekom.'),

  // GMX and WEB.DE: https://hilfe.gmx.net/pop-imap/imap/imap-serverdaten.html ; https://hilfe.web.de/pop-imap/imap/imap-serverdaten.html
  'gmx.com': preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.net': preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.de':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.at':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.ch':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.fr':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.es':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'gmx.us':  preset('GMX', 'mail.gmx.net', 587, false, 'Включите IMAP/POP в настройках GMX; поддерживаются TLS 1.2/1.3.'),
  'web.de':  preset('WEB.DE', 'smtp.web.de', 587, false, 'Включите IMAP/POP в настройках WEB.DE; поддерживаются TLS 1.2/1.3.'),

  // Fastmail: https://www.fastmail.help/hc/en-us/articles/1500000279921-IMAP-POP-and-SMTP
  'fastmail.com': preset('Fastmail', 'smtp.fastmail.com', 465, true, 'Нужен отдельный Fastmail App Password; SMTP доступен не на каждом тарифе.'),
  'fastmail.fm':  preset('Fastmail', 'smtp.fastmail.com', 465, true, 'Нужен отдельный Fastmail App Password; SMTP доступен не на каждом тарифе.'),
  'fastmail.net': preset('Fastmail', 'smtp.fastmail.com', 465, true, 'Нужен отдельный Fastmail App Password; SMTP доступен не на каждом тарифе.'),

  // Mail.com: https://support.mail.com/premium/imap/server.html
  'mail.com': preset('Mail.com', 'smtp.mail.com', 465, true, 'Разрешите IMAP/SMTP в настройках Mail.com, если доступ отключён.'),

  // Mailbox.org: https://kb.mailbox.org/en/private/e-mail/e-mail-configuration/
  'mailbox.org': preset('Mailbox.org', 'smtp.mailbox.org', 465, true, 'При 2FA используйте пароль приложения Mailbox.org.'),

  // Posteo: https://posteo.de/en/help/how-do-i-set-up-posteo-in-an-email-client-pop3-imap-and-smtp
  'posteo.de':  preset('Posteo', 'posteo.de', 465, true, 'Используйте Posteo app password; TLS обязателен.'),
  'posteo.com': preset('Posteo', 'posteo.de', 465, true, 'Используйте Posteo app password; TLS обязателен.'),
  'posteo.net': preset('Posteo', 'posteo.de', 465, true, 'Используйте Posteo app password; TLS обязателен.'),
  'posteo.uk':  preset('Posteo', 'posteo.de', 465, true, 'Используйте Posteo app password; TLS обязателен.'),

  // Seznam Email: https://o-seznam.cz/napoveda/email/mohlo-by-se-hodit/postovni-programy-a-aplikace/
  'seznam.cz': preset('Seznam Email', 'smtp.seznam.cz', 465, true, 'SMTP требует аутентификацию полной почтовой учётной записью.'),

  // Runbox: https://help.runbox.com/email-program-settings/
  'runbox.com':     preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),
  'runbox.no':      preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),
  'rbx.run':        preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),
  'rbx.email':      preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),
  'offshore.rocks': preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),
  'mailhouse.biz':  preset('Runbox', 'mail.runbox.com', 465, true, 'SMTP доступен после верификации альтернативного адреса или оплаты Runbox.'),

  // Mail.ru: https://help.mail.ru/mail/login/mailer/
  'mail.ru':  preset('Mail', 'smtp.mail.ru', 465, true, 'Нужен пароль для внешнего приложения Mail.'),
  'inbox.ru': preset('Mail', 'smtp.mail.ru', 465, true, 'Нужен пароль для внешнего приложения Mail.'),
  'list.ru':  preset('Mail', 'smtp.mail.ru', 465, true, 'Нужен пароль для внешнего приложения Mail.'),
  'bk.ru':    preset('Mail', 'smtp.mail.ru', 465, true, 'Нужен пароль для внешнего приложения Mail.'),

  // Rambler: https://help.rambler.ru/mail/mail-pochtovye-klienty/1275
  'rambler.ru':     preset('Rambler Mail', 'smtp.rambler.ru', 465, true, 'Включите доступ почтовых клиентов; при 2FA нужен специальный пароль.'),
  'lenta.ru':       preset('Rambler Mail', 'smtp.rambler.ru', 465, true, 'Включите доступ почтовых клиентов; при 2FA нужен специальный пароль.'),
  'ro.ru':          preset('Rambler Mail', 'smtp.rambler.ru', 465, true, 'Включите доступ почтовых клиентов; при 2FA нужен специальный пароль.'),
  'autorambler.ru': preset('Rambler Mail', 'smtp.rambler.ru', 465, true, 'Включите доступ почтовых клиентов; при 2FA нужен специальный пароль.'),
  'myrambler.ru':   preset('Rambler Mail', 'smtp.rambler.ru', 465, true, 'Включите доступ почтовых клиентов; при 2FA нужен специальный пароль.'),

  // Yandex consumer configuration retained from existing deployed catalogue.
  'yandex.ru':  preset('Yandex Mail', 'smtp.yandex.ru', 465, true, HINT_APP_PASSWORD),
  'yandex.com': preset('Yandex Mail', 'smtp.yandex.com', 465, true, HINT_APP_PASSWORD),
  'ya.ru':      preset('Yandex Mail', 'smtp.yandex.ru', 465, true, HINT_APP_PASSWORD),

  // Zoho: https://www.zoho.com/mail/help/zoho-smtp.html
  'zoho.com':     preset('Zoho Mail', 'smtp.zoho.com', 465, true, 'Для custom-domain платного Zoho может требоваться smtppro.zoho.com; сверяйте данные в кабинете Zoho.'),
  'zohomail.com': preset('Zoho Mail', 'smtp.zoho.com', 465, true, 'При 2FA может требоваться пароль приложения Zoho.'),

  // Existing provider presets retained for explicit/manual provider aliases.
  'qq.com':      preset('QQ Mail', 'smtp.qq.com', 465, true, HINT_APP_PASSWORD),
  '163.com':     preset('NetEase Mail', 'smtp.163.com', 465, true, HINT_APP_PASSWORD),
  '126.com':     preset('NetEase Mail', 'smtp.126.com', 465, true, HINT_APP_PASSWORD),
  'sina.com':    preset('Sina Mail', 'smtp.sina.com', 465, true, HINT_APP_PASSWORD),
  'sendgrid':    preset('SendGrid', 'smtp.sendgrid.net', 587, false, 'Используйте API key/SMTP credential SendGrid.'),
  'mailgun':     preset('Mailgun', 'smtp.mailgun.org', 587, false, 'Используйте SMTP credential Mailgun.'),
  'postmark':    preset('Postmark', 'smtp.postmarkapp.com', 587, false, 'Используйте SMTP token Postmark.'),
  'brevo':       preset('Brevo', 'smtp-relay.brevo.com', 587, false, 'Используйте SMTP credential Brevo.'),
  'sendinblue':  preset('Brevo', 'smtp-relay.brevo.com', 587, false, 'Используйте SMTP credential Brevo.'),
  'mailjet':     preset('Mailjet', 'in-v3.mailjet.com', 587, false, 'Используйте SMTP credential Mailjet.'),
})

function getDomainFromEmail(email) {
  const value = String(email || '').trim().toLowerCase()
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return ''
  return value.slice(value.lastIndexOf('@') + 1)
}

function getSmtpConfigForDomain(domain) {
  const d = String(domain || '').trim().toLowerCase()
  if (!/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(d)) return null
  if (SMTP_CONFIGS[d]) return { ...SMTP_CONFIGS[d] }
  if (d.startsWith('outlook.') || d.startsWith('hotmail.') || d.startsWith('live.')) {
    return { ...SMTP_CONFIGS['outlook.com'] }
  }
  if (d.startsWith('yahoo.')) return { ...SMTP_CONFIGS['yahoo.com'] }
  if (d.startsWith('gmx.')) return { ...SMTP_CONFIGS['gmx.net'] }
  return null
}

function getSmtpPresetForEmail(email) {
  const domain = getDomainFromEmail(email)
  const cfg = domain ? getSmtpConfigForDomain(domain) : null
  if (!cfg) return {
    known: false,
    domain,
    provider: '',
    host: '',
    port: 587,
    use_ssl: false,
    use_tls: true,
    imap_host: '',
    imap_port: 993,
    imap_ssl: true,
    password_hint: '',
    auth_mode: 'manual',
    message: domain
      ? `Для домена ${domain} нет проверенного preset. Укажите SMTP-хост, порт и шифрование вручную.`
      : 'Введите корректный email-адрес для автозаполнения SMTP.',
  }
  return {
    known: true,
    domain,
    provider: cfg.provider,
    host: cfg.host,
    port: cfg.port,
    use_ssl: cfg.secure,
    use_tls: cfg.requireTLS,
    imap_host: cfg.imapHost,
    imap_port: cfg.imapPort,
    imap_ssl: cfg.imapSecure,
    password_hint: cfg.passwordHint,
    auth_mode: cfg.authMode,
    message: `Автозаполнено: ${cfg.provider} — ${cfg.host}:${cfg.port}.`,
  }
}

module.exports = { SMTP_CONFIGS, getDomainFromEmail, getSmtpConfigForDomain, getSmtpPresetForEmail }
