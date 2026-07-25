<template>
  <motion.div
    :initial="{ opacity: 0, y: 12 }"
    :animate="{ opacity: 1, y: 0 }"
    :transition="staggerDelay(index)"
    :whileHover="hoverable ? hoverLift : undefined"
    class="h-full"
  >
    <UCard
      class="h-full transition-colors duration-200"
      :class="hoverable ? 'hover:ring-1 hover:ring-primary/25' : ''"
      :ui="{ body: 'p-4 sm:p-5' }"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="text-xs font-medium tracking-wide text-muted uppercase">{{ label }}</p>
          <p class="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight" :class="valueClass">
            {{ value }}
          </p>
          <p v-if="hint" class="mt-1 text-xs text-dimmed">{{ hint }}</p>
        </div>
        <div
          v-if="icon"
          class="flex size-9 shrink-0 items-center justify-center rounded-lg"
          :class="iconWrapClass"
        >
          <UIcon :name="icon" class="size-4" />
        </div>
      </div>
    </UCard>
  </motion.div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { motion } from "motion-v";
import { hoverLift, staggerDelay } from "@/utils/motion";

const props = withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    hint?: string;
    icon?: string;
    tone?: "primary" | "success" | "warning" | "muted" | "error" | "info";
    index?: number;
    hoverable?: boolean;
  }>(),
  {
    tone: "primary",
    index: 0,
    hoverable: true,
  }
);

const valueClass = computed(() => {
  switch (props.tone) {
    case "success":
      return "text-success";
    case "warning":
      return "text-warning";
    case "error":
      return "text-error";
    case "info":
      return "text-info";
    case "muted":
      return "text-muted";
    default:
      return "text-primary";
  }
});

const iconWrapClass = computed(() => {
  switch (props.tone) {
    case "success":
      return "bg-success/10 text-success";
    case "warning":
      return "bg-warning/10 text-warning";
    case "error":
      return "bg-error/10 text-error";
    case "info":
      return "bg-info/10 text-info";
    case "muted":
      return "bg-elevated text-muted";
    default:
      return "bg-primary/10 text-primary";
  }
});
</script>
