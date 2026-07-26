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
  updatedAt: number;
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
/** 连续轮询失败达到该次数后放弃，避免定时器永久空转 */
const MAX_CONSECUTIVE_ERRORS = 6;
/** 列表上限，防止长会话中失败任务无限累积 */
const MAX_TASKS = 50;

export const useTaskStore = defineStore("tasks", () => {
  const tasks = ref<TrackedTask[]>([]);
  const timers = new Map<string, ReturnType<typeof setInterval>>();
  const dismissTimers = new Map<string, ReturnType<typeof setTimeout>>();
  /** 已触发过终态回调的任务，保证 onSuccess/onFailure 只跑一次 */
  const settled = new Set<string>();
  /** 请求在途标记，避免慢响应时多个轮询请求叠加 */
  const inFlight = new Set<string>();
  const errorCounts = new Map<string, number>();

  const activeTasks = computed(() =>
    tasks.value.filter((t) => t.status === "PENDING" || t.status === "RUNNING")
  );
  const activeCount = computed(() => activeTasks.value.length);
  const recentTasks = computed(() =>
    [...tasks.value].sort((a, b) => b.createdAt - a.createdAt).slice(0, 12)
  );

  function upsertTask(task: Omit<TrackedTask, "createdAt" | "updatedAt">) {
    const now = Date.now();
    const idx = tasks.value.findIndex((t) => t.id === task.id);
    if (idx >= 0) {
      // createdAt 保持首次入列时间，否则排序会随每次轮询抖动
      tasks.value[idx] = { ...tasks.value[idx], ...task, updatedAt: now };
    } else {
      tasks.value.unshift({ ...task, createdAt: now, updatedAt: now });
      if (tasks.value.length > MAX_TASKS) tasks.value.length = MAX_TASKS;
    }
  }

  function stopPolling(taskId: string) {
    const timer = timers.get(taskId);
    if (timer) {
      clearInterval(timer);
      timers.delete(taskId);
    }
    errorCounts.delete(taskId);
  }

  function scheduleDismiss(taskId: string) {
    if (dismissTimers.has(taskId)) return;
    dismissTimers.set(
      taskId,
      setTimeout(() => {
        tasks.value = tasks.value.filter((t) => t.id !== taskId);
        dismissTimers.delete(taskId);
        settled.delete(taskId);
      }, DISMISS_MS)
    );
  }

  /** 终态收尾，靠 settled 集合保证幂等 */
  function finalize(taskId: string, ok: boolean, options: TrackTaskOptions, message?: string) {
    stopPolling(taskId);
    if (settled.has(taskId)) return;
    settled.add(taskId);
    if (ok) {
      scheduleDismiss(taskId);
      if (options.successMessage) toastSuccess(options.successMessage);
      options.onSuccess?.();
    } else {
      const msg = message || "任务失败";
      toastError(msg);
      options.onFailure?.(msg);
    }
  }

  /** @returns 是否已到终态（成功/失败/放弃） */
  async function pollOnce(taskId: string, options: TrackTaskOptions): Promise<boolean> {
    if (inFlight.has(taskId)) return false;
    inFlight.add(taskId);
    try {
      const data = await fetchTaskStatus(taskId);
      errorCounts.delete(taskId);
      upsertTask({
        id: taskId,
        label: options.label,
        detail: options.detail,
        taskType: data.task_type ?? options.taskType,
        status: data.status,
        progress: data.progress,
        errorMsg: data.error_msg,
      });

      if (data.status === "SUCCESS") {
        finalize(taskId, true, options);
        return true;
      }
      if (data.status === "FAILURE") {
        finalize(taskId, false, options, data.error_msg || undefined);
        return true;
      }
      return false;
    } catch (e: unknown) {
      const count = (errorCounts.get(taskId) ?? 0) + 1;
      errorCounts.set(taskId, count);
      if (count < MAX_CONSECUTIVE_ERRORS) return false;
      // 连续失败过多：标记失败并停止，避免僵尸任务与永久空转的定时器
      const msg = e instanceof Error ? e.message : "无法获取任务状态";
      upsertTask({
        id: taskId,
        label: options.label,
        detail: options.detail,
        taskType: options.taskType,
        status: "FAILURE",
        progress: 0,
        errorMsg: msg,
      });
      finalize(taskId, false, options, msg);
      return true;
    } finally {
      inFlight.delete(taskId);
    }
  }

  async function trackTaskAsync(taskId: string, options: TrackTaskOptions) {
    if (timers.has(taskId) || settled.has(taskId)) return;
    upsertTask({
      id: taskId,
      label: options.label,
      detail: options.detail,
      taskType: options.taskType,
      status: "PENDING",
      progress: 0,
      errorMsg: null,
    });

    // 首轮失败不应中断跟踪：交给定时器重试，由错误计数决定何时放弃
    const done = await pollOnce(taskId, options);
    if (done || timers.has(taskId)) return;

    timers.set(
      taskId,
      setInterval(() => {
        void pollOnce(taskId, options).catch(() => undefined);
      }, POLL_MS)
    );
  }

  /** 退出登录 / 卸载时清空，避免定时器在后台持续打 401 */
  function stopAll() {
    timers.forEach((t) => clearInterval(t));
    timers.clear();
    dismissTimers.forEach((t) => clearTimeout(t));
    dismissTimers.clear();
    inFlight.clear();
    errorCounts.clear();
    settled.clear();
    tasks.value = [];
  }

  return { tasks, activeTasks, activeCount, recentTasks, trackTaskAsync, stopAll };
});
