#!/usr/bin/env python3
  """
  Тест SMTP Connection Pool — core/smtp_pool.py
  Запуск: python tests/test_smtp_pool.py
  """
  import sys
  import time
  from pathlib import Path

  # Добавляем корень проекта в PATH
  sys.path.insert(0, str(Path(__file__).parent.parent))

  from core.smtp_pool import (
      SmtpConnectionPool,
      PROVIDER_SESSION_LIMITS,
      PROVIDER_SEND_DELAYS,
      get_global_pool,
  )
  from core.send_checkpoint import CheckpointManager, list_checkpoints


  def test_provider_limits():
      """Проверяем что лимиты провайдеров заданы правильно."""
      required = ["smtp.gmail.com", "smtp.office365.com", "smtp.mail.yahoo.com",
                  "smtp.rambler.ru", "smtp.mail.ru", "smtp.yandex.ru", "mail.gmx.net"]
      for host in required:
          assert host in PROVIDER_SESSION_LIMITS, f"Нет лимита для {host}"
          assert host in PROVIDER_SEND_DELAYS, f"Нет задержки для {host}"
          assert PROVIDER_SESSION_LIMITS[host] >= 50, f"Лимит слишком мал: {host}"
          assert 0.1 <= PROVIDER_SEND_DELAYS[host] <= 5.0, f"Задержка вне диапазона: {host}"
      print(f"✅ provider_limits: {len(required)} провайдеров OK")


  def test_pool_instance():
      """Проверяем что глобальный пул создаётся."""
      pool = get_global_pool()
      assert pool is not None
      assert isinstance(pool, SmtpConnectionPool)
      # Второй вызов — тот же объект
      pool2 = get_global_pool()
      assert pool is pool2
      print("✅ pool_instance: глобальный пул OK")


  def test_checkpoint_manager():
      """Проверяем чекпоинты."""
      import tempfile
      from unittest.mock import patch

      campaign_id = "test-campaign-001"
      
      # Изолируем от реального хранилища
      with tempfile.TemporaryDirectory() as tmp:
          from core.send_checkpoint import CHECKPOINT_DIR as _orig_dir
          from core import send_checkpoint as _ck_mod
          _ck_mod.CHECKPOINT_DIR = Path(tmp)
          
          try:
              mgr = CheckpointManager(campaign_id, total=100)
              assert not mgr.is_resumable(), "Новая кампания не должна быть resumable"
              
              mgr.record_sent("a@example.com")
              mgr.record_sent("b@example.com")
              mgr.flush()
              
              sent = mgr.get_sent_set()
              assert "a@example.com" in sent
              assert "b@example.com" in sent
              
              # Simulate resume
              mgr2 = CheckpointManager(campaign_id, total=100)
              assert mgr2.is_resumable()
              sent2 = mgr2.get_sent_set()
              assert sent2 == sent
              
              mgr2.complete()
              
              checkpoints = list_checkpoints()
              assert all(c["campaign_id"] != campaign_id for c in checkpoints),                   "Завершённая кампания не должна быть в списке"
              
              print("✅ checkpoint_manager: создание, запись, resume, complete OK")
          finally:
              _ck_mod.CHECKPOINT_DIR = _orig_dir


  def test_session_exhaustion():
      """Проверяем логику is_exhausted."""
      from core.smtp_pool import SmtpConnection
      conn = SmtpConnection(
          host="smtp.gmail.com", port=465, use_ssl=True, use_tls=False,
          email="test@gmail.com", password="pass", proxy_url="socks5://1.2.3.4:1080",
          smtp=None, sent_count=399,
      )
      assert not conn.is_exhausted  # 399 < 400
      conn.sent_count = 400
      assert conn.is_exhausted     # 400 >= 400
      print("✅ session_exhaustion: is_exhausted check OK")


  def test_session_stale():
      """Проверяем логику is_stale."""
      from core.smtp_pool import SmtpConnection
      conn = SmtpConnection(
          host="smtp.gmail.com", port=465, use_ssl=True, use_tls=False,
          email="test@gmail.com", password="pass", proxy_url="socks5://1.2.3.4:1080",
          smtp=None,
      )
      conn.last_used = time.time() - 400  # 400 сек назад
      assert conn.is_stale
      conn.last_used = time.time() - 100  # 100 сек назад — свежее
      assert not conn.is_stale
      print("✅ session_stale: is_stale check OK")


  if __name__ == "__main__":
      tests = [
          test_provider_limits,
          test_pool_instance,
          test_checkpoint_manager,
          test_session_exhaustion,
          test_session_stale,
      ]
      passed = 0
      failed = 0
      for t in tests:
          try:
              t()
              passed += 1
          except Exception as e:
              print(f"❌ {t.__name__}: {e}")
              failed += 1
      print(f"\nРезультат: {passed}/{len(tests)} тестов прошло")
      sys.exit(0 if failed == 0 else 1)
  