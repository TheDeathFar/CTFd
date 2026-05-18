"""
API-эндпоинты для управления окружениями DVP.
"""

import time
import datetime
from flask import current_app, request, jsonify
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.models import db

from .dvp_client import dvp_client
from .models import DVPEnvironment
from .utils.subdomain import generate_subdomain
from .utils.cache import get_redis
from .decorators import admin_required


def load_routes(app):
    
    @app.route("/api/v1/dvp/launch", methods=["POST"])
    @authed_only
    def launch_environment():
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        challenge_class = CHALLENGE_CLASSES.get("dvp_dynamic")
        if not challenge_class:
            return jsonify({"error": "DVP challenge class not found"}), 500
        
        dvp_challenge = challenge_class.model.query.filter_by(id=challenge_id).first()
        if not dvp_challenge:
            return jsonify({"error": "Challenge not found"}), 404
        
        existing = DVPEnvironment.query.filter_by(
            user_id=user.id, challenge_id=challenge_id
        ).first()
        
        if existing and existing.status == "active":
            now = int(time.time())
            if now < existing.expires_at:
                return jsonify({
                    "status": "already_running",
                    "url": f"https://{existing.subdomain}" if existing.subdomain else "",
                    "expires_at": existing.expires_at,
                })
            else:
                dvp_client.delete_environment(user.id, challenge_id)
                existing.status = "terminated"
                existing.expires_at = int(time.time())
                db.session.commit()
        
        subdomain = generate_subdomain(
            dvp_challenge.subdomain_template, user.id, challenge_id
        )
        
        config = {
            "git_repo_url": dvp_challenge.git_repo_url,
            "git_ref": dvp_challenge.git_ref,
            "chart_path": dvp_challenge.chart_path,
            "helm_values": dvp_challenge.helm_values,
            "timeout": dvp_challenge.timeout,
            "subdomain": subdomain,
        }
        
        try:
            result = dvp_client.create_environment(user.id, challenge_id, config)
            
            now = int(time.time())
            env = DVPEnvironment(
                user_id=user.id,
                challenge_id=challenge_id,
                project_name=result["project"],
                subdomain=result.get("subdomain", ""),
                check_status="pending",
                status="active",
                created_at=now,
                expires_at=now + dvp_challenge.timeout
            )
            db.session.add(env)
            db.session.commit()
            
            r = get_redis()
            if r:
                r.setex(f"dvp:env:{user.id}:{challenge_id}", dvp_challenge.timeout, result["project"])
            
            return jsonify({
                "status": "launched",
                "url": result.get("url", ""),
                "expires_at": env.expires_at
            })
            
        except Exception as e:
            current_app.logger.error(f"Failed to launch DVP environment: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/v1/dvp/terminate", methods=["POST"])
    @authed_only
    def terminate_environment():
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id, challenge_id=challenge_id, status="active"
        ).first()
        
        if env:
            try:
                dvp_client.delete_environment(user.id, challenge_id)
            except:
                pass
            
            env.status = "terminated"
            env.expires_at = int(time.time())
            db.session.commit()
            
            r = get_redis()
            if r:
                r.delete(f"dvp:env:{user.id}:{challenge_id}")
        
        return jsonify({"status": "terminated"})
    
    @app.route("/api/v1/dvp/status", methods=["GET"])
    @authed_only
    def get_status():
        user = get_current_user()
        challenge_id = request.args.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id, challenge_id=challenge_id, status="active"
        ).first()
        
        if not env:
            return jsonify({"status": "not_found"})
        
        now = int(time.time())
        if now > env.expires_at:
            try:
                dvp_client.delete_environment(user.id, challenge_id)
            except:
                pass
            env.status = "terminated"
            env.expires_at = int(time.time())
            db.session.commit()
            
            r = get_redis()
            if r:
                r.delete(f"dvp:env:{user.id}:{challenge_id}")
            return jsonify({"status": "expired"})
        
        urls = []
        try:
            ingresses = dvp_client._k8s["networking_v1"].list_namespaced_ingress(namespace=env.project_name)
            for ing in ingresses.items:
                for rule in ing.spec.rules:
                    urls.append(f"https://{rule.host}")
        except:
            pass
        
        return jsonify({
            "status": "running",
            "urls": urls,
            "check_status": env.check_status,
            "expires_at": env.expires_at,
            "time_remaining": env.expires_at - now
        })
    
    @app.route("/api/v1/dvp/check", methods=["POST"])
    @authed_only
    def check_environment():
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        challenge_class = CHALLENGE_CLASSES.get("dvp_dynamic")
        dvp_challenge = challenge_class.model.query.filter_by(id=challenge_id).first()
        
        if not dvp_challenge or not dvp_challenge.check_script:
            return jsonify({"status": "error", "message": "Скрипт проверки не задан"}), 400
        
        result = dvp_client.execute_check_script(user.id, challenge_id, dvp_challenge.check_script)
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id, challenge_id=challenge_id, status="active"
        ).first()
        if env:
            env.check_status = "success" if result["success"] else "failed"
            db.session.commit()
        
        if result["success"]:
            return jsonify({"status": "success", "message": "Задание выполнено!"})
        else:
            return jsonify({"status": "failed", "message": result.get("output", "Ошибка проверки")})
    
    @app.route("/api/v1/dvp/extend", methods=["POST"])
    @authed_only
    def extend_environment():
        user = get_current_user()
        data = request.get_json() or {}
        challenge_id = data.get("challenge_id")
        extend_by = data.get("extend_by", 1800)
        
        if not challenge_id:
            return jsonify({"error": "challenge_id is required"}), 400
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id, challenge_id=challenge_id, status="active"
        ).first()
        
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        env.expires_at += extend_by
        db.session.commit()
        
        remaining = env.expires_at - int(time.time())
        if remaining > 0:
            r = get_redis()
            if r:
                r.expire(f"dvp:env:{user.id}:{challenge_id}", remaining)
        
        return jsonify({
            "status": "extended",
            "expires_at": env.expires_at,
            "time_remaining": remaining
        })
    
    @app.route("/api/v1/dvp/mock/status", methods=["GET"])
    def get_mock_status():
        return jsonify({
            "mock_mode": dvp_client.mock_mode,
            "environments": dvp_client.list_all_environments() if dvp_client.mock_mode else []
        })
    
    @app.route("/api/v1/dvp/admin/environments", methods=["GET"])
    @admin_required
    def admin_list_environments():
        envs = DVPEnvironment.query.order_by(DVPEnvironment.created_at.desc()).all()
        result = []
        for env in envs:
            result.append({
                "id": env.id,
                "user_id": env.user_id,
                "challenge_id": env.challenge_id,
                "project_name": env.project_name,
                "subdomain": env.subdomain,
                "check_status": env.check_status,
                "status": env.status,
                "created_at": datetime.datetime.fromtimestamp(env.created_at).strftime("%Y-%m-%d %H:%M:%S") if env.created_at else "",
                "expires_at": datetime.datetime.fromtimestamp(env.expires_at).strftime("%Y-%m-%d %H:%M:%S") if env.expires_at else "",
                "time_remaining": max(0, env.expires_at - int(time.time())) if env.status == "active" else 0
            })
        return jsonify({"environments": result})
    
    @app.route("/api/v1/dvp/admin/environments/<int:env_id>/terminate", methods=["POST"])
    @admin_required
    def admin_terminate_environment_post(env_id):
        env = DVPEnvironment.query.get(env_id)
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        try:
            dvp_client.delete_environment(env.user_id, env.challenge_id)
        except:
            pass
        
        env.status = "terminated"
        env.expires_at = int(time.time())
        db.session.commit()
        
        r = get_redis()
        if r:
            r.delete(f"dvp:env:{env.user_id}:{env.challenge_id}")
        
        return jsonify({"status": "terminated"})
    
    @app.route("/api/v1/dvp/admin/environments/<int:env_id>/extend", methods=["POST"])
    @admin_required
    def admin_extend_environment(env_id):
        env = DVPEnvironment.query.get(env_id)
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        data = request.get_json() or {}
        extend_by = data.get("extend_by", 1800)
        
        env.expires_at += extend_by
        db.session.commit()
        
        return jsonify({"status": "extended", "expires_at": env.expires_at})
    
    @app.route("/api/v1/dvp/admin/environments/<int:env_id>/delete", methods=["POST"])
    @admin_required
    def admin_delete_environment(env_id):
        """Полное удаление записи об окружении из БД."""
        env = DVPEnvironment.query.get(env_id)
        if not env:
            return jsonify({"error": "Environment not found"}), 404
        
        db.session.delete(env)
        db.session.commit()
        
        r = get_redis()
        if r:
            r.delete(f"dvp:env:{env.user_id}:{env.challenge_id}")
        
        return jsonify({"status": "deleted"})