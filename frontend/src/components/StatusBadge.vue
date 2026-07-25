<template>
  <UBadge :color="color" variant="subtle" size="sm">
    <span class="inline-flex items-center gap-1.5">
      <span class="size-1.5 rounded-full" :class="dotClass" />
      {{ label }}
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
  return "error" as const;
});

const dotClass = computed(() => {
  if (props.status === "RUNNING") return "bg-success";
  if (props.status === "STARTING" || props.status === "STOPPING") return "bg-warning animate-pulse";
  if (props.status === "STOPPED") return "bg-muted";
  return "bg-error";
});
</script>
