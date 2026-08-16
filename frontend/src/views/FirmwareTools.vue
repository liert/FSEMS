<template>
  <UDashboardPanel id="firmware-tools">
    <template #header>
      <UDashboardNavbar title="固件工具">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <TaskCenter />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <PageMotion>
        <div class="relative flex h-full min-h-0 flex-col overflow-hidden rounded-3xl border border-default bg-elevated/30 shadow-sm">
          <div class="pointer-events-none absolute inset-0 opacity-50 [background-image:linear-gradient(to_right,rgba(148,163,184,0.07)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.07)_1px,transparent_1px)] [background-size:32px_32px]" />
          <div class="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-primary/10 blur-3xl" />

          <div class="relative flex min-h-0 flex-1 flex-col overflow-auto p-6 sm:p-8">
            <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              <button
                type="button"
                class="group flex min-h-36 flex-col items-center justify-center rounded-2xl border border-transparent p-4 text-center transition-all duration-200 hover:-translate-y-1 hover:border-primary/30 hover:bg-primary/8 hover:shadow-lg hover:shadow-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                @click="openFilesystemConverter"
              >
                <span class="mb-3 flex size-16 items-center justify-center rounded-2xl bg-primary/12 text-primary shadow-inner shadow-primary/10 transition-transform duration-200 group-hover:scale-110">
                  <UIcon name="i-lucide-layers-3" class="size-8" />
                </span>
                <span class="font-medium text-highlighted">文件系统转换</span>
                <span class="mt-1 text-xs text-dimmed">Ext4 · SquashFS · F2FS</span>
              </button>

              <div class="flex min-h-36 flex-col items-center justify-center rounded-2xl border border-dashed border-default/70 p-4 text-center opacity-70">
                <span class="mb-3 flex size-16 items-center justify-center rounded-2xl bg-neutral/10 text-dimmed">
                  <UIcon name="i-lucide-plus" class="size-7" />
                </span>
                <span class="font-medium text-muted">更多工具</span>
                <span class="mt-1 text-xs text-dimmed">后续扩展</span>
              </div>
            </div>

            <div class="mt-auto pt-10">
              <UAlert
                color="neutral"
                variant="subtle"
                icon="i-lucide-shield-check"
                title="安全提示"
                description="源路径支持宿主机任意普通文件，生成文件会保存到 workspace/firmware-tools/filesystem-converter。"
              />
            </div>
          </div>
        </div>
      </PageMotion>
    </template>
  </UDashboardPanel>

  <UModal
    v-model:open="filesystemDialogOpen"
    title="文件系统转换"
    description="将 RootFS 内容转换为另一种文件系统镜像"
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-5">
        <UAlert
          color="info"
          variant="subtle"
          icon="i-lucide-info"
          title="转换说明"
          description="源镜像会先提取到临时目录，再生成新的 raw 文件系统镜像。源文件不会被修改。"
        />

        <UFormField label="源镜像路径" required description="支持宿主机上的任意普通文件路径">
          <UInput
            v-model="sourcePath"
            class="w-full"
            icon="i-lucide-file-archive"
            placeholder="例如：/var/fsems/rootfs/rootfs.img.gz"
          />
        </UFormField>

        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField label="源文件系统">
            <USelect v-model="sourceType" :items="sourceTypeOptions" value-key="value" class="w-full" />
          </UFormField>
          <UFormField label="目标文件系统" required>
            <USelect v-model="targetType" :items="filesystemOptions" value-key="value" class="w-full" />
          </UFormField>
        </div>

        <UFormField label="输出文件名" description="仅填写文件名，输出目录由系统统一管理">
          <UInput v-model="outputName" class="w-full" icon="i-lucide-file-output" placeholder="留空自动生成" />
        </UFormField>

        <UFormField
          v-if="targetType !== 'squashfs'"
          label="目标镜像容量（MB）"
          description="留空时根据源文件内容估算，最小 64 MB"
        >
          <UInput v-model.number="sizeMb" type="number" min="32" max="131072" step="1" class="w-full" />
        </UFormField>

        <UAlert
          v-if="sourceType !== 'auto' && sourceType === targetType"
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          title="源文件系统与目标相同"
          description="请选择不同的目标文件系统。"
        />

        <UAlert
          v-if="result"
          color="success"
          variant="subtle"
          icon="i-lucide-circle-check"
          title="转换完成"
          :description="`${formatBytes(result.output_size_bytes)} · 用时 ${formatDuration(result.duration_ms)}`"
        >
          <template #description>
            <p>{{ formatBytes(result.output_size_bytes) }} · 用时 {{ formatDuration(result.duration_ms) }}</p>
            <p class="mt-1 break-all font-mono text-xs">{{ result.output_path }}</p>
          </template>
        </UAlert>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="关闭" :disabled="converting" @click="filesystemDialogOpen = false" />
        <UButton
          label="开始转换"
          icon="i-lucide-arrow-right-left"
          :loading="converting"
          :disabled="!canConvert"
          @click="convert"
        />
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { convertFilesystem } from "@/api/endpoints";
import type { FilesystemConvertResult, FilesystemType, SourceFilesystemType } from "@/api/types";
import PageMotion from "@/components/PageMotion.vue";
import TaskCenter from "@/components/TaskCenter.vue";
import { toastError, toastSuccess } from "@/utils/toast";

const filesystemDialogOpen = ref(false);
const converting = ref(false);
const sourcePath = ref("");
const sourceType = ref<SourceFilesystemType>("auto");
const targetType = ref<FilesystemType>("ext4");
const outputName = ref("");
const sizeMb = ref<number | undefined>(undefined);
const result = ref<FilesystemConvertResult | null>(null);

const sourceTypeOptions: Array<{ label: string; value: SourceFilesystemType }> = [
  { label: "自动识别", value: "auto" },
  { label: "Ext4", value: "ext4" },
  { label: "SquashFS", value: "squashfs" },
  { label: "F2FS", value: "f2fs" },
];

const filesystemOptions: Array<{ label: string; value: FilesystemType }> = [
  { label: "Ext4（可写）", value: "ext4" },
  { label: "SquashFS（只读）", value: "squashfs" },
  { label: "F2FS（可写）", value: "f2fs" },
];

const canConvert = computed(() => {
  if (!sourcePath.value.trim() || converting.value) return false;
  return sourceType.value === "auto" || sourceType.value !== targetType.value;
});

function openFilesystemConverter() {
  result.value = null;
  filesystemDialogOpen.value = true;
}

async function convert() {
  if (!canConvert.value) return;
  converting.value = true;
  result.value = null;
  try {
    result.value = await convertFilesystem({
      sourcePath: sourcePath.value.trim(),
      sourceType: sourceType.value,
      targetType: targetType.value,
      outputName: outputName.value.trim() || undefined,
      sizeMb: targetType.value === "squashfs" ? undefined : sizeMb.value,
    });
    toastSuccess("文件系统转换完成");
  } catch (error: unknown) {
    toastError(error instanceof Error ? error.message : "文件系统转换失败");
  } finally {
    converting.value = false;
  }
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDuration(durationMs: number) {
  if (durationMs < 1000) return `${durationMs} ms`;
  return `${(durationMs / 1000).toFixed(1)} s`;
}
</script>
