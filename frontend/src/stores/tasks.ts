import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchTaskStatus } from "@/api/endpoints";
import { toastError, toastSuccess } from "@/utils/toast";

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
    if (idx >= 0) tasks.value[idx] = { ...tasks.value[idx], ...task };
    else tasks.value.unshift(task);
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
      createdAt: Date.now(),
    });

    if (data.status === "SUCCESS") {
      stopPolling(taskId);
      scheduleDismiss(taskId);
      if (options.successMessage) toastSuccess(options.successMessage);
      options.onSuccess?.();
    } else if (data.status === "FAILURE") {
      stopPolling(taskId);
      const msg = data.error_msg || "任务失败";
      toastError(msg);
      options.onFailure?.(msg);
    }
  }

  async function trackTaskAsync(taskId: string, options: TrackTaskOptions) {
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
    await pollOnce(taskId, options);
    if (timers.has(taskId)) return;
    timers.set(
      taskId,
      setInterval(() => {
        void pollOnce(taskId, options).catch(() => undefined);
      }, POLL_MS)
    );
  }

  return { tasks, activeTasks, activeCount, recentTasks, trackTaskAsync };
});
