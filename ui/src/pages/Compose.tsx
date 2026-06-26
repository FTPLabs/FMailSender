import { useEffect, useState } from 'react'
  import { Save, Eye, EyeOff, Code } from 'lucide-react'
  import { api, type CampaignConfig } from '../api'

  const PLACEHOLDERS = [
    { tag: '{{name}}',    desc: 'Имя получателя' },
    { tag: '{{email}}',   desc: 'Email получателя' },
    { tag: '{{domain}}',  desc: 'Домен отправителя' },
    { tag: '{{date}}',    desc: 'Текущая дата' },
    { tag: '{{random}}',  desc: 'Случайная строка' },
  ]

  export default function Compose() {
    const [cfg, setCfg]           = useState<Partial<CampaignConfig>>({
      subject: '', body_html: '', body_text: '', from_name: '',
      reply_to: '', delay_min: 1, delay_max: 3, daily_limit_per_account: 500,
    })
    const [preview, setPreview]   = useState(false)
    const [htmlMode, setHtmlMode] = useState(true)
    const [saved, setSaved]       = useState(false)
    const [loading, setLoading]   = useState(true)

    useEffect(() => {
      api.campaign.get().then(d => {
        setCfg({
          subject: d.subject ?? '', body_html: d.body_html ?? '',
          body_text: d.body_text ?? '', from_name: d.from_name ?? '',
          reply_to: d.reply_to ?? '', delay_min: d.delay_min ?? 1,
          delay_max: d.delay_max ?? 3, daily_limit_per_account: d.daily_limit_per_account ?? 500,
        })
        setLoading(false)
      }).catch(() => setLoading(false))
    }, [])

    async function save() {
      await api.campaign.save(cfg)
      setSaved(true); setTimeout(() => setSaved(false), 2000)
    }

    if (loading) return <div className="text-muted text-center py-12">Загрузка...</div>

    return (
      <div className="space-y-5 animate-fade-in max-w-4xl">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text">Письмо</h1>
            <p className="text-muted text-sm mt-1">Тема, тело и настройки рассылки</p>
          </div>
          <button onClick={save} className="btn-primary">
            <Save size={14} />
            {saved ? '✓ Сохранено!' : 'Сохранить'}
          </button>
        </div>

        {/* Sender info */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-text">Отправитель</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Имя отправителя</label>
              <input className="input" placeholder="Company Name" value={cfg.from_name ?? ''}
                onChange={e => setCfg(c => ({...c, from_name: e.target.value}))} />
            </div>
            <div>
              <label className="label">Reply-To (необяз.)</label>
              <input className="input" placeholder="reply@example.com" value={cfg.reply_to ?? ''}
                onChange={e => setCfg(c => ({...c, reply_to: e.target.value}))} />
            </div>
          </div>
          <div>
            <label className="label">Тема письма</label>
            <input className="input" placeholder="Привет, {{name}}! Специальное предложение..." value={cfg.subject ?? ''}
              onChange={e => setCfg(c => ({...c, subject: e.target.value}))} />
          </div>
        </div>

        {/* Body */}
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">Тело письма</h2>
            <div className="flex items-center gap-2">
              <button onClick={() => setHtmlMode(!htmlMode)}
                className={`btn-secondary text-xs py-1 ${htmlMode ? 'text-cyan border-cyan/30' : ''}`}>
                <Code size={12} /> {htmlMode ? 'HTML' : 'Текст'}
              </button>
              <button onClick={() => setPreview(!preview)} className="btn-secondary text-xs py-1">
                {preview ? <EyeOff size={12} /> : <Eye size={12} />}
                {preview ? 'Скрыть' : 'Превью'}
              </button>
            </div>
          </div>

          {/* Placeholders */}
          <div className="flex flex-wrap gap-1.5">
            {PLACEHOLDERS.map(p => (
              <button key={p.tag}
                onClick={() => {
                  const field = htmlMode ? 'body_html' : 'body_text'
                  setCfg(c => ({...c, [field]: ((c[field] as string) ?? '') + p.tag}))
                }}
                title={p.desc}
                className="text-xs bg-surf3 text-muted hover:text-purple hover:bg-purple/10 px-2 py-0.5 rounded font-mono transition-colors">
                {p.tag}
              </button>
            ))}
          </div>

          {htmlMode ? (
            <textarea className="input font-mono text-xs leading-relaxed resize-none"
              style={{ height: '320px' }}
              placeholder="<h1>Привет, {{name}}!</h1>&#10;<p>Ваш email: {{email}}</p>"
              value={cfg.body_html ?? ''}
              onChange={e => setCfg(c => ({...c, body_html: e.target.value}))} />
          ) : (
            <textarea className="input font-mono text-xs leading-relaxed resize-none"
              style={{ height: '320px' }}
              placeholder="Привет, {{name}}!&#10;&#10;Текстовая версия письма..."
              value={cfg.body_text ?? ''}
              onChange={e => setCfg(c => ({...c, body_text: e.target.value}))} />
          )}

          {preview && cfg.body_html && (
            <div className="border border-text-dim/20 rounded-lg overflow-hidden">
              <div className="bg-surf3 px-3 py-1.5 text-xs text-muted border-b border-text-dim/20">
                Превью HTML ({{name}} → Иван)
              </div>
              <iframe
                className="w-full bg-white"
                style={{ height: '300px' }}
                srcDoc={(cfg.body_html ?? '').replace(/{{name}}/g, 'Иван').replace(/{{email}}/g, 'ivan@example.com')}
              />
            </div>
          )}
        </div>

        {/* Sending settings */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-text">Настройки отправки</h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Задержка мин. (сек)</label>
              <input className="input" type="number" min="0.1" step="0.1" value={cfg.delay_min ?? 1}
                onChange={e => setCfg(c => ({...c, delay_min: +e.target.value}))} />
            </div>
            <div>
              <label className="label">Задержка макс. (сек)</label>
              <input className="input" type="number" min="0.1" step="0.1" value={cfg.delay_max ?? 3}
                onChange={e => setCfg(c => ({...c, delay_max: +e.target.value}))} />
            </div>
            <div>
              <label className="label">Дневной лимит/аккаунт</label>
              <input className="input" type="number" min="1" value={cfg.daily_limit_per_account ?? 500}
                onChange={e => setCfg(c => ({...c, daily_limit_per_account: +e.target.value}))} />
            </div>
          </div>
        </div>
      </div>
    )
  }
  