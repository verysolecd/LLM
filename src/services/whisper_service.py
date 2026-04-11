import os
import subprocess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.config_utils import load_config, get_abs_path
from utils.process_utils import kill_proc_tree
from utils.log_utils import add_log, capture_output

router = APIRouter()
config = load_config()

whisper_config = config.get("whisper", {})
tts_config = config.get("tts", {})
directories = config.get("directories", {})

whisper_cwd = get_abs_path(directories.get("dir_whisper", "whisper.cpp"))
models_dir = get_abs_path(directories.get("local_Models", "_Models"))

class WhisperManager:
    def __init__(self):
        self.processes = {} # tool_name -> {pid, port}

    def is_running(self, name):
        return name in self.processes

    def get_status(self):
        tools = whisper_config.get("tools", [])
        return {
            "tools": [{"name": t["name"], "running": t["name"] in self.processes} for t in tools],
            "running_count": len(self.processes)
        }

manager = WhisperManager()

class ToolStartRequest(BaseModel):
    tool_name: str
    model: str = ""

@router.get("/models")
def get_whisper_models():
    """List available whisper bin models."""
    if not os.path.exists(models_dir):
        return []
    models = [f for f in os.listdir(models_dir) if f.startswith("ggml") and f.endswith(".bin")]
    return models

@router.get("/tools")
def get_tools_status():
    return manager.get_status()

@router.post("/tool/start")
def start_tool(req: ToolStartRequest):
    if manager.is_running(req.tool_name):
        raise HTTPException(status_code=400, detail=f"Tool {req.tool_name} is already running")
        
    tools = whisper_config.get("tools", [])
    target_tool = next((t for t in tools if t["name"] == req.tool_name), None)
    
    if not target_tool:
        raise HTTPException(status_code=404, detail="Tool not found in config")
        
    exe_path = os.path.join(whisper_cwd, target_tool["exe"])
    cmd = [exe_path]
    
    if req.model:
        model_path = os.path.join(models_dir, req.model)
        if os.path.exists(model_path):
            cmd.extend(["-m", model_path])
            
    port = str(target_tool.get("port", 8081))
    if req.tool_name == "whisper-server":
        host = whisper_config.get("host", "127.0.0.1")
        cmd.extend(["--host", host, "--port", port])
    
    # whisper-command may have its own params, keep it generic
    add_log("whisper", f"Starting tool: {req.tool_name} (Port: {port})")
        
    try:
        p = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            cwd=whisper_cwd
        )
        manager.processes[req.tool_name] = {"pid": p.pid, "port": port}
        
        # Monitor this process
        capture_output("whisper", p)
        
        return {"status": "success", "message": f"Started {req.tool_name}", "pid": p.pid}
    except Exception as e:
        add_log("whisper", f"Failed to start {req.tool_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start tool: {str(e)}")

@router.post("/tool/stop")
def stop_tool(tool_name: str):
    if not manager.is_running(tool_name):
        return {"status": "success", "message": f"{tool_name} is not running"}
        
    proc_info = manager.processes[tool_name]
    add_log("whisper", f"Stopping tool: {tool_name} (PID: {proc_info['pid']})")
    
    try:
        kill_proc_tree(proc_info['pid'])
        del manager.processes[tool_name]
        return {"status": "success", "message": f"{tool_name} stopped"}
    except Exception as e:
        add_log("whisper", f"Error stopping {tool_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop: {str(e)}")

class RecognizeRequest(BaseModel):
    audio_path: str
    model: str

@router.post("/recognize")
async def recognize_audio(req: RecognizeRequest):
    """One-shot recognition using whisper-cli.exe strictly."""
    # 强制物理路径锚定
    # 动态获取可执行文件名 (从 TTS 配置中获取，作为其采集辅助工具)
    cli_exe = tts_config.get("whisper_cli_executable", "whisper-cli.exe")
    exe_path = os.path.join(whisper_cwd, cli_exe)
    
    if not os.path.exists(exe_path):
        # 尝试回退
        alt_exe = "main.exe" if cli_exe != "main.exe" else "whisper-cli.exe"
        exe_path = os.path.join(whisper_cwd, alt_exe)
        if os.path.exists(exe_path):
            add_log("whisper", f"Primary CLI {cli_exe} not found, falling back to {alt_exe}")
        else:
            raise HTTPException(status_code=500, detail=f"Whisper CLI not found in {whisper_cwd}")

    # 模型选择逻辑：优先使用来自请求或 TTS 配置的默认模型
    model_name = req.model if req.model else tts_config.get("whisper_default_model", "whisper_large.bin")
    model_path = os.path.join(models_dir, model_name)
    
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail=f"Model file not found: {model_path}")

    # 1. 构建并执行命令：whisper-cli.exe -m <model> -f <audio> -nt (No Timestamps) -np (No Prints)
    # -l zh: 强制锁定中文，防止语言漂移
    # --prompt: 注入提示词，强力引导模型输出简体中文
    cmd = [
        exe_path, 
        "-m", model_path, 
        "-f", req.audio_path, 
        "-nt", "-np", 
        "-l", "zh", 
        "--prompt", "以下是普通话的录音，项请用简体中文输出。"
    ]
    
    add_log("whisper", f"Executing ISOLATED smart recognition (Zh-Simplified): {exe_path}")
    
    try:
        # 使用 subprocess.run 确保进程在完成后立即关闭并释放资源
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=whisper_cwd,
            timeout=120
        )
        
        if result.returncode != 0:
            err_msg = result.stderr if result.stderr else "Unknown error from whisper-cli"
            add_log("whisper", f"Recognition process failed/terminated: {err_msg}")
            raise HTTPException(status_code=500, detail=err_msg)
            
        transcribed_text = result.stdout.strip()
        add_log("whisper", f"Transcription complete. Result length: {len(transcribed_text)}")
        return {"text": transcribed_text}
        
    except subprocess.TimeoutExpired:
        add_log("whisper", "Recognition TIMEOUT - Process forcibly terminated")
        raise HTTPException(status_code=500, detail="Recognition task timed out")
    except Exception as e:
        add_log("whisper", f"Critical error during recognition: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
