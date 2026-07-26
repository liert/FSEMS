<template>
  <div
    class="term-shell relative h-full min-h-0 w-full overflow-hidden rounded-lg border border-default bg-inverted shadow-inner"
    @click="focusTerm"
    @mousedown="focusTerm"
  >
    <!-- 右上角浮动工具条：清屏 / 重连 / 切换访客串口与宿主机 shell -->
    <div class="absolute right-2 top-2 z-30">
      <div
        class="flex items-center gap-0.5 rounded-lg border border-white/10 bg-black/55 p-0.5 shadow-lg backdrop-blur-sm"
      >
        <UTooltip text="清屏" :content="{ side: 'bottom' }">
          <UButton
            size="xs"
            square
            color="neutral"
            variant="ghost"
            icon="i-lucide-eraser"
            aria-label="清屏"
            class="text-white/55 hover:bg-white/10 hover:text-white"
            @click.stop="clearScreen"
          />
        </UTooltip>
        <UTooltip :text="reconnectTooltip" :content="{ side: 'bottom' }">
          <UButton
            size="xs"
            square
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-cw"
            :loading="status === 'connecting'"
            :aria-label="reconnectTooltip"
            class="text-white/55 hover:bg-white/10 hover:text-white"
            :class="{ 'text-warning': status === 'closed' || status === 'error' }"
            @click.stop="reconnect"
          />
        </UTooltip>
        <span class="mx-0.5 h-4 w-px bg-white/10" />
        <UTooltip :text="switchTooltip" :content="{ side: 'bottom' }">
          <UButton
            size="xs"
            square
            color="neutral"
            variant="ghost"
            :icon="mode === 'guest' ? 'i-lucide-hard-drive' : 'i-lucide-monitor'"
            :aria-label="switchTooltip"
            class="hover:bg-white/10"
            :class="mode === 'host' ? 'bg-primary/25 text-primary' : 'text-white/55 hover:text-white'"
            @click.stop="toggleMode"
          />
        </UTooltip>
      </div>
    </div>

    <div
      v-if="bannerVisible"
      class="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center gap-2 border-b border-white/5 bg-black/45 py-1.5 pl-3 pr-28 text-xs backdrop-blur-sm"
    >
      <span class="size-1.5 shrink-0 rounded-full" :class="statusDotClass" />
      <span class="truncate text-white/70">{{ statusLabel }}</span>
      <UBadge
        size="xs"
        variant="subtle"
        :color="mode === 'host' ? 'primary' : 'neutral'"
        class="ml-auto shrink-0"
      >
        {{ mode === 'host' ? 'RootFS 目录' : '访客串口' }}
      </UBadge>
    </div>

    <div
      v-if="mode === 'guest' && !guestAvailable"
      class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-inverted/95 p-6 text-center"
    >
      <UIcon name="i-lucide-monitor-off" class="size-10 text-muted" />
      <p class="text-sm font-medium text-highlighted">访客串口不可用</p>
      <p class="max-w-xs text-xs text-muted">
        虚拟机未运行时无法连接串口。你仍可以进入该实例的自定义 RootFS 解压目录进行操作。
      </p>
      <UButton
        size="sm"
        color="neutral"
        variant="soft"
        icon="i-lucide-hard-drive"
        label="切换到 RootFS 目录终端"
        @click.stop="toggleMode"
      />
    </div>

    <div ref="termHost" class="absolute inset-0 min-h-0">
      <div ref="termEl" class="h-full w-full" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { consoleWsUrl, hostShellWsUrl } from "@/api/endpoints";

export type ConsoleMode = "guest" | "host";

const props = withDefaults(
  defineProps<{
    instanceId: string;
    /** 访客串口是否可用（实例运行中） */
    guestAvailable?: boolean;
  }>(),
  { guestAvailable: true }
);

const termHost = ref<HTMLElement | null>(null);
const termEl = ref<HTMLElement | null>(null);
const status = ref<"connecting" | "open" | "closed" | "error" | "idle">("idle");
const mode = ref<ConsoleMode>("guest");

const switchTooltip = computed(() =>
  mode.value === "guest" ? "切换到自定义 RootFS 目录终端" : "切换到访客机串口"
);

const reconnectTooltip = computed(() =>
  status.value === "connecting" ? "正在连接…" : "重新连接"
);

const statusLabel = computed(() => {
  if (mode.value === "guest" && !props.guestAvailable) return "访客串口不可用";
  if (status.value === "connecting") {
    return mode.value === "host" ? "正在连接 RootFS 目录 shell…" : "正在连接串口…";
  }
  if (status.value === "open") {
    return mode.value === "host" ? "RootFS 解压目录 shell 已连接" : "串口已连接";
  }
  if (status.value === "error") return "连接失败，请重试";
  if (status.value === "idle") return "就绪";
  return "连接已断开";
});

const statusDotClass = computed(() => {
  if (mode.value === "guest" && !props.guestAvailable) return "bg-muted";
  if (status.value === "connecting") return "bg-warning animate-pulse";
  if (status.value === "open") return "bg-success";
  if (status.value === "error") return "bg-error";
  return "bg-muted";
});

const bannerVisible = computed(
  () => status.value !== "open" || mode.value === "host" || !props.guestAvailable
);

let term: Terminal | null = null;
let fit: FitAddon | null = null;
let ws: WebSocket | null = null;
let ro: ResizeObserver | null = null;
let fitRaf = 0;
const textEncoder = new TextEncoder();

function scheduleFit() {
  if (fitRaf) cancelAnimationFrame(fitRaf);
  fitRaf = requestAnimationFrame(() => {
    fitRaf = 0;
    doFit();
  });
}

function doFit() {
  if (!term || !fit || !termHost.value) return;
  const { clientWidth: w, clientHeight: h } = termHost.value;
  if (w < 20 || h < 20) return;
  try {
    fit.fit();
  } catch {
    /* ignore */
  }
  sendResize();
}

function focusTerm() {
  term?.focus();
}

function sendInput(data: string) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(textEncoder.encode(data));
}

function sendResize() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return;
  if (term.cols < 2 || term.rows < 2) return;
  ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
}

function closeWsOnly() {
  if (ws) {
    // 先摘掉回调：close 事件是异步派发的，否则旧连接的 onclose
    // 会在新会话建立之后才触发，把状态打回 closed 并写入误导性提示
    ws.onopen = null;
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    try {
      ws.close();
    } catch {
      /* ignore */
    }
    ws = null;
  }
}

function ensureTerminal() {
  if (term || !termEl.value) return;
  term = new Terminal({
    cursorBlink: true,
    cursorStyle: "block",
    fontSize: 13,
    fontFamily: "ui-monospace, Cascadia Code, Consolas, monospace",
    theme: {
      background: "#0b0f14",
      foreground: "#e2e8f0",
      cursor: "#38bdf8",
      selectionBackground: "#38bdf855",
    },
    scrollback: 10000,
    convertEol: true,
    allowTransparency: false,
    disableStdin: false,
    macOptionIsMeta: true,
  });
  fit = new FitAddon();
  term.loadAddon(fit);
  term.open(termEl.value);
  term.focus();
  term.onData((data) => {
    sendInput(data);
  });
  term.attachCustomKeyEventHandler((ev) => {
    if (ev.type !== "keydown") return true;
    const mod = ev.ctrlKey || ev.metaKey;
    // 有选中内容时把 Ctrl/Cmd+C 让给浏览器：xterm 的 copy 事件处理器会
    // 用终端选区填充剪贴板。返回 true 只会把它当成 SIGINT 发出去。
    if (mod && !ev.altKey && ev.key.toLowerCase() === "c" && term?.hasSelection()) {
      return false;
    }
    // 粘贴同样交还浏览器，由隐藏 textarea 的 paste 事件处理
    if (mod && ev.key.toLowerCase() === "v") return false;
    return true;
  });
  ro = new ResizeObserver(() => scheduleFit());
  if (termHost.value) ro.observe(termHost.value);
  else if (termEl.value) ro.observe(termEl.value);
}

function connect() {
  ensureTerminal();
  if (!term) return;

  closeWsOnly();

  // 访客不可用且当前是 guest：不连串口
  if (mode.value === "guest" && !props.guestAvailable) {
    status.value = "idle";
    term.clear();
    term.writeln("\r\n\x1b[90m[FSEMS] 访客串口不可用（实例未运行）\x1b[0m");
    term.writeln(
      "\x1b[90m[FSEMS] 点击右上角图标切换到自定义 RootFS 解压目录终端\x1b[0m\r\n"
    );
    return;
  }

  status.value = "connecting";
  term.clear();

  const url =
    mode.value === "host"
      ? hostShellWsUrl(props.instanceId)
      : consoleWsUrl(props.instanceId);

  const socket = new WebSocket(url);
  ws = socket;
  socket.binaryType = "arraybuffer";
  // 所有回调都先确认自己仍是当前连接，避免重连过程中的交叉写入
  const isCurrent = () => ws === socket;

  socket.onopen = () => {
    if (!isCurrent()) return;
    status.value = "open";
    scheduleFit();
    term?.focus();
    if (mode.value === "host") {
      term?.writeln(
        "\r\n\x1b[90m[FSEMS] 已切换到自定义 RootFS 解压目录 shell\x1b[0m\r\n"
      );
    } else {
      term?.writeln("\r\n\x1b[90m[FSEMS] 串口已连接\x1b[0m\r\n");
    }
  };

  socket.onerror = () => {
    if (!isCurrent()) return;
    status.value = "error";
    term?.writeln("\r\n\x1b[31m[FSEMS] WebSocket 连接错误\x1b[0m\r\n");
  };

  socket.onclose = () => {
    if (!isCurrent()) return;
    if (status.value !== "error") status.value = "closed";
    term?.writeln("\r\n\x1b[90m[FSEMS] 连接已关闭，可点击右上角重连\x1b[0m\r\n");
  };

  socket.onmessage = (ev) => {
    if (!isCurrent() || !term) return;
    if (ev.data instanceof ArrayBuffer) term.write(new Uint8Array(ev.data));
    else term.write(String(ev.data));
  };

  void nextTick(() => {
    scheduleFit();
    setTimeout(() => {
      scheduleFit();
      term?.focus();
    }, 50);
    setTimeout(() => {
      scheduleFit();
      term?.focus();
    }, 200);
  });
}

function toggleMode() {
  mode.value = mode.value === "guest" ? "host" : "guest";
  connect();
}

function clearScreen() {
  term?.clear();
  term?.focus();
}

function reconnect() {
  if (status.value === "connecting") return;
  connect();
}

function disconnect() {
  if (fitRaf) {
    cancelAnimationFrame(fitRaf);
    fitRaf = 0;
  }
  ro?.disconnect();
  ro = null;
  closeWsOnly();
  term?.dispose();
  term = null;
  fit = null;
  status.value = "closed";
}

function refit() {
  scheduleFit();
  term?.focus();
}

defineExpose({ refit, focusTerm, toggleMode, reconnect, clearScreen, mode });

watch(
  () => props.instanceId,
  () => {
    void nextTick(() => connect());
  }
);

watch(
  () => props.guestAvailable,
  (ok) => {
    if (!ok && mode.value === "guest") {
      // 串口断开提示；不强制切 host
      closeWsOnly();
      status.value = "idle";
      term?.writeln("\r\n\x1b[90m[FSEMS] 访客串口已断开\x1b[0m\r\n");
    } else if (ok && mode.value === "guest" && status.value !== "open") {
      connect();
    }
  }
);

onMounted(() => {
  // 默认：访客可用则 guest，否则 host
  if (!props.guestAvailable) {
    mode.value = "host";
  }
  void nextTick(() => connect());
});

onBeforeUnmount(disconnect);
</script>

<style scoped>
.term-shell :deep(.xterm) {
  height: 100%;
  width: 100%;
  padding: 6px 8px;
  box-sizing: border-box;
}

.term-shell :deep(.xterm-viewport) {
  overflow-y: scroll !important;
  overscroll-behavior: contain;
}

.term-shell :deep(.xterm-helpers) {
  z-index: 10;
  position: absolute;
  top: 0;
  left: 0;
}

.term-shell :deep(.xterm-helper-textarea) {
  z-index: 10;
  opacity: 0;
  left: 0;
  top: 0;
  width: 1px;
  height: 1px;
  resize: none;
  border: none;
  padding: 0;
  margin: 0;
  overflow: hidden;
  color: transparent;
  background: transparent;
  caret-color: transparent;
}
</style>
