<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="系统设置">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex gap-2">
            <UButton color="neutral" variant="soft" label="重新加载" :loading="loading" @click="loadSystem" />
            <UButton label="保存设置" :loading="saving" @click="saveSystem" />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <PageMotion>
        <div
          v-if="loading && !system"
          class="flex h-full items-center justify-center"
        >
          <LoadingState description="正在加载系统配置…" />
        </div>
        <ErrorState
          v-else-if="loadError && !system"
          :description="loadError"
          :retry="() => loadSystem()"
        />
        <div
          v-else
          class="flex h-full min-h-0 overflow-hidden rounded-xl border border-default bg-elevated/30 ring-1 ring-default/50"
        >
        <aside class="flex w-44 shrink-0 flex-col gap-1 overflow-y-auto border-r border-default p-2.5 sm:w-52 sm:p-3">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            type="button"
            class="relative flex items-start gap-2 rounded-lg px-3 py-2.5 text-left transition-all duration-150"
            :class="
              activeTab === tab.id
                ? 'bg-primary/10 text-highlighted ring-1 ring-primary/30 shadow-sm'
                : 'text-muted hover:bg-muted hover:text-default'
            "
            @click="activeTab = tab.id"
          >
            <UIcon :name="tab.icon" class="mt-0.5 size-4 shrink-0" :class="activeTab === tab.id ? 'text-primary' : ''" />
            <span class="min-w-0">
              <span class="block text-sm font-semibold">{{ tab.label }}</span>
              <span class="hidden text-xs text-dimmed sm:block">{{ tab.desc }}</span>
            </span>
          </button>
        </aside>

        <div class="flex min-w-0 flex-1 flex-col">
          <div class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
            <motion.div
              :key="activeTab"
              :initial="{ opacity: 0, x: 8 }"
              :animate="{ opacity: 1, x: 0 }"
              :transition="{ duration: 0.2 }"
            >
            <div v-if="activeTab === 'account'" class="max-w-md space-y-4">
              <h2 class="text-lg font-semibold text-highlighted">账户</h2>
              <UFormField label="管理员用户名">
                <UInput v-model="form.admin_user" class="w-full" />
              </UFormField>
              <UFormField label="管理员密码">
                <UInput v-model="form.admin_password" type="password" placeholder="留空则不修改" class="w-full" />
              </UFormField>
              <UFormField label="JWT 有效期（秒）">
                <UInputNumber v-model="form.jwt_expire_seconds" :min="60" :max="2592000" class="w-full" />
              </UFormField>
              <div class="flex items-center justify-between border-t border-muted pt-4">
                <div>
                  <p class="text-sm font-medium">当前会话</p>
                  <p class="text-xs text-dimmed">{{ auth.username || "—" }}</p>
                </div>
                <UButton color="error" variant="soft" label="退出登录" @click="logout" />
              </div>
            </div>

            <div v-else-if="activeTab === 'paths'" class="max-w-3xl space-y-4">
              <h2 class="text-lg font-semibold text-highlighted">路径与存储</h2>
              <div class="grid gap-3 sm:grid-cols-2">
                <UFormField label="工作空间"><UInput v-model="form.workspace" class="w-full font-mono text-sm" /></UFormField>
                <UFormField label="内核目录"><UInput v-model="form.kernels_dir" class="w-full font-mono text-sm" /></UFormField>
                <UFormField label="RootFS 目录"><UInput v-model="form.rootfs_dir" class="w-full font-mono text-sm" /></UFormField>
                <UFormField label="挂载目录"><UInput v-model="form.mnt_dir" class="w-full font-mono text-sm" /></UFormField>
                <UFormField label="日志目录"><UInput v-model="form.logs_dir" class="w-full font-mono text-sm" /></UFormField>
                <UFormField label="数据库（只读）">
                  <UInput :model-value="system?.database_path || ''" readonly class="w-full font-mono text-sm" />
                </UFormField>
              </div>
            </div>

            <div v-else-if="activeTab === 'network'" class="max-w-md space-y-4">
              <h2 class="text-lg font-semibold text-highlighted">网络与 QEMU</h2>
              <UFormField label="默认网桥"><UInput v-model="form.bridge" class="w-full" /></UFormField>
              <UFormField label="启动超时（秒）">
                <UInputNumber v-model="form.boot_timeout_sec" :min="10" :max="3600" class="w-full" />
              </UFormField>
              <UFormField label="串口 Socket 目录"><UInput v-model="form.qemu_serial_dir" class="w-full font-mono text-sm" /></UFormField>
              <UFormField label="运行用户（TAP）"><UInput v-model="form.fsems_user" class="w-full" /></UFormField>
              <UFormField label="访客 SSH 用户"><UInput v-model="form.guest_ssh_user" class="w-full" /></UFormField>
              <UFormField :label="guestPasswordLabel">
                <UInput v-model="form.guest_ssh_password" type="password" placeholder="留空则不修改" class="w-full" />
              </UFormField>
            </div>

            <div v-else-if="activeTab === 'mcp'" class="max-w-md space-y-4">
              <h2 class="text-lg font-semibold text-highlighted">MCP（Agent）</h2>
              <UFormField label="启用 MCP"><USwitch v-model="form.mcp_enabled" /></UFormField>
              <UFormField label="挂载路径"><UInput v-model="form.mcp_path" class="w-full" /></UFormField>
              <UFormField label="独立进程 Host"><UInput v-model="form.mcp_host" class="w-full" /></UFormField>
              <UFormField label="独立进程端口">
                <UInputNumber v-model="form.mcp_port" :min="1" :max="65535" class="w-full" />
              </UFormField>
              <UFormField label="无状态模式"><USwitch v-model="form.mcp_stateless" /></UFormField>
              <UFormField :label="mcpTokenLabel">
                <UInput v-model="form.mcp_token" type="password" placeholder="留空则不修改" class="w-full" />
              </UFormField>
              <p class="font-mono text-xs text-dimmed">同进程地址：{{ mcpApiUrl }}</p>
            </div>

            <div v-else class="max-w-3xl space-y-4">
              <h2 class="text-lg font-semibold text-highlighted">其它</h2>
              <div class="grid gap-3 sm:grid-cols-2">
                <UFormField label="OpenWrt 下载源">
                  <UInput v-model="form.openwrt_download_base" class="w-full font-mono text-sm" />
                </UFormField>
                <UFormField label="Redis URL">
                  <UInput v-model="form.redis_url" :placeholder="system?.redis_url_masked || '留空则不修改'" class="w-full font-mono text-sm" />
                </UFormField>
                <UFormField label="API Host"><UInput v-model="form.api_host" class="w-full" /></UFormField>
                <UFormField label="API Port">
                  <UInputNumber v-model="form.api_port" :min="1" :max="65535" class="w-full" />
                </UFormField>
              </div>
            </div>
            </motion.div>
          </div>

          <div class="flex shrink-0 flex-wrap justify-end gap-2 border-t border-default bg-elevated/40 px-4 py-3 sm:px-5">
            <UButton color="neutral" variant="soft" label="放弃修改并重新加载" icon="i-lucide-rotate-ccw" :loading="loading" @click="loadSystem" />
            <UButton label="保存设置" icon="i-lucide-save" :loading="saving" @click="saveSystem" />
          </div>
        </div>
      </div>
      </PageMotion>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { motion } from "motion-v";
import {
  fetchSystemSettings,
  updateSystemSettings,
  type SystemSettings,
  type SystemSettingsUpdate,
} from "@/api/endpoints";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import PageMotion from "@/components/PageMotion.vue";
import { useAuthStore } from "@/stores/auth";
import { toastError, toastSuccess, toastWarning } from "@/utils/toast";

type TabId = "account" | "paths" | "network" | "mcp" | "advanced";

const tabs: { id: TabId; label: string; desc: string; icon: string }[] = [
  { id: "account", label: "账户", desc: "登录与令牌", icon: "i-lucide-key-round" },
  { id: "paths", label: "路径存储", desc: "工作区与目录", icon: "i-lucide-folder-open" },
  { id: "network", label: "网络 QEMU", desc: "网桥与 SSH", icon: "i-lucide-network" },
  { id: "mcp", label: "MCP Agent", desc: "管理接口", icon: "i-lucide-bot" },
  { id: "advanced", label: "其它", desc: "Redis / API", icon: "i-lucide-sliders-horizontal" },
];

const auth = useAuthStore();
const router = useRouter();
const activeTab = ref<TabId>("account");
const loading = ref(false);
const loadError = ref("");
const saving = ref(false);
const system = ref<SystemSettings | null>(null);

const form = reactive({
  workspace: "",
  kernels_dir: "",
  rootfs_dir: "",
  mnt_dir: "",
  logs_dir: "",
  bridge: "",
  boot_timeout_sec: 120,
  qemu_serial_dir: "",
  fsems_user: "",
  guest_ssh_user: "",
  guest_ssh_password: "",
  openwrt_download_base: "",
  mcp_enabled: true,
  mcp_path: "/mcp",
  mcp_host: "127.0.0.1",
  mcp_port: 8001,
  mcp_stateless: true,
  mcp_token: "",
  admin_user: "",
  admin_password: "",
  jwt_expire_seconds: 3600,
  api_host: "127.0.0.1",
  api_port: 8000,
  redis_url: "",
});

const guestPasswordLabel = computed(() =>
  system.value?.guest_ssh_password_set ? "访客 SSH 密码（已设置，留空不改）" : "访客 SSH 密码"
);
const mcpTokenLabel = computed(() =>
  system.value?.mcp_auth_required ? "MCP Token（已设置，留空不改）" : "MCP Token（可选）"
);
const mcpApiUrl = computed(() => {
  const path = form.mcp_path || "/mcp";
  return typeof window !== "undefined"
    ? `${window.location.origin}${path.startsWith("/") ? path : `/${path}`}`
    : path;
});

function applySystemToForm(s: SystemSettings) {
  form.workspace = s.workspace;
  form.kernels_dir = s.kernels_dir;
  form.rootfs_dir = s.rootfs_dir;
  form.mnt_dir = s.mnt_dir;
  form.logs_dir = s.logs_dir;
  form.bridge = s.bridge;
  form.boot_timeout_sec = s.boot_timeout_sec;
  form.qemu_serial_dir = s.qemu_serial_dir;
  form.fsems_user = s.fsems_user || "";
  form.guest_ssh_user = s.guest_ssh_user;
  form.guest_ssh_password = "";
  form.openwrt_download_base = s.openwrt_download_base;
  form.mcp_enabled = s.mcp_enabled;
  form.mcp_path = s.mcp_path;
  form.mcp_host = s.mcp_host || "127.0.0.1";
  form.mcp_port = s.mcp_port || 8001;
  form.mcp_stateless = s.mcp_stateless;
  form.mcp_token = "";
  form.admin_user = s.admin_user;
  form.admin_password = "";
  form.jwt_expire_seconds = s.jwt_expire_seconds;
  form.api_host = s.api_host;
  form.api_port = s.api_port;
  form.redis_url = "";
}

async function loadSystem() {
  loading.value = true;
  try {
    system.value = await fetchSystemSettings();
    applySystemToForm(system.value);
    loadError.value = "";
  } catch (e: unknown) {
    loadError.value = e instanceof Error ? e.message : "加载系统设置失败";
    toastError(loadError.value);
  } finally {
    loading.value = false;
  }
}

function buildPayload(): SystemSettingsUpdate {
  const body: SystemSettingsUpdate = {
    workspace: form.workspace.trim(),
    kernels_dir: form.kernels_dir.trim(),
    rootfs_dir: form.rootfs_dir.trim(),
    mnt_dir: form.mnt_dir.trim(),
    logs_dir: form.logs_dir.trim(),
    bridge: form.bridge.trim(),
    boot_timeout_sec: form.boot_timeout_sec,
    qemu_serial_dir: form.qemu_serial_dir.trim(),
    fsems_user: form.fsems_user.trim(),
    guest_ssh_user: form.guest_ssh_user.trim(),
    openwrt_download_base: form.openwrt_download_base.trim(),
    mcp_enabled: form.mcp_enabled,
    mcp_path: form.mcp_path.trim(),
    mcp_host: form.mcp_host.trim(),
    mcp_port: form.mcp_port,
    mcp_stateless: form.mcp_stateless,
    admin_user: form.admin_user.trim(),
    jwt_expire_seconds: form.jwt_expire_seconds,
    api_host: form.api_host.trim(),
    api_port: form.api_port,
  };
  if (form.guest_ssh_password.trim()) body.guest_ssh_password = form.guest_ssh_password;
  if (form.admin_password.trim()) body.admin_password = form.admin_password;
  if (form.mcp_token.trim()) body.mcp_token = form.mcp_token;
  if (form.redis_url.trim()) body.redis_url = form.redis_url.trim();
  return body;
}

async function saveSystem() {
  if (!form.admin_user.trim()) {
    toastWarning("管理员用户名不能为空");
    activeTab.value = "account";
    return;
  }
  if (!form.bridge.trim()) {
    toastWarning("默认网桥不能为空");
    activeTab.value = "network";
    return;
  }
  saving.value = true;
  try {
    system.value = await updateSystemSettings(buildPayload());
    applySystemToForm(system.value);
    toastSuccess(system.value.restart_hint || "设置已保存");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

function logout() {
  auth.logout();
  router.push("/login");
}

onMounted(() => void loadSystem());
</script>
