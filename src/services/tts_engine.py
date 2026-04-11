import os

# 7840HS/CPU 性能优化：限制 OpenMP 线程数以匹配物理核心，避免超线程导致的缓存竞争
if 'OMP_NUM_THREADS' not in os.environ:
    os.environ['OMP_NUM_THREADS'] = '8'

import json
import torch
import numpy as np
import soundfile as sf
import shutil
import time
import hashlib
from qwen_tts import Qwen3TTSModel
from utils.config_utils import load_config, get_abs_path, get_project_root

try:
    from faster_qwen3_tts import FasterQwen3TTSModel
    HAS_FASTER_QWEN = True
except ImportError:
    HAS_FASTER_QWEN = False

_tmp_config = load_config()
_dirs_cfg = _tmp_config.get("directories", {})

# 确保 TTS 多级存储目录存在 (统一使用 get_abs_path)
RESULTS_DIR = get_abs_path(_dirs_cfg.get("tts_results", "tts_results/results"))
VOICES_ROOT_DIR = get_abs_path(_dirs_cfg.get("tts_voices", "tts_results/Voices"))
TEMP_DIR = get_abs_path(_dirs_cfg.get("tts_temp", "tts_results/temp"))

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(VOICES_ROOT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class TTSEngine:
    def __init__(self):
        self.config = load_config()
        self.tts_config = self.config.get("tts", {})
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._check_vram()
        self.loaded_models = {}
        # 预设音色列表
        self.supported_speakers = ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee"]
        
        # 初始化不同模型的音色库目录
        self.voices_dirs = {}
        for model_id, info in self.tts_config.get("models", {}).items():
            voices_dir = info.get("voices_dir", "tts_results/Voices")
            self.voices_dirs[model_id] = get_abs_path(voices_dir)
            os.makedirs(self.voices_dirs[model_id], exist_ok=True)


    def scan_tts_models_directory(self):
        """
        自动扫描 tts_models 目录，发现新模型并提示更新配置
        返回：(已配置模型列表，新发现的模型列表)
        """
        from utils.config_utils import load_config
        
        tts_models_base = _dirs_cfg.get("tts_models", "tts_models")
        tts_models_path = get_abs_path(tts_models_base)
        
        if not os.path.exists(tts_models_path):
            return [], []
        
        # 获取所有子目录（每个子目录是一个模型）
        discovered_dirs = [d for d in os.listdir(tts_models_path) 
                          if os.path.isdir(os.path.join(tts_models_path, d))]
        
        # 重新加载最新配置（确保能获取到动态添加的模型）
        latest_config = load_config()
        configured_models = list(latest_config.get("tts", {}).get("models", {}).keys())
        # 创建小写映射，用于忽略大小写的匹配
        configured_models_lower = {m.lower().replace('_', '-'): m for m in configured_models}
        
        new_models = []
        
        for dir_name in discovered_dirs:
            # 忽略大小写检查是否已在配置中
            dir_name_normalized = dir_name.lower().replace('_', '-')
            if dir_name_normalized not in configured_models_lower:
                model_path = os.path.join(tts_models_path, dir_name)
                config_json = os.path.join(model_path, "config.json")
                
                # 验证是否为有效的 Qwen3-TTS 模型目录
                if os.path.exists(config_json):
                    try:
                        with open(config_json, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            # 检查是否包含 Qwen3-TTS 特征
                            if "tts_model_type" in cfg or "qwen" in dir_name.lower():
                                new_models.append({
                                    "dir_name": dir_name,
                                    "path": model_path,
                                    "config": cfg
                                })
                    except:
                        pass
        
        return configured_models, new_models

    def get_available_models(self, auto_discover=True):
        """
        获取可用模型列表
        auto_discover: 是否自动发现新模型并提示
        """
        models_config = self.tts_config.get("models", {})
        available = []
        
        # 如果需要，自动扫描新模型
        if auto_discover:
            configured, new_models = self.scan_tts_models_directory()
            if new_models:
                print(f"\n[+] 发现 {len(new_models)} 个新模型:")
                for model in new_models:
                    print(f"    - {model['dir_name']}")
                print(f"\n[!] 提示：请在 config.json 中手动添加这些模型的配置")
        
        for mid, info in models_config.items():
            path = info.get("path")
            if not os.path.isabs(path):
                # 获取 tts_models 根目录
                tts_models_base = _dirs_cfg.get("tts_models", "tts_models")
                path = os.path.abspath(os.path.join(get_project_root(), tts_models_base, path))
            
            if not os.path.exists(path):
                print(f"[!] Model path not found: {path}")
                continue
                
            # 基础信息
            model_info = {
                "id": mid,
                "name": mid.upper(),
                "path": path,
                "model_type": "unknown",
                "speakers": []
            }

            # 读取模型配置文件
            config_path = os.path.join(path, "config.json")
            model_config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        model_config = json.load(f)
                except:
                    pass
            
            # Qwen 系列模型自动识别
            if "qwen3" in mid.lower() or "qwen3" in model_config.get("model_type", "").lower() or "qwen3tts" in "".join(model_config.get("architectures", [])).lower():
                model_info["model_type"] = model_config.get("tts_model_type", "base")
                
                # 如果是 custom_voice 类型
                if model_info["model_type"] == "custom_voice":
                    model_info["speakers"] = self.supported_speakers
                
                # 标记为轻量版（如果模型名称或配置中包含 0.6b、small 等）
                model_name_lower = mid.lower()
                model_size = model_config.get("tts_model_size", "")
                if "0.6b" in model_name_lower or "0b6" in model_size.lower() or "small" in model_name_lower:
                    model_info["name"] = f"{mid.upper()}"
            
            # Faster-Qwen 特有逻辑
            elif "faster-qwen3" in mid:
                model_info["model_type"] = "faster_qwen3"
                model_info["speakers"] = self.supported_speakers

            available.append(model_info)
            
        return available

    def is_model_loaded(self, model_id):
        return model_id in self.loaded_models

    def unload_model(self, model_id):
        if model_id in self.loaded_models:
            print(f"[*] Unloading TTS model: {model_id}")
            # 这里的 unload 逻辑根据具体后端模型而定
            # 对于 PyTorch 模型：
            model_info = self.loaded_models.pop(model_id)
            del model_info["model"]
            
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"[+] Model {model_id} unloaded and VRAM cleared.")
            return True
        return False

    def _check_vram(self):
        """检查 VRAM 情况并并在显存不足时输出警告"""
        if self.device == "cuda":
            try:
                # 获取总显存（单位：GB）
                total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                free_vram = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / (1024**3)
                print(f"[*] CUDA detected. Total VRAM: {total_vram:.2f} GB, Free VRAM: {free_vram:.2f} GB")
                
                # Qwen3-TTS 约需要 4GB 显存，如果可用显存不足则发出警告
                if free_vram < 3.5:
                    print(f"[!] WARNING: Low VRAM ({free_vram:.2f} GB). Loading might fail or be extremely slow.")
            except Exception as e:
                print(f"[!] Failed to check VRAM: {e}")

    def load_model(self, model_id):
        if model_id in self.loaded_models:
            return self.loaded_models[model_id]

        info = self.tts_config.get("models", {}).get(model_id)
        if not info:
            raise ValueError(f"Model ID {model_id} not found in config")

        path = info.get("path")
        if not os.path.isabs(path):
            # 获取 tts_models 根目录
            tts_models_base = _dirs_cfg.get("tts_models", "tts_models")
            path = os.path.abspath(os.path.join(get_project_root(), tts_models_base, path))
        
        # 检查模型配置文件以确定模型类型
        config_path = os.path.join(path, "config.json")
        model_config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
            except:
                pass
        
        # 根据模型配置自动选择加载方式
        model_type = model_config.get("model_type", "").lower()
        arch = model_config.get("architectures", [""])[0].lower()
        
        # 判断是否为 Qwen3-TTS 系列模型
        is_qwen3 = "qwen3" in model_id.lower() or "qwen3" in model_type or "qwen3tts" in arch
        
        if is_qwen3:
            # 检查是否请求使用 faster 版本
            use_faster = "faster" in model_id.lower()
            
            if use_faster and self.device == "cpu":
                print(f"[*] Faster-Qwen3-TTS requested but CUDA not found. Falling back to Standard Qwen3-TTS.")
                return self._load_qwen3tts(path, model_id)
            elif use_faster:
                return self._load_faster_qwen3tts(path, model_id)
            else:
                return self._load_qwen3tts(path, model_id)
        else:
            raise NotImplementedError(f"Engine for {model_id} (type: {model_type}) not available or dropped")

    def _load_qwen3tts(self, path, model_id):
        print(f"[*] Loading Qwen3-TTS from {path}...")
        try:
            # 使用官方 qwen-tts 库加载
            # 注意：CPU 上建议使用 float32，GPU 建议 bfloat16
            # 使用 dtype 代替已废弃的 torch_dtype
            model = Qwen3TTSModel.from_pretrained(
                path,
                device_map=self.device if self.device != "cpu" else None,
                dtype=torch.float32 if self.device == "cpu" else torch.bfloat16,
                attn_implementation="eager" if self.device == "cpu" else "flash_attention_2"
            )
            # 自动探测模型基因 (Base vs Instruct)
            model_type = "base"
            if hasattr(model, 'tts_model_type'):
                model_type = model.tts_model_type
            elif hasattr(model, 'config') and hasattr(model.config, 'tts_model_type'):
                model_type = model.config.tts_model_type
            
            engine = {
                "type": "qwen3-tts",
                "model_id": model_id,
                "model_type": model_type,
                "model": model,
                "device": self.device
            }
            # 针对 7840HS (Zen 4/AVX-512) 的专属优化：
            # 在 CPU 环境下启用 torch.compile 静态图加速
            if self.device == "cpu":
                print("[*] Applying torch.compile (Inductor) for 7840HS Zen4/AVX-512 optimization...")
                try:
                    # 探测真正的计算模块 (Qwen3TTSModel 是一个包装类，其核心 model 才是 nn.Module)
                    compile_target = model
                    if hasattr(model, 'model') and isinstance(model.model, torch.nn.Module):
                        compile_target = model.model
                    
                    if isinstance(compile_target, torch.nn.Module):
                        # 使用 'reduce-overhead' 模式平衡编译时间和推理性能
                        # 注意：直接替换原模块中的对象
                        if hasattr(model, 'model') and compile_target == model.model:
                            model.model = torch.compile(model.model, mode="reduce-overhead")
                        else:
                            compile_target = torch.compile(compile_target, mode="reduce-overhead")
                            
                        print("[+] torch.compile applied successfully to internal compute module.")
                    else:
                        print(f"[!] Skip torch.compile: Target {type(compile_target)} is not a torch.nn.Module")

                except Exception as ce:
                    print(f"[!] torch.compile failed (normal if no C++ compiler found): {ce}")
                    print("[*] Continuing with standard Eager mode.")

            self.loaded_models[model_id] = engine
            print(f"[+] Qwen3-TTS ({model_type}) loaded successfully on {self.device}!")
            return engine
        except Exception as e:
            print(f"[!] Error loading Qwen3-TTS: {type(e).__name__}: {e}")
            if "CUDA out of memory" in str(e):
                print("[!] Suggestion: Your GPU VRAM might be insufficient. Try closing other apps or use a lighter model.")
            raise

    def _load_faster_qwen3tts(self, path, model_id):
        if not HAS_FASTER_QWEN:
            raise ImportError("faster_qwen3_tts library not found. Please install it first.")
        
        print(f"[*] Loading Faster-Qwen3-TTS from {path}...")
        try:
            # 使用 faster-qwen3-tts 库加载 (默认 CUDAGraph 优化)
            model = FasterQwen3TTSModel.from_pretrained(
                path,
                device_map=self.device if self.device != "cpu" else None,
                dtype=torch.float32 if self.device == "cpu" else torch.bfloat16
            )
            
            engine = {
                "type": "faster-qwen3-tts",
                "model_id": model_id,
                "model": model,
                "device": self.device
            }
            self.loaded_models[model_id] = engine
            print(f"[+] Faster-Qwen3-TTS loaded successfully on {self.device}!")
            return engine
        except Exception as e:
            error_msg = str(e)
            print(f"[!] Error loading Faster-Qwen3-TTS: {type(e).__name__}: {error_msg}")
            
            if "CUDA out of memory" in error_msg:
                print("[!] CRITICAL: CUDA Out of Memory. This model requires approx 4GB VRAM.")
            elif "not found" in error_msg.lower():
                print(f"[!] CRITICAL: Model files not found at {path}. Please check your tts_models directory.")
            
            raise

    def synthesize(self, text, model_id, voice=None, language="Auto", instruct="", ref_audio=None, ref_text=None):
        engine = self.load_model(model_id)
        
        # 确保输出目录指向 TTS results/results
        os.makedirs(RESULTS_DIR, exist_ok=True)
        # 防止 text 过长导致文件名问题，使用时间戳或简单哈希
        # 提取前 30 个字作为文件名的一部分
        text_part = text[:30].replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        hash_part = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
        
        # 根据模型类型生成不同的文件名前缀
        filename = f"qwen_{int(time.time())}_{text_part}_{hash_part}.wav"
            
        output_path = os.path.join(RESULTS_DIR, filename)

        # 根据模型 ID 自动选择合成方式
        # 支持所有 Qwen3-TTS 系列模型
        if "faster" in model_id.lower():
            return self._synthesize_faster_qwen3tts(engine, text, output_path, voice, language, instruct)
        elif "qwen3" in model_id.lower():
            return self._synthesize_qwen3tts(engine, text, output_path, voice, language, instruct)
        else:
            raise ValueError(f"Unsupported model_id for synthesis: {model_id}")

    def _synthesize_faster_qwen3tts(self, engine, text, output_path, speaker, language, instruct):
        """Faster-Qwen3-TTS 合成逻辑，复用 Qwen3 的音色克隆/预设逻辑"""
        # 注意：此处直接复用 _synthesize_qwen3tts，因为 faster-qwen3-tts 库的 API
        # 高度兼容原版 Qwen3TTSModel (通常提供 generate, generate_voice_clone 等方法)
        # 如果有差异，则在此处进行映射
        return self._synthesize_qwen3tts(engine, text, output_path, speaker, language, instruct)

    def _synthesize_qwen3tts(self, engine, text, output_path, speaker, language, instruct):
        model = engine["model"]
        model_type = engine.get("model_type", "base")
        model_id = engine.get("model_id", "qwen3-tts")
        # 1. 路径预处理：在模型特定的三层级目录中精准定位 (Voices/<Name>/<ID>.xxx)
        speaker_id = str(speaker).strip() if speaker else ""
        custom_wav = ""
        custom_json = ""
        custom_pt = ""
        
        # 获取该模型应该搜索的音色库根目录
        current_voices_root = self.voices_dirs.get(model_id, VOICES_ROOT_DIR)
        
        if speaker_id:
            # 遍历寻找包含该 ID 的子文件夹 (仅在当前模型的 voices_root 下寻找)
            found_folder = None
            if os.path.exists(current_voices_root):
                for root, dirs, files in os.walk(current_voices_root):
                    # 检查 JSON 文件是否存在（优先）
                    if f"{speaker_id}.json" in files:
                        found_folder = root
                        break
                    # 兜底：检查 WAV 文件（兼容旧格式）
                    elif f"{speaker_id}.wav" in files:
                        found_folder = root
                        break
            
            if found_folder:
                custom_wav = os.path.join(found_folder, f"{speaker_id}.wav")
                custom_json = os.path.join(found_folder, f"{speaker_id}.json")
                custom_pt = os.path.join(found_folder, f"{speaker_id}.pt")
            
            # --- 兜底检查：如果在 Voices 没找到，尝试在 TEMP_DIR 找 (支持 ad-hoc 使用临时录音) ---
            if not custom_wav or not os.path.exists(custom_wav):
                temp_wav = os.path.join(TEMP_DIR, f"{speaker_id}.wav")
                if os.path.exists(temp_wav):
                    custom_wav = temp_wav
                    custom_json = "" # 临时录音无元数据
                    custom_pt = ""

        # 2. 核心逻辑分支 A：音色克隆模式 (ICL)
        # 命中条件：文件物理存在 (通过 ID 直接定位)
        if custom_wav and os.path.exists(custom_wav) and os.path.exists(custom_json):
            print(f"[*] Identified custom voice! Switching to Voice Cloning (ICL) mode. ID: {speaker_id}")
            try:
                # 读取参考元数据 (提取 ref_text 和验证名称)
                with open(custom_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    ref_text = meta.get("ref_text", "")
                    display_name = meta.get("display_name", speaker_id)
                    
                # 持久化优化：加速路径
                voice_clone_prompt = None
                
                # 为不同模型保存独立的缓存文件
                # 格式：{speaker_id}_{model_dim}.pt
                model_enc_dim = None
                custom_pt_model = None
                
                # 只有模型已加载时，才尝试加载缓存
                if hasattr(model, 'config'):
                    model_enc_dim = model.config.speaker_encoder_config.get('enc_dim', 2048)
                    custom_pt_model = os.path.join(found_folder, f"{speaker_id}_{model_enc_dim}.pt")
                    
                    # 优先加载模型特定的缓存
                    if os.path.exists(custom_pt_model):
                        print(f"[*] Loading model-specific prompt from {custom_pt_model} (Fast Path) for: {display_name}")
                        try:
                            voice_clone_prompt = torch.load(custom_pt_model, map_location=self.device, weights_only=False)
                            
                            # 维度兼容性检查（即使是模型特定缓存，也做最后验证）
                            prompt_enc_dim = None
                            if isinstance(voice_clone_prompt, (list, tuple)) and len(voice_clone_prompt) > 0:
                                first_item = voice_clone_prompt[0]
                                if hasattr(first_item, 'embedding') and first_item.embedding is not None:
                                    prompt_enc_dim = first_item.embedding.shape[-1]
                            
                            # 如果维度不匹配，丢弃缓存
                            if prompt_enc_dim is not None and prompt_enc_dim != model_enc_dim:
                                print(f"[!] Model-specific cache dimension mismatch! Expected {model_enc_dim}, got {prompt_enc_dim}.")
                                print(f"[*] Will recompute from audio (safe path).")
                                voice_clone_prompt = None
                        except Exception as load_err:
                            print(f"[!] Failed to load model-specific cache: {load_err}")
                            print(f"[*] Will use raw audio instead.")
                            voice_clone_prompt = None
                    else:
                        # 尝试加载通用缓存（兼容旧格式）
                        if os.path.exists(custom_pt):
                            print(f"[*] Loading generic prompt from {custom_pt} (Fast Path) for: {display_name}")
                            try:
                                voice_clone_prompt = torch.load(custom_pt, map_location=self.device, weights_only=False)
                                
                                # 维度兼容性检查
                                prompt_enc_dim = None
                                if isinstance(voice_clone_prompt, (list, tuple)) and len(voice_clone_prompt) > 0:
                                    first_item = voice_clone_prompt[0]
                                    if hasattr(first_item, 'embedding') and first_item.embedding is not None:
                                        prompt_enc_dim = first_item.embedding.shape[-1]
                                
                                # 如果维度不匹配，丢弃通用缓存
                                if prompt_enc_dim is not None and prompt_enc_dim != model_enc_dim:
                                    print(f"[!] Generic cache dimension mismatch! Expected {model_enc_dim}, got {prompt_enc_dim}.")
                                    print(f"[*] Will recompute from audio (safe path).")
                                    voice_clone_prompt = None
                            except Exception as load_err:
                                print(f"[!] Failed to load generic cache: {load_err}")
                                print(f"[*] Will use raw audio instead.")
                                voice_clone_prompt = None
                        else:
                            print(f"[*] No cache found, will compute from audio.")
                else:
                    # 模型未加载时，直接使用 WAV 重新计算，避免维度不匹配
                    print(f"[*] Model not loaded, will compute from audio (safe path).")
                    voice_clone_prompt = None
                


                # 调用克隆接口
                if hasattr(model, 'generate_voice_clone'):
                    wavs, sr = model.generate_voice_clone(
                        text=text,
                        language=language if language != "Auto" else "Auto",
                        ref_audio=custom_wav if not voice_clone_prompt else None,
                        ref_text=ref_text if not voice_clone_prompt else None,
                        voice_clone_prompt=voice_clone_prompt,
                        x_vector_only_mode=False
                    )
                    sf.write(output_path, wavs[0], sr)
                    
                    # 自动保存模型特定的缓存（如果没有）
                    # 当使用大模型的音色时，自动为小模型创建缓存
                    if hasattr(model, 'config') and hasattr(model, 'create_voice_clone_prompt'):
                        model_enc_dim = model.config.speaker_encoder_config.get('enc_dim', 2048)
                        custom_pt_model = os.path.join(found_folder, f"{speaker_id}_{model_enc_dim}.pt")
                        
                        # 如果模型特定缓存不存在，自动创建
                        if not os.path.exists(custom_pt_model):
                            print(f"[*] Auto-saving model-specific prompt for future use...")
                            try:
                                prompts = model.create_voice_clone_prompt(ref_audio=custom_wav, ref_text=ref_text)
                                torch.save(prompts, custom_pt_model)
                                print(f"[+] Auto-saved model-specific prompt to {custom_pt_model}")
                            except Exception as save_err:
                                print(f"[!] Failed to auto-save model-specific cache: {save_err}")
                    
                    return os.path.basename(output_path)
            except Exception as e:
                print(f"[!] Custom voice cloning error: {e}")
                raise e
        
        # 3. 核心逻辑分支 B：预设/兜底模式
        else:
            # 基础版模型硬约束：必须提供参考
            if model_type == "base":
                err_msg = "Qwen3-TTS Base 版不具备预设音色，必须选择一个『个人音色』或进行『实时录音』才能合成。"
                print(f"[!] Policy restriction: {err_msg}")
                raise ValueError(err_msg)

            # 指令/设计版模型：支持高级自定义和语气提示
            try:
                if hasattr(model, 'generate_custom_voice'):
                    # 如果用户没提供 speaker_id，或者提供的 ID 既不是个人音色也不在预设列表
                    if not speaker_id or speaker_id not in self.supported_speakers:
                        err_msg = "尚未选择有效音色。请从‘系统音色’或‘个人音色’列表中选择一个音色后再合成。"
                        print(f"[!] Policy restriction: {err_msg}")
                        raise ValueError(err_msg)
                        
                    final_speaker = speaker_id
                    print(f"[*] Using generate_custom_voice for: {final_speaker}")
                    wavs, sr = model.generate_custom_voice(
                        text=text,
                        language=language if language != "Auto" else "Auto",
                        speaker=final_speaker,
                        instruct=instruct
                    )
                else:
                    # 最后的兜底：普通生成
                    print("[*] Falling back to basic generate()")
                    wavs, sr = model.generate(
                        text=text,
                        language=language if language != "Auto" else "Auto"
                    )
                
                sf.write(output_path, wavs[0], sr)
                return os.path.basename(output_path)
            except Exception as e:
                print(f"[!] Preset synthesis failed: {e}")
                raise e


    def get_voice_library(self, model_id="qwen3-tts"):
        """返回完整的音色库：预设 + 本地自定义音色 (支持多级子目录扫描)"""
        library = {
            "presets": self.supported_speakers,
            "cloned": []
        }
        
        # 获取该模型对应的音色库目录
        voices_dir = self.voices_dirs.get(model_id, "tts_results/voice_qwen3")
        
        # 获取当前模型的维度信息
        model_enc_dim = 2048  # 默认值
        try:
            engine = self.load_model(model_id)
            model = engine["model"]
            if hasattr(model, 'config') and hasattr(model.config, 'speaker_encoder_config'):
                model_enc_dim = model.config.speaker_encoder_config.get('enc_dim', 2048)
        except Exception as e:
            print(f"[!] Failed to get model enc_dim: {e}, using default 2048")
        
        # 递归读取本地自定义音色子目录
        if os.path.exists(voices_dir):
            for root, dirs, files in os.walk(voices_dir):
                for f in files:
                    # 仅通过 .json 元数据来确认识别有效的音色组
                    if f.endswith(".json"):
                        safe_id = f.replace(".json", "")
                        json_path = os.path.join(root, f)
                        wav_path = os.path.join(root, f"{safe_id}.wav")
                        
                        if not os.path.exists(wav_path):
                            continue
                            
                        try:
                            with open(json_path, "r", encoding="utf-8") as meta_f:
                                meta = json.load(meta_f)
                                display_name = meta.get("display_name", "未知音色")
                                
                                # 如果没有显示名，跳过
                                if not display_name or display_name == "":
                                    continue
                                
                                # 检查音色兼容性
                                voice_enc_dim = meta.get("enc_dim", 2048)
                                voice_model_id = meta.get("model_id", "")
                                
                                # 如果维度不匹配，检查是否可以适配
                                is_compatible = False
                                compat_reason = ""
                                
                                if voice_enc_dim == model_enc_dim:
                                    # 维度完全匹配
                                    is_compatible = True
                                    compat_reason = "dimension match"
                                elif voice_enc_dim > model_enc_dim and voice_enc_dim % model_enc_dim == 0:
                                    # 高维→低维：可以适配
                                    is_compatible = True
                                    compat_reason = f"adaptable ({voice_enc_dim}D -> {model_enc_dim}D)"
                                elif voice_enc_dim < model_enc_dim:
                                    # 低维→高维：不兼容
                                    is_compatible = False
                                    compat_reason = f"incompatible ({voice_enc_dim}D < {model_enc_dim}D)"
                                else:
                                    # 无法整除：不兼容
                                    is_compatible = False
                                    compat_reason = f"incompatible dimensions"
                                
                                # 只添加兼容的音色
                                if is_compatible:
                                    library["cloned"].append({
                                        "id": safe_id,
                                        "name": display_name,
                                        "path": wav_path,
                                        "enc_dim": voice_enc_dim,
                                        "compatible": compat_reason
                                    })
                                else:
                                    print(f"[!] Skip incompatible voice: {display_name} ({compat_reason})")
                                    
                        except Exception as e:
                            print(f"[!] Library scan error for {f}: {e}")
                            
        return library

    def save_voice(self, name, source_path, ref_text="", model_id="faster-qwen3-tts"):
        """持久化保存一个音色及其元数据到模型指定的 voices_dir (文件夹隔离方案)"""
        # 1. 获取模型特定的音色库根目录
        target_root = self.voices_dirs.get(model_id)
        if not target_root:
            # 兜底使用全局 Voices
            target_root = VOICES_ROOT_DIR
            
        # 2. 准备并创建子文件夹 (处理特殊字符)
        safe_folder_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in name])
        voice_dir = os.path.join(target_root, safe_folder_name)
        os.makedirs(voice_dir, exist_ok=True)
        
        # 处理全路径或相对 TEMP_DIR 的路径
        actual_source = source_path
        if not os.path.isabs(source_path):
            actual_source = os.path.join(TEMP_DIR, source_path)
            
        if not os.path.exists(actual_source):
             # 再次尝试 RESULTS_DIR (兼容性)
             fallback = os.path.join(RESULTS_DIR, source_path)
             if os.path.exists(fallback):
                 actual_source = fallback
             else:
                 raise FileNotFoundError(f"Source audio not found: {source_path}")
            
        # 2. 使用用户输入的名称作为 ID
        safe_id = name
        # 替换特殊字符为下划线
        safe_id = ''.join([c if c.isalnum() or c in " _-" else "_" for c in safe_id])
        
        target_wav = os.path.join(voice_dir, f"{safe_id}.wav")
        target_json = os.path.join(voice_dir, f"{safe_id}.json")
        target_pt = os.path.join(voice_dir, f"{safe_id}.pt")
        target_npy = os.path.join(voice_dir, f"{safe_id}.npy")
        
        # 2. 复制/移动音频并保存文本与显示名
        # 使用 move 而不是 copy，实现"录音不保存就删除，保存就存入"的逻辑
        shutil.move(actual_source, target_wav)
        
        # 获取模型维度信息并保存到 JSON
        model_enc_dim = 2048  # 默认值
        try:
            engine = self.load_model(model_id)
            model = engine["model"]
            if hasattr(model, 'config') and hasattr(model.config, 'speaker_encoder_config'):
                model_enc_dim = model.config.speaker_encoder_config.get('enc_dim', 2048)
        except Exception as e:
            print(f"[!] Failed to get model enc_dim: {e}, using default 2048")
        
        with open(target_json, "w", encoding="utf-8") as f:
            json.dump({
                "display_name": name, 
                "ref_text": ref_text,
                "model_id": model_id,
                "enc_dim": model_enc_dim,
                "created_at": __import__('time').time()
            }, f, ensure_ascii=False, indent=2)
            
        # 3. 深度特征固化：提取 Prompt 和 Embedding
        try:
            # 确保模型已加载 (如果未加载则临时拉起)
            engine = self.load_model(model_id)
            model = engine["model"]
            
            if hasattr(model, 'create_voice_clone_prompt'):
                print(f"[*] Extracting industrial features (Hex ID: {safe_id}) for: {name}")
                prompts = model.create_voice_clone_prompt(ref_audio=target_wav, ref_text=ref_text)
                
                # 保存为 PyTorch 专有格式 (含完整上下文信息)
                torch.save(prompts, target_pt)
                
                # 尝试提取原始向量并保存为通用的 NumPy 格式 (跨平台备份)
                try:
                    embeddings = []
                    for item in prompts:
                        if hasattr(item, 'embedding') and item.embedding is not None:
                            embeddings.append(item.embedding.cpu().numpy())
                        elif isinstance(item, dict) and 'embedding' in item:
                            embeddings.append(item['embedding'].cpu().numpy())
                    
                    if embeddings:
                        np.save(target_npy, np.stack(embeddings))
                except Exception as ne:
                    print(f"[!] Numpy embedding export failed (minor): {ne}")
                    
                print(f"[+] Advanced features generated for safe_id: {safe_id}")
        except Exception as e:
            print(f"[!] Advanced feature extraction failed: {e}")

        return {"name": name, "id": safe_id, "path": target_wav}

    def delete_voice(self, name, model_id="faster-qwen3-tts"):
        """同步删除指定模型音色文件夹及其所有元数据"""
        target_root = self.voices_dirs.get(model_id)
        if not target_root or not os.path.exists(target_root):
            return False
            
        # 寻找包含该 ID 的文件夹并删除
        deleted = False
        for folder_name in os.listdir(target_root):
            folder_path = os.path.join(target_root, folder_name)
            if not os.path.isdir(folder_path):
                continue
            
            if f"{name}.json" in os.listdir(folder_path):
                print(f"[*] Found voice folder for {name} in {model_id} library: {folder_path}. Deleting...")
                shutil.rmtree(folder_path)
                deleted = True
                break
            
        return deleted

# Global singleton
tts_engine = TTSEngine()
