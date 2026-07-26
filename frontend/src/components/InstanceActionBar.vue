<template>
  <div class="inline-flex items-center gap-0.5" :class="compact ? '' : 'gap-1'">
    <UTooltip :text="startTooltip" :disabled="!showTooltips">
      <UButton
        :color="actionColor('start')"
        :variant="variant"
        :size="size"
        square
        :loading="isLoading('start')"
        :icon="isLoading('start') ? undefined : 'i-lucide-play'"
        :disabled="startDisabled"
        class="action-btn"
        :class="{ 'action-btn--busy': isLoading('start'), 'action-btn--pulse': status === 'STARTING' && !busyAction }"
        @click.stop="run('start')"
      />
    </UTooltip>

    <UTooltip :text="stopTooltip" :disabled="!showTooltips">
      <UButton
        :color="actionColor('stop')"
        :variant="variant"
        :size="size"
        square
        :loading="isLoading('stop')"
        :icon="isLoading('stop') ? undefined : 'i-lucide-square'"
        :disabled="stopDisabled"
        class="action-btn"
        :class="{ 'action-btn--busy': isLoading('stop'), 'action-btn--pulse': status === 'STOPPING' && !busyAction }"
        @click.stop="run('stop')"
      />
    </UTooltip>

    <UTooltip :text="resetTooltip" :disabled="!showTooltips">
      <UButton
        :color="actionColor('reset')"
        :variant="variant"
        :size="size"
        square
        :loading="isLoading('reset')"
        :icon="isLoading('reset') ? undefined : 'i-lucide-refresh-cw'"
        :disabled="resetDisabled"
        class="action-btn"
        :class="{
          'action-btn--busy': isLoading('reset'),
          'action-btn--spin-icon': status === 'STARTING' || status === 'STOPPING' || isLoading('reset'),
        }"
        @click.stop="run('reset')"
      />
    </UTooltip>

    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { instanceAction } from "@/api/endpoints";
import { toastError, toastInfo, toastSuccess } from "@/utils/toast";

export type InstanceLifecycleAction = "start" | "stop" | "reset";

const props = withDefaults(
  defineProps<{
    instanceId: string;
    status: string;
    /** 全局禁用（如整行删除中） */
    disabled?: boolean;
    size?: "xs" | "sm" | "md" | "lg" | "xl";
    variant?: "ghost" | "soft" | "subtle" | "outline" | "solid";
    compact?: boolean;
    showTooltips?: boolean;
  }>(),
  {
    disabled: false,
    size: "sm",
    variant: "ghost",
    compact: true,
    showTooltips: true,
  }
);

const emit = defineEmits<{
  /** 乐观状态变更（STARTING/STOPPING 等） */
  "status-optimistic": [status: string];
  /** API 返回后的状态 */
  "status-changed": [status: string];
  done: [action: InstanceLifecycleAction, status: string];
  error: [action: InstanceLifecycleAction, message: string];
}>();

const busyAction = ref<InstanceLifecycleAction | null>(null);

const startDisabled = computed(
  () =>
    props.disabled ||
    busyAction.value !== null ||
    props.status === "RUNNING" ||
    props.status === "STARTING" ||
    props.status === "STOPPING" ||
    props.status === "LOADING"
);

const stopDisabled = computed(
  () =>
    props.disabled ||
    busyAction.value !== null ||
    props.status === "STOPPED" ||
    props.status === "STOPPING" ||
    props.status === "LOADING"
);

const resetDisabled = computed(
  () => props.disabled || busyAction.value !== null || props.status !== "RUNNING"
);

const startTooltip = computed(() => {
  if (isLoading("start") || props.status === "STARTING") return "正在启动…";
  if (props.status === "RUNNING") return "已在运行";
  return "启动";
});

const stopTooltip = computed(() => {
  if (isLoading("stop") || props.status === "STOPPING") return "正在停止…";
  if (props.status === "STOPPED") return "已停止";
  return "停止";
});

const resetTooltip = computed(() => {
  if (isLoading("reset")) return "正在重启…";
  if (props.status !== "RUNNING") return "仅运行中可重启";
  return "重启";
});

function isLoading(action: InstanceLifecycleAction) {
  return busyAction.value === action;
}

function actionColor(action: InstanceLifecycleAction) {
  if (isLoading(action)) {
    if (action === "start") return "primary" as const;
    if (action === "stop") return "error" as const;
    return "warning" as const;
  }
  if (action === "start") return "primary" as const;
  if (action === "stop") return "error" as const;
  return "warning" as const;
}

async function run(action: InstanceLifecycleAction) {
  if (busyAction.value) return;
  if (action === "start" && startDisabled.value) return;
  if (action === "stop" && stopDisabled.value) return;
  if (action === "reset" && resetDisabled.value) return;

  const labels = { start: "启动", stop: "停止", reset: "重启" } as const;
  const previousStatus = props.status;
  busyAction.value = action;

  // 乐观 UI：按钮 loading + 状态点动画
  if (action === "start") emit("status-optimistic", "STARTING");
  else if (action === "stop") emit("status-optimistic", "STOPPING");
  else emit("status-optimistic", "STARTING");

  toastInfo(`正在${labels[action]}…`);

  try {
    const updated = await instanceAction(props.instanceId, action);
    const next = updated.status || (action === "stop" ? "STOPPING" : "STARTING");
    emit("status-changed", next);
    emit("done", action, next);
    toastSuccess(`已下发${labels[action]}指令`);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : `${labels[action]}失败`;
    // 回滚乐观状态，否则状态徽章会一直停在「启动中」直到轮询兜底纠正
    emit("status-changed", previousStatus);
    emit("error", action, msg);
    toastError(msg);
  } finally {
    busyAction.value = null;
  }
}
</script>

<style scoped>
.action-btn {
  transition:
    transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
    background-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease,
    box-shadow 0.2s ease;
}

.action-btn:not(:disabled):hover {
  transform: scale(1.08);
}

.action-btn:not(:disabled):active {
  transform: scale(0.92);
}

.action-btn--busy {
  transform: scale(1) !important;
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--ui-primary) 25%, transparent);
}

.action-btn--pulse {
  animation: action-soft-pulse 1.4s ease-in-out infinite;
}

@keyframes action-soft-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.72;
  }
}

/* 重启图标在过渡态时轻微旋转感（UButton loading 自带 spinner，这里给非 loading 的 refresh 图标） */
.action-btn--spin-icon :deep(svg) {
  transition: transform 0.3s ease;
}

@media (prefers-reduced-motion: reduce) {
  .action-btn,
  .action-btn:hover,
  .action-btn:active,
  .action-btn--pulse {
    transition: none;
    animation: none;
    transform: none;
  }
}
</style>
