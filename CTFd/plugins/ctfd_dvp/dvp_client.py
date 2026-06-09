"""
Клиент для создания ArgoCD Application и проверки окружений.
"""

import json
import os
from flask import current_app


class DVPClient:
    
    def __init__(self, mock_mode=None):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            self.mock_mode = config.get("mock_mode", True)
            self.project_prefix = config.get("project_prefix", "student")
            self.ingress_domain = config.get("ingress_domain", "polygon.local")
            self.default_timeout = config.get("default_timeout", 3600)
            self.argocd_namespace = config.get("argocd_namespace", "argocd")
        except:
            self.mock_mode = True
            self.project_prefix = "student"
            self.ingress_domain = "polygon.local"
            self.default_timeout = 3600
            self.argocd_namespace = "argocd"
        
        if self.mock_mode:
            from .mock_data import get_mock_client
            self._mock = get_mock_client()
            self._k8s = None
            print("[DVP] Running in MOCK MODE - no real cluster required")
        else:
            try:
                from kubernetes import client, config as k8s_config
                k8s_config.load_incluster_config()
                self._k8s = {
                    "core_v1": client.CoreV1Api(),
                    "custom_objects": client.CustomObjectsApi(),
                    "networking_v1": client.NetworkingV1Api(), 
                }
                print("[DVP] Connected to Kubernetes API (ArgoCD mode)")
            except Exception as e:
                print(f"[DVP] Failed to connect to K8s: {e}")
                self._k8s = None
            self._mock = None
    
    def _get_app_name(self, user_id, challenge_id):
        return f"{self.project_prefix}-{user_id}-lab-{challenge_id}"
    
    def create_environment(self, user_id, challenge_id, config):
        app_name = self._get_app_name(user_id, challenge_id)
        
        node_selectors = config.get("node_selectors", [])
        
        values = {
            "project": {"create": True, "name": app_name},
            "ingress": {
                "enabled": True,
                "className": "nginx",
                "hostBase": self.ingress_domain,
                "clusterIssuer": "selfsigned"
            },
            "vm": {
                "namePrefix": "student",
                "nodeSelector": node_selectors
            }
        }
        
        values_yaml = json.dumps(values, indent=2)
        
        application = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": app_name,
                "namespace": self.argocd_namespace,
                "finalizers": ["resources-finalizer.argocd.argoproj.io"]
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": config.get("git_repo_url", ""),
                    "targetRevision": config.get("git_ref", "main"),
                    "path": config.get("chart_path", "."),
                    "helm": {"values": values_yaml}
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default"
                },
                "syncPolicy": {
                    "automated": {"prune": True, "selfHeal": True}
                },
                "ignoreDifferences": [
                    {
                        "group": "virtualization.deckhouse.io",
                        "kind": "VirtualMachine",
                        "jsonPointers": ["/spec/runPolicy"]
                    }
                ]
            }
        }
        
        if self.mock_mode:
            return {"project": app_name, "urls": [f"https://student-0.{app_name}.{self.ingress_domain}"]}
        
        self._k8s["custom_objects"].create_namespaced_custom_object(
            group="argoproj.io", version="v1alpha1",
            namespace=self.argocd_namespace, plural="applications", body=application
        )
        
        return {"project": app_name, "urls": []}
    
    def delete_environment(self, user_id, challenge_id):
        app_name = self._get_app_name(user_id, challenge_id)
        
        if self.mock_mode:
            print(f"[MOCK] Environment deleted: {app_name}")
            return {"status": "deleted"}
        
        # 1. Сначала удалить проект DVP (вместе со всеми ВМ, дисками, сервисами)
        try:
            self._k8s["custom_objects"].delete_namespaced_custom_object(
                group="deckhouse.io",
                version="v1alpha2",
                namespace="default",
                plural="projects",
                name=app_name
            )
            print(f"[DVP] Project deleted: {app_name}")
        except Exception as e:
            print(f"[DVP] Delete Project error: {e}")
        
        # 2. Потом удалить ArgoCD Application (уже пустой)
        try:
            self._k8s["custom_objects"].delete_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=self.argocd_namespace,
                plural="applications",
                name=app_name
            )
            print(f"[DVP] Application deleted: {app_name}")
        except Exception as e:
            print(f"[DVP] Delete Application error: {e}")
        
        return {"status": "deleted"}
    
    def get_environment_status(self, user_id, challenge_id):
        app_name = self._get_app_name(user_id, challenge_id)
        
        if self.mock_mode:
            return {"sync": "Synced", "health": "Healthy"}
        else:
            try:
                app = self._k8s["custom_objects"].get_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=self.argocd_namespace,
                    plural="applications",
                    name=app_name
                )
                status = app.get("status", {})
                return {
                    "sync": status.get("sync", {}).get("status", "Unknown"),
                    "health": status.get("health", {}).get("status", "Unknown")
                }
            except Exception:
                return {"sync": "Unknown", "health": "Unknown"}

    def pause_vms(self, namespace):
        """Приостанавливает все ВМ в namespace."""
        try:
            vms = self._k8s["custom_objects"].list_namespaced_custom_object(
                group="virtualization.deckhouse.io",
                version="v1alpha2",
                namespace=namespace,
                plural="virtualmachines"
            )
            for vm in vms.get("items", []):
                vm_name = vm["metadata"]["name"]
                self._k8s["custom_objects"].patch_namespaced_custom_object(
                    group="virtualization.deckhouse.io",
                    version="v1alpha2",
                    namespace=namespace,
                    plural="virtualmachines",
                    name=vm_name,
                    body={"spec": {"runPolicy": "AlwaysOff"}}
                )
            return True
        except Exception as e:
            print(f"[DVP] Failed to pause VMs: {e}")
            return False


    def resume_vms(self, namespace):
        """Возобновляет все ВМ в namespace."""
        try:
            vms = self._k8s["custom_objects"].list_namespaced_custom_object(
                group="virtualization.deckhouse.io",
                version="v1alpha2",
                namespace=namespace,
                plural="virtualmachines"
            )
            for vm in vms.get("items", []):
                vm_name = vm["metadata"]["name"]
                self._k8s["custom_objects"].patch_namespaced_custom_object(
                    group="virtualization.deckhouse.io",
                    version="v1alpha2",
                    namespace=namespace,
                    plural="virtualmachines",
                    name=vm_name,
                    body={"spec": {"runPolicy": "AlwaysOn"}}
                )
            return True
        except Exception as e:
            print(f"[DVP] Failed to resume VMs: {e}")
            return False
        
    def execute_check_script(self, user_id, challenge_id, script):
        if self.mock_mode:
            return {"success": True, "output": "Mock check passed"}

        import uuid
        import time

        app_name = self._get_app_name(user_id, challenge_id)
        namespace = app_name
        pod_name = f"check-{app_name}-{str(uuid.uuid4())[:8]}"

        # 1. Получаем IP-адреса ВСЕХ ВМ
        vm_ips = []
        try:
            vms = self._k8s["custom_objects"].list_namespaced_custom_object(
                group="virtualization.deckhouse.io",
                version="v1alpha2",
                namespace=namespace,
                plural="virtualmachines"
            )
            for vm in (vms.get("items") or []):
                ip = vm.get("status", {}).get("ipAddress")
                if ip:
                    vm_ips.append(ip)
        except Exception as e:
            return {"success": False, "output": f"Failed to get VM IPs: {e}"}

        if not vm_ips:
            return {"success": False, "output": "No VMs found"}

        # 2. Формируем переменные окружения VM0_IP, VM1_IP, ...
        env_vars = []
        for i, ip in enumerate(vm_ips):
            env_vars.append({"name": f"VM{i}_IP", "value": ip})

        # 3. Копируем SSH-секрет в Namespace студента
        try:
            self._k8s["core_v1"].read_namespaced_secret("checker-ssh-key", namespace)
        except:
            try:
                original = self._k8s["core_v1"].read_namespaced_secret("checker-ssh-key", "ctfd")
                secret = {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {"name": "checker-ssh-key", "namespace": namespace},
                    "data": original.data,
                    "type": original.type
                }
                self._k8s["core_v1"].create_namespaced_secret(namespace, secret)
            except Exception as e:
                print(f"Failed to copy SSH secret: {e}")

        # 4. Создаём под-проверщик с SSH
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": pod_name, "namespace": namespace},
            "spec": {
                "restartPolicy": "Never",
                "volumes": [{
                    "name": "ssh-key",
                    "secret": {
                        "secretName": "checker-ssh-key",
                        "defaultMode": 0o600
                    }
                }],
                "containers": [{
                    "name": "checker",
                    "image": "alpine:latest",
                    "command": ["/bin/sh", "-c"],
                    "args": [
                        f"apk add --no-cache openssh-client > /dev/null 2>&1; {script}"
                    ],
                    "env": env_vars,
                    "resources": {
                        "limits": {"cpu": "500m", "memory": "256Mi"},
                        "requests": {"cpu": "100m", "memory": "128Mi"}
                    },
                    "volumeMounts": [{
                        "name": "ssh-key",
                        "mountPath": "/ssh-key",
                        "readOnly": True
                    }]
                }]
            }
        }

        try:
            self._k8s["core_v1"].create_namespaced_pod(namespace, pod_manifest)

            # 5. Ждём завершения
            for _ in range(15):
                time.sleep(2)
                pod_status = self._k8s["core_v1"].read_namespaced_pod_status(pod_name, namespace)
                if pod_status.status.phase in ["Succeeded", "Failed"]:
                    break

            # 6. Получаем логи
            logs = self._k8s["core_v1"].read_namespaced_pod_log(pod_name, namespace)
            success = "SUCCESS" in logs
            return {"success": success, "output": logs}

        except Exception as e:
            return {"success": False, "output": str(e)}
        finally:
            try:
                self._k8s["core_v1"].delete_namespaced_pod(pod_name, namespace)
            except:
                pass


dvp_client = DVPClient()