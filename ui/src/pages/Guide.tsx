import { GothicIcon } from '../components/GothicIcon'
import { useI18n } from '../i18n'

const STEPS = [
  ['guide.step1', 'guide.step1text'],
  ['guide.step2', 'guide.step2text'],
  ['guide.step3', 'guide.step3text'],
  ['guide.step4', 'guide.step4text'],
  ['guide.step5', 'guide.step5text'],
  ['guide.step6', 'guide.step6text'],
  ['guide.step7', 'guide.step7text'],
] as const

export default function Guide() {
  const { t } = useI18n()
  return (
    <div className="page flex-1">
      <div className="page-header">
        <div>
          <h1 className="page-title flex items-center gap-2"><GothicIcon name="guide" size={20} className="text-purple-light" />{t('guide.title')}</h1>
          <p className="page-sub">{t('guide.sub')}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.75fr)] gap-5">
        <section className="card divide-y divide-dim/35 p-0 overflow-hidden">
          {STEPS.map(([title, text]) => (
            <div key={title} className="p-4">
              <h2 className="text-sm font-semibold text-text">{t(title)}</h2>
              <p className="mt-1.5 text-sm leading-6 text-muted">{t(text)}</p>
            </div>
          ))}
        </section>

        <aside className="card h-fit space-y-3">
          <div className="flex items-center gap-2 text-purple-light"><GothicIcon name="key" size={16} /><h2 className="text-sm font-semibold text-text">{t('guide.keyTitle')}</h2></div>
          <p className="text-sm leading-6 text-muted">{t('guide.keyText')}</p>
          <a className="btn btn-secondary btn-sm w-full justify-center" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
            Google AI Studio <GothicIcon name="external" size={13} />
          </a>
        </aside>
      </div>
    </div>
  )
}
