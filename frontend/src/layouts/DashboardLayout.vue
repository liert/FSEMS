<template>
  <AppShell>
    <!--
      UDashboardGroup 要求 UDashboardPanel 作为直接 flex 子节点。
      不要在这里包 Transition / motion.div，否则右侧内容区会塌缩成白屏。
    -->
    <RouterView />
  </AppShell>
</template>

<script setup lang="ts">
import AppShell from "./AppShell.vue";
</script>
