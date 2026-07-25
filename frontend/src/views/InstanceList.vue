<template>
  <UDashboardPanel id="instances">
    <template #header>
      <UDashboardNavbar title="实例管理">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UInput
              v-model="searchQuery"
              icon="i-lucide-search"
              placeholder="搜索名称或 ID…"
              class="w-48 sm:w-56"
            />
            <UButton icon="i-lucide-plus" label="新建实例" @click="showCreate = true" />
            <TaskCenter />
            <UButton
              color="neutral"
              variant="ghost"
              square
              :icon="ui.theme === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'"
              @click="ui.toggleTheme()"
            />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex h-full min-h-0 flex-col gap-4">
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <UCard :ui="{ body: 'p-4' }">
            <p class="text-xs text-muted">实例总数</p>
            <p class="mt-1 text-2xl font-semibold text-primary">{{ instances.length }}</p>
          </UCard>
          <UCard :ui="{ body: 'p-4' }">
            <p class="text-xs text-muted">运行中</p>
            <p class="mt-1 text-2xl font-semibold text-success">{{ runningCount }}</p>
          </UCard>
          <UCard :ui="{ body: 'p-4' }">
            <p class="text-xs text-muted">已停止</p>
            <p class="mt-1 text-2xl font-semibold text-muted">{{ stoppedCount }}</p>
          </UCard>
          <UCard :ui="{ body: 'p-4' }">
            <p class="text-xs text-muted">过渡状态</p>
            <p class="mt-1 text-2xl font-semibold text-warning">{{ transitionalCount }}</p>
          </UCard>
        </div>

        <UCard class="flex min-h-0 flex-1 flex-col overflow-hidden" :ui="{ body: 'flex-1 min-h-0 p-0' }">
          <div class="h-full min-h-0 overflow-auto">
            <table class="w-full text-sm">
              <thead class="sticky top-0 z-10 border-b border-default bg-elevated text-left text-muted">
                <tr>
                  <th class="px-4 py-3 font-medium">名称</th>
                  <th class="px-4 py-3 font-medium">状态</th>
                  <th class="px-4 py-3 font-medium">SSH 地址</th>
                  <th class="px-4 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody v-if="filteredInstances.length">
                <tr
                  v-for="row in filteredInstances"
                  :key="row.id"
                  class="border-b border-muted hover:bg-muted/50"
                >
                  <td class="px-4 py-3 font-medium text-highlighted">{{ row.name }}</td>
                  <td class="px-4 py-3"><StatusBadge :status="row.status" /></td>
                  <td class="px-4 py-3 font-mono text-xs text-toned">{{ row.guest_ssh_host || "—" }}</td>
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-1">
                      <UButton
                        icon="i-lucide-play"
                        color="primary"
                        variant="ghost"
                        size="sm"
                        square
                        :disabled="
                          deletingId !== null ||
                          row.status === 'RUNNING' ||
                          row.status === 'STARTING' ||
                          row.status === 'STOPPING'
                        "
                        @click="doAction(row.id, 'start')"
                      />
                      <UButton
                        icon="i-lucide-square"
                        color="error"
                        variant="ghost"
                        size="sm"
                        square
                        :disabled="
                          deletingId !== null ||
                          row.status === 'STOPPED' ||
                          row.status === 'STOPPING'
                        "
                        @click="doAction(row.id, 'stop')"
                      />
                      <UButton
                        icon="i-lucide-refresh-cw"
                        color="warning"
                        variant="ghost"
                        size="sm"
                        square
                        :disabled="deletingId !== null"
                        @click="doAction(row.id, 'reset')"
                      />
                      <UButton
                        icon="i-lucide-trash-2"
                        color="error"
                        variant="ghost"
                        size="sm"
                        square
                        :loading="deletingId === row.id"
                        :disabled="
                          deletingId !== null ||
                          row.status === 'RUNNING' ||
                          row.status === 'STARTING' ||
                          row.status === 'STOPPING'
                        "
                        @click="deleteInst(row)"
                      />
                      <UButton
                        size="sm"
                        variant="soft"
                        label="进入管理"
                        :disabled="deletingId === row.id"
                        @click="manageInstance(row.id)"
                      />
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-if="!loading && !filteredInstances.length"
              title="还没有实例"
              description="创建第一个 QEMU 固件实例，开始串口调试与文件传输实验。"
            >
              <template #action>
                <UButton label="新建实例" icon="i-lucide-plus" @click="showCreate = true" />
              </template>
            </EmptyState>
            <div v-if="loading" class="flex justify-center py-12">
              <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
            </div>
          </div>
        </UCard>
      </div>

      <UModal v-model:open="showCreate" title="新建实例">
        <template #body>
          <div class="space-y-4">
            <UFormField label="名称" required>
              <UInput v-model="newName" placeholder="例如：OpenWrt 实验环境" class="w-full" />
            </UFormField>
            <UFormField label="固件模板" required>
              <USelect
                v-model="newTemplateId"
                :items="templateOptions"
                value-key="value"
                class="w-full"
              />
            </UFormField>
            <UFormField label="自定义 RootFS">
              <UInput v-model="newRootfsPath" placeholder="可选：宿主机上的压缩包或目录路径" class="w-full" />
              <p class="mt-1 text-xs text-dimmed">留空则使用模板默认 rootfs 镜像</p>
            </UFormField>
            <UFormField label="网络模式">
              <URadioGroup
                v-model="newNetworkType"
                :items="[
                  { label: '同一局域网', value: 'same' },
                  { label: '独立局域网', value: 'different' },
                ]"
              />
            </UFormField>
          </div>
        </template>
        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton color="neutral" variant="ghost" label="取消" @click="cancelCreate" />
            <UButton label="创建实例" :loading="creating" @click="create" />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="deleteProgressVisible"
        title="正在删除实例"
        :dismissible="false"
        :close="false"
      >
        <template #body>
          <div class="space-y-4 text-center">
            <UIcon name="i-lucide-loader-circle" class="mx-auto size-9 animate-spin text-error" />
            <div>
              <p class="font-semibold text-highlighted">{{ deleteTargetName || "实例" }}</p>
              <p class="mt-1 text-sm text-muted">{{ deleteProgressLabel }}</p>
            </div>
            <UProgress :model-value="Math.min(100, Math.round(deleteProgressPercent))" color="error" />
            <ul class="space-y-2 text-left text-sm">
              <li
                v-for="(step, idx) in DELETE_STEPS"
                :key="step.label"
                class="flex items-center gap-2"
                :class="idx < deleteProgressStep ? 'text-success' : idx === deleteProgressStep ? 'text-default' : 'text-dimmed'"
              >
                <UIcon
                  v-if="idx < deleteProgressStep"
                  name="i-lucide-circle-check"
                  class="size-4"
                />
                <UIcon
                  v-else-if="idx === deleteProgressStep"
                  name="i-lucide-loader-circle"
                  class="size-4 animate-spin"
                />
                <span v-else class="size-2 rounded-full bg-muted" />
                {{ step.doneLabel }}
              </li>
            </ul>
            <p class="text-xs text-dimmed">请勿关闭页面，清理磁盘与工作空间可能需要一些时间…</p>
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  createInstance,
  fetchInstances,
  fetchTemplates,
  instanceAction,
  deleteInstance,
} from "@/api/endpoints";
import type { Instance, Template } from "@/api/types";
import StatusBadge from "@/components/StatusBadge.vue";
import EmptyState from "@/components/EmptyState.vue";
import TaskCenter from "@/components/TaskCenter.vue";
import { useUiStore } from "@/stores/ui";
import { toastError, toastSuccess } from "@/utils/toast";

const DELETE_STEPS = [
  { label: "正在卸载离线文件系统…", doneLabel: "卸载离线文件系统", targetPercent: 15, holdMs: 400 },
  { label: "正在清理快照记录…", doneLabel: "清理快照记录", targetPercent: 30, holdMs: 350 },
  { label: "正在停止虚拟机并释放网络资源…", doneLabel: "停止虚拟机并释放网络资源", targetPercent: 48, holdMs: 550 },
  { label: "正在删除工作空间与磁盘镜像…", doneLabel: "删除工作空间与磁盘镜像", targetPercent: 90, holdMs: 900 },
  { label: "正在清理数据库记录…", doneLabel: "清理数据库记录", targetPercent: 97, holdMs: 0 },
] as const;

const DELETE_HOLD_STEP = 3;

const router = useRouter();
const ui = useUiStore();
const instances = ref<Instance[]>([]);
const templates = ref<Template[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const newName = ref("");
const newTemplateId = ref<number | undefined>(undefined);
const creating = ref(false);
const newRootfsPath = ref("");
const newNetworkType = ref<"same" | "different">("same");
const searchQuery = ref("");
let statusPollTimer: ReturnType<typeof setInterval> | null = null;

const deletingId = ref<string | null>(null);
const deleteTargetName = ref("");
const deleteTargetId = ref("");
const deleteProgressVisible = ref(false);
const deleteProgressPercent = ref(0);
const deleteProgressStep = ref(0);
const deleteProgressLabel = ref("");
let deleteProgressTimer: ReturnType<typeof setTimeout> | null = null;

const runningCount = computed(() => instances.value.filter((i) => i.status === "RUNNING").length);
const stoppedCount = computed(() => instances.value.filter((i) => i.status === "STOPPED").length);
const transitionalCount = computed(() =>
  instances.value.filter((i) => i.status === "STARTING" || i.status === "STOPPING").length
);

const filteredInstances = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return instances.value;
  return instances.value.filter(
    (i) => i.name.toLowerCase().includes(q) || i.id.toLowerCase().includes(q)
  );
});

const templateOptions = computed(() =>
  templates.value.map((t) => ({ label: `${t.name} (${t.arch})`, value: t.id }))
);

async function load(silent = false) {
  if (!silent) loading.value = true;
  try {
    const data = await fetchInstances();
    instances.value = data.list;
  } finally {
    if (!silent) loading.value = false;
  }
}

function syncStatusPolling() {
  if (transitionalCount.value > 0) {
    if (!statusPollTimer) {
      statusPollTimer = setInterval(() => {
        void load(true);
      }, 3000);
    }
    return;
  }
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

watch(transitionalCount, syncStatusPolling, { immediate: true });

async function loadTemplates() {
  templates.value = await fetchTemplates();
  if (templates.value.length && newTemplateId.value === undefined) {
    newTemplateId.value = templates.value[0].id;
  }
}

async function doAction(id: string, action: "start" | "stop" | "reset") {
  const actionMap = { start: "启动", stop: "停止", reset: "重启" };
  try {
    await instanceAction(id, action);
    toastSuccess(`已执行${actionMap[action]}`);
    await load();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "操作失败");
  }
}

function clearDeleteProgressTimer() {
  if (deleteProgressTimer) {
    clearTimeout(deleteProgressTimer);
    deleteProgressTimer = null;
  }
}

function resetDeleteProgressUi() {
  clearDeleteProgressTimer();
  deleteProgressVisible.value = false;
  deleteProgressPercent.value = 0;
  deleteProgressStep.value = 0;
  deleteProgressLabel.value = "";
  deleteTargetName.value = "";
  deleteTargetId.value = "";
  deletingId.value = null;
}

function startDeleteProgressSimulation() {
  clearDeleteProgressTimer();
  deleteProgressStep.value = 0;
  deleteProgressPercent.value = 5;
  deleteProgressLabel.value = DELETE_STEPS[0].label;

  const crawlWhileHolding = () => {
    if (deleteProgressPercent.value < 92) {
      deleteProgressPercent.value = Math.min(92, deleteProgressPercent.value + 0.35);
      deleteProgressTimer = setTimeout(crawlWhileHolding, 450);
    }
  };

  const advance = (stepIdx: number) => {
    if (stepIdx > DELETE_HOLD_STEP) return;
    deleteProgressStep.value = stepIdx;
    const step = DELETE_STEPS[stepIdx];
    deleteProgressLabel.value = step.label;
    const from = deleteProgressPercent.value;
    const to = step.targetPercent;
    deleteProgressPercent.value = Math.max(from, Math.min(to, from + Math.max(4, (to - from) * 0.4)));

    deleteProgressTimer = setTimeout(() => {
      deleteProgressPercent.value = Math.max(deleteProgressPercent.value, step.targetPercent);
      if (stepIdx < DELETE_HOLD_STEP) advance(stepIdx + 1);
      else crawlWhileHolding();
    }, step.holdMs);
  };
  advance(0);
}

function finishDeleteProgressSuccess() {
  clearDeleteProgressTimer();
  deleteProgressStep.value = DELETE_STEPS.length;
  deleteProgressPercent.value = 100;
  deleteProgressLabel.value = "删除完成";
}

async function deleteInst(row: Instance) {
  if (deletingId.value) return;
  if (!window.confirm("确定要彻底删除该实例吗？这将同步清理虚拟机专属磁盘镜像及全部解压的工作空间数据！")) {
    return;
  }

  deletingId.value = row.id;
  deleteTargetId.value = row.id;
  deleteTargetName.value = row.name;
  deleteProgressVisible.value = true;
  startDeleteProgressSimulation();

  try {
    await deleteInstance(row.id);
    finishDeleteProgressSuccess();
    await new Promise((r) => setTimeout(r, 450));
    toastSuccess("实例删除成功");
    resetDeleteProgressUi();
    await load();
  } catch (e: unknown) {
    resetDeleteProgressUi();
    toastError(e instanceof Error ? e.message : "删除失败");
  }
}

function manageInstance(id: string) {
  router.push(`/instances/${id}/manage`);
}

async function create() {
  if (!newName.value || newTemplateId.value === undefined) return;
  creating.value = true;
  try {
    await createInstance(newName.value, newTemplateId.value, newRootfsPath.value.trim(), newNetworkType.value);
    showCreate.value = false;
    resetForm();
    await load();
    toastSuccess("实例已创建且解压完成");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "创建失败");
  } finally {
    creating.value = false;
  }
}

function cancelCreate() {
  showCreate.value = false;
  resetForm();
}

function resetForm() {
  newName.value = "";
  newRootfsPath.value = "";
  newNetworkType.value = "same";
}

onMounted(async () => {
  await Promise.all([load(), loadTemplates()]);
});

onBeforeUnmount(() => {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
  clearDeleteProgressTimer();
});
</script>
