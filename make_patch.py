"""
Генератор патч-бандла для релиза FMailSender.
Определяет изменённые .py-файлы с момента последнего тега,
создаёт patch_manifest_vNEW.json с SHA-256 и URL каждого файла.

Использование:
    python make_patch.py v3.4.1 v3.4.2
    python make_patch.py --auto          # автоматически определяет теги
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO = "FTPLabs/FMailSender"
GITHUB_RAW = f"https://raw.githubusercontent.com/{REPO}"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return r.stdout.strip()


def _get_changed_files(old_tag: str) -> list[str]:
    """Возвращает список изменённых .py файлов с момента old_tag."""
    raw = _git("diff", "--name-only", f"{old_tag}..HEAD", "--", "*.py")
    return [f for f in raw.splitlines() if f.strip() and Path(f.strip()).exists()]


def make_patch(old_tag: str, new_tag: str, dist_dir: Path) -> None:
    """Создаёт patch_manifest_vNEW.json в dist_dir."""
    new_ver = new_tag.lstrip("v")
    old_ver = old_tag.lstrip("v")

    changed = _get_changed_files(old_tag)

    if not changed:
        print(f"[patch] Нет изменённых .py файлов с {old_tag} -> пустой манифест")
        manifest = {
            "version": new_ver,
            "base_version": old_ver,
            "files": [],
        }
    else:
        files_info = []
        for rel in changed:
            p = Path(rel)
            data = p.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            url = f"{GITHUB_RAW}/{new_tag}/{rel}"
            files_info.append({
                "path": rel,
                "sha256": sha,
                "url": url,
                "size": len(data),
            })
            print(f"  + {rel} ({len(data):,} bytes)")

        total_kb = sum(f["size"] for f in files_info) / 1024
        print(f"[patch] {len(files_info)} файлов, ~{total_kb:.1f} КБ")

        manifest = {
            "version": new_ver,
            "base_version": old_ver,
            "files": files_info,
        }

    dist_dir.mkdir(parents=True, exist_ok=True)
    out = dist_dir / f"patch_manifest_{new_tag}.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[patch] Манифест: {out}")


def main() -> None:
    args = sys.argv[1:]

    if "--auto" in args:
        # Определяем теги автоматически: предпоследний и последний
        tags = _git("tag", "--sort=-version:refname").splitlines()
        if len(tags) < 2:
            print("[patch] Недостаточно тегов для авто-режима")
            sys.exit(0)
        old_tag, new_tag = tags[1], tags[0]
    elif len(args) >= 2:
        old_tag, new_tag = args[0], args[1]
    else:
        print(__doc__)
        sys.exit(1)

    print(f"[patch] {old_tag} -> {new_tag}")
    make_patch(old_tag, new_tag, Path("dist"))


if __name__ == "__main__":
    main()
