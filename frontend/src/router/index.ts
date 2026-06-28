import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/Login.vue"), meta: { public: true } },
    { path: "/", redirect: "/instances" },
    { path: "/instances", component: () => import("@/views/InstanceList.vue") },
    { path: "/instances/:id/manage", component: () => import("@/views/InstanceManage.vue") },
    { path: "/logs", component: () => import("@/views/LogViewer.vue") },
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
