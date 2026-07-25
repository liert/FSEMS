<template>
  <div class="flex flex-col items-center justify-center py-16 px-6 text-center">
    <div class="mb-4 flex size-12 items-center justify-center rounded-full bg-elevated text-muted">
      <UIcon :name="icon" class="size-6" />
    </div>
    <h3 class="text-base font-semibold text-highlighted">{{ title }}</h3>
    <p v-if="description" class="mt-1 max-w-sm text-sm text-muted">{{ description }}</p>
    <div v-if="$slots.action" class="mt-4">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    icon?: string;
  }>(),
  { icon: "i-lucide-inbox" }
);
</script>
