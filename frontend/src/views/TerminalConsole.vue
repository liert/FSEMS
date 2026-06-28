<!-- 串口控制台组件：以嵌入组件形式展示 QEMU 串口，接受 instanceId 作为参数 -->
<template>
  <div class="console-wrapper">
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

// 初始化终端和 WebSocket 串口连接
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
    term?.writeln("\r\n[WebSocket 串口已连接]\r\n");
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
    term?.writeln("\r\n[WebSocket 串口已断开]\r\n");
  };

  ws.onerror = () => {
    term?.writeln("\r\n[WebSocket 串口发生错误]\r\n");
  };

  term.onData((data) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(new TextEncoder().encode(data));
    }
  });

  window.addEventListener("resize", onResize);
}

function onResize() {
  fitAddon?.fit();
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
  border: 1px solid rgba(255, 255, 255, 0.05);
  overflow: hidden;
}

/* 已移除 redundant console status bar 样式 */

.terminal-body {
  flex: 1;
  padding: 12px;
  background: #181824;
}

/* 覆盖 xterm 背景样式 */
:deep(.xterm-viewport) {
  background-color: #181824 !important;
}
</style>
