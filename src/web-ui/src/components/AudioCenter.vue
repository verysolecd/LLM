<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { 
  Mic2, 
  RefreshCw, 
  Terminal,
  Activity,
  Zap,
  ChevronRight,
  ChevronLeft,
  LayoutGrid,
  MessageSquare,
  Cpu,
  Settings2
} from 'lucide-vue-next';
import { WhisperService } from '../api/audio';
import { SystemService } from '../api/system';

const emit = defineEmits(['log']);

// Whisper State
const whisperTools = ref<any[]>([
  { name: 'whisper-server', desc: '核心 API 服务', port: 8081, running: false },
  { name: 'whisper-stream', desc: '实时语音识别', port: 8082, running: false },
  { name: 'whisper-cli', desc: '命令行转写工具', port: 8083, running: false },
  { name: 'whisper-command', desc: '轻量命令监听', port: 8084, running: false }
]);
const whisperModels = ref<string[]>([]);
const selectedWhisperModel = ref('');
const isRefreshing = ref(false);
const logs = ref<string[]>([]);
const logsVisible = ref(false);

let statusTimer: any = null;
let logsTimer: any = null;

const isServerRunning = computed(() => {
  return whisperTools.value.find(t => t.name === 'whisper-server')?.running;
});

const isCommandRunning = computed(() => {
  return whisperTools.value.find(t => t.name === 'whisper-command')?.running;
});

async function fetchInitialData() {
  isRefreshing.value = true;
  try {
    const modelsRes = await WhisperService.getModels();
    whisperModels.value = modelsRes.data;
    if (whisperModels.value.length > 0 && !selectedWhisperModel.value) {
      selectedWhisperModel.value = whisperModels.value[0];
    }
  } catch (e) {} finally {
    isRefreshing.value = false;
  }
}

async function fetchStatus() {
  try {
    const res = await WhisperService.getTools();
    const remoteTools = res.data.tools || [];
    whisperTools.value = whisperTools.value.map(local => {
      const match = remoteTools.find((t: any) => t.name === local.name);
      return { ...local, running: match ? match.running : false };
    });
  } catch (e) {}
}

async function fetchLogs() {
  try {
    const res = await SystemService.getLogs('whisper');
    logs.value = res.data.logs;
    nextTick(() => {
      const el = document.getElementById('audio-log-scroller');
      if (el) el.scrollTop = el.scrollHeight;
    });
  } catch (e) {}
}


async function toggleTool(toolName: string) {
  const tool = whisperTools.value.find(t => t.name === toolName);
  if (!tool) return;
  
  const targetOn = !tool.running;
  try {
    if (targetOn) {
      if (!selectedWhisperModel.value) {
        alert('请先选择 Whisper 模型');
        return;
      }
      await WhisperService.startTool(toolName, selectedWhisperModel.value);
      emit('log', `启动工具: ${toolName}`, 'info');
    } else {
      await WhisperService.stopTool(toolName);
      emit('log', `停止工具: ${toolName}`, 'warning');
    }
    fetchStatus();
  } catch (e: any) {
    emit('log', '操作失败: ' + e.message, 'error');
  }
}

onMounted(() => {
  fetchInitialData();
  fetchStatus();
  fetchLogs();
  statusTimer = setInterval(fetchStatus, 3000);
  logsTimer = setInterval(fetchLogs, 2000);
});

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer);
  if (logsTimer) clearInterval(logsTimer);
});
</script>

<template>
  <div class="flex h-full bg-[#f3f4f6] overflow-hidden p-6 gap-6">
    
    <!-- 1. LEFT: Service Library (300px) -->
    <div class="w-[300px] shrink-0 flex flex-col gap-5 overflow-y-auto no-scrollbar pr-1">
      <div class="flex items-center gap-2 mb-2 px-1">
        <Mic2 class="w-5 h-5 text-gray-800" />
        <h2 class="font-bold text-[15px] text-gray-800 uppercase tracking-tight">服务状态库</h2>
      </div>

      <div class="space-y-4">
        <div class="bg-white p-4 rounded-lg border border-gray-200 shadow-sm space-y-3">
          <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-widest">全局模型选择</label>
          <div class="flex gap-2">
             <button @click="fetchInitialData" class="shrink-0 w-9 h-9 border border-gray-200 rounded-md flex items-center justify-center hover:bg-gray-50 transition-colors">
                <RefreshCw class="w-4 h-4 text-gray-300" :class="{ 'animate-spin': isRefreshing }" />
             </button>
             <select v-model="selectedWhisperModel" class="flex-1 bg-white border border-gray-200 rounded-md px-3 py-1.5 text-[13px] outline-none focus:border-blue-500 transition-all font-medium shadow-sm">
                <option value="" disabled>-- 选择模型 --</option>
                <option v-for="m in whisperModels" :key="m" :value="m">{{ m }}</option>
             </select>
          </div>
        </div>

        <div 
          v-for="tool in whisperTools" 
          :key="tool.name" 
          class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm transition-all"
          :class="{ 'border-blue-500 bg-blue-50/10': tool.running }"
        >
           <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                 <div class="p-1.5 rounded" :class="tool.running ? 'text-blue-600' : 'text-gray-400'">
                    <Zap v-if="tool.name === 'whisper-server'" class="w-4 h-4" />
                    <Activity v-else-if="tool.name === 'whisper-stream'" class="w-4 h-4" />
                    <Terminal v-else-if="tool.name === 'whisper-cli'" class="w-4 h-4" />
                    <Mic2 v-else class="w-4 h-4" />
                 </div>
                 <div class="text-[14px] font-bold text-gray-800">{{ tool.name }}</div>
              </div>
              <label class="relative inline-flex items-center cursor-pointer scale-90">
                <input type="checkbox" :checked="tool.running" @change="toggleTool(tool.name)" class="sr-only peer">
                <div class="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
              </label>
           </div>
           <div class="text-[12px] text-gray-500 mb-1 leading-tight">{{ tool.desc }}</div>
           <div class="text-[10px] font-mono text-gray-400">Port: {{ tool.port }}</div>
        </div>
      </div>
    </div>

    <!-- 2. MIDDLE: Whisper Control Center (Flex-1) -->
    <div class="flex-1 flex flex-col gap-6 min-w-0">
      <div class="bg-white border border-gray-200 rounded-lg flex flex-col shadow-sm overflow-hidden grow">
        <div class="h-16 px-6 border-b border-gray-100 flex items-center justify-between shrink-0 bg-white">
           <div class="flex items-center gap-3">
              <MessageSquare class="w-4 h-4 text-gray-400" />
              <h2 class="font-bold text-[15px] text-gray-800">Whisper 控制中心</h2>
              <span v-if="isServerRunning" class="text-[9px] bg-green-50 text-green-600 border border-green-100 px-1.5 py-0.5 rounded font-bold uppercase tracking-tight">服务端运行中</span>
           </div>

           <div class="flex items-center gap-4">
              <div class="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded border border-gray-100">
                 <span class="text-[11px] text-gray-600 font-bold uppercase tracking-widest">语音开关</span>
                 <label class="relative inline-flex items-center cursor-pointer scale-75">
                    <input type="checkbox" :checked="isCommandRunning" @change="toggleTool('whisper-command')" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4"></div>
                 </label>
              </div>
           </div>
        </div>

        <div class="p-6 grow flex flex-col bg-white">
           <!-- Content when server is off -->
           <div v-if="!isServerRunning" class="flex-1 flex flex-col items-center justify-center text-center space-y-4">
              <Cpu class="w-12 h-12 text-gray-100 mb-2" />
              <div class="max-w-md space-y-1">
                 <h3 class="text-[16px] font-bold text-gray-800">启动服务端激活指令映射</h3>
                 <p class="text-[12px] text-gray-400">服务端开启后，即可配置语音关键词与后台服务的自动联动功能。</p>
              </div>
              <button @click="toggleTool('whisper-server')" class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-bold text-[13px] shadow-sm transition-all active:scale-95">
                 立即启动服务端 (8081)
              </button>
           </div>

           <!-- Content when server is on -->
           <div v-else class="flex-1 flex flex-col gap-6">
              <div class="grid grid-cols-2 gap-4">
                 <div class="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:border-blue-400 transition-all cursor-pointer group">
                    <div class="flex items-center justify-between mb-3">
                       <Activity class="w-5 h-5 text-blue-500" />
                       <span class="text-[10px] text-gray-400 font-bold uppercase tracking-widest italic">REAL-TIME</span>
                    </div>
                    <h4 class="font-bold text-[14px] text-gray-800">开始实时录音识别</h4>
                    <p class="text-[11px] text-gray-500 mt-1">启动本地语音流转文本识别服务</p>
                 </div>
                 <div class="bg-gray-50 border border-gray-200 rounded-lg p-5 hover:border-blue-400 transition-all cursor-pointer group">
                    <div class="flex items-center justify-between mb-3">
                       <Download class="w-5 h-5 text-blue-500" />
                       <span class="text-[10px] text-gray-400 font-bold uppercase tracking-widest italic">FILE-PROC</span>
                    </div>
                    <h4 class="font-bold text-[14px] text-gray-800">批量音频文件转写</h4>
                    <p class="text-[11px] text-gray-500 mt-1">使用 whisper-cli 进行本地离线解析</p>
                 </div>
              </div>

              <div class="bg-white border border-gray-200 rounded-lg p-5 grow">
                 <h4 class="font-bold text-[13px] text-gray-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Settings2 class="w-4 h-4" />
                    自定义语音指令映射
                 </h4>
                 <div class="space-y-2">
                    <div v-for="i in 3" :key="i" class="flex items-center gap-2 p-2 px-3 border border-gray-100 rounded bg-gray-50/50">
                       <input type="text" placeholder="语音关键词" class="w-32 bg-white border border-gray-200 rounded px-2 py-1 text-[12px] outline-none" />
                       <ChevronRight class="w-3 h-3 text-gray-300" />
                       <select class="flex-1 bg-white border border-gray-200 rounded px-2 py-1 text-[12px] outline-none">
                          <option>执行：启动聊天对话</option>
                          <option>执行：停止录音进程</option>
                          <option>执行：清空历史会话</option>
                       </select>
                       <button class="text-gray-300 hover:text-red-500 px-1 text-lg">×</button>
                    </div>
                    <button class="w-full py-2 border border-dashed border-gray-200 rounded text-[11px] text-gray-400 hover:text-blue-500 hover:border-blue-300 transition-all font-bold">
                       + 添加指令映射
                    </button>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>

    <!-- 3. RIGHT: Logs (Collapsible, 300px) -->
    <div 
      :style="{ width: logsVisible ? '300px' : '40px' }" 
      class="shrink-0 border-l border-gray-200 bg-white flex flex-col transition-all duration-300 relative shadow-[-4px_0_10px_rgba(0,0,0,0.02)]"
    >
      <button 
        @click="logsVisible = !logsVisible" 
        class="absolute -left-3 top-1/2 -translate-y-1/2 w-6 h-6 bg-white border border-gray-200 rounded-full flex items-center justify-center shadow-md text-gray-400 hover:text-blue-500 z-20 group transition-all"
      >
        <ChevronRight v-if="!logsVisible" class="w-4 h-4 group-hover:scale-110" />
        <ChevronLeft v-else class="w-4 h-4 group-hover:scale-110" />
      </button>

      <div class="h-16 border-b border-gray-50 px-4 flex items-center justify-between shrink-0 overflow-hidden whitespace-nowrap">
        <h3 v-if="logsVisible" class="font-bold text-[13px] text-gray-800 flex items-center gap-2 uppercase tracking-widest">
           <LayoutGrid class="w-4 h-4 text-gray-400" />
           系统日志
        </h3>
        <button v-if="logsVisible" @click="logs = []" class="text-[10px] text-gray-400 hover:text-red-500 ml-auto font-bold uppercase tracking-tighter">Clear</button>
      </div>

      <div v-show="logsVisible" id="audio-log-scroller" class="flex-1 p-4 overflow-y-auto bg-gray-50 font-mono text-[10px] leading-relaxed no-scrollbar scroll-smooth">
          <div v-for="(log, idx) in logs" :key="idx" class="mb-1 text-gray-600 border-b border-gray-200/50 pb-1">
             <span class="text-blue-500 mr-2 opacity-50 font-bold">»</span>{{ log }}
          </div>
          <div v-if="logs.length === 0" class="text-gray-400 italic text-center mt-20 select-none">
             等待输出...
          </div>
      </div>

      <div v-if="!logsVisible" class="flex-1 flex flex-col items-center pt-10 text-[10px] text-gray-300 font-bold uppercase tracking-widest pointer-events-none [writing-mode:vertical-lr] gap-4">
         <span>SYSTEM LOGS</span>
         <div class="w-[1px] h-20 bg-gray-100"></div>
      </div>
    </div>
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
