"""
Клиент для работы с Deckhouse Virtualization Platform.
Поддерживает два режима:
- MOCK_MODE = True: эмуляция для локального тестирования
- MOCK_MODE = False: реальные HTTP-запросы к DVP API
"""

import json
import time
from flask import current_app


class DVPClient:
    """
    Универсальный клиент для Deckhouse DVP.
    Автоматически переключается между реальным API и эмуляцией.
    """
    
    def __init__(self, mock_mode=None):
        """
        Инициализация клиента.
        Если mock_mode не указан, берётся из конфига CTFd.
        """
        self.mock_mode = mock_mode if mock_mode is not None else self._get_config("MOCK_MODE", True)
        
        if self.mock_mode:
            from .mock_data import get_mock_client
            self._mock = get_mock_client()
            self._api_url = None
            self._token = None
            print("[DVP] 🧪 Running in MOCK MODE - no real cluster required")
        else:
            self._api_url = self._get_config("DVP_API_URL", "https://dvp.example.com/api")
            self._token = self._get_config("DVP_TOKEN", "")
            self._mock = None
            print(f"[DVP] 🔌 Running in REAL MODE - connecting to {self._api_url}")
    
    def _get_config(self, key, default=None):
        """
        Получить настройку из конфигурации CTFd.
        Ищет параметры с префиксом DVP_.
        """
        try:
            full_key = f"DVP_{key.upper()}" if not key.startswith("DVP_") else key.upper()
            return current_app.config.get(full_key, default)
        except RuntimeError:
            # Вне контекста приложения (например, при импорте)
            return default
    
    def _get_project_name(self, user_id, challenge_id):
        """Генерирует стандартное имя проекта для студента"""
        prefix = self._get_config("PROJECT_PREFIX", "student")
        return f"{prefix}-{user_id}-challenge-{challenge_id}"
    
    # ========== Публичные методы (единый интерфейс) ==========
    
    def create_environment(self, user_id, challenge_id, config):
        """
        Создать полное окружение для студента.
        
        config должен содержать:
        - environment_type: 'container' или 'virtualmachine'
        - image: Docker-образ или ContainerDisk
        - ports: строка с портами (для контейнеров)
        - cpu: количество ядер (для ВМ)
        - memory: объём памяти (для ВМ)
        - subdomain: поддомен для доступа
        
        Возвращает:
        {
            "project": "student-1-challenge-5",
            "subdomain": "user-1-challenge-5.polygon.local",
            "url": "https://..."
        }
        """
        project_name = config.get("project_name")
        if not project_name:
            project_name = self._get_project_name(user_id, challenge_id)
        
        config["project_name"] = project_name
        
        if self.mock_mode:
            return self._mock.create_environment(user_id, challenge_id, config)
        else:
            # TODO: Реальная реализация через HTTP-запросы к DVP API
            return self._create_environment_real(user_id, challenge_id, config)
    
    def delete_environment(self, user_id, challenge_id):
        """
        Удалить окружение студента.
        """
        project_name = self._get_project_name(user_id, challenge_id)
        
        if self.mock_mode:
            return self._mock.delete_environment(project_name)
        else:
            # TODO: Реальная реализация
            return self._delete_environment_real(project_name)
    
    def get_environment_status(self, user_id, challenge_id):
        """
        Получить статус окружения.
        """
        project_name = self._get_project_name(user_id, challenge_id)
        
        if self.mock_mode:
            return self._mock.get_environment_status(project_name)
        else:
            # TODO: Реальная реализация
            return self._get_environment_status_real(project_name)
    
    def list_all_environments(self):
        """
        Получить список всех активных окружений (для админки).
        """
        if self.mock_mode:
            return self._mock.list_all_environments()
        else:
            # TODO: Реальная реализация
            return self._list_all_environments_real()
    
    # ========== Заглушки для реального режима (TODO) ==========
    
    def _create_environment_real(self, user_id, challenge_id, config):
        """
        Реальная реализация создания окружения через DVP API.
        Будет дописана, когда появится доступ к кластеру.
        """
        raise NotImplementedError("Real DVP API integration not implemented yet")
    
    def _delete_environment_real(self, project_name):
        """Реальное удаление окружения"""
        raise NotImplementedError("Real DVP API integration not implemented yet")
    
    def _get_environment_status_real(self, project_name):
        """Реальное получение статуса"""
        raise NotImplementedError("Real DVP API integration not implemented yet")
    
    def _list_all_environments_real(self):
        """Реальное получение списка окружений"""
        raise NotImplementedError("Real DVP API integration not implemented yet")


# Глобальный экземпляр клиента
dvp_client = DVPClient()