import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { fetchTaskStatus } from "@/api/endpoints";

export interface TrackedTask {
  id: string;
  label: string;
  detail?: string;
  taskType?: string | null;
  status: string;
  progress: number;
  errorMsg: string | null;
  createdAt: number;
}

export interface TrackTaskOptions {
  label: string;
  detail?: string;
  taskType?: string | null;
  successMessage?: string;
  onSuccess?: () => void;
  onFailure?: (message: string) => void;
}

const POLL_MS = 1500;
const DISMISS_MS = 4000;

export const useTaskStore = defineStore("tasks", () => {
  const tasks = ref<TrackedTask[]>([]);
  const timers = new Map<string, ReturnType<typeof setInterval>>();
  const dismissTimers = new Map<string, ReturnType<typeof setTimeout>>();

  const activeTasks = computed(() =>
    tasks.value.filter((t) => t.status === "PENDING" || t.status === "RUNNING")
  );

  const activeCount = computed(() => activeTasks.value.length);

  const recentTasks = computed(() =>
    [...tasks.value].sort((a, b) => b.createdAt - a.createdAt).slice(0, 12)
  );

  function upsertTask(task: TrackedTask) {
    const idx = tasks.value.findIndex((t) => t.id === task.id);
    if (idx >= 0) {
      tasks.value[idx] = { ...tasks.value[idx], ...task };
    } else {
      tasks.value.unshift(task);
    }
  }

  function stopPolling(taskId: string) {
    const timer = timers.get(taskId);
    if (timer) {
      clearInterval(timer);
      timers.delete(taskId);
    }
  }

  function scheduleDismiss(taskId: string) {
    if (dismissTimers.has(taskId)) return;
    dismissTimers.set(
      taskId,
      setTimeout(() => {
        tasks.value = tasks.value.filter((t) => t.id !== taskId);
        dismissTimers.delete(taskId);
      }, DISMISS_MS)
    );
  }

  async function pollOnce(taskId: string, options: TrackTaskOptions) {
    const data = await fetchTaskStatus(taskId);
    upsertTask({
      id: taskId,
      label: options.label,
      detail: options.detail,
      taskType: data.task_type ?? options.taskType,
      status: data.status,
      progress: data.progress,
      errorMsg: data.error_msg,
      createdAt: tasks.value.find((t) => t.id === taskId)?.createdAt ?? Date.now(),
    });

    if (data.status === "SUCCESS") {
      stopPolling(taskId);
      if (options.successMessage) {
        ElMessage.success(options.successMessage);
      }
      options.onSuccess?.();
      scheduleDismiss(taskId);
    } else if (data.status === "FAILURE") {
      stopPolling(taskId);
      const message = data.error_msg || "任务失败";
      ElMessage.error(message);
      options.onFailure?.(message);
      scheduleDismiss(taskId);
    }
  }

  function trackTask(taskId: string, options: TrackTaskOptions) {
    stopPolling(taskId);
    upsertTask({
      id: taskId,
      label: options.label,
      detail: options.detail,
      taskType: options.taskType,
      status: "PENDING",
      progress: 0,
      errorMsg: null,
      createdAt: Date.now(),
    });

    void pollOnce(taskId, options).catch(() => {
      upsertTask({
        id: taskId,
        label: options.label,
        detail: options.detail,
        status: "FAILURE",
        progress: 100,
        errorMsg: "无法查询任务状态",
        createdAt: tasks.value.find((t) => t.id === taskId)?.createdAt ?? Date.now(),
      });
    });

    const timer = setInterval(() => {
      void pollOnce(taskId, options).catch(() => {
        stopPolling(taskId);
      });
    }, POLL_MS);
    timers.set(taskId, timer);
  }

  function trackTaskAsync(taskId: string, options: TrackTaskOptions): Promise<void> {
    return new Promise((resolve, reject) => {
      trackTask(taskId, {
        ...options,
        onSuccess: () => {
          options.onSuccess?.();
          resolve();
        },
        onFailure: (message) => {
          options.onFailure?.(message);
          reject(new Error(message));
        },
      });
    });
  }

  function clearFinished() {
    tasks.value = tasks.value.filter((t) => t.status === "PENDING" || t.status === "RUNNING");
  }

  return {
    tasks,
    activeTasks,
    activeCount,
    recentTasks,
    trackTask,
    trackTaskAsync,
    clearFinished,
  };
});
