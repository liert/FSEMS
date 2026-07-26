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
              class="w-40 sm:w-56"
              :ui="{ base: 'transition-shadow focus-within:ring-primary/40' }"
            />
            <UButton icon="i-lucide-plus" label="新建实例" class="hidden sm:inline-flex" @click="showCreate = true" />
            <UButton icon="i-lucide-plus" square class="sm:hidden" @click="showCreate = true" />
            <TaskCenter />
            <UTooltip :text="ui.theme === 'dark' ? '浅色主题' : '深色主题'">
              <UButton
                color="neutral"
                variant="ghost"
                square
                :icon="ui.theme === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'"
                @click="ui.toggleTheme()"
              />
            </UTooltip>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <PageMotion class="gap-4">
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="实例总数" :value="instances.length" icon="i-lucide-server" tone="primary" :index="0" />
          <StatCard label="运行中" :value="runningCount" icon="i-lucide-activity" tone="success" :index="1" />
          <StatCard label="已停止" :value="stoppedCount" icon="i-lucide-circle-pause" tone="muted" :index="2" />
          <StatCard label="过渡状态" :value="transitionalCount" icon="i-lucide-loader" tone="warning" :index="3" />
        </div>

        <UCard
          class="flex min-h-0 flex-1 flex-col overflow-hidden ring-1 ring-default"
          :ui="{ body: 'flex-1 min-h-0 p-0', header: 'py-3' }"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-highlighted">实例列表</span>
                <UBadge v-if="filteredInstances.length" color="neutral" variant="subtle" size="sm">
                  {{ filteredInstances.length }}
                </UBadge>
              </div>
              <UButton
                color="neutral"
                variant="ghost"
                size="sm"
                icon="i-lucide-refresh-cw"
                :loading="loading"
                label="刷新"
                @click="load()"
              />
            </div>
          </template>

          <div class="h-full min-h-0 overflow-auto">
            <ErrorState
              v-if="loadError && !loading"
              :description="loadError"
              :retry="() => load()"
            />
            <LoadingState v-else-if="loading && !instances.length" description="正在拉取实例状态…" />
            <template v-else>
              <table v-if="filteredInstances.length" class="w-full text-sm">
                <thead class="sticky top-0 z-10 border-b border-default bg-elevated/95 backdrop-blur-sm text-left text-muted">
                  <tr>
                    <th class="px-4 py-3 font-medium">名称</th>
                    <th class="px-4 py-3 font-medium">状态</th>
                    <th class="hidden px-4 py-3 font-medium md:table-cell">SSH 地址</th>
                    <th class="px-4 py-3 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in filteredInstances"
                    :key="row.id"
                    class="table-row-interactive border-b border-muted group"
                  >
                    <td class="px-4 py-3">
                      <div class="font-medium text-highlighted group-hover:text-primary transition-colors">
                        {{ row.name }}
                      </div>
                      <div class="mt-0.5 font-mono text-[11px] text-dimmed md:hidden">
                        {{ row.guest_ssh_host || "—" }}
                      </div>
                    </td>
                    <td class="px-4 py-3"><StatusBadge :status="row.status" /></td>
                    <td class="hidden px-4 py-3 font-mono text-xs text-toned md:table-cell">
                      {{ row.guest_ssh_host || "—" }}
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center justify-end gap-0.5">
                        <InstanceActionBar
                          :instance-id="row.id"
                          :status="row.status"
                          :disabled="deletingId !== null"
                          size="sm"
                          @status-optimistic="(s) => onStatusOptimistic(row.id, s)"
                          @status-changed="(s) => onStatusChanged(row.id, s)"
                          @done="() => onActionDone()"
                        />
                        <UTooltip text="删除">
                          <UButton
                            icon="i-lucide-trash-2"
                            color="error"
                            variant="ghost"
                            size="sm"
                            square
                            class="action-btn"
                            :loading="deletingId === row.id"
                            :disabled="isDeleteDisabled(row)"
                            @click="askDelete(row)"
                          />
                        </UTooltip>
                        <UButton
                          size="sm"
                          variant="soft"
                          label="进入管理"
                          class="ml-1 transition-transform duration-150 hover:translate-x-0.5"
                          trailing-icon="i-lucide-arrow-right"
                          :disabled="deletingId === row.id"
                          @click="manageInstance(row.id)"
                        />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
              <EmptyState
                v-else-if="!loading"
                :title="searchQuery.trim() ? '没有匹配的实例' : '还没有实例'"
                :description="
                  searchQuery.trim()
                    ? '试试调整搜索关键词，或清空搜索查看全部实例。'
                    : '创建第一个 QEMU 固件实例，开始串口调试与文件传输实验。'
                "
                :icon="searchQuery.trim() ? 'i-lucide-search-x' : 'i-lucide-server'"
              >
                <template #action>
                  <UButton
                    v-if="searchQuery.trim()"
                    color="neutral"
                    variant="soft"
                    label="清空搜索"
                    @click="searchQuery = ''"
                  />
                  <UButton v-else label="新建实例" icon="i-lucide-plus" @click="showCreate = true" />
                </template>
              </EmptyState>
            </template>
          </div>
        </UCard>
      </PageMotion>

      <UModal v-model:open="showCreate" title="新建实例" description="基于固件模板创建 QEMU 实例">
        <template #body>
          <div class="space-y-4">
            <UFormField label="名称" required>
              <UInput v-model="newName" placeholder="例如：OpenWrt 实验环境" class="w-full" autofocus />
            </UFormField>
            <UFormField label="固件模板" required>
              <USelect
                v-model="newTemplateId"
                :items="templateOptions"
                value-key="value"
                class="w-full"
                placeholder="选择模板"
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
                  { label: '同一局域网', value: 'same', description: '共享 br_fsems 网桥' },
                  { label: '独立局域网', value: 'different', description: '独立 br_fs_* 网段' },
                ]"
              />
            </UFormField>
          </div>
        </template>
        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton color="neutral" variant="ghost" label="取消" @click="cancelCreate" />
            <UButton
              label="创建实例"
              icon="i-lucide-plus"
              :loading="creating"
              :disabled="!newName.trim() || newTemplateId === undefined"
              @click="create"
            />
          </div>
        </template>
      </UModal>

      <UModal
        v-model:open="confirmDeleteOpen"
        title="删除实例"
        description="此操作不可恢复"
      >
        <template #body>
          <UAlert
            color="error"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            title="将彻底删除该实例"
            description="同步清理虚拟机专属磁盘镜像及全部解压的工作空间数据。"
          />
          <p class="mt-3 text-sm text-muted">
            确认删除
            <span class="font-semibold text-highlighted">{{ pendingDelete?.name }}</span>
            ？
          </p>
        </template>
        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton color="neutral" variant="ghost" label="取消" @click="confirmDeleteOpen = false" />
            <UButton color="error" label="确认删除" icon="i-lucide-trash-2" @click="confirmDelete" />
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
            <motion.div
              :animate="{ rotate: 360 }"
              :transition="{ duration: 1, repeat: Infinity, ease: 'linear' }"
              class="mx-auto flex size-12 items-center justify-center rounded-full bg-error/10 text-error"
            >
              <UIcon name="i-lucide-loader-circle" class="size-6" />
            </motion.div>
            <div>
              <p class="font-semibold text-highlighted">{{ deleteTargetName || "实例" }}</p>
              <p class="mt-1 text-sm text-muted">{{ deleteProgressLabel }}</p>
            </div>
            <UProgress :model-value="Math.min(100, Math.round(deleteProgressPercent))" color="error" />
            <ul class="space-y-2 text-left text-sm">
              <li
                v-for="(step, idx) in DELETE_STEPS"
                :key="step.label"
                class="flex items-center gap-2 transition-colors"
                :class="
                  idx < deleteProgressStep
                    ? 'text-success'
                    : idx === deleteProgressStep
                      ? 'text-default'
                      : 'text-dimmed'
                "
              >
                <UIcon v-if="idx < deleteProgressStep" name="i-lucide-circle-check" class="size-4" />
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
import { motion } from "motion-v";
import {
  createInstance,
  fetchInstances,
  fetchTemplates,
  deleteInstance,
} from "@/api/endpoints";
import type { Instance, Template } from "@/api/types";
import StatusBadge from "@/components/StatusBadge.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import InstanceActionBar from "@/components/InstanceActionBar.vue";
import LoadingState from "@/components/LoadingState.vue";
import PageMotion from "@/components/PageMotion.vue";
import StatCard from "@/components/StatCard.vue";
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
const loadError = ref("");
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

const confirmDeleteOpen = ref(false);
const pendingDelete = ref<Instance | null>(null);

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

function isDeleteDisabled(row: Instance) {
  return (
    deletingId.value !== null ||
    row.status === "RUNNING" ||
    row.status === "STARTING" ||
    row.status === "STOPPING"
  );
}

/** 生命周期操作在途的实例 id；轮询响应不得覆盖这些行的状态 */
const pendingActionIds = new Set<string>();
/** 列表请求序号，用于丢弃过期响应 */
let listSeq = 0;

function patchInstanceStatus(id: string, status: string) {
  const idx = instances.value.findIndex((i) => i.id === id);
  if (idx < 0) return;
  instances.value[idx] = { ...instances.value[idx], status: status as Instance["status"] };
}

function onStatusOptimistic(id: string, status: string) {
  // 标记为「操作在途」，期间不让后台轮询的旧响应把乐观状态覆盖回去
  pendingActionIds.add(id);
  patchInstanceStatus(id, status);
}

function onStatusChanged(id: string, status: string) {
  pendingActionIds.delete(id);
  patchInstanceStatus(id, status);
  syncStatusPolling();
}

function onActionDone() {
  // 过渡态由轮询刷新到最终 RUNNING/STOPPED
  void load(true);
}

async function load(silent = false) {
  const seq = ++listSeq;
  if (!silent) loading.value = true;
  try {
    const data = await fetchInstances();
    if (seq !== listSeq) return; // 丢弃过期响应
    instances.value = data.list.map((item) => {
      if (!pendingActionIds.has(item.id)) return item;
      const local = instances.value.find((i) => i.id === item.id);
      return local ? { ...item, status: local.status } : item;
    });
    loadError.value = "";
  } catch (e: unknown) {
    if (seq !== listSeq) return;
    if (!silent) {
      loadError.value = e instanceof Error ? e.message : "加载实例失败";
    }
  } finally {
    if (!silent && seq === listSeq) loading.value = false;
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
  try {
    templates.value = await fetchTemplates();
    if (templates.value.length && newTemplateId.value === undefined) {
      newTemplateId.value = templates.value[0].id;
    }
  } catch {
    /* templates optional for list view */
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

function askDelete(row: Instance) {
  if (deletingId.value) return;
  pendingDelete.value = row;
  confirmDeleteOpen.value = true;
}

async function confirmDelete() {
  const row = pendingDelete.value;
  confirmDeleteOpen.value = false;
  if (!row) return;
  await deleteInst(row);
  pendingDelete.value = null;
}

async function deleteInst(row: Instance) {
  if (deletingId.value) return;

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
    await createInstance(
      newName.value,
      newTemplateId.value,
      newRootfsPath.value.trim(),
      newNetworkType.value
    );
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
