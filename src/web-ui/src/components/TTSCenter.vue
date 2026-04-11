<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { 
  Mic, 
  Settings, 
  Save,
  Play,
  Pause,
  Download,
  Wind,
  Activity,
  CheckCircle2,
  AudioLines,
  FastForward,
  Rewind,
  Trash2,
  Square,
  Sparkles,
  RefreshCw
} from 'lucide-vue-next';
import { TTSService, WhisperService } from '../api/audio';

const emit = defineEmits(['log']);

// --- 状态 ---
const availableModels = ref<any[]>([]);
const whisperModels = ref<string[]>([]);
const selectedWhisperModel = ref('whisper_large.bin');
const selectedModelId = ref('');
// const activeService = ref(''); // 默认为空以触发“请选择”占位符
const isServiceRunning = ref(false);
const isPending = ref(false);

const ttsPresets = ref<string[]>([]);
const clonedVoices = ref<any[]>([]);
const selectedSpeaker = ref('');
const enablePresetVoices = ref(false); // 预设音色总开关

watch(enablePresetVoices, (newVal) => {
  if (!newVal && ttsPresets.value.includes(selectedSpeaker.value)) {
    selectedSpeaker.value = '';
  }
});

const isRecording = ref(false);
const recordingTime = ref(0);
let mediaRecorder: MediaRecorder | null = null;
let recordingChunks: Blob[] = [];
let timerInterval: any = null;

// 新发现的模型列表
const newDiscoveredModels = ref<any[]>([]);

const ttsInput = ref('');
const instructPrompt = ref('');
const refAudioPath = ref('');
const refAudioUrl = ref('');
const refText = ref('');
const saveVoiceName = ref('');
const useRecordedVoice = ref(false); // 是否直接使用当前录音进行合成

const currentAudioUrl = ref('');
const isSynthesizing = ref(false);
const isSavingVoice = ref(false);
const audioMeta = ref({
  duration: '0:00',
  pitch: '正常'
});

const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const playerRef = ref<HTMLAudioElement | null>(null);

const formatTime = (s: number) => {
  const mins = Math.floor(s / 60);
  const secs = Math.floor(s % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

// --- 初始化 ---
async function init() {
  try {
    await refreshModels();
    refreshVoiceLibrary();
    
    // 拉取 Whisper 模型供识别使用
    const whisperRes = await WhisperService.getModels();
    whisperModels.value = whisperRes.data;
    // 优先保留 whisper_large.bin 的默认选中状态，如果列表中没有则回退
    if (!whisperModels.value.includes('whisper_large.bin') && whisperModels.value.length > 0) {
      selectedWhisperModel.value = whisperModels.value[0];
    }
  } catch (e) {}
}

// 刷新模型列表
async function refreshModels() {
  try {
    emit('log', '刷新模型列表...', 'info');
    const modelRes = await TTSService.getModels();
    availableModels.value = modelRes.data;
    if (availableModels.value.length > 0) {
      // 保持当前选中的模型，如果不存在则选择第一个
      const currentSelection = selectedModelId.value;
      const stillExists = availableModels.value.find(m => m.id === currentSelection);
      if (!stillExists) {
        selectedModelId.value = availableModels.value[0].id;
      }
      checkStatus();
    }
    // 检测是否有新模型
    const discoverRes = await TTSService.discoverModels();
    if (discoverRes.data.has_new && discoverRes.data.new_models.length > 0) {
      newDiscoveredModels.value = discoverRes.data.new_models;
      const newModelNames = discoverRes.data.new_models.map((m: any) => m.dir_name).join(', ');
      emit('log', `发现新模型：${newModelNames}。请点击下方按钮一键添加。`, 'info');
    } else {
      newDiscoveredModels.value = [];
    }
    emit('log', '模型列表已刷新', 'success');
  } catch (e: any) {
    emit('log', '刷新失败：' + e.message, 'error');
  }
}

// 添加新模型到配置
async function addNewModel(modelDir: string) {
  try {
    emit('log', `正在添加模型 ${modelDir}...`, 'info');
    const res = await TTSService.addModel(modelDir);
    emit('log', res.data.message, 'success');
    // 添加成功后刷新模型列表
    await refreshModels();
  } catch (e: any) {
    emit('log', '添加失败：' + (e.response?.data?.detail || e.message), 'error');
  }
}

async function checkStatus() {
  if (!selectedModelId.value) return;
  try {
    const res = await TTSService.getStatus(selectedModelId.value);
    isServiceRunning.value = res.data.loaded;
  } catch (e) {}
}

async function refreshVoiceLibrary() {
  try {
    const voiceRes = await TTSService.getVoices();
    ttsPresets.value = voiceRes.data.presets;
    clonedVoices.value = voiceRes.data.cloned;
    if (ttsPresets.value.length > 0 && !selectedSpeaker.value && enablePresetVoices.value) {
       selectedSpeaker.value = ttsPresets.value[0];
    }
  } catch (e) {}
}

// --- 操作 ---
async function toggleService() {
  if (isPending.value) return;
  isPending.value = true;
  const targetOn = !isServiceRunning.value;
  try {
    if (targetOn) {
      await TTSService.start(selectedModelId.value);
      isServiceRunning.value = true;
    } else {
      await TTSService.stop(selectedModelId.value);
      isServiceRunning.value = false;
    }
  } catch (e: any) {
    alert('启动失败');
  } finally {
    isPending.value = false;
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    recordingChunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordingChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      const blob = new Blob(recordingChunks, { type: 'audio/wav' });
      try {
        const res = await TTSService.uploadRef(blob, `rec_${Date.now()}.wav`);
        refAudioPath.value = res.data.path;
        refAudioUrl.value = res.data.url;
      } catch (e) {}
    };
    mediaRecorder.start();
    isRecording.value = true;
    recordingTime.value = 0;
    timerInterval = setInterval(() => { recordingTime.value++; }, 1000);
  } catch (e) {}
}

const isRecognizing = ref(false);
async function performRecognition() {
  if (!refAudioPath.value) { alert('请先录制音频'); return; }
  if (!selectedWhisperModel.value) { alert('请先在侧边栏配置中选择 Whisper 模型'); return; }
  
  isRecognizing.value = true;
  refText.value = '识别中...';
  try {
    const res = await WhisperService.recognize({
      audio_path: refAudioPath.value,
      model: selectedWhisperModel.value
    });
    refText.value = (res.data as any).text;
  } catch (e: any) {
    alert('识别失败: ' + (e.response?.data?.detail || e.message));
    refText.value = '';
  } finally {
    isRecognizing.value = false;
  }
}

const isPlayingRef = ref(false);
function playRefAudio() {
  if (!refAudioUrl.value) return;
  
  // 使用后端返回的相对路径，Vite Proxy 会自动转发到正确的后端端口
  const audio = new Audio(refAudioUrl.value);
  isPlayingRef.value = true;
  audio.play();
  audio.onended = () => { isPlayingRef.value = false; };
}

function stopRecording() {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop();
    isRecording.value = false;
    clearInterval(timerInterval);
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
  }
}

function handleFileUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => { ttsInput.value = e.target?.result as string; };
  reader.readAsText(file);
}

async function performSynthesize() {
  if (!isServiceRunning.value) { alert('服务未启动，请先开启服务。'); return; }
  
  // Qwen3-TTS 特定拦截：Base 版必须有参考音频或音色名
  if (selectedModelId.value === 'qwen3-tts' && !selectedSpeaker.value && !refAudioPath.value) {
    alert('【操作引导】Qwen3-TTS 需要一个参考音色。请在下方「选择音色」或在左侧「音色实时采集」录制一段声音。');
    return;
  }

  isSynthesizing.value = true;
  try {
    let finalSpeaker = selectedSpeaker.value;
    
    // 如果选择了“使用当前录音”，则覆盖已选音色
    if (useRecordedVoice.value && refAudioPath.value) {
      finalSpeaker = '';
    }

    const res = await TTSService.synthesize({
      text: ttsInput.value,
      model_id: selectedModelId.value,
      voice: finalSpeaker,
      instruct: instructPrompt.value,
      ref_audio: refAudioPath.value,
      ref_text: refText.value
    });
    
    if (res.data && res.data.audio_url) {
      currentAudioUrl.value = res.data.audio_url;
      console.log('[TTS] Synthesis success, URL:', currentAudioUrl.value);
    } else {
      throw new Error('Backend failed to return audio URL');
    }
  } catch (e: any) {
    console.error('[TTS] Synthesis failed:', e);
    alert('合成失败: ' + (e.response?.data?.detail || e.message));
  } finally {
    isSynthesizing.value = false;
  }
}

async function handleSaveVoice() {
  if (!saveVoiceName.value || !refAudioPath.value) return;
  
  isSavingVoice.value = true;
  try {
    await TTSService.saveVoice({
      name: saveVoiceName.value,
      source_path: refAudioPath.value,
      ref_text: refText.value
    });
    
    // 立即刷新列表并选中新音色
    await refreshVoiceLibrary();

    // 找到新保存的那个音色并选中
    const newVoice = clonedVoices.value.find(v => v.name === saveVoiceName.value);
    if (newVoice) {
      selectedSpeaker.value = newVoice.id;
    }
    
    // 清空命名区
    saveVoiceName.value = '';
    // 如果需要保留参考文案供合成可注释下行
    // refText.value = '';
    
  } catch (e: any) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message));
  } finally {
    isSavingVoice.value = false;
  }
}

function togglePlay() {
  if (!playerRef.value) return;
  if (isPlaying.value) playerRef.value.pause();
  else playerRef.value.play();
}

onMounted(init);
watch(selectedModelId, checkStatus);
</script>

<template>
  <div class="flex h-full bg-[#f8fafc] overflow-hidden">
    
    <!-- 第二栏：集约化侧边栏 (控制 & 音色管理) -->
    <aside class="w-[320px] bg-white border-r border-slate-200 flex flex-col shadow-sm z-10 overflow-y-auto no-scrollbar">
      <div class="p-6 space-y-8">
        <!-- 1 服务配置 -->
        <div class="space-y-4">
          <div class="flex items-center gap-2 mb-2">
             <Settings class="w-4 h-4 text-slate-400" />
             <h3 class="text-[12px] font-bold text-slate-400 uppercase tracking-widest">服务配置</h3>
          </div>
          
          <div class="space-y-3">
            <!-- 新模型提示 -->
            <div v-if="newDiscoveredModels.length > 0" class="bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2">
              <div class="flex items-center gap-2 text-blue-700">
                <Sparkles class="w-3.5 h-3.5" />
                <span class="text-[11px] font-bold">发现新模型</span>
              </div>
              <div class="space-y-1">
                <div v-for="model in newDiscoveredModels" :key="model.dir_name" class="flex items-center justify-between gap-2">
                  <span class="text-[10px] text-blue-600">{{ model.dir_name }}</span>
                  <button 
                    @click="addNewModel(model.dir_name)"
                    class="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-[10px] rounded transition-colors"
                  >
                    添加
                  </button>
                </div>
              </div>
            </div>
            
            <!-- 并排的刷新与选择 -->
            <div class="flex items-center gap-2">
              <button @click="refreshModels" class="shrink-0 px-2 py-2 border border-dashed border-slate-200 rounded text-[11px] text-slate-500 hover:bg-slate-50 hover:border-blue-300 hover:text-blue-600 flex items-center justify-center gap-1.5 transition-all">
                <RefreshCw class="w-3 h-3" /> 刷新
              </button>
              <select v-model="selectedModelId" class="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-[13px] outline-none shadow-sm min-w-0">
                <option value="" disabled selected>-- 请选择模型版本 --</option>
                <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
              </select>
            </div>
            
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span class="text-[12px] text-slate-500 font-bold uppercase tracking-tight">{{ isServiceRunning ? '运行中' : '已停止' }}</span>
                <label class="relative inline-flex items-center cursor-pointer scale-75">
                   <input type="checkbox" :checked="isServiceRunning" @change="toggleService" class="sr-only peer" :disabled="isPending">
                   <div class="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-blue-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                </label>
            </div>
          </div>
        </div>

        <!-- 2 音色实时克隆 (采集区) -->
        <div class="space-y-4 border-t border-slate-100 pt-6">
          <div class="flex items-center justify-between group">
             <div class="flex items-center gap-2">
                <Mic class="w-4 h-4 text-blue-500" />
                <h3 class="text-[13px] font-bold text-slate-700 uppercase tracking-tight">音色实时采集</h3>
             </div>
             
             <!-- 录音按钮右对齐紧凑 -->
             <button 
                @click="isRecording ? stopRecording() : startRecording()" 
                :class="isRecording ? 'bg-red-500 ring-4 ring-red-100' : 'bg-blue-600 hover:bg-blue-700'"
                class="w-8 h-8 rounded-full text-white flex items-center justify-center transition-all shadow-md active:scale-90"
              >
                <Square v-if="isRecording" class="w-3.5 h-3.5" />
                <Mic v-else class="w-3.5 h-3.5" />
              </button>
          </div>

          <div class="space-y-2">
             <!-- 状态指示器与识别按钮 -->
             <div class="flex items-center justify-between px-1">
                <div class="flex items-center gap-2">
                   <div class="w-1.5 h-1.5 rounded-full" :class="isRecording ? 'bg-red-500 animate-pulse' : (refAudioPath ? 'bg-green-500' : 'bg-gray-300')"></div>
                   <span class="text-[11px] font-mono text-slate-500">{{ isRecording ? 'RECORDING' : (refAudioPath ? 'READY' : 'IDLE') }}</span>
                   <span class="text-[11px] font-mono text-slate-400">/ {{ formatTime(recordingTime) }}</span>
                </div>
                <!-- 智能识别控制组 -->
                <div class="flex items-center gap-2">
                    <!-- 播放采集音频按钮 -->
                    <button 
                      v-if="refAudioPath && !isRecording"
                      @click="playRefAudio" 
                      class="flex items-center justify-center p-1.5 bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-600 rounded transition-colors"
                      title="回放采集的音频"
                    >
                       <Activity v-if="isPlayingRef" class="w-3.5 h-3.5 text-blue-500 animate-pulse" />
                       <Play v-else class="w-3.5 h-3.5 font-bold" />
                    </button>

                    <!-- 智能识别按钮 -->
                    <button 
                      v-if="refAudioPath && !isRecording"
                      @click="performRecognition" 
                      :disabled="isRecognizing"
                      class="flex items-center gap-1.5 px-2 py-1 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-600 rounded text-[10px] font-bold transition-colors disabled:opacity-50"
                      title="使用 Whisper-CLI 转录录音"
                    >
                       <Activity v-if="isRecognizing" class="w-3 h-3 animate-spin" />
                       <Sparkles v-else class="w-3 h-3" />
                       <span>{{ isRecognizing ? '识别中...' : '智能识别' }}</span>
                    </button>
                </div>
             </div>

             <div v-if="refAudioPath || isRecording" class="space-y-2 pt-1">
                <textarea 
                  v-model="refText" 
                  placeholder="等待识别或手动输入参考文本..."
                  class="w-full bg-slate-50 border border-slate-200 rounded-lg p-3 text-[12px] h-24 outline-none focus:border-blue-500 focus:bg-white transition-all resize-none leading-relaxed"
                ></textarea>
                
                <div class="flex gap-2">
                   <input v-model="saveVoiceName" placeholder="音色命名" class="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-[12px] outline-none focus:bg-white focus:border-blue-500 transition-all" />
                  <button 
                    @click="handleSaveVoice" 
                    :disabled="!saveVoiceName || isSavingVoice"
                    class="px-3 bg-slate-900 text-white rounded-lg hover:bg-black transition-colors disabled:bg-slate-300 flex items-center justify-center min-w-[40px]"
                    title="保存到个人音色库"
                  >
                     <Activity v-if="isSavingVoice" class="w-4 h-4 animate-spin" />
                     <Save v-else class="w-4 h-4" />
                  </button>
                </div>
                
                <!-- 录音使用选项 -->
                <div v-if="refAudioPath && !isRecording" class="flex items-center gap-2 py-1 px-1 bg-blue-50/50 rounded-lg border border-blue-100">
                    <input type="checkbox" v-model="useRecordedVoice" class="w-3 h-3 accent-blue-600" id="use-rec-cb" />
                    <label for="use-rec-cb" class="text-[11px] font-bold text-blue-600 cursor-pointer">使用当前录音作为克隆音色</label>
                </div>

                <!-- 模型选择 (仅在有克隆需要时显示或置于配置区) -->
                <div class="flex items-center justify-between pt-1 opacity-60">
                   <span class="text-[10px] text-slate-400 font-bold uppercase">转录模型</span>
                   <select v-model="selectedWhisperModel" class="bg-transparent text-[10px] text-slate-500 outline-none">
                      <option v-for="m in whisperModels" :key="m" :value="m">{{ m }}</option>
                   </select>
                </div>
             </div>
          </div>
        </div>

        <!-- 3 音色库 -->
        <div class="space-y-4 border-t border-slate-100 pt-6">
           <div class="flex items-center gap-2 mb-2">
              <AudioLines class="w-4 h-4 text-slate-400" />
              <h3 class="text-[12px] font-bold text-slate-400 uppercase tracking-widest">选择音色</h3>
           </div>
           
           <div class="space-y-6">
              <!-- 我的音色 -->
              <div class="space-y-2">
                 <div class="text-[11px] font-bold text-blue-600 flex items-center gap-2">
                    <CheckCircle2 class="w-3 h-3" /> 我的个人音色
                 </div>
                 <div class="grid grid-cols-1 gap-2">
                    <div v-if="clonedVoices.length === 0" class="text-[11px] text-slate-400 bg-slate-50 p-3 rounded-lg border border-dashed text-center italic">暂无克隆记录</div>
                    <div 
                      v-for="c in clonedVoices" :key="c.id"
                      @click="selectedSpeaker = c.id"
                      class="px-3 py-2 rounded-lg border flex items-center justify-between cursor-pointer transition-all"
                      :class="selectedSpeaker === c.id ? 'bg-blue-600 border-blue-600 text-white shadow-sm' : 'bg-white border-slate-200 hover:border-blue-300 text-slate-700'"
                    >
                       <span class="text-[12px] font-medium truncate">{{ c.name }}</span>
                       <Trash2 v-if="selectedSpeaker !== c.id" @click.stop="TTSService.deleteVoice(c.id).then(refreshVoiceLibrary)" class="w-3 h-3 text-slate-300 hover:text-red-500" />
                    </div>
                 </div>
              </div>

              <!-- 预设音色 -->
              <div class="space-y-2">
                 <div class="flex items-center justify-between">
                   <div class="text-[11px] font-bold text-slate-400 flex items-center gap-2">
                      <Wind class="w-3 h-3" /> 系统核心音色
                   </div>
                   <label class="relative inline-flex items-center cursor-pointer scale-75" title="启用/禁用预设音色">
                      <input type="checkbox" v-model="enablePresetVoices" class="sr-only peer">
                      <div class="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-blue-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                   </label>
                 </div>
                 <select 
                   v-model="selectedSpeaker" 
                   :disabled="!enablePresetVoices"
                   class="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2 text-[13px] text-slate-600 outline-none hover:border-slate-400 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                 >
                    <option value="" disabled selected>{{ enablePresetVoices ? '-- 选择预设音色 --' : '-- 预设音色未开启 --' }}</option>
                    <option v-for="s in ttsPresets" :key="s" :value="s">{{ s }}</option>
                 </select>
              </div>
           </div>
        </div>
      </div>
    </aside>

    <!-- 第三栏：管理页面 -->
    <main class="flex-1 flex flex-col p-10 gap-8 overflow-y-auto bg-white">
      
      <!-- 合成音频指示与播放 -->
      <section class="grid grid-cols-12 gap-8">
         <!-- 合成音频指示状态 -->
         <div class="col-span-4 border border-slate-200 rounded-2xl p-6 shadow-sm">
            <h3 class="text-[14px] font-bold text-slate-800 mb-4">合成音频</h3>
            <div class="space-y-4">
               <div class="flex justify-between items-center bg-slate-50 p-3 rounded-lg">
                  <span class="text-[12px] text-slate-500">长度</span>
                  <span class="text-[14px] font-bold">{{ audioMeta.duration }}</span>
               </div>
               <div class="flex justify-between items-center bg-slate-50 p-3 rounded-lg">
                  <span class="text-[12px] text-slate-500">声调高低</span>
                  <span class="text-[14px] font-bold">{{ audioMeta.pitch }}</span>
               </div>
               <div class="flex items-center gap-2">
                  <Mic class="w-4 h-4" :class="isSynthesizing ? 'text-blue-500 animate-pulse' : 'text-slate-400'" />
                  <span class="text-[12px] text-slate-500">麦克风指示</span>
               </div>
            </div>
         </div>

         <!-- 播放控件 -->
         <div class="col-span-8 bg-slate-900 rounded-2xl p-8 text-white flex flex-col justify-between">
            <div class="flex justify-between items-center">
               <span class="text-[14px] font-bold">播放器</span>
               <a v-if="currentAudioUrl" 
                  :href="currentAudioUrl" 
                  :download="'synthesized_' + Date.now() + '.wav'"
                  class="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-[12px] font-bold transition-all"
                  title="下载合成的音频文件"
               >
                  <Download class="w-3.5 h-3.5" />
                  <span>下载工程文件</span>
               </a>
            </div>
            
            <audio ref="playerRef" :src="currentAudioUrl" @timeupdate="currentTime = playerRef?.currentTime || 0; duration = playerRef?.duration || 0" @play="isPlaying = true" @pause="isPlaying = false" class="hidden"></audio>
            
            <div class="mt-6 space-y-4">
               <input type="range" :value="currentTime" :max="duration" @input="playerRef!.currentTime = parseFloat(($event.target as HTMLInputElement).value)" class="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500" />
               <div class="flex items-center justify-center gap-6">
                  <button @click="playerRef!.currentTime -= 5" class="text-slate-400 hover:text-white"><Rewind class="w-5 h-5"/></button>
                  <button @click="togglePlay" class="w-12 h-12 rounded-full bg-white text-slate-900 flex items-center justify-center">
                      <Pause v-if="isPlaying" /><Play v-else class="translate-x-0.5" />
                  </button>
                  <button @click="playerRef!.currentTime += 5" class="text-slate-400 hover:text-white"><FastForward class="w-5 h-5"/></button>
               </div>
            </div>
         </div>
      </section>

      <!-- 核心输入区 -->
      <section class="grid grid-cols-12 gap-8">
         <div class="col-span-12 space-y-6">
            <div class="space-y-2">
               <label class="text-[14px] font-bold text-slate-800 flex items-center justify-between">
                  语料
                  <label class="text-[12px] font-normal text-blue-600 cursor-pointer hover:underline">
                     上传.txt .md文件
                     <input type="file" class="hidden" accept=".txt,.md" @change="handleFileUpload">
                  </label>
               </label>
               <textarea v-model="ttsInput" placeholder="输入语料文字..." class="w-full h-64 bg-slate-50 border border-slate-200 rounded-xl p-6 outline-none focus:border-blue-500 transition-colors resize-none text-[16px] leading-relaxed"></textarea>
            </div>
            
            <div class="grid grid-cols-12 gap-4">
               <div class="col-span-10 space-y-2">
                  <label class="text-[14px] font-bold text-slate-800">语气提示</label>
                  <input v-model="instructPrompt" type="text" placeholder="语气自然语言描述..." class="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-4 outline-none focus:border-blue-500 transition-colors" />
               </div>
               <div class="col-span-2 flex items-end">
                  <button @click="performSynthesize" :disabled="isSynthesizing" class="w-full h-[58px] rounded-xl bg-blue-600 text-white font-bold flex items-center justify-center gap-2 hover:bg-blue-700 disabled:bg-slate-300 transition-all shadow-lg active:scale-95">
                     <Activity v-if="isSynthesizing" class="w-4 h-4 animate-spin" />
                     {{ isSynthesizing ? '合成中' : '开始合成' }}
                  </button>
               </div>
            </div>
         </div>
      </section>

    </main>
  </div>
</template>

<style scoped>
::-webkit-scrollbar { display: none; }
</style>
