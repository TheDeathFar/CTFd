"""
Генерация поддоменов для доступа к окружениям.
"""

from flask import current_app


def generate_subdomain(template, user_id, challenge_id):
    """
    Генерирует поддомен на основе шаблона.
    
    Поддерживаемые переменные:
    - {user_id} — ID пользователя
    - {user_name} — имя пользователя
    - {challenge_id} — ID челленджа
    
    Если шаблон пустой, используется формат по умолчанию:
    user-{user_id}-challenge-{challenge_id}.{domain}
    """
    if not template:
        domain = current_app.config.get("DVP_INGRESS_DOMAIN", "polygon.local")
        return f"user-{user_id}-challenge-{challenge_id}.{domain}"
    
    # Подстановка переменных
    result = template.replace("{user_id}", str(user_id))
    result = result.replace("{challenge_id}", str(challenge_id))
    
    # {user_name} пока не поддерживается, но можно добавить
    # user = Users.query.get(user_id)
    # result = result.replace("{user_name}", user.name if user else str(user_id))
    
    return result