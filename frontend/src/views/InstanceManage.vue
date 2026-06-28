<!-- 实例管理中心：整合控制台、文件管理与生命周期控制 (启动、停止、重置) -->
<template>
  <div class="manage-center-container">
    <header class="header-section">
      <div class="header-left">
        <div class="header-title-row">
          <h1 class="gradient-title">{{ instanceName || '加载中...' }}</h1>
          <span class="info-item id-item">ID: {{ instanceId }}</span>
          <span class="divider">|</span>
          <span class="info-item">
            状态: 
            <el-tag :type="statusTagType" size="small" effect="dark">{{ statusTextCn }}</el-tag>
          </span>
        </div>
      </div>
      <div class="header-actions">
        <el-button-group>
          <el-button 
            type="primary" 
            size="default" 
            :disabled="instanceStatus === 'RUNNING' || instanceStatus === 'STARTING' || instanceStatus === 'STOPPING'" 
            @click="doAction('start')"
          >
            启动
          </el-button>
          <el-button 
            type="danger" 
            size="default" 
            :disabled="instanceStatus === 'STOPPED' || instanceStatus === 'STOPPING'" 
            @click="doAction('stop')"
          >
            停止
          </el-button>
          <el-button 
            type="warning" 
            size="default" 
            :disabled="instanceStatus !== 'RUNNING'" 
            @click="doAction('reset')"
          >
            重置
          </el-button>
        </el-button-group>
        <el-button class="glass-btn back-btn" @click="goBack">
          <el-icon><Back /></el-icon> 返回列表
        </el-button>
      </div>
    </header>

    <div class="tabs-card glass-card">
      <el-tabs v-model="activeTab" class="custom-tabs">
        <el-tab-pane label="串口控制台" name="console">
          <div class="tab-pane-content">
            <!-- 虚拟机已停止时，显示控制台启动引导占位符 -->
            <div v-if="instanceStatus === 'STOPPED'" class="placeholder-card glass-placeholder">
              <el-icon class="placeholder-icon text-blue"><Monitor /></el-icon>
              <h3>串口控制台不可用</h3>
              <p>虚拟机当前处于已停止状态。请启动虚拟机以开启串口控制台会话。</p>
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
            <!-- 虚拟机未完全就绪运行，显示文件管理启动引导占位符 -->
            <div v-if="instanceStatus !== 'RUNNING'" class="placeholder-card glass-placeholder">
              <el-icon class="placeholder-icon text-green"><FolderOpened /></el-icon>
              <h3>虚拟机网络及 SSH 未就绪</h3>
              <p>文件管理器需要虚拟机处于运行中且 SSH 服务正常响应。当前状态: {{ instanceStatus }}</p>
              <el-button 
                type="success" 
                size="large" 
                class="glow-action-btn green-glow" 
                :disabled="instanceStatus === 'STARTING' || instanceStatus === 'STOPPING'"
                @click="doAction('start')"
              >
                {{ instanceStatus === 'STARTING' ? '虚拟机启动中，请稍候...' : '启动虚拟机' }}
              </el-button>
            </div>
            <!-- 虚拟机已启动，渲染双栏文件管理器 -->
            <div v-else class="tab-pane-fill">
              <FileManager :instance-id="instanceId" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Back, Monitor, FolderOpened } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { fetchInstanceDetail, instanceAction } from "@/api/endpoints";
import TerminalConsole from "./TerminalConsole.vue";
import FileManager from "./FileManager.vue";

const route = useRoute();
const router = useRouter();
const instanceId = route.params.id as string;

const instanceName = ref("");
const instanceStatus = ref("LOADING");
const activeTab = ref("console");

let pollTimer: ReturnType<typeof setInterval> | null = null;

// 计算标签类型样式
const statusTagType = computed(() => {
  if (instanceStatus.value === "RUNNING") return "success";
  if (instanceStatus.value === "STARTING") return "warning";
  if (instanceStatus.value === "STOPPED") return "info";
  return "danger";
});

// 计算中文状态显示
const statusTextCn = computed(() => {
  const statusMap: Record<string, string> = {
    LOADING: "加载中...",
    STARTING: "启动中",
    RUNNING: "运行中",
    STOPPING: "停止中",
    STOPPED: "已停止",
  };
  return statusMap[instanceStatus.value] || instanceStatus.value;
});

// 加载实例详细数据并按需调整轮询
async function loadInstanceDetails() {
  try {
    const data = await fetchInstanceDetail(instanceId);
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

// 执行启动、停止、重置生命周期操作
async function doAction(action: "start" | "stop" | "reset") {
  try {
    const actionMap = { start: "启动", stop: "停止", reset: "重置" };
    ElMessage.info(`正在尝试 ${actionMap[action]} 虚拟机...`);
    
    const updated = await instanceAction(instanceId, action);
    instanceStatus.value = updated.status;
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
      const data = await fetchInstanceDetail(instanceId);
      instanceStatus.value = data.status;
      if (data.status !== "STARTING" && data.status !== "STOPPING") {
        stopPolling();
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

onMounted(() => {
  loadInstanceDetails();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.manage-center-container {
  padding: 24px;
  background: linear-gradient(135deg, #0f0f15 0%, #171725 100%);
  height: 100vh;
  color: #e2e8f0;
  font-family: 'Outfit', 'Inter', system-ui, -apple-system, sans-serif;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden; /* 绝对禁止整个网页产生滚动条 */
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
  color: rgba(255, 255, 255, 0.15);
}

.info-item {
  display: inline-flex;
  align-items: center;
  color: #94a3b8;
  font-size: 0.9rem;
}

.id-item {
  font-family: monospace;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.glass-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #f1f5f9;
  backdrop-filter: blur(12px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.glass-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
  color: #fff;
}

.back-btn {
  border-radius: 8px;
  padding: 10px 18px;
}

.tabs-card {
  flex: 1; /* 撑满高度方向的剩余空间 */
  display: flex;
  flex-direction: column;
  min-height: 0; /* 允许子元素自由缩小，防止撑高 */
  padding: 16px 24px;
  border-radius: 16px;
  background: rgba(23, 23, 37, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
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

/* 自定义 tabs 标签页美化，融入暗色主题 */
:deep(.el-tabs__nav-wrap::after) {
  background-color: rgba(255, 255, 255, 0.05);
}

:deep(.el-tabs__item) {
  color: #94a3b8 !important;
  font-weight: 500;
  font-size: 1.05rem;
  transition: all 0.3s ease;
}

:deep(.el-tabs__item.is-active) {
  color: #38bdf8 !important;
  font-weight: 600;
  text-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
}

:deep(.el-tabs__active-bar) {
  background-color: #38bdf8;
  height: 3px;
  border-radius: 1.5px;
  box-shadow: 0 0 8px #38bdf8;
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
  color: #cbd5e1;
  flex: 1;
}

.glass-placeholder {
  background: rgba(255, 255, 255, 0.02);
  border: 1.5px dashed rgba(255, 255, 255, 0.08);
}

.placeholder-icon {
  font-size: 4rem;
  margin-bottom: 20px;
}

.text-blue {
  color: #38bdf8;
  filter: drop-shadow(0 0 12px rgba(56, 189, 248, 0.4));
}

.text-green {
  color: #10b981;
  filter: drop-shadow(0 0 12px rgba(16, 185, 129, 0.4));
}

.placeholder-card h3 {
  font-size: 1.4rem;
  font-weight: 600;
  margin: 0 0 10px 0;
}

.placeholder-card p {
  font-size: 0.95rem;
  color: #94a3b8;
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
