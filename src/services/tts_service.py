import os
import json
import shutil
from fastapi import APIRouter, HTTPException, BackgroundTasks, File, UploadFile
from pydantic import BaseModel
from typing import List, Optional
import subprocess
from services.tts_engine import tts_engine
from utils.config_utils import load_config, get_abs_path, add_tts_model
from utils.log_utils import add_log

config = load_config()
dirs_cfg = config.get("directories", {})

# 确保 TTS 结果、音源存储根目录及临时录音目录存在 (统一使用 get_abs_path)
RESULTS_DIR = get_abs_path(dirs_cfg.get("tts_results", "tts_results/results"))
VOICES_ROOT_DIR = get_abs_path(dirs_cfg.get("tts_voices", "tts_results/Voices"))
TEMP_DIR = get_abs_path(dirs_cfg.get("tts_temp", "tts_results/temp"))

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(VOICES_ROOT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    model_id: str
    voice: Optional[str] = "Vivian" # 对于 QwenTTS 来说是 speaker
    language: Optional[str] = "Auto"
    instruct: Optional[str] = ""
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = ""

@router.get("/models")
async def get_models():
    try:
        return tts_engine.get_available_models()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/discover")
async def discover_new_models():
    """扫描并返回新发现的模型"""
    try:
        configured, new_models = tts_engine.scan_tts_models_directory()
        return {
            "configured": configured,
            "new_models": new_models,
            "has_new": len(new_models) > 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/add")
async def add_new_model(model_dir: str):
    """
    将新发现的模型添加到 config.json
    
    Args:
        model_dir: 模型目录名称（如 Qwen3-TTS-0.6B）
    """
    try:
        # 扫描新模型
        configured, new_models = tts_engine.scan_tts_models_directory()
        
        # 查找指定的模型
        target_model = None
        for model in new_models:
            if model["dir_name"] == model_dir:
                target_model = model
                break
        
        if not target_model:
            raise HTTPException(status_code=404, detail=f"未找到模型：{model_dir}")
        
        # 生成模型 ID（使用目录名的小写版本）
        model_id = model_dir.lower().replace("_", "-")
        
        # 添加到 config.json
        success = add_tts_model(
            model_id=model_id,
            model_path=model_dir,
            voices_dir="tts_results/voice_qwen3"
        )
        
        if success:
            add_log("tts", f"Added new model to config: {model_id} ({model_dir})")
            return {
                "status": "success",
                "message": f"已添加模型 {model_id} 到 config.json",
                "model_id": model_id,
                "model_dir": model_dir
            }
        else:
            raise HTTPException(status_code=500, detail="保存配置失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status(model_id: str = "faster-qwen3-tts"):
    return {
        "model_id": model_id,
        "loaded": tts_engine.is_model_loaded(model_id)
    }

@router.post("/start")
async def start_service(model_id: str = "faster-qwen3-tts"):
    try:
        tts_engine.load_model(model_id)
        add_log("tts", f"Service started: {model_id} loaded into memory")
        return {"status": "success", "loaded": True}
    except Exception as e:
        add_log("tts", f"Failed to start service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_service(model_id: str = "faster-qwen3-tts"):
    try:
        success = tts_engine.unload_model(model_id)
        if success:
            add_log("tts", f"Service stopped: {model_id} unloaded from memory")
        return {"status": "success", "loaded": False}
    except Exception as e:
        add_log("tts", f"Failed to stop service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/voices")
async def get_voices():
    try:
        return tts_engine.get_voice_library()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-ref")
async def upload_ref(file: UploadFile = File(...)):
    """上传参考音频 (存放到 tts_results/temp)"""
    try:
        # 确保目录存在
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        raw_path = os.path.join(TEMP_DIR, f"raw_{file.filename}")
        final_path = os.path.join(TEMP_DIR, f"recorded_{file.filename}")
        
        # 1. 保存原始上传文件
        with open(raw_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        # 2. 标准化归一：强制转换为 16kHz, 单声道 WAV (Whisper & TTS 通用标准)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", raw_path, "-ar", "16000", "-ac", "1", final_path],
                capture_output=True,
                check=True
            )
            if os.path.exists(raw_path):
                os.remove(raw_path)
        except Exception as fe:
            add_log("tts", f"Standardization failed, using raw: {str(fe)}")
            os.rename(raw_path, final_path)
    
        # 返回绝对路径供后端加载，同时返回 URL 供前端播放
        return {
            "status": "success",
            "path": os.path.abspath(final_path),
            "url": f"/temp_upload/recorded_{file.filename}"
        }
    except Exception as e:
        add_log("tts", f"Upload failure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class SaveVoiceRequest(BaseModel):
    name: str
    source_path: str
    ref_text: Optional[str] = ""
    model_id: Optional[str] = "faster-qwen3-tts"

@router.post("/save-voice")
async def save_voice(request: SaveVoiceRequest):
    try:
        add_log("tts", f"Saving custom voice: {request.name} for model {request.model_id}")
        return tts_engine.save_voice(request.name, request.source_path, request.ref_text, request.model_id)
    except Exception as e:
        add_log("tts", f"Save voice failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/voices/{name}")
async def delete_voice(name: str, model_id: str = "faster-qwen3-tts"):
    try:
        success = tts_engine.delete_voice(name, model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Voice not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/synthesize")
async def synthesize(request: TTSRequest):
    add_log("tts", f"Synthesis request: {request.text[:50]}... (Speaker: {request.voice}, ModelType: {request.model_id})")
    try:
        # engine.synthesize 现在返回的是文件名
        filename = tts_engine.synthesize(
            text=request.text,
            model_id=request.model_id,
            voice=request.voice,
            language=request.language,
            instruct=request.instruct,
            ref_audio=request.ref_audio,
            ref_text=request.ref_text
        )
        
        # 返回音频的访问 URL
        # app.py 中已经挂载了 /temp_audio 静态目录
        audio_url = f"/temp_audio/{filename}"
        add_log("tts", f"Successfully generated: {filename}")
        
        return {
            "status": "success",
            "audio_url": audio_url,
            "filename": filename
        }
    except Exception as e:
        add_log("tts", f"Synthesis failed: {str(e)}")
        print(f"[!] Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/synthesis/{filename}")
async def delete_synthesis(filename: str):
    try:
        # 构建文件路径
        file_path = os.path.join(RESULTS_DIR, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            add_log("tts", f"Deleted synthesis file: {filename}")
            return {"status": "success", "message": f"File {filename} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"File {filename} not found")
    except Exception as e:
        add_log("tts", f"Delete synthesis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/synthesis-history")
async def get_synthesis_history():
    try:
        # 读取 results 文件夹中的所有文件
        files = [f for f in os.listdir(RESULTS_DIR) if os.path.isfile(os.path.join(RESULTS_DIR, f))]
        history = []
        
        for file in files:
            if file.endswith('.wav'):
                file_path = os.path.join(RESULTS_DIR, file)
                stat = os.stat(file_path)
                
                # 尝试从文件名提取信息
                # 文件名格式：qwen_<timestamp>_<text_part>_<hash>.wav
                parts = file.split('_')
                if len(parts) >= 4:
                    # 获取中间的文本部分
                    text = ' '.join(parts[2:-1])
                else:
                    text = '未知文本'
                
                history.append({
                    'id': f'synth-{stat.st_mtime}',
                    'url': f'/temp_audio/{file}',
                    'text': text,
                    'timestamp': stat.st_mtime * 1000,
                    'duration': None
                })
        
        # 按时间戳降序排序
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {"status": "success", "data": history}
    except Exception as e:
        add_log("tts", f"Get synthesis history failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))