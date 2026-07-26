<template>
  <UDashboardPanel id="not-found">
    <template #header>
      <UDashboardNavbar title="页面不存在">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-1 items-center justify-center py-16">
        <EmptyState
          title="找不到这个页面"
          :description="`路径 ${route.fullPath} 不存在，可能是链接已失效或地址输入有误。`"
          icon="i-lucide-compass"
        >
          <template #action>
            <UButton icon="i-lucide-server" label="前往实例管理" to="/instances" />
            <UButton
              color="neutral"
              variant="soft"
              icon="i-lucide-arrow-left"
              label="返回上一页"
              @click="router.back()"
            />
          </template>
        </EmptyState>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import EmptyState from "@/components/EmptyState.vue";

const route = useRoute();
const router = useRouter();
</script>
