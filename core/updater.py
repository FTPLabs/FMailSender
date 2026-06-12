"""
  FMailSender auto-updater v1.0.0.
  Checks GitHub Releases for a newer version and notifies the user.
  """
  from __future__ import annotations

  import logging
  import threading
  from typing import Callable, Optional

  import requests

  from core._version import APP_VERSION

  logger = logging.getLogger("updater")

  GITHUB_API_URL = "https://api.github.com/repos/FTPLabs/FMailSender/releases/latest"
  CHECK_INTERVAL_SEC = 3600  # check once per hour


  def _parse_version(tag: str) -> tuple[int, ...]:
      """Convert 'v2.9.0' or '2.9.0' to (2, 9, 0) for comparison."""
      clean = tag.lstrip("v").strip()
      try:
          return tuple(int(x) for x in clean.split("."))
      except ValueError:
          return (0,)


  def check_for_update(timeout: float = 10.0) -> Optional[dict]:
      """
      Check GitHub Releases for a newer version.
      Returns dict with keys: tag_name, html_url, body — or None if no update / error.
      """
      try:
          resp = requests.get(
              GITHUB_API_URL,
              timeout=timeout,
              headers={"User-Agent": f"FMailSender/{APP_VERSION}"},
          )
          if resp.status_code != 200:
              return None
          data = resp.json()
          tag = data.get("tag_name", "")
          if not tag:
              return None
          latest = _parse_version(tag)
          current = _parse_version(APP_VERSION)
          if latest > current:
              return {
                  "tag_name": tag,
                  "html_url": data.get("html_url", ""),
                  "body": data.get("body", ""),
                  "download_url": (
                      data.get("assets", [{}])[0].get("browser_download_url", data.get("html_url", ""))
                      if data.get("assets") else data.get("html_url", "")
                  ),
              }
      except Exception as e:
          logger.debug("Update check failed: %s", e)
      return None


  def start_background_check(
      on_update_found: Callable[[dict], None],
      delay_sec: float = 30.0,
  ) -> None:
      """
      Start a daemon thread that checks for updates after delay_sec,
      then every CHECK_INTERVAL_SEC. Calls on_update_found(info) on the
      calling thread is NOT guaranteed — wire it to a Qt signal for GUI use.
      """
      def _worker() -> None:
          import time
          time.sleep(delay_sec)
          while True:
              info = check_for_update()
              if info:
                  logger.info("New version available: %s", info["tag_name"])
                  try:
                      on_update_found(info)
                  except Exception:
                      pass
                  return
              time.sleep(CHECK_INTERVAL_SEC)

      threading.Thread(target=_worker, daemon=True, name="updater").start()
  