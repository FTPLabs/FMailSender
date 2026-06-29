import { useEffect, useState } from 'react'
import { Save, Eye, EyeOff, FileText } from 'lucide-react'
import { api, type CampaignConfig } from '../api'

const TAGS = [
  { tag: '{{name}}',   desc: 'Имя получателя' },
  { tag: '{{email}}',  desc: 'Email получателя' },
  { tag: '{{domain}}', desc: 'Домен отправителя' },
  { tag: '{{date}}',   desc: 'Текущая дата' },
  { tag: '{{random}}', desc: 'Случайная строка' },
]

const EMPTY: Partial<CampaignConfig> = {
  subject: '', body_html: '', body_text: '', from_name: '',
  reply_to: '', delay_min: 1, delay_max: 3, daily_limit_per_account: 500,
}

export default function Compose() {
  const [cfg, setCfg]       = useState<Partial<CampaignConfig>>(EMPTY)
  const [preview, setPrev]  = useState(false)
  const [htmlMode, setHtml] = useState(true)
  const [saved, setSaved]   = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.campaign.get()
      .then(d => setCfg({
        subject: d.subject ?? '', body_html: d.body_html ?? '',
        body_text: d.body_text ?? '', from_name: d.from_name ?? '',
        reply_to: d.reply_to ?? '', delay_min: d.delay_min ?? 1,
        delay_max: d.delay_max ?? 3, daily_limit_per_account: d.daily_limit_per_account ?? 500,
      }))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  function set(k: keyof CampaignConfig, v: any) { setCfg(c => ({ ...c, [k]: v })) }

  async function save() {
    await api.campaign.save(cfg)
    setSaved(true); setTimeout(() => setSaved(false), 2000)
  }

  function insertTag(tag: string) {
    const field = htmlMode ? 'body_html' : 'body_text'
    setCfg(c => ({ ...c, [field]: ((c[field] as string) ?? '') + tag }))
  }

  if (loading) {
    return <div className="empty py-24"><div className="text-sm">Загрузка...</div></div>
  }

  return (
    <div className="page flex-1 flex flex-col">
      <div className="page-header">
        <div>
          <h1 className="page-title">Письмо</h1>
          <p className="page-sub">Тема, тело и настройки рассылки</p>
        </div>
        <button onClick={save} className="btn btn-primary">
          <Save size={14} />
          {saved ? '✓ Сохранено' : 'Сохранить'}
        </button>
      </div>

      {/* Top row: Sender + Send settings — 1 col on narrow, 2 cols on wide */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Sender */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-[#e8e8ff]">Отправитель</h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Имя отправителя</label>
              <input className="input" placeholder="Company Name" value={cfg.from_name ?? ''}
                onChange={e => set('from_name', e.target.value)} />
            </div>
            <div>
              <label className="label">Reply-To (необязательно)</label>
              <input className="input" placeholder="reply@example.com" value={cfg.reply_to ?? ''}
                onChange={e => set('reply_to', e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">Тема письма</label>
            <input className="input" placeholder="Привет, {{name}}! Специальное предложение..."
              value={cfg.subject ?? ''} onChange={e => set('subject', e.target.value)} />
          </div>
        </div>

        {/* Send settings */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-[#e8e8ff]">Настройки отправки</h2>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Задержка мин. (сек)</label>
              <input className="input" type="number" min="0.1" step="0.1" value={cfg.delay_min ?? 1}
                onChange={e => set('delay_min', +e.target.value)} />
            </div>
            <div>
              <label className="label">Задержка макс. (сек)</label>
              <input className="input" type="number" min="0.1" step="0.1" value={cfg.delay_max ?? 3}
                onChange={e => set('delay_max', +e.target.value)} />
            </div>
            <div>
              <label className="label">Дневной лимит / аккаунт</label>
              <input className="input" type="number" min="1" value={cfg.daily_limit_per_account ?? 500}
                onChange={e => set('daily_limit_per_account', +e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-[#6666aa]">
            Между каждым письмом будет ожидание от <span className="text-[#e8e8ff]">{cfg.delay_min}с</span>{' '}
            до <span className="text-[#e8e8ff]">{cfg.delay_max}с</span>. Не ставьте меньше 1с — многие серверы блокируют.
          </p>
        </div>
      </div>

      {/* Body — fills remaining height */}
      <div className="card flex-1 flex flex-col space-y-3 min-h-0">
        <div className="flex items-center justify-between flex-shrink-0">
          <h2 className="text-sm font-semibold text-[#e8e8ff]">Тело письма</h2>
          <div className="flex items-center gap-2">
            <button onClick={() => setHtml(!htmlMode)}
              className={`btn btn-secondary btn-sm ${htmlMode ? 'text-[#06b6d4] border-[#06b6d4]/30' : ''}`}>
              <FileText size={12} /> {htmlMode ? 'HTML' : 'Текст'}
            </button>
            <button onClick={() => setPrev(!preview)} className="btn btn-secondary btn-sm">
              {preview ? <EyeOff size={12} /> : <Eye size={12} />}
              {preview ? 'Скрыть' : 'Превью'}
            </button>
          </div>
        </div>

        {/* Tag shortcuts */}
        <div className="flex flex-wrap gap-1.5 flex-shrink-0">
          {TAGS.map(p => (
            <button key={p.tag} onClick={() => insertTag(p.tag)} title={p.desc}
              className="text-xs bg-[#1c1c35] text-[#6666aa] hover:text-[#a78bfa] hover:bg-[#8b5cf6]/10
                         px-2 py-0.5 rounded font-mono transition-colors">
              {p.tag}
            </button>
          ))}
        </div>

        {!preview ? (
          <textarea
            className="input font-mono text-xs leading-relaxed resize-none flex-1"
            style={{ minHeight: '200px' }}
            placeholder={htmlMode
              ? '<h1>Привет, {{name}}!</h1>\n<p>Ваш email: {{email}}</p>'
              : 'Привет, {{name}}!\n\nТекстовая версия письма...'}
            value={(htmlMode ? cfg.body_html : cfg.body_text) ?? ''}
            onChange={e => set(htmlMode ? 'body_html' : 'body_text', e.target.value)}
            spellCheck={false}
          />
        ) : (
          <div className="flex-1 flex flex-col border border-[#3a3a66]/40 rounded-lg overflow-hidden min-h-0">
            <div className="bg-[#1c1c35] px-3 py-1.5 text-xs text-[#6666aa] border-b border-[#3a3a66]/30 flex-shrink-0">
              Превью HTML — {'{{name}}'} → Иван
            </div>
            <iframe className="w-full flex-1 bg-white"
              style={{ minHeight: '200px' }}
              srcDoc={(cfg.body_html ?? '')
                .replace(/{{name}}/g, 'Иван')
                .replace(/{{email}}/g, 'ivan@example.com')
                .replace(/{{date}}/g, new Date().toLocaleDateString('ru-RU'))
              }
              sandbox="allow-same-origin"
            />
          </div>
        )}
      </div>
    </div>
  )
}
