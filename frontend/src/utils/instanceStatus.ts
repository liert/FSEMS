export const INSTANCE_STATUS_LABELS: Record<string, string> = {
  LOADING: "加载中",
  STARTING: "启动中",
  RUNNING: "运行中",
  STOPPING: "停止中",
  STOPPED: "已停止",
};

export function statusLabel(status: string): string {
  return INSTANCE_STATUS_LABELS[status] || status;
}

export function statusTagType(status: string): "success" | "warning" | "info" | "danger" {
  if (status === "RUNNING") return "success";
  if (status === "STARTING") return "warning";
  if (status === "STOPPED") return "info";
  return "danger";
}

export function shortInstanceId(id: string): string {
  if (id.startsWith("inst_") && id.length > 22) {
    return `inst_${id.slice(5, 13)}…${id.slice(-4)}`;
  }
  if (id.length > 24) {
    return `${id.slice(0, 20)}…`;
  }
  return id;
}
