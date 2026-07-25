<template>
  <UDashboardPanel id="logs">
    <template #header>
      <UDashboardNavbar title="系统日志">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <TaskCenter />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UTabs v-model="activeTab" :items="tabItems" class="flex h-full min-h-0 flex-col gap-3" :ui="{ content: 'flex-1 min-h-0' }">
        <template #backend>
          <div class="flex h-full min-h-0 flex-col gap-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <UButtonGroup>
                  <UButton
                    :variant="backendType === 'fastapi' ? 'solid' : 'soft'"
                    color="neutral"
                    label="FastAPI"
                    size="sm"
                    @click="backendType = 'fastapi'; loadBackendLogs()"
                  />
                  <UButton
                    :variant="backendType === 'celery' ? 'solid' : 'soft'"
                    color="neutral"
                    label="Celery"
                    size="sm"
                    @click="backendType = 'celery'; loadBackendLogs()"
                  />
                </UButtonGroup>
                <USelect
                  v-model="backendLines"
                  :items="[50, 100, 200, 500, 1000]"
                  class="w-28"
                  @update:model-value="loadBackendLogs"
                />
                <UInput v-model="backendSearch" icon="i-lucide-search" placeholder="过滤日志…" class="w-52" />
              </div>
              <div class="flex items-center gap-3">
                <UCheckbox v-model="autoScroll" label="自动滚动" />
                <UButton label="刷新" :loading="loadingBackend" size="sm" @click="loadBackendLogs" />
              </div>
            </div>
            <div
              ref="terminalEl"
              class="min-h-0 flex-1 overflow-auto rounded-lg border border-default bg-inverted p-4 font-mono text-xs text-inverted"
            >
              <template v-if="filteredBackendLines.length">
                <div v-for="(line, idx) in filteredBackendLines" :key="idx" class="flex gap-3">
                  <span class="w-10 shrink-0 text-right text-dimmed select-none">{{ idx + 1 }}</span>
                  <span class="min-w-0 flex-1 break-all whitespace-pre-wrap" :class="lineClass(line)">{{ line }}</span>
                </div>
              </template>
              <div v-else class="flex h-full items-center justify-center text-dimmed">
                {{ loadingBackend ? "正在加载日志…" : "暂无匹配的日志记录" }}
              </div>
            </div>
            <p class="shrink-0 text-xs text-dimmed font-mono">
              共 {{ backendTotalLines }} 行 · 已载入末尾 {{ backendLines }} 行
            </p>
          </div>
        </template>

        <template #frontend>
          <div class="flex h-full min-h-0 flex-col gap-3">
            <div class="flex justify-between gap-2">
              <UButton color="error" variant="soft" size="sm" label="触发测试错误" @click="triggerTestError" />
              <UButton size="sm" label="刷新" :loading="loadingFrontend" @click="loadFrontendLogs" />
            </div>
            <div class="min-h-0 flex-1 overflow-auto rounded-lg border border-default">
              <table class="w-full text-sm">
                <thead class="sticky top-0 bg-elevated text-left text-muted">
                  <tr>
                    <th class="px-3 py-2">ID</th>
                    <th class="px-3 py-2">级别</th>
                    <th class="px-3 py-2">消息</th>
                    <th class="px-3 py-2">URL</th>
                    <th class="px-3 py-2">时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in frontendLogs" :key="row.id" class="border-t border-muted">
                    <td class="px-3 py-2">{{ row.id }}</td>
                    <td class="px-3 py-2">
                      <UBadge :color="levelColor(row.level)" variant="subtle" size="sm">
                        {{ String(row.level).toUpperCase() }}
                      </UBadge>
                    </td>
                    <td class="max-w-xs truncate px-3 py-2" :title="row.message">{{ row.message }}</td>
                    <td class="max-w-xs truncate px-3 py-2 font-mono text-xs" :title="row.url">{{ row.url }}</td>
                    <td class="px-3 py-2 text-xs text-muted">{{ formatTime(row.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-if="!loadingFrontend && !frontendLogs.length" class="py-10 text-center text-muted">
                暂无上报日志
              </p>
            </div>
          </div>
        </template>
      </UTabs>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { fetchBackendLogs, fetchFrontendLogs } from "@/api/endpoints";
import type { FrontendLog } from "@/api/types";
import TaskCenter from "@/components/TaskCenter.vue";
import { toastError, toastWarning } from "@/utils/toast";

const activeTab = ref("backend");
const tabItems = [
  { label: "后端系统日志", value: "backend", slot: "backend" as const },
  { label: "前端客户端日志", value: "frontend", slot: "frontend" as const },
];

const backendType = ref<"fastapi" | "celery">("fastapi");
const backendLines = ref(100);
const backendSearch = ref("");
const backendTotalLines = ref(0);
const backendLinesData = ref<string[]>([]);
const loadingBackend = ref(false);
const autoScroll = ref(true);
const terminalEl = ref<HTMLElement | null>(null);
let backendTimer: ReturnType<typeof setInterval> | null = null;

const filteredBackendLines = computed(() => {
  const chrono = [...backendLinesData.value].reverse();
  if (!backendSearch.value) return chrono;
  const q = backendSearch.value.toLowerCase();
  return chrono.filter((line) => line.toLowerCase().includes(q));
});

const frontendLogs = ref<FrontendLog[]>([]);
const loadingFrontend = ref(false);

function lineClass(line: string) {
  if (line.includes("ERROR") || line.includes("CRITICAL")) return "text-error";
  if (line.includes("WARNING") || line.includes("WARN")) return "text-warning";
  if (line.includes("INFO")) return "text-info";
  return "text-toned";
}

function levelColor(level: string) {
  const l = String(level).toUpperCase();
  if (l === "ERROR") return "error" as const;
  if (l === "WARN" || l === "WARNING") return "warning" as const;
  return "info" as const;
}

async function loadBackendLogs() {
  loadingBackend.value = true;
  try {
    const data = await fetchBackendLogs(backendType.value, backendLines.value, 0);
    backendTotalLines.value = data.total_lines;
    backendLinesData.value = data.lines;
    if (autoScroll.value) {
      await nextTick();
      if (terminalEl.value) terminalEl.value.scrollTop = terminalEl.value.scrollHeight;
    }
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "获取后端日志失败");
  } finally {
    loadingBackend.value = false;
  }
}

async function loadFrontendLogs() {
  loadingFrontend.value = true;
  try {
    const data = await fetchFrontendLogs(50, 0);
    frontendLogs.value = data.logs;
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "获取前端日志失败");
  } finally {
    loadingFrontend.value = false;
  }
}

function startBackendPoll() {
  stopBackendPoll();
  backendTimer = setInterval(() => void loadBackendLogs(), 5000);
}
function stopBackendPoll() {
  if (backendTimer) {
    clearInterval(backendTimer);
    backendTimer = null;
  }
}

watch(activeTab, (tab) => {
  if (tab === "backend") {
    void loadBackendLogs();
    startBackendPoll();
  } else {
    stopBackendPoll();
    void loadFrontendLogs();
  }
});

function triggerTestError() {
  toastWarning("正在触发测试错误…");
  setTimeout(() => {
    throw new Error("这是一个用于测试上报功能的运行时错误日志 (Test Error Log)");
  }, 100);
  setTimeout(() => void loadFrontendLogs(), 1200);
}

function formatTime(utcString: string) {
  if (!utcString) return "";
  try {
    return new Date(utcString).toLocaleString("zh-CN");
  } catch {
    return utcString;
  }
}

onMounted(() => {
  void loadBackendLogs();
  startBackendPoll();
});
onUnmounted(stopBackendPoll);
</script>
