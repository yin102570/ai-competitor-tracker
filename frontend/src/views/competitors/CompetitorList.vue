<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-white">竞品列表</h1>
      <button class="btn btn-primary" @click="showAddModal = true">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        新增竞品
      </button>
    </div>

    <!-- 筛选栏 -->
    <div class="card">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="searchKeyword"
            class="input"
            placeholder="搜索竞品名称或公司..."
            @input="onSearch"
          />
        </div>
        <div class="w-48">
          <select v-model="selectedCategory" class="input" @change="fetchList">
            <option value="">全部分类</option>
            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <!-- 表格 -->
    <div v-else class="card !p-0 overflow-hidden">
      <div v-if="!listData || listData.items.length === 0" class="py-16 text-center text-slate-500">
        暂无竞品数据
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-slate-400 border-b border-slate-700 bg-slate-800/50">
              <th class="px-4 py-3">竞品名称</th>
              <th class="px-4 py-3">公司</th>
              <th class="px-4 py-3">分类</th>
              <th class="px-4 py-3">活跃状态</th>
              <th class="px-4 py-3">更新时间</th>
              <th class="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredItems"
              :key="item.slug"
              class="border-b border-slate-700/50 hover:bg-slate-800/30 cursor-pointer transition-colors"
              @click="router.push(`/competitors/${item.slug}`)"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center text-cyan-400 font-bold text-xs">
                    {{ item.name.charAt(0) }}
                  </div>
                  <span class="font-medium text-white">{{ item.name }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-slate-300">{{ item.company }}</td>
              <td class="px-4 py-3">
                <span class="badge badge-info">{{ item.category }}</span>
              </td>
              <td class="px-4 py-3">
                <span :class="item.is_active ? 'badge badge-success' : 'badge badge-danger'">
                  {{ item.is_active ? '活跃' : '停用' }}
                </span>
              </td>
              <td class="px-4 py-3 text-slate-400">{{ formatTime(item.updated_at) }}</td>
              <td class="px-4 py-3 text-right" @click.stop>
                <button
                  class="text-cyan-400 hover:text-cyan-300 text-sm font-medium"
                  @click="router.push(`/competitors/${item.slug}`)"
                >
                  查看详情
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="listData && listData.total > 0" class="flex items-center justify-between px-4 py-3 border-t border-slate-700">
        <span class="text-sm text-slate-400">
          共 {{ listData.total }} 条，第 {{ currentPage }} / {{ listData.total_pages }} 页
        </span>
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
            :disabled="!listData || currentPage >= listData.total_pages"
            @click="changePage(currentPage + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 新增竞品弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showAddModal = false">
      <div class="card w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4">新增竞品</h3>
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-slate-400 mb-1">竞品名称</label>
            <input v-model="newCompetitor.name" class="input" placeholder="请输入竞品名称" />
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">公司</label>
            <input v-model="newCompetitor.company" class="input" placeholder="请输入公司名称" />
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">分类</label>
            <input v-model="newCompetitor.category" class="input" placeholder="请输入分类" />
          </div>
          <div>
            <label class="block text-sm text-slate-400 mb-1">描述</label>
            <textarea v-model="newCompetitor.description" class="input" rows="3" placeholder="请输入竞品描述"></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button class="btn btn-secondary" @click="showAddModal = false">取消</button>
          <button class="btn btn-primary" :disabled="submitting" @click="handleCreate">
            {{ submitting ? '创建中...' : '确认创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { competitorApi, type Competitor, type PaginatedResponse } from '@/api/modules'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const listData = ref<PaginatedResponse<Competitor> | null>(null)
const currentPage = ref(1)
const pageSize = 10
const searchKeyword = ref('')
const selectedCategory = ref('')
const showAddModal = ref(false)
const newCompetitor = ref({ name: '', company: '', category: '', description: '' })

const categories = computed(() => {
  if (!listData.value) return []
  const cats = new Set<string>()
  listData.value.items.forEach((item) => cats.add(item.category))
  return Array.from(cats)
})

const filteredItems = computed(() => {
  if (!listData.value) return []
  if (!searchKeyword.value) return listData.value.items
  const kw = searchKeyword.value.toLowerCase()
  return listData.value.items.filter(
    (item) =>
      item.name.toLowerCase().includes(kw) ||
      item.company.toLowerCase().includes(kw)
  )
})

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
  }, 300)
}

function changePage(page: number) {
  currentPage.value = page
  fetchList()
}

async function fetchList() {
  loading.value = true
  try {
    listData.value = await competitorApi.list({
      page: currentPage.value,
      size: pageSize,
      category: selectedCategory.value || undefined,
    })
  } catch (err: any) {
    console.error('竞品列表加载失败:', err)
    listData.value = null
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newCompetitor.value.name || !newCompetitor.value.company) return
  submitting.value = true
  try {
    await competitorApi.create(newCompetitor.value)
    showAddModal.value = false
    newCompetitor.value = { name: '', company: '', category: '', description: '' }
    currentPage.value = 1
    await fetchList()
  } catch (err: any) {
    console.error('创建竞品失败:', err)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchList()
})
</script>
