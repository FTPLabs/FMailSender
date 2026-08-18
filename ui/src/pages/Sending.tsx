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
}

export default function Sending() {
  const { status, refresh } = useStatus()
  const { language } = useI18n()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [readiness, setReadiness] = useState<CampaignReadiness | null>(null)

  const loadReadiness = useCallback(async () => {
    try { setReadiness(await api.campaign.readiness()) }
    catch { setReadiness(null) }
  }, [])
  useEffect(() => { void loadReadiness() }, [loadReadiness])

  const cp = status?.campaign
  const state = cp?.state ?? 'idle'
  const run = state === 'running'; const paused = state === 'paused'; const done = state === 'done'; const failed = state === 'error'
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
  async function start() {
    const current = await api.campaign.readiness()
    setReadiness(current)
    if (!current.ready) { setNotice(language === 'en' ? 'Fix the blocking readiness items before starting.' : 'Исправьте обязательные пункты готовности перед запуском.') ; return }
    await act(api.campaign.start)
  }

  const elapsed = cp?.started_at ? Math.round((Date.now() / 1000 - cp.started_at) / 60) : 0
  const speed = elapsed > 0 && cp?.sent ? Math.round(cp.sent / elapsed) : 0
  const stateColor = run ? '#06b6d4' : done ? '#10b981' : failed ? '#ef4444' : paused ? '#f59e0b' : '#6666aa'
  const stateLabel = run ? (language === 'en' ? '▶ Sending...' : '▶ Отправка...') : paused ? (language === 'en' ? '⏸ Paused' : '⏸ Пауза') : done ? (language === 'en' ? '✓ Completed' : '✓ Завершено') : failed ? (language === 'en' ? '✗ Error' : '✗ Ошибка') : (language === 'en' ? '⏹ Idle' : '⏹ Ожидание')

  return <div className="page max-w-2xl flex-1 flex flex-col">
    <div><h1 className="page-title">Рассылка</h1><p className="page-sub">Запуск и мониторинг кампании</p></div>
    {notice && <div role="status" className="mt-4 text-sm text-[#f59e0b] bg-[#f59e0b]/10 border border-[#f59e0b]/20 rounded-lg px-4 py-2">{notice}</div>}
    {!run && !paused && !done && <div className="card mt-5 space-y-3">
      <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold text-[#e8e8ff]">Готовность</h2><button onClick={() => void loadReadiness()} className="btn btn-secondary btn-sm"><GothicIcon name="refresh" size={13} /> Обновить</button></div>
      <div className="space-y-2">
        {(readiness?.errors || []).map(code => <div key={code} className="flex items-start gap-3 text-sm"><GothicIcon name="error" size={14} className="mt-0.5 text-error flex-shrink-0" /><span className="text-xs text-[#fca5a5]">{local(code)}</span></div>)}
        {readiness?.ready && <div className="flex items-center gap-3 text-sm"><GothicIcon name="check" size={14} className="text-success" /><span className="text-xs text-[#86efac]">{language === 'en' ? 'Required conditions are met.' : 'Обязательные условия выполнены.'}</span></div>}
        {(readiness?.warnings || []).map(code => <div key={code} className="flex items-start gap-3 text-sm"><GothicIcon name="info" size={14} className="mt-0.5 text-warn flex-shrink-0" /><span className="text-xs text-[#fcd34d]">{local(code)}</span></div>)}
      </div>
      {readiness && <p className="text-[11px] text-[#6666aa]">{language === 'en' ? `Ready accounts: ${readiness.active_accounts} · recipients: ${readiness.recipients} · available today: ${readiness.available_daily}` : `Готовых аккаунтов: ${readiness.active_accounts} · получателей: ${readiness.recipients} · доступно сегодня: ${readiness.available_daily}`}</p>}
    </div>}
    <div className="card flex-1 mt-5 flex flex-col items-center justify-center gap-6 py-10">
      <Ring value={cp?.sent ?? 0} max={cp?.total || recipients || 1} />
      <div className="text-center"><div className="text-base font-semibold" style={{ color: stateColor }}>{stateLabel}</div>{cp?.current_email && <div className="text-xs text-[#6666aa] mt-1 font-mono">→ <span className="text-[#06b6d4]">{cp.current_email}</span>{cp.current_account && <span> · <span className="text-[#8b5cf6]">{cp.current_account}</span></span>}</div>}</div>
      {(cp?.total ?? 0) > 0 && <div className="grid grid-cols-4 gap-3 w-full text-center">{[
        { label: language === 'en' ? 'Sent' : 'Отправлено', value: cp?.sent ?? 0, color: '#10b981' }, { label: language === 'en' ? 'Errors' : 'Ошибок', value: cp?.failed ?? 0, color: '#ef4444' }, { label: language === 'en' ? 'Remaining' : 'Осталось', value: Math.max(0, (cp?.total ?? 0) - (cp?.sent ?? 0) - (cp?.failed ?? 0)), color: '#6666aa' }, { label: language === 'en' ? 'Speed' : 'Скорость', value: `${speed}/${language === 'en' ? 'm' : 'м'}`, color: '#06b6d4' },
      ].map(item => <div key={item.label} className="card-inset py-3"><div className="text-base font-bold tabular-nums" style={{ color: item.color }}>{item.value}</div><div className="text-[10px] text-[#6666aa] mt-0.5">{item.label}</div></div>)}</div>}
      <div className="flex items-center gap-3">
        {!run && !paused && <button onClick={() => void start()} disabled={busy || readiness?.ready === false} className="btn btn-primary px-8 py-2.5 text-sm"><GothicIcon name="play" size={16} /> {language === 'en' ? 'Start campaign' : 'Начать рассылку'}</button>}
        {run && <><button onClick={() => void act(api.campaign.pause)} disabled={busy} className="btn btn-secondary px-6"><GothicIcon name="pause" size={15} /> {language === 'en' ? 'Pause' : 'Пауза'}</button><button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-danger px-6"><GothicIcon name="stop" size={15} /> {language === 'en' ? 'Stop' : 'Стоп'}</button></>}
        {paused && <><button onClick={() => void act(api.campaign.resume)} disabled={busy} className="btn btn-primary px-6"><GothicIcon name="play" size={15} /> {language === 'en' ? 'Resume' : 'Продолжить'}</button><button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-danger px-6"><GothicIcon name="stop" size={15} /> {language === 'en' ? 'Stop' : 'Стоп'}</button></>}
        {(done || failed) && <button onClick={() => void act(api.campaign.stop)} disabled={busy} className="btn btn-secondary px-6"><GothicIcon name="refresh" size={15} /> {language === 'en' ? 'Reset' : 'Сбросить'}</button>}
      </div>
    </div>
    {cp?.errors?.length ? <div className="card mt-5 space-y-2"><div className="flex items-center gap-2 text-xs font-semibold text-[#f59e0b] uppercase tracking-wider"><GothicIcon name="warning" size={13} /> {language === 'en' ? `Sending errors (${cp.errors.length})` : `Ошибки отправки (${cp.errors.length})`}</div><div className="max-h-40 overflow-y-auto space-y-1">{cp.errors.slice(-20).map((item, index) => <div key={index} className="text-xs font-mono text-[#ef4444]/80 bg-[#ef4444]/5 px-2.5 py-1 rounded">{item}</div>)}</div></div> : null}
  </div>
}
