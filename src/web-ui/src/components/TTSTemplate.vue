<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { Mic, Settings, Save, Play, Download, Activity, AudioLines, Trash2, Square, Sparkles, History } from 'lucide-vue-next';
import { TTSService, WhisperService } from '../api/audio';

const emit = defineEmits(['log']);

// --- 状态 ---
const availableModels = ref<any[]>([]);
const whisperModels = ref<string[]>([]);
const selectedWhisperModel = ref('whisper_large.bin');
const selectedModelId = ref('');
const isServiceRunning = ref(false);
const isPending = ref(false);

const ttsPresets = ref<string[]>([]);
const clonedVoices = ref<any[]>([]);
const selectedSpeaker = ref('');
const enablePresetVoices = ref(false); // 预设音色总开关

// 合成历史记录 (从服务器获取)
const synthesisHistory = ref<Array<{id: string, url: string, text: string, timestamp: number, duration?: number}>>([]);

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

const ttsInput = ref('');
const instructPrompt = ref('');
const refAudioPath = ref('');
const refAudioUrl = ref('');
const refText = ref('');
const saveVoiceName = ref('');
const useRecordedVoice = ref(false); // 是否直接使用当前录音进行合成

const isSynthesizing = ref(false);
const isSavingVoice = ref(false);

const formatTime = (s: number) => {
  const mins = Math.floor(s / 60);
  const secs = Math.floor(s % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

// --- 初始化 ---
async function init() {
  try {
    await refreshSynthesisHistory(); // 加载历史记录
    const modelRes = await TTSService.getModels();
    availableModels.value = modelRes.data;
    if (availableModels.value.length > 0) {
      selectedModelId.value = availableModels.value[0].id;
      checkStatus();
    }
    
    refreshVoiceLibrary();
    
    // 拉取 Whisper 模型供识别使用
    const whisperRes = await WhisperService.getModels();
    whisperModels.value = whisperRes.data;
    // 优先保留 whisper_large.bin 
    if (!whisperModels.value.includes('whisper_large.bin') && whisperModels.value.length > 0) {
      selectedWhisperModel.value = whisperModels.value[0];
    }
    // 监听服务状态变化
    setInterval(checkStatus, 5000);
  } catch (e) {
    console.error('Initialization failed:', e);
  }
}

// 刷新合成历史
async function refreshSynthesisHistory() {
  try {
    const res = await TTSService.getSynthesisHistory();
    if (res.data && res.data.status === 'success') {
      synthesisHistory.value = res.data.data;
      
      // 预加载所有音频的时长
      synthesisHistory.value.forEach(item => {
        const audio = new Audio(item.url);
        audio.addEventListener('loadedmetadata', () => {
          item.duration = audio.duration;
        });
      });
    }
  } catch (e) {
    console.error('Failed to refresh synthesis history:', e);
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
  
  if (!selectedSpeaker.value && !refAudioPath.value) {
    alert('【操作引导】Faster Qwen3-TTS 需要一个参考音色。请在下方「选择音色」或在左侧「音色实时采集」录制一段声音。');
    return;
  }

  isSynthesizing.value = true;
  try {
    let finalSpeaker = selectedSpeaker.value;
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
      await refreshSynthesisHistory();
    } else {
      throw new Error('Backend failed to return audio URL');
    }
  } catch (e: any) {
    alert('合成失败: ' + (e.response?.data?.detail || e.message));
  } finally {
    isSynthesizing.value = false;
  }
}

async function deleteSynthesis(id: string) {
  const item = synthesisHistory.value.find(item => item.id === id);
  if (item) {
    try {
      const filename = item.url.split('/').pop();
      if (filename) {
        await TTSService.deleteSynthesis(filename);
      }
    } catch (e) {
      console.error('Failed to delete synthesis file:', e);
    }
  }
  await refreshSynthesisHistory();
}

function playSynthesis(url: string) {
  const audio = new Audio(url);
  audio.play();
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
    await refreshVoiceLibrary();
    saveVoiceName.value = '';
    refAudioPath.value = '';
    refAudioUrl.value = '';
    useRecordedVoice.value = false;
    refText.value = '';
  } catch (e: any) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message));
  } finally {
    isSavingVoice.value = false;
  }
}

onMounted(init);
watch(selectedModelId, checkStatus);
</script>

<template>
  <div class="flex h-full bg-white overflow-hidden">
    
    <!-- 侧边栏：控制 & 音色管理 -->
    <aside class="md:w-[280px] w-60 bg-white border-r border-slate-200 flex flex-col shadow-sm z-10 overflow-y-auto no-scrollbar transition-all duration-300">
      <div class="p-4">
        <!-- 服务配置标题 -->
        <div class="flex items-center gap-2 mb-4">
           <Settings class="w-4 h-4 text-slate-400" />
           <h3 class="text-[14px] font-bold text-slate-700">模型服务配置 (模板)</h3>
        </div>
        
        <!-- 服务配置内容 -->
        <div class="space-y-3 mb-6">
           <select v-model="selectedModelId" class="w-full bg-white border border-slate-200 rounded-lg px-4 py-2 text-[14px] outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="" disabled selected>-- 请选择模型 --</option>
              <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
          <div class="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
              <span class="text-[12px] text-slate-500 font-bold uppercase tracking-tight">{{ isServiceRunning ? '运行中' : '已停止' }}</span>
              <label class="relative inline-flex items-center cursor-pointer scale-75">
                 <input type="checkbox" :checked="isServiceRunning" @change="toggleService" class="sr-only peer" :disabled="isPending">
                 <div class="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-blue-600 peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
          </div>
        </div>

        <!-- 音色实时克隆 -->
        <div class="space-y-3 bg-white rounded-xl shadow-sm p-4">
          <div class="flex items-center justify-between group">
             <div class="flex items-center gap-2">
                <Mic class="w-4 h-4 text-blue-500" />
                <h3 class="text-[14px] font-bold text-slate-700">音色实时采集</h3>
             </div>
              
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
             <div class="flex items-center justify-between px-1">
                <div class="flex items-center gap-2">
                   <div class="w-1.5 h-1.5 rounded-full" :class="isRecording ? 'bg-red-500 animate-pulse' : (refAudioPath ? 'bg-green-500' : 'bg-gray-300')"></div>
                   <span class="text-[11px] font-mono text-slate-500">{{ isRecording ? 'RECORDING' : (refAudioPath ? 'READY' : 'IDLE') }}</span>
                   <span class="text-[11px] font-mono text-slate-400">/ {{ formatTime(recordingTime) }}</span>
                </div>
                <div class="flex items-center gap-2">
                    <button 
                      v-if="refAudioPath && !isRecording"
                      @click="playRefAudio" 
                      class="flex items-center justify-center p-1.5 bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-600 rounded transition-colors"
                    >
                       <Activity v-if="isPlayingRef" class="w-3.5 h-3.5 text-blue-500 animate-pulse" />
                       <Play v-else class="w-3.5 h-3.5" />
                    </button>

                    <button 
                      v-if="refAudioPath && !isRecording"
                      @click="performRecognition" 
                      :disabled="isRecognizing"
                      class="flex items-center gap-1.5 px-2 py-1 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-600 rounded text-[10px] font-bold transition-colors disabled:opacity-50"
                    >
                       <Activity v-if="isRecognizing" class="w-3 h-3 animate-spin" />
                       <Sparkles v-else class="w-3 h-3" />
                       <span>{{ isRecognizing ? '识别中...' : '智能识别' }}</span>
                    </button>
                </div>
             </div>

             <div class="space-y-2 pt-1">
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
                  >
                     <Activity v-if="isSavingVoice" class="w-4 h-4 animate-spin" />
                     <Save v-else class="w-4 h-4" />
                  </button>
                </div>
                
                <div v-if="refAudioPath && !isRecording" class="flex items-center gap-2 py-1 px-1 bg-blue-50/50 rounded-lg border border-blue-100">
                  <input type="checkbox" v-model="useRecordedVoice" class="w-3 h-3 accent-blue-600" id="use-rec-cb" />
                  <label for="use-rec-cb" class="text-[11px] font-bold text-blue-600 cursor-pointer">使用当前录音作为克隆音色</label>
                </div>
             </div>
          </div>
        </div>

        <!-- 音色库 -->
        <div class="space-y-4 bg-white rounded-xl shadow-sm p-4">
           <div class="flex items-center gap-2 mb-2">
              <AudioLines class="w-4 h-4 text-slate-400" />
              <h3 class="text-[14px] font-bold text-slate-700">选择音色</h3>
           </div>
           
           <div class="space-y-6">
              <div class="space-y-2">
                 <div class="text-[11px] font-bold text-slate-400 flex items-center gap-2">
                    <AudioLines class="w-3 h-3" /> 我的个人音色
                 </div>
                 <div class="grid grid-cols-1 gap-2">
                    <div v-if="clonedVoices.length === 0" class="text-[11px] text-slate-400 bg-slate-50 p-3 rounded-lg border border-dashed text-center italic">暂无克隆记录</div>
                    <div 
                       v-for="c in clonedVoices" :key="c.id"
                       @click="selectedSpeaker = c.name"
                       class="px-3 py-2 rounded-lg border flex items-center justify-between cursor-pointer transition-all"
                       :class="selectedSpeaker === c.name ? 'bg-blue-600 border-blue-600 text-white shadow-sm' : 'bg-white border-slate-200 hover:border-blue-300 text-slate-700'"
                     >
                        <span class="text-[12px] font-medium truncate">{{ c.name }}</span>
                        <Trash2 @click.stop="TTSService.deleteVoice(c.id).then(refreshVoiceLibrary)" class="w-3 h-3 text-slate-300 hover:text-red-500" />
                     </div>
                 </div>
              </div>

              <div class="space-y-2">
                 <div class="flex items-center justify-between">
                    <div class="text-[11px] font-bold text-slate-400 flex items-center gap-2">
                       <AudioLines class="w-3 h-3" /> 系统核心音色
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer scale-75">
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

    <!-- 管理页面 -->
    <main class="flex-1 flex flex-col gap-6 overflow-y-auto bg-[#f8fafc]">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-0 min-h-full">
        <!-- 合成区域 -->
        <section class="space-y-4 border-r border-slate-200 pr-2 h-full bg-white rounded-xl shadow-sm p-4 mt-0">
          <div class="flex items-center gap-2 mb-2">
             <Settings class="w-4 h-4 text-slate-400" />
             <h2 class="text-[14px] font-bold text-slate-700">TTS 语音合成 (通用模板)</h2>
          </div>
          
          <div class="flex items-center justify-between">
             <div class="flex gap-2">
                <input type="file" @change="handleFileUpload" accept=".txt" class="hidden" id="file-upload" />
                <label for="file-upload" class="px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-100 cursor-pointer transition-colors text-sm font-medium text-slate-700">
                  加载文本
                </label>
              </div>
          </div>

          <textarea 
            v-model="ttsInput" 
            placeholder="请输入要合成的文本..."
            class="w-full bg-white border border-slate-200 rounded-xl p-4 text-[14px] h-48 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all resize-none leading-relaxed"
          ></textarea>

          <div class="grid grid-cols-12 gap-6">
             <div class="col-span-8 space-y-2">
                <label class="text-[12px] font-bold text-slate-500 uppercase tracking-tight">情绪指令 (可选)</label>
                <input 
                  v-model="instructPrompt" 
                  placeholder="例如：温柔、开心、悲伤、严肃..."
                  class="w-full bg-white border border-slate-200 rounded-lg px-4 py-2 text-[14px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
                />
             </div>

             <div class="col-span-4 space-y-2">
                <label class="text-[12px] font-bold text-slate-500 uppercase tracking-tight">当前音色</label>
                <div class="bg-white border border-slate-200 rounded-lg px-4 py-2 text-[14px]">
                   {{ selectedSpeaker || '未选择' }}
                </div>
             </div>
          </div>

          <div class="space-y-4">
             <button 
               @click="performSynthesize" 
               :disabled="!ttsInput || !isServiceRunning || isSynthesizing"
               class="w-full bg-blue-600 text-white rounded-lg px-6 py-3 hover:bg-blue-700 transition-colors disabled:bg-slate-300 disabled:text-slate-500 font-medium text-lg shadow-md flex items-center justify-center gap-2"
             >
               <Activity v-if="isSynthesizing" class="w-5 h-5 animate-spin" />
               <AudioLines v-else class="w-5 h-5" />
               <span>{{ isSynthesizing ? '合成中...' : '开始合成' }}</span>
             </button>
          </div>
        </section>
        
        <!-- 合成历史 -->
        <section class="space-y-4 h-full bg-white rounded-xl shadow-sm p-4 mt-0">
          <div class="flex items-center gap-2 mb-2">
             <History class="w-4 h-4 text-slate-400" />
             <h3 class="text-[14px] font-bold text-slate-700">合成历史</h3>
          </div>
          
          <div class="space-y-3">
            <div v-if="synthesisHistory.length === 0" class="text-center py-12 text-slate-400">
              <AudioLines class="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p class="text-lg">暂无合成记录</p>
              <p class="text-sm mt-2">点击"开始合成"按钮生成音频</p>
            </div>
            
            <div v-for="item in synthesisHistory" :key="item.id" class="flex items-center justify-between bg-white border border-slate-200 rounded-xl p-3 shadow-sm">
               <div class="flex items-center gap-3 flex-1">
                  <div class="flex items-center gap-2">
                     <History class="w-4 h-4 text-slate-400" />
                     <span class="text-xs text-slate-500 font-mono">
                       {{ new Date(item.timestamp).toLocaleString() }}
                     </span>
                     <button 
                        @click="playSynthesis(item.url)"
                        class="text-blue-600 hover:text-blue-800 transition-colors"
                     >
                        <Play class="w-4 h-4" />
                     </button>
                  </div>
                  
                  <div class="flex-1 min-w-0">
                     <div class="flex items-center justify-between">
                        <p class="text-sm font-medium text-slate-800 truncate">{{ item.text }}</p>
                        <span class="text-xs text-slate-400 ml-2">{{ item.duration ? formatTime(item.duration) : '--:--' }}</span>
                     </div>
                  </div>
               </div>
               
               <div class="flex items-center gap-3">
                  <a 
                     :href="item.url" 
                     :download="'synthesized_' + item.id + '.wav'"
                     class="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-[12px] font-medium text-slate-700 transition-colors"
                  >
                     <Download class="w-3.5 h-3.5" />
                     下载
                  </a>
                  
                  <button 
                     @click="deleteSynthesis(item.id)"
                     class="w-10 h-10 bg-red-50 text-red-600 rounded-full flex items-center justify-center hover:bg-red-100 transition-colors"
                  >
                     <Trash2 class="w-4 h-4" />
                  </button>
               </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
