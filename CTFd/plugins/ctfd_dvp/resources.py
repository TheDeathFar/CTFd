"""
Ресурсы кластера, парсинг чарта, алгоритм FFD.
"""

import yaml
import requests
import time


_cache_nodes = None
_cache_time = 0

MIN_FREE_CPU = 0.5
MIN_FREE_RAM = 1.0
MIN_FREE_DISK = 2.0


def get_nodes_resources(k8s_client):
    global _cache_nodes, _cache_time
    
    now = time.time()
    if _cache_nodes is not None and now - _cache_time < 10:
        return _cache_nodes
    
    core_v1 = k8s_client["core_v1"]
    custom_api = k8s_client["custom_objects"]
    
    node_disk = {}
    try:
        vgs = custom_api.list_cluster_custom_object(
            group="storage.deckhouse.io", version="v1alpha1", plural="lvmvolumegroups"
        )
        for vg in vgs.get("items", []):
            node_name = vg.get("spec", {}).get("nodeName", vg.get("spec", {}).get("local", {}).get("nodeName", ""))
            status = vg.get("status", {})
            size_mb = _parse_disk_size(status.get("vgSize", "0"))
            alloc_mb = _parse_disk_size(status.get("allocatedSize", "0"))
            if node_name:
                node_disk[node_name] = (size_mb - alloc_mb) / 1024
    except:
        pass
    
    nodes = []
    
    for node in core_v1.list_node().items:
        name = node.metadata.name
        
        if "node-role.kubernetes.io/control-plane" in node.metadata.labels:
            continue
        
        ready = any(c.type == "Ready" and c.status == "True" for c in node.status.conditions)
        if not ready:
            continue
        
        free_disk = node_disk.get(name)
        if free_disk is None:
            continue
        
        alloc = node.status.allocatable
        alloc_cpu = _parse_cpu(alloc.get("cpu", "0"))
        alloc_mem = _parse_mem_gb(alloc.get("memory", "0Ki"))
        
        req_cpu = 0.0
        req_mem = 0.0
        
        pods = core_v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={name}").items
        for pod in pods:
            if pod.status.phase not in ["Running", "Pending"]:
                continue
            for c in pod.spec.containers:
                if c.resources and c.resources.requests:
                    req_cpu += _parse_cpu(c.resources.requests.get("cpu", "0"))
                    req_mem += _parse_mem_gb(c.resources.requests.get("memory", "0Mi"))
        
        free_cpu = alloc_cpu - req_cpu
        free_mem = alloc_mem - req_mem
        
        nodes.append({"name": name, "cpu": free_cpu, "ram_gb": free_mem, "disk_gb": free_disk})
    
    _cache_nodes = nodes
    _cache_time = now
    return nodes


def get_chart_resources(git_repo_url, git_ref="main", chart_path="."):
    raw = git_repo_url.replace("github.com", "raw.githubusercontent.com").rstrip("/")
    url = f"{raw}/{git_ref}/{chart_path}/values.yaml"
    
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    v = yaml.safe_load(r.text)
    
    disk_per_vm = _parse_disk(v["disk"].get("size", "4Gi"))
    
    return {
        "vm_count": v.get("replicaCount", 1),
        "cpu_per_vm": v["vm"].get("cpu", 1),
        "ram_per_vm": _parse_ram(v["vm"].get("memory", "2Gi")),
        "disk_per_vm": disk_per_vm,
        "scratch_gb": disk_per_vm
    }


def get_limits_for_strategy(strategy, cpu_per_vm, ram_per_vm, disk_per_vm):
    if strategy == "regular":
        return cpu_per_vm, ram_per_vm, disk_per_vm, MIN_FREE_CPU, MIN_FREE_RAM, MIN_FREE_DISK
    elif strategy == "competition":
        return cpu_per_vm, ram_per_vm, disk_per_vm, MIN_FREE_CPU, MIN_FREE_RAM, MIN_FREE_DISK
    elif strategy == "selfstudy":
        return cpu_per_vm * 0.6, ram_per_vm * 0.6, disk_per_vm, MIN_FREE_CPU, MIN_FREE_RAM, MIN_FREE_DISK
    return cpu_per_vm, ram_per_vm, disk_per_vm, MIN_FREE_CPU, MIN_FREE_RAM, MIN_FREE_DISK


def suspend_lower_priority(strategy, needed_cpu, needed_ram, needed_disk, k8s_client):
    """
    Приостанавливает низкоприоритетные окружения по одному,
    пока не освободится достаточно ресурсов.
    Competition > Regular > SelfStudy
    """
    priority = {"competition": 3, "regular": 2, "selfstudy": 1}
    
    from .models import DVPEnvironment, DVPChallengeModel
    from .dvp_client import dvp_client
    
    active_envs = DVPEnvironment.query.filter_by(status="active").order_by(DVPEnvironment.created_at.asc()).all()
    suspended = []
    
    for env in active_envs:
        challenge = DVPChallengeModel.query.get(env.challenge_id)
        if not challenge:
            continue
        
        env_priority = priority.get(challenge.strategy, 1)
        
        if env_priority >= priority[strategy]:
            continue
        
        dvp_client.pause_vms(env.project_name)
        env.status = "suspended"
        suspended.append(env.project_name)
        
        from CTFd.models import db
        db.session.commit()
        
        global _cache_time
        _cache_time = 0
        
        ok, _ = can_launch(needed_cpu, needed_ram, needed_disk, 1, k8s_client, 0)
        if ok:
            break
    
    return suspended


def ffd_place_vms(cpu_per_vm, ram_per_vm, disk_per_vm, vm_count, k8s_client):
    nodes = get_nodes_resources(k8s_client)
    nodes.sort(key=lambda n: n["disk_gb"], reverse=True)
    
    node_names = []
    for _ in range(vm_count):
        placed = False
        for node in nodes:
            if (node["cpu"] - cpu_per_vm >= MIN_FREE_CPU and 
                node["ram_gb"] - ram_per_vm >= MIN_FREE_RAM and 
                node["disk_gb"] - disk_per_vm >= MIN_FREE_DISK):
                
                node["cpu"] -= cpu_per_vm
                node["ram_gb"] -= ram_per_vm
                node["disk_gb"] -= disk_per_vm
                node_names.append(node["name"])
                placed = True
                break
        if not placed:
            return None
    
    return node_names


def can_launch(cpu_per_vm, ram_per_vm, disk_per_vm, vm_count, k8s_client, scratch_gb):
    disk_total = disk_per_vm + scratch_gb
    node_names = ffd_place_vms(cpu_per_vm, ram_per_vm, disk_total, vm_count, k8s_client)
    
    if node_names:
        return True, node_names
    
    return False, "Недостаточно ресурсов. Попробуйте позже."


def _parse_cpu(s):
    if not s: return 0.0
    s = str(s)
    return int(s[:-1]) / 1000 if s.endswith("m") else float(s)

def _parse_mem_gb(s):
    if not s: return 0.0
    s = str(s).strip()
    if s.endswith("Ki"): return int(s[:-2]) / (1024*1024)
    if s.endswith("Mi"): return int(s[:-2]) / 1024
    if s.endswith("Gi"): return float(s[:-2])
    if s.endswith("Ti"): return float(s[:-2]) * 1024
    return float(s) / (1024*1024*1024)

def _parse_ram(s):
    if not s: return 2
    s = str(s).strip()
    if s.endswith("Gi"): return int(s[:-2])
    if s.endswith("Mi"): return int(s[:-2]) / 1024
    return int(s)

def _parse_disk(s):
    if not s: return 4
    s = str(s).strip()
    if s.endswith("Gi"): return int(s[:-2])
    if s.endswith("Mi"): return int(s[:-2]) / 1024
    return int(s)

def _parse_disk_size(s):
    if not s: return 0
    s = str(s).strip()
    if s.endswith("Mi"): return int(s[:-2])
    elif s.endswith("Gi"): return int(s[:-2]) * 1024
    elif s.endswith("Ti"): return int(s[:-2]) * 1024 * 1024
    return int(s)