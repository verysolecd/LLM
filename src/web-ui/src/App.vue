<script setup lang="ts">
import { ref, defineAsyncComponent, onMounted } from 'vue';
import { 
  Mic2, 
  Download, 
  ChevronLeft,
  ChevronRight,
  Settings,
  Plug,
  User,
  Link,
  Globe,
  Volume2
} from 'lucide-vue-next';

// 动态载入组件
const LlamaChat = defineAsyncComponent(() => import('./components/LlamaChat.vue'));
const AudioCenter = defineAsyncComponent(() => import('./components/AudioCenter.vue'));
const DownloadCenter = defineAsyncComponent(() => import('./components/DownloadCenter.vue'));
const TTSCenter = defineAsyncComponent(() => import('./components/TTSCenter.vue'));
const TTSQwen = defineAsyncComponent(() => import('./components/TTSQwen.vue'));

const currentView = ref('llama');
const sidebarCollapsed = ref(false);
const logsVisible = ref(true);
const logs = ref<{ type: string; msg: string; time: string }[]>([]);

// 侧边栏分组定义
const navGroups = [
  {
    title: '',
    items: [
      { id: 'llama', name: '推理模型', icon: Settings },
      { id: 'audio', name: '语音模型', icon: Mic2 },
      { id: 'tts', name: '语音合成', icon: Volume2 },
      { id: 'tts-qwen', name: 'Qwen 语音合成', icon: Volume2 },
      { id: 'download', name: '下载模型', icon: Download },
      { id: 'api', name: 'API 扩展', icon: Plug },
    ]
  },
  {
    title: '账户',
    items: [
      { id: 'integrated', name: '集成', icon: Link },
      { id: 'language', name: '语言', icon: Globe },
    ]
  }
];

function addLog(msg: string, type: 'info' | 'error' | 'success' = 'info') {
  logs.value.push({
    msg,
    type,
    time: new Date().toLocaleTimeString(),
  });
  // 保持最新
  setTimeout(() => {
    const el = document.getElementById('log-scroller');
    if (el) el.scrollTop = el.scrollHeight;
  }, 50);
}

onMounted(() => {
  addLog('Web-UI 系统环境就绪', 'success');
});
</script>

<template>
  <div class="flex h-screen w-screen bg-[#f3f4f6] text-gray-900 overflow-hidden font-sans">
    <!-- Sidebar -->
    <aside 
      :style="{ width: sidebarCollapsed ? '64px' : '240px' }"
      class="flex flex-col bg-white border-r border-gray-200 transition-all duration-300 z-50 shadow-sm"
    >
      <div class="p-4 h-16 flex items-center justify-between">
        <span v-if="!sidebarCollapsed" class="font-bold text-lg text-gray-800">工作空间</span>
        <button 
          @click="sidebarCollapsed = !sidebarCollapsed"
          class="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 transition-colors"
        >
          <ChevronLeft v-if="!sidebarCollapsed" class="w-5 h-5" />
          <ChevronRight v-else class="w-5 h-5" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-3 py-2">
        <template v-for="group in navGroups" :key="group.title">
          <div v-if="!sidebarCollapsed" class="mt-6 mb-2 px-3 text-[12px] font-bold text-gray-400 uppercase tracking-wider">
            {{ group.title }}
          </div>
          
          <div class="space-y-0.5">
            <button 
              v-for="item in group.items" 
              :key="item.id"
              @click="currentView = item.id"
              :class="[
                currentView === item.id 
                  ? 'bg-blue-50 text-blue-600' 
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              ]"
              class="w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm font-medium"
            >
              <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
              <span v-if="!sidebarCollapsed">{{ item.name }}</span>
            </button>
          </div>
        </template>
      </div>

      <div class="p-4 border-t border-gray-100">
        <button class="w-full flex items-center gap-3 px-3 py-2 rounded-md text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-all text-sm font-medium">
           <User class="w-5 h-5 flex-shrink-0" />
           <span v-if="!sidebarCollapsed">账户概览</span>
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 flex flex-col relative min-w-0">
      <div class="flex-1 overflow-hidden">
        <KeepAlive>
          <component 
            :is="currentView === 'llama' ? LlamaChat : (currentView === 'audio' ? AudioCenter : (currentView === 'tts' ? TTSCenter : (currentView === 'tts-qwen' ? TTSQwen : DownloadCenter)))" 
            class="h-full w-full"
            @log="addLog"
          />
        </KeepAlive>
      </div>

      <!-- Floating Log Panel (Hidden in TTS mode) -->
      <transition enter-active-class="transition duration-300 ease-out" enter-from-class="translate-y-full opacity-0" enter-to-class="translate-y-0 opacity-100" leave-active-class="transition duration-200 ease-in" leave-from-class="translate-y-0 opacity-100" leave-to-class="translate-y-full opacity-0">
        <div v-if="logsVisible && currentView !== 'tts' && currentView !== 'tts-qwen'" class="absolute bottom-6 right-6 w-96 max-h-64 bg-slate-900/90 backdrop-blur-xl border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden z-40">
           <div class="p-3 border-b border-slate-700 flex justify-between items-center text-xs font-bold uppercase tracking-wider bg-slate-800/50">
             <div class="flex items-center gap-2">
               <Terminal class="w-3 h-3 text-indigo-400" />
               <span>系统日志</span>
             </div>
             <button @click="logsVisible = false" class="text-slate-500 hover:text-white">✕</button>
           </div>
           <div id="log-scroller" class="flex-1 overflow-y-auto p-3 text-[11px] font-mono space-y-1 bg-black/20">
             <div v-for="(log, i) in logs" :key="i" class="flex gap-2">
               <span class="text-slate-600 flex-shrink-0">[{{ log.time }}]</span>
               <span :class="{ 'text-emerald-400': log.type === 'success', 'text-rose-400': log.type === 'error', 'text-indigo-400': log.type === 'info' }">
                 {{ log.msg }}
               </span>
             </div>
             <div v-if="logs.length === 0" class="text-slate-700 italic">等待系统日志...</div>
           </div>
        </div>
      </transition>
    </main>
  </div>
</template>

<style>
/* 滚动条美化 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: #475569;
}
</style>
