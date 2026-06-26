"""
  FMailSender — Storage layer v6.0
  All read/write operations for accounts, proxies, recipients, campaign config.
  Data lives in data/ directory (created automatically).
  """
  from __future__ import annotations
  import json
  from pathlib import Path
  from cryptography.fernet import Fernet
  import base64, hashlib

  from core.models import SmtpAccount, Recipient, CampaignConfig

  DATA_DIR = Path(__file__).parent.parent / "data"
  DATA_DIR.mkdir(exist_ok=True)

  ACCOUNTS_FILE   = DATA_DIR / "accounts.json"
  PROXIES_FILE    = DATA_DIR / "global_proxies.json"
  RECIPIENTS_FILE = DATA_DIR / "recipients.json"
  CAMPAIGN_FILE   = DATA_DIR / "campaign.json"
  KEY_FILE        = DATA_DIR / ".fernet_key"


  # ── Encryption ───────────────────────────────────────────────────────────────

  def _get_key() -> bytes:
      if KEY_FILE.exists():
          return KEY_FILE.read_bytes()
      key = Fernet.generate_key()
      KEY_FILE.write_bytes(key)
      return key


  def _fernet() -> Fernet:
      return Fernet(_get_key())


  def _enc(s: str) -> str:
      try:
          return _fernet().encrypt(s.encode()).decode()
      except Exception:
          return s


  def _dec(s: str) -> str:
      try:
          return _fernet().decrypt(s.encode()).decode()
      except Exception:
          return s


  # ── Accounts ─────────────────────────────────────────────────────────────────

  def save_accounts(accounts: list[SmtpAccount]) -> None:
      data = []
      for a in accounts:
          d = a.to_dict()
          d["password"] = _enc(d["password"])
          if d.get("access_token"):
              d["access_token"] = _enc(d["access_token"])
          data.append(d)
      ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


  def load_accounts() -> list[SmtpAccount]:
      if not ACCOUNTS_FILE.exists():
          return []
      try:
          data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
          accounts = []
          for d in data:
              d["password"] = _dec(d.get("password", ""))
              if d.get("access_token"):
                  d["access_token"] = _dec(d["access_token"])
              # Proxy fields are session-only on load
              d["proxy"] = d.get("proxy", "")
              d["proxy_list"] = []
              accounts.append(SmtpAccount.from_dict(d))
          return accounts
      except Exception:
          return []


  # ── Proxies ──────────────────────────────────────────────────────────────────

  _proxy_cache: list[str] = []


  def save_proxies(proxies: list[str]) -> None:
      global _proxy_cache
      _proxy_cache = list(proxies)
      PROXIES_FILE.write_text(json.dumps(proxies, ensure_ascii=False, indent=2), encoding="utf-8")


  def load_proxies() -> list[str]:
      global _proxy_cache
      if _proxy_cache:
          return list(_proxy_cache)
      if PROXIES_FILE.exists():
          try:
              data = json.loads(PROXIES_FILE.read_text(encoding="utf-8"))
              _proxy_cache = [str(p) for p in data if p]
          except Exception:
              _proxy_cache = []
      return list(_proxy_cache)


  # ── Recipients ───────────────────────────────────────────────────────────────

  def save_recipients(recipients: list[Recipient]) -> None:
      RECIPIENTS_FILE.write_text(
          json.dumps([r.to_dict() for r in recipients], ensure_ascii=False, indent=2),
          encoding="utf-8"
      )


  def load_recipients() -> list[Recipient]:
      if not RECIPIENTS_FILE.exists():
          return []
      try:
          return [Recipient.from_dict(d) for d in json.loads(RECIPIENTS_FILE.read_text(encoding="utf-8"))]
      except Exception:
          return []


  # ── Campaign config ───────────────────────────────────────────────────────────

  def save_campaign(cfg: CampaignConfig) -> None:
      CAMPAIGN_FILE.write_text(
          json.dumps(cfg.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
      )


  def load_campaign() -> CampaignConfig:
      if not CAMPAIGN_FILE.exists():
          return CampaignConfig()
      try:
          d = json.loads(CAMPAIGN_FILE.read_text(encoding="utf-8"))
          return CampaignConfig(**d)
      except Exception:
          return CampaignConfig()
  