import request, { unwrap } from "./request";
import type { ApiResponse, Instance, InstanceDetail, InstanceList, Template, TemplateInput, TokenData, BackendLogs, FrontendLogs, HostDirListing, GuestDirListing, TransferTask, TaskStatus, DriveExpandResult, Snapshot, SnapshotList, SnapshotTaskResponse, HostUploadResult } from "./types";

export function login(username: string, password: string) {
  return unwrap(
    request.post<ApiResponse<TokenData>>("/auth/login", { username, password })
  );
}

export function fetchTemplates(arch?: string) {
  return unwrap(
    request.get<ApiResponse<Template[]>>("/templates", { params: arch ? { arch } : undefined })
  );
}

export function createTemplate(body: TemplateInput) {
  return unwrap(request.post<ApiResponse<Template>>("/templates", body));
}

export function updateTemplate(id: number, body: Partial<TemplateInput>) {
  return unwrap(request.put<ApiResponse<Template>>(`/templates/${id}`, body));
}

export function deleteTemplate(id: number) {
  return unwrap(request.delete<ApiResponse<void>>(`/templates/${id}`));
}

export function fetchInstances(page = 1, limit = 20) {
  return unwrap(
    request.get<ApiResponse<InstanceList>>("/instances", { params: { page, limit } })
  );
}

export function fetchInstanceDetail(id: string) {
  return unwrap(
    request.get<ApiResponse<InstanceDetail>>(`/instances/${id}`)
  );
}

export function createInstance(
  name: string,
  templateId: number,
  rootfsPath?: string,
  networkType?: "same" | "different"
) {
  return unwrap(
    request.post<ApiResponse<{ id: string; status: string }>>("/instances", {
      name,
      template_id: templateId,
      rootfs_path: rootfsPath || null,
      network_type: networkType || "same",
    })
  );
}

export function instanceAction(
  id: string,
  action: "start" | "stop" | "reset",
  options?: { allowSigkill?: boolean; timeoutMs?: number }
) {
  return unwrap(
    request.post<ApiResponse<{ id: string; status: string }>>(
      `/instances/${id}/action`,
      {
        action,
        allow_sigkill: options?.allowSigkill,
      },
      { timeout: options?.timeoutMs ?? 30000 }
    )
  );
}

export function expandInstanceDrive(
  instanceId: string,
  expandMb: number,
  manageLifecycle = false
) {
  return unwrap(
    request.post<ApiResponse<DriveExpandResult>>(
      `/instances/${instanceId}/drive/expand`,
      { expand_mb: expandMb, manage_lifecycle: manageLifecycle },
      { timeout: 120000 }
    )
  );
}

export function deleteInstance(id: string) {
  return unwrap(
    request.delete<ApiResponse<void>>(`/instances/${id}`)
  );
}

export function fetchSnapshots(instanceId: string) {
  return unwrap(request.get<ApiResponse<SnapshotList>>(`/instances/${instanceId}/snapshots`));
}

export function createSnapshot(instanceId: string, name: string) {
  return unwrap(
    request.post<ApiResponse<SnapshotTaskResponse>>(`/instances/${instanceId}/snapshots`, { name })
  );
}

export function restoreSnapshot(instanceId: string, snapshotId: string) {
  return unwrap(
    request.post<ApiResponse<SnapshotTaskResponse>>(
      `/instances/${instanceId}/snapshots/${snapshotId}/restore`
    )
  );
}

export function deleteSnapshot(instanceId: string, snapshotId: string) {
  return unwrap(
    request.delete<ApiResponse<void>>(`/instances/${instanceId}/snapshots/${snapshotId}`)
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

export function uploadHostFile(file: File, path: string, instanceId?: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("path", path);
  if (instanceId) {
    form.append("instance_id", instanceId);
  }
  return unwrap(
    request.post<ApiResponse<HostUploadResult>>("/fs/host/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
}

export function guestFsOp(
  instanceId: string,
  op: "mkdir" | "delete" | "rename",
  path: string,
  destPath?: string
) {
  return unwrap(
    request.post<ApiResponse<{ op: string; path: string; dest_path?: string | null }>>(
      `/fs/guest/${instanceId}/ops`,
      { op, path, dest_path: destPath ?? null }
    )
  );
}

export function fetchTaskStatus(taskId: string) {
  return unwrap(
    request.get<ApiResponse<TaskStatus>>(`/tasks/${taskId}/status`)
  );
}
