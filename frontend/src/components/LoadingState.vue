<template>
  <div
    class="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center"
    role="status"
    aria-live="polite"
  >
    <motion.div
      :animate="{ rotate: 360 }"
      :transition="{ duration: 0.9, repeat: Infinity, ease: 'linear' }"
      class="flex size-10 items-center justify-center rounded-full bg-elevated text-primary"
    >
      <UIcon name="i-lucide-loader-circle" class="size-5" />
    </motion.div>
    <div>
      <p class="text-sm font-medium text-highlighted">{{ title }}</p>
      <p v-if="description" class="mt-1 text-xs text-muted">{{ description }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { motion } from "motion-v";

withDefaults(
  defineProps<{
    title?: string;
    description?: string;
  }>(),
  {
    title: "加载中…",
    description: undefined,
  }
);
</script>
