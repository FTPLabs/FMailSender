import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export type AppLanguage = 'ru' | 'en'

type Dictionary = Record<string, string>

const RU: Dictionary = {
  'nav.dashboard': 'Дашборд', 'nav.accounts': 'Аккаунты', 'nav.proxies': 'Прокси', 'nav.recipients': 'Получатели', 'nav.compose': 'Письмо', 'nav.sending': 'Рассылка', 'nav.inbox': 'Входящие', 'nav.guide': 'Инструкция',
  'layout.navigation': 'Навигация', 'layout.coreStatus': 'Статус ядра', 'layout.accounts': 'аккаунты', 'layout.recipients': 'получатели', 'layout.theme': 'режим темы', 'layout.language': 'язык', 'layout.light': 'Светлая тема', 'layout.dark': 'Тёмная тема', 'layout.system': 'Как в системе',
  'state.idle': 'Ожидание', 'state.running': 'Отправка', 'state.paused': 'Пауза', 'state.done': 'Завершено', 'state.error': 'Ошибка',
  'compose.title': 'Письмо', 'compose.sub': 'Тема, тело и настройки рассылки', 'compose.save': 'Сохранить', 'compose.saved': '✓ Сохранено', 'compose.sender': 'Отправитель', 'compose.senderName': 'Имя отправителя', 'compose.sendSettings': 'Настройки отправки', 'compose.delayMin': 'Задержка мин.', 'compose.delayMax': 'Задержка макс.', 'compose.dailyLimit': 'Лимит / день', 'compose.seconds': '(сек)', 'compose.perAccount': '(на аккаунт)', 'compose.delayNote': 'Рекомендуется не менее 1с.',
  'compose.ai': 'AI-шаблон', 'compose.aiDescription': 'Создаёт или улучшает прозрачный HTML для согласованных писем. Результат всегда нужно проверить перед сохранением.', 'compose.create': 'Создать HTML', 'compose.refine': 'Улучшить', 'compose.brief': 'Цель, аудитория и тон. Например: письмо участникам вебинара с резюме и ссылкой на запись.', 'compose.working': 'Gemini готовит черновик…', 'compose.personalKey': 'Личный Gemini API-ключ', 'compose.personalKeyHint': 'Только для этого сеанса. Не сохраняется, не отправляется на сервер лицензий и не попадает в логи.', 'compose.personalKeyPlaceholder': 'Вставьте ключ из Google AI Studio', 'compose.clearKey': 'Очистить', 'compose.serverKey': 'По умолчанию используется лицензированный серверный AI.', 'compose.body': 'Тело письма', 'compose.text': 'Текст', 'compose.preview': 'Превью', 'compose.hide': 'Скрыть',
  'startup.activation': 'Активация лицензии', 'startup.checking': 'Идёт проверка лицензии на сервере...', 'startup.activate': 'Активировать', 'startup.activating': 'Проверка...', 'startup.unavailable': 'Сервер лицензий временно недоступен. Проверьте подключение и повторите попытку.', 'startup.device': 'Ключ привязывается к устройству · Поддержка: fmail.shop',
  'guide.title': 'Быстрый запуск', 'guide.sub': 'Только необходимые действия. Ничего не вставляйте в поля, если не знаете назначение.', 'guide.step1': '1. Активируйте приложение', 'guide.step1text': 'На стартовом экране вставьте ключ лицензии и нажмите «Активировать». При ошибке проверьте интернет и повторите попытку.', 'guide.step2': '2. Добавьте отправителя', 'guide.step2text': 'Аккаунты → Добавить. Вставьте полный email и пароль приложения. Host, порт, SMTP и IMAP заполняются автоматически для известных провайдеров. Нажмите «Проверить».', 'guide.step3': '3. Импортируйте несколько ящиков', 'guide.step3text': 'Аккаунты → Импорт. Одна строка: email:пароль. Допустимы разделители : | или ;. Для неизвестного домена укажите SMTP вручную по документации провайдера.', 'guide.step4': '4. Добавьте получателей', 'guide.step4text': 'Получатели → Импорт. Одна строка: email или email|имя. Загружайте только контакты с подтверждённым согласием.', 'guide.step5': '5. Подготовьте письмо', 'guide.step5text': 'Письмо → заполните имя отправителя, Reply-To, тему и HTML. Используйте «Превью», затем «Сохранить».', 'guide.step6': '6. Настройте AI', 'guide.step6text': 'В «Письмо» опишите задачу и нажмите «Создать HTML». Личный Gemini-ключ действует только до закрытия приложения; вставьте его в поле, если хотите использовать собственный лимит.', 'guide.step7': '7. Запустите рассылку', 'guide.step7text': 'Рассылка → проверьте лимит и задержку → Запустить. Не обходите антиспам-защиты; используйте SPF, DKIM, DMARC и прозрачную отписку.', 'guide.keyTitle': 'Личный Gemini API-ключ', 'guide.keyText': 'Получите ключ в Google AI Studio. Вставьте его только в поле «Личный Gemini API-ключ» на странице «Письмо». Он используется для одного запроса через локальное ядро, не сохраняется и не передаётся на VPS.',
}

const EN: Dictionary = {
  'nav.dashboard': 'Dashboard', 'nav.accounts': 'Accounts', 'nav.proxies': 'Proxies', 'nav.recipients': 'Recipients', 'nav.compose': 'Message', 'nav.sending': 'Sending', 'nav.inbox': 'Inbox', 'nav.guide': 'Guide',
  'layout.navigation': 'Navigation', 'layout.coreStatus': 'Core status', 'layout.accounts': 'accounts', 'layout.recipients': 'recipients', 'layout.theme': 'theme mode', 'layout.language': 'language', 'layout.light': 'Light theme', 'layout.dark': 'Dark theme', 'layout.system': 'Follow system',
  'state.idle': 'Idle', 'state.running': 'Sending', 'state.paused': 'Paused', 'state.done': 'Completed', 'state.error': 'Error',
  'compose.title': 'Message', 'compose.sub': 'Subject, content and sending settings', 'compose.save': 'Save', 'compose.saved': '✓ Saved', 'compose.sender': 'Sender', 'compose.senderName': 'Sender name', 'compose.sendSettings': 'Sending settings', 'compose.delayMin': 'Min delay', 'compose.delayMax': 'Max delay', 'compose.dailyLimit': 'Daily limit', 'compose.seconds': '(sec)', 'compose.perAccount': '(per account)', 'compose.delayNote': 'At least 1 second is recommended.',
  'compose.ai': 'AI template', 'compose.aiDescription': 'Creates or improves transparent HTML for consent-based email. Always review the result before saving.', 'compose.create': 'Create HTML', 'compose.refine': 'Improve', 'compose.brief': 'Goal, audience and tone. Example: a webinar follow-up with a summary and recording link.', 'compose.working': 'Gemini is preparing a draft…', 'compose.personalKey': 'Personal Gemini API key', 'compose.personalKeyHint': 'Current session only. It is not saved, sent to the license server, or written to logs.', 'compose.personalKeyPlaceholder': 'Paste a key from Google AI Studio', 'compose.clearKey': 'Clear', 'compose.serverKey': 'The licensed server AI is used by default.', 'compose.body': 'Message body', 'compose.text': 'Text', 'compose.preview': 'Preview', 'compose.hide': 'Hide',
  'startup.activation': 'License activation', 'startup.checking': 'Checking the license on the server...', 'startup.activate': 'Activate', 'startup.activating': 'Checking...', 'startup.unavailable': 'The license server is temporarily unavailable. Check your connection and try again.', 'startup.device': 'The key is bound to this device · Support: fmail.shop',
  'guide.title': 'Quick start', 'guide.sub': 'Only required steps. Do not paste data into fields whose purpose you do not know.', 'guide.step1': '1. Activate the app', 'guide.step1text': 'On the startup screen, paste the license key and click Activate. If it fails, check your internet connection and retry.', 'guide.step2': '2. Add a sender', 'guide.step2text': 'Accounts → Add. Paste a full email address and an app password. Host, port, SMTP and IMAP are filled in for known providers. Click Test.', 'guide.step3': '3. Import several inboxes', 'guide.step3text': 'Accounts → Import. One line: email:password. Separators : | or ; are accepted. For an unknown domain, use the provider documentation to enter SMTP manually.', 'guide.step4': '4. Add recipients', 'guide.step4text': 'Recipients → Import. One line: email or email|name. Import only contacts with documented consent.', 'guide.step5': '5. Prepare the message', 'guide.step5text': 'Message → fill in sender name, Reply-To, subject and HTML. Use Preview, then Save.', 'guide.step6': '6. Set up AI', 'guide.step6text': 'In Message, describe the task and click Create HTML. A personal Gemini key lasts only until the app closes; paste it if you want to use your own quota.', 'guide.step7': '7. Start sending', 'guide.step7text': 'Sending → review the limit and delay → Start. Do not bypass spam protections; use SPF, DKIM, DMARC and a visible unsubscribe link.', 'guide.keyTitle': 'Personal Gemini API key', 'guide.keyText': 'Create a key in Google AI Studio. Paste it only into the Personal Gemini API key field on the Message page. It is used for one request through the local core, is not saved, and is not sent to the VPS.',
}

const dictionaries: Record<AppLanguage, Dictionary> = { ru: RU, en: EN }

type I18nValue = { language: AppLanguage; setLanguage: (value: AppLanguage) => void; t: (key: string) => string }
const I18nContext = createContext<I18nValue | null>(null)

function readLanguage(): AppLanguage {
  return localStorage.getItem('fmail-language') === 'en' ? 'en' : 'ru'
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<AppLanguage>(readLanguage)
  useEffect(() => {
    localStorage.setItem('fmail-language', language)
    document.documentElement.lang = language
  }, [language])
  const value = useMemo<I18nValue>(() => ({ language, setLanguage, t: (key) => dictionaries[language][key] || RU[key] || key }), [language])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('I18nProvider is required')
  return value
}
