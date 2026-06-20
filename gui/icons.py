"""
FMailSender icon set v3.6.2
Icons as unicode symbols + emoji for sidebar nav and buttons.
For production, replace with actual SVG QIcon loading.
"""


class Icons:
    # Nav
    DASHBOARD   = "📊"
    ACCOUNTS    = "👤"
    RECIPIENTS  = "📋"
    COMPOSE     = "✉️"
    SENDING     = "🚀"
    INBOX       = "📥"
    SETTINGS    = "⚙️"
    LICENSE     = "🔑"

    # Status
    SUCCESS     = "✅"
    ERROR       = "❌"
    WARNING     = "⚠️"
    INFO        = "ℹ️"
    LOADING     = "⏳"
    ONLINE      = "🟢"
    OFFLINE     = "🔴"

    # Actions
    ADD         = "+"
    REMOVE      = "−"
    REFRESH     = "↻"
    UPLOAD      = "↑"
    DOWNLOAD    = "↓"
    COPY        = "⎘"
    EDIT        = "✏️"
    DELETE      = "🗑"
    CHECK       = "✓"
    SEARCH      = "🔍"
    FILTER      = "⚡"
    STOP        = "■"
    PLAY        = "▶"
    PAUSE       = "⏸"
    EXPORT      = "↗"
    IMPORT      = "↙"

    # SMTP / Email
    SMTP        = "📡"
    BOUNCE      = "↩"
    REPLY       = "↩"
    SEND        = "→"
    ATTACH      = "📎"
    HTML        = "<>"
    PLAIN       = "≡"


# Sidebar navigation definitions (id, label, icon)
NAV_ITEMS = [
    ("dashboard",   "Дашборд",     Icons.DASHBOARD),
    ("accounts",    "Аккаунты",    Icons.ACCOUNTS),
    ("recipients",  "Получатели",  Icons.RECIPIENTS),
    ("compose",     "Письмо",      Icons.COMPOSE),
    ("sending",     "Рассылка",    Icons.SENDING),
    ("inbox",       "Входящие",    Icons.INBOX),
]
