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
      <PageMotion>
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
                <UInput v-model="backendSearch" icon="i-lucide-search" placeholder="过滤日志…" class="w-40 sm:w-52" />
              </div>
              <div class="flex items-center gap-3">
                <UCheckbox v-model="autoScroll" label="自动滚动" />
                <UButton label="刷新" icon="i-lucide-refresh-cw" :loading="loadingBackend" size="sm" @click="loadBackendLogs" />
              </div>
            </div>
            <div
              ref="terminalEl"
              class="min-h-0 flex-1 overflow-auto rounded-xl border border-default bg-inverted p-4 font-mono text-xs text-inverted shadow-inner"
            >
              <template v-if="filteredBackendLines.length">
                <div
                  v-for="(line, idx) in filteredBackendLines"
                  :key="idx"
                  class="flex gap-3 rounded px-1 py-0.5 hover:bg-white/5 transition-colors"
                >
                  <span class="w-10 shrink-0 text-right text-dimmed select-none">{{ idx + 1 }}</span>
                  <span class="min-w-0 flex-1 break-all whitespace-pre-wrap" :class="lineClass(line)">{{ line }}</span>
                </div>
              </template>
              <div v-else class="flex h-full items-center justify-center">
                <EmptyState
                  :loading="loadingBackend"
                  :title="loadingBackend ? '正在加载日志…' : '暂无匹配的日志记录'"
                  :description="loadingBackend ? undefined : '尝试调整过滤条件或切换日志源'"
                  icon="i-lucide-scroll-text"
                  size="sm"
                  variant="naked"
                  class="text-inverted"
                />
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
              <UButton color="error" variant="soft" size="sm" icon="i-lucide-bug" label="触发测试错误" @click="triggerTestError" />
              <UButton size="sm" icon="i-lucide-refresh-cw" label="刷新" :loading="loadingFrontend" @click="loadFrontendLogs" />
            </div>
            <div class="min-h-0 flex-1 overflow-auto rounded-xl border border-default ring-1 ring-default/40">
              <LoadingState v-if="loadingFrontend && !frontendLogs.length" description="加载前端日志…" />
              <template v-else>
                <table v-if="frontendLogs.length" class="w-full text-sm">
                  <thead class="sticky top-0 bg-elevated/95 backdrop-blur-sm text-left text-muted">
                    <tr>
                      <th class="px-3 py-2.5 font-medium">ID</th>
                      <th class="px-3 py-2.5 font-medium">级别</th>
                      <th class="px-3 py-2.5 font-medium">消息</th>
                      <th class="hidden px-3 py-2.5 font-medium md:table-cell">URL</th>
                      <th class="px-3 py-2.5 font-medium">时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in frontendLogs"
                      :key="row.id"
                      class="table-row-interactive border-t border-muted"
                    >
                      <td class="px-3 py-2.5 text-toned">{{ row.id }}</td>
                      <td class="px-3 py-2.5">
                        <UBadge :color="levelColor(row.level)" variant="subtle" size="sm">
                          {{ String(row.level).toUpperCase() }}
                        </UBadge>
                      </td>
                      <td class="max-w-xs truncate px-3 py-2.5" :title="row.message">{{ row.message }}</td>
                      <td class="hidden max-w-xs truncate px-3 py-2.5 font-mono text-xs md:table-cell" :title="row.url">
                        {{ row.url }}
                      </td>
                      <td class="px-3 py-2.5 text-xs text-muted whitespace-nowrap">{{ formatTime(row.created_at) }}</td>
                    </tr>
                  </tbody>
                </table>
                <EmptyState
                  v-else
                  title="暂无上报日志"
                  description="前端运行时错误会自动上报到这里。"
                  icon="i-lucide-bug"
                />
              </template>
            </div>
          </div>
        </template>
      </UTabs>
      </PageMotion>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { fetchBackendLogs, fetchFrontendLogs } from "@/api/endpoints";
import type { FrontendLog } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import LoadingState from "@/components/LoadingState.vue";
import PageMotion from "@/components/PageMotion.vue";
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
/** 后端日志请求序号，用于丢弃切换日志源后返回的过期响应 */
let backendSeq = 0;

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
  // 切换日志源时轮询请求可能仍在途，用序号丢弃过期响应，
  // 否则会在 Celery 选中态下渲染 FastAPI 的日志
  const seq = ++backendSeq;
  loadingBackend.value = true;
  try {
    const data = await fetchBackendLogs(backendType.value, backendLines.value, 0);
    if (seq !== backendSeq) return;
    backendTotalLines.value = data.total_lines;
    backendLinesData.value = data.lines;
    if (autoScroll.value) {
      await nextTick();
      if (terminalEl.value) terminalEl.value.scrollTop = terminalEl.value.scrollHeight;
    }
  } catch (e: unknown) {
    if (seq !== backendSeq) return;
    toastError(e instanceof Error ? e.message : "获取后端日志失败");
  } finally {
    if (seq === backendSeq) loadingBackend.value = false;
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
