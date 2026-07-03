<template>
  <el-popover placement="bottom-end" :width="360" trigger="click">
    <template #reference>
      <el-badge :value="taskStore.activeCount" :hidden="taskStore.activeCount === 0" :max="9">
        <el-button class="icon-action task-center-btn" text>
          <el-icon><List /></el-icon>
        </el-button>
      </el-badge>
    </template>

    <div class="task-center">
      <div class="task-center-head">
        <span class="task-center-title">后台任务</span>
        <el-button v-if="taskStore.tasks.length" link type="primary" size="small" @click="taskStore.clearFinished()">
          清除已完成
        </el-button>
      </div>

      <div v-if="!taskStore.recentTasks.length" class="task-empty">
        暂无进行中的任务
      </div>

      <ul v-else class="task-list">
        <li v-for="task in taskStore.recentTasks" :key="task.id" class="task-item">
          <div class="task-item-head">
            <span class="task-label">{{ task.label }}</span>
            <el-tag size="small" :type="statusTag(task.status)" effect="plain">
              {{ statusText(task.status) }}
            </el-tag>
          </div>
          <p v-if="task.detail" class="task-detail">{{ task.detail }}</p>
          <el-progress
            :percentage="task.progress"
            :stroke-width="8"
            :status="progressStatus(task.status)"
            :show-text="true"
          />
          <p v-if="task.errorMsg" class="task-error">{{ task.errorMsg }}</p>
        </li>
      </ul>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { List } from "@element-plus/icons-vue";
import { useTaskStore } from "@/stores/tasks";

const taskStore = useTaskStore();

function statusText(status: string) {
  const map: Record<string, string> = {
    PENDING: "排队中",
    RUNNING: "进行中",
    SUCCESS: "已完成",
    FAILURE: "失败",
  };
  return map[status] || status;
}

function statusTag(status: string) {
  if (status === "SUCCESS") return "success";
  if (status === "FAILURE") return "danger";
  if (status === "RUNNING") return "warning";
  return "info";
}

function progressStatus(status: string) {
  if (status === "SUCCESS") return "success";
  if (status === "FAILURE") return "exception";
  return undefined;
}
</script>

<style scoped>
.task-center-btn {
  font-size: 1.05rem;
}

.task-center-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.task-center-title {
  font-weight: 600;
  color: var(--fsems-text);
}

.task-empty {
  color: var(--fsems-text-dim);
  font-size: 0.88rem;
  padding: 12px 0;
  text-align: center;
}

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 360px;
  overflow-y: auto;
}

.task-item {
  padding-bottom: 2px;
  border-bottom: 1px solid var(--fsems-border);
}

.task-item:last-child {
  border-bottom: none;
}

.task-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.task-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--fsems-text);
}

.task-detail {
  margin: 0 0 8px;
  font-size: 0.78rem;
  color: var(--fsems-text-dim);
  word-break: break-all;
  line-height: 1.4;
}

.task-error {
  margin: 6px 0 0;
  font-size: 0.78rem;
  color: var(--fsems-danger);
}
</style>
