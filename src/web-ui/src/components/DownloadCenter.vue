<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { 
  Search, 
  CloudDownload,
  Loader2,
  CheckCircle2,
  XCircle
} from 'lucide-vue-next';
import { DownloadService } from '../api/download';

const emit = defineEmits(['log']);
const repoId = ref('');
const fileName = ref('');
const isDownloading = ref(false);
const activeDownloads = ref<any>({});
let statusTimer: any = null;

async function fetchStatus() {
  try {
    const res = await DownloadService.getStatus();
    activeDownloads.value = res.data;
  } catch (e) {}
}

async function startDownload() {
  if (!repoId.value.trim()) {
    emit('log', '请输入模型仓库 ID', 'warning');
    return;
  }
  isDownloading.value = true;
  emit('log', `尝试从 ModelScope 下载: ${repoId.value}`, 'info');
  try {
    await DownloadService.download(repoId.value, fileName.value || undefined);
    emit('log', '下载请求已成功发送至后台', 'success');
    fetchStatus();
  } catch (e: any) {
    emit('log', '启动下载失败: ' + e.message, 'error');
  } finally {
    isDownloading.value = false;
  }
}

onMounted(() => {
  fetchStatus();
  statusTimer = setInterval(fetchStatus, 3000);
});

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer);
});
</script>

<template>
  <div class="flex flex-col h-full bg-[#f3f4f6] overflow-hidden">
    <!-- Top Header Config -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4 shadow-sm z-10 shrink-0">
      <div class="flex-1 max-w-[450px]">
        <label class="block text-[12px] text-gray-500 mb-1">输入魔搭 (ModelScope) 模型仓库 ID, 回车搜索 (例: qwen/Qwen1.5-1.8B-Chat-GGUF)</label>
        <div class="flex">
          <input 
            v-model="repoId"
            type="text" 
            placeholder="输入模型库名进行搜索..."
            class="flex-1 border border-gray-300 rounded-l-md px-3 py-1.5 text-[13px] outline-none focus:border-blue-500"
          />
          <button class="bg-blue-600 text-white px-4 rounded-r-md hover:bg-blue-700">
             <Search class="w-4 h-4" />
          </button>
        </div>
      </div>

      <div class="flex-1 max-w-[350px]">
        <label class="block text-[12px] text-gray-500 mb-1">复制所需的文件名称并粘贴在此处 (例: qwen1_5-1_8b-chat-q4_0.gguf)</label>
        <input 
          v-model="fileName"
          type="text" 
          placeholder="指定要下载的文件名..."
          class="w-full border border-gray-300 rounded-md px-3 py-1.5 text-[13px] outline-none focus:border-blue-500"
        />
      </div>

      <button 
        @click="startDownload"
        :disabled="isDownloading"
        class="mt-5 bg-[#3b82f6] hover:bg-blue-700 text-white px-6 py-2 rounded-md font-bold text-[14px] flex items-center gap-2 shadow-sm active:scale-95 transition-all disabled:opacity-50"
      >
        <Loader2 v-if="isDownloading" class="w-4 h-4 animate-spin" />
        <CloudDownload v-else class="w-4 h-4" />
        魔搭下载
      </button>
    </div>

    <!-- Main Content: Embedded ModelScope + Status Overlay -->
    <div class="flex-1 w-full bg-white relative overflow-hidden flex flex-col">
       <div class="flex-1 relative">
         <iframe 
           src="https://www.modelscope.cn/models" 
           class="w-full h-full border-none"
           title="ModelScope Model Center"
         ></iframe>
       </div>
       
       <!-- Status Overlay Bar -->
       <div v-if="Object.keys(activeDownloads).length > 0" class="h-16 bg-gray-900 text-white px-6 flex items-center gap-6 shadow-2xl z-20">
          <div class="text-xs font-bold uppercase tracking-wider text-gray-400 shrink-0">当前任务</div>
          <div class="flex-1 flex gap-4 overflow-x-auto no-scrollbar">
             <div v-for="(v, k) in activeDownloads" :key="k" class="flex items-center gap-2 bg-gray-800 px-3 py-1.5 rounded border border-gray-700 shrink-0 whitespace-nowrap">
                <Loader2 v-if="v.status === 'downloading'" class="w-3 h-3 animate-spin text-blue-400" />
                <CheckCircle2 v-else-if="v.status === 'completed'" class="w-3 h-3 text-green-400" />
                <XCircle v-else class="w-3 h-3 text-red-400" />
                <span class="text-[11px] font-mono">{{ v.model.split('/').pop() }}</span>
                <span class="text-[10px] text-gray-500">{{ v.status }}</span>
             </div>
          </div>
       </div>
    </div>
  </div>
</template>

<style scoped>
/* Ensure the iframe fills correctly and scrolls naturally */
iframe {
  background-color: white;
}
</style>
