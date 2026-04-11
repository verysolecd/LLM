import os
import sys
import subprocess
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 将项目入口所在目录的 src 子目录添加到 Python 搜索路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "src"))

from utils.config_utils import load_config, get_abs_path
from services.llama_service import router as llama_router
from services.whisper_service import router as whisper_router
from services.download_service import router as download_router
from services.tts_service import router as tts_router
from utils.log_utils import get_service_logs

frontend_process = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global frontend_process
    # 前端代码现在位于 src/web-ui
    frontend_dir = os.path.join(BASE_DIR, "src", "web-ui")
    
    # 强制端口 8000 并绑定 127.0.0.1 以确保访问成功
    cmd = ["npm.cmd", "run", "dev", "--", "--port", "8000", "--host", "127.0.0.1"] if os.name == 'nt' else ["npm", "run", "dev", "--", "--port", "8000", "--host", "127.0.0.1"]
    
    print(f"[*] Starting Vue 3 dev server at {frontend_dir} on port 8000...")
    try:
        frontend_process = subprocess.Popen(
            cmd,
            cwd=frontend_dir
        )
        
        def open_browser():
            # Dev server 启动较慢，等待几秒
            time.sleep(5)
            print("[*] Opening browser to http://127.0.0.1:8000 ...")
            webbrowser.open("http://127.0.0.1:8000")
            
        threading.Thread(target=open_browser, daemon=True).start()
    except Exception as e:
        print(f"[*] Failed to start frontend dev server: {e}")
        
    yield
    
    if frontend_process:
        print("[*] Stopping frontend dev server...")
        if os.name == 'nt':
            # Windows 下暴力清理进程树
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(frontend_process.pid)], capture_output=True)
        else:
            frontend_process.terminate()

app = FastAPI(title="Local LLM Manager API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()

# Serve generated audio files
results_rel_path = config.get("directories", {}).get("tts_results", "tts_results/results")
RESULTS_PATH = get_abs_path(results_rel_path)
os.makedirs(RESULTS_PATH, exist_ok=True)
app.mount("/temp_audio", StaticFiles(directory=RESULTS_PATH), name="temp_audio")

# Mount temporary uploads/recordings
temp_rel_path = config.get("directories", {}).get("tts_temp", "tts_results/temp")
TEMP_PATH = get_abs_path(temp_rel_path)
os.makedirs(TEMP_PATH, exist_ok=True)
app.mount("/temp_upload", StaticFiles(directory=TEMP_PATH), name="temp_upload")

app.include_router(llama_router, prefix="/api/v1")
app.include_router(whisper_router, prefix="/api/v1/whisper")
app.include_router(download_router, prefix="/api/v1/download")
app.include_router(tts_router, prefix="/api/v1/tts")

@app.get("/api/v1/logs/{service}")
def get_logs(service: str):
    return {"logs": get_service_logs(service)}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Local LLM Manager API is running"}

if __name__ == "__main__":
    import uvicorn
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 5001)
    uvicorn.run("app:app", host=host, port=port, reload=True)
