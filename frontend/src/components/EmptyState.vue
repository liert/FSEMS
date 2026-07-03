<template>
  <div class="empty-state">
    <div class="empty-icon">
      <slot name="icon">
        <el-icon><Box /></el-icon>
      </slot>
    </div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Box } from "@element-plus/icons-vue";

defineProps<{
  title: string;
  description: string;
}>();
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 56px 24px;
  color: var(--fsems-text-muted);
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.18);
  color: var(--fsems-accent);
  font-size: 28px;
}

.empty-state h3 {
  margin: 0 0 8px;
  color: var(--fsems-text);
  font-size: 1.05rem;
  font-weight: 600;
}

.empty-state p {
  margin: 0;
  max-width: 420px;
  line-height: 1.6;
  font-size: 0.9rem;
}

.empty-action {
  margin-top: 20px;
}
</style>
