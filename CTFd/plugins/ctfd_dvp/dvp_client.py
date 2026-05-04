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
        
        values = {
            "project": {"create": True, "name": app_name},
            "ingress": {
                "enabled": True,
                "className": "nginx",
                "hostBase": self.ingress_domain,
                "clusterIssuer": "selfsigned"
            },
            "vm": {"namePrefix": "student"}
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
                }
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
    
    def execute_check_script(self, user_id, challenge_id, script):
        if self.mock_mode:
            print(f"[MOCK] Check script executed for {user_id}/{challenge_id}")
            return {"success": True, "output": "Mock check passed"}
        
        app_name = self._get_app_name(user_id, challenge_id)
        namespace = app_name
        
        pods = self._k8s["core_v1"].list_namespaced_pod(
            namespace=namespace,
            label_selector="vm.kubevirt.io/name"
        )
        
        if not pods.items:
            return {"success": False, "output": "Pod not found"}
        
        pod_name = pods.items[0].metadata.name
        
        from kubernetes.stream import stream
        
        try:
            resp = stream(
                self._k8s["core_v1"].connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                command=["/bin/bash", "-c", script],
                stderr=True, stdin=False,
                stdout=True, tty=False
            )
            
            output = resp.strip() if resp else ""
            success = "SUCCESS" in output
            return {"success": success, "output": output}
        except Exception as e:
            return {"success": False, "output": str(e)}
    
    def list_all_environments(self):
        if self.mock_mode:
            return self._mock.list_all_environments()
        else:
            try:
                apps = self._k8s["custom_objects"].list_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=self.argocd_namespace,
                    plural="applications"
                )
                return apps.get("items", [])
            except Exception:
                return []


dvp_client = DVPClient()