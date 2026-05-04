"""
Эмуляция ArgoCD + DVP API для локального тестирования.
Все данные хранятся в памяти и сбрасываются при перезапуске CTFd.
"""

import time
import uuid


class MockDVPClient:
    """
    Эмулирует создание ArgoCD Application и проверку окружений.
    """
    
    def __init__(self):
        self._applications = {}   # app_name -> app_data
        self._environments = {}   # project_name -> env_data
        
        print("[MOCK] DVP Mock Client initialized (ArgoCD mode)")
    
    # ========== Управление окружением ==========
    
    def create_environment(self, user_id, challenge_id, config):
        """
        Эмулирует создание ArgoCD Application.
        """
        app_name = f"student-{user_id}-lab-{challenge_id}"
        
        self._applications[app_name] = {
            "name": app_name,
            "user_id": user_id,
            "challenge_id": challenge_id,
            "git_repo_url": config.get("git_repo_url", ""),
            "created_at": time.time(),
            "sync_status": "Synced",
            "health_status": "Healthy"
        }
        
        self._environments[app_name] = {
            "project": app_name,
            "status": "running",
            "check_status": "pending"
        }
        
        print(f"[MOCK] ✅ ArgoCD Application created: {app_name}")
        return {
            "project": app_name,
            "subdomain": f"{app_name}.polygon.local",
            "url": f"https://{app_name}.polygon.local"
        }
    
    def delete_environment(self, user_id, challenge_id):
        """
        Эмулирует удаление ArgoCD Application.
        """
        app_name = f"student-{user_id}-lab-{challenge_id}"
        self._applications.pop(app_name, None)
        self._environments.pop(app_name, None)
        print(f"[MOCK] 🗑️ ArgoCD Application deleted: {app_name}")
        return {"status": "deleted"}
    
    def get_environment_status(self, user_id, challenge_id):
        """
        Эмулирует получение статуса Application.
        """
        app_name = f"student-{user_id}-lab-{challenge_id}"
        app = self._applications.get(app_name)
        if app:
            return {
                "sync": app["sync_status"],
                "health": app["health_status"]
            }
        return {"sync": "Unknown", "health": "Unknown"}
    
    # ========== Проверка задания ==========
    
    def execute_check_script(self, user_id, challenge_id, script):
        """
        Эмулирует выполнение скрипта проверки.
        """
        app_name = f"student-{user_id}-lab-{challenge_id}"
        
        if app_name in self._environments:
            self._environments[app_name]["check_status"] = "success"
        
        print(f"[MOCK] ✅ Check script executed for {user_id}/{challenge_id}")
        return {"success": True, "output": "Mock check passed"}
    
    # ========== Администрирование ==========
    
    def list_all_environments(self):
        """
        Список всех эмулированных окружений.
        """
        result = []
        for app_name, app in self._applications.items():
            result.append({
                "name": app_name,
                "user_id": app["user_id"],
                "challenge_id": app["challenge_id"],
                "sync": app["sync_status"],
                "health": app["health_status"]
            })
        return result


# Глобальный экземпляр для использования во всём плагине
_mock_client = MockDVPClient()


def get_mock_client():
    """Возвращает глобальный экземпляр Mock-клиента"""
    return _mock_client