<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">系统管理</h1>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 左侧: 配置编辑 + 备份 -->
      <div class="lg:col-span-2 space-y-6">
        <!-- 配置编辑表单 -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-white">系统配置</h2>
            <button
              class="btn btn-primary"
              :disabled="savingConfig || !hasConfigChanges"
              @click="handleSaveConfig"
            >
              {{ savingConfig ? '保存中...' : '保存配置' }}
            </button>
          </div>

          <div v-if="configLoading" class="flex items-center justify-center py-12">
            <div class="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
          </div>

          <div v-else-if="configEntries.length > 0" class="space-y-4">
            <div v-for="entry in configEntries" :key="entry.key">
              <label class="block text-sm text-slate-400 mb-1">
                {{ configLabel(entry.key) }}
                <span class="text-xs text-slate-600 ml-1">({{ entry.key }})</span>
              </label>
              <input
                v-model="entry.value"
                class="input"
                :placeholder="`请输入${configLabel(entry.key)}`"
              />
              <p v-if="entry.description" class="text-xs text-slate-500 mt-1">{{ entry.description }}</p>
            </div>
          </div>

          <div v-else class="py-12 text-center text-slate-500">
            暂无配置数据
          </div>
        </div>

        <!-- 手动备份 -->
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-lg font-semibold text-white">数据备份</h3>
              <p class="text-sm text-slate-400 mt-1">手动触发系统数据备份，备份文件将存储在服务器指定目录</p>
            </div>
            <button
              class="btn btn-secondary"
              :disabled="backing"
              @click="handleBackup"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {{ backing ? '备份中...' : '手动备份' }}
            </button>
          </div>
          <div v-if="backupResult" class="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <p class="text-sm text-emerald-400">备份成功</p>
            <p v-if="backupResult.file || backupResult.path" class="text-xs text-slate-400 mt-1">
              文件: {{ backupResult.file || backupResult.path }}
            </p>
            <p v-if="backupResult.size" class="text-xs text-slate-400">
              大小: {{ formatSize(backupResult.size) }}
            </p>
          </div>
        </div>
      </div>

      <!-- 右侧: 健康检查 -->
      <div class="space-y-6">
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-white">健康检查</h3>
            <button
              class="text-cyan-400 hover:text-cyan-300 text-sm"
              :disabled="healthLoading"
              @click="fetchHealth"
            >
              {{ healthLoading ? '检查中...' : '刷新' }}
            </button>
          </div>

          <div v-if="healthLoading && !health" class="flex items-center justify-center py-8">
            <div class="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
          </div>

          <div v-else-if="health" class="space-y-3">
            <!-- 整体状态 -->
            <div class="flex items-center gap-3 p-3 rounded-lg" :class="overallHealthy ? 'bg-emerald-500/10' : 'bg-red-500/10'">
              <div
                class="w-3 h-3 rounded-full"
                :class="overallHealthy ? 'bg-emerald-500' : 'bg-red-500'"
              ></div>
              <span class="text-sm font-medium" :class="overallHealthy ? 'text-emerald-400' : 'text-red-400'">
                {{ overallHealthy ? '系统运行正常' : '系统存在异常' }}
              </span>
            </div>

            <!-- 各服务状态 -->
            <div
              v-for="(value, key) in health"
              :key="key"
              class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50"
            >
              <span class="text-sm text-slate-300">{{ healthLabel(key as string) }}</span>
              <div class="flex items-center gap-2">
                <span class="text-sm text-slate-400">{{ formatHealthValue(value) }}</span>
                <div
                  class="w-2.5 h-2.5 rounded-full"
                  :class="isHealthy(value) ? 'bg-emerald-500' : 'bg-red-500'"
                ></div>
              </div>
            </div>
          </div>

          <div v-else class="py-8 text-center text-slate-500">
            点击刷新检查系统健康状态
          </div>
        </div>

        <!-- 系统信息 -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">系统信息</h3>
          <div class="space-y-3 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-slate-400">版本</span>
              <span class="text-slate-200">{{ health?.version || 'v1.0.0' }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">运行时间</span>
              <span class="text-slate-200">{{ health?.uptime || '-' }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">服务器时间</span>
              <span class="text-slate-200">{{ formatTime(new Date().toISOString()) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { adminApi } from '@/api/modules'
import dayjs from 'dayjs'

const configLoading = ref(false)
const savingConfig = ref(false)
const healthLoading = ref(false)
const backing = ref(false)
const config = ref<any>(null)
const originalConfig = ref<any>(null)
const health = ref<any>(null)
const backupResult = ref<any>(null)

interface ConfigEntry {
  key: string
  value: any
  description?: string
}

const configEntries = computed<ConfigEntry[]>(() => {
  if (!config.value) return []
  if (Array.isArray(config.value)) {
    return config.value
  }
  return Object.entries(config.value).map(([key, value]) => ({
    key,
    value: typeof value === 'object' ? JSON.stringify(value) : value,
  }))
})

const hasConfigChanges = computed(() => {
  if (!originalConfig.value || !config.value) return false
  return JSON.stringify(originalConfig.value) !== JSON.stringify(config.value)
})

const overallHealthy = computed(() => {
  if (!health.value) return false
  const values = Object.values(health.value)
  return values.every((v) => isHealthy(v))
})

function isHealthy(value: any): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') return value === 'healthy' || value === 'ok' || value === 'up'
  if (typeof value === 'object' && value !== null) {
    return value.status === 'healthy' || value.status === 'ok' || value.status === 'up'
  }
  return true
}

function formatHealthValue(value: any): string {
  if (typeof value === 'boolean') return value ? '正常' : '异常'
  if (typeof value === 'string') return value
  if (typeof value === 'object' && value !== null) {
    return value.status || value.message || JSON.stringify(value)
  }
  return String(value)
}

function configLabel(key: string): string {
  const map: Record<string, string> = {
    spider_interval: '爬虫间隔(秒)',
    spider_timeout: '爬虫超时(秒)',
    max_concurrent_tasks: '最大并发任务数',
    sentiment_model: '情感分析模型',
    deepseek_api_key: 'DeepSeek API Key',
    deepseek_base_url: 'DeepSeek Base URL',
    cache_ttl: '缓存过期时间(秒)',
    rate_limit_per_minute: '每分钟请求限制',
    max_upload_size: '最大上传大小(MB)',
    log_level: '日志级别',
    enable_cors: '启用CORS',
    jwt_expire_minutes: 'JWT过期时间(分钟)',
    database_url: '数据库连接',
    redis_url: 'Redis连接',
  }
  return map[key] || key
}

function healthLabel(key: string): string {
  const map: Record<string, string> = {
    database: '数据库',
    redis: 'Redis缓存',
    api: 'API服务',
    spider: '爬虫引擎',
    sentiment: '情感分析',
    storage: '文件存储',
    version: '系统版本',
    uptime: '运行时间',
  }
  return map[key] || key
}

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
}

async function fetchConfig() {
  configLoading.value = true
  try {
    const res: any = await adminApi.config()
    config.value = res
    originalConfig.value = JSON.parse(JSON.stringify(res))
  } catch (err: any) {
    console.error('系统配置加载失败:', err)
    config.value = null
  } finally {
    configLoading.value = false
  }
}

async function fetchHealth() {
  healthLoading.value = true
  try {
    health.value = await adminApi.health()
  } catch (err: any) {
    console.error('健康检查失败:', err)
    health.value = null
  } finally {
    healthLoading.value = false
  }
}

async function handleSaveConfig() {
  savingConfig.value = true
  try {
    const data: Record<string, any> = {}
    configEntries.value.forEach((entry) => {
      data[entry.key] = entry.value
    })
    await adminApi.updateConfig(data)
    originalConfig.value = JSON.parse(JSON.stringify(config.value))
    alert('配置保存成功')
  } catch (err: any) {
    console.error('配置保存失败:', err)
    alert('保存失败: ' + (err.message || '未知错误'))
  } finally {
    savingConfig.value = false
  }
}

async function handleBackup() {
  backing.value = true
  backupResult.value = null
  try {
    backupResult.value = await adminApi.backup()
  } catch (err: any) {
    console.error('备份失败:', err)
    alert('备份失败: ' + (err.message || '未知错误'))
  } finally {
    backing.value = false
  }
}

onMounted(() => {
  fetchConfig()
  fetchHealth()
})
</script>
