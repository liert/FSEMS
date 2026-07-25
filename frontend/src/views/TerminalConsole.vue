<template>
  <div
    class="term-shell relative h-full min-h-0 w-full overflow-hidden rounded-lg border border-default bg-inverted shadow-inner"
    @click="focusTerm"
    @mousedown="focusTerm"
  >
    <div
      v-if="status !== 'open'"
      class="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center gap-2 border-b border-white/5 bg-black/40 px-3 py-1.5 text-xs backdrop-blur-sm"
    >
      <span
        class="size-1.5 rounded-full"
        :class="statusDotClass"
      />
      <span class="text-white/70">{{ statusLabel }}</span>
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
import { consoleWsUrl } from "@/api/endpoints";

const props = defineProps<{ instanceId: string }>();

const termHost = ref<HTMLElement | null>(null);
const termEl = ref<HTMLElement | null>(null);
const status = ref<"connecting" | "open" | "closed" | "error">("connecting");

const statusLabel = computed(() => {
  if (status.value === "connecting") return "正在连接串口…";
  if (status.value === "open") return "已连接";
  if (status.value === "error") return "连接失败，请重试";
  return "连接已断开";
});

const statusDotClass = computed(() => {
  if (status.value === "connecting") return "bg-warning animate-pulse";
  if (status.value === "open") return "bg-success";
  if (status.value === "error") return "bg-error";
  return "bg-muted";
});

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
    /* container may be temporarily detached */
  }
  sendResize();
}

function focusTerm() {
  term?.focus();
}

/**
 * 串口协议：键盘输入必须走二进制帧；resize 用 JSON 文本。
 * 后端只对 bytes 调用 write_bytes；纯 text 仅处理 ping/resize。
 */
function sendInput(data: string) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(textEncoder.encode(data));
}

function connect() {
  disconnect();
  if (!termEl.value) return;
  status.value = "connecting";

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
  // 打开后立即抢焦点，否则需要点一下才能输入
  term.focus();

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

  const url = consoleWsUrl(props.instanceId);
  ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    status.value = "open";
    scheduleFit();
    term?.focus();
    term?.writeln("\r\n\x1b[90m[FSEMS] 串口已连接\x1b[0m\r\n");
  };

  ws.onerror = () => {
    status.value = "error";
    term?.writeln("\r\n\x1b[31m[FSEMS] WebSocket 连接错误\x1b[0m\r\n");
  };

  ws.onclose = () => {
    if (status.value !== "error") status.value = "closed";
    term?.writeln("\r\n\x1b[90m[FSEMS] 连接已关闭\x1b[0m\r\n");
  };

  ws.onmessage = (ev) => {
    if (!term) return;
    if (ev.data instanceof ArrayBuffer) term.write(new Uint8Array(ev.data));
    else term.write(String(ev.data));
  };

  term.onData((data) => {
    sendInput(data);
  });

  // 粘贴也走同一路径
  term.attachCustomKeyEventHandler((ev) => {
    // 让浏览器快捷键（复制等）正常工作；输入本身由 onData 处理
    if (ev.ctrlKey && (ev.key === "c" || ev.key === "v") && term?.hasSelection()) {
      return true;
    }
    return true;
  });

  ro = new ResizeObserver(() => scheduleFit());
  if (termHost.value) ro.observe(termHost.value);
  else if (termEl.value) ro.observe(termEl.value);
}

function sendResize() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return;
  if (term.cols < 2 || term.rows < 2) return;
  ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
}

function disconnect() {
  if (fitRaf) {
    cancelAnimationFrame(fitRaf);
    fitRaf = 0;
  }
  ro?.disconnect();
  ro = null;
  if (ws) {
    try {
      ws.close();
    } catch {
      /* ignore */
    }
    ws = null;
  }
  term?.dispose();
  term = null;
  fit = null;
  status.value = "closed";
}

function refit() {
  scheduleFit();
  term?.focus();
}

defineExpose({ refit, focusTerm });

watch(
  () => props.instanceId,
  () => {
    void nextTick(() => connect());
  }
);

onMounted(() => {
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

/* 保证 helper textarea 可聚焦（部分布局会把 z-index:-5 裁切掉） */
.term-shell :deep(.xterm-helpers) {
  z-index: 10;
  position: absolute;
  top: 0;
  left: 0;
}

.term-shell :deep(.xterm-helper-textarea) {
  z-index: 10;
  opacity: 0;
  /* 不要移到屏幕外：overflow:hidden 父级会导致无法聚焦/输入 */
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
