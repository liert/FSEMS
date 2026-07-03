<template>
  <div class="page-stack">
    <PageHeader
      title="固件模板"
      description="管理 QEMU 启动参数、内核与 rootfs 路径。种子模板按架构预置，可编辑或新增自定义模板。"
    >
      <template #actions>
        <el-select
          v-model="archFilter"
          clearable
          placeholder="架构筛选"
          style="width: 150px"
          @change="load"
        >
          <el-option label="aarch64" value="aarch64" />
          <el-option label="mips" value="mips" />
          <el-option label="mipsel" value="mipsel" />
          <el-option label="x86_64" value="x86_64" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新建模板
        </el-button>
      </template>
    </PageHeader>

    <section class="glass-card table-panel content-panel">
      <el-table :data="templates" v-loading="loading" empty-text=" " style="width: 100%">
        <template #empty>
          <EmptyState title="暂无模板" description="创建固件模板以定义 QEMU 机器类型、内核与 SSH 默认值。">
            <template #action>
              <el-button type="primary" @click="openCreate">新建模板</el-button>
            </template>
          </EmptyState>
        </template>

        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <span class="name-text">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="arch" label="架构" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.arch }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="qemu_binary" label="QEMU" min-width="160">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.qemu_binary }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ram_size" label="内存" width="90">
          <template #default="{ row }">{{ row.ram_size }} MB</template>
        </el-table-column>
        <el-table-column prop="guest_ssh_host" label="SSH 默认" width="120">
          <template #default="{ row }">
            <span class="mono-cell">{{ row.guest_ssh_host }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="showDialog" :title="editingId ? '编辑模板' : '新建模板'" width="640px">
      <el-form label-width="120px" label-position="left">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="架构"><el-input v-model="form.arch" placeholder="aarch64 / mipsel" /></el-form-item>
        <el-form-item label="QEMU 二进制"><el-input v-model="form.qemu_binary" /></el-form-item>
        <el-form-item label="Machine"><el-input v-model="form.machine" /></el-form-item>
        <el-form-item label="CPU"><el-input v-model="form.cpu" /></el-form-item>
        <el-form-item label="内核路径"><el-input v-model="form.kernel_path" /></el-form-item>
        <el-form-item label="磁盘路径"><el-input v-model="form.drive_path" /></el-form-item>
        <el-form-item label="Kernel append">
          <el-input v-model="form.kernel_append" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内存 (MB)">
          <el-input-number v-model="form.ram_size" :min="64" :max="16384" />
        </el-form-item>
        <el-form-item label="SSH 主机"><el-input v-model="form.guest_ssh_host" /></el-form-item>
        <el-form-item label="SSH 端口">
          <el-input-number v-model="form.guest_ssh_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="Extra args">
          <el-input v-model="form.extra_args" placeholder="可选 QEMU 额外参数" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus } from "@element-plus/icons-vue";
import {
  createTemplate,
  deleteTemplate,
  fetchTemplates,
  updateTemplate,
} from "@/api/endpoints";
import type { Template, TemplateInput } from "@/api/types";
import PageHeader from "@/components/PageHeader.vue";
import EmptyState from "@/components/EmptyState.vue";

const templates = ref<Template[]>([]);
const loading = ref(false);
const saving = ref(false);
const showDialog = ref(false);
const editingId = ref<number | null>(null);
const archFilter = ref<string>("");

const emptyForm = (): TemplateInput => ({
  name: "",
  arch: "aarch64",
  qemu_binary: "qemu-system-aarch64",
  machine: "virt",
  cpu: "cortex-a72",
  kernel_path: "",
  drive_path: "",
  kernel_append: "",
  ram_size: 512,
  guest_ssh_host: "192.168.1.1",
  guest_ssh_port: 22,
  extra_args: "",
});

const form = ref<TemplateInput>(emptyForm());

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
  showDialog.value = true;
}

function openEdit(row: Template) {
  editingId.value = row.id;
  form.value = { ...row };
  showDialog.value = true;
}

async function save() {
  saving.value = true;
  try {
    if (editingId.value) {
      await updateTemplate(editingId.value, form.value);
      ElMessage.success("模板已更新");
    } else {
      await createTemplate(form.value);
      ElMessage.success("模板已创建");
    }
    showDialog.value = false;
    await load();
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}

async function remove(row: Template) {
  try {
    await ElMessageBox.confirm(`确定删除模板「${row.name}」？`, "确认", { type: "warning" });
    await deleteTemplate(row.id);
    ElMessage.success("已删除");
    await load();
  } catch {
    /* cancelled */
  }
}

onMounted(load);
</script>

<style scoped>
.name-text {
  font-weight: 600;
}
</style>
