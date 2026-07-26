<template>
  <div class="relative flex min-h-dvh items-center justify-center overflow-hidden bg-default px-4 py-10">
    <div class="pointer-events-none absolute inset-0">
      <motion.div
        class="absolute -top-24 right-0 size-80 rounded-full bg-primary/20 blur-3xl"
        :animate="{ scale: [1, 1.08, 1], opacity: [0.35, 0.5, 0.35] }"
        :transition="{ duration: 8, repeat: Infinity, ease: 'easeInOut' }"
      />
      <motion.div
        class="absolute bottom-0 left-0 size-72 rounded-full bg-secondary/15 blur-3xl"
        :animate="{ scale: [1, 1.12, 1], opacity: [0.25, 0.4, 0.25] }"
        :transition="{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }"
      />
    </div>

    <div class="relative z-10 grid w-full max-w-5xl gap-10 lg:grid-cols-2 lg:items-center">
      <motion.section
        class="hidden lg:block"
        :initial="{ opacity: 0, x: -24 }"
        :animate="{ opacity: 1, x: 0 }"
        :transition="{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }"
      >
        <UBadge color="primary" variant="subtle" class="mb-4">Firmware Sandbox EMS</UBadge>
        <h1 class="text-3xl font-bold tracking-tight text-highlighted xl:text-4xl">
          在浏览器中
          <span class="text-primary">管理 QEMU 固件实例</span>
        </h1>
        <p class="mt-4 text-muted leading-relaxed">
          启动 OpenWrt / IoT 虚拟机、串口控制台、双栏文件传输与磁盘快照 ——
          面向安全研究与固件实验的一体化控制台。
        </p>
        <ul class="mt-6 space-y-3 text-sm text-toned">
          <motion.li
            v-for="(item, i) in features"
            :key="item.text"
            class="flex items-center gap-2"
            :initial="{ opacity: 0, x: -12 }"
            :animate="{ opacity: 1, x: 0 }"
            :transition="{ delay: 0.15 + i * 0.08, duration: 0.3 }"
          >
            <span class="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
              <UIcon :name="item.icon" class="size-4" />
            </span>
            {{ item.text }}
          </motion.li>
        </ul>
      </motion.section>

      <motion.div
        :initial="{ opacity: 0, y: 16, scale: 0.98 }"
        :animate="{ opacity: 1, y: 0, scale: 1 }"
        :transition="{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay: 0.08 }"
      >
        <UCard
          class="w-full max-w-md mx-auto lg:mx-0 shadow-lg shadow-primary/5 ring-1 ring-default"
          :ui="{ body: 'space-y-5' }"
        >
          <div class="text-center sm:text-left">
            <div class="mb-3 flex items-center justify-center sm:justify-start gap-2">
              <div class="flex size-9 items-center justify-center rounded-lg bg-primary text-inverted text-xs font-bold">
                FS
              </div>
              <span class="text-sm font-semibold text-highlighted">FSEMS</span>
            </div>
            <h2 class="text-lg font-semibold text-highlighted">登录控制台</h2>
            <p class="mt-1 text-sm text-muted">使用管理员凭据进入 FSEMS</p>
          </div>

          <UAlert
            v-if="errorMsg"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            :title="errorMsg"
            class="text-left"
          />

          <form class="space-y-4" @submit.prevent="onSubmit">
            <UFormField label="用户名" name="username">
              <UInput
                v-model="username"
                size="lg"
                autofocus
                autocomplete="username"
                placeholder="请输入用户名"
                icon="i-lucide-user"
                class="w-full"
                :disabled="loading"
              />
            </UFormField>
            <UFormField label="密码" name="password">
              <UInput
                v-model="password"
                size="lg"
                type="password"
                autocomplete="current-password"
                placeholder="••••••••"
                icon="i-lucide-lock"
                class="w-full"
                :disabled="loading"
              />
            </UFormField>
            <UButton
              type="submit"
              size="lg"
              block
              :loading="loading"
              label="进入控制台"
              trailing-icon="i-lucide-arrow-right"
            />
          </form>

          <div class="flex items-center justify-between gap-2">
            <p class="text-xs text-dimmed">
              账号见 <code class="font-mono">.env</code> 的
              <code class="font-mono">FSEMS_ADMIN_*</code>
            </p>
            <UTooltip :text="ui.theme === 'dark' ? '浅色主题' : '深色主题'">
              <UButton
                color="neutral"
                variant="ghost"
                size="sm"
                square
                :icon="ui.theme === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'"
                @click="ui.toggleTheme()"
              />
            </UTooltip>
          </div>
        </UCard>
      </motion.div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { motion } from "motion-v";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();
// 不预填凭据：生产构建下等同于把默认管理员口令公开在登录页
const username = ref("");
const password = ref("");
const loading = ref(false);
const errorMsg = ref("");

const features = [
  { icon: "i-lucide-monitor", text: "TAP 网络 · 真实 SSH 访客机" },
  { icon: "i-lucide-folder-open", text: "宿主机 / 访客机双栏 VFS" },
  { icon: "i-lucide-cpu", text: "多架构模板 · 快照与扩容" },
];

async function onSubmit() {
  errorMsg.value = "";
  if (!username.value.trim() || !password.value) {
    errorMsg.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    await router.push("/instances");
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>
