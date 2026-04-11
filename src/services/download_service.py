import os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from modelscope.hub.snapshot_download import snapshot_download

from utils.config_utils import load_config
from utils.log_utils import add_log

router = APIRouter()
config = load_config()

directories = config.get("directories", {})
models_dir = directories.get("local_Models", "../_Models")
if not os.path.isabs(models_dir):
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", models_dir))

class DownloadState:
    active_downloads = {}

state = DownloadState()

class DownloadRequest(BaseModel):
    model_id: str
    file_id: str = None

def download_task(task_id: str, model_id: str, file_id: str):
    state.active_downloads[task_id] = {"status": "downloading", "model": model_id, "file": file_id}
    add_log("download", f"Starting download task for model: {model_id}")
    try:
        save_path = os.path.join(models_dir, model_id.split('/')[-1])
        if file_id:
            # If download specific file. modelscope API requires handling. Simple snapshot for now.
            snapshot_download(model_id, local_dir=save_path)
        else:
            snapshot_download(model_id, local_dir=save_path)
        state.active_downloads[task_id]["status"] = "completed"
        add_log("download", f"Successfully downloaded {model_id} to {save_path}")
    except Exception as e:
        state.active_downloads[task_id]["status"] = f"failed: {str(e)}"
        add_log("download", f"Download failed for {model_id}: {str(e)}")

@router.post("/model")
def start_download(req: DownloadRequest, bg_tasks: BackgroundTasks):
    task_id = f"{req.model_id}-{req.file_id or 'all'}"
    if task_id in state.active_downloads and state.active_downloads[task_id]["status"] == "downloading":
        return {"status": "already_downloading", "task_id": task_id}
        
    add_log("download", f"Queuing download request: {req.model_id}")
    bg_tasks.add_task(download_task, task_id, req.model_id, req.file_id)
    return {"status": "started", "task_id": task_id}

@router.get("/status")
def get_download_status():
    return state.active_downloads
