<template>
  <!--
    仅包裹 Panel 内部内容，不参与路由层。
    禁止用 Transition/motion 包裹 UDashboardPanel（多根节点 + flex 子级会导致白屏）。
  -->
  <div class="page-content flex h-full min-h-0 flex-col" :class="attrs.class">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { useAttrs } from "vue";

defineOptions({ inheritAttrs: false });
const attrs = useAttrs();
</script>
