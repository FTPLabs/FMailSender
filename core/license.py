"""
  FMailSender — License validation module v1.0.0
  Validates license against fmail.shop license server.
  Caches valid license locally for offline startup.

  License key format: FM-XXXXXXXX-XXXXXXXX-XXXXXXXX
  """
  from __future__ import annotations

  import hashlib
  import json
  import logging
  import os
  import platform
  import sys
  import time
  import uuid
  from pathlib import Path
  from typing import Optional

  logger = logging.getLogger("fmailsender.license")

  LICENSE_SERVER_URL = "https://fmail.shop/api/license"
  CACHE_TTL_SECS = 24 * 3600   # Re-validate every 24 hours
  OFFLINE_GRACE_DAYS = 7        # Allow offline use for up to 7 days


  def _get_data_dir() -> Path:
      if getattr(sys, "frozen", False):
          appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
          return Path(appdata) / "FMailSender"
      return Path(__file__).parent.parent / "data"


  DATA_DIR = _get_data_dir()
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  LICENSE_FILE = DATA_DIR / "license.json"


  def _get_hardware_id() -> str:
      """Stable hardware ID: SHA256 of MAC address + OS info."""
      try:
          node = uuid.getnode()
          raw = f"{node}:{platform.machine()}:{platform.node() or 'x'}"
          return hashlib.sha256(raw.encode()).hexdigest()[:32]
      except Exception:
          return hashlib.sha256(b"fallback").hexdigest()[:32]


  def _load_cached() -> Optional[dict]:
      if not LICENSE_FILE.exists():
          return None
      try:
          return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
      except Exception:
          return None


  def _save_cache(data: dict) -> None:
      try:
          tmp = LICENSE_FILE.with_suffix(".tmp")
          tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
          tmp.replace(LICENSE_FILE)
      except Exception as exc:
          logger.warning("license cache write failed: %s", exc)


  def _validate_online(key: str, hwid: str, timeout: float = 10.0) -> dict:
      try:
          import requests
          resp = requests.post(
              LICENSE_SERVER_URL + "/validate",
              json={"key": key, "hwid": hwid},
              timeout=timeout,
          )
          if resp.status_code == 200:
              return resp.json()
          return {"valid": False, "error": f"HTTP {resp.status_code}"}
      except ImportError:
          return {"valid": False, "error": "requests not installed", "offline": True}
      except Exception as exc:
          return {"valid": False, "error": str(exc), "offline": True}


  def get_license_status() -> dict:
      """Returns current license status. Checks cache, re-validates online if stale."""
      hwid = _get_hardware_id()
      cached = _load_cached()

      if not cached or not cached.get("key"):
          return {
              "valid": False,
              "plan": None,
              "hwid": hwid,
              "message": "Лицензия не активирована",
              "requires_activation": True,
          }

      key = cached["key"]

      # Fresh cache — skip network
      if (time.time() - cached.get("validated_at", 0)) < CACHE_TTL_SECS:
          return {
              "valid": cached.get("valid", False),
              "plan": cached.get("plan"),
              "expires_at": cached.get("expires_at"),
              "hwid": hwid,
              "key": key[:12] + "****",
              "message": cached.get("message", ""),
              "from_cache": True,
          }

      # Online re-validation
      result = _validate_online(key, hwid)
      if result.get("offline"):
          if (time.time() - cached.get("validated_at", 0)) < (OFFLINE_GRACE_DAYS * 86400):
              return {
                  "valid": cached.get("valid", False),
                  "plan": cached.get("plan"),
                  "expires_at": cached.get("expires_at"),
                  "hwid": hwid,
                  "key": key[:12] + "****",
                  "message": "Оффлайн-режим (нет связи с сервером лицензий)",
                  "offline": True,
                  "from_cache": True,
              }
          return {"valid": False, "hwid": hwid, "message": "Лицензия не подтверждена: нет связи с сервером"}

      cached.update({
          "valid": result.get("valid", False),
          "plan": result.get("plan", cached.get("plan")),
          "expires_at": result.get("expires_at"),
          "message": result.get("message", ""),
          "validated_at": time.time(),
      })
      _save_cache(cached)
      return {
          "valid": result.get("valid", False),
          "plan": result.get("plan"),
          "expires_at": result.get("expires_at"),
          "hwid": hwid,
          "key": key[:12] + "****",
          "message": result.get("message", ""),
      }


  def activate_license_key(key: str) -> dict:
      """Activate a license key on this machine."""
      if not key or not key.upper().startswith("FM-"):
          raise ValueError("Неверный формат ключа. Ожидается: FM-XXXXXXXX-XXXXXXXX-XXXXXXXX")

      hwid = _get_hardware_id()
      logger.info("Activating license key %s... hwid=%s...", key[:12], hwid[:8])

      try:
          import requests
          resp = requests.post(
              LICENSE_SERVER_URL + "/activate",
              json={"key": key, "hwid": hwid},
              timeout=15.0,
          )
          result = resp.json()
          if not result.get("valid") and resp.status_code != 200:
              raise RuntimeError(result.get("error") or result.get("message") or "Ключ недействителен")
      except ImportError:
          # requests unavailable — accept key offline
          result = {"valid": True, "plan": "offline", "message": "Ключ сохранён (оффлайн)"}
      except RuntimeError:
          raise
      except Exception as exc:
          raise RuntimeError(f"Не удалось связаться с сервером лицензий: {exc}") from exc

      cache_data = {
          "key": key,
          "valid": True,
          "plan": result.get("plan", "unknown"),
          "expires_at": result.get("expires_at"),
          "hwid": hwid,
          "message": result.get("message", "Активировано"),
          "activated_at": time.time(),
          "validated_at": time.time(),
      }
      _save_cache(cache_data)
      logger.info("License activated: plan=%s", cache_data["plan"])

      return {
          "success": True,
          "plan": cache_data["plan"],
          "expires_at": cache_data.get("expires_at"),
          "message": result.get("message", "Лицензия успешно активирована"),
      }
  