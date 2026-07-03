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
                    <a
                      v-else
                      class="breadcrumb-link"
                      :title="part.fullName"
                      @click.prevent="navigateHostToIdx(part.originalIndex)"
                    >{{ part.name }}</a>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </div>
            <div class="pane-actions">
              <input
                ref="hostUploadInputRef"
                type="file"
                multiple
                hidden
                @change="handleHostUploadPick"
              />
              <el-button size="small" :loading="hostUploading" @click="triggerHostUpload">
                <el-icon><Upload /></el-icon>
                上传
              </el-button>
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
              <span class="pulse-indicator guest-pulse" :class="{ 'offline': guestVfsMode === 'offline' }"></span>
              虚拟机 (Guest)
              <el-tag v-if="guestVfsMode === 'offline'" size="small" type="info" effect="plain" class="mode-tag">
                离线只读
              </el-tag>
            </div>
            
            <!-- 访客机地址栏：运行中(在线)或已停止(离线) -->
            <div v-if="isGuestBrowseable" class="address-bar-container">
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
                    <a
                      v-else
                      class="breadcrumb-link"
                      :title="part.fullName"
                      @click.prevent="navigateGuestToIdx(part.originalIndex)"
                    >{{ part.name }}</a>
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </div>
            <div v-if="guestCanTransfer" class="pane-actions">
              <el-button size="small" @click="createGuestFolder">
                <el-icon><FolderAdd /></el-icon>
                新建文件夹
              </el-button>
            </div>
          </div>
        </div>

        <!-- 启动/停止过渡态 -->
        <div v-if="isGuestTransitioning" class="placeholder-card glass-placeholder guest-offline-placeholder">
          <el-icon class="placeholder-icon text-green"><FolderOpened /></el-icon>
          <h3>虚拟机状态切换中</h3>
          <p class="desc-text">请等待虚拟机完成{{ props.instanceStatus === 'STARTING' ? '启动' : '停止' }}后再浏览文件系统。</p>
          <p>当前状态: <el-tag :type="vmStatusTagType" size="small">{{ vmStatusTextCn }}</el-tag></p>
        </div>

        <!-- 在线 / 离线文件列表 -->
        <div v-else-if="isGuestBrowseable" class="file-list-wrapper" v-loading="guestLoading" element-loading-background="rgba(20, 20, 25, 0.8)">
          <el-table
            ref="guestTableRef"
            :data="guestFiles"
            height="100%"
            highlight-current-row
            @current-change="handleGuestSelect"
            @row-contextmenu="handleGuestContextMenu"
            class="file-table"
            :empty-text="guestEmptyText"
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
          <div v-if="guestVfsMode === 'offline'" class="offline-hint">
            离线模式：浏览 rootfs.img 磁盘内容。启动虚拟机前会自动卸载；传输需在线 SSH。
            <el-button type="success" link @click="emit('start-instance')">启动虚拟机</el-button>
          </div>
        </div>
      </div>
    </div>

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
      <template v-if="contextMenu.pane === 'guest' && guestCanTransfer">
        <div class="menu-item" @click="handleContextMenuRename">
          <el-icon><EditPen /></el-icon>
          <span>重命名</span>
        </div>
        <div class="menu-item menu-item-danger" @click="handleContextMenuDelete">
          <el-icon><Delete /></el-icon>
          <span>删除</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  FolderOpened,
  Folder,
  Document,
  DocumentCopy,
  Upload,
  FolderAdd,
  EditPen,
  Delete,
} from "@element-plus/icons-vue";
import {
  fetchHostFiles,
  fetchGuestFiles,
  transferFile,
  uploadHostFile,
  guestFsOp,
} from "@/api/endpoints";
import type { FileEntry } from "@/api/types";
import { useTaskStore } from "@/stores/tasks";

const props = defineProps<{
  instanceId: string;
  instanceStatus: string;
}>();

const emit = defineEmits<{
  (e: "start-instance"): void;
}>();

const taskStore = useTaskStore();

const vmStatusTextCn = computed(() => {
  const statusMap: Record<string, string> = {
    LOADING: "加载中...",
    STARTING: "启动中",
    RUNNING: "运行中",
    STOPPING: "停止中",
    STOPPED: "已停止",
  };
  return statusMap[props.instanceStatus] || props.instanceStatus;
});

const vmStatusTagType = computed(() => {
  if (props.instanceStatus === "RUNNING") return "success";
  if (props.instanceStatus === "STARTING") return "warning";
  if (props.instanceStatus === "STOPPED") return "info";
  return "danger";
});

const guestVfsMode = computed(() => {
  if (props.instanceStatus === "RUNNING") return "online";
  if (props.instanceStatus === "STOPPED") return "offline";
  return "unavailable";
});

const isGuestTransitioning = computed(() =>
  props.instanceStatus === "STARTING" || props.instanceStatus === "STOPPING"
);

const isGuestBrowseable = computed(() =>
  props.instanceStatus === "RUNNING" || props.instanceStatus === "STOPPED"
);

const guestCanTransfer = computed(() => props.instanceStatus === "RUNNING");

const guestEmptyText = computed(() =>
  guestVfsMode.value === "offline"
    ? "暂无文件或目录 (离线只读，传输需启动虚拟机)"
    : "暂无文件或目录 (右键文件/文件夹可发起传输)"
);

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
const hostEffectiveRootPath = ref("");
const hostUploadInputRef = ref<HTMLInputElement | null>(null);
const hostUploading = ref(false);

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
    loadGuestFilesList();
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
  if (!guestCanTransfer.value) {
    return;
  }
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
    if (!guestCanTransfer.value) {
      ElMessage.warning("虚拟机未运行，无法传输到访客机");
      closeContextMenu();
      return;
    }
    initiateTransfer("host_to_guest", menu.row);
  } else if (menu.pane === "guest") {
    initiateTransfer("guest_to_host", menu.row);
  }
  
  closeContextMenu();
}

async function createGuestFolder() {
  if (!guestCanTransfer.value) return;
  try {
    const { value } = await ElMessageBox.prompt("输入新文件夹名称", "新建文件夹", {
      confirmButtonText: "创建",
      cancelButtonText: "取消",
      inputPattern: /^[^/\\]+$/,
      inputErrorMessage: "名称不能包含路径分隔符",
    });
    const name = value.trim();
    if (!name) return;
    const target = guestCurrentPath.value.endsWith("/")
      ? `${guestCurrentPath.value}${name}`
      : `${guestCurrentPath.value}/${name}`;
    await guestFsOp(props.instanceId, "mkdir", target);
    ElMessage.success("文件夹已创建");
    await loadGuestFilesList();
  } catch (error: unknown) {
    if (error !== "cancel" && (error as Error)?.message !== "cancel") {
      ElMessage.error(error instanceof Error ? error.message : "创建失败");
    }
  }
}

async function handleContextMenuRename() {
  const menu = contextMenu.value;
  if (!menu.row || menu.pane !== "guest" || !guestCanTransfer.value) return;
  closeContextMenu();
  try {
    const { value } = await ElMessageBox.prompt("输入新名称", "重命名", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputValue: menu.row.name,
      inputPattern: /^[^/\\]+$/,
      inputErrorMessage: "名称不能包含路径分隔符",
    });
    const newName = value.trim();
    if (!newName || newName === menu.row.name) return;
    const parent = guestCurrentPath.value.replace(/\/$/, "") || "";
    const dest = parent === "" || parent === "/" ? `/${newName}` : `${parent}/${newName}`;
    await guestFsOp(props.instanceId, "rename", menu.row.path, dest);
    ElMessage.success("重命名成功");
    await loadGuestFilesList();
  } catch (error: unknown) {
    if (error !== "cancel" && (error as Error)?.message !== "cancel") {
      ElMessage.error(error instanceof Error ? error.message : "重命名失败");
    }
  }
}

async function handleContextMenuDelete() {
  const menu = contextMenu.value;
  if (!menu.row || menu.pane !== "guest" || !guestCanTransfer.value) return;
  closeContextMenu();
  try {
    await ElMessageBox.confirm(
      `确定删除「${menu.row.name}」？此操作不可撤销。`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除" }
    );
    await guestFsOp(props.instanceId, "delete", menu.row.path);
    ElMessage.success("已删除");
    await loadGuestFilesList();
  } catch (error: unknown) {
    if (error !== "cancel" && (error as Error)?.message !== "cancel") {
      ElMessage.error(error instanceof Error ? error.message : "删除失败");
    }
  }
}

function closeContextMenu() {
  contextMenu.value.visible = false;
}

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
  fullName: string;
  originalIndex: number;
  isEllipsis: boolean;
}

function formatSegmentLabel(name: string): string {
  if (name.startsWith("inst_") && name.length > 22) {
    return `inst_${name.slice(5, 13)}…${name.slice(-4)}`;
  }
  if (name.length > 24) {
    return `${name.slice(0, 20)}…`;
  }
  return name;
}

function getVisibleParts(parts: string[]): VisiblePart[] {
  const maxVisible = 4; // 最多显示 4 个节点（不计 root 根节点）
  if (parts.length <= maxVisible) {
    return parts.map((name, index) => ({
      name: formatSegmentLabel(name),
      fullName: name,
      originalIndex: index,
      isEllipsis: false,
    }));
  }

  // 节点过多，收缩中间部分
  const first = parts[0];
  const tail = parts.slice(parts.length - 2);
  return [
    { name: formatSegmentLabel(first), fullName: first, originalIndex: 0, isEllipsis: false },
    { name: "...", fullName: "...", originalIndex: -1, isEllipsis: true },
    ...tail.map((name, index) => ({
      name: formatSegmentLabel(name),
      fullName: name,
      originalIndex: parts.length - 2 + index,
      isEllipsis: false,
    })),
  ];
}

// 宿主机路径在实例上下文中只展示有效根目录下的相对路径
function countPathPrefixSegments(fullPath: string, rootPath: string): number {
  const normalize = (value: string) => value.replace(/\/+$/, "") || "/";
  const full = normalize(fullPath);
  const root = normalize(rootPath);
  if (root === "/") return 0;
  if (full === root) return root.split("/").filter(Boolean).length;
  if (full.startsWith(`${root}/`)) return root.split("/").filter(Boolean).length;
  return 0;
}

const hostInstancePrefixLength = computed(() => {
  if (!hostEffectiveRootPath.value) return 0;
  return countPathPrefixSegments(hostRelativePath.value, hostEffectiveRootPath.value);
});

const hostDisplayParts = computed(() => {
  const prefixLen = hostInstancePrefixLength.value;
  return hostPathParts.value.slice(prefixLen);
});

const hostVisibleParts = computed(() => getVisibleParts(hostDisplayParts.value));
const guestVisibleParts = computed(() => getVisibleParts(guestPathParts.value));

// 加载宿主机文件列表
async function loadHostFiles() {
  hostLoading.value = true;
  selectedHostFile.value = null;
  try {
    const data = await fetchHostFiles(hostRelativePath.value, props.instanceId);
    hostFiles.value = data.files;
    if (data.host_root_path) {
      hostEffectiveRootPath.value = data.host_root_path;
    }
    hostRelativePath.value = data.current_path;
  } catch (error: any) {
    ElMessage.error(`加载宿主机文件失败: ${error.message || error}`);
  } finally {
    hostLoading.value = false;
  }
}

// 加载访客机文件列表（运行中=在线 SSH，已停止=离线 guestmount）
async function loadGuestFilesList() {
  if (!isGuestBrowseable.value) {
    guestFiles.value = [];
    return;
  }
  guestLoading.value = true;
  selectedGuestFile.value = null;
  const mode = guestVfsMode.value === "offline" ? "offline" : "online";
  try {
    const data = await fetchGuestFiles(props.instanceId, guestCurrentPath.value, mode);
    guestFiles.value = data.files;
  } catch (error: any) {
    ElMessage.error(`加载虚拟机文件失败: ${error.message || error}`);
  } finally {
    guestLoading.value = false;
  }
}

// 监听实例状态改变以切换在线/离线浏览
watch(() => props.instanceStatus, () => {
  if (isGuestBrowseable.value) {
    loadGuestFilesList();
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
  if (path === "/") {
    hostRelativePath.value = hostEffectiveRootPath.value || "";
  } else {
    hostRelativePath.value = path;
  }
  loadHostFiles();
}

function navigateHostToIdx(displayIdx: number) {
  const prefixLen = hostInstancePrefixLength.value;
  const parts = hostPathParts.value.slice(0, prefixLen + displayIdx + 1);
  hostRelativePath.value = parts.length ? `/${parts.join("/")}` : "";
  loadHostFiles();
}

// 访客机目录双击深入
function enterGuestDir(dirName: string) {
  if (guestCurrentPath.value.endsWith("/")) {
    guestCurrentPath.value += dirName;
  } else {
    guestCurrentPath.value += `/${dirName}`;
  }
  loadGuestFilesList();
}

// 访客机面包屑跳转
function navigateGuest(path: string) {
  guestCurrentPath.value = path;
  loadGuestFilesList();
}

function navigateGuestToIdx(idx: number) {
  const parts = guestPathParts.value.slice(0, idx + 1);
  guestCurrentPath.value = "/" + parts.join("/");
  loadGuestFilesList();
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

function triggerHostUpload() {
  hostUploadInputRef.value?.click();
}

async function handleHostUploadPick(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (!files.length) return;

  hostUploading.value = true;
  let uploaded = 0;
  try {
    for (const file of files) {
      const exists = hostFiles.value.some((f) => f.name === file.name && !f.is_dir);
      if (exists) {
        try {
          await ElMessageBox.confirm(
            `当前目录已存在 "${file.name}"，是否覆盖？`,
            "覆盖确认",
            { confirmButtonText: "覆盖", cancelButtonText: "跳过", type: "warning" }
          );
        } catch {
          continue;
        }
      }
      await uploadHostFile(file, hostRelativePath.value, props.instanceId);
      uploaded += 1;
    }
    if (uploaded > 0) {
      ElMessage.success(`已上传 ${uploaded} 个文件`);
      await loadHostFiles();
    }
  } catch (error: unknown) {
    ElMessage.error(error instanceof Error ? error.message : "上传失败");
  } finally {
    hostUploading.value = false;
  }
}

// 发起文件/目录传输
async function initiateTransfer(direction: "host_to_guest" | "guest_to_host", file: FileEntry) {
  if (!guestCanTransfer.value) {
    ElMessage.warning("文件传输需要虚拟机处于运行中");
    return;
  }
  const fileName = file.name;
  let src = file.path;
  let dest = "";

  if (direction === "host_to_guest") {
    const remoteDir = guestCurrentPath.value;
    dest = remoteDir.endsWith("/") ? remoteDir + fileName : remoteDir + "/" + fileName;
  } else {
    dest = hostRelativePath.value.endsWith("/") 
      ? hostRelativePath.value + fileName 
      : hostRelativePath.value + "/" + fileName;
  }

  // 存在时询问是否覆盖
  let exists = false;
  if (direction === "host_to_guest") {
    exists = guestFiles.value.some(f => f.name === fileName && !f.is_dir);
  } else {
    exists = hostFiles.value.some(f => f.name === fileName && !f.is_dir);
  }

  if (exists) {
    try {
      await ElMessageBox.confirm(
        `目标位置已存在同名文件 "${fileName}"，是否确定覆盖？`,
        "覆盖确认",
        {
          confirmButtonText: "覆盖",
          cancelButtonText: "取消",
          type: "warning",
        }
      );
    } catch {
      // 用户取消了传输
      return;
    }
  }

  const directionLabel = direction === "host_to_guest" ? "宿主机 → 访客机" : "访客机 → 宿主机";

  try {
    const taskData = await transferFile(props.instanceId, direction, src, dest);
    taskStore.trackTask(taskData.task_id, {
      label: "文件传输",
      detail: `${directionLabel}: ${fileName}`,
      taskType: "FILE_TRANSFER",
      successMessage: "传输成功",
      onSuccess: () => {
        loadHostFiles();
        loadGuestFilesList();
      },
    });
  } catch (error: unknown) {
    ElMessage.error(error instanceof Error ? error.message : "传输任务提交失败");
  }
}

// 监听实例 ID 变更，重新加载文件列表
watch(() => props.instanceId, () => {
  hostRelativePath.value = "";
  hostEffectiveRootPath.value = "";
  guestCurrentPath.value = "/";
  loadHostFiles();
  loadGuestFilesList();
});

onMounted(() => {
  loadHostFiles();
  loadGuestFilesList();
  
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
  background: var(--fsems-bg-elevated);
  border: 1px solid var(--fsems-border);
  backdrop-filter: blur(16px);
  box-shadow: var(--fsems-shadow);
  transition: border-color 0.3s ease;
}

.glass-card:hover {
  border-color: color-mix(in srgb, var(--fsems-accent) 35%, var(--fsems-border));
}

.pane-header {
  padding: 14px 20px;
  background: var(--fsems-bg-card);
  border-bottom: 1px solid var(--fsems-border);
}

.pane-title {
  font-size: 1.05rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  color: var(--fsems-text);
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
  --el-table-header-bg-color: var(--fsems-bg-card);
  --el-table-row-hover-bg-color: color-mix(in srgb, var(--fsems-accent) 8%, transparent);
  --el-table-border-color: var(--fsems-border);
  --el-table-text-color: var(--fsems-text);
  --el-table-header-text-color: var(--fsems-text);
  border-radius: 8px;
}

.clickable-name {
  cursor: pointer;
  color: var(--fsems-accent);
  font-weight: 500;
  transition: color 0.2s ease;
}

.clickable-name:hover {
  color: color-mix(in srgb, var(--fsems-accent) 80%, white);
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
  background: var(--fsems-bg-elevated);
  backdrop-filter: blur(20px);
  border: 1px solid var(--fsems-border);
  border-radius: 16px;
}

:deep(.custom-progress-dialog .el-dialog__title) {
  color: var(--fsems-text);
  font-weight: 600;
}

.progress-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--fsems-text-muted);
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

.pane-actions {
  flex-shrink: 0;
}

/* 智能地址栏统一容器 */
.address-bar-container {
  flex: 1;
  min-width: 0;
}

/* 面包屑导航的默认状态模拟输入框框体 */
.address-breadcrumbs {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 12px;
  background: var(--fsems-bg-card);
  border: 1px solid var(--fsems-border);
  border-radius: 8px;
  cursor: text;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-sizing: border-box;
}

.address-breadcrumbs:hover {
  border-color: color-mix(in srgb, var(--fsems-accent) 45%, var(--fsems-border));
  background: var(--fsems-bg-elevated);
}

.folder-prefix {
  color: var(--fsems-text-dim);
  font-size: 0.95rem;
  flex-shrink: 0;
}

/* 面包屑内的链接样式 */
:deep(.el-breadcrumb) {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  min-width: 0;
  overflow: hidden;
  font-size: 0.85rem;
}

:deep(.el-breadcrumb__item) {
  float: none;
  flex-shrink: 1;
  min-width: 0;
  max-width: 140px;
}

:deep(.el-breadcrumb__item .el-breadcrumb__inner) {
  display: inline-flex;
  max-width: 100%;
  overflow: hidden;
}

.breadcrumb-link,
:deep(.el-breadcrumb__item) a {
  color: var(--fsems-text-muted) !important;
  cursor: pointer;
  font-weight: 500;
  transition: color 0.2s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 100%;
}

.ellipsis-node {
  color: var(--fsems-text-dim);
  cursor: default;
  user-select: none;
  font-weight: bold;
  padding: 0 2px;
}

:deep(.el-breadcrumb__item) a:hover {
  color: var(--fsems-accent) !important;
}

/* 地址编辑状态的输入框美化 */
.address-input {
  width: 100%;
}

:deep(.address-input .el-input__wrapper) {
  height: 32px;
  box-sizing: border-box;
  background-color: var(--fsems-bg-elevated) !important;
  border: 1px solid color-mix(in srgb, var(--fsems-accent) 55%, var(--fsems-border)) !important;
  box-shadow: none !important;
}

:deep(.address-input .el-input__inner) {
  color: var(--fsems-text) !important;
  font-size: 0.85rem;
}

/* 网页自定义右键上下文菜单样式 */
.custom-context-menu {
  position: absolute;
  z-index: 10000;
  min-width: 120px;
  background: var(--fsems-bg-elevated);
  border: 1px solid var(--fsems-border);
  border-radius: 8px;
  box-shadow: var(--fsems-shadow);
  padding: 4px 0;
  backdrop-filter: blur(12px);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 0.9rem;
  color: var(--fsems-text);
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: color-mix(in srgb, var(--fsems-accent) 12%, transparent);
  color: var(--fsems-accent);
}

.menu-item-danger:hover {
  background: color-mix(in srgb, var(--fsems-danger) 12%, transparent);
  color: var(--fsems-danger);
}

.guest-offline-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: var(--fsems-bg-card) !important;
  border: 1.5px dashed var(--fsems-border);
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
  color: var(--fsems-success);
}

.guest-offline-placeholder h3 {
  font-size: 1.15rem;
  margin: 0 0 10px 0;
  color: var(--fsems-text);
}

.guest-offline-placeholder p {
  font-size: 0.85rem;
  color: var(--fsems-text-dim);
  margin: 4px 0;
}

.guest-offline-placeholder .desc-text {
  max-width: 320px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.mode-tag {
  margin-left: 8px;
  vertical-align: middle;
}

.offline-hint {
  flex-shrink: 0;
  padding: 8px 12px;
  font-size: 0.82rem;
  color: var(--fsems-text-dim);
  border-top: 1px solid var(--fsems-border);
  background: color-mix(in srgb, var(--fsems-success) 8%, transparent);
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
  background-color: var(--fsems-text-dim) !important;
  box-shadow: none !important;
  animation: none !important;
}
</style>
