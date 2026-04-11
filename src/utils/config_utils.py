import json
import os

def get_project_root():
    """
    Returns the project root directory (absolute path).
    Assuming this file is at src/utils/config_utils.py
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_abs_path(rel_path):
    """
    Resolves a relative path (from config.json) to an absolute path,
    relative to the project root.
    """
    if os.path.isabs(rel_path):
        return rel_path
    return os.path.join(get_project_root(), rel_path)

def load_config(config_path="config.json"):
    """
    Load configuration from config.json.
    Defaults to looking in the project root.
    """
    if not os.path.isabs(config_path):
        # 统一从根目录读取 config.json
        config_path = os.path.join(get_project_root(), config_path)
    
    if not os.path.exists(config_path):
        print(f"Config file not found at: {config_path}")
        return {}
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def save_config(config_data, config_path="config.json"):
    """
    保存配置到 config.json
    """
    if not os.path.isabs(config_path):
        config_path = os.path.join(get_project_root(), config_path)
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def add_tts_model(model_id: str, model_path: str, voices_dir: str = "tts_results/voice_qwen3"):
    """
    添加 TTS 模型配置到 config.json
    
    Args:
        model_id: 模型 ID（如 qwen3-tts-0.6b）
        model_path: 模型目录路径（相对路径，如 Qwen3-TTS-0.6B）
        voices_dir: 音色目录（相对路径）
    
    Returns:
        bool: 是否成功添加
    """
    config = load_config()
    
    # 检查是否已存在
    tts_models = config.get("tts", {}).get("models", {})
    if model_id in tts_models:
        print(f"Model {model_id} already exists in config")
        return False
    
    # 添加新模型配置
    if "tts" not in config:
        config["tts"] = {}
    if "models" not in config["tts"]:
        config["tts"]["models"] = {}
    
    config["tts"]["models"][model_id] = {
        "path": model_path,
        "voices_dir": voices_dir
    }
    
    return save_config(config)
