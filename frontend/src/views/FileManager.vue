<template>
  <div class="grid h-full min-h-0 gap-3 p-1 lg:grid-cols-2">
    <!-- ============ 宿主机 ============ -->
    <UCard
      class="flex min-h-0 flex-col overflow-hidden ring-1 ring-default/40"
      :ui="{ body: 'flex flex-1 min-h-0 flex-col p-0', header: 'py-2' }"
    >
      <template #header>
        <div class="flex items-center gap-2">
          <div class="flex min-w-0 items-center gap-1.5">
            <UIcon name="i-lucide-monitor" class="size-4 shrink-0 text-primary" />
            <span class="truncate text-sm font-semibold">宿主机</span>
            <UBadge v-if="hostFiles.length" color="neutral" variant="subtle" size="sm">
              {{ hostFiles.length }}
            </UBadge>
          </div>
          <div class="ml-auto flex shrink-0 items-center gap-0.5">
            <UTooltip text="返回上级">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-corner-left-up"
                aria-label="返回上级"
                :disabled="!hostParentPath"
                @click="navigateHost(hostParentPath!)"
              />
            </UTooltip>
            <UTooltip text="新建文件夹">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-folder-plus"
                aria-label="新建文件夹"
                @click="openCreateFolder('host')"
              />
            </UTooltip>
            <UTooltip text="上传文件到当前目录">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-upload"
                aria-label="上传"
                :loading="hostUploading"
                @click="triggerHostUpload"
              />
            </UTooltip>
            <UTooltip text="刷新">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-refresh-cw"
                aria-label="刷新"
                :loading="hostLoading"
                @click="loadHost()"
              />
            </UTooltip>
            <input ref="hostUploadInputRef" type="file" class="hidden" multiple @change="handleHostUploadPick" />
          </div>
        </div>

        <!-- 面包屑与筛选同属「当前目录」范畴，合并成一行，省下一整行高度 -->
        <div class="mt-1.5 flex items-center gap-2">
          <div class="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto whitespace-nowrap font-mono text-xs">
            <UTooltip text="回到根目录">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-hard-drive"
                aria-label="回到根目录"
                class="shrink-0"
                @click="navigateHost(hostRootPath || '/')"
              />
            </UTooltip>
            <template v-for="p in hostParts" :key="p.path">
              <span class="shrink-0 text-dimmed">/</span>
              <UButton size="xs" variant="link" :label="p.name" class="min-w-0 shrink-0 px-0.5" @click="navigateHost(p.path)" />
            </template>
          </div>

          <UInput
            v-model="hostSearch"
            icon="i-lucide-search"
            size="xs"
            placeholder="筛选"
            class="w-24 shrink-0 sm:w-32"
            :ui="{ trailing: 'pe-1' }"
          >
            <template v-if="hostSearch" #trailing>
              <UButton color="neutral" variant="link" size="xs" icon="i-lucide-x" aria-label="清除筛选" @click="hostSearch = ''" />
            </template>
          </UInput>
        </div>
      </template>

      <UContextMenu :items="hostMenuItems" :ui="{ content: 'w-60' }">
        <div
          class="min-h-0 flex-1 overflow-auto outline-none"
          tabindex="0"
          @contextmenu="onPanelContextMenu('host', $event)"
          @keydown="onPanelKeydown('host', $event)"
        >
          <LoadingState v-if="hostLoading && !hostFiles.length" description="正在读取宿主机目录…" />
          <table v-else-if="filteredHostFiles.length" class="w-full text-sm">
            <thead class="sticky top-0 z-[1] border-b border-default bg-elevated/95 text-left text-muted backdrop-blur-sm">
              <tr>
                <th class="w-10 px-2 py-2" />
                <th class="px-2 py-2 font-medium">名称</th>
                <th class="w-20 px-2 py-2 text-right font-medium">大小</th>
                <th class="hidden w-28 px-2 py-2 text-right font-medium xl:table-cell">修改时间</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredHostFiles"
                :key="row.path"
                :data-path="row.path"
                class="table-row-interactive cursor-pointer border-t border-muted"
                :class="rowClass(selectedHost?.path === row.path)"
                :title="rowTitle(row)"
                @click="selectRow('host', row, $event)"
                @dblclick="openEntry('host', row)"
              >
                <td class="px-2 py-1.5">
                  <UIcon
                    :name="entryIcon(row)"
                    class="size-4"
                    :class="row.is_dir ? 'text-primary' : 'text-muted'"
                  />
                </td>
                <td class="max-w-0 truncate px-2 py-1.5">
                  <span v-if="!hostSearch.trim()">{{ row.name }}</span>
                  <span v-else v-html="highlightName(row.name, hostSearch)" />
                  <span v-if="row.is_link && row.link_target" class="ml-1.5 text-xs text-dimmed">
                    → {{ row.link_target }}
                  </span>
                </td>
                <td class="px-2 py-1.5 text-right text-xs tabular-nums text-muted">
                  {{ row.is_dir ? "—" : formatSize(row.size) }}
                </td>
                <td class="hidden px-2 py-1.5 text-right text-xs tabular-nums text-dimmed xl:table-cell">
                  {{ formatMtime(row.mtime) }}
                </td>
              </tr>
            </tbody>
          </table>
          <EmptyState
            v-else-if="hostSearch.trim()"
            title="没有匹配项"
            :description="`当前目录下没有名称包含「${hostSearch.trim()}」的文件`"
            icon="i-lucide-search-x"
            size="sm"
          >
            <template #action>
              <UButton size="sm" color="neutral" variant="soft" label="清除筛选" @click="hostSearch = ''" />
            </template>
          </EmptyState>
          <EmptyState v-else title="空目录" description="右键空白处可新建文件夹或上传文件" icon="i-lucide-folder-open" size="sm" />
        </div>
      </UContextMenu>
    </UCard>

    <!-- ============ 虚拟机 ============ -->
    <UCard
      class="flex min-h-0 flex-col overflow-hidden ring-1 ring-default/40"
      :ui="{ body: 'flex flex-1 min-h-0 flex-col p-0', header: 'py-2' }"
    >
      <template #header>
        <div class="flex items-center gap-2">
          <div class="flex min-w-0 items-center gap-1.5">
            <UIcon name="i-lucide-hard-drive" class="size-4 shrink-0 text-success" />
            <span class="truncate text-sm font-semibold">虚拟机</span>
            <UTooltip :text="guestModeHint">
              <UBadge :color="guestModeBadge.color" variant="subtle" size="sm">{{ guestModeBadge.label }}</UBadge>
            </UTooltip>
          </div>
          <div v-if="isGuestBrowseable" class="ml-auto flex shrink-0 items-center gap-0.5">
            <UTooltip text="返回上级">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-corner-left-up"
                aria-label="返回上级"
                :disabled="!guestParentPath"
                @click="navigateGuest(guestParentPath!)"
              />
            </UTooltip>
            <UTooltip :text="guestCanWrite ? '新建文件夹' : '离线模式为只读'">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-folder-plus"
                aria-label="新建文件夹"
                :disabled="!guestCanWrite"
                @click="openCreateFolder('guest')"
              />
            </UTooltip>
            <UTooltip text="刷新">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-refresh-cw"
                aria-label="刷新"
                :loading="guestLoading"
                @click="loadGuest()"
              />
            </UTooltip>
          </div>
        </div>

        <div v-if="isGuestBrowseable" class="mt-1.5 flex items-center gap-2">
          <div class="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto whitespace-nowrap font-mono text-xs">
            <UTooltip text="回到根目录">
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                square
                icon="i-lucide-folder-root"
                aria-label="回到根目录"
                class="shrink-0"
                @click="navigateGuest('/')"
              />
            </UTooltip>
            <template v-for="p in guestParts" :key="p.path">
              <span class="shrink-0 text-dimmed">/</span>
              <UButton size="xs" variant="link" :label="p.name" class="min-w-0 shrink-0 px-0.5" @click="navigateGuest(p.path)" />
            </template>
          </div>

          <UInput
            v-model="guestSearch"
            icon="i-lucide-search"
            size="xs"
            placeholder="筛选"
            class="w-24 shrink-0 sm:w-32"
            :ui="{ trailing: 'pe-1' }"
          >
            <template v-if="guestSearch" #trailing>
              <UButton color="neutral" variant="link" size="xs" icon="i-lucide-x" aria-label="清除筛选" @click="guestSearch = ''" />
            </template>
          </UInput>
        </div>
      </template>

      <div v-if="isGuestTransitioning" class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
        <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-muted" />
        <p class="text-sm text-muted">虚拟机状态切换中…</p>
      </div>

      <div v-else-if="isGuestBrowseable" class="flex min-h-0 flex-1 flex-col">
        <UContextMenu :items="guestMenuItems" :ui="{ content: 'w-60' }">
          <div
            class="min-h-0 flex-1 overflow-auto outline-none"
            tabindex="0"
            @contextmenu="onPanelContextMenu('guest', $event)"
            @keydown="onPanelKeydown('guest', $event)"
          >
            <LoadingState v-if="guestLoading && !guestFiles.length" description="正在读取访客文件系统…" />
            <table v-else-if="filteredGuestFiles.length" class="w-full text-sm">
              <thead class="sticky top-0 z-[1] border-b border-default bg-elevated/95 text-left text-muted backdrop-blur-sm">
                <tr>
                  <th class="w-10 px-2 py-2" />
                  <th class="px-2 py-2 font-medium">名称</th>
                  <th class="w-20 px-2 py-2 text-right font-medium">大小</th>
                  <th class="hidden w-28 px-2 py-2 text-right font-medium xl:table-cell">修改时间</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in filteredGuestFiles"
                  :key="row.path"
                  :data-path="row.path"
                  class="table-row-interactive cursor-pointer border-t border-muted"
                  :class="rowClass(selectedGuest?.path === row.path)"
                  :title="rowTitle(row)"
                  @click="selectRow('guest', row, $event)"
                  @dblclick="openEntry('guest', row)"
                >
                  <td class="px-2 py-1.5">
                    <UIcon
                      :name="entryIcon(row)"
                      class="size-4"
                      :class="row.is_dir ? 'text-success' : 'text-muted'"
                    />
                  </td>
                  <td class="max-w-0 truncate px-2 py-1.5">
                    <span v-if="!guestSearch.trim()">{{ row.name }}</span>
                    <span v-else v-html="highlightName(row.name, guestSearch)" />
                    <span v-if="row.is_link && row.link_target" class="ml-1.5 text-xs text-dimmed">
                      → {{ row.link_target }}
                    </span>
                  </td>
                  <td class="px-2 py-1.5 text-right text-xs tabular-nums text-muted">
                    {{ row.is_dir ? "—" : formatSize(row.size) }}
                  </td>
                  <td class="hidden px-2 py-1.5 text-right text-xs tabular-nums text-dimmed xl:table-cell">
                    {{ formatMtime(row.mtime) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-else-if="guestSearch.trim()"
              title="没有匹配项"
              :description="`当前目录下没有名称包含「${guestSearch.trim()}」的文件`"
              icon="i-lucide-search-x"
              size="sm"
            >
              <template #action>
                <UButton size="sm" color="neutral" variant="soft" label="清除筛选" @click="guestSearch = ''" />
              </template>
            </EmptyState>
            <EmptyState
              v-else
              :title="guestCanWrite ? '空目录' : '空目录（离线只读）'"
              :description="guestCanWrite ? '右键空白处可新建文件夹' : '离线模式直接读取磁盘镜像，只能浏览'"
              icon="i-lucide-folder-open"
              size="sm"
            />
          </div>
        </UContextMenu>

        <div
          v-if="guestVfsMode === 'offline'"
          class="flex flex-wrap items-center gap-x-1 border-t border-muted px-3 py-2 text-xs text-dimmed"
        >
          <UIcon name="i-lucide-info" class="size-3.5" />
          <span>离线模式直接读取 rootfs.img，只能浏览。</span>
          <UButton size="xs" variant="link" color="success" label="启动虚拟机以启用传输" @click="emit('start-instance')" />
        </div>
      </div>

      <div v-else class="flex flex-1 items-center justify-center p-6">
        <EmptyState
          title="无法浏览访客文件系统"
          description="实例既未运行、也没有可离线挂载的磁盘镜像。启动虚拟机后即可浏览与传输。"
          icon="i-lucide-monitor-off"
          size="sm"
        >
          <template #action>
            <UButton size="sm" icon="i-lucide-play" label="启动虚拟机" @click="emit('start-instance')" />
          </template>
        </EmptyState>
      </div>
    </UCard>

    <!-- 新建文件夹 / 重命名 -->
    <UModal v-model:open="promptOpen" :title="promptTitle" :description="promptDescription">
      <template #body>
        <UFormField :label="promptLabel">
          <UInput
            v-model="promptValue"
            autofocus
            class="w-full"
            :placeholder="promptPlaceholder"
            @keyup.enter="submitPrompt"
          />
        </UFormField>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="取消" @click="promptOpen = false" />
          <UButton label="确定" :loading="promptBusy" :disabled="!promptValue.trim()" @click="submitPrompt" />
        </div>
      </template>
    </UModal>

    <!-- 删除确认 -->
    <UModal v-model:open="deleteOpen" title="删除确认">
      <template #body>
        <p class="text-sm text-toned">
          确定要在<span class="font-medium">{{ deleteSide === "host" ? "宿主机" : "虚拟机" }}</span>删除
          <span class="font-mono font-medium text-highlighted">{{ deleteTarget?.name }}</span>
          吗？
          <span v-if="deleteTarget?.is_dir">该目录及其全部内容都会被移除，</span>
          此操作不可撤销。
        </p>
        <p class="mt-2 break-all font-mono text-xs text-dimmed">{{ deleteTarget?.path }}</p>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" label="取消" @click="deleteOpen = false" />
          <UButton color="error" label="删除" :loading="deleteBusy" @click="confirmDelete" />
        </div>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { ContextMenuItem } from "@nuxt/ui";
import {
  fetchGuestFiles,
  fetchHostFiles,
  guestFsOp,
  hostFsOp,
  uploadHostFile,
  transferFile,
  type FsOp,
} from "@/api/endpoints";
import type { FileEntry } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import LoadingState from "@/components/LoadingState.vue";
import { useTaskStore } from "@/stores/tasks";
import { toastError, toastSuccess } from "@/utils/toast";

type Side = "host" | "guest";

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
const selectedHost = ref<FileEntry | null>(null);
const selectedGuest = ref<FileEntry | null>(null);
const hostUploadInputRef = ref<HTMLInputElement | null>(null);
const hostSearch = ref("");
const guestSearch = ref("");
/** 右键落点所在行；落在空白处为 null，菜单据此在「对文件」与「对目录」之间切换 */
const hostContextRow = ref<FileEntry | null>(null);
const guestContextRow = ref<FileEntry | null>(null);
const taskStore = useTaskStore();

/** 请求序号：快速切换目录时丢弃过期响应 */
let hostSeq = 0;
let guestSeq = 0;

const guestVfsMode = computed(() => {
  if (props.instanceStatus === "RUNNING") return "online";
  if (props.instanceStatus === "STOPPED") return "offline";
  return "none";
});
const isGuestBrowseable = computed(() => guestVfsMode.value !== "none");
const isGuestTransitioning = computed(() =>
  ["STARTING", "STOPPING", "LOADING"].includes(props.instanceStatus)
);
/** 只有在线（SSH 可达）时才能写入访客文件系统或传输 */
const guestCanWrite = computed(() => guestVfsMode.value === "online");

const guestModeBadge = computed(() => {
  if (guestVfsMode.value === "online") return { label: "在线", color: "success" as const };
  if (guestVfsMode.value === "offline") return { label: "离线只读", color: "neutral" as const };
  return { label: "不可用", color: "neutral" as const };
});
const guestModeHint = computed(() => {
  if (guestVfsMode.value === "online") return "通过 SSH 访问运行中的访客机，可读写与传输";
  if (guestVfsMode.value === "offline") return "直接挂载 rootfs.img 浏览，只读";
  return "实例未就绪，无法浏览访客文件系统";
});

const filteredHostFiles = computed(() => filterEntries(hostFiles.value, hostSearch.value));
const filteredGuestFiles = computed(() => filterEntries(guestFiles.value, guestSearch.value));

const hostParts = computed(() => {
  const root = hostRootPath.value;
  const cur = hostCurrentPath.value;
  if (!root || !cur.startsWith(root)) return [];
  const rel = cur.slice(root.length).replace(/^\/+/, "");
  if (!rel) return [];
  let acc = root;
  return rel.split("/").filter(Boolean).map((name) => {
    acc = acc.endsWith("/") ? acc + name : `${acc}/${name}`;
    return { name, path: acc };
  });
});

const guestParts = computed(() => {
  const cur = guestCurrentPath.value.replace(/\/+$/, "") || "/";
  if (cur === "/") return [];
  let acc = "";
  return cur.split("/").filter(Boolean).map((name) => {
    acc += `/${name}`;
    return { name, path: acc };
  });
});

/** 上级目录；已在根则为 null */
const hostParentPath = computed(() => {
  const parts = hostParts.value;
  if (!parts.length) return null;
  return parts.length === 1 ? hostRootPath.value || "/" : parts[parts.length - 2].path;
});
const guestParentPath = computed(() => {
  const parts = guestParts.value;
  if (!parts.length) return null;
  return parts.length === 1 ? "/" : parts[parts.length - 2].path;
});

/* ---------------- 右键菜单 ---------------- */

const hostMenuItems = computed(() => buildMenu("host"));
const guestMenuItems = computed(() => buildMenu("guest"));

function buildMenu(side: Side): ContextMenuItem[][] {
  const row = side === "host" ? hostContextRow.value : guestContextRow.value;
  const writable = side === "host" ? true : guestCanWrite.value;
  const parent = side === "host" ? hostParentPath.value : guestParentPath.value;
  const otherLabel = side === "host" ? "虚拟机" : "宿主机";
  const otherDir = side === "host" ? guestCurrentPath.value : hostCurrentPath.value;
  const groups: ContextMenuItem[][] = [];

  if (row) {
    const primary: ContextMenuItem[] = [];
    if (row.is_dir) {
      primary.push({
        label: "打开",
        icon: "i-lucide-folder-open",
        kbds: ["enter"],
        onSelect: () => openEntry(side, row),
      });
    }
    primary.push({
      label: `传到${otherLabel}`,
      description: guestCanWrite.value ? otherDir : "需要虚拟机处于运行状态",
      icon: side === "host" ? "i-lucide-arrow-right" : "i-lucide-arrow-left",
      disabled: !guestCanWrite.value,
      onSelect: () => void transfer(side, row),
    });
    groups.push(primary);

    const edit: ContextMenuItem[] = [
      {
        label: "重命名",
        icon: "i-lucide-pencil",
        kbds: ["f2"],
        disabled: !writable,
        onSelect: () => openRename(side, row),
      },
      {
        label: "复制路径",
        icon: "i-lucide-clipboard",
        onSelect: () => void copyText(row.path),
      },
    ];
    if (row.is_link && row.link_target) {
      edit.push({
        label: "复制链接目标",
        description: row.link_target,
        icon: "i-lucide-link",
        onSelect: () => void copyText(row.link_target!),
      });
    }
    groups.push(edit);

    groups.push([
      {
        label: "删除",
        icon: "i-lucide-trash-2",
        color: "error",
        kbds: ["del"],
        disabled: !writable,
        onSelect: () => askDelete(side, row),
      },
    ]);
  }

  const create: ContextMenuItem[] = [
    {
      label: "新建文件夹",
      icon: "i-lucide-folder-plus",
      disabled: !writable,
      onSelect: () => openCreateFolder(side),
    },
  ];
  if (side === "host") {
    create.push({
      label: "上传文件到此处",
      icon: "i-lucide-upload",
      onSelect: triggerHostUpload,
    });
  }
  groups.push(create);

  groups.push([
    {
      label: "返回上级",
      icon: "i-lucide-corner-left-up",
      kbds: ["backspace"],
      disabled: !parent,
      onSelect: () => parent && (side === "host" ? navigateHost(parent) : navigateGuest(parent)),
    },
    {
      label: "刷新",
      icon: "i-lucide-refresh-cw",
      onSelect: () => void (side === "host" ? loadHost() : loadGuest()),
    },
    {
      label: "复制当前目录",
      icon: "i-lucide-clipboard-list",
      onSelect: () => void copyText(side === "host" ? hostCurrentPath.value : guestCurrentPath.value),
    },
  ]);

  return groups;
}

/**
 * 右键时先定位所在行并选中它（与常见文件管理器一致）。
 * 不能在行上用 @contextmenu.stop：事件必须继续冒泡到 ContextMenu 的 trigger，
 * 否则菜单根本不会弹出。所以统一在容器上用 closest 反查行。
 */
function onPanelContextMenu(side: Side, event: MouseEvent) {
  const el = (event.target as HTMLElement | null)?.closest?.("tr[data-path]") as HTMLElement | null;
  const path = el?.dataset.path;
  const list = side === "host" ? hostFiles.value : guestFiles.value;
  const row = path ? list.find((f) => f.path === path) ?? null : null;
  if (side === "host") {
    hostContextRow.value = row;
    if (row) selectedHost.value = row;
  } else {
    guestContextRow.value = row;
    if (row) selectedGuest.value = row;
  }
}

function onPanelKeydown(side: Side, event: KeyboardEvent) {
  const row = side === "host" ? selectedHost.value : selectedGuest.value;
  const writable = side === "host" ? true : guestCanWrite.value;
  const parent = side === "host" ? hostParentPath.value : guestParentPath.value;

  if (event.key === "Backspace") {
    event.preventDefault();
    if (parent) side === "host" ? navigateHost(parent) : navigateGuest(parent);
    return;
  }
  if (event.key === "F5") {
    event.preventDefault();
    void (side === "host" ? loadHost() : loadGuest());
    return;
  }
  if (!row) return;
  if (event.key === "Enter") {
    event.preventDefault();
    openEntry(side, row);
  } else if (event.key === "F2" && writable) {
    event.preventDefault();
    openRename(side, row);
  } else if (event.key === "Delete" && writable) {
    event.preventDefault();
    askDelete(side, row);
  }
}

function selectRow(side: Side, row: FileEntry, event: MouseEvent) {
  if (side === "host") selectedHost.value = row;
  else selectedGuest.value = row;
  // 让容器拿到焦点，F2 / Delete / Enter 这些快捷键才能生效
  (event.currentTarget as HTMLElement).closest<HTMLElement>("[tabindex]")?.focus();
}

function openEntry(side: Side, row: FileEntry) {
  if (!row.is_dir) return;
  const base = side === "host" ? hostCurrentPath.value : guestCurrentPath.value;
  const next = joinPath(base, row.name);
  side === "host" ? navigateHost(next) : navigateGuest(next);
}

/* ---------------- 展示辅助 ---------------- */

function rowClass(selected: boolean) {
  return selected ? "bg-primary/10 ring-1 ring-inset ring-primary/20" : "";
}

function rowTitle(row: FileEntry) {
  return row.is_link && row.link_target ? `${row.path} → ${row.link_target}` : row.path;
}

function entryIcon(row: FileEntry) {
  if (row.is_link) return row.is_dir ? "i-lucide-folder-symlink" : "i-lucide-file-symlink";
  if (row.is_dir) return "i-lucide-folder";
  const ext = row.name.includes(".") ? row.name.split(".").pop()!.toLowerCase() : "";
  if (["sh", "bash", "py", "pl", "lua"].includes(ext)) return "i-lucide-file-code";
  if (["conf", "cfg", "ini", "json", "yaml", "yml", "toml"].includes(ext)) return "i-lucide-file-cog";
  if (["log", "txt", "md"].includes(ext)) return "i-lucide-file-text";
  if (["img", "bin", "squashfs", "ubi", "trx"].includes(ext)) return "i-lucide-file-box";
  if (["gz", "xz", "bz2", "zip", "tar", "tgz", "ipk"].includes(ext)) return "i-lucide-file-archive";
  return "i-lucide-file";
}

/** 目录优先，其次按名称排序，和常见文件管理器保持一致 */
function filterEntries(list: FileEntry[], query: string): FileEntry[] {
  const q = query.trim().toLowerCase();
  const matched = q ? list.filter((e) => e.name.toLowerCase().includes(q)) : list.slice();
  return matched.sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    return a.name.localeCompare(b.name, "zh-Hans-CN");
  });
}

/** 转义 HTML 并高亮匹配片段（仅用于受控文件名展示） */
function highlightName(name: string, query: string): string {
  const q = query.trim();
  if (!q) return escapeHtml(name);
  const idx = name.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return escapeHtml(name);
  const before = escapeHtml(name.slice(0, idx));
  const match = escapeHtml(name.slice(idx, idx + q.length));
  const after = escapeHtml(name.slice(idx + q.length));
  return `${before}<mark class="rounded-sm bg-primary/20 px-0.5 text-highlighted">${match}</mark>${after}`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatSize(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

function formatMtime(sec: number) {
  if (!sec) return "—";
  const d = new Date(sec * 1000);
  const pad = (v: number) => String(v).padStart(2, "0");
  const sameYear = d.getFullYear() === new Date().getFullYear();
  const md = `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return sameYear ? `${md} ${pad(d.getHours())}:${pad(d.getMinutes())}` : `${d.getFullYear()}-${md}`;
}

function joinPath(base: string, name: string) {
  const b = base.replace(/\/+$/, "");
  const n = name.replace(/^\/+/, "");
  return `${b}/${n}`.replace(/\/{2,}/g, "/") || "/";
}

async function copyText(text: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      // 非安全上下文（局域网 http 访问）下 Clipboard API 不可用，退回旧接口
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    toastSuccess("已复制路径");
  } catch {
    toastError("复制失败");
  }
}

/* ---------------- 目录加载与导航 ---------------- */

async function loadHost() {
  const seq = ++hostSeq;
  hostLoading.value = true;
  try {
    const data = await fetchHostFiles(hostCurrentPath.value || undefined, props.instanceId);
    if (seq !== hostSeq) return;
    hostFiles.value = data.files;
    hostCurrentPath.value = data.current_path;
    if (data.host_root_path) hostRootPath.value = data.host_root_path;
    if (selectedHost.value && !data.files.some((f) => f.path === selectedHost.value?.path)) {
      selectedHost.value = null;
    }
  } catch (e: unknown) {
    if (seq !== hostSeq) return;
    toastError(e instanceof Error ? e.message : "加载宿主机目录失败");
  } finally {
    if (seq === hostSeq) hostLoading.value = false;
  }
}

async function loadGuest() {
  if (!isGuestBrowseable.value) {
    guestFiles.value = [];
    return;
  }
  const seq = ++guestSeq;
  guestLoading.value = true;
  try {
    const data = await fetchGuestFiles(
      props.instanceId,
      guestCurrentPath.value,
      guestVfsMode.value === "offline" ? "offline" : "online"
    );
    if (seq !== guestSeq) return;
    guestFiles.value = data.files;
    guestCurrentPath.value = data.current_path || guestCurrentPath.value;
    if (selectedGuest.value && !data.files.some((f) => f.path === selectedGuest.value?.path)) {
      selectedGuest.value = null;
    }
  } catch (e: unknown) {
    if (seq !== guestSeq) return;
    toastError(e instanceof Error ? e.message : "加载访客目录失败");
    guestFiles.value = [];
  } finally {
    if (seq === guestSeq) guestLoading.value = false;
  }
}

function navigateHost(path: string) {
  hostCurrentPath.value = path;
  selectedHost.value = null;
  hostContextRow.value = null;
  hostSearch.value = "";
  void loadHost();
}

function navigateGuest(path: string) {
  guestCurrentPath.value = path;
  selectedGuest.value = null;
  guestContextRow.value = null;
  guestSearch.value = "";
  void loadGuest();
}

/* ---------------- 文件操作 ---------------- */

function runFsOp(side: Side, op: FsOp, path: string, destPath?: string) {
  return side === "host"
    ? hostFsOp(op, path, destPath)
    : guestFsOp(props.instanceId, op, path, destPath);
}

function reload(side: Side) {
  return side === "host" ? loadHost() : loadGuest();
}

type PromptMode = "mkdir" | "rename";
const promptOpen = ref(false);
const promptMode = ref<PromptMode>("mkdir");
const promptSide = ref<Side>("host");
const promptValue = ref("");
const promptBusy = ref(false);
const renameTarget = ref<FileEntry | null>(null);

const promptTitle = computed(() => (promptMode.value === "mkdir" ? "新建文件夹" : "重命名"));
const promptLabel = computed(() => (promptMode.value === "mkdir" ? "文件夹名称" : "新名称"));
const promptDescription = computed(() => {
  const where = promptSide.value === "host" ? "宿主机" : "虚拟机";
  const dir = promptSide.value === "host" ? hostCurrentPath.value : guestCurrentPath.value;
  return promptMode.value === "mkdir" ? `将在${where} ${dir} 下创建` : `${where} ${dir}`;
});
const promptPlaceholder = computed(() =>
  promptMode.value === "mkdir" ? "例如：payloads" : renameTarget.value?.name || ""
);

function openCreateFolder(side: Side) {
  promptMode.value = "mkdir";
  promptSide.value = side;
  renameTarget.value = null;
  promptValue.value = "";
  promptOpen.value = true;
}

function openRename(side: Side, row: FileEntry) {
  promptMode.value = "rename";
  promptSide.value = side;
  renameTarget.value = row;
  promptValue.value = row.name;
  promptOpen.value = true;
}

async function submitPrompt() {
  const name = promptValue.value.trim();
  if (!name || promptBusy.value) return;
  if (name.includes("/")) {
    toastError("名称中不能包含「/」");
    return;
  }
  const side = promptSide.value;
  const baseDir = side === "host" ? hostCurrentPath.value : guestCurrentPath.value;
  promptBusy.value = true;
  try {
    if (promptMode.value === "mkdir") {
      await runFsOp(side, "mkdir", joinPath(baseDir, name));
      toastSuccess("文件夹已创建");
    } else if (renameTarget.value) {
      if (name === renameTarget.value.name) {
        promptOpen.value = false;
        return;
      }
      await runFsOp(side, "rename", renameTarget.value.path, joinPath(baseDir, name));
      toastSuccess("已重命名");
    }
    promptOpen.value = false;
    await reload(side);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "操作失败");
  } finally {
    promptBusy.value = false;
  }
}

const deleteOpen = ref(false);
const deleteBusy = ref(false);
const deleteSide = ref<Side>("host");
const deleteTarget = ref<FileEntry | null>(null);

function askDelete(side: Side, row: FileEntry) {
  deleteSide.value = side;
  deleteTarget.value = row;
  deleteOpen.value = true;
}

async function confirmDelete() {
  const target = deleteTarget.value;
  const side = deleteSide.value;
  if (!target || deleteBusy.value) return;
  deleteBusy.value = true;
  try {
    await runFsOp(side, "delete", target.path);
    toastSuccess("已删除");
    if (side === "host" && selectedHost.value?.path === target.path) selectedHost.value = null;
    if (side === "guest" && selectedGuest.value?.path === target.path) selectedGuest.value = null;
    deleteOpen.value = false;
    deleteTarget.value = null;
    await reload(side);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "删除失败");
  } finally {
    deleteBusy.value = false;
  }
}

/* ---------------- 上传与传输 ---------------- */

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
    toastSuccess(files.length > 1 ? `已上传 ${files.length} 个文件` : "上传完成");
    await loadHost();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "上传失败");
  } finally {
    hostUploading.value = false;
    input.value = "";
  }
}

/** 从 side 一侧把 row 传到对侧的当前目录 */
async function transfer(side: Side, row: FileEntry) {
  if (!guestCanWrite.value) return;
  const direction = side === "host" ? "host_to_guest" : "guest_to_host";
  const destDir = side === "host" ? guestCurrentPath.value : hostCurrentPath.value;
  const label = side === "host" ? "传到虚拟机" : "传到宿主机";
  try {
    const task = await transferFile(props.instanceId, direction, row.path, joinPath(destDir, row.name));
    await taskStore.trackTaskAsync(task.task_id, {
      label,
      detail: row.name,
      successMessage: "传输完成",
      onSuccess: () => {
        void (side === "host" ? loadGuest() : loadHost());
      },
    });
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "传输失败");
  }
}

// 只在在线/离线/不可用之间切换时重载；同一模式内的状态抖动不必反复拉目录。
// 换模式后旧路径可能不存在（在线的 /root 在离线镜像里未必有），回到根目录更稳妥。
watch(guestVfsMode, (mode, prev) => {
  if (mode !== prev) {
    guestCurrentPath.value = "/";
    selectedGuest.value = null;
    guestContextRow.value = null;
    guestSearch.value = "";
  }
  void loadGuest();
});

onMounted(() => {
  void loadHost();
  void loadGuest();
});
</script>
