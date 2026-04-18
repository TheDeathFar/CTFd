"""
Эмуляция Deckhouse DVP API для локального тестирования.
Все данные хранятся в памяти и сбрасываются при перезапуске CTFd.
"""

import time
import uuid


class MockDVPClient:
    """
    Эмулирует клиент Deckhouse DVP API.
    Создаёт видимость работы реального кластера.
    """
    
    def __init__(self):
        # Хранилища в памяти
        self._projects = {}       # project_name -> project_data
        self._vms = {}            # project_name -> {vm_name: vm_data}
        self._containers = {}     # project_name -> {container_name: container_data}
        self._services = {}       # project_name -> {service_name: service_data}
        self._ingresses = {}      # project_name -> {ingress_name: ingress_data}
        self._lab_instances = {}  # НОВОЕ: project_name -> lab_instance_data
        
        print("[MOCK] DVP Mock Client initialized")
    
    # ========== Проекты ==========
    
    def create_project(self, name, user_id, challenge_id):
        """Создать проект (аналог Namespace)"""
        project_id = f"project-{uuid.uuid4().hex[:8]}"
        
        self._projects[name] = {
            "id": project_id,
            "name": name,
            "user_id": user_id,
            "challenge_id": challenge_id,
            "created_at": time.time(),
            "status": "Active",
            "phase": "Active"
        }
        
        print(f"[MOCK] ✅ Project created: {name} (user={user_id}, challenge={challenge_id})")
        return {
            "metadata": {
                "name": name,
                "uid": project_id,
                "creationTimestamp": time.time()
            },
            "status": {
                "phase": "Active"
            }
        }
    
    def get_project(self, name):
        """Получить информацию о проекте"""
        return self._projects.get(name)
    
    def get_project_status(self, name):
        """Получить статус проекта"""
        project = self._projects.get(name)
        if project:
            return {"phase": project["status"]}
        return None
    
    def delete_project(self, name):
        """Удалить проект и всё его содержимое"""
        self._projects.pop(name, None)
        self._vms.pop(name, None)
        self._containers.pop(name, None)
        self._services.pop(name, None)
        self._ingresses.pop(name, None)
        print(f"[MOCK] 🗑️ Project deleted: {name}")
        return {"status": "Success", "message": f"Project {name} deleted"}
    
    def list_projects(self):
        """Список всех проектов"""
        return list(self._projects.keys())
    
    # ========== Виртуальные машины ==========
    
    def create_virtual_machine(self, project_name, name, image, cpu, memory):
        """Создать ВМ в проекте"""
        vm_id = f"vm-{uuid.uuid4().hex[:8]}"
        
        if project_name not in self._vms:
            self._vms[project_name] = {}
        
        # Генерируем псевдо-IP
        ip_parts = [
            10,
            244,
            hash(name) % 255,
            hash(project_name) % 255
        ]
        ip_address = ".".join(str(p) for p in ip_parts)
        
        self._vms[project_name][name] = {
            "id": vm_id,
            "name": name,
            "image": image,
            "cpu": cpu,
            "memory": memory,
            "created_at": time.time(),
            "status": "Running",
            "printableStatus": "Running",
            "phase": "Running",
            "ip": ip_address,
            "interfaces": [{"ipAddress": ip_address}]
        }
        
        print(f"[MOCK] 🖥️ VM created: {name} in {project_name} (cpu={cpu}, mem={memory}, ip={ip_address})")
        return {
            "metadata": {
                "name": name,
                "namespace": project_name,
                "uid": vm_id
            },
            "status": {
                "phase": "Running",
                "printableStatus": "Running",
                "interfaces": [{"ipAddress": ip_address}]
            }
        }
    
    def get_vm(self, project_name, vm_name):
        """Получить информацию о ВМ"""
        if project_name in self._vms:
            return self._vms[project_name].get(vm_name)
        return None
    
    def get_vm_status(self, project_name, vm_name):
        """Получить статус ВМ"""
        vm = self.get_vm(project_name, vm_name)
        if vm:
            return {
                "phase": vm["status"],
                "printableStatus": vm["status"],
                "interfaces": [{"ipAddress": vm["ip"]}]
            }
        return None
    
    # ========== Контейнеры (Pods) ==========
    
    def create_container(self, project_name, name, image, ports):
        """Создать контейнер в проекте"""
        container_id = f"pod-{uuid.uuid4().hex[:8]}"
        
        if project_name not in self._containers:
            self._containers[project_name] = {}
        
        ip_parts = [
            10,
            244,
            hash(name) % 255,
            hash(project_name) % 255
        ]
        ip_address = ".".join(str(p) for p in ip_parts)
        
        self._containers[project_name][name] = {
            "id": container_id,
            "name": name,
            "image": image,
            "ports": ports,
            "created_at": time.time(),
            "status": "Running",
            "phase": "Running",
            "ip": ip_address,
            "podIP": ip_address
        }
        
        print(f"[MOCK] 📦 Container created: {name} in {project_name} (image={image}, ports={ports}, ip={ip_address})")
        return {
            "metadata": {
                "name": name,
                "namespace": project_name,
                "uid": container_id
            },
            "status": {
                "phase": "Running",
                "podIP": ip_address
            }
        }
    
    def get_container(self, project_name, container_name):
        """Получить информацию о контейнере"""
        if project_name in self._containers:
            return self._containers[project_name].get(container_name)
        return None
    
    # ========== Сервисы ==========
    
    def create_service(self, project_name, name, port):
        """Создать Service для доступа к окружению"""
        service_id = f"svc-{uuid.uuid4().hex[:8]}"
        
        if project_name not in self._services:
            self._services[project_name] = {}
        
        self._services[project_name][name] = {
            "id": service_id,
            "name": name,
            "port": port,
            "created_at": time.time(),
            "cluster_ip": f"10.96.{hash(name) % 255}.{hash(project_name) % 255}"
        }
        
        print(f"[MOCK] 🔌 Service created: {name} in {project_name} (port={port})")
        return {
            "metadata": {"name": name, "namespace": project_name},
            "spec": {
                "ports": [{"port": port, "targetPort": port}],
                "clusterIP": self._services[project_name][name]["cluster_ip"]
            }
        }
    
    # ========== Ingress ==========
    
    def create_ingress(self, project_name, name, host, service_name, service_port):
        """Создать Ingress для внешнего доступа"""
        ingress_id = f"ing-{uuid.uuid4().hex[:8]}"
        
        if project_name not in self._ingresses:
            self._ingresses[project_name] = {}
        
        self._ingresses[project_name][name] = {
            "id": ingress_id,
            "name": name,
            "host": host,
            "service_name": service_name,
            "service_port": service_port,
            "created_at": time.time(),
            "status": "Active",
            "address": "192.168.1.100"
        }
        
        print(f"[MOCK] 🌐 Ingress created: https://{host} -> {service_name}:{service_port}")
        return {
            "metadata": {"name": name, "namespace": project_name},
            "spec": {
                "rules": [{"host": host}]
            },
            "status": {
                "loadBalancer": {
                    "ingress": [{"ip": self._ingresses[project_name][name]["address"]}]
                }
            }
        }
    
    # ========== Комплексные операции ==========
    
    def create_environment(self, user_id, challenge_id, config):
        """
        Создать полное окружение: проект + ресурсы + доступ.
        """
        project_name = config.get("project_name")
        if not project_name:
            project_name = f"student-{user_id}-challenge-{challenge_id}"
        
        # 1. Проект
        self.create_project(project_name, user_id, challenge_id)
        
        env_type = config.get("environment_type", "container")
        resource_name = f"challenge-{challenge_id}"
        
        # 2. Основной ресурс (ВМ или контейнер)
        if env_type == "virtualmachine":
            self.create_virtual_machine(
                project_name=project_name,
                name=resource_name,
                image=config.get("image", "ubuntu:22.04"),
                cpu=config.get("cpu", 2),
                memory=config.get("memory", "2Gi")
            )
        else:
            ports = config.get("ports", [80])
            if isinstance(ports, str):
                ports = [int(p.strip()) for p in ports.split(",") if p.strip()]
            self.create_container(
                project_name=project_name,
                name=resource_name,
                image=config.get("image", "nginx:alpine"),
                ports=ports
            )
        
        # 3. Service
        service_name = f"{resource_name}-svc"
        self.create_service(project_name, service_name, 80)
        
        # 4. Ingress
        subdomain = config.get("subdomain", f"user-{user_id}-challenge-{challenge_id}.polygon.local")
        self.create_ingress(
            project_name=project_name,
            name=f"{resource_name}-ingress",
            host=subdomain,
            service_name=service_name,
            service_port=80
        )
        
        return {
            "project": project_name,
            "subdomain": subdomain,
            "url": f"https://{subdomain}"
        }
    
    def delete_environment(self, project_name):
        """Удалить окружение целиком"""
        return self.delete_project(project_name)
    
    def get_environment_status(self, project_name):
        """Получить статус окружения"""
        project = self.get_project(project_name)
        if not project:
            return None
        
        status = {
            "project": project_name,
            "project_status": project["status"],
            "resources": []
        }
        
        # ВМ
        if project_name in self._vms:
            for vm_name, vm in self._vms[project_name].items():
                status["resources"].append({
                    "type": "virtualmachine",
                    "name": vm_name,
                    "status": vm["status"],
                    "ip": vm["ip"]
                })
        
        # Контейнеры
        if project_name in self._containers:
            for cont_name, cont in self._containers[project_name].items():
                status["resources"].append({
                    "type": "container",
                    "name": cont_name,
                    "status": cont["status"],
                    "ip": cont["ip"]
                })
        
        return status
    
    def list_all_environments(self):
        """Полный список всех окружений (для админки)"""
        result = []
        for project_name, project in self._projects.items():
            env = {
                "project": project_name,
                "user_id": project.get("user_id"),
                "challenge_id": project.get("challenge_id"),
                "created_at": project.get("created_at"),
                "status": project.get("status"),
                "vms": list(self._vms.get(project_name, {}).keys()),
                "containers": list(self._containers.get(project_name, {}).keys())
            }
            result.append(env)
        return result


# Глобальный экземпляр для использования во всём плагине
_mock_client = MockDVPClient()

  

def get_mock_client():
    """Возвращает глобальный экземпляр Mock-клиента"""
    return _mock_client