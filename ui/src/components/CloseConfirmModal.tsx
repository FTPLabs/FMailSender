import { useEffect, useState } from 'react'
import { GothicIcon } from './GothicIcon'
import { useI18n } from '../i18n'

type CloseChoice = 'clear' | 'keep' | 'cancel'
type FmailBridge = {
  onCloseRequest?: (callback: () => void) => () => void
  resolveClose?: (choice: CloseChoice) => void
}

export default function CloseConfirmModal() {
  const { language } = useI18n()
  const [open, setOpen] = useState(false)
  const bridge = (window as Window & { fmailApp?: FmailBridge }).fmailApp

  useEffect(() => {
    const unsubscribe = bridge?.onCloseRequest?.(() => setOpen(true))
    return () => unsubscribe?.()
  }, [bridge])

  const choose = (choice: CloseChoice) => {
    setOpen(false)
    bridge?.resolveClose?.(choice)
  }

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') choose('cancel')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null
  const en = language === 'en'
  return <div className="close-modal-backdrop" role="presentation" onMouseDown={event => { if (event.currentTarget === event.target) choose('cancel') }}>
    <section className="close-modal" role="dialog" aria-modal="true" aria-labelledby="close-modal-title">
      <div className="close-modal-mark"><GothicIcon name="warning" size={22} /></div>
      <div className="close-modal-kicker">NOCTURNE // EXIT PROTOCOL</div>
      <h2 id="close-modal-title">{en ? 'Close FMailSender?' : 'Закрыть FMailSender?'}</h2>
      <p>{en ? 'Choose what to do with locally stored accounts, recipients and campaign data.' : 'Выберите, что сделать с локально сохранёнными аккаунтами, получателями и данными кампании.'}</p>
      <div className="close-modal-actions">
        <button type="button" className="btn btn-danger" onClick={() => choose('clear')}><GothicIcon name="delete" size={15} />{en ? 'Clear data and exit' : 'Очистить данные и выйти'}</button>
        <button type="button" className="btn btn-secondary" onClick={() => choose('keep')}>{en ? 'Exit without clearing' : 'Выйти без очистки'}</button>
        <button type="button" className="btn btn-ghost" onClick={() => choose('cancel')}>{en ? 'Cancel' : 'Отмена'}</button>
      </div>
    </section>
  </div>
}
