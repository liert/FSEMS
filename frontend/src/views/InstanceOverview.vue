<template>
  <div
    class="overview-panel"
    v-loading="initialLoading"
    element-loading-background="rgba(20, 20, 25, 0.75)"
  >
    <div class="overview-grid">
      <section class="info-card">
        <h3 class="card-title">运行状态</h3>
        <dl class="info-list">
          <div class="info-row">
            <dt>状态</dt>
            <dd><el-tag :type="statusTagType" size="small" effect="dark">{{ statusTextCn }}</el-tag></dd>
          </div>
          <div class="info-row">
            <dt>QEMU 进程 PID</dt>
            <dd>{{ detail?.pid ?? "—" }}</dd>
          </div>
          <div class="info-row">
            <dt>SSH 地址</dt>
            <dd>{{ sshEndpoint }}</dd>
          </div>
          <div class="info-row">
            <dt>网桥 / 网络</dt>
            <dd>{{ networkSummary }}</dd>
          </div>
          <div v-if="detail?.error_msg" class="info-row error-row">
            <dt>错误信息</dt>
            <dd>{{ detail.error_msg }}</dd>
          </div>
        </dl>
      </section>

      <section class="info-card">
        <h3 class="card-title">QEMU 内存</h3>
        <dl class="info-list">
          <div class="info-row">
            <dt>配置上限</dt>
            <dd>{{ detail?.ram_size_mb ?? "—" }} MB</dd>
          </div>
          <div class="info-row">
            <dt>进程已用 (RSS)</dt>
            <dd>{{ ramUsedText }}</dd>
          </div>
        </dl>
        <div v-if="detail?.ram_size_mb" class="usage-bar-wrap">
          <el-progress
            :percentage="ramUsagePercent"
            :stroke-width="10"
            :status="detail?.pid ? undefined : 'warning'"
            :show-text="false"
          />
          <span class="usage-caption">{{ ramUsageCaption }}</span>
        </div>
      </section>

      <section class="info-card">
        <h3 class="card-title">启动磁盘 (rootfs.img)</h3>
        <dl class="info-list">
          <div class="info-row">
            <dt>文件系统容量</dt>
            <dd>{{ formatBytes(detail?.drive_fs_total_bytes) }}</dd>
          </div>
          <div class="info-row">
            <dt>已用空间</dt>
            <dd>{{ formatBytes(detail?.drive_fs_used_bytes) }}</dd>
          </div>
          <div class="info-row path-row">
            <dt>路径</dt>
            <dd :title="detail?.drive_path || undefined">{{ detail?.drive_path || "—" }}</dd>
          </div>
        </dl>
        <div v-if="driveUsagePercent !== null" class="usage-bar-wrap">
          <el-progress
            :percentage="driveUsagePercent"
            :stroke-width="10"
            color="#a855f7"
            :show-text="false"
          />
          <span class="usage-caption">文件系统已用 / 总容量</span>
        </div>
        <div class="drive-actions">
          <el-button
            type="primary"
            size="small"
            plain
            :disabled="!canExpandDrive"
            @click="showExpandDialog = true"
          >
            扩容磁盘
          </el-button>
          <span v-if="detail?.status === 'STOPPING'" class="action-hint">虚拟机正在停止中，请稍候</span>
          <span v-else-if="isRunningLike" class="action-hint">运行中将先优雅停止，扩容后自动重启</span>
        </div>
      </section>

      <section class="info-card">
        <h3 class="card-title">自定义 RootFS</h3>
        <dl class="info-list">
          <div class="info-row path-row">
            <dt>创建时源路径</dt>
            <dd :title="detail?.custom_rootfs_source_path || undefined">
              {{ detail?.custom_rootfs_source_path || "未指定" }}
            </dd>
          </div>
          <div class="info-row path-row">
            <dt>解压目录</dt>
            <dd :title="detail?.custom_rootfs_dir_path || undefined">
              {{ detail?.custom_rootfs_dir_path || "不存在" }}
            </dd>
          </div>
          <div class="info-row">
            <dt>目录占用</dt>
            <dd>{{ formatBytes(detail?.custom_rootfs_dir_size_bytes) }}</dd>
          </div>
        </dl>
      </section>

      <section class="info-card wide-card">
        <h3 class="card-title">模板与路径</h3>
        <dl class="info-list">
          <div class="info-row">
            <dt>固件模板</dt>
            <dd>{{ detail?.template_name || "—" }} ({{ detail?.template_arch || "—" }})</dd>
          </div>
          <div class="info-row path-row">
            <dt>内核路径</dt>
            <dd :title="detail?.kernel_path || undefined">{{ detail?.kernel_path || "—" }}</dd>
          </div>
          <div class="info-row path-row">
            <dt>工作目录</dt>
            <dd :title="detail?.workspace_path || undefined">{{ detail?.workspace_path || "—" }}</dd>
          </div>
          <div class="info-row">
            <dt>创建时间</dt>
            <dd>{{ formatTime(detail?.created_at) }}</dd>
          </div>
        </dl>
      </section>

      <section class="info-card wide-card">
        <div class="card-title-row">
          <h3 class="card-title">磁盘快照</h3>
          <el-button
            type="primary"
            size="small"
            plain
            :disabled="!canManageSnapshots || snapshotBusy"
            @click="showSnapshotDialog = true"
          >
            创建快照
          </el-button>
        </div>
        <p class="snapshot-hint">
          使用 <strong>qcow2 压缩快照</strong>（比 raw 整盘复制更省空间）。仅虚拟机 <strong>已停止</strong> 时可创建/恢复/删除。
        </p>
        <el-table :data="snapshots" size="small" class="snapshot-table" empty-text="暂无快照">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                size="small"
                :disabled="!canManageSnapshots || snapshotBusy"
                @click="confirmRestore(row)"
              >
                恢复
              </el-button>
              <el-button
                link
                type="danger"
                size="small"
                :disabled="!canManageSnapshots || snapshotBusy"
                @click="confirmDeleteSnapshot(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>

    <el-dialog
      v-model="showSnapshotDialog"
      title="创建磁盘快照"
      width="420px"
      @closed="snapshotName = ''"
    >
      <el-form label-width="80px" @submit.prevent>
        <el-form-item label="名称">
          <el-input v-model="snapshotName" placeholder="例如：实验前备份" maxlength="100" />
        </el-form-item>
      </el-form>
      <p class="snapshot-dialog-hint">任务提交后可在顶栏「后台任务」查看进度。</p>
      <template #footer>
        <el-button @click="showSnapshotDialog = false">取消</el-button>
        <el-button type="primary" :loading="snapshotBusy" @click="submitCreateSnapshot">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showExpandDialog"
      title="扩容启动磁盘 (rootfs.img)"
      width="480px"
      class="expand-dialog"
      :close-on-click-modal="!expanding"
      :close-on-press-escape="!expanding"
      :show-close="!expanding"
      @closed="resetExpandDialog"
    >
      <template v-if="expandView === 'form'">
        <p class="expand-desc">
          将同时扩展磁盘镜像与内部 ext4 文件系统。
          <template v-if="isRunningLike">
            当前虚拟机正在运行，将分步执行：优雅停止 → 扩容 → 启动；SSH 就绪在后台等待，无需停留在此窗口。
          </template>
          <template v-else>
            当前虚拟机已停止，将直接扩容磁盘。
          </template>
        </p>
        <el-form label-width="96px" @submit.prevent>
          <el-form-item label="增加容量">
            <el-input-number v-model="expandMb" :min="1" :max="4096" :step="64" :disabled="expanding" />
            <span class="expand-unit">MB</span>
          </el-form-item>
          <el-form-item label="快捷选择">
            <el-button-group>
              <el-button
                v-for="preset in expandPresets"
                :key="preset"
                size="small"
                :disabled="expanding"
                @click="expandMb = preset"
              >
                +{{ preset }} MB
              </el-button>
            </el-button-group>
          </el-form-item>
          <el-form-item label="扩容后容量">
            <span class="expand-preview">{{ projectedDriveTotal }}</span>
          </el-form-item>
        </el-form>
      </template>

      <div v-else class="expand-progress-panel">
        <div class="progress-header">
          <span class="progress-title">{{ expandProgressTitle }}</span>
          <span class="progress-elapsed">总耗时 {{ formatElapsed(totalElapsedSec) }}</span>
        </div>
        <el-progress
          :percentage="overallProgress"
          :stroke-width="12"
          :status="expandProgressStatus"
          striped
          striped-flow
        />
        <p class="progress-summary">{{ currentStepSummary }}</p>
        <el-alert
          v-if="slowWarning"
          :title="slowWarning"
          type="warning"
          show-icon
          :closable="false"
          class="slow-alert"
        />
        <el-steps direction="vertical" :space="72" class="expand-steps">
          <el-step
            v-for="step in expandSteps"
            :key="step.id"
            :title="step.title"
            :status="mapStepStatus(step)"
            :description="stepDescription(step)"
          />
        </el-steps>
        <el-result
          v-if="expandView === 'done'"
          icon="success"
          title="扩容完成"
          :sub-title="expandDoneMessage"
        />
        <el-result
          v-if="expandView === 'error'"
          icon="error"
          title="扩容失败"
          :sub-title="expandErrorMessage"
        />
      </div>

      <template #footer>
        <template v-if="expandView === 'form'">
          <el-button :disabled="expanding" @click="showExpandDialog = false">取消</el-button>
          <el-button type="primary" :disabled="!canExpandDrive" @click="confirmExpand">
            {{ isRunningLike ? "停止、扩容并重启" : "确认扩容" }}
          </el-button>
        </template>
        <template v-else-if="expandView === 'done' || expandView === 'error'">
          <el-button type="primary" @click="showExpandDialog = false">关闭</el-button>
        </template>
        <template v-else>
          <el-button disabled>正在执行…</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { expandInstanceDrive, fetchInstanceDetail, instanceAction, fetchSnapshots, createSnapshot, restoreSnapshot, deleteSnapshot } from "@/api/endpoints";
import type { DriveExpandResult, InstanceDetail, Snapshot } from "@/api/types";
import { useTaskStore } from "@/stores/tasks";

type ExpandView = "form" | "progress" | "done" | "error";
type StepId = "stop" | "expand" | "start";
type StepState = "pending" | "running" | "done" | "error";

interface ExpandStepItem {
  id: StepId;
  title: string;
  hint: string;
  slowAfterSec: number;
  slowHint: string;
  state: StepState;
  startedAt: number | null;
  finishedAt: number | null;
  error?: string;
}

const props = defineProps<{
  instanceId: string;
  refreshKey?: number;
}>();

const emit = defineEmits<{
  (e: "updated"): void;
  (e: "status-changed", status: string): void;
}>();

const initialLoading = ref(true);
const detail = ref<InstanceDetail | null>(null);
const showExpandDialog = ref(false);
const expandView = ref<ExpandView>("form");
const expandMb = ref(128);
const expanding = ref(false);
const expandPresets = [64, 128, 256, 512];
const expandSteps = ref<ExpandStepItem[]>([]);
const expandDoneMessage = ref("");
const expandErrorMessage = ref("");
const progressTick = ref(0);
const expandStartedAt = ref(0);
const taskStore = useTaskStore();
const snapshots = ref<Snapshot[]>([]);
const showSnapshotDialog = ref(false);
const snapshotName = ref("");
const snapshotBusy = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let progressTimer: ReturnType<typeof setInterval> | null = null;

const statusTagType = computed(() => {
  const status = detail.value?.status;
  if (status === "RUNNING") return "success";
  if (status === "STARTING") return "warning";
  if (status === "STOPPED") return "info";
  return "danger";
});

const statusTextCn = computed(() => {
  const map: Record<string, string> = {
    STARTING: "启动中",
    RUNNING: "运行中",
    STOPPING: "停止中",
    STOPPED: "已停止",
  };
  return map[detail.value?.status || ""] || detail.value?.status || "—";
});

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
  return "未运行";
});

const ramUsagePercent = computed(() => {
  if (!detail.value?.ram_size_mb || detail.value.ram_used_mb == null) return 0;
  return Math.min(100, Math.round((detail.value.ram_used_mb / detail.value.ram_size_mb) * 100));
});

const ramUsageCaption = computed(() => {
  if (detail.value?.ram_used_mb == null) return "虚拟机未运行时无进程内存数据";
  return `${detail.value.ram_used_mb} MB / ${detail.value.ram_size_mb} MB`;
});

const driveUsagePercent = computed(() => {
  const total = detail.value?.drive_fs_total_bytes;
  const used = detail.value?.drive_fs_used_bytes;
  if (!total || used == null) return null;
  return Math.min(100, Math.round((used / total) * 100));
});

const canExpandDrive = computed(
  () =>
    detail.value?.status !== "STOPPING" &&
    detail.value?.status !== "STARTING" &&
    !expanding.value
);

const canManageSnapshots = computed(() => detail.value?.status === "STOPPED" && !expanding.value && !snapshotBusy.value);

const isRunningLike = computed(() => {
  const status = detail.value?.status;
  return status === "RUNNING" || status === "STARTING";
});

const totalElapsedSec = computed(() => {
  progressTick.value;
  if (!expandStartedAt.value) return 0;
  return Math.floor((Date.now() - expandStartedAt.value) / 1000);
});

const activeStep = computed(() => expandSteps.value.find((s) => s.state === "running") ?? null);

const overallProgress = computed(() => {
  progressTick.value;
  const steps = expandSteps.value;
  if (!steps.length) return 0;
  const done = steps.filter((s) => s.state === "done").length;
  let base = (done / steps.length) * 100;
  const running = activeStep.value;
  if (running?.startedAt) {
    const elapsed = (Date.now() - running.startedAt) / 1000;
    const partial = Math.min(0.85, elapsed / (running.slowAfterSec * 1.5));
    base += (partial / steps.length) * 100;
  }
  if (expandView.value === "done") return 100;
  return Math.min(99, Math.round(base));
});

const expandProgressStatus = computed(() => {
  if (expandView.value === "error") return "exception";
  if (expandView.value === "done") return "success";
  return undefined;
});

const expandProgressTitle = computed(() => {
  if (expandView.value === "done") return "全部步骤已完成";
  if (expandView.value === "error") return "执行中断";
  return activeStep.value?.title ?? "准备中";
});

const currentStepSummary = computed(() => {
  progressTick.value;
  const running = activeStep.value;
  if (!running) {
    if (expandView.value === "done") return "磁盘已成功扩容。";
    if (expandView.value === "error") return expandErrorMessage.value || "操作失败";
    return "正在初始化…";
  }
  const elapsed = running.startedAt
    ? formatElapsed(Math.floor((Date.now() - running.startedAt) / 1000))
    : "0:00";
  return `${running.hint}（本步已用时 ${elapsed}）`;
});

const slowWarning = computed(() => {
  progressTick.value;
  const running = activeStep.value;
  if (!running?.startedAt) return "";
  const elapsedSec = (Date.now() - running.startedAt) / 1000;
  if (elapsedSec >= running.slowAfterSec) return running.slowHint;
  return "";
});

const projectedDriveTotal = computed(() => {
  const current = detail.value?.drive_fs_total_bytes ?? 0;
  return formatBytes(current + expandMb.value * 1024 * 1024);
});

function formatBytes(value?: number | null): string {
  if (value == null) return "—";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  const num = value / 1024 ** i;
  return `${num.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function formatTime(value?: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function formatElapsed(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function mapStepStatus(step: ExpandStepItem) {
  if (step.state === "done") return "success";
  if (step.state === "error") return "error";
  if (step.state === "running") return "process";
  return "wait";
}

function stepDescription(step: ExpandStepItem): string {
  if (step.state === "error") return step.error || "失败";
  if (step.state === "done" && step.startedAt && step.finishedAt) {
    const sec = Math.max(1, Math.round((step.finishedAt - step.startedAt) / 1000));
    return `已完成，耗时 ${formatElapsed(sec)}`;
  }
  if (step.state === "running") return step.hint;
  return "等待中";
}

function buildExpandSteps(needsRestart: boolean): ExpandStepItem[] {
  const steps: ExpandStepItem[] = [];
  if (needsRestart) {
    steps.push({
      id: "stop",
      title: "优雅停止 QEMU",
      hint: "正在等待虚拟机进程退出…",
      slowAfterSec: 15,
      slowHint: "停止耗时较长，仍在等待 QEMU 优雅退出（最长约 30 秒）",
      state: "pending",
      startedAt: null,
      finishedAt: null,
    });
  }
  steps.push({
    id: "expand",
    title: "扩容磁盘与文件系统",
    hint: "正在执行 qemu-img resize 与 resize2fs…",
    slowAfterSec: 45,
    slowHint: "磁盘扩容耗时较长，可能正在检查/扩展 ext4 文件系统，请继续等待",
    state: "pending",
    startedAt: null,
    finishedAt: null,
  });
  if (needsRestart) {
    steps.push({
      id: "start",
      title: "启动虚拟机",
      hint: "正在创建 TAP 并启动 QEMU 进程…",
      slowAfterSec: 20,
      slowHint: "启动命令已下发，QEMU 初始化可能较慢",
      state: "pending",
      startedAt: null,
      finishedAt: null,
    });
  }
  return steps;
}

function getStep(id: StepId): ExpandStepItem {
  const step = expandSteps.value.find((s) => s.id === id);
  if (!step) throw new Error(`missing step ${id}`);
  return step;
}

function beginStep(id: StepId) {
  const step = getStep(id);
  step.state = "running";
  step.startedAt = Date.now();
  step.finishedAt = null;
  step.error = undefined;
}

function finishStep(id: StepId) {
  const step = getStep(id);
  step.state = "done";
  step.finishedAt = Date.now();
}

function failStep(id: StepId, message: string) {
  const step = getStep(id);
  step.state = "error";
  step.error = message;
  step.finishedAt = Date.now();
}

function startProgressTimer() {
  stopProgressTimer();
  progressTimer = setInterval(() => {
    progressTick.value += 1;
  }, 1000);
}

function stopProgressTimer() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

function resetExpandDialog() {
  if (expanding.value) return;
  expandView.value = "form";
  expandSteps.value = [];
  expandDoneMessage.value = "";
  expandErrorMessage.value = "";
  expandStartedAt.value = 0;
  stopProgressTimer();
}

async function waitForStatus(
  target: string | string[],
  timeoutMs: number,
  intervalMs = 2000
): Promise<InstanceDetail> {
  const targets = Array.isArray(target) ? target : [target];
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const data = await fetchInstanceDetail(props.instanceId);
    if (targets.includes(data.status)) return data;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`等待状态 ${targets.join("/")} 超时`);
}

async function watchBootInBackground() {
  try {
    const result = await waitForStatus(["RUNNING", "STOPPED"], 130000);
    if (detail.value) {
      detail.value.status = result.status;
      detail.value.pid = result.pid;
    }
    emit("status-changed", result.status);
    emit("updated");
    if (result.status === "RUNNING") {
      ElMessage.success("虚拟机已启动并就绪");
    } else {
      ElMessage.error(result.error_msg || "虚拟机启动失败或超时");
    }
  } catch (error: any) {
    await loadDetail(true);
    if (detail.value) emit("status-changed", detail.value.status);
    emit("updated");
    ElMessage.error(error.message || "等待虚拟机就绪超时");
  }
}

function finishExpandFlow(message: string, closeDialog = true) {
  expandDoneMessage.value = message;
  stopProgressTimer();
  expanding.value = false;
  ElMessage.success(message);
  emit("updated");
  if (closeDialog) showExpandDialog.value = false;
}

async function confirmExpand() {
  if (!canExpandDrive.value) return;
  const needsRestart = isRunningLike.value;
  expanding.value = true;
  expandView.value = "progress";
  expandSteps.value = buildExpandSteps(needsRestart);
  expandStartedAt.value = Date.now();
  startProgressTimer();

  let lastResult: DriveExpandResult | null = null;

  try {
    if (needsRestart) {
      beginStep("stop");
      emit("status-changed", "STOPPING");
      await instanceAction(props.instanceId, "stop", { allowSigkill: false, timeoutMs: 45000 });
      const stopped = await waitForStatus("STOPPED", 40000);
      finishStep("stop");
      if (detail.value) detail.value.status = stopped.status;
      emit("status-changed", stopped.status);
    }

    beginStep("expand");
    lastResult = await expandInstanceDrive(props.instanceId, expandMb.value, false);
    finishStep("expand");
    if (detail.value && lastResult) {
      detail.value.drive_fs_total_bytes = lastResult.drive_fs_total_bytes;
      detail.value.drive_fs_used_bytes = lastResult.drive_fs_used_bytes;
      detail.value.drive_path = lastResult.drive_path;
    }

    if (needsRestart) {
      beginStep("start");
      emit("status-changed", "STARTING");
      await instanceAction(props.instanceId, "start", { timeoutMs: 30000 });
      finishStep("start");
      if (detail.value) detail.value.status = "STARTING";
      finishExpandFlow(
        `已扩容 +${expandMb.value} MB，虚拟机正在后台启动，可在页面查看状态。`
      );
      void watchBootInBackground();
      return;
    }

    finishExpandFlow(`已扩容 +${expandMb.value} MB。`);
  } catch (error: any) {
    const message = error.message || "扩容失败";
    expandErrorMessage.value = message;
    expandView.value = "error";
    const failed = expandSteps.value.find((s) => s.state === "running");
    if (failed) failStep(failed.id, message);
    ElMessage.error(message);
    await loadDetail(true);
    if (detail.value) emit("status-changed", detail.value.status);
    emit("updated");
  } finally {
    expanding.value = false;
    stopProgressTimer();
  }
}

async function loadDetail(silent = false) {
  if (!silent && !detail.value) {
    initialLoading.value = true;
  }
  try {
    detail.value = await fetchInstanceDetail(props.instanceId);
    await loadSnapshots();
  } catch (error) {
    console.error("加载实例基本信息失败:", error);
  } finally {
    initialLoading.value = false;
  }
}

async function loadSnapshots() {
  try {
    const data = await fetchSnapshots(props.instanceId);
    snapshots.value = data.list;
  } catch (error) {
    console.error("加载快照列表失败:", error);
  }
}

async function submitCreateSnapshot() {
  const name = snapshotName.value.trim();
  if (!name) {
    ElMessage.warning("请输入快照名称");
    return;
  }
  snapshotBusy.value = true;
  try {
    const task = await createSnapshot(props.instanceId, name);
    showSnapshotDialog.value = false;
    snapshotName.value = "";
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
  } catch (error: unknown) {
    ElMessage.error(error instanceof Error ? error.message : "创建快照失败");
  } finally {
    snapshotBusy.value = false;
  }
}

async function confirmRestore(row: Snapshot) {
  try {
    await ElMessageBox.confirm(
      `确定将 rootfs.img 恢复为快照「${row.name}」？当前磁盘内容将被覆盖。`,
      "恢复快照",
      { type: "warning", confirmButtonText: "恢复" }
    );
    snapshotBusy.value = true;
    try {
      const task = await restoreSnapshot(props.instanceId, row.id);
      await taskStore.trackTaskAsync(task.task_id, {
        label: "恢复快照",
        detail: row.name,
        taskType: "SNAPSHOT_RESTORE",
        successMessage: "快照已恢复",
        onSuccess: async () => {
          await loadDetail(true);
          emit("updated");
        },
      });
    } catch (error: unknown) {
      ElMessage.error(error instanceof Error ? error.message : "恢复快照失败");
    } finally {
      snapshotBusy.value = false;
    }
  } catch (error: unknown) {
    if (error !== "cancel" && (error as Error)?.message !== "cancel") {
      ElMessage.error(error instanceof Error ? error.message : "恢复快照失败");
    }
  }
}

async function confirmDeleteSnapshot(row: Snapshot) {
  try {
    await ElMessageBox.confirm(`确定删除快照「${row.name}」？`, "删除快照", { type: "warning" });
    snapshotBusy.value = true;
    await deleteSnapshot(props.instanceId, row.id);
    ElMessage.success("快照已删除");
    await loadSnapshots();
  } catch (error: any) {
    if (error !== "cancel" && error?.message !== "cancel") {
      ElMessage.error(error.message || "删除快照失败");
    }
  } finally {
    snapshotBusy.value = false;
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    const status = detail.value?.status;
    if (status === "RUNNING" || status === "STARTING" || status === "STOPPING") {
      loadDetail(true);
    } else {
      stopPolling();
    }
  }, 3000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

watch(
  () => props.refreshKey,
  () => {
    if (props.refreshKey) loadDetail(true);
  }
);

watch(
  () => detail.value?.status,
  (status) => {
    if (status === "RUNNING" || status === "STARTING" || status === "STOPPING") startPolling();
    else stopPolling();
  }
);

onMounted(() => {
  loadDetail();
});

onBeforeUnmount(() => {
  stopPolling();
  stopProgressTimer();
});
</script>

<style scoped>
.overview-panel {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 4px 2px 12px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.info-card {
  background: var(--fsems-bg-card);
  border: 1px solid var(--fsems-border);
  border-radius: 12px;
  padding: 18px 20px;
}

.wide-card {
  grid-column: 1 / -1;
}

.card-title {
  margin: 0 0 14px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--fsems-text);
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.card-title-row .card-title {
  margin: 0;
}

.snapshot-hint {
  margin: 0 0 12px;
  color: var(--fsems-text-dim);
  font-size: 0.82rem;
  line-height: 1.5;
}

.snapshot-dialog-hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--fsems-text-dim);
}

.snapshot-table {
  width: 100%;
}

.snapshot-progress-panel {
  padding: 4px 2px 8px;
}

.snapshot-progress-label {
  margin: 0 0 12px;
  color: var(--fsems-text-muted);
  font-size: 0.9rem;
}

.snapshot-progress-error {
  margin: 12px 0 0;
  color: var(--fsems-danger);
  font-size: 0.85rem;
}

.info-list {
  margin: 0;
}

.info-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--fsems-border);
}

.info-row:last-child {
  border-bottom: none;
}

.info-row dt {
  margin: 0;
  color: var(--fsems-text-dim);
  font-size: 0.88rem;
}

.info-row dd {
  margin: 0;
  color: var(--fsems-text);
  font-size: 0.92rem;
  word-break: break-all;
}

.path-row dd {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.84rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.error-row dd {
  color: var(--fsems-danger);
}

.usage-bar-wrap {
  margin-top: 14px;
}

.usage-caption {
  display: block;
  margin-top: 6px;
  color: var(--fsems-text-dim);
  font-size: 0.82rem;
}

.drive-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.action-hint {
  color: var(--fsems-text-dim);
  font-size: 0.82rem;
}

.expand-desc {
  margin: 0 0 16px;
  color: var(--fsems-text-muted);
  font-size: 0.9rem;
  line-height: 1.6;
}

.expand-unit {
  margin-left: 8px;
  color: var(--fsems-text-muted);
}

.expand-preview {
  color: var(--fsems-text);
  font-weight: 600;
}

.expand-progress-panel {
  padding: 4px 2px 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}

.progress-title {
  color: var(--fsems-text);
  font-weight: 600;
  font-size: 0.95rem;
}

.progress-elapsed {
  color: var(--fsems-text-dim);
  font-size: 0.82rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.progress-summary {
  margin: 10px 0 14px;
  color: var(--fsems-text-muted);
  font-size: 0.88rem;
  line-height: 1.5;
}

.slow-alert {
  margin-bottom: 14px;
}

.expand-steps {
  margin-top: 8px;
}

:deep(.expand-steps .el-step__title) {
  color: var(--fsems-text) !important;
  font-size: 0.92rem;
}

:deep(.expand-steps .el-step__description) {
  color: var(--fsems-text-dim) !important;
  font-size: 0.82rem;
}

:deep(.expand-progress-panel .el-result) {
  padding: 12px 0 0;
}

:deep(.expand-progress-panel .el-result__title) {
  color: var(--fsems-text);
}

:deep(.expand-progress-panel .el-result__subtitle) {
  color: var(--fsems-text-muted);
}

:deep(.expand-dialog .el-dialog) {
  background: var(--fsems-bg-elevated);
  border: 1px solid var(--fsems-border);
}

:deep(.expand-dialog .el-dialog__title),
:deep(.expand-dialog .el-form-item__label) {
  color: var(--fsems-text);
}

@media (max-width: 960px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
