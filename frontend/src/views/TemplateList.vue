<template>
  <UDashboardPanel id="templates">
    <template #header>
      <UDashboardNavbar title="固件模板">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <USelect
              v-model="archFilter"
              :items="archOptions"
              placeholder="架构筛选"
              class="w-36"
            />
            <UButton icon="i-lucide-plus" label="新建模板" @click="openCreate" />
            <TaskCenter />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UCard class="flex h-full min-h-0 flex-col overflow-hidden" :ui="{ body: 'flex-1 min-h-0 p-0' }">
        <div class="h-full min-h-0 overflow-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 z-10 bg-elevated border-b border-default">
              <tr class="text-left text-muted">
                <th class="px-4 py-3 font-medium">ID</th>
                <th class="px-4 py-3 font-medium">名称</th>
                <th class="px-4 py-3 font-medium">架构</th>
                <th class="px-4 py-3 font-medium">QEMU</th>
                <th class="px-4 py-3 font-medium">内存</th>
                <th class="px-4 py-3 font-medium">SSH 默认</th>
                <th class="px-4 py-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody v-if="templates.length">
              <tr
                v-for="row in templates"
                :key="row.id"
                class="border-b border-muted hover:bg-muted/50"
              >
                <td class="px-4 py-3 text-toned">{{ row.id }}</td>
                <td class="px-4 py-3 font-medium text-highlighted">{{ row.name }}</td>
                <td class="px-4 py-3">
                  <UBadge variant="subtle" color="neutral" size="sm">{{ row.arch }}</UBadge>
                </td>
                <td class="px-4 py-3 font-mono text-xs text-toned">{{ row.qemu_binary }}</td>
                <td class="px-4 py-3">{{ row.ram_size }} MB</td>
                <td class="px-4 py-3 font-mono text-xs">{{ row.guest_ssh_host }}</td>
                <td class="px-4 py-3">
                  <div class="flex justify-end gap-1">
                    <UButton size="sm" variant="soft" color="neutral" label="编辑" @click="openEdit(row)" />
                    <UButton size="sm" variant="soft" color="error" label="删除" @click="remove(row)" />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <EmptyState
            v-if="!loading && !templates.length"
            title="暂无模板"
            description="创建固件模板以定义 QEMU 机器类型、内核与 SSH 默认值。"
          >
            <template #action>
              <UButton label="新建模板" icon="i-lucide-plus" @click="openCreate" />
            </template>
          </EmptyState>
          <div v-if="loading" class="flex justify-center py-12">
            <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
          </div>
        </div>
      </UCard>

      <UModal v-model:open="showDialog" :title="editingId ? '编辑模板' : '新建模板'" :ui="{ content: 'sm:max-w-2xl' }">
        <template #body>
          <div class="max-h-[min(62vh,520px)] space-y-3 overflow-y-auto pr-1">
            <div class="grid gap-3 sm:grid-cols-2">
              <UFormField label="名称" class="sm:col-span-2">
                <UInput v-model="form.name" placeholder="模板显示名称" class="w-full" />
              </UFormField>
              <UFormField label="架构">
                <USelectMenu
                  v-model="form.arch"
                  :items="['aarch64', 'arm', 'mips', 'mipsel', 'x86_64', 'i386']"
                  create-item
                  class="w-full"
                  @update:model-value="onArchChange"
                />
              </UFormField>
              <UFormField label="QEMU">
                <UInput v-model="form.qemu_binary" readonly class="w-full" />
              </UFormField>
              <UFormField label="Machine">
                <UInput v-model="form.machine" class="w-full" />
              </UFormField>
              <UFormField label="CPU">
                <USelectMenu
                  v-model="form.cpu"
                  :items="displayedCpuOptions"
                  :loading="cpuLoading"
                  create-item
                  searchable
                  class="w-full"
                />
              </UFormField>
              <UFormField label="内存 (MB)">
                <UInputNumber v-model="form.ram_size" :min="64" :max="16384" class="w-full" />
              </UFormField>
              <UFormField label="SSH 端口">
                <UInputNumber v-model="form.guest_ssh_port" :min="1" :max="65535" class="w-full" />
              </UFormField>
              <UFormField label="SSH 主机" class="sm:col-span-2">
                <UInput v-model="form.guest_ssh_host" class="w-full" />
              </UFormField>
              <UFormField label="版本" class="sm:col-span-2">
                <div class="flex gap-2">
                  <USelectMenu
                    v-model="openwrtVersion"
                    :items="openwrtVersions"
                    :loading="versionsLoading"
                    searchable
                    class="flex-1"
                    @update:model-value="onOpenWrtVersionChange"
                  />
                  <UButton color="neutral" variant="soft" label="刷新" :loading="versionsLoading" @click="loadOpenWrtVersions(true)" />
                </div>
              </UFormField>
              <UFormField label="内核" class="sm:col-span-2">
                <div class="flex gap-2">
                  <USelectMenu
                    v-model="selectedKernelName"
                    :items="openwrtKernels.map((k) => k.name)"
                    :loading="kernelsLoading"
                    :disabled="!openwrtVersion"
                    searchable
                    class="flex-1"
                    @update:model-value="onKernelSelect"
                  />
                  <UButton
                    label="下载"
                    :loading="kernelDownloading"
                    :disabled="!canDownloadKernel"
                    @click="downloadSelectedKernel"
                  />
                </div>
              </UFormField>
              <UFormField label="本地内核" class="sm:col-span-2">
                <USelectMenu
                  v-model="form.kernel_path"
                  :items="localKernelOptions"
                  value-key="value"
                  label-key="label"
                  searchable
                  class="w-full"
                  @update:model-value="onLocalKernelPathChange"
                />
              </UFormField>
              <UFormField label="磁盘路径" class="sm:col-span-2">
                <UInput v-model="form.drive_path" class="w-full" />
              </UFormField>
              <UFormField label="Kernel 参数" class="sm:col-span-2">
                <UTextarea v-model="form.kernel_append" :rows="2" class="w-full" />
              </UFormField>
              <UFormField label="Extra args" class="sm:col-span-2">
                <UInput v-model="form.extra_args" class="w-full" />
              </UFormField>
            </div>
          </div>
        </template>
        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton color="neutral" variant="ghost" label="取消" @click="showDialog = false" />
            <UButton label="保存" :loading="saving" @click="save" />
          </div>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  createTemplate,
  deleteTemplate,
  downloadOpenWrtKernel,
  fetchLocalKernels,
  fetchOpenWrtKernels,
  fetchOpenWrtVersions,
  fetchQemuCpuModels,
  fetchTemplates,
  updateTemplate,
  type OpenWrtKernelItem,
} from "@/api/endpoints";
import type { Template, TemplateInput } from "@/api/types";
import EmptyState from "@/components/EmptyState.vue";
import TaskCenter from "@/components/TaskCenter.vue";
import { toastError, toastSuccess } from "@/utils/toast";

const ARCH_DEFAULTS: Record<string, { qemu: string; machine: string; cpu: string }> = {
  aarch64: { qemu: "qemu-system-aarch64", machine: "virt", cpu: "cortex-a72" },
  arm64: { qemu: "qemu-system-aarch64", machine: "virt", cpu: "cortex-a72" },
  arm: { qemu: "qemu-system-arm", machine: "virt", cpu: "cortex-a15" },
  mips: { qemu: "qemu-system-mips", machine: "malta", cpu: "24Kc" },
  mipsel: { qemu: "qemu-system-mipsel", machine: "malta", cpu: "24Kc" },
  x86_64: { qemu: "qemu-system-x86_64", machine: "pc", cpu: "qemu64" },
  amd64: { qemu: "qemu-system-x86_64", machine: "pc", cpu: "qemu64" },
  x86: { qemu: "qemu-system-x86_64", machine: "pc", cpu: "qemu64" },
  i386: { qemu: "qemu-system-i386", machine: "pc", cpu: "qemu32" },
};

const ARCH_CPU_FALLBACKS: Record<string, string[]> = {
  aarch64: ["cortex-a72", "cortex-a57", "cortex-a53", "max"],
  arm64: ["cortex-a72", "cortex-a57", "cortex-a53", "max"],
  arm: ["cortex-a15", "cortex-a9", "cortex-a7", "max"],
  mips: ["24Kc", "34Kf", "74Kf", "mips32r6-generic"],
  mipsel: ["24Kc", "34Kf", "74Kf", "mips32r6-generic"],
  x86_64: ["qemu64", "max", "host"],
  i386: ["qemu32", "max", "486"],
};

const archOptions = [
  { label: "全部架构", value: "" },
  { label: "aarch64", value: "aarch64" },
  { label: "arm", value: "arm" },
  { label: "mips", value: "mips" },
  { label: "mipsel", value: "mipsel" },
  { label: "x86_64", value: "x86_64" },
  { label: "i386", value: "i386" },
];

const templates = ref<Template[]>([]);
const loading = ref(false);
const saving = ref(false);
const showDialog = ref(false);
const editingId = ref<number | null>(null);
const archFilter = ref<string>("");

const cpuOptions = ref<string[]>([]);
const displayedCpuOptions = ref<string[]>([]);
const cpuLoading = ref(false);
let cpuProbeTimer: ReturnType<typeof setTimeout> | null = null;
let cpuProbeSeq = 0;

const openwrtVersions = ref<string[]>([]);
const openwrtVersion = ref("");
const openwrtKernels = ref<OpenWrtKernelItem[]>([]);
const selectedKernelName = ref("");
const versionsLoading = ref(false);
const kernelsLoading = ref(false);
const kernelDownloading = ref(false);
const localKernels = ref<{ name: string; path: string; size: number }[]>([]);
let kernelsLoadSeq = 0;

function defaultsForArch(arch: string) {
  const key = (arch || "").trim().toLowerCase();
  return ARCH_DEFAULTS[key] || { qemu: key ? `qemu-system-${key}` : "", machine: "virt", cpu: "max" };
}

function pickDefaultCpu(arch: string, available?: string[]) {
  const key = (arch || "").trim().toLowerCase();
  const preferred = [ARCH_DEFAULTS[key]?.cpu, ...(ARCH_CPU_FALLBACKS[key] || []), "max"].filter(Boolean) as string[];
  if (available?.length) {
    for (const name of preferred) if (available.includes(name)) return name;
    return available[0];
  }
  return preferred[0] || "max";
}

const emptyForm = (): TemplateInput => {
  const d = defaultsForArch("aarch64");
  return {
    name: "",
    arch: "aarch64",
    qemu_binary: d.qemu,
    machine: d.machine,
    cpu: d.cpu,
    kernel_path: "",
    drive_path: "",
    kernel_append: "root=/dev/vda rootfstype=ext4 console=ttyAMA0",
    ram_size: 512,
    guest_ssh_host: "192.168.1.1",
    guest_ssh_port: 22,
    extra_args: "",
  };
};

const form = ref<TemplateInput>(emptyForm());

const selectedKernel = computed(() => openwrtKernels.value.find((k) => k.name === selectedKernelName.value) || null);
const selectedKernelLocal = computed(() => !!selectedKernel.value?.local);
const canDownloadKernel = computed(
  () => !!openwrtVersion.value && !!selectedKernelName.value && !selectedKernelLocal.value && !kernelDownloading.value
);
const localKernelOptions = computed(() =>
  localKernels.value.map((k) => ({ label: k.name, value: k.path }))
);

function onArchChange(arch: string | string[] | undefined) {
  const a = Array.isArray(arch) ? arch[0] : arch || "";
  form.value.arch = a;
  const d = defaultsForArch(a);
  form.value.qemu_binary = d.qemu;
  form.value.machine = d.machine;
  form.value.cpu = d.cpu;
  selectedKernelName.value = "";
  openwrtKernels.value = [];
  if (openwrtVersion.value) void loadOpenWrtKernels();
}

function syncDisplayedCpuOptions(query = "") {
  const q = query.trim().toLowerCase();
  let list = !q ? cpuOptions.value.slice(0, 80) : cpuOptions.value.filter((c) => c.toLowerCase().includes(q)).slice(0, 80);
  const cur = (form.value.cpu || "").trim();
  if (cur && !list.includes(cur)) list = [cur, ...list];
  displayedCpuOptions.value = list;
}

async function probeCpuModels(binary: string) {
  const q = binary.trim();
  if (!q) {
    cpuOptions.value = [];
    displayedCpuOptions.value = [];
    return;
  }
  const seq = ++cpuProbeSeq;
  cpuLoading.value = true;
  try {
    const data = await fetchQemuCpuModels(q);
    if (seq !== cpuProbeSeq) return;
    cpuOptions.value = data.cpus;
    const cur = (form.value.cpu || "").trim();
    if (!cur || !data.cpus.includes(cur)) form.value.cpu = pickDefaultCpu(form.value.arch, data.cpus);
    syncDisplayedCpuOptions("");
  } catch {
    if (seq !== cpuProbeSeq) return;
    cpuOptions.value = [];
    displayedCpuOptions.value = [];
  } finally {
    if (seq === cpuProbeSeq) cpuLoading.value = false;
  }
}

function scheduleProbeCpuModels() {
  if (cpuProbeTimer) clearTimeout(cpuProbeTimer);
  cpuProbeTimer = setTimeout(() => void probeCpuModels(form.value.qemu_binary), 350);
}

async function loadOpenWrtVersions(force = false) {
  versionsLoading.value = true;
  try {
    const data = await fetchOpenWrtVersions(force);
    openwrtVersions.value = data.versions || [];
    if (!openwrtVersions.value.length) return;
    if (!openwrtVersion.value) {
      const preferred = openwrtVersions.value.find((v) => v !== "snapshot") || openwrtVersions.value[0];
      openwrtVersion.value = preferred;
    }
    await loadOpenWrtKernels(force);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "获取 OpenWrt 版本失败");
  } finally {
    versionsLoading.value = false;
  }
}

async function loadOpenWrtKernels(force = false) {
  const version = openwrtVersion.value;
  const arch = form.value.arch;
  if (!version || !arch) {
    openwrtKernels.value = [];
    return;
  }
  const seq = ++kernelsLoadSeq;
  kernelsLoading.value = true;
  try {
    const data = await fetchOpenWrtKernels(version, arch, force);
    if (seq !== kernelsLoadSeq) return;
    openwrtKernels.value = data.kernels || [];
    const pathName = (form.value.kernel_path || "").split(/[/\\]/).pop() || "";
    const matched = openwrtKernels.value.find(
      (k) => k.name === selectedKernelName.value || k.name === pathName || k.local_path === form.value.kernel_path
    );
    if (matched) {
      selectedKernelName.value = matched.name;
      if (matched.local && matched.local_path) form.value.kernel_path = matched.local_path;
    } else if (!selectedKernelName.value && openwrtKernels.value.length === 1) {
      selectedKernelName.value = openwrtKernels.value[0].name;
      onKernelSelect(selectedKernelName.value);
    }
  } catch (e: unknown) {
    if (seq !== kernelsLoadSeq) return;
    openwrtKernels.value = [];
    toastError(e instanceof Error ? e.message : "获取内核列表失败");
  } finally {
    if (seq === kernelsLoadSeq) kernelsLoading.value = false;
  }
}

function onOpenWrtVersionChange() {
  selectedKernelName.value = "";
  void loadOpenWrtKernels();
}

function onKernelSelect(name: string | string[] | undefined | null) {
  const n = Array.isArray(name) ? name[0] : name;
  if (!n) return;
  selectedKernelName.value = n;
  const item = openwrtKernels.value.find((k) => k.name === n);
  if (item?.local && item.local_path) form.value.kernel_path = item.local_path;
}

function onLocalKernelPathChange(path: string | string[] | undefined | null) {
  const p = Array.isArray(path) ? path[0] : path;
  if (!p) return;
  form.value.kernel_path = p;
  selectedKernelName.value = p.split(/[/\\]/).pop() || "";
}

async function downloadSelectedKernel() {
  if (!openwrtVersion.value || !selectedKernelName.value) return;
  kernelDownloading.value = true;
  try {
    const result = await downloadOpenWrtKernel(openwrtVersion.value, form.value.arch, selectedKernelName.value);
    form.value.kernel_path = result.path;
    toastSuccess(result.downloaded ? "内核下载完成" : "本地已存在该内核");
    await Promise.all([loadOpenWrtKernels(), loadLocalKernels()]);
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "下载失败");
  } finally {
    kernelDownloading.value = false;
  }
}

async function loadLocalKernels() {
  try {
    const data = await fetchLocalKernels();
    localKernels.value = data.kernels || [];
  } catch {
    localKernels.value = [];
  }
}

function resetOpenWrtPicker() {
  openwrtVersion.value = "";
  openwrtKernels.value = [];
  selectedKernelName.value = "";
}

async function load() {
  loading.value = true;
  try {
    templates.value = await fetchTemplates(archFilter.value || undefined);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  form.value = emptyForm();
  resetOpenWrtPicker();
  showDialog.value = true;
}

function openEdit(row: Template) {
  editingId.value = row.id;
  form.value = { ...row, extra_args: row.extra_args || "" };
  resetOpenWrtPicker();
  const base = (row.kernel_path || "").split(/[/\\]/).pop() || "";
  if (base) selectedKernelName.value = base;
  showDialog.value = true;
}

async function save() {
  if (!form.value.kernel_path?.trim()) {
    toastError("请选择或下载 OpenWrt 内核");
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await updateTemplate(editingId.value, form.value);
      toastSuccess("模板已更新");
    } else {
      await createTemplate(form.value);
      toastSuccess("模板已创建");
    }
    showDialog.value = false;
    await load();
  } catch (e: unknown) {
    toastError(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function remove(row: Template) {
  if (!window.confirm(`确定删除模板「${row.name}」？`)) return;
  try {
    await deleteTemplate(row.id);
    toastSuccess("已删除");
    await load();
  } catch {
    /* cancelled */
  }
}

watch(showDialog, (open) => {
  if (open) {
    void probeCpuModels(form.value.qemu_binary);
    void loadLocalKernels();
    void loadOpenWrtVersions(false);
  } else {
    cpuOptions.value = [];
    displayedCpuOptions.value = [];
    cpuLoading.value = false;
    resetOpenWrtPicker();
    if (cpuProbeTimer) {
      clearTimeout(cpuProbeTimer);
      cpuProbeTimer = null;
    }
  }
});

watch(
  () => form.value.qemu_binary,
  () => {
    if (showDialog.value) scheduleProbeCpuModels();
  }
);

watch(archFilter, () => void load());

onMounted(load);
onBeforeUnmount(() => {
  if (cpuProbeTimer) clearTimeout(cpuProbeTimer);
});
</script>
