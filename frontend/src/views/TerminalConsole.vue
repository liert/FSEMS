<!-- 控制台组件：以嵌入形式展示 QEMU 串口，接受 instanceId 作为参数 -->
<template>
  <div class="console-wrapper">
    <div class="console-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">控制台</span>
        <span class="toolbar-sub">QEMU · WebSocket</span>
      </div>
      <div class="toolbar-right">
        <span class="conn-pill" :class="{ online: connected }">
          <span class="conn-dot" />
          {{ connected ? "已连接" : "连接中…" }}
        </span>
      </div>
    </div>
    <div ref="termEl" class="terminal-body" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { consoleWsUrl } from "@/api/endpoints";

const props = defineProps<{
  instanceId: string;
}>();

const termEl = ref<HTMLElement | null>(null);
const connected = ref(false);

let term: Terminal | null = null;
let fitAddon: FitAddon | null = null;
let ws: WebSocket | null = null;
let pingTimer: ReturnType<typeof setInterval> | null = null;

// 初始化终端和 WebSocket 连接
function initTerminal() {
  if (!termEl.value) return;
  
  // 销毁旧连接以防内存泄漏
  cleanup();

  term = new Terminal({ 
    cursorBlink: true, 
    fontSize: 14,
    theme: {
      background: '#181824',
      foreground: '#cbd5e1',
      cursor: '#38bdf8'
    }
  });
  fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.open(termEl.value);
  fitAddon.fit();

  const url = consoleWsUrl(props.instanceId);
  ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    connected.value = true;
    term?.writeln("\r\n[控制台已连接]\r\n");
    sendTerminalSize();
    pingTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) ws.send("ping");
    }, 30000);
  };

  ws.onmessage = (ev) => {
    if (typeof ev.data === "string") {
      if (ev.data === "pong") return;
      term?.write(ev.data);
      return;
    }
    term?.write(new Uint8Array(ev.data));
  };

  ws.onclose = () => {
    connected.value = false;
    term?.writeln("\r\n[控制台已断开]\r\n");
  };

  ws.onerror = () => {
    term?.writeln("\r\n[控制台连接错误]\r\n");
  };

  term.onData((data) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(new TextEncoder().encode(data));
    }
  });

  window.addEventListener("resize", onResize);
}

function sendTerminalSize() {
  fitAddon?.fit();
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
}

function onResize() {
  sendTerminalSize();
}

function cleanup() {
  window.removeEventListener("resize", onResize);
  if (pingTimer) clearInterval(pingTimer);
  ws?.close();
  term?.dispose();
  term = null;
  ws = null;
}

// 监听实例 ID 切换时重新连接
watch(() => props.instanceId, () => {
  initTerminal();
});

onMounted(() => {
  initTerminal();
});

onBeforeUnmount(() => {
  cleanup();
});
</script>

<style scoped>
.console-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #181824;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.console-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.toolbar-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.toolbar-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: #e2e8f0;
}

.toolbar-sub {
  font-size: 0.75rem;
  color: #64748b;
}

.conn-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  color: #94a3b8;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.conn-pill.online {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.25);
  background: rgba(52, 211, 153, 0.08);
}

.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64748b;
}

.conn-pill.online .conn-dot {
  background: #34d399;
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.8);
}

.terminal-body {
  flex: 1;
  min-height: 0;
  padding: 8px 12px 12px;
  background: #181824;
}

/* 覆盖 xterm 背景样式 */
:deep(.xterm-viewport) {
  background-color: #181824 !important;
}
</style>
