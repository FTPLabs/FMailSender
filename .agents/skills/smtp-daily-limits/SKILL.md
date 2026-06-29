# SKILL: SMTP Daily Limits (Official)

## Purpose
Provides official SMTP daily/hourly sending limits per provider.
Prevents account blocks caused by exceeding provider limits.

## Module
`core/smtp_limits.py`

## Usage

```python
from core.smtp_limits import get_limits, get_daily_limit, get_hourly_limit, apply_limits_to_account

# Get full limits for a domain
lim = get_limits("user@gmail.com")
# → {"daily": 500, "hourly": 100, "notes": "...", "source": "..."}

# Quick shortcuts
daily = get_daily_limit("gmail.com")   # 500
hourly = get_hourly_limit("gmx.com")   # 30

# Auto-apply to account on import
apply_limits_to_account(account)
```

## Official Limits Table

| Provider | Daily | Hourly | Notes |
|---|---|---|---|
| Gmail (personal) | 500 | 100 | App Password required. Source: support.google.com/mail/answer/22839 |
| Gmail (Workspace) | 2000 | 400 | Business accounts |
| Outlook.com (consumer) | 300 | 50 | Source: support.microsoft.com |
| Yahoo | 500 | 100 | App Password required. Source: help.yahoo.com/kb/SLN3403.html |
| GMX (.com/.net/.de) | 100 | 30 | ⚠️ Datacenter IPs blocked — use residential proxies |
| GMX US (.us) | 100 | 30 | Different endpoint: smtp.gmx.com |
| Web.de | 500 | 100 | GMX infrastructure |
| Yandex | 500 | 100 | App Password required |
| Mail.ru | 500 | 100 | App Password if 2FA enabled |
| Rambler | 500 | 100 | Plain password, no 2FA |
| iCloud | 1000 | 200 | App-Specific Password required |
| Zoho (free) | 200 | 50 | Source: zoho.com/mail/help/smtp-access.html |
| FastMail | 1000 | 200 | App Password required |
| AOL | 500 | 100 | Yahoo infrastructure |
| T-Online | 500 | 100 | SSL port 465 |
| Ukr.net | 500 | 100 | App Password required |

## Critical Notes

### GMX — Residential Proxies Only
GMX (.com, .net, .de, .at, .ch, .co.uk, .fr, .es) **blocks datacenter IPs**.
Symptom: "SMTP AUTH не поддерживается сервером" error even with correct credentials.
Fix: Use residential (ISP) or mobile proxies only for GMX accounts.

### Gmail — App Password Required
Regular Gmail password won't work with 3rd-party SMTP since May 2022.
Steps: Google Account → Security → 2-Step Verification → App Passwords → Mail

### Yahoo — App Password Required  
Since March 2021. Steps: security.yahoo.com → Manage App Passwords

### Outlook — SMTP AUTH May Be Disabled
Microsoft 365 may have SmtpClientAuthentication disabled.
Error: "5.7.139 Authentication unsuccessful — SmtpClientAuthentication is disabled"
Fix: Admin Center → Users → Active Users → [user] → Mail → Manage Email Apps → Authenticated SMTP

### Microsoft OAuth2 (Outlook/Hotmail/Live)
Preferred over App Password. Use refresh_token import format:
`email|password|refresh_token`
The code auto-rotates access_token via refresh_token using public client IDs.
Public client IDs used (may be revoked by Microsoft):
- `9e5f94bc-e8a4-4e73-b8be-63364c29d753` (Outlook iOS)
- `08162f7c-0fd2-4200-a84a-f25a4db0b584` (Thunderbird)
- `d3590ed6-52b3-4102-aeff-aad2292ab01c` (Microsoft Office)

## When to Use This Skill
- Importing accounts: auto-set daily_limit from official limits
- UI display: show limits next to account type
- Rate limiter: enforce per-domain thresholds
- Debugging blocks: check if limit was exceeded
