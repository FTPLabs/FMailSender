"""
Автоматическое обновление отключено согласно правилам площадки (п. 1.8):
«Запрещена продажа ПО с функцией автоматического обновления.
Разрешается публикация обновленных версий для свободного скачивания.»

Новые версии публикуются на странице релизов:
https://github.com/FTPLabs/EmailSenderPro/releases
"""
import logging

logger = logging.getLogger("updater")


def check_for_updates(*args, **kwargs):
    """Проверка обновлений отключена (правило 1.8)."""
    return None


def apply_update_windows(*args, **kwargs):
    """Применение обновлений отключено (правило 1.8)."""
    return False


def is_newer(*args, **kwargs):
    return False
