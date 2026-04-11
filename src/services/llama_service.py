import os
import subprocess
import socket
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Optional

from utils.config_utils import load_config, get_abs_path
from utils.process_utils import kill_proc_tree
from utils.log_utils import add_log, capture_output

router = APIRouter()
config = load_config()

llama_config = config.get("llama", {})
directories = config.get("directories", {})

llama_cwd = get_abs_path(directories.get("dir_llama", "llama.cpp"))
models_dir = get_abs_path(directories.get("local_Models", "_Models"))

llama_exe = os.path.join(llama_cwd, llama_config.get("executable", "llama-server.exe"))

# 管理多个并发进程
class LlamaManager:
    def __init__(self):
        self.processes: Dict[str, dict] = {} # model_name -> { pid, port, p_obj }

    def is_port_in_use(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def get_next_available_port(self, start_port):
        current_port = start_port
        # 同时检查系统端口占用和内部已分配端口
        assigned_ports = [p["port"] for p in self.processes.values()]
        while current_port in assigned_ports or self.is_port_in_use(current_port):
            current_port += 1
        return current_port

manager = LlamaManager()

class StartRequest(BaseModel):
    model: str

@router.get("/models")
def get_models():
    """List available gguf models."""
    if not os.path.exists(models_dir):
        return []
    models = [f for f in os.listdir(models_dir) if f.endswith(".gguf") or f.endswith(".bin")]
    return models

@router.get("/status")
def get_status():
    """返回所有活跃模型的列表"""
    active_list = []
    # 验证进程是否还在运行
    dead_models = []
    for name, info in manager.processes.items():
        if info["p_obj"].poll() is None:
            active_list.append({
                "model": name,
                "port": info["port"],
                "pid": info["pid"]
            })
        else:
            dead_models.append(name)
    
    # 清理已意外退出的模型
    for name in dead_models:
        del manager.processes[name]
        
    return {"status": "success", "running_models": active_list}

@router.post("/start")
def start_model(req: StartRequest):
    if req.model in manager.processes:
        raise HTTPException(status_code=400, detail=f"Model {req.model} is already running")
        
    model_path = os.path.join(models_dir, req.model)
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail="Model file not found")
        
    # 分配新端口
    base_port = llama_config.get("port", 8080)
    port = manager.get_next_available_port(base_port)
    
    ctx_size = str(llama_config.get("ctx_size", 20480))
    host = llama_config.get("host", "127.0.0.1")
    
    cmd = [llama_exe, "-m", model_path, "--host", host, "--port", str(port), "-c", ctx_size]
    
    add_log("llama", f"Starting model {req.model} on port {port}")
    add_log("llama", f"Command: {' '.join(cmd)}")
    
    try:
        p = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            cwd=llama_cwd
        )
        manager.processes[req.model] = {
            "pid": p.pid,
            "port": port,
            "p_obj": p
        }
        
        # 启动日志捕获
        capture_output(f"llama", p)
        
        return {
            "status": "success", 
            "message": f"Started model {req.model}", 
            "port": port,
            "pid": p.pid
        }
    except Exception as e:
        add_log("llama", f"Start failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start model: {str(e)}")

@router.post("/stop")
def stop_model(model: str = Query(...)):
    if model not in manager.processes:
        return {"status": "success", "message": f"Model {model} is not running"}
        
    info = manager.processes[model]
    add_log("llama", f"Stopping model {model} (PID: {info['pid']})")
    
    try:
        kill_proc_tree(info["pid"])
        del manager.processes[model]
        return {"status": "success", "message": f"Model {model} stopped"}
    except Exception as e:
        add_log("llama", f"Stop failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop model: {str(e)}")
