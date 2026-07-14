<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">用户中心</h1>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <template v-else-if="user">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 用户信息卡片 -->
        <div class="card">
          <div class="flex flex-col items-center text-center">
            <div class="w-20 h-20 rounded-full bg-gradient-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center text-cyan-400 font-bold text-3xl mb-4">
              {{ (user.name || user.email).charAt(0).toUpperCase() }}
            </div>
            <h2 class="text-xl font-bold text-white">{{ user.name }}</h2>
            <p class="text-slate-400 text-sm mt-1">{{ user.email }}</p>
            <span
              class="mt-3 badge"
              :class="user.role === 'admin' ? 'badge-danger' : user.role === 'analyst' ? 'badge-info' : 'badge-success'"
            >
              {{ roleLabel(user.role) }}
            </span>
          </div>
          <div class="mt-6 space-y-3 text-sm border-t border-slate-700 pt-4">
            <div class="flex items-center justify-between">
              <span class="text-slate-400">注册时间</span>
              <span class="text-slate-200">{{ formatTime(user.created_at) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-400">账号状态</span>
              <span :class="user.is_active ? 'badge badge-success' : 'badge badge-danger'">
                {{ user.is_active ? '正常' : '停用' }}
              </span>
            </div>
          </div>

          <!-- 编辑姓名 -->
          <div class="mt-4 border-t border-slate-700 pt-4">
            <div v-if="!editingName" class="flex items-center justify-between">
              <span class="text-sm text-slate-400">姓名</span>
              <button class="text-cyan-400 hover:text-cyan-300 text-sm" @click="startEditName">编辑</button>
            </div>
            <div v-else class="space-y-2">
              <input v-model="editNameValue" class="input" placeholder="请输入新姓名" />
              <div class="flex gap-2">
                <button class="btn btn-primary flex-1 !py-1.5" :disabled="savingName" @click="saveName">
                  {{ savingName ? '保存中...' : '保存' }}
                </button>
                <button class="btn btn-secondary flex-1 !py-1.5" @click="editingName = false">取消</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 配额信息 -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">配额信息</h3>
          <div class="space-y-4">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-slate-400">每日配额</span>
                <span class="text-lg font-bold text-white">{{ user.daily_quota }}</span>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-slate-400">已使用</span>
                <span class="text-lg font-bold text-amber-400">{{ user.quota_used }}</span>
              </div>
              <div class="w-full h-3 rounded-full bg-slate-700 overflow-hidden">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-amber-500 to-red-500 transition-all"
                  :style="{ width: quotaPercent + '%' }"
                ></div>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm text-slate-400">剩余</span>
                <span class="text-lg font-bold text-emerald-400">{{ user.quota_remaining }}</span>
              </div>
              <div class="w-full h-3 rounded-full bg-slate-700 overflow-hidden">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all"
                  :style="{ width: remainingPercent + '%' }"
                ></div>
              </div>
            </div>
            <div class="pt-2 border-t border-slate-700">
              <div class="flex items-center justify-between text-sm">
                <span class="text-slate-400">使用率</span>
                <span :class="quotaPercent > 80 ? 'text-red-400' : 'text-slate-200'">{{ quotaPercent }}%</span>
              </div>
            </div>
            <router-link to="/payment" class="btn btn-primary w-full">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              充值扩容
            </router-link>
          </div>
        </div>

        <!-- API Key管理 -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-white">API Key管理</h3>
            <button class="btn btn-primary !py-1.5 !px-3 text-xs" :disabled="creatingKey" @click="handleCreateKey">
              {{ creatingKey ? '生成中...' : '生成新Key' }}
            </button>
          </div>
          <div v-if="apiKeysLoading" class="text-slate-400 text-sm py-4">加载中...</div>
          <div v-else-if="apiKeys.length === 0" class="py-8 text-center text-slate-500 text-sm">
            暂无API Key
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="key in apiKeys"
              :key="key.id || key.key"
              class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-medium text-white">{{ key.name }}</span>
                <span :class="key.is_active ? 'badge badge-success' : 'badge badge-danger'">
                  {{ key.is_active ? '启用' : '停用' }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <code class="text-xs text-slate-400 font-mono flex-1 truncate">
                  {{ maskKey(key.key || key.api_key) }}
                </code>
                <button
                  class="text-cyan-400 hover:text-cyan-300 text-xs shrink-0"
                  @click="copyKey(key.key || key.api_key)"
                >
                  复制
                </button>
              </div>
              <p v-if="key.created_at" class="text-xs text-slate-500 mt-1">
                创建于: {{ formatTime(key.created_at) }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card text-center py-12">
      <p class="text-slate-400">用户信息加载失败</p>
      <button class="btn btn-primary mt-4" @click="fetchUser">重新加载</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { userApi, authApi, type UserProfile } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'

const authStore = useAuthStore()
const loading = ref(false)
const user = ref<UserProfile | null>(null)
const editingName = ref(false)
const editNameValue = ref('')
const savingName = ref(false)
const creatingKey = ref(false)
const apiKeysLoading = ref(false)
const apiKeys = ref<any[]>([])

const quotaPercent = computed(() => {
  if (!user.value || user.value.daily_quota === 0) return 0
  return Math.min(100, Math.round((user.value.quota_used / user.value.daily_quota) * 100))
})

const remainingPercent = computed(() => {
  return 100 - quotaPercent.value
})

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function roleLabel(role: string): string {
  const map: Record<string, string> = {
    admin: '管理员',
    analyst: '分析师',
    user: '普通用户',
  }
  return map[role] || role
}

function maskKey(key: string): string {
  if (!key || key.length < 12) return key
  return key.substring(0, 8) + '****' + key.substring(key.length - 4)
}

function startEditName() {
  editNameValue.value = user.value?.name || ''
  editingName.value = true
}

async function saveName() {
  if (!editNameValue.value.trim()) return
  savingName.value = true
  try {
    await userApi.updateMe({ name: editNameValue.value })
    user.value!.name = editNameValue.value
    authStore.user!.name = editNameValue.value
    editingName.value = false
  } catch (err: any) {
    console.error('保存姓名失败:', err)
    alert('保存失败: ' + (err.message || '未知错误'))
  } finally {
    savingName.value = false
  }
}

async function fetchApiKeys() {
  apiKeysLoading.value = true
  try {
    const res: any = await authApi.getApiKeys()
    apiKeys.value = res.items || res.data || res || []
  } catch (err: any) {
    console.error('API Key加载失败:', err)
    apiKeys.value = []
  } finally {
    apiKeysLoading.value = false
  }
}

async function handleCreateKey() {
  const name = prompt('请输入API Key名称:')
  if (!name) return
  creatingKey.value = true
  try {
    await authApi.createApiKey(name)
    await fetchApiKeys()
  } catch (err: any) {
    console.error('创建API Key失败:', err)
    alert('创建失败: ' + (err.message || '未知错误'))
  } finally {
    creatingKey.value = false
  }
}

function copyKey(key: string) {
  navigator.clipboard.writeText(key).then(() => {
    alert('已复制到剪贴板')
  }).catch(() => {
    alert('复制失败')
  })
}

async function fetchUser() {
  loading.value = true
  try {
    user.value = await userApi.getMe()
  } catch (err: any) {
    console.error('用户信息加载失败:', err)
    user.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchUser()
  fetchApiKeys()
})
</script>
