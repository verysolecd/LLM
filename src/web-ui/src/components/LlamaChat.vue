<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { 
  Cpu,
  RefreshCw,
  LayoutGrid,
  ExternalLink,
  MessageSquare,
  ChevronRight
} from 'lucide-vue-next';
import { LlamaService } from '../api/llama';
import { SystemService } from '../api/system';

const emit = defineEmits(['log']);
const models = ref<string[]>([]);
const selectedModel = ref('');
const activeModels = ref<any[]>([]); // [{ model, port, pid }]
const logs = ref<string[]>([]);
const iframeKey = ref(0);
const logsVisible = ref(false);

let statusTimer: any = null;
let logsTimer: any = null;

// 计算当前选中的模型是否正在运行
const isSelectedRunning = computed(() => {
  return activeModels.value.some(m => m.model === selectedModel.value);
});

// 计算 Iframe 显示的端口（显示最新启动的或默认 8080）
const currentIframePort = computed(() => {
  if (activeModels.value.length > 0) {
    // 默认展示最新启动的模型端口
    return activeModels.value[activeModels.value.length - 1].port;
  }
  return 8080;
});

async function fetchModels() {
  try {
    const res = await LlamaService.getModels();
    models.value = res.data;
    if (models.value.length > 0 && !selectedModel.value) selectedModel.value = models.value[0];
  } catch (e: any) {
    emit('log', '获取模型失败: ' + e.message, 'error');
  }
}

async function fetchStatus() {
  try {
    const res = await LlamaService.getStatus();
    const newActiveList = res.data.running_models || [];
    
    // 如果列表长度增加，重载一次 Iframe 视图
    if (newActiveList.length > activeModels.value.length) {
      setTimeout(() => { iframeKey.value++; }, 1000);
    }
    activeModels.value = newActiveList;
  } catch (e) {}
}

async function fetchLogs() {
  try {
    const res = await SystemService.getLogs('llama');
    logs.value = res.data.logs;
    nextTick(() => {
      const el = document.getElementById('log-scroller');
      if (el) el.scrollTop = el.scrollHeight;
    });
  } catch (e) {}
}

async function startSelectedModel() {
  if (!selectedModel.value) return;
  try {
    await LlamaService.start(selectedModel.value);
    emit('log', `尝试启动模型: ${selectedModel.value}`, 'info');
    fetchStatus();
  } catch (e: any) {
    emit('log', '启动失败: ' + e.message, 'error');
  }
}

async function stopModel(modelName: string) {
  try {
    await LlamaService.stop(modelName);
    emit('log', `已停止模型: ${modelName}`, 'warning');
    fetchStatus();
  } catch (e: any) {
    emit('log', '停止失败: ' + e.message, 'error');
  }
}

function refreshChat() {
  iframeKey.value++;
}

onMounted(() => {
  fetchModels();
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
  <div class="flex h-full bg-[#f3f4f6] overflow-hidden">
    
    <!-- 1. LEFT: Configuration (260px) -->
    <div class="w-[260px] shrink-0 border-r border-gray-200 bg-white flex flex-col shadow-sm focus-within:shadow-md transition-shadow">
      <div class="p-4 border-b border-gray-50 flex flex-col justify-center h-16 shrink-0">
        <div class="flex justify-between items-center">
          <h3 class="font-bold text-[14px] flex items-center gap-2 text-gray-800 uppercase tracking-tight">
             <Cpu class="w-4 h-4 text-blue-500" />
             推理模型服务
          </h3>
          <label class="relative inline-flex items-center cursor-pointer">
            <input 
              type="checkbox" 
              :checked="isSelectedRunning" 
              @change="isSelectedRunning ? stopModel(selectedModel) : startSelectedModel()"
              class="sr-only peer"
            >
            <div class="w-10 h-5 bg-gray-200 rounded-full peer-focus:outline-none peer-checked:bg-blue-600 peer-checked:after:translate-x-5 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
          </label>
        </div>
      </div>
      
      <div class="p-5 space-y-6 overflow-y-auto grow no-scrollbar">
        <div class="space-y-4">
           <!-- 并排的刷新与选择 -->
           <div class="flex items-center gap-2">
              <button @click="fetchModels" class="shrink-0 px-2 py-2 border border-dashed border-gray-200 rounded text-[11px] text-gray-500 hover:bg-gray-50 flex items-center justify-center gap-1.5 transition-colors">
                <RefreshCw class="w-3 h-3" /> 刷新
              </button>
              <select v-model="selectedModel" class="flex-1 bg-white border border-gray-200 rounded px-2 py-2 text-[13px] outline-none shadow-sm focus:border-blue-500 transition-all font-medium min-w-0">
                <option value="" disabled>选择模型文件</option>
                <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
              </select>
           </div>

           <!-- 运行中的模型列表 (多行显示) -->
           <div class="space-y-3 mt-4">
              <div v-if="activeModels.length > 0" class="flex items-center justify-between px-1">
                 <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">活跃实例</span>
                 <span class="text-[9px] bg-blue-100 text-blue-600 px-1.5 rounded-full font-bold">{{ activeModels.length }}</span>
              </div>

              <!-- 活跃卡片循环 -->
              <div v-for="m in activeModels" :key="m.model" class="p-3 bg-red-50/50 border border-red-100 rounded-lg space-y-3 animate-in slide-in-from-top-1 duration-300">
                 <div class="border-t border-red-200/30"></div>
                 
                 <div class="flex items-center gap-3">
                    <div class="flex-1 text-[12px] font-bold text-gray-800 break-words whitespace-normal leading-snug">
                       {{ m.model }}
                       <div class="text-[9px] font-mono text-gray-400 mt-0.5">Port: {{ m.port }}</div>
                    </div>
                    
                    <div class="flex items-center gap-2 shrink-0">
                       <span class="text-[9px] text-green-600 bg-green-50 border border-green-100 px-1.5 py-0.5 rounded font-bold uppercase tracking-tighter shrink-0 animate-pulse">运行中</span>
                       <button 
                         @click="stopModel(m.model)" 
                         title="停止该服务"
                         class="w-4 h-4 bg-blue-500 hover:bg-blue-600 active:scale-90 transition-all shadow-sm rounded-sm"
                       ></button>
                    </div>
                 </div>
              </div>

              <div v-if="activeModels.length === 0" class="py-10 text-center px-4">
                 <Cpu class="w-10 h-10 text-gray-100 mx-auto mb-2" />
                 <p class="text-[11px] text-gray-300 italic">暂无活跃模型服务</p>
              </div>
           </div>
        </div>
      </div>
    </div>

    <!-- 2. MIDDLE: Native Chat (Flex-1) -->
    <div class="flex-1 flex flex-col bg-gray-50 relative min-w-0">
       <div class="h-16 border-b border-gray-200 bg-white px-6 flex items-center justify-between z-10 shadow-sm">
          <div class="flex items-center gap-3">
             <MessageSquare class="w-4 h-4 text-gray-400" />
             <span class="font-bold text-[14px] text-gray-800">推理对话</span>
             <a 
               :href="'http://127.0.0.1:' + currentIframePort" 
               target="_blank" 
               class="text-[11px] font-mono text-blue-500 hover:text-blue-700 underline decoration-blue-200 underline-offset-1 flex items-center gap-0.5 transition-all mt-0.5"
             >
                127.0.0.1:{{ currentIframePort }}
                <ExternalLink class="w-2.5 h-2.5" />
             </a>
          </div>
          
          <div v-if="activeModels.length > 0" class="flex items-center gap-4">
             <div class="px-2 py-1 bg-gray-100 rounded text-[9px] font-mono text-gray-500 flex items-center gap-1.5">
                <div class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                127.0.0.1:{{ currentIframePort }}
             </div>
             <button @click="refreshChat" class="text-[11px] font-bold text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-all">
                <RefreshCw class="w-3 h-3" /> 重载
             </button>
             <a :href="'http://127.0.0.1:' + currentIframePort" target="_blank" class="text-[11px] font-bold text-gray-500 hover:text-blue-600 flex items-center gap-1 transition-all">
                <ExternalLink class="w-3 h-3" /> 外部打开
             </a>
          </div>
       </div>

       <div class="flex-1 relative overflow-hidden bg-white">
          <div v-if="activeModels.length === 0" class="absolute inset-0 flex flex-col items-center justify-center text-gray-300 pointer-events-none select-none z-0">
             <div class="relative mb-6">
                <Cpu class="w-24 h-24 opacity-5" stroke-width="1" />
                <div class="absolute inset-0 flex items-center justify-center">
                   <div class="w-12 h-12 border-2 border-dashed border-gray-100 rounded-full animate-spin"></div>
                </div>
             </div>
             <p class="text-[12px] tracking-widest text-gray-400 uppercase font-light">模型就绪后载入界面</p>
          </div>

          <iframe 
            v-if="activeModels.length > 0"
            :key="iframeKey"
            :src="'http://127.0.0.1:' + currentIframePort"
            class="w-full h-full bg-white relative z-10"
            frameborder="0"
          ></iframe>
       </div>
    </div>

    <!-- 3. RIGHT: Logs (Collapsible, 320px) -->
    <div 
      :style="{ width: logsVisible ? '340px' : '40px' }" 
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
        <h3 v-if="logsVisible" class="font-bold text-[14px] text-gray-800 flex items-center gap-2">
           <LayoutGrid class="w-4 h-4 text-gray-400" />
           实时日志
        </h3>
        <button v-if="logsVisible" @click="logs = []" class="text-[11px] text-gray-400 hover:text-red-500 ml-auto font-bold uppercase tracking-tighter">Clear</button>
      </div>

      <div v-show="logsVisible" id="log-scroller" class="flex-1 p-4 overflow-y-auto bg-gray-900 font-mono text-[10px] leading-relaxed select-text no-scrollbar scroll-smooth">
          <div v-for="(log, idx) in logs" :key="idx" class="mb-1 text-gray-300 break-words opacity-80 hover:opacity-100 border-b border-gray-800/10 pb-1">
             <span class="text-blue-500 mr-2">»</span>{{ log }}
          </div>
          <div v-if="logs.length === 0" class="text-gray-600 italic text-center mt-20">
             等待引擎初始化...
          </div>
      </div>

      <div v-if="!logsVisible" class="flex-1 flex flex-col items-center pt-10 text-[10px] text-gray-300 font-bold uppercase tracking-widest pointer-events-none [writing-mode:vertical-lr] gap-4">
         <span>ENGINE LOGS</span>
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
