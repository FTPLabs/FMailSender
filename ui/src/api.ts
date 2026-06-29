/**
 * FMailSender — HTTP client v6.1
 *
 * VPN-compatible: probes both 127.0.0.1 and localhost to find the working
 * address before the first API call. Some VPN clients intercept or block
 * connections to 127.0.0.1 while leaving 'localhost' untouched (or vice-versa).
 *
 * Security:
 *   withCredentials: false — never attaches cookies/auth headers to requests.
 *   The backend only listens on loopback anyway, but being explicit is safer.
 */
import axios, { type AxiosInstance } from 'axios'

const CORE_PORT  = 7531
const CANDIDATES = ['http://127.0.0.1', 'http://localhost']

let _baseUrl = `${CANDIDATES[0]}:${CORE_PORT}`
let _http: AxiosInstance = _makeClient(_baseUrl)

function _makeClient(base: string): AxiosInstance {
  return axios.create({ baseURL: base, timeout: 30_000, withCredentials: false })
}

/**
 * Probe candidate hosts and use the first that responds.
 * Falls back silently if all are unreachable (normal during startup window).
 * Called once at startup by StatusContext before the first poll.
 */
export async function initBaseUrl(): Promise<void> {
  for (const host of CANDIDATES) {
    const url = `${host}:${CORE_PORT}`
    try {
      await axios.get(`${url}/api/health`, { timeout: 2_000, withCredentials: false })
      _baseUrl = url
      _http    = _makeClient(url)
      return
    } catch { /* try next candidate */ }
  }
  // all candidates unreachable — keep 127.0.0.1 as default, StatusContext retries
}

/** Current resolved base URL (e.g. "http://127.0.0.1:7531") */
export function getBaseUrl(): string { return _baseUrl }

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Account {
  email: string
  password: string
  refresh_token: string
  access_token: string
  host: string
  port: number
  use_ssl: boolean
  use_tls: boolean
  display_name: string
  daily_limit: number
  hourly_limit: number
  is_active: boolean
  proxy: string
  proxy_list: string[]
  imap_host: string
  imap_port: number
  imap_ssl: boolean
  last_test_ok: boolean | null
  last_test_msg: string
  sent_today: number
  sent_this_hour: number
}

export interface Recipient {
  email: string
  name: string
  variables: Record<string, string>
}

export interface CampaignConfig {
  subject: string
  body_html: string
  body_text: string
  from_name: string
  reply_to: string
  delay_min: number
  delay_max: number
  daily_limit_per_account: number
}

export interface CampaignStatus {
  state: 'idle' | 'running' | 'paused' | 'done' | 'error'
  sent: number
  failed: number
  total: number
  progress_pct: number
  current_email: string
  current_account: string
  started_at: number
  errors: string[]
}

export interface AppStatus {
  campaign: CampaignStatus
  accounts: { total: number; valid: number; invalid: number; untested: number; ready: number }
  recipients: number
  proxies: number
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  health: () => _http.get('/api/health').then(r => r.data),

  accounts: {
    list:      ()                    => _http.get<Account[]>('/api/accounts').then(r => r.data),
    add:       (a: Partial<Account>) => _http.post<Account>('/api/accounts', a).then(r => r.data),
    update:    (email: string, a: Partial<Account>) =>
                 _http.put<Account>(`/api/accounts/${encodeURIComponent(email)}`, a).then(r => r.data),
    delete:    (email: string)       => _http.delete(`/api/accounts/${encodeURIComponent(email)}`).then(r => r.data),
    test:      (a: Partial<Account>) => _http.post<{ok:boolean;message:string}>('/api/accounts/test', a).then(r => r.data),
    testAll:   ()                    => _http.post('/api/accounts/test-all').then(r => r.data),
    importTxt: (file: File)          => {
      const fd = new FormData()
      fd.append('file', file)
      return _http.post('/api/accounts/import-txt', fd).then(r => r.data)
    },
  },

  proxies: {
    list:       ()                   => _http.get<{proxies:string[];count:number}>('/api/proxies').then(r => r.data),
    set:        (proxies: string[])  => _http.post('/api/proxies', {proxies}).then(r => r.data),
    check:      (proxies?: string[]) => _http.post('/api/proxies/check', {proxies}).then(r => r.data),
    distribute: ()                   => _http.post('/api/proxies/distribute').then(r => r.data),
  },

  recipients: {
    list:      ()                        => _http.get<{recipients:Recipient[];count:number}>('/api/recipients').then(r => r.data),
    set:       (recipients: Recipient[]) => _http.post('/api/recipients', {recipients}).then(r => r.data),
    importTxt: (file: File)              => {
      const fd = new FormData()
      fd.append('file', file)
      return _http.post('/api/recipients/import-txt', fd).then(r => r.data)
    },
    clear:     ()                        => _http.delete('/api/recipients').then(r => r.data),
  },

  campaign: {
    get:    ()                             => _http.get('/api/campaign').then(r => r.data),
    save:   (cfg: Partial<CampaignConfig>) => _http.post('/api/campaign', cfg).then(r => r.data),
    start:  ()                             => _http.post('/api/campaign/start').then(r => r.data),
    pause:  ()                             => _http.post('/api/campaign/pause').then(r => r.data),
    resume: ()                             => _http.post('/api/campaign/resume').then(r => r.data),
    stop:   ()                             => _http.post('/api/campaign/stop').then(r => r.data),
  },

  status: () => _http.get<AppStatus>('/api/status').then(r => r.data),

    license: {
      get: () => _http.get('/api/license').then(r => r.data),
      activate: (key: string) => _http.post('/api/license/activate', { key }).then(r => r.data),
    },
  }
