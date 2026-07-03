<template>
  <div class="page-stack">
    <PageHeader
      title="实例管理"
      description="创建、启动与管理 QEMU 固件实例。Phase 1 同时仅允许一个运行中的实例。"
    >
      <template #actions>
        <el-input
          v-model="searchQuery"
          placeholder="搜索名称或 ID…"
          clearable
          style="width: 220px"
          :prefix-icon="Search"
        />
        <el-button type="primary" @click="showCreate = true">
          <el-icon><Plus /></el-icon>
          新建实例
        </el-button>
      </template>
    </PageHeader>

    <section class="glass-card instance-panel">
      <div class="stats-grid stats-in-panel">
        <div class="stat-card">
          <div class="stat-label">实例总数</div>
          <div class="stat-value accent">{{ instances.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">运行中</div>
          <div class="stat-value success">{{ runningCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">已停止</div>
          <div class="stat-value muted">{{ stoppedCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">过渡状态</div>
          <div class="stat-value">{{ transitionalCount }}</div>
        </div>
      </div>

      <div class="table-panel content-panel table-section">
        <el-table
          :data="filteredInstances"
          v-loading="loading"
          empty-text=" "
          style="width: 100%"
        >
        <template #empty>
          <EmptyState
            title="还没有实例"
            description="创建第一个 QEMU 固件实例，开始串口调试与文件传输实验。"
          >
            <template #action>
              <el-button type="primary" @click="showCreate = true">新建实例</el-button>
            </template>
          </EmptyState>
        </template>

        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <div class="name-cell">
              <span class="name-text">{{ row.name }}</span>
              <span class="name-sub mono-cell">{{ shortInstanceId(row.id) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="guest_ssh_host" label="SSH 地址" width="150">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.guest_ssh_host || "—" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <div class="lifecycle-icons">
                <el-tooltip content="启动" placement="top">
                  <span class="icon-btn-wrap">
                    <el-button
                      type="primary"
                      text
                      size="small"
                      class="lifecycle-icon-btn"
                      :disabled="row.status === 'RUNNING' || row.status === 'STARTING' || row.status === 'STOPPING'"
                      @click="doAction(row.id, 'start')"
                    >
                      <el-icon><VideoPlay /></el-icon>
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip content="停止" placement="top">
                  <span class="icon-btn-wrap">
                    <el-button
                      type="danger"
                      text
                      size="small"
                      class="lifecycle-icon-btn"
                      :disabled="row.status === 'STOPPED' || row.status === 'STOPPING'"
                      @click="doAction(row.id, 'stop')"
                    >
                      <el-icon><SwitchButton /></el-icon>
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip content="重启" placement="top">
                  <span class="icon-btn-wrap">
                    <el-button
                      type="warning"
                      text
                      size="small"
                      class="lifecycle-icon-btn"
                      @click="doAction(row.id, 'reset')"
                    >
                      <el-icon><RefreshRight /></el-icon>
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <span class="icon-btn-wrap">
                    <el-button
                      type="danger"
                      text
                      size="small"
                      class="lifecycle-icon-btn"
                      :disabled="row.status === 'RUNNING' || row.status === 'STARTING' || row.status === 'STOPPING'"
                      @click="deleteInst(row.id)"
                    >
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </span>
                </el-tooltip>
              </div>
              <el-button size="small" type="primary" plain @click="manageInstance(row.id)">
                进入管理
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </section>

    <el-dialog v-model="showCreate" title="新建实例" width="520px" :before-close="cancelCreate">
      <el-form label-width="120px" label-position="left">
        <el-form-item label="名称" required>
          <el-input v-model="newName" placeholder="例如：OpenWrt 实验环境" />
        </el-form-item>
        <el-form-item label="固件模板" required>
          <el-select v-model="newTemplateId" style="width: 100%">
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="`${t.name} (${t.arch})`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="自定义 RootFS">
          <el-input
            v-model="newRootfsPath"
            placeholder="可选：宿主机上的压缩包或目录路径"
          />
          <div class="field-hint">留空则使用模板默认 rootfs 镜像</div>
        </el-form-item>
        <el-form-item label="网络模式">
          <el-radio-group v-model="newNetworkType">
            <el-radio label="same">同一局域网</el-radio>
            <el-radio label="different">独立局域网</el-radio>
          </el-radio-group>
          <div class="field-hint">
            同一局域网共享 `br_fsems`（192.168.1.x）；独立局域网为实例分配专属网桥与网段。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelCreate">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建实例</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Delete,
  Plus,
  RefreshRight,
  Search,
  SwitchButton,
  VideoPlay,
} from "@element-plus/icons-vue";
import {
  createInstance,
  fetchInstances,
  fetchTemplates,
  instanceAction,
  deleteInstance,
} from "@/api/endpoints";
import type { Instance, Template } from "@/api/types";
import PageHeader from "@/components/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import EmptyState from "@/components/EmptyState.vue";
import { shortInstanceId } from "@/utils/instanceStatus";

const router = useRouter();
const instances = ref<Instance[]>([]);
const templates = ref<Template[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const newName = ref("");
const newTemplateId = ref<number | null>(null);
const creating = ref(false);
const newRootfsPath = ref("");
const newNetworkType = ref<"same" | "different">("same");
const searchQuery = ref("");
let statusPollTimer: ReturnType<typeof setInterval> | null = null;

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

async function load(silent = false) {
  if (!silent) {
    loading.value = true;
  }
  try {
    const data = await fetchInstances();
    instances.value = data.list;
  } finally {
    if (!silent) {
      loading.value = false;
    }
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
  if (templates.value.length && newTemplateId.value === null) {
    newTemplateId.value = templates.value[0].id;
  }
}

async function doAction(id: string, action: "start" | "stop" | "reset") {
  const actionMap = { start: "启动", stop: "停止", reset: "重启" };
  try {
    await instanceAction(id, action);
    ElMessage.success(`已执行${actionMap[action]}`);
    await load();
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  }
}

async function deleteInst(id: string) {
  try {
    await ElMessageBox.confirm(
      "确定要彻底删除该实例吗？这将同步清理虚拟机专属磁盘镜像及全部解压的工作空间数据！",
      "安全警告",
      {
        confirmButtonText: "确定删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
    await deleteInstance(id);
    ElMessage.success("实例删除成功");
    await load();
  } catch (e: unknown) {
    if (e !== "cancel") {
      ElMessage.error(e instanceof Error ? e.message : "删除失败");
    }
  }
}

function manageInstance(id: string) {
  router.push(`/instances/${id}/manage`);
}

async function create() {
  if (!newName.value || newTemplateId.value === null) return;
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
    ElMessage.success("实例已创建且解压完成");
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "创建失败");
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
});
</script>

<style scoped>
.instance-panel {
  overflow: hidden;
}

.stats-in-panel {
  padding: 18px 22px 0;
}

.table-section {
  padding-top: 12px;
  border-top: 1px solid var(--fsems-border);
  margin-top: 4px;
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-text {
  font-weight: 600;
  color: var(--fsems-text);
}

.name-sub {
  font-size: 0.78rem;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.lifecycle-icons {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.icon-btn-wrap {
  display: inline-flex;
}

.lifecycle-icon-btn {
  border: none !important;
  padding: 4px 6px !important;
  margin: 0 !important;
  height: auto !important;
}

.field-hint {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--fsems-text-dim);
  line-height: 1.5;
}
</style>
