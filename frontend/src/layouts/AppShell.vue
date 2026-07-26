<template>
  <UDashboardGroup storage="local" storage-key="fsems-dashboard" class="min-h-dvh">
    <UDashboardSidebar
      collapsible
      resizable
      :ui="{
        root: 'bg-elevated/40 border-default backdrop-blur-sm',
        header: 'border-b border-default/60',
        footer: 'border-t border-default/60',
      }"
    >
      <template #header="{ collapsed }">
        <motion.div
          class="flex items-center gap-2.5 px-1 py-1"
          :initial="{ opacity: 0, x: -8 }"
          :animate="{ opacity: 1, x: 0 }"
          :transition="{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }"
        >
          <div
            class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-inverted text-xs font-bold shadow-sm shadow-primary/30"
          >
            FS
          </div>
          <div v-if="!collapsed" class="min-w-0">
            <p class="text-sm font-semibold text-highlighted truncate">FSEMS</p>
            <p class="text-xs text-dimmed truncate">Firmware Sandbox EMS</p>
          </div>
        </motion.div>
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="navItems"
          orientation="vertical"
          class="w-full"
        />
      </template>

      <template #footer="{ collapsed }">
        <UDropdownMenu :items="userMenuItems" :content="{ align: 'start', side: 'top' }">
          <UButton
            color="neutral"
            variant="ghost"
            block
            class="justify-start transition-colors"
            :class="collapsed ? 'px-0 justify-center' : ''"
          >
            <UAvatar :text="userInitial" size="sm" class="shrink-0 ring-1 ring-default" />
            <span v-if="!collapsed" class="truncate text-left flex-1">
              <span class="block text-sm font-medium text-default">{{ displayName }}</span>
              <span class="block text-xs text-dimmed">管理员</span>
            </span>
            <UIcon
              v-if="!collapsed"
              name="i-lucide-chevrons-up-down"
              class="size-4 text-dimmed shrink-0"
            />
          </UButton>
        </UDropdownMenu>
      </template>
    </UDashboardSidebar>

    <slot />
  </UDashboardGroup>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { DropdownMenuItem, NavigationMenuItem } from "@nuxt/ui";
import { motion } from "motion-v";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const displayName = computed(() => auth.username || "Admin");
const userInitial = computed(() => displayName.value.slice(0, 1).toUpperCase());

const navItems = computed<NavigationMenuItem[]>(() => [
  {
    label: "实例管理",
    icon: "i-lucide-server",
    to: "/instances",
    active: route.path === "/instances" || route.path.startsWith("/instances/"),
  },
  {
    label: "固件模板",
    icon: "i-lucide-cpu",
    to: "/templates",
    active: route.path.startsWith("/templates"),
  },
  {
    label: "系统日志",
    icon: "i-lucide-scroll-text",
    to: "/logs",
    active: route.path.startsWith("/logs"),
  },
  {
    label: "系统设置",
    icon: "i-lucide-settings",
    to: "/settings",
    active: route.path.startsWith("/settings"),
  },
]);

const userMenuItems = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: "系统设置",
      icon: "i-lucide-settings",
      onSelect: () => router.push("/settings"),
    },
  ],
  [
    {
      label: ui.theme === "dark" ? "切换浅色主题" : "切换深色主题",
      icon: ui.theme === "dark" ? "i-lucide-sun" : "i-lucide-moon",
      onSelect: () => ui.toggleTheme(),
    },
  ],
  [
    {
      label: "退出登录",
      icon: "i-lucide-log-out",
      color: "error",
      onSelect: () => {
        auth.logout();
        router.push("/login");
      },
    },
  ],
]);
</script>
