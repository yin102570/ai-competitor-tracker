<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">审计日志</h1>

    <!-- 统计概览 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card">
        <p class="text-sm text-slate-400">总请求数</p>
        <p class="text-2xl font-bold text-white mt-2">{{ stats?.total_requests || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-slate-400">成功请求</p>
        <p class="text-2xl font-bold text-emerald-400 mt-2">{{ stats?.success_count || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-slate-400">错误请求</p>
        <p class="text-2xl font-bold text-red-400 mt-2">{{ stats?.error_count || 0 }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-slate-400">活跃用户</p>
        <p class="text-2xl font-bold text-cyan-400 mt-2">{{ stats?.active_users || 0 }}</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div>
          <label class="block text-xs text-slate-400 mb-1">开始时间</label>
          <input v-model="filters.start_date" type="datetime-local" class="input" />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">结束时间</label>
          <input v-model="filters.end_date" type="datetime-local" class="input" />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">用户</label>
          <input v-model="filters.user" class="input" placeholder="用户名/邮箱" />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">路径</label>
          <input v-model="filters.path" class="input" placeholder="/api/v1/..." />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">HTTP方法</label>
          <select v-model="filters.method" class="input">
            <option value="">全部</option>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
            <option value="PATCH">PATCH</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        <div>
          <label class="block text-xs text-slate-400 mb-1">状态码</label>
          <input v-model="filters.status_code" class="input" placeholder="如 200, 404, 500" />
        </div>
        <div class="flex items-end gap-2">
          <button class="btn btn-primary flex-1" @click="fetchLogs">查询</button>
          <button class="btn btn-secondary flex-1" @click="resetFilters">重置</button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <!-- 日志表格 -->
    <div v-else class="card !p-0 overflow-hidden">
      <div v-if="logs.length === 0" class="py-16 text-center text-slate-500">
        暂无审计日志
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b border-slate-700 bg-slate-800/50">
              <th class="px-4 py-3">时间</th>
              <th class="px-4 py-3">用户</th>
              <th class="px-4 py-3">方法</th>
              <th class="px-4 py-3">路径</th>
              <th class="px-4 py-3">状态码</th>
              <th class="px-4 py-3">耗时</th>
              <th class="px-4 py-3">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="log in logs"
              :key="log.id"
              class="border-b border-slate-700/50 hover:bg-slate-800/30 transition-colors"
            >
              <td class="px-4 py-3 text-slate-400 whitespace-nowrap">{{ formatTime(log.created_at || log.timestamp) }}</td>
              <td class="px-4 py-3 text-slate-200">{{ log.user_email || log.user || '-' }}</td>
              <td class="px-4 py-3">
                <span :class="methodBadgeClass(log.method)">{{ log.method }}</span>
              </td>
              <td class="px-4 py-3 text-slate-300 font-mono text-xs max-w-xs truncate" :title="log.path">
                {{ log.path }}
              </td>
              <td class="px-4 py-3">
                <span :class="statusCodeClass(log.status_code)">
                  {{ log.status_code }}
                </span>
              </td>
              <td class="px-4 py-3 text-slate-400">{{ log.duration ? log.duration + 'ms' : '-' }}</td>
              <td class="px-4 py-3 text-slate-400 font-mono text-xs">{{ log.ip || log.client_ip || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="flex items-center justify-between px-4 py-3 border-t border-slate-700">
        <span class="text-sm text-slate-400">共 {{ total }} 条，第 {{ currentPage }} 页</span>
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
            :disabled="currentPage * pageSize >= total"
            @click="changePage(currentPage + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { auditApi } from '@/api/modules'
import dayjs from 'dayjs'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const stats = ref<any>(null)

const filters = reactive({
  start_date: '',
  end_date: '',
  user: '',
  path: '',
  method: '',
  status_code: '',
})

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

function methodBadgeClass(method: string): string {
  const map: Record<string, string> = {
    GET: 'badge badge-info',
    POST: 'badge badge-success',
    PUT: 'badge badge-warning',
    DELETE: 'badge badge-danger',
    PATCH: 'badge badge-warning',
  }
  return map[method] || 'badge badge-info'
}

function statusCodeClass(code: number | string): string {
  const num = Number(code)
  if (num >= 200 && num < 300) return 'badge badge-success'
  if (num >= 300 && num < 400) return 'badge badge-info'
  if (num >= 400 && num < 500) return 'badge badge-warning'
  if (num >= 500) return 'badge badge-danger'
  return 'badge badge-info'
}

function resetFilters() {
  filters.start_date = ''
  filters.end_date = ''
  filters.user = ''
  filters.path = ''
  filters.method = ''
  filters.status_code = ''
  currentPage.value = 1
  fetchLogs()
}

function changePage(page: number) {
  currentPage.value = page
  fetchLogs()
}

async function fetchLogs() {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date
    if (filters.user) params.user = filters.user
    if (filters.path) params.path = filters.path
    if (filters.method) params.method = filters.method
    if (filters.status_code) params.status_code = filters.status_code

    const res: any = await auditApi.logs(params)
    logs.value = res.items || res.data || []
    total.value = res.total || logs.value.length
  } catch (err: any) {
    console.error('审计日志加载失败:', err)
    logs.value = []
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    stats.value = await auditApi.stats(7)
  } catch (err: any) {
    console.error('统计概览加载失败:', err)
    stats.value = null
  }
}

onMounted(() => {
  fetchLogs()
  fetchStats()
})
</script>
