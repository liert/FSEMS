<template>
  <el-tag :type="statusTagType(status)" size="small" effect="dark" class="status-badge">
    <span v-if="showDot" class="status-dot" :class="dotClass" />
    {{ statusLabel(status) }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { statusLabel, statusTagType } from "@/utils/instanceStatus";

const props = withDefaults(
  defineProps<{
    status: string;
    showDot?: boolean;
  }>(),
  { showDot: true }
);

const dotClass = computed(() => {
  if (props.status === "RUNNING") return "dot-success";
  if (props.status === "STARTING" || props.status === "STOPPING") return "dot-warning";
  if (props.status === "STOPPED") return "dot-muted";
  return "dot-danger";
});
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-success {
  background: #34d399;
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.7);
}

.dot-warning {
  background: #fbbf24;
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.6);
  animation: pulse 1.4s ease-in-out infinite;
}

.dot-muted {
  background: #64748b;
}

.dot-danger {
  background: #f87171;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}
</style>
