<template>
  <UDashboardPanel
    id="instance-manage"
    class="min-h-0"
    :ui="{
      body:
        activeTab === 'console' || activeTab === 'files'
          ? 'flex flex-col flex-1 min-h-0 overflow-hidden p-2 sm:p-3'
          : 'flex flex-col flex-1 min-h-0 overflow-y-auto p-4 sm:p-6',
    }"
  >
    <template #header>
      <UDashboardNavbar :title="instanceName || '加载中…'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #left>
          <StatusBadge :status="instanceStatus" />
        </template>
        <template #right>
          <div class="flex items-center gap-1">
            <InstanceActionBar
              :instance-id="instanceId"
              :status="instanceStatus"
              size="md"
              @status-optimistic="onStatusOptimistic"
              @status-changed="onStatusChanged"
              @done="onActionDone"
            />
            <UButton color="neutral" variant="soft" icon="i-lucide-arrow-left" label="返回列表" @click="goBack" />
            <TaskCenter />
          </div>
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UTabs v-model="activeTab" :items="tabItems" class="w-full" :content="false" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="flex min-h-0 flex-1 flex-col">
        <div v-show="activeTab === 'overview'" class="min-h-0 flex-1 overflow-auto">
          <InstanceOverview
            :instance-id="instanceId"
            :refresh-key="overviewRefreshKey"
            @updated="onOverviewUpdated"
            @status-changed="instanceStatus = $event"
          />
        </div>
        <!-- v-if：避免 display:none 时 xterm fit 得到 0 高度导致无法滚动 -->
        <div v-if="activeTab === 'console'" class="relative min-h-0 flex-1 overflow-hidden">
          <div
            v-if="instanceStatus === 'STOPPED'"
            class="flex h-full items-center justify-center p-6"
          >
            <EmptyState
              title="控制台不可用"
              description="虚拟机已停止，请先启动后再打开串口控制台。"
              icon="i-lucide-monitor-off"
              size="lg"
            >
              <template #action>
                <UButton
                  label="立即启动虚拟机"
                  icon="i-lucide-play"
                  size="lg"
                  :loading="consoleStartBusy"
                  @click="startFromConsoleEmpty"
                />
              </template>
            </EmptyState>
          </div>
          <TerminalConsole
            v-else
            ref="consoleRef"
            :instance-id="instanceId"
            class="absolute inset-0 h-full min-h-0"
          />
        </div>
        <div v-if="activeTab === 'files'" class="relative min-h-0 flex-1 overflow-hidden">
          <FileManager
            :instance-id="instanceId"
            :instance-status="instanceStatus"
            class="h-full min-h-0"
            @start-instance="doAction('start')"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchInstanceDetail, instanceAction } from "@/api/endpoints";
import EmptyState from "@/components/EmptyState.vue";
import InstanceActionBar from "@/components/InstanceActionBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import TaskCenter from "@/components/TaskCenter.vue";
import { useUiStore } from "@/stores/ui";
import { toastError, toastInfo, toastSuccess } from "@/utils/toast";
import TerminalConsole from "./TerminalConsole.vue";
import FileManager from "./FileManager.vue";
import InstanceOverview from "./InstanceOverview.vue";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const instanceId = computed(() => route.params.id as string);

const instanceName = ref("");
const instanceStatus = ref("LOADING");
const activeTab = ref("overview");
const overviewRefreshKey = ref(0);
const consoleRef = ref<InstanceType<typeof TerminalConsole> | null>(null);
const consoleStartBusy = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

watch(activeTab, async (tab) => {
  if (tab !== "console") return;
  await nextTick();
  consoleRef.value?.refit();
  // 布局稳定后再 fit 一次
  setTimeout(() => consoleRef.value?.refit(), 80);
});

const tabItems = [
  { label: "基本信息", value: "overview" },
  { label: "控制台", value: "console" },
  { label: "文件管理器", value: "files" },
];

watch(
  instanceName,
  (name) => {
    ui.setPageBreadcrumbLabel(name || null);
  },
  { immediate: true }
);

async function loadInstanceDetails() {
  try {
    const data = await fetchInstanceDetail(instanceId.value);
    instanceName.value = data.name;
    instanceStatus.value = data.status;
    if (data.status === "STARTING" || data.status === "STOPPING") startPolling();
    else stopPolling();
  } catch (error) {
    console.error("加载实例详情发生错误:", error);
    stopPolling();
  }
}

function onStatusOptimistic(status: string) {
  instanceStatus.value = status;
}

function onStatusChanged(status: string) {
  instanceStatus.value = status;
  startPolling();
}

function onActionDone() {
  overviewRefreshKey.value += 1;
  startPolling();
}

/** 控制台空态启动（带按钮 loading） */
async function startFromConsoleEmpty() {
  if (consoleStartBusy.value) return;
  consoleStartBusy.value = true;
  instanceStatus.value = "STARTING";
  try {
    toastInfo("正在启动…");
    const updated = await instanceAction(instanceId.value, "start");
    instanceStatus.value = updated.status;
    overviewRefreshKey.value += 1;
    toastSuccess("已下发启动指令");
    startPolling();
  } catch (error: unknown) {
    toastError(error instanceof Error ? error.message : "启动失败");
    await loadInstanceDetails();
  } finally {
    consoleStartBusy.value = false;
  }
}

async function doAction(action: "start" | "stop" | "reset") {
  // 供 FileManager 等子组件调用
  if (action === "start") instanceStatus.value = "STARTING";
  else if (action === "stop") instanceStatus.value = "STOPPING";
  else instanceStatus.value = "STARTING";
  try {
    const actionMap = { start: "启动", stop: "停止", reset: "重启" };
    toastInfo(`正在${actionMap[action]}…`);
    const updated = await instanceAction(instanceId.value, action);
    instanceStatus.value = updated.status;
    overviewRefreshKey.value += 1;
    toastSuccess(`已下发${actionMap[action]}指令`);
    startPolling();
  } catch (error: unknown) {
    toastError(error instanceof Error ? error.message : "虚拟机操作执行失败");
    await loadInstanceDetails();
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      const data = await fetchInstanceDetail(instanceId.value);
      instanceStatus.value = data.status;
      if (data.status !== "STARTING" && data.status !== "STOPPING") {
        stopPolling();
        overviewRefreshKey.value += 1;
        toastSuccess(`虚拟机状态：${data.status}`);
      }
    } catch {
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function onOverviewUpdated() {
  void loadInstanceDetails();
}

function goBack() {
  router.push("/instances");
}

watch(instanceId, () => void loadInstanceDetails(), { immediate: true });
onBeforeUnmount(() => {
  stopPolling();
  ui.setPageBreadcrumbLabel(null);
});
</script>
