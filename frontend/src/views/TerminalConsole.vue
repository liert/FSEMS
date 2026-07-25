<template>
  <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-default bg-inverted">
    <div ref="termEl" class="min-h-0 flex-1 p-1" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { consoleWsUrl } from "@/api/endpoints";

const props = defineProps<{ instanceId: string }>();
const termEl = ref<HTMLElement | null>(null);
let term: Terminal | null = null;
let fit: FitAddon | null = null;
let ws: WebSocket | null = null;
let ro: ResizeObserver | null = null;

function connect() {
  disconnect();
  if (!termEl.value) return;
  term = new Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: "ui-monospace, Cascadia Code, Consolas, monospace",
    theme: { background: "#0b0f14", foreground: "#e2e8f0", cursor: "#38bdf8" },
  });
  fit = new FitAddon();
  term.loadAddon(fit);
  term.open(termEl.value);
  fit.fit();
  const url = consoleWsUrl(props.instanceId);
  ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (ev) => {
    if (!term) return;
    if (ev.data instanceof ArrayBuffer) term.write(new Uint8Array(ev.data));
    else term.write(String(ev.data));
  };
  ws.onopen = () => {
    sendResize();
  };
  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
  });
  ro = new ResizeObserver(() => {
    fit?.fit();
    sendResize();
  });
  ro.observe(termEl.value);
}

function sendResize() {
  if (!term || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
}

function disconnect() {
  ro?.disconnect();
  ro = null;
  if (ws) {
    try { ws.close(); } catch { /* */ }
    ws = null;
  }
  term?.dispose();
  term = null;
  fit = null;
}

watch(() => props.instanceId, () => connect());
onMounted(connect);
onBeforeUnmount(disconnect);
</script>
