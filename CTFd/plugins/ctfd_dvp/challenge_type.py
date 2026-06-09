"""
Класс челленджа для CTFd.
"""

from CTFd.models import db, Challenges
from CTFd.plugins.dynamic_challenges import DynamicValueChallenge

from .models import DVPChallengeModel, DVPEnvironment
from .dvp_client import dvp_client


class DVPChallenge(DynamicValueChallenge):
    id = "dvp_dynamic"
    name = "Динамическая DVP-среда"
    
    model = DVPChallengeModel
    challenge_model = Challenges
    
    @classmethod
    def read(cls, challenge):
        dvp_challenge = cls.model.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "description": challenge.description,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "type_data": {"id": cls.id, "name": cls.name, "templates": cls.templates, "scripts": cls.scripts},
        }
        if dvp_challenge:
            data.update({
                "git_repo_url": dvp_challenge.git_repo_url,
                "git_ref": dvp_challenge.git_ref,
                "chart_path": dvp_challenge.chart_path,
                "helm_values": dvp_challenge.helm_values,
                "timeout": dvp_challenge.timeout,
                "subdomain_template": dvp_challenge.subdomain_template,
                "check_script": dvp_challenge.check_script,
                "auto_submit_flag": dvp_challenge.auto_submit_flag,
                "strategy": dvp_challenge.strategy,
            })
        return data
    
    @classmethod
    def create(cls, request):
        data = request.form or request.get_json()
        challenge = cls.challenge_model(
            name=data.get("name", "New DVP Lab"),
            category=data.get("category", "DVP"),
            value=int(data.get("value", 100)),
            description=data.get("description", ""),
            state=data.get("state", "visible"),
            type=cls.id,
        )
        db.session.add(challenge)
        db.session.flush()
        dvp_challenge = cls.model(
            id=challenge.id,
            git_repo_url=data.get("git_repo_url", ""),
            git_ref=data.get("git_ref", "main"),
            chart_path=data.get("chart_path", "."),
            helm_values=data.get("helm_values", "{}"),
            timeout=int(data.get("timeout", 3600)),
            subdomain_template=data.get("subdomain_template", ""),
            check_script=data.get("check_script", ""),
            auto_submit_flag=bool(data.get("auto_submit_flag", False)),
            strategy=data.get("strategy", "regular"),
        )
        db.session.add(dvp_challenge)
        db.session.commit()
        return challenge
    
    @classmethod
    def update(cls, challenge, request):
        data = request.form or request.get_json()
        challenge.name = data.get("name", challenge.name)
        challenge.category = data.get("category", challenge.category)
        challenge.value = int(data.get("value", challenge.value))
        challenge.description = data.get("description", challenge.description)
        challenge.state = data.get("state", challenge.state)
        dvp_challenge = cls.model.query.filter_by(id=challenge.id).first()
        if dvp_challenge:
            dvp_challenge.git_repo_url = data.get("git_repo_url", dvp_challenge.git_repo_url)
            dvp_challenge.git_ref = data.get("git_ref", dvp_challenge.git_ref)
            dvp_challenge.chart_path = data.get("chart_path", dvp_challenge.chart_path)
            dvp_challenge.helm_values = data.get("helm_values", dvp_challenge.helm_values)
            dvp_challenge.timeout = int(data.get("timeout", dvp_challenge.timeout))
            dvp_challenge.subdomain_template = data.get("subdomain_template", dvp_challenge.subdomain_template)
            dvp_challenge.check_script = data.get("check_script", dvp_challenge.check_script)
            dvp_challenge.auto_submit_flag = bool(data.get("auto_submit_flag", dvp_challenge.auto_submit_flag))
            dvp_challenge.strategy = data.get("strategy", dvp_challenge.strategy)
        db.session.commit()
        return challenge
    
    @classmethod
    def delete(cls, challenge):
        for env in DVPEnvironment.query.filter_by(challenge_id=challenge.id).all():
            try:
                dvp_client.delete_environment(env.user_id, env.challenge_id)
            except:
                pass
            db.session.delete(env)
        dvp_challenge = cls.model.query.filter_by(id=challenge.id).first()
        if dvp_challenge:
            db.session.delete(dvp_challenge)
        db.session.delete(challenge)
        db.session.commit()
        return True
    
    @classmethod
    def attempt(cls, challenge, request):
        from CTFd.utils.user import get_current_user
        user = get_current_user()
        env = DVPEnvironment.query.filter_by(user_id=user.id, challenge_id=challenge.id).first()
        if not env:
            return False, "Окружение не запущено."
        if env.check_status == "success":
            return True, "Задание выполнено!"
        elif env.check_status == "failed":
            return False, "Задание не выполнено."
        else:
            return False, "Проверка ещё не запущена."
    
    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)