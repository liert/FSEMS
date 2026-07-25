<template>
  <div class="flex h-full min-h-0 flex-col gap-3 p-1">
    <div class="grid min-h-0 flex-1 gap-3 lg:grid-cols-2">
      <!-- Host -->
      <UCard class="flex min-h-0 flex-col overflow-hidden" :ui="{ body: 'flex flex-1 min-h-0 flex-col p-0' }">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="font-semibold">宿主机 (Host)</span>
            <div class="flex gap-1">
              <UButton size="xs" variant="soft" color="neutral" icon="i-lucide-folder-plus" @click="createHostFolder" />
              <UButton size="xs" variant="soft" color="neutral" icon="i-lucide-upload" :loading="hostUploading" @click="triggerHostUpload" />
              <input ref="hostUploadInputRef" type="file" class="hidden" multiple @change="handleHostUploadPick" />
            </div>
          </div>
          <div class="mt-2 flex items-center gap-1 text-xs">
            <UButton size="xs" variant="link" label="root" @click="navigateHost(hostRootPath || '/')" />
            <template v-for="(p, i) in hostParts" :key="i">
              <span class="text-dimmed">/</span>
              <UButton size="xs" variant="link" :label="p.name" @click="navigateHost(p.path)" />
            </template>
          </div>
        </template>
        <div class="min-h-0 flex-1 overflow-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 bg-elevated text-left text-muted">
              <tr>
                <th class="w-10 px-2 py-2" />
                <th class="px-2 py-2">名称</th>
                <th class="w-24 px-2 py-2">大小</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in hostFiles"
                :key="row.path"
                class="cursor-pointer border-t border-muted hover:bg-muted/50"
                :class="{ 'bg-primary/10': selectedHost?.path === row.path }"
                @click="selectedHost = row"
                @dblclick="row.is_dir && enterHostDir(row.name)"
              >
                <td class="px-2 py-1.5">
                  <UIcon :name="row.is_dir ? 'i-lucide-folder' : 'i-lucide-file'" class="size-4" :class="row.is_dir ? 'text-primary' : 'text-muted'" />
                </td>
                <td class="px-2 py-1.5">{{ row.name }}</td>
                <td class="px-2 py-1.5 text-xs text-muted">{{ row.is_dir ? "—" : formatSize(row.size) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!hostLoading && !hostFiles.length" class="py-8 text-center text-muted">空目录</p>
        </div>
      </UCard>

      <!-- Guest -->
      <UCard class="flex min-h-0 flex-col overflow-hidden" :ui="{ body: 'flex flex-1 min-h-0 flex-col p-0' }">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="font-semibold">虚拟机 (Guest)</span>
              <UBadge v-if="guestVfsMode === 'offline'" color="neutral" variant="subtle" size="sm">离线只读</UBadge>
              <UBadge v-else-if="guestVfsMode === 'online'" color="success" variant="subtle" size="sm">在线</UBadge>
            </div>
            <UButton
              v-if="guestCanTransfer"
              size="xs"
              variant="soft"
              color="neutral"
              icon="i-lucide-folder-plus"
              @click="createGuestFolder"
            />
          </div>
          <div v-if="isGuestBrowseable" class="mt-2 flex items-center gap-1 text-xs">
            <UButton size="xs" variant="link" label="root" @click="navigateGuest('/')" />
            <template v-for="(p, i) in guestParts" :key="i">
              <span class="text-dimmed">/</span>
              <UButton size="xs" variant="link" :label="p.name" @click="navigateGuest(p.path)" />
            </template>
          </div>
        </template>

        <div v-if="isGuestTransitioning" class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-muted" />
          <p class="text-sm text-muted">状态切换中…</p>
        </div>
        <div v-else-if="isGuestBrowseable" class="flex min-h-0 flex-1 flex-col">
          <div class="min-h-0 flex-1 overflow-auto">
            <table class="w-full text-sm">
              <thead class="sticky top-0 bg-elevated text-left text-muted">
                <tr>
                  <th class="w-10 px-2 py-2" />
                  <th class="px-2 py-2">名称</th>
                  <th class="w-24 px-2 py-2">大小</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in guestFiles"
                  :key="row.path"
                  class="cursor-pointer border-t border-muted hover:bg-muted/50"
                  :class="{ 'bg-primary/10': selectedGuest?.path === row.path }"
                  @click="selectedGuest = row"
                  @dblclick="row.is_dir && enterGuestDir(row.name)"
                >
                  <td class="px-2 py-1.5">
                    <UIcon :name="row.is_dir ? 'i-lucide-folder' : 'i-lucide-file'" class="size-4" :class="row.is_dir ? 'text-success' : 'text-muted'" />
                  </td>
                  <td class="px-2 py-1.5">{{ row.name }}</td>
                  <td class="px-2 py-1.5 text-xs text-muted">{{ row.is_dir ? "—" : formatSize(row.size) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!guestLoading && !guestFiles.length" class="py-8 text-center text-muted">{{ guestEmptyText }}</p>
          </div>
          <div v-if="guestVfsMode === 'offline'" class="border-t border-muted px-3 py-2 text-xs text-dimmed">
            离线模式：浏览 rootfs.img 磁盘内容。
            <UButton size="xs" variant="link" color="success" label="启动虚拟机" @click="emit('start-instance')" />
          </div>
        </div>
        <div v-else class="flex flex-1 items-center justify-center p-6 text-sm text-muted">无法浏览访客文件系统</div>
      </UCard>
    </div>

    <div class="flex flex-wrap items-center justify-center gap-2">
      <UButton
        icon="i-lucide-arrow-right"
        label="传到访客机"
        size="sm"
        :disabled="!canTransferToGuest"
        :loading="transferring"
        @click="transfer('host_to_guest')"
      />
      <UButton
        icon="i-lucide-arrow-left"
        label="传到宿主机"
        size="sm"
        color="neutral"
        variant="soft"
        :disabled="!canTransferToHost"
        :loading="transferring"
        @click="transfer('guest_to_host')"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  fetchGuestFiles,
  fetchHostFiles,
  guestFsOp,
  uploadHostFile,
  transferFile,
} from "@/api/endpoints";
import type { FileEntry } from "@/api/types";
import { useTaskStore } from "@/stores/tasks";
import { toastError, toastSuccess } from "@/utils/toast";

const props = defineProps<{ instanceId: string; instanceStatus: string }>();
const emit = defineEmits<{ (e: "start-instance"): void }>();

const hostFiles = ref<FileEntry[]>([]);
const guestFiles = ref<FileEntry[]>([]);
const hostCurrentPath = ref("");
const guestCurrentPath = ref("/");
const hostRootPath = ref("");
const hostLoading = ref(false);
const guestLoading = ref(false);
const hostUploading = ref(false);
const transferring = ref(false);
const selectedHost = ref<FileEntry | null>(null);
const selectedGuest = ref<FileEntry | null>(null);
const hostUploadInputRef = ref<HTMLInputElement | null>(null);
const taskStore = useTaskStore();

const guestVfsMode = computed(() => {
  if (props.instanceStatus === "RUNNING") return "online";
  if (props.instanceStatus === "STOPPED") return "offline";
  return "none";
});
const isGuestBrowseable = computed(() => guestVfsMode.value === "online" || guestVfsMode.value === "offline");
const isGuestTransitioning = computed(() =>
  ["STARTING", "STOPPING", "LOADING"].includes(props.instanceStatus)
);
const guestCanTransfer = computed(() => guestVfsMode.value === "online");
const guestEmptyText = computed(() =>
  guestVfsMode.value === "offline" ? "暂无文件 (离线只读)" : "暂无文件"
);
const canTransferToGuest = computed(
  () => guestCanTransfer.value && !!selectedHost.value && !selectedHost.value.is_dir
);
const canTransferToHost = computed(
  () => guestCanTransfer.value && !!selectedGuest.value && !selectedGuest.value.is_dir
);

const hostParts = computed(() => {
  const root = hostRootPath.value;
  const cur = hostCurrentPath.value;
  if (!root || !cur.startsWith(root)) return [];
  const rel = cur.slice(root.length).replace(/^\/+/, "");
  if (!rel) return [];
  const segs = rel.split("/").filter(Boolean);
  let acc = root;
  return segs.map((name) => {
    acc = acc.endsWith("/") ? acc + name : `${acc}/${name}`;
    return { name, path: acc };
  });
});

const guestParts = computed(() => {
  const cur = guestCurrentPath.value.replace(/\/+$/, "") || "/";
  if (cur === "/") return [];
  const segs = cur.split("/").filter(Boolean);
  let acc = "";
  return segs.map((name) => {
    acc += `/${name}`;
    return { name, path: acc };
  });
});

function formatSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

async function loadHost() {
  hostLoading.value = true;
  try {
    const data = await fetchHostFiles(hostCurrentPath.value || undefined, props.instanceId);
    hostFiles.value = data.files;
    hostCurrentPath.value = data.current_path;
    if (data.host_root_path) hostRootPath.value = data.host_root_path;
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "加载宿主机目录失败");
  } finally {
    hostLoading.value = false;
  }
}

async function loadGuest() {
  if (!isGuestBrowseable.value) {
    guestFiles.value = [];
    return;
  }
  guestLoading.value = true;
  try {
    const mode = guestVfsMode.value === "offline" ? "offline" : "online";
    const data = await fetchGuestFiles(props.instanceId, guestCurrentPath.value, mode);
    guestFiles.value = data.files;
    guestCurrentPath.value = data.current_path || guestCurrentPath.value;
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "加载访客目录失败");
    guestFiles.value = [];
  } finally {
    guestLoading.value = false;
  }
}

function navigateHost(path: string) {
  hostCurrentPath.value = path;
  selectedHost.value = null;
  void loadHost();
}
function enterHostDir(name: string) {
  const base = hostCurrentPath.value.replace(/\/+$/, "");
  navigateHost(`${base}/${name}`);
}
function navigateGuest(path: string) {
  guestCurrentPath.value = path;
  selectedGuest.value = null;
  void loadGuest();
}
function enterGuestDir(name: string) {
  const base = guestCurrentPath.value.replace(/\/+$/, "") || "";
  navigateGuest(base === "/" || base === "" ? `/${name}` : `${base}/${name}`);
}

async function createHostFolder() {
  toastError("当前后端未提供宿主机新建文件夹接口");
}

async function createGuestFolder() {
  const name = window.prompt("新建文件夹名称");
  if (!name?.trim()) return;
  const base = guestCurrentPath.value.replace(/\/+$/, "") || "";
  const path = base === "/" || base === "" ? `/${name.trim()}` : `${base}/${name.trim()}`;
  try {
    await guestFsOp(props.instanceId, "mkdir", path);
    toastSuccess("已创建");
    await loadGuest();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "创建失败");
  }
}

function triggerHostUpload() {
  hostUploadInputRef.value?.click();
}

async function handleHostUploadPick(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (!files.length) return;
  hostUploading.value = true;
  try {
    for (const f of files) {
      await uploadHostFile(f, hostCurrentPath.value, props.instanceId);
    }
    toastSuccess("上传完成");
    await loadHost();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "上传失败");
  } finally {
    hostUploading.value = false;
    input.value = "";
  }
}

async function transfer(direction: "host_to_guest" | "guest_to_host") {
  if (direction === "host_to_guest" && !selectedHost.value) return;
  if (direction === "guest_to_host" && !selectedGuest.value) return;
  transferring.value = true;
  try {
    const src =
      direction === "host_to_guest" ? selectedHost.value!.path : selectedGuest.value!.path;
    const fileName = src.split("/").pop() || "file";
    const destDir = direction === "host_to_guest" ? guestCurrentPath.value : hostCurrentPath.value;
    const dest = destDir.endsWith("/") ? destDir + fileName : `${destDir}/${fileName}`;
    const task = await transferFile(props.instanceId, direction, src, dest);
    await taskStore.trackTaskAsync(task.task_id, {
      label: direction === "host_to_guest" ? "传到访客机" : "传到宿主机",
      detail: fileName,
      successMessage: "传输完成",
      onSuccess: async () => {
        if (direction === "host_to_guest") await loadGuest();
        else await loadHost();
      },
    });
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "传输失败");
  } finally {
    transferring.value = false;
  }
}

watch(
  () => props.instanceStatus,
  () => {
    void loadGuest();
  }
);

onMounted(async () => {
  await loadHost();
  await loadGuest();
});
</script>
