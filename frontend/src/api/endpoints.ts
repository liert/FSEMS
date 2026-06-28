import request, { unwrap } from "./request";
import type { ApiResponse, Instance, InstanceList, Template, TokenData, BackendLogs, FrontendLogs, HostDirListing, GuestDirListing, TransferTask, TaskStatus } from "./types";

export function login(username: string, password: string) {
  return unwrap(
    request.post<ApiResponse<TokenData>>("/auth/login", { username, password })
  );
}

export function fetchTemplates() {
  return unwrap(request.get<ApiResponse<Template[]>>("/templates"));
}

export function fetchInstances(page = 1, limit = 20) {
  return unwrap(
    request.get<ApiResponse<InstanceList>>("/instances", { params: { page, limit } })
  );
}

export function fetchInstanceDetail(id: string) {
  return unwrap(
    request.get<ApiResponse<Instance>>(`/instances/${id}`)
  );
}

export function createInstance(
  name: string,
  templateId: number,
  rootfsPath?: string
) {
  return unwrap(
    request.post<ApiResponse<{ id: string; status: string }>>("/instances", {
      name,
      template_id: templateId,
      rootfs_path: rootfsPath || null,
    })
  );
}

export function instanceAction(id: string, action: "start" | "stop" | "reset") {
  return unwrap(
    request.post<ApiResponse<{ id: string; status: string }>>(`/instances/${id}/action`, {
      action,
    })
  );
}

export function deleteInstance(id: string) {
  return unwrap(
    request.delete<ApiResponse<void>>(`/instances/${id}`)
  );
}

export function consoleWsUrl(id: string): string {
  const token = localStorage.getItem("fsems_token") || "";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/v1/instances/${id}/console?token=${encodeURIComponent(token)}`;
}

export function fetchBackendLogs(type = "fastapi", lines = 100, offset = 0) {
  return unwrap(
    request.get<ApiResponse<BackendLogs>>("/logs/backend", { params: { type, lines, offset } })
  );
}

export function reportFrontendLog(log: { level: string; message: string; stack?: string; url?: string }) {
  return unwrap(
    request.post<ApiResponse<void>>("/logs/frontend", log)
  );
}

export function fetchFrontendLogs(limit = 50, offset = 0) {
  return unwrap(
    request.get<ApiResponse<FrontendLogs>>("/logs/frontend", { params: { limit, offset } })
  );
}

export function fetchHostFiles(path = "", instanceId?: string) {
  return unwrap(
    request.get<ApiResponse<HostDirListing>>("/fs/host", {
      params: { path, instance_id: instanceId },
    })
  );
}

export function fetchGuestFiles(instanceId: string, path = "/", mode = "online") {
  return unwrap(
    request.get<ApiResponse<GuestDirListing>>(`/fs/guest/${instanceId}`, {
      params: { path, mode },
    })
  );
}

export function transferFile(instanceId: string, direction: "host_to_guest" | "guest_to_host", src: string, dest: string) {
  return unwrap(
    request.post<ApiResponse<TransferTask>>("/fs/transfer", {
      instance_id: instanceId,
      direction,
      src,
      dest,
    })
  );
}

export function fetchTaskStatus(taskId: string) {
  return unwrap(
    request.get<ApiResponse<TaskStatus>>(`/tasks/${taskId}/status`)
  );
}
