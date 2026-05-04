"""
CTFd-DVP Plugin
"""

from flask import Blueprint, redirect
from CTFd.plugins import (
    register_plugin_assets_directory,
    register_admin_plugin_menu_bar,
)
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from CTFd.plugins.migrations import upgrade
from CTFd.utils.decorators import admins_only


def load(app):
    plugin_name = "ctfd_dvp"
    
    # 1. Применяем миграции
    try:
        upgrade(plugin_name=plugin_name)
    except Exception as e:
        print(f"[CTFd-DVP] Migration error (may be normal): {e}")
    
    # 2. Импортируем класс челленджа
    from .challenge_type import DVPChallenge
    
    # 3. Регистрируем assets через CTFd (как в Whale)
    register_plugin_assets_directory(
        app,
        base_path=f"/plugins/{plugin_name}/assets",
        endpoint=f"plugins.{plugin_name}.assets"
    )
    
    # 4. ЯВНО присваиваем templates и scripts классу
    DVPChallenge.templates = {
        "create": f"/plugins/{plugin_name}/assets/create.html",
        "update": f"/plugins/{plugin_name}/assets/update.html",
        "view": f"/plugins/{plugin_name}/assets/view.html",
    }
    DVPChallenge.scripts = {
        "create": f"/plugins/{plugin_name}/assets/create.js",
        "update": f"/plugins/{plugin_name}/assets/update.js",
        "view": f"/plugins/{plugin_name}/assets/view.js",
    }
    
    # 5. Регистрируем тип челленджа
    CHALLENGE_CLASSES["dvp_dynamic"] = DVPChallenge
    
    # 6. Создаём Blueprint для админ-панели
    admin_bp = Blueprint(
        "ctfd_dvp_admin",
        __name__,
        template_folder="templates",
        static_folder="assets",
        url_prefix=f"/plugins/{plugin_name}"
    )
    
    # 7. Редирект с /dvp на админ-панель (на уровне всего приложения)
    @app.route("/dvp")
    @admins_only
    def dvp_redirect():
        return redirect(f"/plugins/{plugin_name}/admin/environments")
    
    # 8. Регистрируем пункт в меню админки
    register_admin_plugin_menu_bar(
        title="DVP",
        route=f"/plugins/{plugin_name}/admin/environments"
    )
    
    # 9. Загружаем API
    from .api import load_routes
    load_routes(app)
    
    # 10. Загружаем админ-панель
    from .admin import load_admin_routes
    load_admin_routes(admin_bp)
    
    # 11. Регистрируем Blueprint
    app.register_blueprint(admin_bp)
    
    # 12. Выводим статус
    from .dvp_client import dvp_client
    mode = "MOCK (эмуляция)" if dvp_client.mock_mode else "REAL"
    print(f"[CTFd-DVP] Plugin loaded successfully! Mode: {mode}")