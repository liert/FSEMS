<!-- 实例管理中心：整合控制台、文件管理与生命周期控制 (启动、停止、重启) -->
<template>
  <div class="manage-center-container">
    <header class="header-section">
      <div class="header-left">
        <div class="header-title-row">
          <h1 class="gradient-title">{{ instanceName || '加载中...' }}</h1>
          <span class="info-item id-item" :title="instanceId">ID: {{ shortInstanceId }}</span>
          <span class="divider">|</span>
          <span class="info-item">
            状态:
            <StatusBadge :status="instanceStatus" />
          </span>
        </div>
      </div>
      <div class="header-actions">
        <div class="lifecycle-icons">
          <el-tooltip content="启动" placement="top">
            <span class="icon-btn-wrap">
              <el-button
                type="primary"
                text
                class="lifecycle-icon-btn"
                :disabled="instanceStatus === 'RUNNING' || instanceStatus === 'STARTING' || instanceStatus === 'STOPPING'"
                @click="doAction('start')"
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
                class="lifecycle-icon-btn"
                :disabled="instanceStatus === 'STOPPED' || instanceStatus === 'STOPPING'"
                @click="doAction('stop')"
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
                class="lifecycle-icon-btn"
                :disabled="instanceStatus !== 'RUNNING'"
                @click="doAction('reset')"
              >
                <el-icon><RefreshRight /></el-icon>
              </el-button>
            </span>
          </el-tooltip>
        </div>
        <el-button class="glass-btn back-btn" @click="goBack">
          <el-icon><Back /></el-icon> 返回列表
        </el-button>
      </div>
    </header>

    <div class="tabs-card glass-card">
      <el-tabs v-model="activeTab" class="custom-tabs">
        <el-tab-pane label="基本信息" name="overview">
          <div class="tab-pane-content">
            <InstanceOverview
              :instance-id="instanceId"
              :refresh-key="overviewRefreshKey"
              @updated="onOverviewUpdated"
              @status-changed="instanceStatus = $event"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="控制台" name="console">
          <div class="tab-pane-content">
            <!-- 虚拟机已停止时，显示控制台启动引导占位符 -->
            <div v-if="instanceStatus === 'STOPPED'" class="placeholder-card glass-placeholder">
              <el-icon class="placeholder-icon text-blue"><Monitor /></el-icon>
              <h3>控制台不可用</h3>
              <p>虚拟机当前处于已停止状态。请启动虚拟机以开启控制台会话。</p>
              <el-button type="primary" size="large" class="glow-action-btn" @click="doAction('start')">
                立即启动虚拟机
              </el-button>
            </div>
            <!-- 虚拟机运行中、启动中或停止中，渲染控制台 -->
            <div v-else class="tab-pane-fill">
              <TerminalConsole :instance-id="instanceId" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="文件管理器" name="files">
          <div class="tab-pane-content">
            <div class="tab-pane-fill">
              <FileManager 
                :instance-id="instanceId" 
                :instance-status="instanceStatus"
                @start-instance="doAction('start')"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Back, Monitor, VideoPlay, SwitchButton, RefreshRight } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { fetchInstanceDetail, instanceAction } from "@/api/endpoints";
import StatusBadge from "@/components/StatusBadge.vue";
import { useUiStore } from "@/stores/ui";
import { shortInstanceId as formatShortInstanceId, statusLabel } from "@/utils/instanceStatus";
import TerminalConsole from "./TerminalConsole.vue";
import FileManager from "./FileManager.vue";
import InstanceOverview from "./InstanceOverview.vue";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const instanceId = computed(() => route.params.id as string);

const shortInstanceId = computed(() => formatShortInstanceId(instanceId.value));

const instanceName = ref("");
const instanceStatus = ref("LOADING");
const activeTab = ref("overview");
const overviewRefreshKey = ref(0);

let pollTimer: ReturnType<typeof setInterval> | null = null;

// 计算标签类型样式 — StatusBadge 已接管展示，保留供轮询提示文案
const statusTextCn = computed(() => statusLabel(instanceStatus.value));

watch(
  instanceName,
  (name) => {
    ui.setPageBreadcrumbLabel(name || null);
  },
  { immediate: true }
);

// 加载实例详细数据并按需调整轮询
async function loadInstanceDetails() {
  try {
    const data = await fetchInstanceDetail(instanceId.value);
    instanceName.value = data.name;
    instanceStatus.value = data.status;

    // 当处于过渡状态（启动中/停止中）时开启轮询
    if (data.status === "STARTING" || data.status === "STOPPING") {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    console.error("加载实例详情发生错误:", error);
    stopPolling();
  }
}

// 执行启动、停止、重启生命周期操作
async function doAction(action: "start" | "stop" | "reset") {
  try {
    const actionMap = { start: "启动", stop: "停止", reset: "重启" };
    ElMessage.info(`正在尝试 ${actionMap[action]} 虚拟机...`);
    
    const updated = await instanceAction(instanceId.value, action);
    instanceStatus.value = updated.status;
    overviewRefreshKey.value += 1;
    ElMessage.success(`操作 '${actionMap[action]}' 已下发成功`);

    // 状态变更为过渡状态，启动轮询
    startPolling();
  } catch (error: any) {
    ElMessage.error(error.message || "虚拟机操作执行失败");
  }
}

// 开启轮询状态监控
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    try {
      const data = await fetchInstanceDetail(instanceId.value);
      instanceStatus.value = data.status;
      if (data.status !== "STARTING" && data.status !== "STOPPING") {
        stopPolling();
        overviewRefreshKey.value += 1;
        ElMessage.success(`虚拟机已成功进入状态: ${data.status}`);
      }
    } catch (e) {
      stopPolling();
    }
  }, 2000);
}

// 停止轮询
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function goBack() {
  router.push("/instances");
}

function onOverviewUpdated() {
  overviewRefreshKey.value += 1;
  loadInstanceDetails();
}

watch(instanceId, () => {
  stopPolling();
  instanceName.value = "";
  instanceStatus.value = "LOADING";
  loadInstanceDetails();
}, { immediate: true });

onBeforeUnmount(() => {
  stopPolling();
  ui.setPageBreadcrumbLabel(null);
});
</script>

<style scoped>
.manage-center-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  color: var(--fsems-text);
  overflow: hidden;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.gradient-title {
  font-size: 1.8rem;
  font-weight: 700;
  background: linear-gradient(90deg, #38bdf8 0%, #a855f7 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.divider {
  color: var(--fsems-border-strong);
}

.info-item {
  display: inline-flex;
  align-items: center;
  color: var(--fsems-text-muted);
  font-size: 0.9rem;
}

.id-item {
  font-family: monospace;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-btn-wrap {
  display: inline-flex;
  vertical-align: middle;
}

.lifecycle-icons {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.lifecycle-icon-btn {
  border: none !important;
  padding: 6px 8px !important;
  margin: 0 !important;
  height: auto !important;
  min-height: unset !important;
  background: transparent !important;
}

.lifecycle-icon-btn .el-icon {
  font-size: 18px;
}

.lifecycle-icon-btn:hover {
  background: rgba(255, 255, 255, 0.08) !important;
}

.glass-btn {
  background: var(--fsems-bg-card);
  border: 1px solid var(--fsems-border);
  color: var(--fsems-text);
  backdrop-filter: blur(12px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-btn:hover {
  background: var(--fsems-bg-elevated);
  border-color: var(--fsems-border-strong);
  transform: translateY(-2px);
  color: var(--fsems-text);
}

.back-btn {
  border-radius: 8px;
  padding: 10px 18px;
}

.tabs-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 16px 24px;
  border-radius: var(--fsems-radius-lg);
  background: var(--fsems-bg-elevated);
  border: 1px solid var(--fsems-border);
  backdrop-filter: blur(16px);
  box-shadow: var(--fsems-shadow);
  overflow: hidden;
}

.custom-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* 贯穿 tabs 内容的弹性铺满 */
:deep(.el-tabs__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

:deep(.el-tab-pane) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.tab-pane-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.tab-pane-fill {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* tabs 标签页 */
:deep(.el-tabs__nav-wrap::after) {
  background-color: var(--fsems-border);
}

:deep(.el-tabs__item) {
  color: var(--fsems-text-muted) !important;
  font-weight: 500;
  font-size: 1.05rem;
  transition: all 0.3s ease;
}

:deep(.el-tabs__item.is-active) {
  color: var(--fsems-accent) !important;
  font-weight: 600;
}

:deep(.el-tabs__active-bar) {
  background-color: var(--fsems-accent);
  height: 3px;
  border-radius: 1.5px;
}

/* 占位符卡片 */
.placeholder-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 80px 24px;
  border-radius: 12px;
  color: var(--fsems-text-muted);
  flex: 1;
}

.glass-placeholder {
  background: var(--fsems-bg-card);
  border: 1.5px dashed var(--fsems-border);
}

.placeholder-icon {
  font-size: 4rem;
  margin-bottom: 20px;
}

.text-blue {
  color: var(--fsems-accent);
}

.text-green {
  color: var(--fsems-success);
}

.placeholder-card h3 {
  font-size: 1.4rem;
  font-weight: 600;
  margin: 0 0 10px 0;
  color: var(--fsems-text);
}

.placeholder-card p {
  font-size: 0.95rem;
  color: var(--fsems-text-dim);
  max-width: 460px;
  margin: 0 0 24px 0;
  line-height: 1.6;
}

.glow-action-btn {
  font-weight: 600;
  padding: 14px 28px;
  border-radius: 8px;
  transition: all 0.3s ease;
  box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
}

.glow-action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 25px rgba(56, 189, 248, 0.6);
}

.green-glow {
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
}

.green-glow:hover {
  box-shadow: 0 0 25px rgba(16, 185, 129, 0.6);
}
</style>
