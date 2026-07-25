import { useToast } from "@nuxt/ui/composables";

/** 统一 toast 封装，替代 Element Plus ElMessage */
export function toastSuccess(description: string, title = "成功") {
  const toast = useToast();
  toast.add({ title, description, color: "success", icon: "i-lucide-check-circle" });
}

export function toastError(description: string, title = "错误") {
  const toast = useToast();
  toast.add({ title, description, color: "error", icon: "i-lucide-circle-alert" });
}

export function toastWarning(description: string, title = "注意") {
  const toast = useToast();
  toast.add({ title, description, color: "warning", icon: "i-lucide-triangle-alert" });
}

export function toastInfo(description: string, title = "提示") {
  const toast = useToast();
  toast.add({ title, description, color: "info", icon: "i-lucide-info" });
}
