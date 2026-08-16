export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error_code: string;
  message: string;
}

export type FilesystemType = "ext4" | "squashfs" | "f2fs";

export type SourceFilesystemType = "auto" | FilesystemType;

export interface FilesystemConvertResult {
  source_path: string;
  source_type: FilesystemType;
  target_type: FilesystemType;
  output_path: string;
  output_size_bytes: number;
  duration_ms: number;
}

export interface TokenData {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Template {
  id: number;
  name: string;
  arch: string;
  qemu_binary: string;
  machine: string;
  cpu: string;
  kernel_path: string;
  drive_path: string;
  kernel_append: string;
  ram_size: number;
  guest_ssh_host: string;
  guest_ssh_port: number;
  extra_args: string | null;
}

export interface Instance {
  id: string;
  name: string;
  template_id: number;
  status: string;
  tap_name: string | null;
  guest_ssh_host: string | null;
  guest_ssh_port: number;
  network_type?: string | null;
  bridge_name?: string | null;
  filesystem_type: FilesystemType;
  use_custom_rootfs: boolean;
  cpu: string | null;
  pid: number | null;
  created_at: string;
}

export interface InstanceDetail extends Instance {
  template_name: string;
  template_arch: string;
  template_cpu: string | null;
  effective_cpu: string | null;
  ram_size_mb: number;
  ram_used_mb: number | null;
  drive_path: string | null;
  drive_fs_total_bytes: number | null;
  drive_fs_used_bytes: number | null;
  custom_rootfs_source_path: string | null;
  custom_rootfs_dir_path: string | null;
  custom_rootfs_dir_size_bytes: number | null;
  workspace_path: string;
  kernel_path: string;
  error_msg: string | null;
}

export interface DriveExpandResult {
  expanded_mb: number;
  drive_path: string;
  drive_fs_total_bytes: number | null;
  drive_fs_used_bytes: number | null;
  stopped_for_expand: boolean;
  restarted: boolean;
  status: string;
}

export interface Snapshot {
  id: string;
  instance_id: string;
  name: string;
  image_path: string;
  size_bytes: number;
  created_at: string;
}

export interface SnapshotList {
  list: Snapshot[];
}

export interface SnapshotRestoreResult {
  id: string;
  instance_id: string;
  restored_from: string;
  drive_path: string;
}

export interface SnapshotTaskResponse {
  task_id: string;
  snapshot_id?: string | null;
}

/** 提交时 extra_args 统一规范成字符串（读取侧可能是 null） */
export type TemplateInput = Omit<Template, "id" | "extra_args"> & { extra_args: string };

export interface InstanceList {
  total: number;
  list: Instance[];
}

export interface BackendLogs {
  log_type: string;
  total_lines: number;
  lines: string[];
}

export interface FrontendLog {
  id: number;
  level: string;
  message: string;
  stack?: string;
  url?: string;
  created_at: string;
}

export interface FrontendLogs {
  logs: FrontendLog[];
}

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  mtime: number;
  /** 符号链接标记；rootfs 内大量条目是指向 busybox 的链接 */
  is_link?: boolean;
  link_target?: string | null;
}

export interface HostDirListing {
  current_path: string;
  files: FileEntry[];
  host_root_path?: string | null;
}

export interface GuestDirListing {
  instance_id: string;
  current_path: string;
  files: FileEntry[];
  mode?: "online" | "offline" | string | null;
}

export interface TransferTask {
  task_id: string;
}

export interface HostUploadResult {
  path: string;
  name: string;
  size: number;
}

export interface TaskStatus {
  task_id: string;
  task_type?: string | null;
  status: string; // PENDING, RUNNING, SUCCESS, FAILURE
  progress: number;
  result_ref?: string | null;
  error_msg: string | null;
}
