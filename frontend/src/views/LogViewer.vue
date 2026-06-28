<template>
  <div class="log-viewer-page">
    <header class="header">
      <div class="header-left">
        <el-button @click="router.push('/instances')">返回实例列表</el-button>
        <span class="title">系统前后端日志</span>
      </div>
      <el-tag type="info">FSEMS 日志控制台</el-tag>
    </header>

    <div class="content-card">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 后端日志 Tab -->
        <el-tab-pane label="后端系统日志" name="backend">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-radio-group v-model="backendType" @change="loadBackendLogs">
                <el-radio-button value="fastapi">FastAPI (API服务)</el-radio-button>
                <el-radio-button value="celery">Celery (异步任务)</el-radio-button>
              </el-radio-group>

              <span class="tool-label">行数:</span>
              <el-select v-model="backendLines" style="width: 100px" @change="loadBackendLogs">
                <el-option :value="50" label="50 行" />
                <el-option :value="100" label="100 行" />
                <el-option :value="200" label="200 行" />
                <el-option :value="500" label="500 行" />
                <el-option :value="1000" label="1000 行" />
              </el-select>

              <el-input
                v-model="backendSearch"
                placeholder="过滤日志内容..."
                style="width: 220px; margin-left: 12px"
                clearable
              />
            </div>

            <div class="toolbar-right">
              <el-checkbox v-model="autoScroll" style="margin-right: 12px">自动滚动到底部</el-checkbox>
              <el-button type="primary" :loading="loadingBackend" @click="loadBackendLogs">
                刷新日志
              </el-button>
            </div>
          </div>

          <!-- 模拟终端日志显示 -->
          <div ref="terminalEl" class="terminal-container">
            <template v-if="filteredBackendLines.length > 0">
              <div v-for="(line, idx) in filteredBackendLines" :key="idx" class="terminal-line">
                <span class="line-num">{{ idx + 1 }}</span>
                <span class="line-content" :class="getLineClass(line)">{{ line }}</span>
              </div>
            </template>
            <div v-else class="empty-terminal">
              {{ loadingBackend ? "正在加载日志..." : "暂无匹配的日志记录" }}
            </div>
          </div>
          <div class="terminal-footer">
            共 {{ backendTotalLines }} 行日志 (已载入后 {{ backendLines }} 行)
          </div>
        </el-tab-pane>

        <!-- 前端日志 Tab -->
        <el-tab-pane label="前端客户端日志" name="frontend">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-button type="danger" plain @click="triggerTestError">
                触发测试错误 (验证上报)
              </el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="primary" :loading="loadingFrontend" @click="loadFrontendLogs">
                刷新上报
              </el-button>
            </div>
          </div>

          <el-table :data="frontendLogs" style="width: 100%" v-loading="loadingFrontend" stripe>
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-container">
                  <h4>异常调用栈 (Stack Trace):</h4>
                  <pre class="stack-trace">{{ row.stack || "无堆栈信息" }}</pre>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="id" label="ID" width="70" align="center" />
            <el-table-column prop="level" label="级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getFrontendLevelType(row.level)">
                  {{ String(row.level).toUpperCase() }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="日志消息/错误原因" min-width="250" show-overflow-tooltip />
            <el-table-column prop="url" label="触发页面 URL" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_at" label="时间 (UTC)" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="frontendPage"
              v-model:page-size="frontendLimit"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              :total="frontendTotal"
              @size-change="loadFrontendLogs"
              @current-change="loadFrontendLogs"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { fetchBackendLogs, fetchFrontendLogs } from "@/api/endpoints";
import type { FrontendLog } from "@/api/types";

const router = useRouter();

const activeTab = ref("backend");

// 后端日志状态
const backendType = ref<"fastapi" | "celery">("fastapi");
const backendLines = ref(100);
const backendSearch = ref("");
const backendTotalLines = ref(0);
const backendLinesData = ref<string[]>([]);
const loadingBackend = ref(false);
const autoScroll = ref(true);
const terminalEl = ref<HTMLElement | null>(null);
let backendTimer: ReturnType<typeof setInterval> | null = null;

// 过滤后的后端日志
const filteredBackendLines = computed(() => {
  // 日志展示：接口返回的是 reverse order (最新在最前)
  // 为了符合终端阅读习惯（最早在上，最新在下），我们在展示时再次翻转回 chronological order
  const chronoLines = [...backendLinesData.value].reverse();
  if (!backendSearch.value) return chronoLines;
  const q = backendSearch.value.toLowerCase();
  return chronoLines.filter(line => line.toLowerCase().includes(q));
});

// 前端日志状态
const frontendLogs = ref<FrontendLog[]>([]);
const loadingFrontend = ref(false);
const frontendTotal = ref(0);
const frontendPage = ref(1);
const frontendLimit = ref(20);

// 后端日志等级高亮类
function getLineClass(line: string) {
  if (line.includes("ERROR") || line.includes("CRITICAL")) return "text-danger";
  if (line.includes("WARNING") || line.includes("WARN")) return "text-warning";
  if (line.includes("INFO")) return "text-info";
  if (line.includes("DEBUG")) return "text-muted";
  return "";
}

function getFrontendLevelType(level: string) {
  const l = String(level).toUpperCase();
  if (l === "ERROR") return "danger";
  if (l === "WARN" || l === "WARNING") return "warning";
  return "info";
}

async function loadBackendLogs() {
  loadingBackend.value = true;
  try {
    const data = await fetchBackendLogs(backendType.value, backendLines.value, 0);
    backendTotalLines.value = data.total_lines;
    backendLinesData.value = data.lines;
    
    if (autoScroll.value) {
      await nextTick();
      if (terminalEl.value) {
        terminalEl.value.scrollTop = terminalEl.value.scrollHeight;
      }
    }
  } catch (e: any) {
    ElMessage.error(e.message || "获取后端日志失败");
  } finally {
    loadingBackend.value = false;
  }
}

async function loadFrontendLogs() {
  loadingFrontend.value = true;
  try {
    const offset = (frontendPage.value - 1) * frontendLimit.value;
    const data = await fetchFrontendLogs(frontendLimit.value, offset);
    frontendLogs.value = data.logs;
    // 由于是分页接口，我们需要简单计算总条数
    // 在这个精简系统中，如果是第一页且少于 Limit，直接作为 Total；否则在 logs 列表中拿到最大的 virtual ID 即可估算
    if (frontendLogs.value.length === 0) {
      frontendTotal.value = 0;
    } else {
      // logs[0] 是最新一条日志（即 ID 最大的那条）
      frontendTotal.value = frontendLogs.value[0].id;
    }
  } catch (e: any) {
    ElMessage.error(e.message || "获取前端日志失败");
  } finally {
    loadingFrontend.value = false;
  }
}

function onTabChange(tab: string | number) {
  if (tab === "backend") {
    loadBackendLogs();
    startBackendPoll();
  } else {
    stopBackendPoll();
    loadFrontendLogs();
  }
}

function startBackendPoll() {
  stopBackendPoll();
  // 5秒自动刷新后端日志
  backendTimer = setInterval(() => {
    loadBackendLogs();
  }, 5000);
}

function stopBackendPoll() {
  if (backendTimer) {
    clearInterval(backendTimer);
    backendTimer = null;
  }
}

function triggerTestError() {
  // 故意触发一个测试用 Runtime Error，以便前端的全局 Exception Catcher 捕获并上报给后端
  ElMessage.warning("正在触发一个测试错误...");
  setTimeout(() => {
    throw new Error("这是一个用于测试上报功能的运行时错误日志 (Test Error Log)");
  }, 100);
  
  // 1秒后刷新前端日志列表
  setTimeout(() => {
    loadFrontendLogs();
  }, 1200);
}

function formatTime(utcString: string) {
  if (!utcString) return "";
  try {
    const d = new Date(utcString);
    return d.toLocaleString("zh-CN");
  } catch (e) {
    return utcString;
  }
}

watch(autoScroll, (val) => {
  if (val && terminalEl.value) {
    terminalEl.value.scrollTop = terminalEl.value.scrollHeight;
  }
});

onMounted(() => {
  loadBackendLogs();
  startBackendPoll();
});

onUnmounted(() => {
  stopBackendPoll();
});
</script>

<style scoped>
.log-viewer-page {
  padding: 24px;
  background: #f5f7fa;
  min-height: calc(100vh - 48px);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.content-card {
  background: #ffffff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.tool-label {
  margin-left: 16px;
  margin-right: 8px;
  font-size: 14px;
  color: #606266;
}

.terminal-container {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: Consolas, Monaco, "Courier New", monospace;
  padding: 16px;
  border-radius: 6px 6px 0 0;
  height: 60vh;
  overflow-y: auto;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
  font-size: 13px;
  line-height: 1.5;
}

.terminal-line {
  display: flex;
  margin-bottom: 2px;
}

.line-num {
  width: 40px;
  color: #5a5a5a;
  text-align: right;
  padding-right: 12px;
  user-select: none;
  border-right: 1px solid #333333;
}

.line-content {
  padding-left: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
}

.empty-terminal {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #5a5a5a;
  font-size: 14px;
}

.terminal-footer {
  background: #2d2d2d;
  color: #a5a5a5;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  padding: 8px 16px;
  border-radius: 0 0 6px 6px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
}

.text-danger {
  color: #f56c6c;
}

.text-warning {
  color: #e6a23c;
}

.text-info {
  color: #409eff;
}

.text-muted {
  color: #909399;
}

.expand-container {
  padding: 12px 24px;
  background: #fafafa;
  border-left: 4px solid #f56c6c;
  margin: 8px 0;
}

.expand-container h4 {
  margin: 0 0 8px 0;
  color: #303133;
}

.stack-trace {
  font-family: Consolas, Monaco, monospace;
  background: #1e1e1e;
  color: #f56c6c;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  margin: 0;
  max-height: 250px;
  overflow-y: auto;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
