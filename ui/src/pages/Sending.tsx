import { useCallback, useEffect, useState } from 'react'
import { GothicIcon } from '../components/GothicIcon'
import { api, type CampaignReadiness } from '../api'
import { useStatus } from '../contexts/StatusContext'
import { useI18n } from '../i18n'

function Ring({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(value / max, 1) : 0
  const radius = 52; const circumference = 2 * Math.PI * radius
  return <svg width="120" height="120" viewBox="0 0 120 120">
    <circle cx="60" cy="60" r={radius} fill="none" stroke="#1c1c35" strokeWidth="10" />
    <circle cx="60" cy="60" r={radius} fill="none" stroke="#8b5cf6" strokeWidth="10" strokeDasharray={`${pct * circumference} ${circumference}`} strokeLinecap="round" transform="rotate(-90 60 60)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
    <text x="60" y="55" textAnchor="middle" fill="#e8e8ff" fontSize="19" fontWeight="700" fontFamily="Inter,system-ui,sans-serif">{Math.round(pct * 100)}%</text>
    <text x="60" y="73" textAnchor="middle" fill="#6666aa" fontSize="10" fontFamily="Inter,system-ui,sans-serif">{value}/{max}</text>
  </svg>
}

const ISSUE_COPY: Record<string, { ru: string; en: string }> = {
  no_ready_accounts: { ru: 'Нет проверенных активных аккаунтов. Добавьте и проверьте аккаунты.', en: 'No tested active accounts. Add and test accounts.' },
  no_recipients: { ru: 'Нет получателей. Загрузите список согласованных контактов.', en: 'No recipients. Load a list of consented contacts.' },
  missing_subject: { ru: 'Не заполнена тема письма.', en: 'The message subject is missing.' },
  missing_body: { ru: 'Не заполнено тело письма.', en: 'The message body is missing.' },
  missing_reply_to: { ru: 'Рекомендуется указать Reply-To для прозрачной обратной связи.', en: 'Set Reply-To for transparent replies.' },
  missing_text_version: { ru: 'Рекомендуется добавить текстовую версию письма.', en: 'Add a text-only version of the email.' },
  missing_unsubscribe: { ru: 'Для согласованных массовых писем добавьте заметную ссылку отписки.', en: 'For consent-based bulk mail, add a visible unsubscribe link.' },
  short_delay: { ru: 'Короткая задержка может не соответствовать правилам нового почтового ящика. Сверьте лимиты провайдера.', en: 'A short delay may not suit a new mailbox. Check your provider limits.' },
  daily_capacity: { ru: 'Список больше доступного дневного лимита активных аккаунтов.', en: 'The list exceeds the remaining daily capacity of active accounts.' },
  'spam:subject_long': { ru: 'Тема длиннее рекомендуемого объёма. Сократите её.', en: 'The subject is longer than recommended. Shorten it.' },
  'spam:subject_caps': { ru: 'В теме слишком много заглавных букв. Уберите крикливое оформление.', en: 'The subject uses excessive capital letters. Use normal casing.' },
  'spam:many_links': { ru: 'Слишком много ссылок. Оставьте только необходимые и проверенные ссылки.', en: 'Too many links. Keep only necessary, verified links.' },
  'spam:insecure_link': { ru: 'Найдена ссылка без HTTPS. Замените её на защищённую.', en: 'An HTTP link was found. Replace it with HTTPS.' },
  'spam:tracking_pixel': { ru: 'Найден невидимый tracking pixel. Удалите его для прозрачной рассылки.', en: 'A hidden tracking pixel was found. Remove it for transparent sending.' },
  'spam:thin_content': { ru: 'Слишком мало видимого текста. Добавьте ясное содержание и контекст письма.', en: 'There is too little visible content. Add clear context and substance.' },
  'spam:missing_unsubscribe': { ru: 'Добавьте понятную ссылку отписки для подписных рассылок.', en: 'Add a clear unsubscribe link for subscribed mail.' },
}

export default function Sending() {
  const { status, refresh } = useStatus()
  const { language } = useI18n()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [readiness, setReadiness] = useState<CampaignReadiness | null>(null)
  const [aiBusy, setAiBusy] = useState(false)

  const loadReadiness = useCallback(async () => {
    try { setReadiness(await api.campaign.readiness()) }
    catch { setReadiness(null) }
  }, [])
  useEffect(() => { void loadReadiness() }, [loadReadiness])

  const cp = status?.campaign
  const state = cp?.state ?? 'idle'
  const run = state === 'running'; const paused = state === 'paused'; const done = state === 'done'; const stopped = state === 'stopped'; const failed = state === 'error' || stopped
  const recipients = status?.recipients ?? 0

  const local = (code: string) => ISSUE_COPY[code]?.[language] || code
  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setNotice('')
    try { await fn(); await refresh(); await loadReadiness() }
    catch (error: unknown) {
      const message = (error as { response?: { data?: { detail?: string } }; message?: string })
      setNotice(message?.response?.data?.detail ?? (error as Error).message)
    } finally { setBusy(false) }
  }
  async function improveWithAi() {
    setAiBusy(true); setNotice('')
    try {
      const campaign = await api.campaign.get()
      const result = await api.ai.template({ mode: 'refine', brief: 'Improve legitimate email deliverability without evasion: preserve factual meaning, remove manipulative wording, keep clear sender identity, HTTPS links, readable text, and a visible unsubscribe instruction where appropriate.', subject: campaign.subject || '', body_html: campaign.body_html || '', body_text: campaign.body_text || '' })
      await api.campaign.save({ subject: result.subject, body_html: result.body_html, body_text: result.body_text })
      await loadReadiness()
      setNotice(language === 'en' ? 'AI revised the content. Review it before sending.' : 'ИИ исправил содержимое. Проверьте его перед отправкой.')
    } catch (error: unknown) {
      const message = error as { response?: { data?: { detail?: string } }; message?: string }
      setNotice(message?.response?.data?.detail ?? message?.message ?? (language === 'en' ? 'AI revision failed.' : 'Не удалось исправить содержимое через ИИ.'))
    } finally { setAiBusy(false) }
  }

  async function start() {
    const current = await api.campaign.readiness()
    setReadiness(current)
    if (!current.ready) { setNotice(language === 'en' ? 'Fix the blocking readiness items before starting.' : 'Исправьте обязательные пункты готовности перед запуском.') ; return }
    await act(api.campaign.start)
  }

  const elapsed = cp?.started_at ? Math.round((Date.now() / 1000 - cp.started_at) / 60) : 0
  const speed = elapsed > 0 && cp?.sent ? Math.round(cp.sent / elapsed) : 0
  const stateColor = run ? '#06b6d4' : done ? '#10b981' : failed ? '#ef4444' : paused ? '#f59e0b' : '#6666aa'
  const stateLabel = run ? (language === 'en' ? 'Sending' : 'Отправка') : paused ? (language === 'en' ? 'Paused' : 'Пауза') : done ? (language === 'en' ? 'Completed' : 'Завершено') : stopped ? (language === 'en' ? 'Stopped: anti-spam rejection' : 'Остановлено: антиспам') : failed ? (language === 'en' ? 'Error' : 'Ошибка') : (language === 'en' ? 'Idle' : 'Ожидание')

  return <div className="page max-w-2xl flex-1 flex flex-col">
    <div><h1 className="page-title">Рассылка</h1><p className="page-sub">Запуск и мониторинг кампании</p></div>
    {notice && <div role="status" className="mt-4 rounded-lg border border-warn/35 bg-warn/10 px-4 py-2 text-sm text-warn">{notice}</div>}
    {!run && !paused && !done && <div className="card mt-5 space-y-3">
      <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold text-[#e8e8ff]">Готовность</h2><button onClick={() => void loadReadiness()} className="btn btn-secondary btn-sm"><GothicIcon name="refresh" size={13} /> Обновить</button></div>
      <div className="space-y-2">
        {(readiness?.errors || []).map(code => <div key={code} className="flex items-start gap-3 text-sm"><GothicIcon name="error" size={14} className="mt-0.5 text-error flex-shrink-0" /><span className="text-xs text-error">{local(code)}</span></div>)}
        {readiness?.ready && <div className="flex items-center gap-3 text-sm"><GothicIcon name="check" size={14} className="text-success" /><span className="text-xs text-[#86efac]">{language === 'en' ? 'Required conditions are met.' : 'Обязательные условия выполнены.'}</span></div>}
        {(readiness?.warnings || []).map(code => <div key={code} className="flex items-start gap-3 text-sm"><GothicIcon name="info" size={14} className="mt-0.5 text-warn flex-shrink-0" /><span className="text-xs text-warn">{local(code)}</span></div>)}
      </div>
      {readiness && <><p className="text-[11px] text-[#6666aa]">{language === 'en' ? `Ready accounts: ${readiness.active_accounts} · recipients: ${readiness.recipients} · available today: ${readiness.available_daily}` : `Готовых аккаунтов: ${readiness.active_accounts} · получателей: ${readiness.recipients} · доступно сегодня: ${readiness.available_daily}`}</p>{readiness.spam && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dim/40 bg-surf2/50 px-3 py-2"><span className="text-xs text-muted">{language === 'en' ? `Content risk: ${readiness.spam.level} · score ${readiness.spam.score}/100` : `Риск контента: ${readiness.spam.level} · оценка ${readiness.spam.score}/100`}</span><button type="button" className="btn btn-secondary btn-sm" disabled={aiBusy} onClick={() => void improveWithAi()}><GothicIcon name="ai" size={13}/>{aiBusy ? (language === 'en' ? 'Working…' : 'Обработка…') : (language === 'en' ? 'Fix with AI' : 'Исправить ИИ')}</button></div>}</>}
    </div>}
    <div className="card flex-1 mt-5 flex flex-col items-center justify-center gap-6 py-10">
      <Ring value={cp?.sent ?? 0} max={cp?.total || recipients || 1} />
      <div className="text-center"><div className="text-base font-semibold" style={{ color: stateColor }}>{stateLabel}</div>{cp?.current_email && <div className="mt-1 text-xs font-mono text-muted"><GothicIcon name="sending" size={12} className="mr-1 inline-block text-cyan" /><span className="text-[#06b6d4]">{cp.current_email}</span>{cp.current_account && <span> · <span className="text-[#8b5cf6]">{cp.current_account}</span></span>}</div>}</div>
      {(cp?.total ?? 0) > 0 && <div className="grid grid-cols-4 gap-3 w-full text-center">{[
        { label: language === 'en' ? 'Sent' : 'Отправлено', value: cp?.sent ?? 0, color: '#10b981' }, { label: language === 'en' ? 'Errors' : 'Ошибок', value: cp?.failed ?? 0, color: '#ef4444' }, { label: language === 'en' ? 'Remaining' : 'Осталось', value: Math.max(0, (cp?.total ?? 0) - (cp?.sent ?? 0) - (cp?.failed ?? 0)), color: '#6666aa' }, { label: language === 'en' ? 'Speed' : 'Скорость', value: `${speed}/${language === 'en' ? 'm' : 'м'}`, color: '#06b6d4' },
      ].map(item => <div key={item.label} className="card-inset py-3"><div className="text-base font-bold tabular-nums" style={{ color: item.color }}>{item.value}</div><div className="text-[10px] text-[#6666aa] mt-0.5">{item.label}</div></div>)}</div>}
      <div className="flex items-center gap-3">
        {!run && !paused && <button onClick={() => void start()} disabled={busy || readiness?.ready === false} className="btn btn-primary px-8 py-2.5 text-sm"><GothicIcon name="play" size={16} /> {language === 'en' ? 'Start campaign' : 'Начать рассылку'}</button>}
        {run && <><button onClick={() => void act(api.campaign.pause)} disabled={busy} className="btn btn-secondary px-6"><GothicIcon name="pause" size={15} /> {language === 'en' ? 'Pause' : 'Пауза'}</button><button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-danger px-6"><GothicIcon name="stop" size={15} /> {language === 'en' ? 'Stop' : 'Стоп'}</button></>}
        {paused && <><button onClick={() => void act(api.campaign.resume)} disabled={busy} className="btn btn-primary px-6"><GothicIcon name="play" size={15} /> {language === 'en' ? 'Resume' : 'Продолжить'}</button><button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-danger px-6"><GothicIcon name="stop" size={15} /> {language === 'en' ? 'Stop' : 'Стоп'}</button></>}
        {(done || failed || stopped) && <button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-secondary px-6"><GothicIcon name="refresh" size={15} /> {language === 'en' ? 'Reset' : 'Сбросить'}</button>}
      </div>
    </div>
    {stopped && cp?.stop_reason && <div className="stop-notice card mt-5"><div className="flex items-start gap-3"><GothicIcon name="warning" size={16} className="mt-0.5 flex-shrink-0 text-error" /><div><div className="font-semibold text-error">{language === 'en' ? 'Sending stopped — no automatic retries' : 'Отправка остановлена — автоматические повторы отключены'}</div><div className="mt-1 text-sm text-text break-words">{cp.stop_reason}</div></div></div></div>}
    {cp?.errors?.length ? <div className="card mt-5 space-y-2"><div className="flex items-center gap-2 text-xs font-semibold text-[#f59e0b] uppercase tracking-wider"><GothicIcon name="warning" size={13} /> {language === 'en' ? `Sending errors (${cp.errors.length})` : `Ошибки отправки (${cp.errors.length})`}</div><div className="error-log-list max-h-64 overflow-y-auto space-y-2 pr-1">{cp.errors.slice(-20).map((item, index) => <div key={index} className="error-log-item rounded-lg px-3 py-2 text-xs font-mono whitespace-pre-wrap break-words leading-relaxed">{item}</div>)}</div></div> : null}
  </div>
}
