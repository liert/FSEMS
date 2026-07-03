<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': ui.sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">FS</div>
        <div v-show="!ui.sidebarCollapsed" class="brand-copy">
          <span class="brand-name">FSEMS</span>
          <span class="brand-tagline">Firmware Sandbox EMS</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <el-tooltip
          v-for="item in navItems"
          :key="item.to"
          :content="item.label"
          placement="right"
          :disabled="!ui.sidebarCollapsed"
        >
          <router-link
            :to="item.to"
            class="nav-item"
            :class="{ active: isActive(item.to) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-show="!ui.sidebarCollapsed" class="nav-label">{{ item.label }}</span>
          </router-link>
        </el-tooltip>
      </nav>

      <div class="sidebar-footer">
        <div class="user-chip">
          <el-avatar :size="32" class="user-avatar">{{ userInitial }}</el-avatar>
          <div v-show="!ui.sidebarCollapsed" class="user-meta">
            <span class="user-name">{{ displayName }}</span>
            <span class="user-role">管理员</span>
          </div>
        </div>
        <el-tooltip content="退出登录" placement="right" :disabled="!ui.sidebarCollapsed">
          <el-button class="logout-btn" text @click="logout">
            <el-icon><SwitchButton /></el-icon>
            <span v-show="!ui.sidebarCollapsed">退出登录</span>
          </el-button>
        </el-tooltip>
      </div>
    </aside>

    <div class="main-column">
      <header v-if="showTopbar" class="topbar">
        <div class="topbar-left">
          <el-button class="icon-action" text @click="ui.toggleSidebar()">
            <el-icon><Expand v-if="ui.sidebarCollapsed" /><Fold v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/instances' }">控制台</el-breadcrumb-item>
            <el-breadcrumb-item v-if="isManagePage" :to="{ path: '/instances' }">
              实例管理
            </el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="route.meta.title">
              {{ route.meta.title }}
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="isManagePage">
              {{ ui.pageBreadcrumbLabel || "加载中…" }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-meta">
          <TaskCenter />
          <el-tooltip :content="ui.theme === 'dark' ? '切换浅色主题' : '切换深色主题'">
            <el-button class="icon-action" text @click="ui.toggleTheme()">
              <el-icon><Moon v-if="ui.theme === 'dark'" /><Sunny v-else /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tag size="small" effect="plain" type="info">Phase 3</el-tag>
        </div>
      </header>

      <main class="main-content" :class="{ 'is-full-bleed': isFullBleed }">
        <div v-if="!isFullBleed" class="main-content-bg" aria-hidden="true" />
        <div class="main-content-inner">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Cpu,
  Document,
  Expand,
  Fold,
  List,
  Moon,
  Sunny,
  SwitchButton,
} from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import TaskCenter from "@/components/TaskCenter.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const navItems = [
  { to: "/instances", label: "实例管理", icon: List },
  { to: "/templates", label: "固件模板", icon: Cpu },
  { to: "/logs", label: "系统日志", icon: Document },
];

const isFullBleed = computed(() => Boolean(route.meta.fullBleed));
const showTopbar = computed(() => !route.meta.hideTopbar);
const isManagePage = computed(() => route.path.includes("/instances/") && route.path.endsWith("/manage"));

const displayName = computed(() => auth.username || "Admin");
const userInitial = computed(() => displayName.value.slice(0, 1).toUpperCase());

function isActive(path: string) {
  if (path === "/instances") {
    return route.path === "/instances" || route.path.startsWith("/instances/");
  }
  return route.path.startsWith(path);
}

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--fsems-bg-shell);
}

.sidebar {
  width: var(--fsems-sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  border-right: 1px solid var(--fsems-border);
  background: var(--fsems-sidebar-bg);
  backdrop-filter: blur(12px);
  transition: width 0.22s ease, padding 0.22s ease;
}

.app-shell.sidebar-collapsed .sidebar {
  width: var(--fsems-sidebar-width-collapsed);
  padding: 20px 10px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 20px;
  position: relative;
}

.app-shell.sidebar-collapsed .brand {
  flex-direction: column;
  gap: 10px;
  padding-bottom: 16px;
}

.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.95rem;
  letter-spacing: -0.04em;
  color: #fff;
  background: linear-gradient(135deg, #38bdf8 0%, #6366f1 55%, #a855f7 100%);
  box-shadow: 0 8px 24px rgba(56, 189, 248, 0.25);
  flex-shrink: 0;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.brand-name {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.brand-tagline {
  font-size: 0.72rem;
  color: var(--fsems-text-dim);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  color: var(--fsems-text-muted);
  font-weight: 500;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.app-shell.sidebar-collapsed .nav-item {
  justify-content: center;
  padding: 11px 8px;
}

.nav-item:hover {
  color: var(--fsems-text);
  background: var(--fsems-bg-card);
}

.nav-item.active {
  color: var(--fsems-accent);
  background: color-mix(in srgb, var(--fsems-accent) 12%, transparent);
  border-color: color-mix(in srgb, var(--fsems-accent) 24%, transparent);
  box-shadow: inset 3px 0 0 var(--fsems-accent);
}

.nav-label {
  white-space: nowrap;
}

.sidebar-footer {
  padding-top: 16px;
  border-top: 1px solid var(--fsems-border);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  margin-bottom: 8px;
}

.app-shell.sidebar-collapsed .user-chip {
  justify-content: center;
  padding: 8px 0;
}

.user-avatar {
  background: linear-gradient(135deg, #334155, #1e293b);
  color: #e2e8f0;
  font-weight: 700;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--fsems-text);
}

.user-role {
  font-size: 0.75rem;
  color: var(--fsems-text-dim);
}

.logout-btn {
  width: 100%;
  justify-content: flex-start;
  color: var(--fsems-text-muted) !important;
  gap: 8px;
}

.app-shell.sidebar-collapsed .logout-btn {
  justify-content: center;
}

.logout-btn:hover {
  color: var(--fsems-danger) !important;
}

.main-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  background: transparent;
}

.topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--fsems-border);
  background: var(--fsems-topbar-bg);
  backdrop-filter: blur(8px);
  gap: 12px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.topbar-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.icon-action {
  color: var(--fsems-text-muted) !important;
}

.icon-action:hover {
  color: var(--fsems-accent) !important;
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 24px;
  position: relative;
}

.main-content-bg {
  pointer-events: none;
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--fsems-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--fsems-grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at 30% 0%, black 20%, transparent 75%);
  opacity: 0.55;
}

.main-content-bg::after {
  content: "";
  position: absolute;
  width: 360px;
  height: 360px;
  top: -120px;
  right: -80px;
  border-radius: 50%;
  background: var(--fsems-glow-color);
  filter: blur(70px);
}

.main-content-inner {
  position: relative;
  z-index: 1;
  min-height: 0;
}

.main-content.is-full-bleed {
  padding: 16px 20px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.main-content.is-full-bleed .main-content-inner {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
