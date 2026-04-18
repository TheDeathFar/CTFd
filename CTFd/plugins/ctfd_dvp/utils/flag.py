"""
Генерация уникальных флагов для каждого студента.
"""

import hashlib
from CTFd.utils import get_config


def generate_flag(user_id, challenge_id):
    """
    Генерирует уникальный флаг для пары (пользователь, задача).
    Флаг имеет формат FLAG{32-символьный хеш}.
    """
    secret = get_config("SECRET_KEY", "default-secret-key-for-ctfd")
    raw = f"dvp:{user_id}:{challenge_id}:{secret}"
    flag_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"FLAG{{{flag_hash}}}"