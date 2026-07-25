<template>
  <UBadge :color="color" variant="subtle" size="sm" class="status-badge">
    <span class="inline-flex items-center gap-1.5">
      <span class="status-dot" :class="dotClass" aria-hidden="true" />
      <Transition name="status-label" mode="out-in">
        <span :key="status" class="status-label">{{ label }}</span>
      </Transition>
    </span>
  </UBadge>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { statusLabel } from "@/utils/instanceStatus";

const props = defineProps<{ status: string }>();

const label = computed(() => statusLabel(props.status));

const color = computed(() => {
  if (props.status === "RUNNING") return "success" as const;
  if (props.status === "STARTING") return "warning" as const;
  if (props.status === "STOPPED") return "neutral" as const;
  if (props.status === "STOPPING") return "warning" as const;
  if (props.status === "LOADING") return "info" as const;
  return "error" as const;
});

const dotClass = computed(() => {
  if (props.status === "RUNNING") return "status-dot--running";
  if (props.status === "STARTING" || props.status === "STOPPING") return "status-dot--pending";
  if (props.status === "STOPPED") return "status-dot--stopped";
  if (props.status === "LOADING") return "status-dot--pending";
  return "status-dot--error";
});
</script>

<style scoped>
.status-badge {
  transition:
    background-color 0.25s ease,
    color 0.25s ease,
    box-shadow 0.25s ease;
}

.status-dot {
  display: inline-block;
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 999px;
  flex-shrink: 0;
  transition: background-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
}

.status-dot--running {
  background-color: var(--ui-success);
  box-shadow: 0 0 0 0 color-mix(in oklab, var(--ui-success) 45%, transparent);
  animation: status-live 2s ease-out infinite;
}

.status-dot--pending {
  background-color: var(--ui-warning);
  animation: status-pulse 1s ease-in-out infinite;
}

.status-dot--stopped {
  background-color: color-mix(in oklab, var(--ui-text-muted) 70%, transparent);
}

.status-dot--error {
  background-color: var(--ui-error);
}

.status-label {
  display: inline-block;
}

.status-label-enter-active,
.status-label-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.status-label-enter-from {
  opacity: 0;
  transform: translateY(3px);
}

.status-label-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.85);
  }
}

@keyframes status-live {
  0% {
    box-shadow: 0 0 0 0 color-mix(in oklab, var(--ui-success) 50%, transparent);
  }
  70% {
    box-shadow: 0 0 0 6px transparent;
  }
  100% {
    box-shadow: 0 0 0 0 transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot--running,
  .status-dot--pending,
  .status-label-enter-active,
  .status-label-leave-active {
    animation: none;
    transition: none;
  }
}
</style>
