<template>
  <div class="page">
    <header class="header">
      <h1>实例管理</h1>
      <div>
        <el-button type="primary" @click="showCreate = true">新建实例</el-button>
        <el-button type="success" @click="goToLogs">系统日志</el-button>
        <el-button @click="logout">退出</el-button>
      </div>
    </header>

    <el-table :data="instances" v-loading="loading" stripe>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="id" label="ID" min-width="280" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="guest_ssh_host" label="SSH 地址" width="140" />
      <el-table-column label="操作" width="300">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status === 'RUNNING' || row.status === 'STARTING' || row.status === 'STOPPING'" @click="doAction(row.id, 'start')">
            启动
          </el-button>
          <el-button size="small" :disabled="row.status === 'STOPPED' || row.status === 'STOPPING'" @click="doAction(row.id, 'stop')">
            停止
          </el-button>
          <el-button size="small" @click="doAction(row.id, 'reset')">重置</el-button>
          <el-button size="small" type="primary" @click="manageInstance(row.id)">
            管理
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="新建实例" width="500px" :before-close="cancelCreate">
      <el-form label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="newName" placeholder="输入实例名称" />
        </el-form-item>
        <el-form-item label="模板">
          <el-select v-model="newTemplateId" style="width: 100%">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <!-- 自动根据所选启动模板设置对应版本的默认内核与文件系统。若需模拟特定固件，可在下方指定自定义 RootFS -->
        <el-form-item label="自定义RootFS (可选)">
          <el-input v-model="newRootfsPath" placeholder="可选输入宿主机上的压缩包或文件夹路径作为自定义系统" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelCreate">取消</el-button>
        <el-button type="primary" :loading="creating" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  createInstance,
  fetchInstances,
  fetchTemplates,
  instanceAction,
} from "@/api/endpoints";
import type { Instance, Template } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();
const instances = ref<Instance[]>([]);
const templates = ref<Template[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const newName = ref("");
const newTemplateId = ref<number | null>(null);
const creating = ref(false);

// 本地自定义 RootFS 文件或目录物理路径
const newRootfsPath = ref("");

function statusType(status: string) {
  if (status === "RUNNING") return "success";
  if (status === "STARTING") return "warning";
  if (status === "STOPPED") return "info";
  return "danger";
}

function statusText(status: string) {
  const statusMap: Record<string, string> = {
    LOADING: "加载中...",
    STARTING: "启动中",
    RUNNING: "运行中",
    STOPPING: "停止中",
    STOPPED: "已停止",
  };
  return statusMap[status] || status;
}

async function load() {
  loading.value = true;
  try {
    const data = await fetchInstances();
    instances.value = data.list;
  } finally {
    loading.value = false;
  }
}

async function loadTemplates() {
  templates.value = await fetchTemplates();
  if (templates.value.length && newTemplateId.value === null) {
    newTemplateId.value = templates.value[0].id;
  }
}

async function doAction(id: string, action: "start" | "stop" | "reset") {
  try {
    await instanceAction(id, action);
    ElMessage.success(`已执行 ${action}`);
    await load();
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "操作失败");
  }
}

function manageInstance(id: string) {
  router.push(`/instances/${id}/manage`);
}

async function create() {
  if (!newName.value || newTemplateId.value === null) return;
  creating.value = true;
  try {
    await createInstance(
      newName.value,
      newTemplateId.value,
      newRootfsPath.value.trim()
    );
    showCreate.value = false;
    resetForm();
    await load();
    ElMessage.success("实例已创建且解压完成");
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "创建失败");
  } finally {
    creating.value = false;
  }
}

function cancelCreate() {
  showCreate.value = false;
  resetForm();
}

function resetForm() {
  newName.value = "";
  newRootfsPath.value = "";
}

function logout() {
  auth.logout();
  router.push("/login");
}

function goToLogs() {
  router.push("/logs");
}

onMounted(async () => {
  await Promise.all([load(), loadTemplates()]);
});
</script>

<style scoped>
.page {
  padding: 24px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
</style>
