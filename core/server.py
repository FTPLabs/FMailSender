"""
FMailSender — FastAPI Server v6.1
All HTTP endpoints on localhost:7531.

Key design:
  - Our models.py SmtpAccount is duck-compatible with sender.py SmtpAccount (same fields).
  - SendingEngine.run() is synchronous; run it in a daemon thread.
  - engine.on_progress(sent, total, result) and engine.on_finished(results) are set as attributes.

Endpoints:
  GET  /api/health
  CRUD /api/accounts
  POST /api/accounts/test         test single account SMTP
  POST /api/accounts/test-all     test all accounts (concurrency=4)
  POST /api/accounts/import-txt   import email:password file
  GET/POST /api/proxies           list / set proxy list
  POST /api/proxies/check         check all proxies
  POST /api/proxies/distribute    assign proxies round-robin to accounts
  GET/POST /api/recipients        list / set recipients
  POST /api/recipients/import-txt import email|name file
  DELETE /api/recipients          clear all recipients
  GET/POST /api/campaign          get or save campaign config
  POST /api/campaign/start        start sending campaign
  POST /api/campaign/pause        pause (engine._paused = True)
  POST /api/campaign/resume       resume (engine._paused = False)
  POST /api/campaign/stop         stop (engine.stop_event.set())
  GET  /api/status                overall status (poll every 1-3s from frontend)
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.models import SmtpAccount, Recipient, CampaignConfig, CampaignStatus
from core.storage import (
    save_accounts, load_accounts, save_proxies, load_proxies,
    save_recipients, load_recipients, save_campaign, load_campaign,
)
from core.proxy import ProxyManager, parse_proxy, validate_proxy
from core._version import APP_VERSION

# sender.py types used for actual campaign execution
from core.sender import (
    Recipient as SenderRecipient,
    CampaignConfig as SenderConfig,
    EmailTemplate,
    SendingEngine,
    get_smtp_config_for_domain,
    test_smtp_connection,
)

# ── Global mutable state ──────────────────────────────────────────────────────
_accounts: list[SmtpAccount]  = []
_proxies:  list[str]          = []
_recipients: list[Recipient]  = []
_campaign_cfg: CampaignConfig = CampaignConfig()
_campaign_status: CampaignStatus = CampaignStatus()
_engine: Optional[SendingEngine] = None
_engine_thread: Optional[threading.Thread] = None

# Run token: incremented on every start/stop so stale thread callbacks are ignored.
_run_id: int = 0

# Lock guarding all reads/writes to _campaign_status from mixed async+thread contexts.
# CPython GIL prevents crashes, but this lock ensures coherent multi-field snapshots.
_status_lock = threading.Lock()

# ── License runtime state ─────────────────────────────────────────────────────
# Set at startup via _lifespan; updated on every GET /api/license call and
# by the periodic background checker (every LICENSE_RECHECK_INTERVAL_SECS).
_license_ok: bool = False
_license_lock = threading.Lock()

# Signal used to stop the periodic checker cleanly on shutdown.
_license_check_stop = threading.Event()

LICENSE_RECHECK_INTERVAL_SECS = 3600  # 1 hour


def _set_license_ok(ok: bool) -> None:
    global _license_ok
    with _license_lock:
        _license_ok = ok


def _get_license_ok() -> bool:
    with _license_lock:
        return _license_ok


def _stop_campaign_if_running() -> None:
    """Stop the active campaign (if any) — called when license is revoked."""
    global _engine
    with _status_lock:
        if _engine is not None:
            try:
                _engine.stop_event.set()
            except Exception:
                pass
        _campaign_status.state = "idle"


def _periodic_license_checker() -> None:
    """Background thread: re-validates the license every LICENSE_RECHECK_INTERVAL_SECS.

    Uses validate_on_startup() which:
      - Always contacts the license server (no cache shortcut).
      - Revokes immediately when server returns valid=False.
      - Allows offline grace period only on genuine network errors.

    If the license is found invalid the campaign is stopped and _license_ok
    is set to False, so the middleware blocks all further API calls until
    the user re-activates.
    """
    import logging as _logging
    _log = _logging.getLogger("fmailsender.license.periodic")

    while not _license_check_stop.wait(timeout=LICENSE_RECHECK_INTERVAL_SECS):
        # wait() returns True when the stop event is set → exit immediately.
        if _license_check_stop.is_set():
            break

        _log.info("Periodic license check …")
        try:
            from core.license import validate_on_startup
            result = validate_on_startup()
            is_valid = bool(result.get("valid", False))
            _set_license_ok(is_valid)
            if not is_valid:
                _log.warning(
                    "License invalid (periodic check): %s — stopping campaign",
                    result.get("message", ""),
                )
                _stop_campaign_if_running()
            else:
                _log.info(
                    "License OK (plan=%s, expires=%s)",
                    result.get("plan"), result.get("expires_at"),
                )
        except ImportError:
            pass  # no license module → dev mode, keep running
        except Exception as exc:
            _log.error("Periodic license check error: %s", exc)


# BUG FIX: replaced deprecated @app.on_event("startup") with lifespan (FastAPI 0.93+)
@asynccontextmanager
async def _lifespan(application: FastAPI):
    global _accounts, _proxies, _recipients, _campaign_cfg
    _accounts     = load_accounts()
    _proxies      = load_proxies()
    _recipients   = load_recipients()
    _campaign_cfg = load_campaign()

    # License check on every startup — always validates online.
    # Revoked licenses are blocked immediately; offline grace period still applies.
    try:
        from core.license import validate_on_startup
        loop = asyncio.get_running_loop()
        lic = await loop.run_in_executor(None, validate_on_startup)
        _set_license_ok(bool(lic.get("valid", False)))
    except ImportError:
        # In production (frozen exe) the license module MUST be present.
        # If it's missing something is wrong with the bundle — block immediately.
        # In dev/debug mode (not frozen) it's OK to run without the module.
        import sys as _sys
        if getattr(_sys, "frozen", False):
            _set_license_ok(False)
        else:
            _set_license_ok(True)
    except Exception:
        _set_license_ok(False)

    # Start periodic license re-check (every 1 hour).
    _license_check_stop.clear()
    checker = threading.Thread(
        target=_periodic_license_checker,
        name="license-checker",
        daemon=True,
    )
    checker.start()

    yield

    # Shutdown: signal the checker thread to exit.
    _license_check_stop.set()


app = FastAPI(title="FMailSender Core", version=APP_VERSION, lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── License guard middleware ──────────────────────────────────────────────────
# Paths that remain accessible even when license is invalid (activation flow).
_LICENSE_EXEMPT = {
    "/api/health",
    "/api/license",
    "/api/license/activate",
    "/api/events",
}

@app.middleware("http")
async def _license_guard(request: Request, call_next):
    """Block all non-exempt routes when the license is invalid or revoked."""
    if request.url.path not in _LICENSE_EXEMPT and not _get_license_ok():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"detail": "Лицензия недействительна. Активируйте или продлите лицензию."},
            status_code=403,
        )
    return await call_next(request)


# ── Pydantic request schemas ──────────────────────────────────────────────────

class AccountIn(BaseModel):
    email: str;          password: str;      host: str
    port: int = 465;     use_ssl: bool = True; use_tls: bool = False
    display_name: str = ""; daily_limit: int = 500; hourly_limit: int = 50
    is_active: bool = True;  proxy: str = "";  proxy_list: list[str] = []
    imap_host: str = "";  imap_port: int = 993;  imap_ssl: bool = True
    # FIX v6.3: OAuth2 поля
    refresh_token: str = "";  access_token: str = ""


class CampaignIn(BaseModel):
    subject: str = "";    body_html: str = "";   body_text: str = ""
    from_name: str = "";  reply_to: str = ""
    delay_min: float = 1.0;  delay_max: float = 3.0
    daily_limit_per_account: int = 500


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_account(body: AccountIn) -> SmtpAccount:
    return SmtpAccount(
        email=body.email, password=body.password, host=body.host,
        port=body.port, use_ssl=body.use_ssl, use_tls=body.use_tls,
        display_name=body.display_name, daily_limit=body.daily_limit,
        hourly_limit=body.hourly_limit, is_active=body.is_active,
        proxy=body.proxy, proxy_list=list(body.proxy_list),
        imap_host=body.imap_host, imap_port=body.imap_port, imap_ssl=body.imap_ssl,
        refresh_token=getattr(body, "refresh_token", ""), access_token=getattr(body, "access_token", ""),
    )


def _to_sender_recipient(r: Recipient) -> SenderRecipient:
    name   = r.name or ""
    parts  = name.split(" ", 1)
    return SenderRecipient(
        email=r.email,
        first_name=parts[0],
        last_name=parts[1] if len(parts) > 1 else "",
        company=r.variables.get("company", ""),
        custom_1=r.variables.get("custom_1", ""),
        custom_2=r.variables.get("custom_2", ""),
    )


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
    if any(a.email.lower() == body.email.lower() for a in _accounts):
        raise HTTPException(400, f"Account {body.email} already exists")
    acc = _make_account(body)
    _accounts.append(acc)
    save_accounts(_accounts)
    return acc.to_dict()


@app.put("/api/accounts/{email}")
def update_account(email: str, body: AccountIn):
    idx = next((i for i, a in enumerate(_accounts) if a.email.lower() == email.lower()), None)
    if idx is None:
        raise HTTPException(404, "Account not found")
    _accounts[idx] = _make_account(body)
    save_accounts(_accounts)
    return _accounts[idx].to_dict()


@app.delete("/api/accounts/{email}")
def delete_account(email: str):
    before = len(_accounts)
    _accounts[:] = [a for a in _accounts if a.email.lower() != email.lower()]
    if len(_accounts) == before:
        raise HTTPException(404, "Account not found")
    save_accounts(_accounts)
    return {"ok": True}


@app.post("/api/accounts/test")
async def test_account_endpoint(body: AccountIn):
    # Our SmtpAccount is duck-compatible with sender.py SmtpAccount (same field names).
    acc = _make_account(body)
    ok, msg = await test_smtp_connection(acc)
    for a in _accounts:
        if a.email.lower() == body.email.lower():
            a.last_test_ok  = ok
            a.last_test_msg = msg
            break
    save_accounts(_accounts)
    return {"ok": ok, "message": msg}


@app.post("/api/accounts/test-all")
async def test_all_accounts():
    results = []
    # FIX v6.1: снижено с 10 до 4 — GMX/Outlook блокируют при >3-4 одновременных соединениях
    # (ошибка 421 Too many connections). Значение соответствует rate-limit-strategy skill.
    sem = asyncio.Semaphore(4)

    async def _one(i: int, acc: SmtpAccount):
        async with sem:
            ok, msg = await test_smtp_connection(acc)
            acc.last_test_ok  = ok
            acc.last_test_msg = msg
            results.append({"index": i, "email": acc.email, "ok": ok, "message": msg})

    await asyncio.gather(*[_one(i, a) for i, a in enumerate(_accounts)])
    save_accounts(_accounts)
    ok_cnt   = sum(1 for a in _accounts if a.last_test_ok is True)
    fail_cnt = sum(1 for a in _accounts if a.last_test_ok is False)
    return {"results": sorted(results, key=lambda x: x["index"]),
            "ok": ok_cnt, "failed": fail_cnt, "total": len(_accounts)}


@app.get("/api/accounts/test-all/stream")
async def test_all_stream(request: Request):
    """
    SSE: tests all accounts with 10 concurrent workers.
    Streams each result immediately as it completes — no waiting for the full batch.

    Per-result event:
      data: {"index":0,"email":"u@h.com","ok":true,"message":"OK","done":1,"total":61}

    Final event:
      data: {"complete":true,"ok":N,"failed":N,"total":N}
    """
    accounts_snapshot = list(_accounts)
    total = len(accounts_snapshot)

    async def _gen():
        if not accounts_snapshot:
            yield f"data: {json.dumps({'complete': True, 'ok': 0, 'failed': 0, 'total': 0})}\n\n"
            return

        q: asyncio.Queue = asyncio.Queue()
        # FIX v6.1: снижено с 10 до 4 — соответствует rate-limit-strategy skill.
        # GMX блокирует при >3 одновременных соединениях (421 Too many connections),
        # Outlook при >3 выдаёт временную ошибку. 4 = безопасный максимум для любого провайдера.
        sem = asyncio.Semaphore(4)

        async def _one(i: int, acc: SmtpAccount):
            async with sem:
                try:
                    ok, msg = await test_smtp_connection(acc)
                except asyncio.CancelledError:
                    q.put_nowait({"i": i, "email": acc.email, "ok": False, "msg": "отменено"})
                    return
                except Exception as exc:
                    ok, msg = False, str(exc)
                acc.last_test_ok  = ok
                acc.last_test_msg = msg
                q.put_nowait({"i": i, "email": acc.email, "ok": ok, "msg": msg})

        tasks = [asyncio.create_task(_one(i, a)) for i, a in enumerate(accounts_snapshot)]
        ok_n = fail_n = done_n = 0

        while done_n < total:
            if await request.is_disconnected():
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                return
            try:
                r = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            done_n += 1
            if r["ok"]:
                ok_n += 1
            else:
                fail_n += 1
            payload = {
                "index":   r["i"],
                "email":   r["email"],
                "ok":      r["ok"],
                "message": r["msg"],
                "done":    done_n,
                "total":   total,
            }
            yield f"data: {json.dumps(payload)}\n\n"

        await asyncio.gather(*tasks, return_exceptions=True)
        save_accounts(accounts_snapshot)
        yield f"data: {json.dumps({'complete': True, 'ok': ok_n, 'failed': fail_n, 'total': total})}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/accounts/import-txt")
async def import_accounts_txt(file: UploadFile = File(...)):
    content  = (await file.read()).decode("utf-8", errors="replace")
    existing = {a.email.lower() for a in _accounts}
    imported = skipped = 0
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ["|", ";", ":"]:
            parts = line.split(sep)
            if len(parts) >= 2:
                email, pwd = parts[0].strip(), parts[1].strip()
                if "@" in email and email.lower() not in existing:
                    domain = email.split("@")[-1].lower()
                    cfg    = get_smtp_config_for_domain(domain) or {}
                    from core.smtp_limits import apply_limits_to_account as _apply_lim
                    _rt = parts[2].strip() if len(parts) >= 3 else ""  # FIX v6.3: email|pwd|refresh_token
                    acc    = SmtpAccount(
                        email=email, password=pwd,
                        host=cfg.get("host", ""),
                        port=cfg.get("port", 465),
                        use_ssl=cfg.get("use_ssl", True),
                        refresh_token=_rt,
                    )
                    _apply_lim(acc)  # set official daily/hourly limits by domain
                    _accounts.append(acc)
                    existing.add(email.lower())
                    imported += 1
                else:
                    skipped += 1
                break
    if _proxies:
        start = len(_accounts) - imported
        ProxyManager(_proxies).distribute(_accounts[start:], start)
    save_accounts(_accounts)
    return {"imported": imported, "skipped": skipped, "total": len(_accounts)}


# ── Proxies ───────────────────────────────────────────────────────────────────

@app.get("/api/proxies")
def get_proxies():
    return {"proxies": _proxies, "count": len(_proxies)}


@app.post("/api/proxies")
def set_proxies(body: dict):
    _proxies[:] = [p for r in body.get("proxies", []) if (p := parse_proxy(r))]
    save_proxies(_proxies)
    return {"count": len(_proxies)}


@app.post("/api/proxies/check")
async def check_proxies_endpoint(body: dict):
    raw      = body.get("proxies", _proxies)
    to_check = [p for r in raw if (p := parse_proxy(r))]
    loop     = asyncio.get_running_loop()
    results  = list(await asyncio.gather(*[
        loop.run_in_executor(None, validate_proxy, px) for px in to_check
    ]))
    return {
        "results":  results,
        "valid":    sum(1 for r in results if r["ok"]),
        "smtp_ok":  sum(1 for r in results if r.get("smtp_ok")),
        "total":    len(to_check),
    }


@app.post("/api/proxies/distribute")
def distribute_proxies():
    if not _proxies:
        raise HTTPException(400, "No proxies loaded")
    ProxyManager(_proxies).distribute(_accounts)
    save_accounts(_accounts)
    return {"distributed": len(_accounts), "proxies": len(_proxies)}


# ── Recipients ────────────────────────────────────────────────────────────────

@app.get("/api/recipients")
def get_recipients():
    return {"recipients": [r.to_dict() for r in _recipients], "count": len(_recipients)}


@app.post("/api/recipients")
def set_recipients(body: dict):
    _recipients[:] = [Recipient.from_dict(d) for d in body.get("recipients", [])]
    save_recipients(_recipients)
    return {"count": len(_recipients)}


@app.post("/api/recipients/import-txt")
async def import_recipients_txt(file: UploadFile = File(...)):
    content  = (await file.read()).decode("utf-8", errors="replace")
    existing = {r.email.lower() for r in _recipients}
    added    = 0
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
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
    _recipients.clear()
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
def start_campaign():
    global _engine, _engine_thread, _campaign_status, _run_id

    with _status_lock:
        if _campaign_status.state == "running":
            raise HTTPException(400, "Campaign already running")

    if not _accounts:
        raise HTTPException(400, "No accounts loaded")
    if not _recipients:
        raise HTTPException(400, "No recipients loaded")

    active = [a for a in _accounts if a.is_active and a.last_test_ok is True]
    if not active:
        raise HTTPException(400, "No validated accounts. Run account test first.")

    # Convert to sender.py types.
    # Note: our SmtpAccount (models.py) is duck-compatible with sender.py's SmtpAccount
    # (both have: email, password, host, port, use_ssl, use_tls, proxy, display_name, etc.)
    sender_recipients = [_to_sender_recipient(r) for r in _recipients]

    template = EmailTemplate(
        subject=_campaign_cfg.subject or "(no subject)",
        body_html=_campaign_cfg.body_html or "",
        body_text=_campaign_cfg.body_text or "",
        reply_to=_campaign_cfg.reply_to or "",
    )

    sender_config = SenderConfig(
        min_delay_ms=int(_campaign_cfg.delay_min * 1000),
        max_delay_ms=int(_campaign_cfg.delay_max * 1000),
        max_threads=min(len(active), 10),
        rotate_accounts=True,
        uniqueize=True,
    )

    with _status_lock:
        _run_id += 1
        current_run = _run_id
        _campaign_status = CampaignStatus(
            state="running",
            total=len(sender_recipients),
            started_at=time.time(),
        )

    stop_event = threading.Event()
    _engine    = SendingEngine(
        accounts=active,          # duck-compatible with sender.py SmtpAccount
        config=sender_config,
        recipients=sender_recipients,
        template=template,
        stop_event=stop_event,
    )

    def _on_progress(sent: int, total: int, result):
        with _status_lock:
            if _run_id != current_run:   # stale callback from a previous campaign run
                return
            _campaign_status.sent  = sent
            _campaign_status.total = total
            if result and not getattr(result, "success", True):
                _campaign_status.failed += 1
                err = getattr(result, "error", "")
                if err:
                    _campaign_status.errors.append(
                        f"{getattr(result, 'recipient_email', '?')}: {err}"
                    )
            if result:
                _campaign_status.current_email   = getattr(result, "recipient_email", "")
                _campaign_status.current_account = getattr(result, "account_used", "")

    def _on_finished(results):
        with _status_lock:
            if _run_id != current_run:   # stop() already invalidated this run
                return
            _campaign_status.state  = "done"
            _campaign_status.sent   = sum(1 for r in results if getattr(r, "success", False))
            _campaign_status.failed = sum(1 for r in results if not getattr(r, "success", True))

    _engine.on_progress = _on_progress
    _engine.on_finished = _on_finished

    def _run():
        try:
            _engine.run()
        except Exception as e:
            with _status_lock:
                if _run_id == current_run:
                    _campaign_status.state = "error"
                    _campaign_status.errors.append(str(e))

    _engine_thread = threading.Thread(target=_run, daemon=True, name="fmail-sender")
    _engine_thread.start()

    return {"ok": True, "total": len(sender_recipients), "accounts": len(active)}


@app.post("/api/campaign/pause")
def pause_campaign():
    with _status_lock:
        if _engine and _campaign_status.state == "running":
            _engine._paused        = True
            _campaign_status.state = "paused"
    return _campaign_status.to_dict()


@app.post("/api/campaign/resume")
def resume_campaign():
    with _status_lock:
        if _engine and _campaign_status.state == "paused":
            _engine._paused        = False
            _campaign_status.state = "running"
    return _campaign_status.to_dict()


@app.post("/api/campaign/stop")
def stop_campaign():
    global _run_id
    with _status_lock:
        # Increment run_id first — callbacks from the running thread will see the
        # mismatch and silently discard their updates (no state flip to "done").
        _run_id += 1
        if _engine:
            _engine.stop_event.set()
            _engine._paused = False
        _campaign_status.state = "idle"
    return {"ok": True}


# ── Overall status ────────────────────────────────────────────────────────────

def _build_status() -> dict:
    """Coherent status snapshot under lock — called by GET /api/status and SSE /api/events."""
    with _status_lock:
        campaign_dict = _campaign_status.to_dict()
        ok_cnt   = sum(1 for a in _accounts if a.last_test_ok is True)
        fail_cnt = sum(1 for a in _accounts if a.last_test_ok is False)
        return {
            "campaign":   campaign_dict,
            "accounts":   {
                "total":    len(_accounts),
                "valid":    ok_cnt,
                "invalid":  fail_cnt,
                "untested": len(_accounts) - ok_cnt - fail_cnt,
                "ready":    sum(1 for a in _accounts if a.is_active and a.last_test_ok is True),
            },
            "recipients": len(_recipients),
            "proxies":    len(_proxies),
        }



@app.get("/api/status")
def get_status():
    return _build_status()


# ── DKIM signing ──────────────────────────────────────────────────────────────
try:
    from core.dkim_signer import (
        load_configs as _dkim_load,
        save_configs as _dkim_save,
        validate_config as _dkim_validate,
        DkimConfig,
        is_available as _dkim_available,
    )
    _HAS_DKIM = True
except ImportError:
    _HAS_DKIM = False


@app.get("/api/dkim")
def get_dkim_configs():
    if not _HAS_DKIM:
        return {"available": False, "configs": [], "message": "dkimpy not installed (pip install dkimpy)"}
    configs = _dkim_load()
    return {
        "available": _dkim_available(),
        "configs": [
            {
                "selector": c.selector,
                "domain": c.domain,
                "enabled": c.enabled,
                "has_key": bool(c.private_key_pem.strip()),
            }
            for c in configs
        ],
    }


class DkimConfigIn(BaseModel):
    selector: str
    domain: str
    private_key_pem: str
    enabled: bool = True


@app.post("/api/dkim")
def add_or_update_dkim_config(body: DkimConfigIn):
    if not _HAS_DKIM:
        raise HTTPException(400, "dkimpy not installed — run: pip install dkimpy")
    cfg = DkimConfig(
        selector=body.selector.strip(),
        domain=body.domain.strip().lower(),
        private_key_pem=body.private_key_pem.strip(),
        enabled=body.enabled,
    )
    ok, msg = _dkim_validate(cfg)
    if not ok:
        raise HTTPException(422, msg)
    configs = _dkim_load()
    # Replace existing config for same domain, or append
    replaced = False
    for i, c in enumerate(configs):
        if c.domain.lower() == cfg.domain.lower():
            configs[i] = cfg
            replaced = True
            break
    if not replaced:
        configs.append(cfg)
    _dkim_save(configs)
    return {"ok": True, "message": msg, "replaced": replaced}


@app.delete("/api/dkim/{domain}")
def delete_dkim_config(domain: str):
    if not _HAS_DKIM:
        raise HTTPException(400, "dkimpy not installed")
    configs = _dkim_load()
    before = len(configs)
    configs = [c for c in configs if c.domain.lower() != domain.lower()]
    _dkim_save(configs)
    return {"ok": True, "deleted": before - len(configs)}


@app.post("/api/dkim/validate")
def validate_dkim_config(body: DkimConfigIn):
    if not _HAS_DKIM:
        raise HTTPException(400, "dkimpy not installed")
    cfg = DkimConfig(
        selector=body.selector.strip(),
        domain=body.domain.strip().lower(),
        private_key_pem=body.private_key_pem.strip(),
        enabled=body.enabled,
    )
    ok, msg = _dkim_validate(cfg)
    return {"ok": ok, "message": msg}


@app.get("/api/events")
async def get_events(request: Request):
    """
    SSE endpoint — streams AppStatus JSON events.
    Interval: 0.8s when campaign is running, 2s otherwise.
    Properly handles client disconnect via request.is_disconnected().
    """
    async def _stream():
        while True:
            # Stop streaming if the client disconnected
            if await request.is_disconnected():
                break
            try:
                payload = _build_status()
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as exc:
                # On error send a named error event — client can ignore or log it
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            state = getattr(_campaign_status, "state", "idle")
            interval = 0.8 if state == "running" else 2.0
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── License ────────────────────────────────────────────────────────────────────────────

@app.get("/api/license")
async def get_license():
    """Returns current license status. Always validates online on every call."""
    try:
        from core.license import validate_on_startup
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, validate_on_startup)
        _set_license_ok(bool(result.get("valid", False)))
        return result
    except ImportError:
        import sys as _sys
        if getattr(_sys, "frozen", False):
            # Frozen exe: license module missing = hard block
            _set_license_ok(False)
            return {"valid": False, "error": "License module unavailable — reinstall the app"}
        # Dev mode: allow without license module
        _set_license_ok(True)
        return {"valid": True, "plan": "unlimited", "note": "license module not available"}
    except Exception as exc:
        _set_license_ok(False)
        return {"valid": False, "error": str(exc)}


@app.post("/api/license/activate")
async def activate_license(req: Request):
    """Activates a license key on this machine."""
    body = await req.json()
    key = (body.get("key") or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="Лицензионный ключ не указан")
    try:
        from core.license import activate_license_key
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, activate_license_key, key)
        if result.get("success"):
            _set_license_ok(True)
        return result
    except ImportError:
        import sys as _sys
        if getattr(_sys, "frozen", False):
            raise HTTPException(status_code=500, detail="License module unavailable — reinstall the app")
        return {"success": True, "message": "Ключ сохранён (оффлайн-режим)"}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
