<template>
  <div ref="fileManagerRef" class="file-manager-wrapper">
    <div class="panes-wrapper">
      <!-- 左栏：宿主机工作空间 (Host Workspace) -->
      <div class="pane-card glass-card">
        <div class="pane-header">
          <div class="pane-header-top">
            <div class="pane-title">
              <span class="pulse-indicator host-pulse"></span>
              宿主机 (Host)
            </div>
            
            <!-- 宿主机智能地址栏 -->
            <div class="address-bar-container">
              <!-- 编辑态：显示路径输入框 -->
              <el-input
                v-if="hostEditingPath"
                ref="hostInputRef"
                v-model="hostInputPath"
                size="small"
                placeholder="输入绝对或相对路径，回车跳转"
                class="address-input"
                @keyup.enter="handleHostPathSubmit"
                @blur="handleHostPathSubmit"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>

              <!-- 非编辑态：显示面包屑路径 -->
              <div v-else class="address-breadcrumbs" @click="startHostEdit">
                <el-icon class="folder-prefix"><Folder /></el-icon>
                <el-breadcrumb separator="/" @click.stop>
                  <el-breadcrumb-item>
                    <a @click.prevent="navigateHost('/')">root</a>
                  </el-breadcrumb-item>
                  <el-breadcrumb-item v-for="(part, idx) in hostVisibleParts" :key="idx">
                    <span v-if="part.isEllipsis" class="ellipsis-node">...</span>
                    <a v-else @click.prevent="navigateHostToIdx(part.originalIndex)">{{ part.name }}</a>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </div>
          </div>
        </div>

        <div class="file-list-wrapper" v-loading="hostLoading" element-loading-background="rgba(20, 20, 25, 0.8)">
          <el-table
            ref="hostTableRef"
            :data="hostFiles"
            height="100%"
            highlight-current-row
            @current-change="handleHostSelect"
            @row-contextmenu="handleHostContextMenu"
            class="file-table"
            empty-text="暂无文件或目录 (右键文件/文件夹可发起传输)"
          >
            <el-table-column width="48">
              <template #default="{ row }">
                <el-icon v-if="row.is_dir" class="dir-icon"><FolderOpened /></el-icon>
                <el-icon v-else class="file-icon"><Document /></el-icon>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称">
              <template #default="{ row }">
                <span
                  v-if="row.is_dir"
                  class="clickable-name"
                  @dblclick="enterHostDir(row.name)"
                >
                  {{ row.name }}
                </span>
                <span v-else>{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="100">
              <template #default="{ row }">
                {{ row.is_dir ? '-' : formatSize(row.size) }}
              </template>
            </el-table-column>
            <el-table-column label="修改时间" width="160">
              <template #default="{ row }">
                {{ formatTime(row.mtime) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 右栏：访客虚拟机文件系统 (Guest VM) -->
      <div class="pane-card glass-card">
        <div class="pane-header">
          <div class="pane-header-top">
            <div class="pane-title">
              <span class="pulse-indicator guest-pulse" :class="{ 'offline': instanceStatus !== 'RUNNING' }"></span>
              虚拟机 (Guest)
            </div>
            
            <!-- 虚拟机智能地址栏 (仅在虚拟机运行时显示) -->
            <div v-if="instanceStatus === 'RUNNING'" class="address-bar-container">
              <!-- 编辑态：显示路径输入框 -->
              <el-input
                v-if="guestEditingPath"
                ref="guestInputRef"
                v-model="guestInputPath"
                size="small"
                placeholder="输入绝对路径，回车跳转"
                class="address-input"
                @keyup.enter="handleGuestPathSubmit"
                @blur="handleGuestPathSubmit"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>

              <!-- 非编辑态：显示面包屑路径 -->
              <div v-else class="address-breadcrumbs" @click="startGuestEdit">
                <el-icon class="folder-prefix"><Folder /></el-icon>
                <el-breadcrumb separator="/" @click.stop>
                  <el-breadcrumb-item>
                    <a @click.prevent="navigateGuest('/')">root</a>
                  </el-breadcrumb-item>
                  <el-breadcrumb-item v-for="(part, idx) in guestVisibleParts" :key="idx">
                    <span v-if="part.isEllipsis" class="ellipsis-node">...</span>
                    <a v-else @click.prevent="navigateGuestToIdx(part.originalIndex)">{{ part.name }}</a>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </div>
          </div>
        </div>

        <!-- 虚拟机未运行就绪时的占位符 -->
        <div v-if="instanceStatus !== 'RUNNING'" class="placeholder-card glass-placeholder guest-offline-placeholder">
          <el-icon class="placeholder-icon text-green"><FolderOpened /></el-icon>
          <h3>虚拟机网络及 SSH 未就绪</h3>
          <p class="desc-text">文件管理器需要虚拟机处于运行中且 SSH 服务正常响应。</p>
          <p>当前状态: <el-tag :type="statusTagType" size="small">{{ statusTextCn }}</el-tag></p>
          <el-button 
            type="success" 
            size="large" 
            class="glow-action-btn green-glow mini-btn" 
            :disabled="instanceStatus === 'STARTING' || instanceStatus === 'STOPPING'"
            @click="emit('start-instance')"
            style="margin-top: 14px;"
          >
            {{ instanceStatus === 'STARTING' ? '虚拟机启动中，请稍候...' : '启动虚拟机' }}
          </el-button>
        </div>

        <!-- 虚拟机运行中时的文件列表 -->
        <div v-else class="file-list-wrapper" v-loading="guestLoading" element-loading-background="rgba(20, 20, 25, 0.8)">
          <el-table
            ref="guestTableRef"
            :data="guestFiles"
            height="100%"
            highlight-current-row
            @current-change="handleGuestSelect"
            @row-contextmenu="handleGuestContextMenu"
            class="file-table"
            empty-text="暂无文件或目录 (右键文件/文件夹可发起传输)"
          >
            <el-table-column width="48">
              <template #default="{ row }">
                <el-icon v-if="row.is_dir" class="dir-icon guest-dir"><Folder /></el-icon>
                <el-icon v-else class="file-icon guest-file"><DocumentCopy /></el-icon>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称">
              <template #default="{ row }">
                <span
                  v-if="row.is_dir"
                  class="clickable-name"
                  @dblclick="enterGuestDir(row.name)"
                >
                  {{ row.name }}
                </span>
                <span v-else>{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="100">
              <template #default="{ row }">
                {{ row.is_dir ? '-' : formatSize(row.size) }}
              </template>
            </el-table-column>
            <el-table-column label="修改时间" width="160">
              <template #default="{ row }">
                {{ formatTime(row.mtime) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <!-- 传输进度对话框 -->
    <el-dialog
      v-model="showProgressDialog"
      title="文件传输进度"
      width="420px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="taskStatus !== 'RUNNING' && taskStatus !== 'PENDING'"
      class="custom-progress-dialog glass-dialog"
    >
      <div class="progress-details">
        <div class="progress-message">
          <p><strong>源路径:</strong> {{ currentTaskDetails.src }}</p>
          <p><strong>目的路径:</strong> {{ currentTaskDetails.dest }}</p>
        </div>

        <div class="progress-bar-container">
          <el-progress
            :percentage="taskProgress"
            :status="progressUiStatus"
            :stroke-width="12"
            striped
            striped-flow
          />
        </div>

        <div class="task-status-text">
          状态: 
          <el-tag :type="statusTagType">{{ taskStatus }}</el-tag>
        </div>

        <div v-if="taskErrorMsg" class="error-alert">
          <el-alert
            title="传输失败"
            type="error"
            :description="taskErrorMsg"
            show-icon
            :closable="false"
          />
        </div>
      </div>
      <template #footer>
        <el-button
          type="primary"
          :disabled="taskStatus === 'RUNNING' || taskStatus === 'PENDING'"
          @click="showProgressDialog = false"
        >
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 网页右键快捷上下文菜单 -->
    <div
      v-if="contextMenu.visible"
      class="custom-context-menu"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
      <div class="menu-item" @click="handleContextMenuTransfer">
        <el-icon><Upload /></el-icon>
        <span>传输</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { ElMessage } from "element-plus";
import {
  FolderOpened,
  Folder,
  Document,
  DocumentCopy,
  Upload,
} from "@element-plus/icons-vue";
import {
  fetchHostFiles,
  fetchGuestFiles,
  transferFile,
  fetchTaskStatus,
} from "@/api/endpoints";
import type { FileEntry } from "@/api/types";

const props = defineProps<{
  instanceId: string;
  instanceStatus: string;
}>();

const emit = defineEmits<{
  (e: "start-instance"): void;
}>();

const statusTextCn = computed(() => {
  const statusMap: Record<string, string> = {
    LOADING: "加载中...",
    STARTING: "启动中",
    RUNNING: "运行中",
    STOPPING: "停止中",
    STOPPED: "已停止",
  };
  return statusMap[props.instanceStatus] || props.instanceStatus;
});

const statusTagType = computed(() => {
  if (props.instanceStatus === "RUNNING") return "success";
  if (props.instanceStatus === "STARTING") return "warning";
  if (props.instanceStatus === "STOPPED") return "info";
  return "danger";
});

// 绑定根容器引用以精准计算右键绝对坐标
const fileManagerRef = ref<HTMLElement | null>(null);

// 引用 ElTable 组件实例，用于触发视觉选中行
const hostTableRef = ref<any>(null);
const guestTableRef = ref<any>(null);

// 宿主机文件系统数据与路径
const hostRelativePath = ref("");
const hostFiles = ref<FileEntry[]>([]);
const hostLoading = ref(false);
const selectedHostFile = ref<FileEntry | null>(null);
const hostInputPath = ref("");
const hostEditingPath = ref(false);
const hostInputRef = ref<any>(null);

// 访客机文件系统数据与路径
const guestCurrentPath = ref("/");
const guestFiles = ref<FileEntry[]>([]);
const guestLoading = ref(false);
const selectedGuestFile = ref<FileEntry | null>(null);
const guestInputPath = ref("");
const guestEditingPath = ref(false);
const guestInputRef = ref<any>(null);

// 网页自定义右键上下文菜单状态
const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  row: null as FileEntry | null,
  pane: "" as "host" | "guest",
});

// 双向同步路径输入框
watch(hostRelativePath, (newVal) => {
  hostInputPath.value = newVal;
}, { immediate: true });

watch(guestCurrentPath, (newVal) => {
  guestInputPath.value = newVal;
}, { immediate: true });

// 切换到编辑态并聚焦输入框
function startHostEdit() {
  hostEditingPath.value = true;
  nextTick(() => {
    hostInputRef.value?.focus();
  });
}

function startGuestEdit() {
  guestEditingPath.value = true;
  nextTick(() => {
    guestInputRef.value?.focus();
  });
}

// 提交地址栏修改并恢复面包屑状态
function handleHostPathSubmit() {
  handleHostPathInput();
  hostEditingPath.value = false;
}

function handleGuestPathSubmit() {
  handleGuestPathInput();
  guestEditingPath.value = false;
}

function handleHostPathInput() {
  let val = hostInputPath.value.trim().replace(/\/+/g, "/");
  if (val.length > 1 && val.endsWith("/")) {
    val = val.substring(0, val.length - 1);
  }
  
  if (hostRelativePath.value !== val) {
    hostRelativePath.value = val;
    loadHostFiles();
  }
}

function handleGuestPathInput() {
  let val = guestInputPath.value.trim().replace(/\/+/g, "/");
  if (!val.startsWith("/")) {
    val = "/" + val;
  }
  if (val.length > 1 && val.endsWith("/")) {
    val = val.substring(0, val.length - 1);
  }
  
  if (guestCurrentPath.value !== val) {
    guestCurrentPath.value = val;
    loadGuestFiles();
  }
}

// 右键事件响应：宿主机
function handleHostContextMenu(row: FileEntry, column: any, event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
  selectedHostFile.value = row;
  hostTableRef.value?.setCurrentRow(row);
  
  let x = event.clientX;
  let y = event.clientY;
  if (fileManagerRef.value) {
    const rect = fileManagerRef.value.getBoundingClientRect();
    x = event.clientX - rect.left;
    y = event.clientY - rect.top;
  }
  
  contextMenu.value = {
    visible: true,
    x,
    y,
    row,
    pane: "host",
  };
}

// 右键事件响应：虚拟机
function handleGuestContextMenu(row: FileEntry, column: any, event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();
  selectedGuestFile.value = row;
  guestTableRef.value?.setCurrentRow(row);
  
  let x = event.clientX;
  let y = event.clientY;
  if (fileManagerRef.value) {
    const rect = fileManagerRef.value.getBoundingClientRect();
    x = event.clientX - rect.left;
    y = event.clientY - rect.top;
  }
  
  contextMenu.value = {
    visible: true,
    x,
    y,
    row,
    pane: "guest",
  };
}

// 执行右键菜单传输操作
function handleContextMenuTransfer() {
  const menu = contextMenu.value;
  if (!menu.row) return;
  
  if (menu.pane === "host") {
    initiateTransfer("host_to_guest", menu.row);
  } else if (menu.pane === "guest") {
    initiateTransfer("guest_to_host", menu.row);
  }
  
  closeContextMenu();
}

function closeContextMenu() {
  contextMenu.value.visible = false;
}

// 传输进度控制
const showProgressDialog = ref(false);
const taskProgress = ref(0);
const taskStatus = ref("PENDING");
const taskErrorMsg = ref<string | null>(null);
const currentTaskDetails = ref({ src: "", dest: "" });

// 计算面包屑导航部分
const hostPathParts = ref<string[]>([]);
const guestPathParts = ref<string[]>([]);

watch(hostRelativePath, (newVal) => {
  if (!newVal || newVal === "/") hostPathParts.value = [];
  else hostPathParts.value = newVal.split("/").filter(Boolean);
}, { immediate: true });

watch(guestCurrentPath, (newVal) => {
  if (!newVal || newVal === "/") guestPathParts.value = [];
  else guestPathParts.value = newVal.split("/").filter(Boolean);
}, { immediate: true });

interface VisiblePart {
  name: string;
  originalIndex: number;
  isEllipsis: boolean;
}

function getVisibleParts(parts: string[]): VisiblePart[] {
  const maxVisible = 4; // 最多显示 4 个节点（不计 root 根节点）
  if (parts.length <= maxVisible) {
    return parts.map((name, index) => ({
      name,
      originalIndex: index,
      isEllipsis: false
    }));
  }
  
  // 节点过多，收缩中间部分
  return [
    { name: parts[0], originalIndex: 0, isEllipsis: false },
    { name: "...", originalIndex: -1, isEllipsis: true },
    ...parts.slice(parts.length - 2).map((name, index) => ({
      name,
      originalIndex: parts.length - 2 + index,
      isEllipsis: false
    }))
  ];
}

const hostVisibleParts = computed(() => getVisibleParts(hostPathParts.value));
const guestVisibleParts = computed(() => getVisibleParts(guestPathParts.value));

// 加载宿主机文件列表
async function loadHostFiles() {
  hostLoading.value = true;
  selectedHostFile.value = null;
  try {
    const data = await fetchHostFiles(hostRelativePath.value, props.instanceId);
    hostFiles.value = data.files;
    // 自动更新宿主机当前真实绝对路径
    hostRelativePath.value = data.current_path;
  } catch (error: any) {
    ElMessage.error(`加载宿主机文件失败: ${error.message || error}`);
  } finally {
    hostLoading.value = false;
  }
}

// 加载访客机文件列表
async function loadGuestFiles() {
  if (props.instanceStatus !== "RUNNING") {
    guestFiles.value = [];
    return;
  }
  guestLoading.value = true;
  selectedGuestFile.value = null;
  try {
    const data = await fetchGuestFiles(props.instanceId, guestCurrentPath.value);
    guestFiles.value = data.files;
  } catch (error: any) {
    ElMessage.error(`加载虚拟机文件失败: ${error.message || error}`);
  } finally {
    guestLoading.value = false;
  }
}

// 监听实例状态改变以加载或清除虚机文件列表
watch(() => props.instanceStatus, (newVal) => {
  if (newVal === "RUNNING") {
    loadGuestFiles();
  } else {
    guestFiles.value = [];
  }
});

// 宿主机目录双击深入
function enterHostDir(dirName: string) {
  if (hostRelativePath.value) {
    const separator = hostRelativePath.value.endsWith("/") ? "" : "/";
    hostRelativePath.value += `${separator}${dirName}`;
  } else {
    hostRelativePath.value = dirName;
  }
  loadHostFiles();
}

// 宿主机面包屑跳转
function navigateHost(path: string) {
  hostRelativePath.value = path;
  loadHostFiles();
}

function navigateHostToIdx(idx: number) {
  const parts = hostPathParts.value.slice(0, idx + 1);
  hostRelativePath.value = "/" + parts.join("/");
  loadHostFiles();
}

// 访客机目录双击深入
function enterGuestDir(dirName: string) {
  if (guestCurrentPath.value.endsWith("/")) {
    guestCurrentPath.value += dirName;
  } else {
    guestCurrentPath.value += `/${dirName}`;
  }
  loadGuestFiles();
}

// 访客机面包屑跳转
function navigateGuest(path: string) {
  guestCurrentPath.value = path;
  loadGuestFiles();
}

function navigateGuestToIdx(idx: number) {
  const parts = guestPathParts.value.slice(0, idx + 1);
  guestCurrentPath.value = "/" + parts.join("/");
  loadGuestFiles();
}

// 选择文件处理
function handleHostSelect(val: FileEntry | null) {
  selectedHostFile.value = val;
}

// 选择文件处理
function handleGuestSelect(val: FileEntry | null) {
  selectedGuestFile.value = val;
}

// 辅助格式化
function formatSize(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatTime(timestamp: number) {
  if (!timestamp) return "-";
  const date = new Date(timestamp * 1000);
  return date.toLocaleString("zh-CN", { hour12: false });
}

// 传输进度 UI 状态计算
const progressUiStatus = computed(() => {
  if (taskStatus.value === "SUCCESS") return "success";
  if (taskStatus.value === "FAILURE") return "exception";
  return "";
});

const statusTagType = computed(() => {
  if (taskStatus.value === "SUCCESS") return "success";
  if (taskStatus.value === "FAILURE") return "danger";
  if (taskStatus.value === "RUNNING") return "warning";
  return "info";
});

// 发起文件/目录传输
async function initiateTransfer(direction: "host_to_guest" | "guest_to_host", file: FileEntry) {
  let src = file.path;
  let dest = "";

  if (direction === "host_to_guest") {
    const fileName = file.name;
    const remoteDir = guestCurrentPath.value;
    dest = remoteDir.endsWith("/") ? remoteDir + fileName : remoteDir + "/" + fileName;
  } else {
    const fileName = file.name;
    dest = hostRelativePath.value.endsWith("/") 
      ? hostRelativePath.value + fileName 
      : hostRelativePath.value + "/" + fileName;
  }

  currentTaskDetails.value = { src, dest };
  taskStatus.value = "PENDING";
  taskProgress.value = 0;
  taskErrorMsg.value = null;
  showProgressDialog.value = true;

  try {
    const taskData = await transferFile(props.instanceId, direction, src, dest);
    pollTaskStatus(taskData.task_id);
  } catch (error: any) {
    taskStatus.value = "FAILURE";
    taskErrorMsg.value = error.message || error;
  }
}

// 轮询任务进度
function pollTaskStatus(taskId: string) {
  const timer = setInterval(async () => {
    try {
      const data = await fetchTaskStatus(taskId);
      taskStatus.value = data.status;
      taskProgress.value = data.progress;
      taskErrorMsg.value = data.error_msg;

      if (data.status === "SUCCESS") {
        clearInterval(timer);
        ElMessage.success("传输成功！");
        loadHostFiles();
        loadGuestFiles();
      } else if (data.status === "FAILURE") {
        clearInterval(timer);
        ElMessage.error(`传输失败: ${data.error_msg}`);
      }
    } catch (error: any) {
      clearInterval(timer);
      taskStatus.value = "FAILURE";
      taskErrorMsg.value = error.message || error;
    }
  }, 1500);
}

// 监听实例 ID 变更，重新加载文件列表
watch(() => props.instanceId, () => {
  hostRelativePath.value = "";
  guestCurrentPath.value = "/";
  loadHostFiles();
  loadGuestFiles();
});

onMounted(() => {
  loadHostFiles();
  loadGuestFiles();
  
  // 注册全局事件以便关闭上下文菜单
  window.addEventListener("click", closeContextMenu);
  window.addEventListener("contextmenu", closeContextMenu);
});

onBeforeUnmount(() => {
  window.removeEventListener("click", closeContextMenu);
  window.removeEventListener("contextmenu", closeContextMenu);
});
</script>

<style scoped>
.file-manager-wrapper {
  background: transparent;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.panes-wrapper {
  display: flex;
  gap: 24px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.pane-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  overflow: hidden;
  height: 100%;
  min-height: 0;
}

.glass-card {
  background: rgba(23, 23, 37, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
  transition: border-color 0.3s ease;
}

.glass-card:hover {
  border-color: rgba(56, 189, 248, 0.25);
}

.pane-header {
  padding: 14px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.pane-title {
  font-size: 1.05rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.pulse-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.host-pulse {
  background-color: #38bdf8;
  box-shadow: 0 0 10px #38bdf8;
  animation: pulse-glow 2s infinite;
}

.guest-pulse {
  background-color: #10b981;
  box-shadow: 0 0 10px #10b981;
  animation: pulse-glow 2s infinite;
}

@keyframes pulse-glow {
  0% { transform: scale(0.9); opacity: 0.6; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.6; }
}

.file-list-wrapper {
  flex: 1;
  padding: 12px;
  overflow: hidden;
  min-height: 0;
}

.file-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.02);
  --el-table-row-hover-bg-color: rgba(255, 255, 255, 0.04);
  --el-table-border-color: rgba(255, 255, 255, 0.04);
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #94a3b8;
  border-radius: 8px;
}

.clickable-name {
  cursor: pointer;
  color: #38bdf8;
  font-weight: 500;
  transition: color 0.2s ease;
}

.clickable-name:hover {
  color: #7dd3fc;
  text-decoration: underline;
}

.dir-icon {
  font-size: 1.35rem;
  color: #eab308;
}

.dir-icon.guest-dir {
  color: #10b981;
}

.file-icon {
  font-size: 1.35rem;
  color: #a855f7;
}

.file-icon.guest-file {
  color: #6366f1;
}

/* 进度对话框 */
:deep(.custom-progress-dialog) {
  background: rgba(20, 20, 30, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
}

:deep(.custom-progress-dialog .el-dialog__title) {
  color: #f1f5f9;
  font-weight: 600;
}

.progress-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: #cbd5e1;
}

.progress-message p {
  margin: 6px 0;
  font-size: 0.9rem;
  word-break: break-all;
}

.progress-bar-container {
  margin: 10px 0;
}

.task-status-text {
  font-size: 0.9rem;
  margin-bottom: 8px;
}

.error-alert {
  margin-top: 10px;
}

:deep(.el-table__body tr.current-row>td.el-table__cell) {
  background-color: rgba(56, 189, 248, 0.15) !important;
  border-top: 1px solid rgba(56, 189, 248, 0.3);
  border-bottom: 1px solid rgba(56, 189, 248, 0.3);
}

.pane-header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

/* 智能地址栏统一容器 */
.address-bar-container {
  flex: 1;
  min-width: 0;
  max-width: 380px;
}

/* 面包屑导航的默认状态模拟输入框框体 */
.address-breadcrumbs {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  cursor: text; /* 模拟可编辑的光标样式 */
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-sizing: border-box;
}

.address-breadcrumbs:hover {
  border-color: rgba(56, 189, 248, 0.45);
  background: rgba(255, 255, 255, 0.06);
}

.folder-prefix {
  color: #64748b;
  font-size: 0.95rem;
  flex-shrink: 0;
}

/* 面包屑内的链接样式 */
:deep(.el-breadcrumb) {
  display: inline-flex;
  align-items: center;
  font-size: 0.85rem;
}

:deep(.el-breadcrumb__item) a {
  color: #94a3b8 !important;
  cursor: pointer;
  font-weight: 500;
  transition: color 0.2s ease;
}

.ellipsis-node {
  color: #64748b;
  cursor: default;
  user-select: none;
  font-weight: bold;
  padding: 0 2px;
}

:deep(.el-breadcrumb__item) a:hover {
  color: #38bdf8 !important;
}

/* 地址编辑状态的输入框美化 */
.address-input {
  width: 100%;
}

:deep(.address-input .el-input__wrapper) {
  height: 32px;
  box-sizing: border-box;
  background-color: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(56, 189, 248, 0.75) !important;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.3) !important;
}

:deep(.address-input .el-input__inner) {
  color: #cbd5e1 !important;
  font-size: 0.85rem;
}

/* 网页自定义右键上下文菜单样式 */
.custom-context-menu {
  position: absolute;
  z-index: 10000;
  min-width: 120px;
  background: rgba(23, 23, 37, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
  padding: 4px 0;
  backdrop-filter: blur(12px);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 0.9rem;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: rgba(56, 189, 248, 0.18);
  color: #38bdf8;
}

/* 虚拟机未启动占位符样式 */
.guest-offline-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: rgba(255, 255, 255, 0.01) !important;
  border: 1.5px dashed rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  margin: 20px;
  text-align: center;
  box-sizing: border-box;
}

.guest-offline-placeholder .placeholder-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.text-green {
  color: #10b981;
  filter: drop-shadow(0 0 10px rgba(16, 185, 129, 0.3));
}

.guest-offline-placeholder h3 {
  font-size: 1.15rem;
  margin: 0 0 10px 0;
  color: #f1f5f9;
}

.guest-offline-placeholder p {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 4px 0;
}

.guest-offline-placeholder .desc-text {
  max-width: 320px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.glow-action-btn {
  font-weight: 600;
  transition: all 0.3s ease;
}

.glow-action-btn:hover {
  transform: translateY(-1px);
}

.green-glow {
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.25);
}

.green-glow:hover {
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
}

.pulse-indicator.offline {
  background-color: #64748b !important;
  box-shadow: none !important;
  animation: none !important;
}
</style>
