"""
Модели данных для плагина CTFd-DVP.
"""

from CTFd.models import db
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey


class DVPChallengeModel(db.Model):
    """
    Расширенная модель челленджа.
    Хранит настройки для развёртывания окружения в DVP.
    """
    __tablename__ = "dvp_challenges"
    
    # Связь с основной таблицей challenges
    id = Column(
        Integer,
        ForeignKey("challenges.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # === Основные параметры окружения ===
    
    # Тип окружения: "container" или "virtualmachine"
    environment_type = Column(String(32), default="container", nullable=False)
    
    # Docker-образ (для контейнеров) или ContainerDisk (для ВМ)
    image = Column(String(256), nullable=False, default="nginx:alpine")
    
    # Порты для проброса (только для контейнеров)
    # Формат: "80,443" или "80:8080,443:8443"
    ports = Column(String(128), default="80")
    
    # === Параметры виртуальной машины ===
    
    # Количество ядер CPU
    vm_cpu = Column(Integer, default=2)
    
    # Объём оперативной памяти (например, "2Gi", "4Gi")
    vm_memory = Column(String(16), default="2Gi")
    
    # === Общие настройки ===
    
    # Время жизни окружения в секундах
    timeout = Column(Integer, default=3600)
    
    # Шаблон поддомена для доступа
    # Можно использовать {user_id} и {challenge_id}
    subdomain_template = Column(String(128), default="")
    
    # Скрипт проверки выполнения задания (Bash)
    check_script = Column(Text, default="")
    
    # Автоматически отправлять флаг при успешной проверке
    auto_submit_flag = Column(Boolean, default=False)
    
    def __init__(self, **kwargs):
        super(DVPChallengeModel, self).__init__(**kwargs)
    
    def __repr__(self):
        return f"<DVPChallenge id={self.id} type={self.environment_type}>"


class DVPEnvironment(db.Model):
    """
    Активные окружения студентов.
    Хранит информацию о запущенных средах.
    """
    __tablename__ = "dvp_environments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ID пользователя, запустившего окружение
    user_id = Column(Integer, nullable=False)
    
    # ID челленджа
    challenge_id = Column(Integer, nullable=False)
    
    # Имя проекта в DVP (аналог Namespace)
    project_name = Column(String(128), nullable=False)
    
    # Поддомен для доступа к окружению
    subdomain = Column(String(256))
    
    # Уникальный флаг для этого экземпляра
    flag = Column(String(128))
    
    # Timestamp создания
    created_at = Column(Integer, nullable=False)
    
    # Timestamp истечения срока жизни
    expires_at = Column(Integer, nullable=False)
    
    def __init__(self, **kwargs):
        super(DVPEnvironment, self).__init__(**kwargs)
    
    def __repr__(self):
        return f"<DVPEnvironment user={self.user_id} challenge={self.challenge_id}>"