export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error_code: string;
  message: string;
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
  pid: number | null;
  created_at: string;
}

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
}

export interface HostDirListing {
  current_path: string;
  files: FileEntry[];
}

export interface GuestDirListing {
  instance_id: string;
  current_path: string;
  files: FileEntry[];
}

export interface TransferTask {
  task_id: string;
}

export interface TaskStatus {
  task_id: string;
  status: string; // PENDING, RUNNING, SUCCESS, FAILURE
  progress: number;
  error_msg: string | null;
}
