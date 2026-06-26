#!/usr/bin/env python3
"""
FMailSender RLM Agent — запуск через CLI
Использует gptvibe.ru как OpenAI-совместимый бэкенд (без платного API)
"""
import os, sys, json, argparse
from pathlib import Path

# Убедимся что .env загружен
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

REQUIRED = ["OPENAI_API_KEY"]
for var in REQUIRED:
    if not os.environ.get(var):
        print(f"❌ Нужен env var: {var}", file=sys.stderr)
        sys.exit(1)

# gptvibe.ru как base_url
os.environ.setdefault("OPENAI_BASE_URL", "https://gptvibe.ru/v1")

def run_query(query: str, verbose: bool = False):
    """Отправить вопрос в RLM агента и получить ответ."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Устанавливаю openai...", file=sys.stderr)
        os.system(f"{sys.executable} -m pip install openai -q")
        from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://gptvibe.ru/v1"),
    )

    # Загружаем память из sessions.json
    memory_file = Path(__file__).parent / "memory" / "sessions.json"
    memory_file.parent.mkdir(exist_ok=True)
    sessions = []
    if memory_file.exists():
        try:
            sessions = json.loads(memory_file.read_text())[-20:]  # последние 20
        except Exception:
            sessions = []

    system_prompt = """Ты — AI-агент FMailSender. Помогаешь с настройкой email-рассылок, 
диагностикой SMTP, исправлением багов. Всегда отвечаешь на русском языке.

Известные проблемы:
- SOCKS5 код 2 = прокси блокирует порт — исправлено в v4.4.6 (автоматический fallback)
- QPushButton RuntimeError — исправлено в v4.4.6 (try/except RuntimeError в _poll_send)

Конфигурации SMTP: Gmail:465/587, Outlook:587, Rambler:465/587, Yahoo:465
При ошибке прокси — использует прямое подключение автоматически."""

    messages = [{"role": "system", "content": system_prompt}]
    # Добавить историю сессии
    for s in sessions:
        messages.append({"role": "user", "content": s.get("q", "")})
        messages.append({"role": "assistant", "content": s.get("a", "")})
    messages.append({"role": "user", "content": query})

    if verbose:
        print(f"🤖 Запрос: {query}")
        print(f"📡 Backend: {client.base_url}")

    resp = client.chat.completions.create(
        model=os.environ.get("RLM_MODEL", "gpt-4o-mini"),
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )
    answer = resp.choices[0].message.content

    # Сохранить в память
    sessions.append({"q": query, "a": answer})
    memory_file.write_text(json.dumps(sessions[-50:], ensure_ascii=False, indent=2))

    return answer

def main():
    parser = argparse.ArgumentParser(description="FMailSender RLM Agent")
    parser.add_argument("query", nargs="?", help="Вопрос агенту")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--diagnose", "-d", action="store_true",
                        help="Диагностика: проверить конфиг и подключение")
    args = parser.parse_args()

    if args.diagnose:
        print("🔍 Диагностика FMailSender RLM Agent")
        print(f"  OPENAI_BASE_URL: {os.environ.get('OPENAI_BASE_URL')}")
        print(f"  OPENAI_API_KEY:  {'✅ set' if os.environ.get('OPENAI_API_KEY') else '❌ not set'}")
        print(f"  GITHUB_TOKEN:    {'✅ set' if os.environ.get('GITHUB_TOKEN') else '❌ not set'}")
        print(f"  RLM_MODEL:       {os.environ.get('RLM_MODEL', 'gpt-4o-mini')}")
        # Тест соединения
        try:
            result = run_query("Скажи 'ОК' если слышишь меня.", verbose=False)
            print(f"  LLM Test:        ✅ {result[:60]}")
        except Exception as e:
            print(f"  LLM Test:        ❌ {e}")
        return

    if not args.query:
        print("Использование: python run_agent.py \"ваш вопрос\"")
        print("           или python run_agent.py --diagnose")
        sys.exit(1)

    answer = run_query(args.query, args.verbose)
    print(answer)

if __name__ == "__main__":
    main()
