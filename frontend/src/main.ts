import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";

import App from "./App.vue";
import router from "./router";
import { reportFrontendLog } from "@/api/endpoints";

const app = createApp(App);

// 全端全局异常捕获上报（中文日志，日志等级大写）
app.config.errorHandler = (err: any, _instance, info) => {
  console.error(err);
  reportFrontendLog({
    level: "ERROR",
    message: err?.message || String(err),
    stack: err?.stack || info || "",
    url: window.location.href,
  }).catch((e) => console.error("上报客户端 Vue 异常失败:", e));
};

window.addEventListener("error", (event) => {
  // 忽略 Vue 自行处理的错误
  if (event.message.includes("ResizeObserver")) return;
  reportFrontendLog({
    level: "ERROR",
    message: event.message,
    stack: event.error?.stack || "",
    url: window.location.href,
  }).catch((e) => console.error("上报客户端全局异常失败:", e));
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  reportFrontendLog({
    level: "ERROR",
    message: reason?.message || String(reason),
    stack: reason?.stack || "",
    url: window.location.href,
  }).catch((e) => console.error("上报客户端 Promise 异常失败:", e));
});

app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.mount("#app");
