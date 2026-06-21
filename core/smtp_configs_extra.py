"""
FMailSender Extended SMTP Configs v1.0.0
Additional providers loaded at runtime into _SMTP_CONFIGS.
Add new providers here — not in sender.py.
"""
from __future__ import annotations


def load_extra_configs() -> dict[str, dict]:
    """Return extra SMTP configs to merge into sender._SMTP_CONFIGS."""
    return {
        # ── Transactional / Marketing SMTP ───────────────────────────────────
        # These require app credentials (username=API_KEY, password=API_KEY or secret)
        "sendgrid":    {"host": "smtp.sendgrid.net",                   "port": 587, "use_ssl": False, "use_tls": True},
        "mailgun":     {"host": "smtp.mailgun.org",                    "port": 587, "use_ssl": False, "use_tls": True},
        "postmark":    {"host": "smtp.postmarkapp.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "sparkpost":   {"host": "smtp.sparkpostmail.com",              "port": 587, "use_ssl": False, "use_tls": True},
        "brevo":       {"host": "smtp-relay.brevo.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "sendinblue":  {"host": "smtp-relay.brevo.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "elasticemail":{"host": "smtp.elasticemail.com",               "port": 2525,"use_ssl": False, "use_tls": True},
        "mailjet":     {"host": "in-v3.mailjet.com",                   "port": 587, "use_ssl": False, "use_tls": True},

        # ── Amazon SES ───────────────────────────────────────────────────────
        "ses-us-east":  {"host": "email-smtp.us-east-1.amazonaws.com",  "port": 465, "use_ssl": True, "use_tls": False},
        "ses-eu-west":  {"host": "email-smtp.eu-west-1.amazonaws.com",  "port": 465, "use_ssl": True, "use_tls": False},
        "ses-ap-south": {"host": "email-smtp.ap-southeast-1.amazonaws.com","port": 465,"use_ssl": True,"use_tls": False},

        # ── Privacy-focused ──────────────────────────────────────────────────
        # Fastmail
        "fastmail.com":  {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.fastmail.com", "imap_port": 993, "imap_ssl": True},
        "fastmail.fm":   {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.fastmail.com", "imap_port": 993, "imap_ssl": True},
        "fastmail.net":  {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False},
        # Tutanota (requires Tutanota Bridge — not standard SMTP)
        # "tutanota.com": NOT SUPPORTED — uses proprietary protocol
        # ProtonMail Bridge (local proxy required)
        "protonmail.com":{"host": "127.0.0.1",         "port": 1025, "use_ssl": False, "use_tls": False,
                          "_note": "Требуется ProtonMail Bridge (https://proton.me/mail/bridge). Без него — Connection refused на 127.0.0.1:1025"},
        "proton.me":     {"host": "127.0.0.1",         "port": 1025, "use_ssl": False, "use_tls": False},
        # mailbox.org определён в core/sender.py._SMTP_CONFIGS — дубликат удалён (FIX M1)

        # ── Asian providers ───────────────────────────────────────────────────
        "qq.com":        {"host": "smtp.qq.com",       "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.qq.com",  "imap_port": 993, "imap_ssl": True},
        "163.com":       {"host": "smtp.163.com",      "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.163.com", "imap_port": 993, "imap_ssl": True},
        "126.com":       {"host": "smtp.126.com",      "port": 465, "use_ssl": True,  "use_tls": False},
        "sina.com":      {"host": "smtp.sina.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "sina.cn":       {"host": "smtp.sina.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "sohu.com":      {"host": "smtp.sohu.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "naver.com":     {"host": "smtp.naver.com",    "port": 587, "use_ssl": False, "use_tls": True},
        "daum.net":      {"host": "smtp.daum.net",     "port": 465, "use_ssl": True,  "use_tls": False},
        "hanmail.net":   {"host": "smtp.daum.net",     "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Additional European ───────────────────────────────────────────────
        "libero.it":     {"host": "smtp.libero.it",    "port": 465, "use_ssl": True,  "use_tls": False},
        "virgilio.it":   {"host": "smtp.virgilio.it",  "port": 465, "use_ssl": True,  "use_tls": False},
        "tin.it":        {"host": "smtp.tin.it",       "port": 587, "use_ssl": False, "use_tls": True},
        "alice.it":      {"host": "smtp.alice.it",     "port": 587, "use_ssl": False, "use_tls": True},
        "tiscali.it":    {"host": "smtp.tiscali.it",   "port": 465, "use_ssl": True,  "use_tls": False},
        "seznam.cz":     {"host": "smtp.seznam.cz",    "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.seznam.cz", "imap_port": 993, "imap_ssl": True},
        "centrum.cz":    {"host": "smtp.centrum.cz",   "port": 465, "use_ssl": True,  "use_tls": False},
        "atlas.cz":      {"host": "smtp.atlas.cz",     "port": 465, "use_ssl": True,  "use_tls": False},
        "wp.pl":         {"host": "smtp.wp.pl",        "port": 465, "use_ssl": True,  "use_tls": False},
        "onet.pl":       {"host": "smtp.poczta.onet.pl","port": 465, "use_ssl": True, "use_tls": False},
        "interia.pl":    {"host": "poczta.interia.pl", "port": 465, "use_ssl": True,  "use_tls": False},
        "o2.pl":         {"host": "smtp.o2.pl",        "port": 465, "use_ssl": True,  "use_tls": False},
        "abv.bg":        {"host": "smtp.abv.bg",       "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Middle East ───────────────────────────────────────────────────────
        "walla.com":     {"host": "smtp.walla.com",    "port": 465, "use_ssl": True,  "use_tls": False},
        "012.net.il":    {"host": "smtp.012.net.il",   "port": 587, "use_ssl": False, "use_tls": True},

        # ── Latin America ─────────────────────────────────────────────────────
        "terra.com.br":  {"host": "smtp.terra.com.br", "port": 587, "use_ssl": False, "use_tls": True},
        "uol.com.br":    {"host": "smtp.uol.com.br",   "port": 587, "use_ssl": False, "use_tls": True},
        "bol.com.br":    {"host": "smtp.bol.com.br",   "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Africa / MENA ─────────────────────────────────────────────────────
        "mail.co.za":    {"host": "smtp.mail.co.za",   "port": 587, "use_ssl": False, "use_tls": True},

          # ── Poland (from official wp.pl, interia, onet docs) ────────────────
          "poczta.fm":      {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
          "interia.eu":     {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
          "op.pl":          {"host": "smtp.poczta.onet.pl",    "port": 465, "use_ssl": True,  "use_tls": False},
          "gazeta.pl":      {"host": "smtp.gazeta.pl",         "port": 465, "use_ssl": True,  "use_tls": False},
          "pisz.to":        {"host": "smtp.poczta.onet.pl",    "port": 465, "use_ssl": True,  "use_tls": False},
          "pacz.to":        {"host": "smtp.poczta.onet.pl",    "port": 465, "use_ssl": True,  "use_tls": False},
          "int.pl":         {"host": "smtp.int.pl",            "port": 587, "use_ssl": False, "use_tls": True},
          "vp.pl":          {"host": "smtp.vp.pl",             "port": 587, "use_ssl": False, "use_tls": True},
          "g.pl":           {"host": "smtp.g.pl",              "port": 465, "use_ssl": True,  "use_tls": False},
          "znajomi.pl":     {"host": "smtp.znajomi.pl",        "port": 465, "use_ssl": True,  "use_tls": False},
          "konto.pl":       {"host": "smtp.konto.pl",          "port": 465, "use_ssl": True,  "use_tls": False},


        # ── Interia group aliases (2gb.pl shares poczta.interia.pl infrastructure)
        "2gb.pl":         {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
        "intmail.pl":     {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
        "adresik.net":    {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
        "vip.interia.pl": {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
        "interia.com":    {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
        "ogarnij.se":     {"host": "poczta.interia.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
          # ── Czech / Slovak (official smtp.centrum.sk, volny.cz docs) ─────────
          "volny.cz":       {"host": "smtp.volny.cz",          "port": 465, "use_ssl": True,  "use_tls": False},
          "centrum.sk":     {"host": "smtp.centrum.sk",         "port": 465, "use_ssl": True,  "use_tls": False},
          "post.cz":        {"host": "smtp.post.cz",            "port": 465, "use_ssl": True,  "use_tls": False},
          "pobox.sk":       {"host": "smtp.pobox.sk",           "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Portugal (official smtp.sapo.pt docs) ────────────────────────────
          "sapo.pt":        {"host": "smtp.sapo.pt",            "port": 465, "use_ssl": True,  "use_tls": False,
                             "imap_host": "imap.sapo.pt",       "imap_port": 993, "imap_ssl": True},
          "portugalmail.pt":{"host": "smtp.portugalmailserver.com","port": 465,"use_ssl": True, "use_tls": False},

          # ── UK / Ireland (official BT, TalkTalk, Tiscali docs) ───────────────
          "btinternet.com": {"host": "mail.btinternet.com",     "port": 465, "use_ssl": True,  "use_tls": False},
          "bt.com":         {"host": "mail.btinternet.com",     "port": 465, "use_ssl": True,  "use_tls": False},
          "btopenworld.com":{"host": "mail.btinternet.com",     "port": 465, "use_ssl": True,  "use_tls": False},
          "talktalk.net":   {"host": "smtp.talktalk.net",       "port": 587, "use_ssl": False, "use_tls": True},
          "tiscali.co.uk":  {"host": "smtp.tiscali.co.uk",      "port": 587, "use_ssl": False, "use_tls": True},
          "blueyonder.co.uk":{"host": "smtp.talktalk.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "totalise.co.uk": {"host": "smtp.totalise.co.uk",     "port": 587, "use_ssl": False, "use_tls": True},
          "madasafish.com": {"host": "smtp.madasafish.com",     "port": 587, "use_ssl": False, "use_tls": True},
          "eircom.net":     {"host": "smtp.eircom.net",         "port": 587, "use_ssl": False, "use_tls": True},
          "lineone.net":    {"host": "smtp.lineone.net",        "port": 587, "use_ssl": False, "use_tls": True},
          "doctors.org.uk": {"host": "smtp.doctors.org.uk",    "port": 587, "use_ssl": False, "use_tls": True},

          # ── Belgium / Netherlands (official telenet.be, ziggo.nl, KPN docs) ──
          "telenet.be":     {"host": "smtp.telenet.be",         "port": 587, "use_ssl": False, "use_tls": True},
          "skynet.be":      {"host": "smtp.telenet.be",         "port": 587, "use_ssl": False, "use_tls": True},
          "pandora.be":     {"host": "smtp.telenet.be",         "port": 587, "use_ssl": False, "use_tls": True},
          "kpnmail.nl":     {"host": "smtp.kpnmail.nl",         "port": 587, "use_ssl": False, "use_tls": True},
          "kpnplanet.nl":   {"host": "smtp.kpnmail.nl",         "port": 587, "use_ssl": False, "use_tls": True},
          "ziggo.nl":       {"host": "smtp.ziggo.nl",           "port": 587, "use_ssl": False, "use_tls": True},
          "home.nl":        {"host": "smtp.home.nl",            "port": 587, "use_ssl": False, "use_tls": True},
          "hetnet.nl":      {"host": "smtp.hetnet.nl",          "port": 587, "use_ssl": False, "use_tls": True},
          "planet.nl":      {"host": "smtp.planet.nl",          "port": 587, "use_ssl": False, "use_tls": True},
          "upcmail.nl":     {"host": "smtp.upcmail.nl",         "port": 587, "use_ssl": False, "use_tls": True},
          "wxs.nl":         {"host": "smtp.ziggo.nl",           "port": 587, "use_ssl": False, "use_tls": True},
          "kabelfoon.net":  {"host": "smtp.ziggo.nl",           "port": 587, "use_ssl": False, "use_tls": True},
          "hccnet.nl":      {"host": "smtp.hccnet.nl",          "port": 587, "use_ssl": False, "use_tls": True},

          # ── Nordic (official telia, lyse/altibox docs) ────────────────────────
          "telia.com":      {"host": "mailout.telia.com",       "port": 465, "use_ssl": True,  "use_tls": False},
          "tele2.com":      {"host": "smtp.tele2.com",          "port": 587, "use_ssl": False, "use_tls": True},
          "lyse.net":       {"host": "smtp.altibox.no",         "port": 465, "use_ssl": True,  "use_tls": False},
          "haugnett.no":    {"host": "smtp.haugnett.no",        "port": 587, "use_ssl": False, "use_tls": True},

          # ── Swiss / Austrian (official bluewin.ch, a1.net docs) ──────────────
          "bluewin.ch":     {"host": "smtpauths.bluewin.ch",   "port": 465, "use_ssl": True,  "use_tls": False,
                             "imap_host": "imaps.bluewin.ch",  "imap_port": 993, "imap_ssl": True},
          "sunrise.ch":     {"host": "smtp.sunrise.ch",        "port": 465, "use_ssl": True,  "use_tls": False},
          "aon.at":         {"host": "securemail.a1.net",       "port": 465, "use_ssl": True,  "use_tls": False},
          "a1.net":         {"host": "securemail.a1.net",       "port": 465, "use_ssl": True,  "use_tls": False},
          "liwest.at":      {"host": "smtp.liwest.at",          "port": 587, "use_ssl": False, "use_tls": True},
          "inode.at":       {"host": "mail.inode.at",           "port": 587, "use_ssl": False, "use_tls": True},
          "utanet.at":      {"host": "mail.utanet.at",          "port": 587, "use_ssl": False, "use_tls": True},
          "vol.at":         {"host": "smtp.vol.at",             "port": 587, "use_ssl": False, "use_tls": True},
          "net2000.ch":     {"host": "smtp.net2000.ch",         "port": 587, "use_ssl": False, "use_tls": True},

          # ── Australia / New Zealand (official Telstra, iinet, Optus docs) ─────
          "bigpond.com":    {"host": "smtp.telstra.com",        "port": 587, "use_ssl": False, "use_tls": True},
          "bigpond.net.au": {"host": "smtp.telstra.com",        "port": 587, "use_ssl": False, "use_tls": True},
          "telstra.com":    {"host": "smtp.telstra.com",        "port": 587, "use_ssl": False, "use_tls": True},
          "iinet.net.au":   {"host": "smtp.iinet.net.au",      "port": 587, "use_ssl": False, "use_tls": True},
          "optusnet.com.au":{"host": "smtp.optusnet.com.au",   "port": 465, "use_ssl": True,  "use_tls": False},
          "westnet.com.au": {"host": "smtp.westnet.com.au",    "port": 587, "use_ssl": False, "use_tls": True},
          "internode.on.net":{"host": "mail.internode.on.net", "port": 587, "use_ssl": False, "use_tls": True},
          "hotkey.net.au":  {"host": "smtp.hotkey.net.au",     "port": 587, "use_ssl": False, "use_tls": True},
          "netspeed.com.au":{"host": "smtp.netspeed.com.au",   "port": 587, "use_ssl": False, "use_tls": True},
          "iprimus.com.au": {"host": "smtp.iprimus.com.au",    "port": 587, "use_ssl": False, "use_tls": True},
          "xtra.co.nz":     {"host": "smtp.xtra.co.nz",        "port": 465, "use_ssl": True,  "use_tls": False},
          "orcon.net.nz":   {"host": "smtp.orcon.net.nz",      "port": 587, "use_ssl": False, "use_tls": True},

          # ── Canada (official Bell, Videotron, Shaw, Cogeco docs) ─────────────
          "bell.net":       {"host": "smtp.bell.net",           "port": 465, "use_ssl": True,  "use_tls": False},
          "sympatico.ca":   {"host": "smtp.bell.net",           "port": 465, "use_ssl": True,  "use_tls": False},
          "videotron.ca":   {"host": "relais.videotron.ca",     "port": 465, "use_ssl": True,  "use_tls": False},
          "shaw.ca":        {"host": "smtp.shaw.ca",            "port": 587, "use_ssl": False, "use_tls": True},
          "cogeco.ca":      {"host": "mail.cogeco.ca",          "port": 587, "use_ssl": False, "use_tls": True},
          "cgocable.ca":    {"host": "mail.cogeco.ca",          "port": 587, "use_ssl": False, "use_tls": True},
          "istar.ca":       {"host": "smtp.istar.ca",           "port": 587, "use_ssl": False, "use_tls": True},
          "omnican.ca":     {"host": "smtp.omnican.ca",         "port": 587, "use_ssl": False, "use_tls": True},
          "wightman.ca":    {"host": "smtp.wightman.ca",        "port": 587, "use_ssl": False, "use_tls": True},

          # ── US ISPs (official Comcast, Charter/Spectrum, Juno docs) ──────────
          "comcast.net":    {"host": "smtp.comcast.net",        "port": 587, "use_ssl": False, "use_tls": True},
          "xfinity.com":    {"host": "smtp.comcast.net",        "port": 587, "use_ssl": False, "use_tls": True},
          "charter.net":    {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "roadrunner.com": {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "twc.com":        {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "spectrum.net":   {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "nc.rr.com":      {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "cfl.rr.com":     {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "nycap.rr.com":   {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "tampabay.rr.com":{"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "socal.rr.com":   {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "rochester.rr.com":{"host": "mobile.charter.net",     "port": 587, "use_ssl": False, "use_tls": True},
          "triad.rr.com":   {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "twcny.rr.com":   {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "wi.rr.com":      {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "woh.rr.com":     {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "tx.rr.com":      {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "hvc.rr.com":     {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "kc.rr.com":      {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "gt.rr.com":      {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "insight.rr.com": {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "hot.rr.com":     {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "neo.rr.com":     {"host": "mobile.charter.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "juno.com":       {"host": "smtp.juno.com",           "port": 465, "use_ssl": True,  "use_tls": False},
          "netzero.net":    {"host": "smtp.netzero.net",        "port": 465, "use_ssl": True,  "use_tls": False},
          "optonline.net":  {"host": "mail.optonline.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "midco.net":      {"host": "smtp.midco.net",          "port": 587, "use_ssl": False, "use_tls": True},
          "toast.net":      {"host": "smtp.toast.net",          "port": 587, "use_ssl": False, "use_tls": True},
          "hughes.net":     {"host": "smtp.hughes.net",         "port": 465, "use_ssl": True,  "use_tls": False},
          "nwlink.com":     {"host": "smtp.nwlink.com",         "port": 587, "use_ssl": False, "use_tls": True},
          "volcano.net":    {"host": "smtp.volcano.net",        "port": 587, "use_ssl": False, "use_tls": True},
          "ozone.net":      {"host": "smtp.ozone.net",          "port": 587, "use_ssl": False, "use_tls": True},
          "pipeline.com":   {"host": "smtp.pipeline.com",       "port": 587, "use_ssl": False, "use_tls": True},
          "usa.net":        {"host": "smtp.usa.net",            "port": 587, "use_ssl": False, "use_tls": True},
          "mindspring.com": {"host": "smtp.mindspring.com",     "port": 587, "use_ssl": False, "use_tls": True},
          "earthlink.net":  {"host": "smtp.earthlink.net",      "port": 587, "use_ssl": False, "use_tls": True},
          "tiac.net":       {"host": "smtp.tiac.net",           "port": 587, "use_ssl": False, "use_tls": True},
          "teleport.com":   {"host": "smtp.teleport.com",       "port": 587, "use_ssl": False, "use_tls": True},

          # ── Japan ISPs (nifty.com, various *.ne.jp — official docs) ──────────
          "nifty.com":      {"host": "smtp.nifty.com",          "port": 465, "use_ssl": True,  "use_tls": False,
                             "imap_host": "imap.nifty.com",     "imap_port": 993, "imap_ssl": True},
          "jcom.zaq.ne.jp": {"host": "smtp.jcom.ne.jp",        "port": 587, "use_ssl": False, "use_tls": True},
          "jcom.home.ne.jp":{"host": "smtp.jcom.ne.jp",        "port": 587, "use_ssl": False, "use_tls": True},
          "clovernet.ne.jp":{"host": "smtp.clovernet.ne.jp",   "port": 587, "use_ssl": False, "use_tls": True},
          "dream.jp":       {"host": "smtp.dream.jp",           "port": 587, "use_ssl": False, "use_tls": True},
          "rakuten.jp":     {"host": "smtp.rakuten.ne.jp",      "port": 587, "use_ssl": False, "use_tls": True},
          "yahoo.co.jp":    {"host": "smtp.mail.yahoo.co.jp",  "port": 465, "use_ssl": True,  "use_tls": False},
          "i.softbank.jp":  {"host": "smtp.softbank.ne.jp",    "port": 465, "use_ssl": True,  "use_tls": False},
          "docomo.ne.jp":   {"host": "smtp.spmode.ne.jp",      "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Taiwan (official HiNet/Chunghwa Telecom docs) ─────────────────────
          "hinet.net":      {"host": "ms35.hinet.net",          "port": 25,  "use_ssl": False, "use_tls": False},
          "msa.hinet.net":  {"host": "ms35.hinet.net",          "port": 25,  "use_ssl": False, "use_tls": False},

          # ── Korea ─────────────────────────────────────────────────────────────
          "nate.com":       {"host": "smtp.nate.com",           "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Israel (official Netvision/013 docs) ──────────────────────────────
          "netvision.net.il":{"host": "smtp.netvision.net.il",  "port": 587, "use_ssl": False, "use_tls": True},
          "013net.net":     {"host": "smtp.netvision.net.il",   "port": 587, "use_ssl": False, "use_tls": True},
          "012.net.il":     {"host": "smtp.012.net.il",         "port": 587, "use_ssl": False, "use_tls": True},

          # ── South Africa ──────────────────────────────────────────────────────
          "mweb.co.za":     {"host": "smtp.mweb.co.za",        "port": 465, "use_ssl": True,  "use_tls": False},
          "telkomsa.net":   {"host": "smtp.telkom.net",         "port": 587, "use_ssl": False, "use_tls": True},
          "mail.bg":        {"host": "smtp.mail.bg",            "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Greece ────────────────────────────────────────────────────────────
          "otenet.gr":      {"host": "mailgate.otenet.gr",      "port": 587, "use_ssl": False, "use_tls": True},

          # ── France (official Orange/SFR docs) ─────────────────────────────────
          "orange.fr":      {"host": "smtp.orange.fr",          "port": 465, "use_ssl": True,  "use_tls": False},
          "wanadoo.fr":     {"host": "smtp.orange.fr",          "port": 465, "use_ssl": True,  "use_tls": False},
          "sfr.fr":         {"host": "smtp.sfr.fr",             "port": 465, "use_ssl": True,  "use_tls": False},
          "cegetel.net":    {"host": "smtp.sfr.fr",             "port": 465, "use_ssl": True,  "use_tls": False},
          "numericable.com":{"host": "smtp.sfr.fr",             "port": 465, "use_ssl": True,  "use_tls": False},
          "neuf.fr":        {"host": "smtp.sfr.fr",             "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Latin America (official docs) ──────────────────────────────────────
          "adinet.com.uy":  {"host": "smtp.adinet.com.uy",     "port": 587, "use_ssl": False, "use_tls": True},
          "montevideo.com.uy":{"host": "smtp.montevideo.com.uy","port": 587, "use_ssl": False, "use_tls": True},
          "ig.com.br":      {"host": "smtp.ig.com.br",         "port": 587, "use_ssl": False, "use_tls": True},

          # ── Singapore ─────────────────────────────────────────────────────────
          "singnet.com.sg": {"host": "smtp.singnet.com.sg",    "port": 587, "use_ssl": False, "use_tls": True},

          # ── Hungary ───────────────────────────────────────────────────────────
          "freemail.hu":    {"host": "smtp.freemail.hu",       "port": 465, "use_ssl": True,  "use_tls": False},
          "t-online.hu":    {"host": "smtp.t-online.hu",       "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Tunisia / Algeria ─────────────────────────────────────────────────
          "topnet.tn":      {"host": "smtp.topnet.tn",         "port": 587, "use_ssl": False, "use_tls": True},
          "gnet.tn":        {"host": "smtp.gnet.tn",           "port": 587, "use_ssl": False, "use_tls": True},
          "gcb.dz":         {"host": "smtp.gcb.dz",            "port": 587, "use_ssl": False, "use_tls": True},

          # ── Privacy / Alternative providers ───────────────────────────────────
          "ik.me":          {"host": "smtp.ik.me",             "port": 465, "use_ssl": True,  "use_tls": False},
          "murena.io":      {"host": "smtp.murena.io",         "port": 465, "use_ssl": True,  "use_tls": False},
          "lilo.org":       {"host": "smtp.lilo.org",          "port": 587, "use_ssl": False, "use_tls": True},
          "mailo.com":      {"host": "mail.mailo.com",         "port": 465, "use_ssl": True,  "use_tls": False},
          "pobox.com":      {"host": "smtp.pobox.com",         "port": 587, "use_ssl": False, "use_tls": True},
          "infomaniak.ch":  {"host": "mail.infomaniak.com",    "port": 465, "use_ssl": True,  "use_tls": False},
          "net-c.com":      {"host": "mail.net-c.com",         "port": 465, "use_ssl": True,  "use_tls": False},
          "mail.com":       {"host": "smtp.mail.com",          "port": 465, "use_ssl": True,  "use_tls": False},
          "email.com":      {"host": "smtp.mail.com",          "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Croatia / Bosnia ──────────────────────────────────────────────────
          "net.hr":         {"host": "smtp.net.hr",            "port": 465, "use_ssl": True,  "use_tls": False},
          "vip.hr":         {"host": "smtp.vip.hr",            "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Luxembourg ────────────────────────────────────────────────────────
          "pt.lu":          {"host": "smtp.pt.lu",             "port": 465, "use_ssl": True,  "use_tls": False},

          # ── Denmark ───────────────────────────────────────────────────────────
          "mail.dk":        {"host": "smtp.mail.dk",           "port": 587, "use_ssl": False, "use_tls": True},
          "mail.tele.dk":   {"host": "smtp.tele.dk",           "port": 587, "use_ssl": False, "use_tls": True},
          "post.tele.dk":   {"host": "smtp.tele.dk",           "port": 587, "use_ssl": False, "use_tls": True},
          "youmail.dk":     {"host": "smtp.youmail.dk",        "port": 587, "use_ssl": False, "use_tls": True},
          "os.dk":          {"host": "smtp.os.dk",             "port": 587, "use_ssl": False, "use_tls": True},
      }
