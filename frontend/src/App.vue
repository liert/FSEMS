<template>
  <router-view />
</template>

<script setup lang="ts"></script>

<style>
html,
body,
#app {
  margin: 0;
  height: 100%;
  font-family: system-ui, sans-serif;
}

/* 全局滚动条样式定制 */
::-webkit-scrollbar {
  width: 8px; /* 垂直滚动条宽度 */
  height: 8px; /* 水平滚动条高度 */
}

/* 滚动条轨道 */
::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.01);
  border-radius: 4px;
}

/* 滚动条滑块 */
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.3s ease;
}

/* 鼠标悬浮滑块高亮 */
::-webkit-scrollbar-thumb:hover {
  background: rgba(56, 189, 248, 0.35); /* 使用主题蓝色高亮 */
  border-color: rgba(56, 189, 248, 0.2);
}

/* 隐藏滚动条上下箭头按钮 */
::-webkit-scrollbar-button {
  display: none;
}
</style>
