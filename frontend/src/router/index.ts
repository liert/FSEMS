import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      component: () => import("@/views/Login.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: () => import("@/layouts/DashboardLayout.vue"),
      children: [
        { path: "", redirect: "/instances" },
        {
          path: "instances",
          component: () => import("@/views/InstanceList.vue"),
          meta: { title: "实例管理" },
        },
        {
          path: "templates",
          component: () => import("@/views/TemplateList.vue"),
          meta: { title: "固件模板" },
        },
        {
          path: "logs",
          component: () => import("@/views/LogViewer.vue"),
          meta: { title: "系统日志" },
        },
        {
          path: "settings",
          component: () => import("@/views/Settings.vue"),
          meta: { title: "系统设置" },
        },
        {
          path: "instances/:id/manage",
          component: () => import("@/views/InstanceManage.vue"),
          meta: { title: "实例详情", fullBleed: true },
        },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isLoggedIn()) {
    return "/login";
  }
  if (to.path === "/login" && auth.isLoggedIn()) {
    return "/instances";
  }
});

export default router;
