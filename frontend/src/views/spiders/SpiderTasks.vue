<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-white">爬虫任务管理</h1>
      <button class="btn btn-primary" @click="showTriggerModal = true">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        触发新任务
      </button>
    </div>

    <!-- 状态筛选 + 调度配置 -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="card lg:col-span-2">
        <div class="flex flex-wrap items-center gap-4">
          <div class="w-48">
            <select v-model="statusFilter" class="input" @change="fetchTasks">
              <option value="">全部状态</option>
              <option value="pending">等待中</option>
              <option value="running">运行中</option>
              <option value="success">成功</option>
              <option value="failed">失败</option>
            </select>
          </div>
          <div class="flex-1">
            <select v-model="competitorFilter" class="input" @change="fetchTasks">
              <option value="">全部竞品</option>
              <option v-for="comp in competitors" :key="comp.slug" :value="comp.slug">{{ comp.name }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 调度配置 -->
      <div class="card">
        <h3 class="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          调度配置
        </h3>
        <div v-if="scheduleLoading" class="text-slate-400 text-sm">加载中...</div>
        <div v-else-if="schedule" class="space-y-2 text-sm">
          <div v-for="(value, key) in schedule" :key="key" class="flex items-center justify-between">
            <span class="text-slate-400">{{ scheduleLabel(key as string) }}</span>
            <span class="text-white font-medium">{{ value }}</span>
          </div>
        </div>
        <div v-else class="text-slate-500 text-sm">暂无调度配置</div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <!-- 任务表格 -->
    <div v-else class="card !p-0 overflow-hidden">
      <div v-if="!tasks || tasks.length === 0" class="py-16 text-center text-slate-500">
        暂无爬虫任务
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b border-slate-700 bg-slate-800/50">
              <th class="px-4 py-3">任务ID</th>
              <th class="px-4 py-3">竞品</th>
              <th class="px-4 py-3">类型</th>
              <th class="px-4 py-3">状态</th>
              <th class="px-4 py-3">开始时间</th>
              <th class="px-4 py-3">耗时</th>
              <th class="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="task in tasks"
              :key="task.id"
              class="border-b border-slate-700/50 hover:bg-slate-800/30 transition-colors"
            >
              <td class="px-4 py-3 font-mono text-xs text-slate-300">{{ task.id?.substring(0, 8) }}...</td>
              <td class="px-4 py-3 text-slate-200">{{ task.competitor_slug || task.competitor_name || '-' }}</td>
              <td class="px-4 py-3">
                <span class="badge badge-info">{{ taskLabel(task.task_type || task.type) }}</span>
              </td>
              <td class="px-4 py-3">
                <span :class="statusBadgeClass(task.status)">
                  {{ statusLabel(task.status) }}
                </span>
              </td>
              <td class="px-4 py-3 text-slate-400">{{ task.started_at ? formatTime(task.started_at) : task.created_at ? formatTime(task.created_at) : '-' }}</td>
              <td class="px-4 py-3 text-slate-400">{{ calcDuration(task) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button
                    class="text-cyan-400 hover:text-cyan-300 text-xs font-medium"
                    @click="viewTaskDetail(task.id)"
                  >
                    详情
                  </button>
                  <button
                    v-if="task.status === 'failed'"
                    class="text-amber-400 hover:text-amber-300 text-xs font-medium"
                    :disabled="retryingId === task.id"
                    @click="handleRetry(task.id)"
                  >
                    {{ retryingId === task.id ? '重试中...' : '重试' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="tasksTotal > pageSize" class="flex items-center justify-between px-4 py-3 border-t border-slate-700">
        <span class="text-sm text-slate-400">第 {{ currentPage }} 页</span>
        <div class="flex items-center gap-2">
          <button
            class="btn btn-secondary !px-3 !py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="currentPage <= 1"
            @click="changePage(currentPage - 1)"
          >
            上一页
          </button>
          <button
            class="btn btn-secondary !px-3 !py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
            :disabled="currentPage * pageSize >= tasksTotal"
            @click="changePage(currentPage + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 触发新任务弹窗 -->
    <div v-if="showTriggerModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showTriggerModal = false">
      <div class="card w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4">触发新爬虫任务</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-slate-400 mb-1">选择竞品</label>
            <select v-model="triggerForm.competitor_slug" class="input">
              <option value="">请选择竞品</option>
              <option v-for="comp in competitors" :key="comp.slug" :value="comp.slug">{{ comp.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">任务类型</label>
            <select v-model="triggerForm.task_type" class="input">
              <option value="full">全量采集</option>
              <option value="incremental">增量采集</option>
              <option value="web_traffic">Web流量</option>
              <option value="app_info">App信息</option>
              <option value="pricing">定价信息</option>
              <option value="sentiment">舆情数据</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button class="btn btn-secondary" @click="showTriggerModal = false">取消</button>
          <button class="btn btn-primary" :disabled="!triggerForm.competitor_slug || triggering" @click="handleTrigger">
            {{ triggering ? '触发中...' : '确认触发' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 任务详情弹窗 -->
    <div v-if="showDetailModal && taskDetail" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showDetailModal = false">
      <div class="card w-full max-w-lg mx-4">
        <h3 class="text-lg font-semibold text-white mb-4">任务详情</h3>
        <div class="space-y-3 text-sm">
          <div class="flex justify-between">
            <span class="text-slate-400">任务ID</span>
            <span class="font-mono text-slate-200">{{ taskDetail.id }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">竞品</span>
            <span class="text-slate-200">{{ taskDetail.competitor_slug || '-' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">类型</span>
            <span class="text-slate-200">{{ taskLabel(taskDetail.task_type || taskDetail.type) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">状态</span>
            <span :class="statusBadgeClass(taskDetail.status)">{{ statusLabel(taskDetail.status) }}</span>
          </div>
          <div v-if="taskDetail.started_at" class="flex justify-between">
            <span class="text-slate-400">开始时间</span>
            <span class="text-slate-200">{{ formatTime(taskDetail.started_at) }}</span>
          </div>
          <div v-if="taskDetail.finished_at" class="flex justify-between">
            <span class="text-slate-400">结束时间</span>
            <span class="text-slate-200">{{ formatTime(taskDetail.finished_at) }}</span>
          </div>
          <div v-if="taskDetail.items_scraped !== undefined" class="flex justify-between">
            <span class="text-slate-400">采集条目</span>
            <span class="text-slate-200">{{ taskDetail.items_scraped }}</span>
          </div>
          <div v-if="taskDetail.error" class="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <p class="text-red-400 text-xs">错误信息: {{ taskDetail.error }}</p>
          </div>
          <div v-if="taskDetail.logs" class="p-3 rounded-lg bg-slate-800 border border-slate-700 max-h-40 overflow-y-auto">
            <pre class="text-xs text-slate-300 whitespace-pre-wrap">{{ taskDetail.logs }}</pre>
          </div>
        </div>
        <div class="flex justify-end mt-6">
          <button class="btn btn-secondary" @click="showDetailModal = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { spiderApi, competitorApi, type Competitor } from '@/api/modules'
import dayjs from 'dayjs'

const loading = ref(false)
const scheduleLoading = ref(false)
const triggering = ref(false)
const retryingId = ref<string | null>(null)
const tasks = ref<any[]>([])
const tasksTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const statusFilter = ref('')
const competitorFilter = ref('')
const competitors = ref<Competitor[]>([])
const schedule = ref<any>(null)

const showTriggerModal = ref(false)
const showDetailModal = ref(false)
const triggerForm = ref({ competitor_slug: '', task_type: 'full' })
const taskDetail = ref<any>(null)

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    success: 'badge badge-success',
    completed: 'badge badge-success',
    running: 'badge badge-info',
    pending: 'badge badge-warning',
    failed: 'badge badge-danger',
  }
  return map[status] || 'badge badge-info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    success: '成功',
    completed: '已完成',
    running: '运行中',
    pending: '等待中',
    failed: '失败',
  }
  return map[status] || status
}

function taskLabel(type: string): string {
  const map: Record<string, string> = {
    full: '全量采集',
    incremental: '增量采集',
    web_traffic: 'Web流量',
    app_info: 'App信息',
    pricing: '定价信息',
    sentiment: '舆情数据',
  }
  return map[type] || type
}

function scheduleLabel(key: string): string {
  const map: Record<string, string> = {
    interval: '执行间隔',
    next_run: '下次执行',
    enabled: '是否启用',
    last_run: '上次执行',
    cron: 'Cron表达式',
  }
  return map[key] || key
}

function calcDuration(task: any): string {
  const start = task.started_at || task.created_at
  const end = task.finished_at || task.completed_at
  if (!start) return '-'
  const startTime = dayjs(start)
  const endTime = end ? dayjs(end) : dayjs()
  const diff = endTime.diff(startTime, 'second')
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m${diff % 60}s`
  return `${Math.floor(diff / 3600)}h${Math.floor((diff % 3600) / 60)}m`
}

function changePage(page: number) {
  currentPage.value = page
  fetchTasks()
}

async function fetchTasks() {
  loading.value = true
  try {
    const res: any = await spiderApi.listTasks({
      status: statusFilter.value || undefined,
      competitor_slug: competitorFilter.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    tasks.value = res.items || res.data || []
    tasksTotal.value = res.total || tasks.value.length
  } catch (err: any) {
    console.error('任务列表加载失败:', err)
    tasks.value = []
  } finally {
    loading.value = false
  }
}

async function fetchCompetitors() {
  try {
    const res = await competitorApi.list({ page: 1, size: 100 })
    competitors.value = res.items
  } catch {
    competitors.value = []
  }
}

async function fetchSchedule() {
  scheduleLoading.value = true
  try {
    schedule.value = await spiderApi.schedule()
  } catch (err: any) {
    console.error('调度配置加载失败:', err)
    schedule.value = null
  } finally {
    scheduleLoading.value = false
  }
}

async function handleTrigger() {
  if (!triggerForm.value.competitor_slug) return
  triggering.value = true
  try {
    await spiderApi.trigger(triggerForm.value)
    showTriggerModal.value = false
    triggerForm.value = { competitor_slug: '', task_type: 'full' }
    await fetchTasks()
    alert('爬虫任务已触发')
  } catch (err: any) {
    console.error('触发任务失败:', err)
    alert('触发失败: ' + (err.message || '未知错误'))
  } finally {
    triggering.value = false
  }
}

async function handleRetry(taskId: string) {
  retryingId.value = taskId
  try {
    await spiderApi.retry(taskId)
    await fetchTasks()
    alert('重试已触发')
  } catch (err: any) {
    console.error('重试失败:', err)
    alert('重试失败: ' + (err.message || '未知错误'))
  } finally {
    retryingId.value = null
  }
}

async function viewTaskDetail(taskId: string) {
  try {
    taskDetail.value = await spiderApi.getTask(taskId)
    showDetailModal.value = true
  } catch (err: any) {
    console.error('任务详情加载失败:', err)
    alert('详情加载失败')
  }
}

onMounted(() => {
  fetchTasks()
  fetchCompetitors()
  fetchSchedule()
})
</script>
