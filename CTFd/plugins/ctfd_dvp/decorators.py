"""
Декораторы для защиты API-эндпоинтов.
"""

from functools import wraps
from flask import abort
from CTFd.utils.user import is_admin, get_current_user
from CTFd.models import Challenges
from .models import DVPChallengeModel


def admin_required(f):
    """
    Декоратор для эндпоинтов, доступных только администраторам.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def challenge_visible(f):
    """
    Декоратор для проверки, что челлендж существует и видим.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Пытаемся получить challenge_id из разных источников
        challenge_id = kwargs.get("challenge_id")
        if not challenge_id:
            # Может быть в JSON-запросе
            from flask import request
            if request.is_json:
                data = request.get_json() or {}
                challenge_id = data.get("challenge_id")
            elif request.form:
                challenge_id = request.form.get("challenge_id")
            elif request.args:
                challenge_id = request.args.get("challenge_id")
        
        if challenge_id:
            challenge = Challenges.query.filter_by(id=challenge_id).first()
            if not challenge:
                abort(404)
            if challenge.state != "visible" and not is_admin():
                abort(403)
        
        return f(*args, **kwargs)
    return decorated_function