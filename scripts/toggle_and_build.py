#!/usr/bin/env python3
"""
toggle_and_build.py — Публичный репо → Сборка EXE → Приватный репо.

Обходит лимит GitHub Actions на приватных репозиториях (Free plan: 2 000 мин/мес)
используя бесплатные БЕЗЛИМИТНЫЕ минуты для публичных репозиториев.

Схема работы:
  1. Делает репозиторий ПУБЛИЧНЫМ через GitHub API
  2. Триггерит workflow_dispatch на release.yml с нужным тегом
  3. Ждёт завершения сборки
  4. Workflow сам делает репо приватным в последнем job (restore-privacy)

Использование:
  python scripts/toggle_and_build.py v3.5.4

Переменные окружения:
  GITHUB_TOKEN  — Personal Access Token с правами: repo (+ admin:repo для смены видимости)
  GITHUB_REPO   — owner/repo (по умолчанию FTPLabs/FMailSender)

Требования:
  pip install requests
"""

from __future__ import annotations
import argparse
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("❌ Установите requests: pip install requests")

REPO     = os.environ.get("GITHUB_REPO", "FTPLabs/FMailSender")
WORKFLOW = "release.yml"


def _headers() -> dict:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        sys.exit(
            "❌ Переменная GITHUB_TOKEN не задана.\n"
            "   Создайте PAT с правами repo + admin:repo:\n"
            "   https://github.com/settings/tokens"
        )
    return {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }


def set_visibility(private: bool) -> bool:
    label = "ПРИВАТНЫМ" if private else "ПУБЛИЧНЫМ"
    resp = requests.patch(
        f"https://api.github.com/repos/{REPO}",
        headers=_headers(),
        json={"private": private},
        timeout=30,
    )
    if resp.status_code == 200:
        print(f"  ✅ Репозиторий → {label}")
        return True
    print(f"  ⚠️  HTTP {resp.status_code} при переключении в {label}")
    print(f"     {resp.text[:300]}")
    return False


def trigger_workflow(tag: str) -> bool:
    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
        headers=_headers(),
        json={"ref": "main", "inputs": {"tag_name": tag}},
        timeout=30,
    )
    if resp.status_code == 204:
        print(f"  ✅ Workflow запущен: {WORKFLOW} (тег: {tag})")
        return True
    print(f"  ❌ Ошибка HTTP {resp.status_code}: {resp.text[:300]}")
    return False


def wait_for_run(timeout_min: int = 40) -> tuple[bool, str]:
    """Ждёт завершения последнего workflow_dispatch-рана. Возвращает (success, url)."""
    print(f"  ⏳ Жду появления run (таймаут: {timeout_min} мин)…")
    deadline = time.time() + timeout_min * 60
    run_id = run_url = None

    for attempt in range(40):
        time.sleep(8)
        data = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/runs?per_page=5",
            headers=_headers(), timeout=20,
        ).json()
        runs = [r for r in data.get("workflow_runs", []) if r.get("event") == "workflow_dispatch"]
        if runs:
            run_id  = runs[0]["id"]
            run_url = runs[0]["html_url"]
            print(f"  🔗 Run: {run_url}")
            break

    if not run_id:
        return False, ""

    dot = 0
    while time.time() < deadline:
        time.sleep(20)
        run = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}",
            headers=_headers(), timeout=20,
        ).json()
        status     = run.get("status", "?")
        conclusion = run.get("conclusion")
        dots = "." * ((dot % 4) + 1)
        dot += 1
        print(f"  [{status}/{conclusion or '...'}]{dots}", end="\r", flush=True)

        if status == "completed":
            ok = conclusion == "success"
            print(f"\n  {'✅' if ok else '❌'} Завершено: {conclusion}")
            return ok, run_url

    print("\n  ⚠️  Таймаут ожидания сборки")
    return False, run_url or ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Билд EXE с автоматическим переключением видимости репозитория"
    )
    ap.add_argument("tag", help="Тег релиза, например v3.5.4")
    ap.add_argument("--no-wait", action="store_true",
                    help="Не ждать завершения (workflow сам сделает репо приватным)")
    ap.add_argument("--timeout", type=int, default=40,
                    help="Таймаут ожидания в минутах (по умолчанию: 40)")
    args = ap.parse_args()

    print()
    print("╔═══════════════════════════════════════╗")
    print("║   FMailSender Release Builder         ║")
    print("╚═══════════════════════════════════════╝")
    print(f"  Репо : {REPO}")
    print(f"  Тег  : {args.tag}")
    print()

    print("1/3 Делаем репозиторий ПУБЛИЧНЫМ…")
    if not set_visibility(private=False):
        print("     Проверьте, что GITHUB_TOKEN имеет права admin:repo")
        sys.exit(1)
    time.sleep(3)

    print("\n2/3 Запускаем сборку…")
    if not trigger_workflow(args.tag):
        print("     Откатываем видимость…")
        set_visibility(private=True)
        sys.exit(1)

    if args.no_wait:
        print()
        print("⚡ --no-wait: не ждём. Workflow сам сделает репо приватным после сборки.")
        print(f"   Прогресс: https://github.com/{REPO}/actions")
        return

    print("\n3/3 Ожидаем завершения сборки…")
    ok, url = wait_for_run(timeout_min=args.timeout)

    if not ok:
        print()
        print("⚠️  Сборка не прошла или таймаут. Принудительно делаем репо приватным…")
        set_visibility(private=True)
        sys.exit(1)

    print()
    print("🎉 Готово!")
    print(f"   EXE прикреплён к релизу: https://github.com/{REPO}/releases/tag/{args.tag}")
    print("   (Репозиторий уже приватный — restore-privacy job сработал)")


if __name__ == "__main__":
    main()
