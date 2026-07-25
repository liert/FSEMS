<template>
  <motion.div
    :initial="{ opacity: 0, scale: 0.97 }"
    :animate="{ opacity: 1, scale: 1 }"
    :transition="{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }"
    class="w-full"
  >
    <UEmpty
      :icon="loading ? undefined : icon"
      :loading="loading"
      :title="title"
      :description="description"
      :variant="variant"
      :size="size"
      :class="rootClass"
    >
      <template v-if="$slots.action || actions?.length" #actions>
        <slot name="action">
          <UButton
            v-for="(action, i) in actions"
            :key="i"
            v-bind="action"
          />
        </slot>
      </template>
    </UEmpty>
  </motion.div>
</template>

<script setup lang="ts">
import { motion } from "motion-v";
import type { ButtonProps } from "@nuxt/ui";

withDefaults(
  defineProps<{
    title: string;
    description?: string;
    icon?: string;
    loading?: boolean;
    variant?: "solid" | "outline" | "soft" | "subtle" | "naked";
    size?: "xs" | "sm" | "md" | "lg" | "xl";
    actions?: ButtonProps[];
    rootClass?: string;
  }>(),
  {
    icon: "i-lucide-inbox",
    loading: false,
    variant: "naked",
    size: "md",
  }
);
</script>
