<template>
  <div class="login-page">
    <div class="login-top-actions">
      <el-tooltip :content="ui.theme === 'dark' ? '切换浅色主题' : '切换深色主题'">
        <el-button class="theme-toggle" text @click="ui.toggleTheme()">
          <el-icon><Moon v-if="ui.theme === 'dark'" /><Sunny v-else /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <div class="login-bg">
      <div class="grid-overlay" />
      <div class="glow glow-a" />
      <div class="glow glow-b" />
    </div>

    <div class="login-layout">
      <section class="login-hero">
        <div class="hero-badge">Firmware Sandbox EMS</div>
        <h1 class="hero-title">
          在浏览器中<br />
          <span class="gradient-text">管理 QEMU 固件实例</span>
        </h1>
        <p class="hero-desc">
          启动 OpenWrt / IoT 虚拟机、串口控制台、双栏文件传输与磁盘快照 —— 面向安全研究与固件实验的一体化控制台。
        </p>
        <ul class="hero-features">
          <li><el-icon><Monitor /></el-icon> TAP 网络 · 真实 SSH 访客机</li>
          <li><el-icon><FolderOpened /></el-icon> 宿主机 / 访客机双栏 VFS</li>
          <li><el-icon><Cpu /></el-icon> 多架构模板 · 快照与扩容</li>
        </ul>
      </section>

      <section class="login-panel glass-card">
        <div class="panel-head">
          <h2>登录控制台</h2>
          <p>使用管理员凭据进入 FSEMS</p>
        </div>

        <el-form class="login-form" @submit.prevent="onSubmit">
          <el-form-item label="用户名">
            <el-input
              v-model="username"
              size="large"
              autocomplete="username"
              placeholder="admin"
            />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="password"
              size="large"
              type="password"
              autocomplete="current-password"
              placeholder="••••••••"
              show-password
              @keyup.enter="onSubmit"
            />
          </el-form-item>
          <el-button type="primary" size="large" native-type="submit" :loading="loading" class="submit-btn">
            进入控制台
          </el-button>
        </el-form>

        <p class="login-footnote">本地开发默认账号见 `.env` 中的 `FSEMS_ADMIN_*` 配置</p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Cpu, FolderOpened, Monitor, Moon, Sunny } from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";

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
    ElMessage.error(e instanceof Error ? e.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
}

.login-top-actions {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 2;
}

.theme-toggle {
  color: var(--fsems-text-muted) !important;
}

.theme-toggle:hover {
  color: var(--fsems-accent) !important;
}

.login-bg {
  position: absolute;
  inset: 0;
  background: var(--fsems-bg-shell);
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--fsems-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--fsems-grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at center, black 30%, transparent 85%);
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.45;
}

.glow-a {
  width: 420px;
  height: 420px;
  top: -120px;
  left: -80px;
  background: #38bdf8;
}

.glow-b {
  width: 360px;
  height: 360px;
  bottom: -100px;
  right: -60px;
  background: #a855f7;
}

.login-layout {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: 1.1fr 420px;
  gap: 48px;
  align-items: center;
}

@media (max-width: 960px) {
  .login-layout {
    grid-template-columns: 1fr;
    max-width: 440px;
  }

  .login-hero {
    display: none;
  }
}

.login-hero {
  padding: 12px 8px;
}

.hero-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fsems-accent);
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.22);
  margin-bottom: 20px;
}

.hero-title {
  margin: 0;
  font-size: clamp(2rem, 4vw, 2.8rem);
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.hero-desc {
  margin: 18px 0 0;
  color: var(--fsems-text-muted);
  font-size: 1rem;
  line-height: 1.7;
  max-width: 520px;
}

.hero-features {
  list-style: none;
  margin: 28px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero-features li {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--fsems-text-muted);
  font-size: 0.92rem;
}

.hero-features .el-icon {
  color: var(--fsems-accent);
}

.login-panel {
  padding: 32px 28px 24px;
}

.panel-head h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
}

.panel-head p {
  margin: 8px 0 0;
  color: var(--fsems-text-dim);
  font-size: 0.88rem;
}

.login-form {
  margin-top: 24px;
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
  font-weight: 600;
}

.login-footnote {
  margin: 18px 0 0;
  text-align: center;
  font-size: 0.78rem;
  color: var(--fsems-text-dim);
}
</style>
