<template>
  <motion.div
    :initial="{ opacity: 0, y: 8 }"
    :animate="{ opacity: 1, y: 0 }"
    :transition="{ duration: 0.25 }"
    class="flex w-full flex-col items-center justify-center gap-4 px-6 py-12 text-center"
  >
    <UAlert
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      :title="title"
      :description="description"
      class="max-w-md text-left"
    />
    <div v-if="$slots.action || retry" class="flex flex-wrap justify-center gap-2">
      <slot name="action">
        <UButton
          v-if="retry"
          color="neutral"
          variant="soft"
          icon="i-lucide-refresh-cw"
          label="重试"
          @click="retry()"
        />
      </slot>
    </div>
  </motion.div>
</template>

<script setup lang="ts">
import { motion } from "motion-v";

withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    retry?: () => void;
  }>(),
  {
    title: "加载失败",
    description: "请检查网络或后端服务后重试。",
  }
);
</script>
