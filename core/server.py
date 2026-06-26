"""
  FMailSender — FastAPI Server v6.0
  All HTTP endpoints. Runs on localhost:7531.
  The React frontend (Tauri WebView) talks to this server.

  Endpoints:
    GET    /api/health
    GET    /api/accounts           → list accounts
    POST   /api/accounts           → add account
    PUT    /api/accounts/{email}   → update account
    DELETE /api/accounts/{email}   → delete account
    POST   /api/accounts/test      → test single SMTP connection
    POST   /api/accounts/test-all  → test all accounts (streaming)
    GET    /api/proxies            → list proxies
    POST   /api/proxies            → set proxy list
    POST   /api/proxies/check      → check proxy list (streaming)
    POST   /api/proxies/distribute → distribute proxies to accounts
    GET    /api/recipients         → list recipients
    POST   /api/recipients         → set recipients list
    POST   /api/recipients/import  → import from txt file
    GET    /api/campaign           → get campaign config + status
    POST   /api/campaign           → save campaign config
    POST   /api/campaign/start     → start sending
    POST   /api/campaign/pause     → pause sending
    POST   /api/campaign/stop      → stop sending
    GET    /api/status             → current campaign status (polling)
  """
  from __future__ import annotations

  import asyncio
  import time
  from pathlib import Path
  from typing import Optional

  from fastapi import FastAPI, HTTPException, UploadFile, File
  from fastapi.middleware.cors import CORSMiddleware
  from fastapi.responses import StreamingResponse
  from pydantic import BaseModel

  from core.models import SmtpAccount, Recipient, CampaignConfig, CampaignStatus
  from core.storage import (
      save_accounts, load_accounts,
      save_proxies, load_proxies,
      save_recipients, load_recipients,
      save_campaign, load_campaign,
  )
  from core.proxy import ProxyManager, parse_proxy, validate_proxy
  from core.validator import validate_account, validate_accounts_batch
  from core._version import APP_VERSION

  app = FastAPI(title="FMailSender Core", version=APP_VERSION)

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_methods=["*"],
      allow_headers=["*"],
  )

  # ── Global state ──────────────────────────────────────────────────────────────
  _accounts: list[SmtpAccount] = []
  _proxies: list[str] = []
  _recipients: list[Recipient] = []
  _campaign_cfg: CampaignConfig = CampaignConfig()
  _campaign_status: CampaignStatus = CampaignStatus()
  _sending_task: Optional[asyncio.Task] = None


  @app.on_event("startup")
  async def _startup():
      global _accounts, _proxies, _recipients, _campaign_cfg
      _accounts    = load_accounts()
      _proxies     = load_proxies()
      _recipients  = load_recipients()
      _campaign_cfg = load_campaign()


  # ── Pydantic request/response models ─────────────────────────────────────────

  class AccountIn(BaseModel):
      email: str
      password: str
      host: str
      port: int = 465
      use_ssl: bool = True
      use_tls: bool = False
      display_name: str = ""
      daily_limit: int = 500
      hourly_limit: int = 50
      is_active: bool = True
      proxy: str = ""
      proxy_list: list[str] = []
      imap_host: str = ""
      imap_port: int = 993
      imap_ssl: bool = True


  class CampaignIn(BaseModel):
      subject: str = ""
      body_html: str = ""
      body_text: str = ""
      from_name: str = ""
      reply_to: str = ""
      delay_min: float = 1.0
      delay_max: float = 3.0
      daily_limit_per_account: int = 500


  # ── Health ────────────────────────────────────────────────────────────────────

  @app.get("/api/health")
  def health():
      return {"ok": True, "version": APP_VERSION}


  # ── Accounts ──────────────────────────────────────────────────────────────────

  @app.get("/api/accounts")
  def get_accounts():
      return [a.to_dict() for a in _accounts]


  @app.post("/api/accounts")
  def add_account(body: AccountIn):
      global _accounts
      # Check for duplicate
      if any(a.email.lower() == body.email.lower() for a in _accounts):
          raise HTTPException(400, f"Account {body.email} already exists")
      acc = SmtpAccount(
          email=body.email, password=body.password, host=body.host,
          port=body.port, use_ssl=body.use_ssl, use_tls=body.use_tls,
          display_name=body.display_name, daily_limit=body.daily_limit,
          hourly_limit=body.hourly_limit, is_active=body.is_active,
          proxy=body.proxy, proxy_list=body.proxy_list,
          imap_host=body.imap_host, imap_port=body.imap_port, imap_ssl=body.imap_ssl,
      )
      _accounts.append(acc)
      save_accounts(_accounts)
      return acc.to_dict()


  @app.put("/api/accounts/{email}")
  def update_account(email: str, body: AccountIn):
      global _accounts
      idx = next((i for i, a in enumerate(_accounts) if a.email.lower() == email.lower()), None)
      if idx is None:
          raise HTTPException(404, "Account not found")
      acc = SmtpAccount(
          email=body.email, password=body.password, host=body.host,
          port=body.port, use_ssl=body.use_ssl, use_tls=body.use_tls,
          display_name=body.display_name, daily_limit=body.daily_limit,
          hourly_limit=body.hourly_limit, is_active=body.is_active,
          proxy=body.proxy, proxy_list=body.proxy_list,
          imap_host=body.imap_host, imap_port=body.imap_port, imap_ssl=body.imap_ssl,
      )
      _accounts[idx] = acc
      save_accounts(_accounts)
      return acc.to_dict()


  @app.delete("/api/accounts/{email}")
  def delete_account(email: str):
      global _accounts
      before = len(_accounts)
      _accounts = [a for a in _accounts if a.email.lower() != email.lower()]
      if len(_accounts) == before:
          raise HTTPException(404, "Account not found")
      save_accounts(_accounts)
      return {"ok": True}


  @app.post("/api/accounts/test")
  async def test_account(body: AccountIn):
      acc = SmtpAccount(
          email=body.email, password=body.password, host=body.host,
          port=body.port, use_ssl=body.use_ssl, use_tls=body.use_tls,
          proxy=body.proxy, proxy_list=body.proxy_list,
      )
      ok, msg = await validate_account(acc)
      # Update last_test_ok if account exists in list
      for a in _accounts:
          if a.email.lower() == body.email.lower():
              a.last_test_ok = ok
              a.last_test_msg = msg
              if ok:
                  a.is_active = True
              break
      save_accounts(_accounts)
      return {"ok": ok, "message": msg}


  @app.post("/api/accounts/test-all")
  async def test_all_accounts():
      """Stream NDJSON results as each account is tested."""
      import json

      async def _stream():
          def _on_result(i, ok, msg):
              pass  # handled in generator

          results: list[tuple[bool, str] | None] = [None] * len(_accounts)
          sem = asyncio.Semaphore(4)

          async def _one(i, acc):
              async with sem:
                  ok, msg = await validate_account(acc)
                  results[i] = (ok, msg)
                  for a in _accounts:
                      if a.email.lower() == acc.email.lower():
                          a.last_test_ok = ok
                          a.last_test_msg = msg
                          a.is_active = ok if ok or any(
                              kw in msg.lower() for kw in ["535", "534", "password", "invalid credentials"]
                          ) else a.is_active
                          break
                  yield json.dumps({"index": i, "email": acc.email, "ok": ok, "message": msg}) + "\n"

          tasks = [asyncio.create_task(_one(i, acc)) for i, acc in enumerate(_accounts)]
          # Collect from generators
          for t in asyncio.as_completed(tasks):
              result_gen = await t
              async for line in result_gen:
                  yield line

          save_accounts(_accounts)
          ok_cnt  = sum(1 for a in _accounts if a.last_test_ok is True)
          fail_cnt= sum(1 for a in _accounts if a.last_test_ok is False)
          yield json.dumps({"done": True, "ok": ok_cnt, "failed": fail_cnt, "total": len(_accounts)}) + "\n"

      # Simpler non-streaming version that returns all results
      ok_results = []
      sem = asyncio.Semaphore(4)

      async def _one(i, acc):
          async with sem:
              ok, msg = await validate_account(acc)
              for a in _accounts:
                  if a.email.lower() == acc.email.lower():
                      a.last_test_ok = ok
                      a.last_test_msg = msg
                      break
              ok_results.append({"index": i, "email": acc.email, "ok": ok, "message": msg})

      await asyncio.gather(*[_one(i, acc) for i, acc in enumerate(_accounts)])
      save_accounts(_accounts)
      ok_cnt   = sum(1 for a in _accounts if a.last_test_ok is True)
      fail_cnt = sum(1 for a in _accounts if a.last_test_ok is False)
      return {
          "results": sorted(ok_results, key=lambda x: x["index"]),
          "ok": ok_cnt,
          "failed": fail_cnt,
          "total": len(_accounts),
      }


  @app.post("/api/accounts/import-txt")
  async def import_accounts_txt(file: UploadFile = File(...)):
      """Import accounts from email:password text file."""
      content = (await file.read()).decode("utf-8", errors="replace")
      lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
      existing = {a.email.lower() for a in _accounts}
      imported, skipped = 0, 0
      for line in lines:
          for sep in ["|", ";", ":"]:
              parts = line.split(sep)
              if len(parts) >= 2:
                  email, pwd = parts[0].strip(), parts[1].strip()
                  if "@" in email and email.lower() not in existing:
                      from core.sender import get_smtp_config_for_domain
                      domain = email.split("@")[-1].lower()
                      cfg = get_smtp_config_for_domain(domain) or {}
                      acc = SmtpAccount(
                          email=email, password=pwd,
                          host=cfg.get("host", ""),
                          port=cfg.get("port", 465),
                          use_ssl=cfg.get("use_ssl", True),
                          use_tls=cfg.get("use_tls", False),
                      )
                      _accounts.append(acc)
                      existing.add(email.lower())
                      imported += 1
                  else:
                      skipped += 1
                  break
      # Assign global proxies to new accounts
      if _proxies:
          start = len(_accounts) - imported
          pm = ProxyManager(_proxies)
          pm.distribute(_accounts[start:], start)
      save_accounts(_accounts)
      return {"imported": imported, "skipped": skipped, "total": len(_accounts)}


  # ── Proxies ───────────────────────────────────────────────────────────────────

  @app.get("/api/proxies")
  def get_proxies():
      return {"proxies": _proxies, "count": len(_proxies)}


  @app.post("/api/proxies")
  def set_proxies(body: dict):
      global _proxies
      raw = body.get("proxies", [])
      _proxies = [p for r in raw if (p := parse_proxy(r))]
      save_proxies(_proxies)
      return {"count": len(_proxies)}


  @app.post("/api/proxies/check")
  async def check_proxies(body: dict):
      """Check all proxies in the list. Returns results."""
      raw = body.get("proxies", _proxies)
      to_check = [p for r in raw if (p := parse_proxy(r))]
      results = []
      for proxy in to_check:
          result = await asyncio.get_event_loop().run_in_executor(None, validate_proxy, proxy)
          results.append(result)
      valid = [r for r in results if r["ok"]]
      smtp_ok = [r for r in results if r.get("smtp_ok")]
      return {"results": results, "valid": len(valid), "smtp_ok": len(smtp_ok), "total": len(to_check)}


  @app.post("/api/proxies/distribute")
  def distribute_proxies_to_accounts():
      global _accounts
      if not _proxies:
          raise HTTPException(400, "No proxies loaded")
      pm = ProxyManager(_proxies)
      pm.distribute(_accounts)
      save_accounts(_accounts)
      return {"distributed": len(_accounts), "proxies": len(_proxies)}


  # ── Recipients ────────────────────────────────────────────────────────────────

  @app.get("/api/recipients")
  def get_recipients():
      return {"recipients": [r.to_dict() for r in _recipients], "count": len(_recipients)}


  @app.post("/api/recipients")
  def set_recipients(body: dict):
      global _recipients
      _recipients = [Recipient.from_dict(d) for d in body.get("recipients", [])]
      save_recipients(_recipients)
      return {"count": len(_recipients)}


  @app.post("/api/recipients/import-txt")
  async def import_recipients_txt(file: UploadFile = File(...)):
      content = (await file.read()).decode("utf-8", errors="replace")
      lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
      added = 0
      existing = {r.email.lower() for r in _recipients}
      for line in lines:
          parts = line.split("|")
          email = parts[0].strip()
          name  = parts[1].strip() if len(parts) > 1 else ""
          if "@" in email and email.lower() not in existing:
              _recipients.append(Recipient(email=email, name=name))
              existing.add(email.lower())
              added += 1
      save_recipients(_recipients)
      return {"added": added, "total": len(_recipients)}


  @app.delete("/api/recipients")
  def clear_recipients():
      global _recipients
      _recipients = []
      save_recipients(_recipients)
      return {"ok": True}


  # ── Campaign ──────────────────────────────────────────────────────────────────

  @app.get("/api/campaign")
  def get_campaign():
      return {**_campaign_cfg.__dict__, "status": _campaign_status.to_dict()}


  @app.post("/api/campaign")
  def update_campaign(body: CampaignIn):
      global _campaign_cfg
      _campaign_cfg = CampaignConfig(**body.model_dump())
      save_campaign(_campaign_cfg)
      return {"ok": True}


  @app.post("/api/campaign/start")
  async def start_campaign():
      global _sending_task, _campaign_status
      if _campaign_status.state == "running":
          raise HTTPException(400, "Campaign already running")
      if not _accounts:
          raise HTTPException(400, "No accounts loaded")
      if not _recipients:
          raise HTTPException(400, "No recipients loaded")
      from core.sender import SendingEngine
      active = [a for a in _accounts if a.is_active and a.last_test_ok is True]
      if not active:
          raise HTTPException(400, "No validated active accounts. Run account test first.")
      _campaign_status = CampaignStatus(
          state="running", total=len(_recipients), started_at=time.time()
      )
      engine = SendingEngine(
          accounts=active,
          recipients=_recipients,
          config=_campaign_cfg,
          on_progress=lambda sent, failed, total, email, account: _update_status(sent, failed, total, email, account),
          on_error=lambda err: _campaign_status.errors.append(err),
      )
      _sending_task = asyncio.create_task(_run_engine(engine))
      return {"ok": True, "total": len(_recipients), "accounts": len(active)}


  def _update_status(sent, failed, total, email, account):
      _campaign_status.sent = sent
      _campaign_status.failed = failed
      _campaign_status.total = total
      _campaign_status.current_email = email
      _campaign_status.current_account = account


  async def _run_engine(engine):
      global _campaign_status
      try:
          await engine.run()
          _campaign_status.state = "done"
      except asyncio.CancelledError:
          _campaign_status.state = "idle"
      except Exception as e:
          _campaign_status.state = "error"
          _campaign_status.errors.append(str(e))


  @app.post("/api/campaign/pause")
  def pause_campaign():
      global _campaign_status
      if _campaign_status.state == "running":
          _campaign_status.state = "paused"
      return _campaign_status.to_dict()


  @app.post("/api/campaign/stop")
  async def stop_campaign():
      global _sending_task, _campaign_status
      if _sending_task and not _sending_task.done():
          _sending_task.cancel()
          try:
              await _sending_task
          except asyncio.CancelledError:
              pass
      _campaign_status.state = "idle"
      return {"ok": True}


  @app.get("/api/status")
  def get_status():
      ok_cnt   = sum(1 for a in _accounts if a.last_test_ok is True)
      fail_cnt = sum(1 for a in _accounts if a.last_test_ok is False)
      return {
          "campaign": _campaign_status.to_dict(),
          "accounts": {
              "total": len(_accounts),
              "valid": ok_cnt,
              "invalid": fail_cnt,
              "untested": len(_accounts) - ok_cnt - fail_cnt,
              "ready": sum(1 for a in _accounts if a.is_active and a.last_test_ok is True),
          },
          "recipients": len(_recipients),
          "proxies": len(_proxies),
      }
  