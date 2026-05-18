"""
Модели данных для плагина CTFd-DVP.
"""

from CTFd.models import db
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey


class DVPChallengeModel(db.Model):
    """
    Расширенная модель челленджа.
    Хранит настройки для развёртывания окружения через ArgoCD.
    """
    __tablename__ = "dvp_challenges"
    
    id = Column(
        Integer,
        ForeignKey("challenges.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # === Git-репозиторий с Helm-чартом ===
    git_repo_url = Column(String(512), nullable=False, default="")
    git_ref = Column(String(64), default="main")
    chart_path = Column(String(256), default=".")
    helm_values = Column(Text, default="{}")
    
    # === Общие настройки ===
    timeout = Column(Integer, default=3600)
    subdomain_template = Column(String(128), default="")
    check_script = Column(Text, default="")
    auto_submit_flag = Column(Boolean, default=False)
    
    def __init__(self, **kwargs):
        super(DVPChallengeModel, self).__init__(**kwargs)
    
    def __repr__(self):
        return f"<DVPChallenge id={self.id} git={self.git_repo_url}>"


class DVPEnvironment(db.Model):
    """
    Активные окружения студентов.
    Хранит информацию о запущенных средах.
    """
    __tablename__ = "dvp_environments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    challenge_id = Column(Integer, nullable=False)
    project_name = Column(String(128), nullable=False)
    subdomain = Column(String(256))
    check_status = Column(String(32), default="pending")  # pending, success, failed
    status = Column(String(32), default="active")  # active, terminated
    created_at = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)
    
    def __init__(self, **kwargs):
        super(DVPEnvironment, self).__init__(**kwargs)
    
    def __repr__(self):
        return f"<DVPEnvironment user={self.user_id} challenge={self.challenge_id}>"