import { useEffect, useState } from 'react'
import { api } from '../api'
import { GothicIcon } from '../components/GothicIcon'
import { useI18n } from '../i18n'

function readBool(key: string, fallback: boolean): boolean {
  const raw = localStorage.getItem(key)
  return raw === null ? fallback : raw === '1'
}

export default function Settings() {
  const { t } = useI18n()
  const [animated, setAnimated] = useState(() => readBool('fmail-animated-bg', true))
  const [closeWarning, setCloseWarning] = useState(() => readBool('fmail-close-warning', true))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  function syncCloseWarning(value: boolean) {
    const bridge = (window as Window & { fmailApp?: { setCloseWarningEnabled?: (enabled: boolean) => Promise<boolean> } }).fmailApp
    void bridge?.setCloseWarningEnabled?.(value)
  }

  useEffect(() => { syncCloseWarning(closeWarning) }, [closeWarning])

  function setPreference(key: string, value: boolean, setter: (v: boolean) => void) {
    setter(value)
    if (key === 'fmail-close-warning') syncCloseWarning(value)
    localStorage.setItem(key, value ? '1' : '0')
    if (key === 'fmail-animated-bg') window.dispatchEvent(new CustomEvent('fmail:background', { detail: value }))
  }

  async function clearConfig(scope: 'all' | 'accounts' | 'campaign' | 'recipients' | 'proxies' | 'license') {
    if (!window.confirm(t(scope === 'all' ? 'settings.clearAllConfirm' : 'settings.clearConfirm'))) return
    setBusy(true); setMessage('')
    try {
      await api.settings.clear(scope)
      setMessage(t('settings.clearDone'))
      window.dispatchEvent(new Event('fmail:status:refresh'))
    } catch {
      setMessage(t('settings.clearFailed'))
    } finally { setBusy(false) }
  }

  return <section className="space-y-6">
    <header><div className="nocturne-kicker">{t('nav.settings')}</div><h1 className="mt-2 text-3xl font-black tracking-tight text-text">{t('settings.title')}</h1><p className="mt-1 text-sm text-muted">{t('settings.sub')}</p></header>
    <div className="grid gap-5 xl:grid-cols-2">
      <div className="card p-5 space-y-4">
        <div className="flex items-start gap-3"><GothicIcon name="settings" size={20} className="mt-0.5 text-purple-light"/><div><h2 className="font-bold text-text">{t('settings.behavior')}</h2><p className="mt-1 text-xs text-muted">{t('settings.behaviorHint')}</p></div></div>
        <label className="flex items-center justify-between gap-4 rounded-lg border border-dim/40 bg-surface/40 p-3"><span><span className="block text-sm font-semibold text-text">{t('settings.animated')}</span><span className="mt-1 block text-xs text-muted">{t('settings.animatedHint')}</span></span><input type="checkbox" checked={animated} onChange={e => setPreference('fmail-animated-bg', e.target.checked, setAnimated)} /></label>
        <label className="flex items-center justify-between gap-4 rounded-lg border border-dim/40 bg-surface/40 p-3"><span><span className="block text-sm font-semibold text-text">{t('settings.closeWarning')}</span><span className="mt-1 block text-xs text-muted">{t('settings.closeWarningHint')}</span></span><input type="checkbox" checked={closeWarning} onChange={e => setPreference('fmail-close-warning', e.target.checked, setCloseWarning)} /></label>
      </div>
      <div className="card p-5 space-y-4">
        <div className="flex items-start gap-3"><GothicIcon name="delete" size={20} className="mt-0.5 text-error"/><div><h2 className="font-bold text-text">{t('settings.data')}</h2><p className="mt-1 text-xs text-muted">{t('settings.dataHint')}</p></div></div>
        <div className="grid gap-2 sm:grid-cols-2">
          <button className="btn btn-secondary justify-center" disabled={busy} onClick={() => clearConfig('accounts')}><GothicIcon name="accounts" size={14}/>{t('settings.clearAccounts')}</button>
          <button className="btn btn-secondary justify-center" disabled={busy} onClick={() => clearConfig('recipients')}><GothicIcon name="recipients" size={14}/>{t('settings.clearRecipients')}</button>
          <button className="btn btn-secondary justify-center" disabled={busy} onClick={() => clearConfig('proxies')}><GothicIcon name="proxies" size={14}/>{t('settings.clearProxies')}</button>
          <button className="btn btn-secondary justify-center" disabled={busy} onClick={() => clearConfig('campaign')}><GothicIcon name="compose" size={14}/>{t('settings.clearCampaign')}</button>
        </div>
        <button className="btn btn-danger w-full justify-center" disabled={busy} onClick={() => clearConfig('all')}><GothicIcon name="delete" size={14}/>{t('settings.clearAll')}</button>
        {message && <p className="text-xs text-muted" role="status">{message}</p>}
      </div>
    </div>
    <div className="card-inset p-4 text-xs text-muted"><span className="font-semibold text-text">{t('settings.author')}</span> <span className="font-mono">@ftpdev_sup</span></div>
  </section>
}
