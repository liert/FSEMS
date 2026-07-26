<template>
  <div class="space-y-4 p-1">
    <LoadingState v-if="initialLoading" description="加载实例详情…" />
    <ErrorState
      v-else-if="loadError && !detail"
      title="无法加载实例详情"
      :description="loadError"
      :retry="() => void loadDetail()"
    />
    <template v-else>
      <div class="grid gap-4 lg:grid-cols-2">
        <motion.div :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(0)">
          <UCard class="h-full ring-1 ring-default/40 transition-shadow hover:shadow-md">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-activity" class="size-4 text-primary" />
                <span class="font-semibold">运行状态</span>
              </div>
            </template>
            <dl class="space-y-2.5">
              <div class="meta-row">
                <dt class="meta-label">状态</dt>
                <dd class="meta-value flex justify-end"><StatusBadge :status="detail?.status || ''" /></dd>
              </div>
              <div class="meta-row">
                <dt class="meta-label">QEMU PID</dt>
                <dd class="meta-value tabular-nums">{{ detail?.pid ?? "—" }}</dd>
              </div>
              <div class="meta-row">
                <dt class="meta-label">SSH</dt>
                <dd class="meta-value meta-mono">{{ sshEndpoint }}</dd>
              </div>
              <div class="meta-row">
                <dt class="meta-label">网络</dt>
                <dd class="meta-value">{{ networkSummary }}</dd>
              </div>
              <UAlert v-if="detail?.error_msg" color="error" variant="subtle" :title="detail.error_msg" class="mt-1" />
            </dl>
          </UCard>
        </motion.div>

        <motion.div :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(1)">
          <UCard class="h-full ring-1 ring-default/40 transition-shadow hover:shadow-md">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-memory-stick" class="size-4 text-info" />
                <span class="font-semibold">QEMU 内存</span>
              </div>
            </template>
            <dl class="space-y-2.5">
              <div class="meta-row">
                <dt class="meta-label">配置上限</dt>
                <dd class="meta-value tabular-nums">{{ detail?.ram_size_mb ?? "—" }} MB</dd>
              </div>
              <div class="meta-row">
                <dt class="meta-label">进程 RSS</dt>
                <dd class="meta-value tabular-nums">{{ ramUsedText }}</dd>
              </div>
            </dl>
            <UProgress v-if="detail?.ram_size_mb" :model-value="ramUsagePercent" class="mt-3" />
          </UCard>
        </motion.div>

        <motion.div :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(2)">
          <UCard class="h-full ring-1 ring-default/40 transition-shadow hover:shadow-md">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-hard-drive" class="size-4 text-secondary" />
                <span class="font-semibold">启动磁盘 (rootfs.img)</span>
              </div>
            </template>
            <dl class="space-y-2.5">
              <div class="meta-row">
                <dt class="meta-label">容量</dt>
                <template v-if="!driveEditing">
                  <dd class="meta-value tabular-nums min-w-0 flex-1 text-right">
                    {{ formatBytes(detail?.drive_fs_total_bytes) }}
                    <span v-if="driveCapacityMb != null" class="ml-1 text-dimmed text-xs">
                      ({{ driveCapacityMb }} MB)
                    </span>
                  </dd>
                  <UTooltip :text="canExpandDrive ? '编辑容量并扩容' : '当前状态不可扩容'">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      square
                      icon="i-lucide-pencil"
                      class="meta-action shrink-0"
                      :ui="{ leadingIcon: 'size-3' }"
                      :disabled="!canExpandDrive || expanding"
                      :loading="expanding"
                      @click.stop="startDriveEdit"
                    />
                  </UTooltip>
                </template>
                <div v-else ref="driveEditWrap" class="flex min-w-0 flex-1 items-center justify-end gap-1.5">
                  <UInputNumber
                    ref="driveInputRef"
                    v-model="driveCapacityEditMb"
                    :min="driveCapacityBaselineMb"
                    :max="driveCapacityBaselineMb + 4096"
                    size="sm"
                    class="w-36"
                    :disabled="expanding"
                    @keydown.enter.prevent="onDriveEditCommitKey"
                    @keydown.escape.prevent="cancelDriveEdit"
                    @blur="onDriveBlur"
                  />
                  <span class="shrink-0 text-xs text-muted">MB</span>
                </div>
              </div>
              <div class="meta-row">
                <dt class="meta-label">已用</dt>
                <dd class="meta-value tabular-nums">{{ formatBytes(detail?.drive_fs_used_bytes) }}</dd>
              </div>
              <div class="meta-row">
                <dt class="meta-label">路径</dt>
                <dd class="meta-value meta-mono truncate" :title="detail?.drive_path || ''">{{ detail?.drive_path || "—" }}</dd>
              </div>
            </dl>
            <UProgress v-if="driveUsagePercent !== null" :model-value="driveUsagePercent" color="secondary" class="mt-3" />
          </UCard>
        </motion.div>

        <motion.div :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(3)">
          <UCard class="h-full ring-1 ring-default/40 transition-shadow hover:shadow-md">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-folder-tree" class="size-4 text-warning" />
                <span class="font-semibold">自定义 RootFS</span>
              </div>
            </template>
            <div class="space-y-2.5">
              <!-- 同一行：标签 + 路径文本 + 编辑图标；非编辑态无输入框 -->
              <div class="meta-row">
                <span class="meta-label">源路径</span>
                <template v-if="!rootfsEditing">
                  <span
                    class="meta-value meta-mono min-w-0 flex-1 truncate"
                    :class="displayRootfsPath ? '' : 'text-dimmed'"
                    :title="displayRootfsPath || undefined"
                  >
                    {{ displayRootfsPath || "未设置" }}
                  </span>
                  <UTooltip :text="customRootfsBusy ? '保存中…' : '编辑源路径'">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      square
                      :icon="customRootfsBusy ? 'i-lucide-loader-circle' : 'i-lucide-pencil'"
                      :loading="customRootfsBusy"
                      :disabled="customRootfsBusy"
                      class="meta-action shrink-0"
                      :ui="{ leadingIcon: 'size-3' }"
                      @click.stop="startRootfsEdit"
                    />
                  </UTooltip>
                </template>
                <div
                  v-else
                  ref="rootfsEditWrap"
                  class="min-w-0 flex-1"
                >
                  <UInput
                    ref="rootfsInputRef"
                    v-model="customRootfsInput"
                    autofocus
                    size="sm"
                    class="w-full"
                    placeholder="宿主机路径，留空清除 · 失焦保存"
                    :disabled="customRootfsBusy"
                    @keydown.enter.prevent="commitRootfsEdit"
                    @keydown.escape.prevent="cancelRootfsEdit"
                    @blur="onRootfsBlur"
                  />
                </div>
              </div>
              <div class="meta-row">
                <span class="meta-label">解压目录</span>
                <span
                  class="meta-value meta-mono truncate"
                  :title="detail?.custom_rootfs_dir_path || ''"
                >
                  {{ detail?.custom_rootfs_dir_path || "不存在" }}
                </span>
              </div>
              <div class="meta-row">
                <span class="meta-label">目录占用</span>
                <span class="meta-value tabular-nums">{{ formatBytes(detail?.custom_rootfs_dir_size_bytes) }}</span>
              </div>
            </div>
          </UCard>
        </motion.div>

        <motion.div class="lg:col-span-2" :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(4)">
          <UCard class="ring-1 ring-default/40">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-file-code" class="size-4 text-muted" />
                <span class="font-semibold">模板与路径</span>
              </div>
            </template>
            <dl class="grid gap-2.5 sm:grid-cols-2">
              <div class="meta-row justify-start gap-2">
                <span class="meta-label">模板</span>
                <span class="meta-value text-left">{{ detail?.template_name }} ({{ detail?.template_arch }})</span>
              </div>
              <div class="meta-row justify-start gap-2 min-w-0">
                <span class="meta-label">工作区</span>
                <span class="meta-value meta-mono min-w-0 truncate text-left" :title="detail?.workspace_path || ''">{{ detail?.workspace_path }}</span>
              </div>
              <div class="meta-row justify-start gap-2 min-w-0 sm:col-span-2">
                <span class="meta-label">内核</span>
                <span class="meta-value meta-mono min-w-0 truncate text-left" :title="detail?.kernel_path || ''">{{ detail?.kernel_path }}</span>
              </div>
            </dl>
          </UCard>
        </motion.div>

        <motion.div class="lg:col-span-2" :initial="{ opacity: 0, y: 10 }" :animate="{ opacity: 1, y: 0 }" :transition="staggerDelay(5)">
          <UCard class="ring-1 ring-default/40">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-camera" class="size-4 text-primary" />
                  <span class="font-semibold">磁盘快照</span>
                </div>
                <UButton size="sm" icon="i-lucide-plus" label="创建" :disabled="detail?.status !== 'STOPPED'" @click="showSnap = true" />
              </div>
            </template>
            <div class="overflow-auto">
              <table v-if="snapshots.length" class="w-full text-sm">
                <thead class="text-left text-muted">
                  <tr>
                    <th class="py-2 font-medium">名称</th>
                    <th class="font-medium">大小</th>
                    <th class="font-medium">时间</th>
                    <th class="text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in snapshots" :key="s.id" class="table-row-interactive border-t border-muted">
                    <td class="py-2.5 font-medium">{{ s.name }}</td>
                    <td class="tabular-nums">{{ formatBytes(s.size_bytes) }}</td>
                    <td class="text-xs text-muted">{{ formatTime(s.created_at) }}</td>
                    <td class="text-right space-x-1">
                      <UButton size="xs" variant="soft" label="恢复" :disabled="detail?.status !== 'STOPPED'" @click="restoreSnap(s)" />
                      <UButton size="xs" color="error" variant="soft" label="删除" @click="deleteSnap(s)" />
                    </td>
                  </tr>
                </tbody>
              </table>
              <EmptyState
                v-else
                title="暂无快照"
                description="在实例停止时创建磁盘快照，便于回滚实验环境。"
                icon="i-lucide-camera"
                size="sm"
              />
            </div>
          </UCard>
        </motion.div>
      </div>
    </template>

    <UModal
      v-model:open="showExpandConfirm"
      title="确认扩容磁盘"
      description="扩容后无法通过此操作缩减容量"
    >
      <template #body>
        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-hard-drive"
          title="将增加磁盘容量"
          :description="expandConfirmDescription"
        />
        <dl class="mt-4 space-y-2 text-sm">
          <div class="flex justify-between gap-4">
            <dt class="text-muted">当前容量</dt>
            <dd class="tabular-nums font-medium">{{ driveCapacityBaselineMb }} MB</dd>
          </div>
          <div class="flex justify-between gap-4">
            <dt class="text-muted">目标容量</dt>
            <dd class="tabular-nums font-medium text-primary">{{ driveCapacityEditMb }} MB</dd>
          </div>
          <div class="flex justify-between gap-4">
            <dt class="text-muted">本次增加</dt>
            <dd class="tabular-nums font-medium text-warning">+{{ pendingExpandMb }} MB</dd>
          </div>
        </dl>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="取消" :disabled="expanding" @click="cancelExpandConfirm" />
          <UButton label="确认扩容" icon="i-lucide-check" :loading="expanding" @click="confirmExpand" />
        </div>
      </template>
    </UModal>

    <UModal v-model:open="showSnap" title="创建快照">
      <template #body>
        <UFormField label="名称"><UInput v-model="snapName" class="w-full" /></UFormField>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="取消" @click="showSnap = false" />
          <UButton label="创建" :loading="snapBusy" @click="submitSnap" />
        </div>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { motion } from "motion-v";
import {
  createSnapshot,
  deleteSnapshot,
  expandInstanceDrive,
  fetchInstanceDetail,
  fetchSnapshots,
  restoreSnapshot,
  updateCustomRootfs,
} from "@/api/endpoints";
import type { InstanceDetail, Snapshot } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { useTaskStore } from "@/stores/tasks";
import { staggerDelay } from "@/utils/motion";
import { toastError, toastSuccess, toastWarning } from "@/utils/toast";

const props = defineProps<{ instanceId: string; refreshKey?: number }>();
const emit = defineEmits<{ (e: "updated"): void; (e: "status-changed", s: string): void }>();

const initialLoading = ref(true);
const detail = ref<InstanceDetail | null>(null);
const loadError = ref("");
const customRootfsInput = ref("");
const customRootfsBusy = ref(false);
const rootfsEditing = ref(false);
const rootfsEditBaseline = ref("");
const rootfsInputRef = ref<{ $el?: HTMLElement } | null>(null);
const rootfsEditWrap = ref<HTMLElement | null>(null);
let rootfsBlurTimer: ReturnType<typeof setTimeout> | null = null;

const displayRootfsPath = computed(
  () => detail.value?.custom_rootfs_source_path || customRootfsInput.value.trim() || ""
);

/** 磁盘容量：展示 + 铅笔编辑（失焦有变化则确认弹窗） */
const driveEditing = ref(false);
const driveCapacityBaselineMb = ref(0);
const driveCapacityEditMb = ref(0);
const driveInputRef = ref<{ $el?: HTMLElement } | null>(null);
const driveEditWrap = ref<HTMLElement | null>(null);
const showExpandConfirm = ref(false);
const pendingExpandMb = ref(0);
const expanding = ref(false);
let driveBlurTimer: ReturnType<typeof setTimeout> | null = null;

const driveCapacityMb = computed(() => {
  const b = detail.value?.drive_fs_total_bytes;
  if (b == null || b <= 0) return null;
  return Math.max(1, Math.round(b / (1024 * 1024)));
});

const expandConfirmDescription = computed(
  () =>
    `将磁盘从 ${driveCapacityBaselineMb.value} MB 扩容至 ${driveCapacityEditMb.value} MB（+${pendingExpandMb.value} MB）。` +
    (isRunningLike.value ? " 实例运行中时将尝试热扩容。" : "")
);
const snapshots = ref<Snapshot[]>([]);
const showSnap = ref(false);
const snapName = ref("");
const snapBusy = ref(false);
const taskStore = useTaskStore();
let pollTimer: ReturnType<typeof setInterval> | null = null;
/** 请求序号：切换实例或轮询与手动刷新重叠时丢弃过期响应 */
let detailSeq = 0;
/** 连续轮询失败计数，超过阈值放弃轮询，避免持续刷错误日志 */
let pollErrors = 0;
const MAX_POLL_ERRORS = 3;

const sshEndpoint = computed(() => {
  if (!detail.value?.guest_ssh_host) return "—";
  return `${detail.value.guest_ssh_host}:${detail.value.guest_ssh_port}`;
});
const networkSummary = computed(() => {
  if (!detail.value) return "—";
  const type = detail.value.network_type === "different" ? "独立局域网" : "同一局域网";
  return `${detail.value.bridge_name || "—"} / ${type}`;
});
const ramUsedText = computed(() => {
  if (detail.value?.ram_used_mb != null) return `${detail.value.ram_used_mb} MB`;
  if (detail.value?.pid) return "读取中…";
  return "—";
});
const ramUsagePercent = computed(() => {
  if (!detail.value?.ram_size_mb || detail.value.ram_used_mb == null) return 0;
  return Math.min(100, Math.round((detail.value.ram_used_mb / detail.value.ram_size_mb) * 100));
});
const driveUsagePercent = computed(() => {
  const t = detail.value?.drive_fs_total_bytes;
  const u = detail.value?.drive_fs_used_bytes;
  if (!t || u == null) return null;
  return Math.min(100, Math.round((u / t) * 100));
});
const canExpandDrive = computed(() => {
  const s = detail.value?.status;
  return !!detail.value?.drive_path && s !== "STARTING" && s !== "STOPPING";
});
const isRunningLike = computed(() => ["RUNNING", "STARTING"].includes(detail.value?.status || ""));

function formatBytes(value?: number | null) {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = value;
  let i = -1;
  do {
    v /= 1024;
    i++;
  } while (v >= 1024 && i < units.length - 1);
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}
function formatTime(value?: string) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("zh-CN");
  } catch {
    return value;
  }
}

async function loadDetail(silent = false) {
  const seq = ++detailSeq;
  if (!silent && !detail.value) initialLoading.value = true;
  try {
    const data = await fetchInstanceDetail(props.instanceId);
    if (seq !== detailSeq) return; // 已有更新的请求在途，丢弃过期响应
    pollErrors = 0;
    loadError.value = "";
    detail.value = data;
    if (!customRootfsBusy.value && !rootfsEditing.value) {
      customRootfsInput.value = data.custom_rootfs_source_path || "";
    }
    // 本组件常驻挂载，是实例状态的唯一轮询源，逐次上报给 InstanceManage
    emit("status-changed", data.status);
    await loadSnapshots(seq);
    if (seq !== detailSeq) return;
    if (data.status === "STARTING" || data.status === "STOPPING") startPolling();
    else stopPolling();
  } catch (e: unknown) {
    if (seq !== detailSeq) return;
    const msg = e instanceof Error ? e.message : "加载实例详情失败";
    if (!detail.value) {
      // 首屏失败：给出错误态与重试入口，而不是一屏空的「—」
      loadError.value = msg;
      stopPolling();
    } else if (++pollErrors >= MAX_POLL_ERRORS) {
      // 实例可能已被删除或后端下线，停止轮询避免无限刷错误
      stopPolling();
      toastError(msg);
    }
  } finally {
    if (seq === detailSeq) initialLoading.value = false;
  }
}

async function loadSnapshots(seq?: number) {
  try {
    const data = await fetchSnapshots(props.instanceId);
    if (seq != null && seq !== detailSeq) return;
    snapshots.value = data.list;
  } catch {
    if (seq != null && seq !== detailSeq) return;
    snapshots.value = [];
  }
}

function focusRootfsInput() {
  void nextTick(() => {
    const root = rootfsInputRef.value?.$el as HTMLElement | undefined;
    const input =
      root?.querySelector?.("input") ||
      (root instanceof HTMLInputElement ? root : null) ||
      rootfsEditWrap.value?.querySelector("input");
    input?.focus();
    input?.select?.();
  });
}

function startRootfsEdit() {
  if (customRootfsBusy.value) return;
  rootfsEditBaseline.value = detail.value?.custom_rootfs_source_path || "";
  customRootfsInput.value = rootfsEditBaseline.value;
  rootfsEditing.value = true;
  focusRootfsInput();
}

function cancelRootfsEdit() {
  if (rootfsBlurTimer) {
    clearTimeout(rootfsBlurTimer);
    rootfsBlurTimer = null;
  }
  customRootfsInput.value = rootfsEditBaseline.value;
  rootfsEditing.value = false;
}

/**
 * 失焦自动保存。用短延迟避免 Enter 与 blur 重复提交。
 */
function onRootfsBlur() {
  if (rootfsBlurTimer) clearTimeout(rootfsBlurTimer);
  rootfsBlurTimer = setTimeout(() => {
    rootfsBlurTimer = null;
    void commitRootfsEdit();
  }, 120);
}

async function commitRootfsEdit() {
  if (rootfsBlurTimer) {
    clearTimeout(rootfsBlurTimer);
    rootfsBlurTimer = null;
  }
  if (!rootfsEditing.value || customRootfsBusy.value) return;

  const path = customRootfsInput.value.trim();
  const baseline = rootfsEditBaseline.value.trim();

  // 未改动：直接退出编辑
  if (path === baseline) {
    rootfsEditing.value = false;
    customRootfsInput.value = baseline;
    return;
  }

  customRootfsBusy.value = true;
  try {
    // 留空 = 清除自定义 RootFS
    detail.value = await updateCustomRootfs(props.instanceId, path || null);
    const saved = detail.value.custom_rootfs_source_path || "";
    customRootfsInput.value = saved;
    rootfsEditBaseline.value = saved;
    rootfsEditing.value = false;
    toastSuccess(path ? "自定义 RootFS 已更新" : "已清除自定义 RootFS");
    emit("updated");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "更新失败");
    // 失败时保持编辑态，方便改路径重试
    focusRootfsInput();
  } finally {
    customRootfsBusy.value = false;
  }
}

function focusDriveInput() {
  void nextTick(() => {
    const root = driveInputRef.value?.$el as HTMLElement | undefined;
    const input =
      root?.querySelector?.("input") ||
      (root instanceof HTMLInputElement ? root : null) ||
      driveEditWrap.value?.querySelector("input");
    input?.focus();
    input?.select?.();
  });
}

function startDriveEdit() {
  if (!canExpandDrive.value || expanding.value) return;
  const mb = driveCapacityMb.value;
  if (mb == null) {
    toastWarning("无法读取当前磁盘容量");
    return;
  }
  driveCapacityBaselineMb.value = mb;
  driveCapacityEditMb.value = mb;
  driveEditing.value = true;
  focusDriveInput();
}

function cancelDriveEdit() {
  if (driveBlurTimer) {
    clearTimeout(driveBlurTimer);
    driveBlurTimer = null;
  }
  driveEditing.value = false;
  driveCapacityEditMb.value = driveCapacityBaselineMb.value;
}

/**
 * 失焦：数值未变则静默退出；有变化则弹出确认框（不立刻提交）。
 */
function onDriveBlur() {
  if (driveBlurTimer) clearTimeout(driveBlurTimer);
  driveBlurTimer = setTimeout(() => {
    driveBlurTimer = null;
    finishDriveEditOnBlur();
  }, 120);
}

function onDriveEditCommitKey() {
  if (driveBlurTimer) {
    clearTimeout(driveBlurTimer);
    driveBlurTimer = null;
  }
  finishDriveEditOnBlur();
}

function finishDriveEditOnBlur() {
  if (!driveEditing.value || expanding.value || showExpandConfirm.value) return;

  const baseline = driveCapacityBaselineMb.value;
  let next = Number(driveCapacityEditMb.value);
  if (!Number.isFinite(next)) {
    cancelDriveEdit();
    return;
  }
  next = Math.round(next);

  // 未改动：不做任何操作
  if (next === baseline) {
    driveEditing.value = false;
    return;
  }

  if (next < baseline) {
    toastWarning("不支持缩小磁盘，请输入不小于当前容量的数值");
    driveCapacityEditMb.value = baseline;
    focusDriveInput();
    return;
  }

  const delta = next - baseline;
  if (delta < 1) {
    driveEditing.value = false;
    return;
  }
  if (delta > 4096) {
    toastWarning("单次扩容最多 4096 MB");
    driveCapacityEditMb.value = baseline + 4096;
    focusDriveInput();
    return;
  }

  pendingExpandMb.value = delta;
  driveCapacityEditMb.value = next;
  driveEditing.value = false;
  showExpandConfirm.value = true;
}

function cancelExpandConfirm() {
  showExpandConfirm.value = false;
  pendingExpandMb.value = 0;
  driveCapacityEditMb.value = driveCapacityBaselineMb.value;
}

async function confirmExpand() {
  const delta = pendingExpandMb.value;
  if (delta < 1) {
    showExpandConfirm.value = false;
    return;
  }
  expanding.value = true;
  try {
    const manage = isRunningLike.value;
    const result = await expandInstanceDrive(props.instanceId, delta, manage);
    toastSuccess(`已扩容 +${result.expanded_mb} MB`);
    showExpandConfirm.value = false;
    pendingExpandMb.value = 0;
    await loadDetail(true);
    emit("updated");
    if (result.status) emit("status-changed", result.status);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "扩容失败");
    // 失败后可再次编辑
    driveEditing.value = true;
    driveCapacityEditMb.value = driveCapacityBaselineMb.value + delta;
    showExpandConfirm.value = false;
    focusDriveInput();
  } finally {
    expanding.value = false;
  }
}

async function submitSnap() {
  const name = snapName.value.trim();
  if (!name) {
    toastWarning("请输入快照名称");
    return;
  }
  snapBusy.value = true;
  try {
    const task = await createSnapshot(props.instanceId, name);
    showSnap.value = false;
    snapName.value = "";
    await taskStore.trackTaskAsync(task.task_id, {
      label: "创建快照",
      detail: name,
      taskType: "SNAPSHOT_CREATE",
      successMessage: "快照创建成功",
      onSuccess: async () => {
        await loadSnapshots();
        emit("updated");
      },
    });
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "创建失败");
  } finally {
    snapBusy.value = false;
  }
}

async function restoreSnap(row: Snapshot) {
  if (!window.confirm(`恢复快照「${row.name}」？`)) return;
  try {
    const task = await restoreSnapshot(props.instanceId, row.id);
    await taskStore.trackTaskAsync(task.task_id, {
      label: "恢复快照",
      detail: row.name,
      taskType: "SNAPSHOT_RESTORE",
      successMessage: "快照恢复成功",
      onSuccess: async () => {
        await loadDetail(true);
        emit("updated");
      },
    });
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "恢复失败");
  }
}

async function deleteSnap(row: Snapshot) {
  if (!window.confirm(`删除快照「${row.name}」？`)) return;
  try {
    await deleteSnapshot(props.instanceId, row.id);
    toastSuccess("已删除");
    await loadSnapshots();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "删除失败");
  }
}

function startPolling() {
  if (pollTimer) return;
  pollErrors = 0;
  pollTimer = setInterval(() => void loadDetail(true), 3000);
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  pollErrors = 0;
}

watch(() => props.refreshKey, () => void loadDetail(true));
// immediate 已覆盖首次加载，不要再叠一个 onMounted，否则挂载时会并发两组请求
watch(() => props.instanceId, () => void loadDetail(), { immediate: true });
onBeforeUnmount(() => {
  stopPolling();
  if (rootfsBlurTimer) {
    clearTimeout(rootfsBlurTimer);
    rootfsBlurTimer = null;
  }
  if (driveBlurTimer) {
    clearTimeout(driveBlurTimer);
    driveBlurTimer = null;
  }
});
</script>
