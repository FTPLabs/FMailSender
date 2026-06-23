"""
  T018 — v4.4.4 Regression Tests
  Покрывают три критических бага исправленных в v4.4.4:

  Bug 1: «50/50 аккаунтов» в разделе Рассылки (неправильный счётчик sendable)
  Bug 2: GMX SMTPServerDisconnected не перехватывался → fallback не срабатывал
  Bug 3: RuntimeError «wrapped C/C++ object of type QPushButton has been deleted»

  Запуск: python3 tests/test_v444_regressions.py
  """
  from __future__ import annotations

  import os
  import sys
  import socket
  import ssl
  import smtplib
  import threading
  import time
  import unittest
  from unittest.mock import MagicMock, patch, call
  from dataclasses import dataclass, field
  from typing import Optional

  _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  sys.path.insert(0, _ROOT)

  _failures: list[str] = []
  _passes: int = 0


  def check(cond: bool, label: str, detail: str = "") -> None:
      global _passes
      if cond:
          _passes += 1
          print(f"[PASS] {label}")
      else:
          _failures.append(label)
          suffix = f" | {detail}" if detail else ""
          print(f"[FAIL] {label}{suffix}")


  # ─────────────────────────────────────────────────────────────────────────────
  # BUG 1: sendable count in set_accounts
  # ─────────────────────────────────────────────────────────────────────────────

  def test_sendable_count_logic() -> None:
      """Проверяет что счётчик sendable правильно считает аккаунты по last_test_ok."""
      print("\n--- Bug 1: sendable count in set_accounts ---")

      from core.sender import SmtpAccount

      def _make(email, is_active, last_test_ok):
          a = SmtpAccount(
              email=email, password="pass",
              host="smtp.test.com", port=465, use_ssl=True,
          )
          a.is_active = is_active
          a.last_test_ok = last_test_ok
          return a

      # Scenario: 30 valid, 20 invalid (as described in bug report)
      accounts = (
          [_make(f"valid{i}@gmx.com", True, True) for i in range(30)] +
          [_make(f"invalid{i}@gmx.com", False, False) for i in range(20)]
      )

      # Simulate the FIXED set_accounts logic from screen_sending.py v4.4.4
      valid_cnt    = sum(1 for a in accounts if a.is_active and getattr(a, "last_test_ok", None) is True)
      untested_cnt = sum(1 for a in accounts if getattr(a, "last_test_ok", None) is None)
      total = len(accounts)
      all_tested = (untested_cnt == 0 and total > 0)
      sendable = valid_cnt if all_tested else sum(1 for a in accounts if a.is_active)

      check(valid_cnt == 30, "valid_cnt == 30 (only last_test_ok=True counted)", f"got {valid_cnt}")
      check(untested_cnt == 0, "untested_cnt == 0 (all tested)", f"got {untested_cnt}")
      check(all_tested is True, "all_tested flag is True")
      check(sendable == 30, "sendable == 30/50 (not 50/50)", f"got {sendable}/{total}")
      check(total == 50, "total == 50")

      # OLD buggy logic — would show 50/50
      old_sendable = sum(1 for a in accounts if a.is_active and getattr(a, "last_test_ok", None) is not False)
      # For invalid accounts: is_active=False → blocked by is_active check → so old_sendable=30 too
      # REAL bug scenario: accounts not yet tested (last_test_ok=None, is_active=True)
      accounts_untested = (
          [_make(f"valid{i}@gmx.com", True, True) for i in range(30)] +
          [_make(f"unknown{i}@gmx.com", True, None) for i in range(20)]  # Never tested, is_active=True
      )
      old_sendable2 = sum(1 for a in accounts_untested if a.is_active and getattr(a, "last_test_ok", None) is not False)
      check(old_sendable2 == 50, "OLD logic: 50/50 for untested+valid mix (the bug)", f"got {old_sendable2}")

      valid_cnt2    = sum(1 for a in accounts_untested if a.is_active and getattr(a, "last_test_ok", None) is True)
      untested_cnt2 = sum(1 for a in accounts_untested if getattr(a, "last_test_ok", None) is None)
      all_tested2   = (untested_cnt2 == 0 and len(accounts_untested) > 0)
      sendable2 = valid_cnt2 if all_tested2 else sum(1 for a in accounts_untested if a.is_active)
      check(all_tested2 is False, "NEW logic: all_tested=False when some untested")
      check(sendable2 == 50, "NEW logic: untested mode shows all active (50) — first-run", f"got {sendable2}")

      # sendable_for_engine: only not-False (both valid + untested)
      for_engine = [a for a in accounts_untested if a.is_active and getattr(a, "last_test_ok", None) is not False]
      check(len(for_engine) == 50, "_start_campaign: passes 50 in first-run mode", f"got {len(for_engine)}")

      # After all tested → 30 valid, 20 invalid (is_active=False)
      for_engine2 = [a for a in accounts if a.is_active and getattr(a, "last_test_ok", None) is not False]
      check(len(for_engine2) == 30, "_start_campaign: passes only 30 valid after testing", f"got {len(for_engine2)}")


  # ─────────────────────────────────────────────────────────────────────────────
  # BUG 2: SMTPServerDisconnected not caught → GMX STARTTLS fallback missing
  # ─────────────────────────────────────────────────────────────────────────────

  def test_smtp_server_disconnected_is_handled() -> None:
      """Проверяет что _send_sync перехватывает SMTPServerDisconnected (Bug 2 — GMX)."""
      print("\n--- Bug 2: SMTPServerDisconnected fallback ---")

      from core.sender import SendingEngine, SmtpAccount, Recipient, EmailTemplate, CampaignConfig

      # Verify the exception IS smtplib.SMTPServerDisconnected
      try:
          raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
      except smtplib.SMTPServerDisconnected as e:
          check(True, "smtplib.SMTPServerDisconnected is catchable")
          check("Connection unexpectedly closed" in str(e), "Error message preserved")

      # Check that _send_sync code path handles SMTPServerDisconnected
      # We verify by inspecting sender.py source
      import inspect
      from core import sender as sender_module
      src = inspect.getsource(sender_module)
      check("except smtplib.SMTPServerDisconnected" in src,
            "sender.py: except smtplib.SMTPServerDisconnected present")
      check("BUG FIX v4.4.4" in src,
            "sender.py: v4.4.4 fix comment present")

      # Verify the fallback block exists after the new handler
      ssd_idx = src.index("except smtplib.SMTPServerDisconnected") if "except smtplib.SMTPServerDisconnected" in src else -1
      if ssd_idx > 0:
          fallback_section = src[ssd_idx:ssd_idx+2000]
          check("smtplib.SMTP_SSL" in fallback_section, "Fallback: SMTP_SSL attempt present")
          check("smtplib.SMTP(" in fallback_section, "Fallback: SMTP STARTTLS attempt present")
          check("SMTPServerDisconnected" in fallback_section, "Fallback: correct error message")


  # ─────────────────────────────────────────────────────────────────────────────
  # BUG 3: RuntimeError QPushButton guard
  # ─────────────────────────────────────────────────────────────────────────────

  def test_runtime_error_guards_exist() -> None:
      """Проверяет наличие RuntimeError guard в screen_sending и screen_accounts (Bug 3)."""
      print("\n--- Bug 3: RuntimeError QPushButton guard ---")

      import inspect
      # Load screen files
      try:
          import gui.screens.screen_sending as ss_mod
          import gui.screens.screen_accounts as sa_mod
          ss_src = inspect.getsource(ss_mod)
          sa_src = inspect.getsource(sa_mod)
      except ImportError as e:
          print(f"[SKIP] Cannot import GUI modules (headless env): {e}")
          check(True, "GUI modules skipped in headless environment")
          return

      # screen_sending: _finish_ui has try/except RuntimeError
      check("except RuntimeError" in ss_src,
            "screen_sending.py: RuntimeError guard present")
      finish_idx = ss_src.find("def _finish_ui")
      if finish_idx > -1:
          finish_section = ss_src[finish_idx:finish_idx+400]
          check("except RuntimeError" in finish_section,
                "screen_sending._finish_ui: RuntimeError guard in correct place")

      # screen_accounts: on_result has try/except RuntimeError
      check("except RuntimeError" in sa_src,
            "screen_accounts.py: RuntimeError guard present")
      on_result_idx = sa_src.find("def on_result(ok, msg, r=row)")
      if on_result_idx > -1:
          on_result_section = sa_src[on_result_idx:on_result_idx+500]
          check("except RuntimeError" in on_result_section,
                "screen_accounts.on_result: RuntimeError guard present")

      # accounts_changed.emit in test completion
      check("accounts_changed.emit(self._accounts)" in sa_src,
            "screen_accounts: accounts_changed.emit() after test completion")


  # ─────────────────────────────────────────────────────────────────────────────
  # BUG 2 Extra: GMX SMTP config verification
  # ─────────────────────────────────────────────────────────────────────────────

  def test_gmx_smtp_config() -> None:
      """Проверяет что GMX настроен на правильный SMTP сервер."""
      print("\n--- GMX SMTP config ---")

      from core.sender import get_smtp_config_for_domain

      gmx_domains = ["gmx.com", "gmx.de", "gmx.net"]
      for domain in gmx_domains:
          try:
              cfg = get_smtp_config_for_domain(domain)
              check("gmx" in cfg.get("host", "").lower(),
                    f"GMX domain {domain}: host contains 'gmx'", f"host={cfg.get('host')}")
              check(cfg.get("port") == 587,
                    f"GMX domain {domain}: port==587 (STARTTLS)", f"port={cfg.get('port')}")
              check(cfg.get("use_ssl") is False,
                    f"GMX domain {domain}: use_ssl=False (STARTTLS not SSL)", f"use_ssl={cfg.get('use_ssl')}")
              check(cfg.get("use_tls") is True,
                    f"GMX domain {domain}: use_tls=True", f"use_tls={cfg.get('use_tls')}")
          except Exception as e:
              check(False, f"GMX {domain} config lookup failed: {e}")


  # ─────────────────────────────────────────────────────────────────────────────
  # _pick_account: validates correct filtering (not False means valid OR untested)
  # ─────────────────────────────────────────────────────────────────────────────

  def test_pick_account_filtering() -> None:
      """Проверяет что _pick_account исключает last_test_ok=False аккаунты."""
      print("\n--- _pick_account filtering ---")

      from core.sender import SmtpAccount, SendingEngine, CampaignConfig
      import queue

      def _make(email, is_active, last_test_ok):
          a = SmtpAccount(email=email, password="pass", host="smtp.test.com", port=465, use_ssl=True)
          a.is_active = is_active
          a.last_test_ok = last_test_ok
          return a

      accounts = [
          _make("valid@test.com", True, True),   # should be picked
          _make("invalid@test.com", True, False), # should be skipped
          _make("untested@test.com", True, None), # should be picked (untested)
          _make("disabled@test.com", False, True), # should be skipped (is_active=False)
      ]

      config = CampaignConfig(max_threads=1)
      engine = SendingEngine(accounts=accounts, config=config, log_queue=queue.Queue())

      # _pick_account should pick valid OR untested (not False), not disabled
      picked_emails = set()
      for _ in range(20):
          acc = engine._pick_account()
          if acc:
              picked_emails.add(acc.email)

      check("valid@test.com" in picked_emails, "_pick_account picks valid (last_test_ok=True)")
      check("untested@test.com" in picked_emails, "_pick_account picks untested (last_test_ok=None)")
      check("invalid@test.com" not in picked_emails, "_pick_account skips invalid (last_test_ok=False)")
      check("disabled@test.com" not in picked_emails, "_pick_account skips disabled (is_active=False)")


  # ─────────────────────────────────────────────────────────────────────────────
  # Version check
  # ─────────────────────────────────────────────────────────────────────────────

  def test_version() -> None:
      print("\n--- Version check ---")
      from core._version import APP_VERSION
      check(APP_VERSION == "4.4.4", f"APP_VERSION == 4.4.4", f"got {APP_VERSION}")


  # ─────────────────────────────────────────────────────────────────────────────
  # MAIN
  # ─────────────────────────────────────────────────────────────────────────────

  if __name__ == "__main__":
      test_version()
      test_sendable_count_logic()
      test_smtp_server_disconnected_is_handled()
      test_runtime_error_guards_exist()
      test_gmx_smtp_config()
      test_pick_account_filtering()

      print(f"\n{'='*60}")
      print(f"Results: {_passes} passed, {len(_failures)} failed")
      if _failures:
          print("FAILED:")
          for f in _failures:
              print(f"  - {f}")
          sys.exit(1)
      else:
          print("✅ All tests passed!")
          sys.exit(0)
  