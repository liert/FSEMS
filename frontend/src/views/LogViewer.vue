<template>
  <div class="page-stack log-page">
    <PageHeader
      title="系统日志"
      description="查看 FastAPI / Celery 后端日志与前端客户端异常上报，便于联调与故障排查。"
    />

    <section class="glass-card content-panel log-card">
      <el-tabs v-model="activeTab" class="log-tabs" @tab-change="onTabChange">
        <el-tab-pane label="后端系统日志" name="backend">
          <div class="toolbar-row">
            <div class="toolbar-left">
              <el-radio-group v-model="backendType" @change="loadBackendLogs">
                <el-radio-button value="fastapi">FastAPI</el-radio-button>
                <el-radio-button value="celery">Celery</el-radio-button>
              </el-radio-group>

              <span class="tool-label">行数</span>
              <el-select v-model="backendLines" style="width: 110px" @change="loadBackendLogs">
                <el-option :value="50" label="50" />
                <el-option :value="100" label="100" />
                <el-option :value="200" label="200" />
                <el-option :value="500" label="500" />
                <el-option :value="1000" label="1000" />
              </el-select>

              <el-input
                v-model="backendSearch"
                placeholder="过滤日志内容…"
                style="width: 220px"
                clearable
                :prefix-icon="Search"
              />
            </div>

            <div class="toolbar-right">
              <el-checkbox v-model="autoScroll">自动滚动</el-checkbox>
              <el-button type="primary" :loading="loadingBackend" @click="loadBackendLogs">
                刷新
              </el-button>
            </div>
          </div>

          <div ref="terminalEl" class="terminal-container">
            <template v-if="filteredBackendLines.length > 0">
              <div v-for="(line, idx) in filteredBackendLines" :key="idx" class="terminal-line">
                <span class="line-num">{{ idx + 1 }}</span>
                <span class="line-content" :class="getLineClass(line)">{{ line }}</span>
              </div>
            </template>
            <div v-else class="empty-terminal">
              {{ loadingBackend ? "正在加载日志…" : "暂无匹配的日志记录" }}
            </div>
          </div>
          <div class="terminal-footer">
            共 {{ backendTotalLines }} 行 · 已载入末尾 {{ backendLines }} 行
          </div>
        </el-tab-pane>

        <el-tab-pane label="前端客户端日志" name="frontend">
          <div class="toolbar-row">
            <div class="toolbar-left">
              <el-button type="danger" plain @click="triggerTestError">
                触发测试错误
              </el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="primary" :loading="loadingFrontend" @click="loadFrontendLogs">
                刷新
              </el-button>
            </div>
          </div>

          <div class="table-panel">
            <el-table :data="frontendLogs" style="width: 100%" v-loading="loadingFrontend" empty-text="暂无上报日志">
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="expand-container">
                    <h4>异常调用栈</h4>
                    <pre class="stack-trace">{{ row.stack || "无堆栈信息" }}</pre>
                  </div>
                </template>
              </el-table-column>

              <el-table-column prop="id" label="ID" width="70" align="center" />
              <el-table-column prop="level" label="级别" width="100">
                <template #default="{ row }">
                  <el-tag :type="getFrontendLevelType(row.level)" size="small" effect="dark">
                    {{ String(row.level).toUpperCase() }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="消息" min-width="250" show-overflow-tooltip />
              <el-table-column prop="url" label="页面 URL" min-width="200" show-overflow-tooltip />
              <el-table-column prop="created_at" label="时间" width="180">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
          </div>

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
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Search } from "@element-plus/icons-vue";
import { fetchBackendLogs, fetchFrontendLogs } from "@/api/endpoints";
import type { FrontendLog } from "@/api/types";
import PageHeader from "@/components/PageHeader.vue";

const activeTab = ref("backend");

const backendType = ref<"fastapi" | "celery">("fastapi");
const backendLines = ref(100);
const backendSearch = ref("");
const backendTotalLines = ref(0);
const backendLinesData = ref<string[]>([]);
const loadingBackend = ref(false);
const autoScroll = ref(true);
const terminalEl = ref<HTMLElement | null>(null);
let backendTimer: ReturnType<typeof setInterval> | null = null;

const filteredBackendLines = computed(() => {
  const chronoLines = [...backendLinesData.value].reverse();
  if (!backendSearch.value) return chronoLines;
  const q = backendSearch.value.toLowerCase();
  return chronoLines.filter((line) => line.toLowerCase().includes(q));
});

const frontendLogs = ref<FrontendLog[]>([]);
const loadingFrontend = ref(false);
const frontendTotal = ref(0);
const frontendPage = ref(1);
const frontendLimit = ref(20);

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
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "获取后端日志失败");
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
    if (frontendLogs.value.length === 0) {
      frontendTotal.value = 0;
    } else {
      frontendTotal.value = frontendLogs.value[0].id;
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "获取前端日志失败");
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
  ElMessage.warning("正在触发测试错误…");
  setTimeout(() => {
    throw new Error("这是一个用于测试上报功能的运行时错误日志 (Test Error Log)");
  }, 100);
  setTimeout(() => {
    loadFrontendLogs();
  }, 1200);
}

function formatTime(utcString: string) {
  if (!utcString) return "";
  try {
    return new Date(utcString).toLocaleString("zh-CN");
  } catch {
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
.log-card {
  min-height: 0;
}

.log-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.tool-label {
  margin-left: 4px;
  font-size: 0.85rem;
  color: var(--fsems-text-dim);
}

.terminal-container {
  background: #0d1117;
  color: #d4d4d4;
  font-family: var(--fsems-mono);
  padding: 16px;
  border-radius: 10px 10px 0 0;
  height: min(58vh, 620px);
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 13px;
  line-height: 1.5;
}

.terminal-line {
  display: flex;
  margin-bottom: 2px;
}

.line-num {
  width: 42px;
  color: #4b5563;
  text-align: right;
  padding-right: 12px;
  user-select: none;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
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
  color: #6b7280;
}

.terminal-footer {
  background: rgba(255, 255, 255, 0.03);
  color: var(--fsems-text-dim);
  font-family: var(--fsems-mono);
  font-size: 0.78rem;
  padding: 8px 14px;
  border-radius: 0 0 10px 10px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-top: none;
  margin-bottom: 8px;
}

.text-danger {
  color: #f87171;
}

.text-warning {
  color: #fbbf24;
}

.text-info {
  color: #38bdf8;
}

.text-muted {
  color: #94a3b8;
}

.expand-container {
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid var(--fsems-danger);
  margin: 8px 0;
}

.expand-container h4 {
  margin: 0 0 8px;
  color: var(--fsems-text);
  font-size: 0.88rem;
}

.stack-trace {
  font-family: var(--fsems-mono);
  background: #0d1117;
  color: #f87171;
  padding: 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  margin: 0;
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
