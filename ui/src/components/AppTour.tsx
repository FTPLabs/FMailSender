import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { GothicIcon } from './GothicIcon'
import { useI18n } from '../i18n'
import { useStatus } from '../contexts/StatusContext'

const TOUR_STORAGE_KEY = 'fmail-tour-v1-completed'

type TourStep = {
  path: string
  ruTitle: string
  enTitle: string
  ruText: string
  enText: string
}

const STEPS: TourStep[] = [
  { path: '/dashboard', ruTitle: 'Обзор приложения', enTitle: 'App overview', ruText: 'Здесь виден статус ядра, готовых аккаунтов, получателей, прокси и текущей рассылки.', enText: 'See core status, ready accounts, recipients, proxies and the current campaign here.' },
  { path: '/accounts', ruTitle: 'Добавьте отправителей', enTitle: 'Add senders', ruText: 'Вставьте email и пароль приложения. Для известных доменов SMTP и IMAP подставляются автоматически. Перед запуском проверьте аккаунты.', enText: 'Paste an email and app password. SMTP and IMAP are filled automatically for known domains. Test accounts before sending.' },
  { path: '/proxies', ruTitle: 'Импортируйте прокси при необходимости', enTitle: 'Import proxies when needed', ruText: 'Вставьте список или загрузите файл. Проверьте доступность и распределите только рабочие прокси между аккаунтами.', enText: 'Paste a list or upload a file. Check reachability and assign only working proxies to accounts.' },
  { path: '/recipients', ruTitle: 'Загрузите согласованных получателей', enTitle: 'Load consented recipients', ruText: 'Импортируйте только контакты с подтверждённым согласием. Одна строка: email или email|имя.', enText: 'Import only contacts with documented consent. One line: email or email|name.' },
  { path: '/compose', ruTitle: 'Подготовьте письмо', enTitle: 'Prepare the message', ruText: 'Заполните тему, текстовую и HTML-версии, Reply-To. AI создаёт только черновик: результат нужно проверить перед сохранением.', enText: 'Fill in subject, text and HTML versions, and Reply-To. AI creates a draft only; review it before saving.' },
  { path: '/sending', ruTitle: 'Проверьте готовность перед запуском', enTitle: 'Review readiness before sending', ruText: 'Перед стартом убедитесь, что аккаунты проверены, получатели согласованы, а лимит и задержка соответствуют правилам провайдера.', enText: 'Before starting, ensure accounts are tested, recipients are consented, and limits and delays meet provider rules.' },
  { path: '/guide', ruTitle: 'Инструкция всегда доступна', enTitle: 'The guide is always available', ruText: 'Откройте «Инструкция» в навигации, чтобы повторить порядок работы. Экскурсию можно запустить снова кнопкой в боковой панели.', enText: 'Open Guide in navigation to review the workflow. Restart this tour at any time from the sidebar.' },
]

export default function AppTour() {
  const { language } = useI18n()
  const { online } = useStatus()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [index, setIndex] = useState(0)

  const step = STEPS[index]
  const copy = useMemo(() => ({
    title: language === 'en' ? step.enTitle : step.ruTitle,
    text: language === 'en' ? step.enText : step.ruText,
    progress: language === 'en' ? `Step ${index + 1} of ${STEPS.length}` : `Шаг ${index + 1} из ${STEPS.length}`,
    skip: language === 'en' ? 'Do not show' : 'Не показывать',
    back: language === 'en' ? 'Back' : 'Назад',
    next: language === 'en' ? 'Next' : 'Далее',
    finish: language === 'en' ? 'Finish' : 'Готово',
    label: language === 'en' ? 'App tour' : 'Экскурсия по приложению',
  }), [index, language, step])

  function finish() {
    localStorage.setItem(TOUR_STORAGE_KEY, '1')
    setOpen(false)
  }

  function go(next: number) {
    const bounded = Math.max(0, Math.min(STEPS.length - 1, next))
    setIndex(bounded)
    if (location.pathname !== STEPS[bounded].path) navigate(STEPS[bounded].path)
  }

  useEffect(() => {
    if (!online || localStorage.getItem(TOUR_STORAGE_KEY) === '1') return
    const timeout = window.setTimeout(() => setOpen(true), 500)
    return () => window.clearTimeout(timeout)
  }, [online])

  useEffect(() => {
    const restart = () => {
      localStorage.removeItem(TOUR_STORAGE_KEY)
      setIndex(0)
      setOpen(true)
      navigate(STEPS[0].path)
    }
    window.addEventListener('fmail:tour:restart', restart)
    return () => window.removeEventListener('fmail:tour:restart', restart)
  }, [navigate])

  if (!open) return null
  return (
    <section role="dialog" aria-modal="false" aria-label={copy.label}
      className="fixed bottom-5 right-5 z-40 w-[min(390px,calc(100vw-2.5rem))] rounded-2xl border border-purple/45 bg-surface/95 p-5 shadow-nocturne backdrop-blur">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-purple-light">
          <GothicIcon name="tour" size={16} />
          <span className="text-[11px] font-semibold uppercase tracking-widest">{copy.progress}</span>
        </div>
        <button onClick={finish} className="btn btn-ghost btn-sm -mr-2 -mt-2 p-2" title={copy.skip} aria-label={copy.skip}><GothicIcon name="close" size={15} /></button>
      </div>
      <h2 className="text-base font-semibold text-text">{copy.title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">{copy.text}</p>
      <div className="mt-5 flex items-center justify-between gap-2">
        <button onClick={finish} className="text-xs text-muted hover:text-text">{copy.skip}</button>
        <div className="flex gap-2">
          <button onClick={() => go(index - 1)} disabled={index === 0} className="btn btn-secondary btn-sm"><GothicIcon name="back" size={14} /> {copy.back}</button>
          <button onClick={() => index === STEPS.length - 1 ? finish() : go(index + 1)} className="btn btn-primary btn-sm">{index === STEPS.length - 1 ? copy.finish : copy.next} {index === STEPS.length - 1 ? <GothicIcon name="close" size={13} /> : <GothicIcon name="next" size={14} />}</button>
        </div>
      </div>
    </section>
  )
}
