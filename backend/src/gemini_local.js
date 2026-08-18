'use strict'

const axios = require('axios')

const GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
const MODEL = 'gemini-2.5-flash'
const MAX_HTML = 20_000
const MAX_TEXT = 8_000
const MAX_BRIEF = 1_200
const DANGEROUS_BLOCKS = /<(script|iframe|object|embed|form)\b[^>]*>[\s\S]*?<\/\1\s*>/gi
const EVENT_ATTRS = /\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi
const SCRIPT_URLS = /(href|src)\s*=\s*(["'])\s*(?:javascript:|data:text\/html)[^"']*\2/gi

function cleanHtml(value) {
  return String(value || '').replace(DANGEROUS_BLOCKS, '').replace(EVENT_ATTRS, '').replace(SCRIPT_URLS, '$1="#"').trim()
}

function publicError(error) {
  const status = Number(error?.response?.status || 0)
  if (status === 401 || status === 403) return 'Gemini отклонил ключ. Проверьте ключ и его ограничения.'
  if (status === 429) return 'Лимит Gemini исчерпан. Повторите попытку позже.'
  if (status >= 400 && status < 500) return 'Gemini не принял запрос. Проверьте модель и параметры ключа.'
  return 'Gemini временно недоступен. Повторите попытку позже.'
}

function extractText(payload) {
  for (const step of payload?.steps || []) {
    if (step?.type !== 'model_output') continue
    for (const block of step?.content || []) if (block?.type === 'text' && typeof block.text === 'string') return block.text
  }
  throw new Error('Gemini не вернул текстовый результат.')
}

function parseResult(text) {
  let source = String(text || '').trim().replace(/^```(?:json)?\s*|\s*```$/gi, '')
  let data
  try { data = JSON.parse(source) } catch { throw new Error('Gemini вернул некорректный формат шаблона.') }
  const subject = String(data?.subject || '').trim()
  const bodyHtml = cleanHtml(data?.body_html)
  const bodyText = String(data?.body_text || '').trim()
  if (!subject || !bodyHtml || !bodyText || subject.length > 180 || bodyHtml.length > MAX_HTML || bodyText.length > MAX_TEXT) throw new Error('Gemini вернул неполный или слишком большой шаблон.')
  return { subject, body_html: bodyHtml, body_text: bodyText, model: MODEL }
}

function buildPayload({ mode, brief, subject, body_html: bodyHtml, body_text: bodyText }) {
  if (!['generate', 'refine'].includes(mode)) throw new Error('Неизвестный режим AI-операции.')
  if (brief.length > MAX_BRIEF || subject.length > 180 || bodyHtml.length > MAX_HTML || bodyText.length > MAX_TEXT) throw new Error('Превышен допустимый размер запроса AI.')
  if (mode === 'generate' && !brief) throw new Error('Опишите цель и аудиторию шаблона.')
  if (mode === 'refine' && !(subject || bodyHtml || bodyText)) throw new Error('Добавьте содержимое шаблона для улучшения.')
  const instruction = 'You are an email template editor for legitimate, consent-based communication. Return only a JSON object with subject, body_html, and body_text. Produce readable, accessible HTML with inline-safe styles, a visible unsubscribe placeholder {{unsubscribe_url}}, and a plain-text alternative. Preserve valid {{name}}, {{email}}, {{company}} placeholders. Do not use hidden text, tracking pixels, obfuscated text, spintax, misleading claims, scripts, forms, iframes, or instructions intended to evade spam filters. Do not invent personal facts.'
  const task = mode === 'generate' ? `Create a new template from this brief: ${brief}` : 'Improve clarity, accessibility and honest call-to-action of this user-owned template without changing its intent.'
  return {
    model: MODEL, store: false,
    input: [instruction, task, `Brief: ${brief}`, `Subject: ${subject}`, `HTML: ${bodyHtml}`, `Text: ${bodyText}`].join('\n\n'),
    response_format: { type: 'text', mime_type: 'application/json', schema: { type: 'object', properties: { subject: { type: 'string' }, body_html: { type: 'string' }, body_text: { type: 'string' } }, required: ['subject', 'body_html', 'body_text'] } },
  }
}

async function createTemplateWithPersonalKey({ apiKey, mode, brief = '', subject = '', body_html = '', body_text = '' }) {
  const key = String(apiKey || '').trim()
  if (!/^[A-Za-z0-9_-]{20,256}$/.test(key)) throw new Error('Введите корректный Gemini API-ключ.')
  const payload = buildPayload({ mode, brief: String(brief).trim(), subject: String(subject).trim(), body_html: String(body_html), body_text: String(body_text).trim() })
  try {
    const response = await axios.post(GEMINI_URL, payload, { headers: { 'x-goog-api-key': key, 'Content-Type': 'application/json' }, timeout: 45_000, proxy: false, validateStatus: status => status >= 200 && status < 300 })
    return parseResult(extractText(response.data))
  } catch (error) {
    if (error instanceof Error && !error.response) {
      if (/^(Gemini|Введите|Опишите|Добавьте|Превышен)/.test(error.message)) throw error
    }
    throw new Error(publicError(error))
  }
}

module.exports = { createTemplateWithPersonalKey, cleanHtml, parseResult, buildPayload, publicError }
