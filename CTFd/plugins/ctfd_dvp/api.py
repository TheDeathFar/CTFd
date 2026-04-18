"""
API-эндпоинты для управления окружениями DVP.
"""

import time
import datetime
from flask import current_app, Blueprint
from flask import request, jsonify
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.models import db

from .dvp_client import dvp_client
from .models import DVPEnvironment
from .utils.flag import generate_flag
from .utils.subdomain import generate_subdomain
from .utils.cache import redis_client
from .decorators import challenge_visible, admin_required


def load_routes(app):
    
    @app.route("/api/v1/dvp/launch", methods=["POST"])
    @authed_only
    def launch_environment():
        """
        Запуск окружения для студента.
        """
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        # Получаем конфигурацию челленджа
        challenge_class = CHALLENGE_CLASSES.get("dvp_dynamic")
        if not challenge_class:
            return jsonify({"error": "DVP challenge class not found"}), 500
        
        dvp_challenge = challenge_class.model.query.filter_by(id=challenge_id).first()
        if not dvp_challenge:
            return jsonify({"error": "Challenge not found"}), 404
        
        # Проверяем, нет ли уже активного окружения
        existing = DVPEnvironment.query.filter_by(
            user_id=user.id,
            challenge_id=challenge_id
        ).first()
        
        if existing:
            now = int(time.time())
            if now < existing.expires_at:
                return jsonify({
                    "status": "already_running",
                    "url": f"https://{existing.subdomain}",
                    "expires_at": existing.expires_at,
                    "flag": existing.flag if dvp_challenge.auto_submit_flag else None
                })
            else:
                # Окружение истекло, удаляем запись
                dvp_client.delete_environment(user.id, challenge_id)
                db.session.delete(existing)
                db.session.commit()
        
        # Генерируем параметры
        subdomain = generate_subdomain(
            dvp_challenge.subdomain_template,
            user.id,
            challenge_id
        )
        flag = generate_flag(user.id, challenge_id)
        
        # Конфиг для DVP
        config = {
            "environment_type": dvp_challenge.environment_type,
            "image": dvp_challenge.image,
            "ports": dvp_challenge.ports,
            "cpu": dvp_challenge.vm_cpu,
            "memory": dvp_challenge.vm_memory,
            "subdomain": subdomain
        }
        
        try:
            # Создаём окружение
            result = dvp_client.create_environment(user.id, challenge_id, config)
            
            # Сохраняем в БД
            now = int(time.time())
            env = DVPEnvironment(
                user_id=user.id,
                challenge_id=challenge_id,
                project_name=result["project"],
                subdomain=result["subdomain"],
                flag=flag,
                created_at=now,
                expires_at=now + dvp_challenge.timeout
            )
            db.session.add(env)
            db.session.commit()
            
            # Кэшируем в Redis
            redis_client.setex(
                f"dvp:env:{user.id}:{challenge_id}",
                dvp_challenge.timeout,
                result["project"]
            )
            
            return jsonify({
                "status": "launched",
                "url": result["url"],
                "subdomain": result["subdomain"],
                "flag": flag if dvp_challenge.auto_submit_flag else None,
                "expires_at": env.expires_at
            })
            
        except Exception as e:
            current_app.logger.error(f"Failed to launch DVP environment: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/v1/dvp/terminate", methods=["POST"])
    @authed_only
    def terminate_environment():
        """
        Остановка и удаление окружения.
        """
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id,
            challenge_id=challenge_id
        ).first()
        
        if env:
            try:
                dvp_client.delete_environment(user.id, challenge_id)
            except Exception as e:
                current_app.logger.warning(f"Failed to delete DVP environment: {e}")
            
            db.session.delete(env)
            db.session.commit()
            redis_client.delete(f"dvp:env:{user.id}:{challenge_id}")
        
        return jsonify({"status": "terminated"})
    
    @app.route("/api/v1/dvp/status", methods=["GET"])
    @authed_only
    def get_status():
        """
        Получение статуса окружения.
        """
        user = get_current_user()
        challenge_id = request.args.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id,
            challenge_id=challenge_id
        ).first()
        
        if not env:
            return jsonify({"status": "not_found"})
        
        now = int(time.time())
        if now > env.expires_at:
            # Окружение истекло
            try:
                dvp_client.delete_environment(user.id, challenge_id)
            except:
                pass
            db.session.delete(env)
            db.session.commit()
            redis_client.delete(f"dvp:env:{user.id}:{challenge_id}")
            return jsonify({"status": "expired"})
        
        # Получаем статус из DVP
        try:
            dvp_status = dvp_client.get_environment_status(user.id, challenge_id)
            status_text = "running" if dvp_status else "unknown"
        except:
            status_text = "unknown"
        
        return jsonify({
            "status": status_text,
            "url": f"https://{env.subdomain}",
            "expires_at": env.expires_at,
            "time_remaining": env.expires_at - now
        })
    
    @app.route("/api/v1/dvp/extend", methods=["POST"])
    @authed_only
    def extend_environment():
        """
        Продление времени жизни окружения.
        """
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        extend_by = data.get("extend_by", 1800)  # по умолчанию +30 минут
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id,
            challenge_id=challenge_id
        ).first()
        
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        env.expires_at += extend_by
        db.session.commit()
        
        # Обновляем TTL в Redis
        remaining = env.expires_at - int(time.time())
        if remaining > 0:
            redis_client.expire(f"dvp:env:{user.id}:{challenge_id}", remaining)
        
        return jsonify({
            "status": "extended",
            "expires_at": env.expires_at,
            "time_remaining": remaining
        })
    
    @app.route("/api/v1/dvp/mock/status", methods=["GET"])
    def get_mock_status():
        """
        Эндпоинт для проверки режима эмуляции.
        Доступен без авторизации.
        """
        return jsonify({
            "mock_mode": dvp_client.mock_mode,
            "environments": dvp_client.list_all_environments() if dvp_client.mock_mode else []
        })
    
    @app.route("/api/v1/dvp/admin/environments", methods=["GET"])
    @admin_required
    def admin_list_environments():
        """
        Список всех активных окружений (только для админов).
        """
        envs = DVPEnvironment.query.all()
        result = []
        for env in envs:
            result.append({
                "id": env.id,
                "user_id": env.user_id,
                "challenge_id": env.challenge_id,
                "project_name": env.project_name,
                "subdomain": env.subdomain,
                "created_at": datetime.datetime.fromtimestamp(env.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                "expires_at": datetime.datetime.fromtimestamp(env.expires_at).strftime("%Y-%m-%d %H:%M:%S"),
                "time_remaining": max(0, env.expires_at - int(time.time()))
            })
        return jsonify({"environments": result})
    
    @app.route("/api/v1/dvp/admin/environments/<int:env_id>/terminate", methods=["DELETE"])
    @admin_required
    def admin_terminate_environment(env_id):
        """
        Принудительное удаление окружения администратором.
        """
        env = DVPEnvironment.query.get(env_id)
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        try:
            dvp_client.delete_environment(env.user_id, env.challenge_id)
        except:
            pass
        
        db.session.delete(env)
        db.session.commit()
        redis_client.delete(f"dvp:env:{env.user_id}:{env.challenge_id}")
        
        return jsonify({"status": "terminated"})
    
    @app.route("/api/v1/dvp/admin/environments/<int:env_id>/extend", methods=["POST"])
    @admin_required
    def admin_extend_environment(env_id):
        """
        Продление времени окружения администратором.
        """
        env = DVPEnvironment.query.get(env_id)
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        data = request.get_json() or {}
        extend_by = data.get("extend_by", 1800)  # +30 минут по умолчанию
        
        env.expires_at += extend_by
        db.session.commit()
        
        return jsonify({"status": "extended", "expires_at": env.expires_at})