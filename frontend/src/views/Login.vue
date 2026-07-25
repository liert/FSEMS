<template>
  <div class="relative flex min-h-dvh items-center justify-center overflow-hidden bg-default px-4">
    <div class="pointer-events-none absolute inset-0 opacity-40">
      <div class="absolute -top-24 right-0 size-80 rounded-full bg-primary/20 blur-3xl" />
      <div class="absolute bottom-0 left-0 size-72 rounded-full bg-secondary/15 blur-3xl" />
    </div>

    <div class="relative z-10 grid w-full max-w-5xl gap-10 lg:grid-cols-2 lg:items-center">
      <section class="hidden lg:block">
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
          <li class="flex items-center gap-2">
            <UIcon name="i-lucide-monitor" class="size-4 text-primary" />
            TAP 网络 · 真实 SSH 访客机
          </li>
          <li class="flex items-center gap-2">
            <UIcon name="i-lucide-folder-open" class="size-4 text-primary" />
            宿主机 / 访客机双栏 VFS
          </li>
          <li class="flex items-center gap-2">
            <UIcon name="i-lucide-cpu" class="size-4 text-primary" />
            多架构模板 · 快照与扩容
          </li>
        </ul>
      </section>

      <UCard class="w-full max-w-md mx-auto lg:mx-0" :ui="{ body: 'space-y-5' }">
        <div class="text-center sm:text-left">
          <h2 class="text-lg font-semibold text-highlighted">登录控制台</h2>
          <p class="mt-1 text-sm text-muted">使用管理员凭据进入 FSEMS</p>
        </div>

        <form class="space-y-4" @submit.prevent="onSubmit">
          <UFormField label="用户名" name="username">
            <UInput v-model="username" size="lg" autocomplete="username" placeholder="admin" class="w-full" />
          </UFormField>
          <UFormField label="密码" name="password">
            <UInput
              v-model="password"
              size="lg"
              type="password"
              autocomplete="current-password"
              placeholder="••••••••"
              class="w-full"
            />
          </UFormField>
          <UButton type="submit" size="lg" block :loading="loading" label="进入控制台" />
        </form>

        <p class="text-center text-xs text-dimmed">
          本地开发默认账号见 <code class="font-mono">.env</code> 中的
          <code class="font-mono">FSEMS_ADMIN_*</code>
        </p>

        <div class="flex justify-end">
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            :icon="ui.theme === 'dark' ? 'i-lucide-sun' : 'i-lucide-moon'"
            @click="ui.toggleTheme()"
          />
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { toastError } from "@/utils/toast";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();
const username = ref("admin");
const password = ref("admin");
const loading = ref(false);

async function onSubmit() {
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    await router.push("/instances");
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>
