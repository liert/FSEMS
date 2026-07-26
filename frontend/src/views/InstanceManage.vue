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
        <!--
          控制台首次打开后保持挂载（v-show），离开标签页不再销毁终端：
          否则 shell 会话、滚动历史和当前工作目录都会丢失。
        -->
        <div
          v-if="consoleMounted"
          v-show="activeTab === 'console'"
          class="relative min-h-0 flex-1 overflow-hidden"
        >
          <TerminalConsole
            ref="consoleRef"
            :instance-id="instanceId"
            :guest-available="consoleGuestAvailable"
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
/** 懒挂载：首次进入控制台标签页才创建终端，避免未使用时也占一条串口连接 */
const consoleMounted = ref(false);
const consoleGuestAvailable = computed(
  () =>
    instanceStatus.value === "RUNNING" ||
    instanceStatus.value === "STARTING" ||
    instanceStatus.value === "STOPPING"
);

watch(activeTab, async (tab) => {
  if (tab !== "console") return;
  consoleMounted.value = true;
  await nextTick();
  consoleRef.value?.refit();
  // 布局稳定后再 fit 一次
  setTimeout(() => consoleRef.value?.refit(), 80);
});

const tabItems = [
  { label: "基本信息", value: "overview", icon: "i-lucide-info" },
  { label: "控制台", value: "console", icon: "i-lucide-square-terminal" },
  { label: "文件管理器", value: "files", icon: "i-lucide-folder-tree" },
];

const statusActionText: Record<string, string> = {
  RUNNING: "已启动",
  STOPPED: "已停止",
  ERROR: "进入错误状态",
};

// 状态由 InstanceOverview 的轮询统一上报，这里只负责在过渡态结束时提示一次
watch(instanceStatus, (next, prev) => {
  const wasTransitional = prev === "STARTING" || prev === "STOPPING";
  const isTransitional = next === "STARTING" || next === "STOPPING";
  if (!wasTransitional || isTransitional || next === "LOADING") return;
  toastSuccess(`虚拟机${statusActionText[next] ?? `状态：${next}`}`);
});

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
  } catch (error) {
    toastError(error instanceof Error ? error.message : "加载实例详情失败");
  }
}

function onStatusOptimistic(status: string) {
  instanceStatus.value = status;
}

function onStatusChanged(status: string) {
  instanceStatus.value = status;
  overviewRefreshKey.value += 1;
}

function onActionDone() {
  overviewRefreshKey.value += 1;
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
  } catch (error: unknown) {
    toastError(error instanceof Error ? error.message : "虚拟机操作执行失败");
    await loadInstanceDetails();
  }
}

function onOverviewUpdated() {
  void loadInstanceDetails();
}

function goBack() {
  router.push("/instances");
}

watch(instanceId, () => void loadInstanceDetails(), { immediate: true });
onBeforeUnmount(() => ui.setPageBreadcrumbLabel(null));
</script>
