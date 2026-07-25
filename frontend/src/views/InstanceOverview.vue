<template>
  <div class="space-y-4 p-1">
    <div v-if="initialLoading" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-muted" />
    </div>
    <template v-else>
      <div class="grid gap-4 lg:grid-cols-2">
        <UCard>
          <template #header><span class="font-semibold">运行状态</span></template>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between gap-4"><dt class="text-muted">状态</dt><dd><StatusBadge :status="detail?.status || ''" /></dd></div>
            <div class="flex justify-between gap-4"><dt class="text-muted">QEMU PID</dt><dd>{{ detail?.pid ?? "—" }}</dd></div>
            <div class="flex justify-between gap-4"><dt class="text-muted">SSH</dt><dd class="font-mono">{{ sshEndpoint }}</dd></div>
            <div class="flex justify-between gap-4"><dt class="text-muted">网络</dt><dd>{{ networkSummary }}</dd></div>
            <div v-if="detail?.error_msg" class="text-error text-xs">{{ detail.error_msg }}</div>
          </dl>
        </UCard>

        <UCard>
          <template #header><span class="font-semibold">QEMU 内存</span></template>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between"><dt class="text-muted">配置上限</dt><dd>{{ detail?.ram_size_mb ?? "—" }} MB</dd></div>
            <div class="flex justify-between"><dt class="text-muted">进程 RSS</dt><dd>{{ ramUsedText }}</dd></div>
          </dl>
          <UProgress v-if="detail?.ram_size_mb" :model-value="ramUsagePercent" class="mt-3" />
        </UCard>

        <UCard>
          <template #header><span class="font-semibold">启动磁盘 (rootfs.img)</span></template>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between"><dt class="text-muted">容量</dt><dd>{{ formatBytes(detail?.drive_fs_total_bytes) }}</dd></div>
            <div class="flex justify-between"><dt class="text-muted">已用</dt><dd>{{ formatBytes(detail?.drive_fs_used_bytes) }}</dd></div>
            <div class="flex justify-between gap-2"><dt class="shrink-0 text-muted">路径</dt><dd class="truncate font-mono text-xs" :title="detail?.drive_path || ''">{{ detail?.drive_path || "—" }}</dd></div>
          </dl>
          <UProgress v-if="driveUsagePercent !== null" :model-value="driveUsagePercent" color="secondary" class="mt-3" />
          <UButton class="mt-3" size="sm" variant="soft" label="扩容磁盘" :disabled="!canExpandDrive" @click="showExpand = true" />
        </UCard>

        <UCard>
          <template #header><span class="font-semibold">自定义 RootFS</span></template>
          <div class="space-y-3">
            <UFormField label="源路径">
              <UInput v-model="customRootfsInput" placeholder="宿主机压缩包或目录" class="w-full" :disabled="customRootfsBusy" />
            </UFormField>
            <div class="flex gap-2">
              <UButton size="sm" label="应用" :loading="customRootfsBusy" @click="applyCustomRootfs" />
              <UButton size="sm" color="neutral" variant="soft" label="清除" :disabled="customRootfsBusy" @click="clearCustomRootfs" />
            </div>
            <dl class="space-y-1 text-sm">
              <div class="flex justify-between gap-2"><dt class="text-muted">解压目录</dt><dd class="truncate font-mono text-xs">{{ detail?.custom_rootfs_dir_path || "不存在" }}</dd></div>
              <div class="flex justify-between"><dt class="text-muted">目录占用</dt><dd>{{ formatBytes(detail?.custom_rootfs_dir_size_bytes) }}</dd></div>
            </dl>
          </div>
        </UCard>

        <UCard class="lg:col-span-2">
          <template #header><span class="font-semibold">模板与路径</span></template>
          <dl class="grid gap-2 text-sm sm:grid-cols-2">
            <div><span class="text-muted">模板</span> · {{ detail?.template_name }} ({{ detail?.template_arch }})</div>
            <div class="truncate"><span class="text-muted">工作区</span> · <span class="font-mono text-xs">{{ detail?.workspace_path }}</span></div>
            <div class="truncate sm:col-span-2"><span class="text-muted">内核</span> · <span class="font-mono text-xs">{{ detail?.kernel_path }}</span></div>
          </dl>
        </UCard>

        <UCard class="lg:col-span-2">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold">磁盘快照</span>
              <UButton size="sm" icon="i-lucide-plus" label="创建" :disabled="detail?.status !== 'STOPPED'" @click="showSnap = true" />
            </div>
          </template>
          <div class="overflow-auto">
            <table class="w-full text-sm">
              <thead class="text-left text-muted">
                <tr><th class="py-2">名称</th><th>大小</th><th>时间</th><th class="text-right">操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="s in snapshots" :key="s.id" class="border-t border-muted">
                  <td class="py-2 font-medium">{{ s.name }}</td>
                  <td>{{ formatBytes(s.size_bytes) }}</td>
                  <td class="text-xs text-muted">{{ formatTime(s.created_at) }}</td>
                  <td class="text-right space-x-1">
                    <UButton size="xs" variant="soft" label="恢复" :disabled="detail?.status !== 'STOPPED'" @click="restoreSnap(s)" />
                    <UButton size="xs" color="error" variant="soft" label="删除" @click="deleteSnap(s)" />
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="!snapshots.length" class="py-6 text-center text-muted">暂无快照</p>
          </div>
        </UCard>
      </div>
    </template>

    <UModal v-model:open="showExpand" title="扩容磁盘">
      <template #body>
        <UFormField label="增加容量 (MB)">
          <UInputNumber v-model="expandMb" :min="1" :max="4096" class="w-full" />
        </UFormField>
        <div class="mt-2 flex flex-wrap gap-2">
          <UButton v-for="p in [64, 128, 256, 512]" :key="p" size="xs" variant="soft" color="neutral" :label="`+${p}`" @click="expandMb = p" />
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="取消" @click="showExpand = false" />
          <UButton label="确认扩容" :loading="expanding" @click="confirmExpand" />
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
import StatusBadge from "@/components/StatusBadge.vue";
import { useTaskStore } from "@/stores/tasks";
import { toastError, toastSuccess, toastWarning } from "@/utils/toast";

const props = defineProps<{ instanceId: string; refreshKey?: number }>();
const emit = defineEmits<{ (e: "updated"): void; (e: "status-changed", s: string): void }>();

const initialLoading = ref(true);
const detail = ref<InstanceDetail | null>(null);
const customRootfsInput = ref("");
const customRootfsBusy = ref(false);
const showExpand = ref(false);
const expandMb = ref(128);
const expanding = ref(false);
const snapshots = ref<Snapshot[]>([]);
const showSnap = ref(false);
const snapName = ref("");
const snapBusy = ref(false);
const taskStore = useTaskStore();
let pollTimer: ReturnType<typeof setInterval> | null = null;

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
  if (!silent && !detail.value) initialLoading.value = true;
  try {
    detail.value = await fetchInstanceDetail(props.instanceId);
    if (!customRootfsBusy.value) customRootfsInput.value = detail.value.custom_rootfs_source_path || "";
    await loadSnapshots();
    if (detail.value.status === "STARTING" || detail.value.status === "STOPPING") startPolling();
    else stopPolling();
  } finally {
    initialLoading.value = false;
  }
}

async function loadSnapshots() {
  try {
    const data = await fetchSnapshots(props.instanceId);
    snapshots.value = data.list;
  } catch {
    snapshots.value = [];
  }
}

async function applyCustomRootfs() {
  const path = customRootfsInput.value.trim();
  if (!path) {
    toastWarning("请填写源路径");
    return;
  }
  customRootfsBusy.value = true;
  try {
    detail.value = await updateCustomRootfs(props.instanceId, path);
    customRootfsInput.value = detail.value.custom_rootfs_source_path || path;
    toastSuccess("自定义 RootFS 已更新");
    emit("updated");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "更新失败");
  } finally {
    customRootfsBusy.value = false;
  }
}

async function clearCustomRootfs() {
  if (!window.confirm("确定清除自定义 RootFS？")) return;
  customRootfsBusy.value = true;
  try {
    detail.value = await updateCustomRootfs(props.instanceId, null);
    customRootfsInput.value = "";
    toastSuccess("已清除");
    emit("updated");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "清除失败");
  } finally {
    customRootfsBusy.value = false;
  }
}

async function confirmExpand() {
  expanding.value = true;
  try {
    const manage = isRunningLike.value;
    const result = await expandInstanceDrive(props.instanceId, expandMb.value, manage);
    toastSuccess(`已扩容 +${result.expanded_mb} MB`);
    showExpand.value = false;
    await loadDetail(true);
    emit("updated");
    if (result.status) emit("status-changed", result.status);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "扩容失败");
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
  pollTimer = setInterval(() => void loadDetail(true), 3000);
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(() => props.refreshKey, () => void loadDetail(true));
watch(() => props.instanceId, () => void loadDetail(), { immediate: true });
onMounted(() => void loadDetail());
onBeforeUnmount(stopPolling);
</script>
