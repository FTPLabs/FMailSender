/**
   * FMailSender — HTTP client v6.0
   * All requests to the Python FastAPI core go through this file.
   * Base URL: http://127.0.0.1:7531
   */
  import axios from 'axios'

  const BASE = 'http://127.0.0.1:7531'
  const http = axios.create({ baseURL: BASE, timeout: 30_000 })

  // ── Types ─────────────────────────────────────────────────────────────────────

  export interface Account {
    email: string
    password: string
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
    // Health
    health: () => http.get('/api/health').then(r => r.data),

    // Accounts
    accounts: {
      list:      ()                   => http.get<Account[]>('/api/accounts').then(r => r.data),
      add:       (a: Partial<Account>) => http.post<Account>('/api/accounts', a).then(r => r.data),
      update:    (email: string, a: Partial<Account>) => http.put<Account>(`/api/accounts/${encodeURIComponent(email)}`, a).then(r => r.data),
      delete:    (email: string)      => http.delete(`/api/accounts/${encodeURIComponent(email)}`).then(r => r.data),
      test:      (a: Partial<Account>) => http.post<{ok:boolean;message:string}>('/api/accounts/test', a).then(r => r.data),
      testAll:   ()                   => http.post('/api/accounts/test-all').then(r => r.data),
      importTxt: (file: File)         => { const fd = new FormData(); fd.append('file', file); return http.post('/api/accounts/import-txt', fd).then(r => r.data) },
    },

    // Proxies
    proxies: {
      list:       ()                   => http.get<{proxies:string[];count:number}>('/api/proxies').then(r => r.data),
      set:        (proxies: string[])  => http.post('/api/proxies', {proxies}).then(r => r.data),
      check:      (proxies?: string[]) => http.post('/api/proxies/check', {proxies}).then(r => r.data),
      distribute: ()                   => http.post('/api/proxies/distribute').then(r => r.data),
    },

    // Recipients
    recipients: {
      list:       ()                      => http.get<{recipients:Recipient[];count:number}>('/api/recipients').then(r => r.data),
      set:        (recipients: Recipient[]) => http.post('/api/recipients', {recipients}).then(r => r.data),
      importTxt:  (file: File)            => { const fd = new FormData(); fd.append('file', file); return http.post('/api/recipients/import-txt', fd).then(r => r.data) },
      clear:      ()                      => http.delete('/api/recipients').then(r => r.data),
    },

    // Campaign
    campaign: {
      get:    ()                      => http.get('/api/campaign').then(r => r.data),
      save:   (cfg: Partial<CampaignConfig>) => http.post('/api/campaign', cfg).then(r => r.data),
      start:  ()                      => http.post('/api/campaign/start').then(r => r.data),
      pause:  ()                      => http.post('/api/campaign/pause').then(r => r.data),
      stop:   ()                      => http.post('/api/campaign/stop').then(r => r.data),
    },

    // Status
    status: () => http.get<AppStatus>('/api/status').then(r => r.data),
  }
  