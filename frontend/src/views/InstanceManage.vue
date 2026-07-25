<template>
  <UDashboardPanel id="instance-manage" class="min-h-0">
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
            <UButton
              icon="i-lucide-play"
              color="primary"
              variant="ghost"
              square
              :disabled="instanceStatus === 'RUNNING' || instanceStatus === 'STARTING' || instanceStatus === 'STOPPING'"
              @click="doAction('start')"
            />
            <UButton
              icon="i-lucide-square"
              color="error"
              variant="ghost"
              square
              :disabled="instanceStatus === 'STOPPED' || instanceStatus === 'STOPPING'"
              @click="doAction('stop')"
            />
            <UButton
              icon="i-lucide-refresh-cw"
              color="warning"
              variant="ghost"
              square
              :disabled="instanceStatus !== 'RUNNING'"
              @click="doAction('reset')"
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
      <div class="flex h-full min-h-0 flex-col">
        <div v-show="activeTab === 'overview'" class="min-h-0 flex-1 overflow-auto">
          <InstanceOverview
            :instance-id="instanceId"
            :refresh-key="overviewRefreshKey"
            @updated="onOverviewUpdated"
            @status-changed="instanceStatus = $event"
          />
        </div>
        <div v-show="activeTab === 'console'" class="min-h-0 flex-1 overflow-hidden">
          <div
            v-if="instanceStatus === 'STOPPED'"
            class="flex h-full flex-col items-center justify-center gap-4 text-center"
          >
            <UIcon name="i-lucide-monitor-off" class="size-12 text-muted" />
            <div>
              <h3 class="text-lg font-semibold text-highlighted">控制台不可用</h3>
              <p class="mt-1 text-sm text-muted">虚拟机已停止，请先启动后再打开控制台。</p>
            </div>
            <UButton label="立即启动虚拟机" icon="i-lucide-play" size="lg" @click="doAction('start')" />
          </div>
          <TerminalConsole v-else :instance-id="instanceId" class="h-full" />
        </div>
        <div v-show="activeTab === 'files'" class="min-h-0 flex-1 overflow-hidden">
          <FileManager
            :instance-id="instanceId"
            :instance-status="instanceStatus"
            class="h-full"
            @start-instance="doAction('start')"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchInstanceDetail, instanceAction } from "@/api/endpoints";
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
let pollTimer: ReturnType<typeof setInterval> | null = null;

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

async function doAction(action: "start" | "stop" | "reset") {
  try {
    const actionMap = { start: "启动", stop: "停止", reset: "重启" };
    toastInfo(`正在尝试 ${actionMap[action]} 虚拟机…`);
    const updated = await instanceAction(instanceId.value, action);
    instanceStatus.value = updated.status;
    overviewRefreshKey.value += 1;
    toastSuccess(`操作「${actionMap[action]}」已下发`);
    startPolling();
  } catch (error: any) {
    toastError(error.message || "虚拟机操作执行失败");
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
