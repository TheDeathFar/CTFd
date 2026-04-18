"""
Класс челленджа для CTFd.
"""

from CTFd.models import db, Challenges
from CTFd.plugins.dynamic_challenges import DynamicValueChallenge

from .models import DVPChallengeModel, DVPEnvironment
from .dvp_client import dvp_client


class DVPChallenge(DynamicValueChallenge):
    """
    Тип челленджа "Динамическая DVP-среда".
    """
    id = "dvp_dynamic"
    name = "Динамическая DVP-среда"
    
    model = DVPChallengeModel
    challenge_model = Challenges
    
    # templates и scripts будут присвоены в __init__.py
    
    @classmethod
    def read(cls, challenge):
        """
        Чтение данных задачи.
        """
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
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        
        if dvp_challenge:
            data.update({
                "environment_type": dvp_challenge.environment_type,
                "image": dvp_challenge.image,
                "ports": dvp_challenge.ports,
                "vm_cpu": dvp_challenge.vm_cpu,
                "vm_memory": dvp_challenge.vm_memory,
                "timeout": dvp_challenge.timeout,
                "subdomain_template": dvp_challenge.subdomain_template,
                "check_script": dvp_challenge.check_script,
                "auto_submit_flag": dvp_challenge.auto_submit_flag,
            })
        
        return data
    
    @classmethod
    def create(cls, request):
        """
        Создание новой задачи.
        """
        data = request.form or request.get_json()
        
        challenge = cls.challenge_model(
            name=data.get("name", "New DVP Challenge"),
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
            environment_type=data.get("environment_type", "container"),
            image=data.get("image", "nginx:alpine"),
            ports=data.get("ports", "80"),
            vm_cpu=int(data.get("vm_cpu", 2)),
            vm_memory=data.get("vm_memory", "2Gi"),
            timeout=int(data.get("timeout", 3600)),
            subdomain_template=data.get("subdomain_template", ""),
            check_script=data.get("check_script", ""),
            auto_submit_flag=bool(data.get("auto_submit_flag", False)),
        )
        db.session.add(dvp_challenge)
        db.session.commit()
        
        return challenge
    
    @classmethod
    def update(cls, challenge, request):
        """
        Обновление задачи.
        """
        data = request.form or request.get_json()
        
        challenge.name = data.get("name", challenge.name)
        challenge.category = data.get("category", challenge.category)
        challenge.value = int(data.get("value", challenge.value))
        challenge.description = data.get("description", challenge.description)
        challenge.state = data.get("state", challenge.state)
        
        dvp_challenge = cls.model.query.filter_by(id=challenge.id).first()
        if dvp_challenge:
            dvp_challenge.environment_type = data.get("environment_type", dvp_challenge.environment_type)
            dvp_challenge.image = data.get("image", dvp_challenge.image)
            dvp_challenge.ports = data.get("ports", dvp_challenge.ports)
            dvp_challenge.vm_cpu = int(data.get("vm_cpu", dvp_challenge.vm_cpu))
            dvp_challenge.vm_memory = data.get("vm_memory", dvp_challenge.vm_memory)
            dvp_challenge.timeout = int(data.get("timeout", dvp_challenge.timeout))
            dvp_challenge.subdomain_template = data.get("subdomain_template", dvp_challenge.subdomain_template)
            dvp_challenge.check_script = data.get("check_script", dvp_challenge.check_script)
            dvp_challenge.auto_submit_flag = bool(data.get("auto_submit_flag", dvp_challenge.auto_submit_flag))
        
        db.session.commit()
        return challenge
    
    @classmethod
    def delete(cls, challenge):
        """
        Удаление задачи.
        """
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
        """
        Проверка флага.
        """
        from CTFd.utils.user import get_current_user
        
        data = request.form or request.get_json()
        submission = data.get("submission", "").strip()
        user = get_current_user()
        
        env = DVPEnvironment.query.filter_by(
            user_id=user.id,
            challenge_id=challenge.id
        ).first()
        
        if not env:
            return False, "Окружение не запущено. Нажмите «Запустить окружение»."
        
        if env.flag == submission:
            return True, "Правильно!"
        return False, "Неверный флаг"
    
    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)