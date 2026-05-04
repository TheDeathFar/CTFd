"""
Административная панель для управления окружениями DVP.
"""

import time
import datetime
from flask import render_template, jsonify, request
from CTFd.utils.decorators import admins_only
from CTFd.models import db, Users, Challenges

from ..models import DVPEnvironment
from ..dvp_client import dvp_client


def load_admin_routes(admin_bp):
    
    @admin_bp.route("/admin/environments")
    @admins_only
    def list_environments():
        envs = DVPEnvironment.query.order_by(DVPEnvironment.created_at.desc()).all()
        
        enriched = []
        for env in envs:
            user = Users.query.get(env.user_id)
            challenge = Challenges.query.get(env.challenge_id)
            
            # Форматируем даты
            created_str = datetime.datetime.fromtimestamp(env.created_at).strftime("%Y-%m-%d %H:%M:%S")
            expires_str = datetime.datetime.fromtimestamp(env.expires_at).strftime("%Y-%m-%d %H:%M:%S")

            enriched.append({
                "id": env.id,
                "user_id": env.user_id,
                "user_name": user.name if user else f"User {env.user_id}",
                "challenge_id": env.challenge_id,
                "challenge_name": challenge.name if challenge else f"Challenge {env.challenge_id}",
                "project_name": env.project_name,
                "subdomain": env.subdomain,
                "check_status": env.check_status or "pending",
                "created_at": created_str,
                "expires_at": expires_str,
                "time_remaining": max(0, env.expires_at - int(time.time()))
            })
        
        mock_envs = []
        if dvp_client.mock_mode:
            mock_envs = dvp_client.list_all_environments()
        
        return render_template(
            "admin_environments.html",
            environments=enriched,
            mock_environments=mock_envs,
            mock_mode=dvp_client.mock_mode
        )