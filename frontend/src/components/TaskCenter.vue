<template>
  <UPopover :content="{ align: 'end' }">
    <UButton color="neutral" variant="ghost" square icon="i-lucide-list-todo">
      <span
        v-if="taskStore.activeCount"
        class="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] text-inverted"
      >
        {{ taskStore.activeCount }}
      </span>
    </UButton>
    <template #content>
      <div class="w-80 p-3">
        <div class="mb-2 flex items-center justify-between">
          <p class="text-sm font-semibold text-highlighted">后台任务</p>
          <UBadge v-if="taskStore.activeCount" color="primary" variant="subtle" size="sm">
            {{ taskStore.activeCount }} 进行中
          </UBadge>
        </div>
        <div v-if="!taskStore.recentTasks.length" class="py-6 text-center text-sm text-muted">
          暂无任务
        </div>
        <ul v-else class="max-h-72 space-y-2 overflow-y-auto">
          <li
            v-for="t in taskStore.recentTasks"
            :key="t.id"
            class="rounded-lg border border-muted bg-elevated/50 p-2.5"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-default">{{ t.label }}</p>
                <p v-if="t.detail" class="truncate text-xs text-dimmed">{{ t.detail }}</p>
              </div>
              <UBadge :color="statusColor(t.status)" variant="subtle" size="sm">
                {{ statusText(t.status) }}
              </UBadge>
            </div>
            <UProgress
              v-if="t.status === 'PENDING' || t.status === 'RUNNING'"
              :model-value="t.progress"
              size="xs"
              class="mt-2"
            />
            <p v-if="t.errorMsg" class="mt-1 text-xs text-error">{{ t.errorMsg }}</p>
          </li>
        </ul>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import { useTaskStore } from "@/stores/tasks";

const taskStore = useTaskStore();

function statusText(s: string) {
  if (s === "PENDING") return "排队";
  if (s === "RUNNING") return "运行中";
  if (s === "SUCCESS") return "完成";
  if (s === "FAILURE") return "失败";
  return s;
}

function statusColor(s: string) {
  if (s === "SUCCESS") return "success" as const;
  if (s === "FAILURE") return "error" as const;
  if (s === "RUNNING") return "primary" as const;
  return "neutral" as const;
}
</script>
