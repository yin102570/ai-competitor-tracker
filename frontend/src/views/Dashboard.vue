<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">综合看板</h1>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <template v-else-if="overview">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card hover:border-cyan-500/50 transition-colors">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400">竞品总数</p>
              <p class="text-3xl font-bold text-white mt-2">{{ overview.competitors.length }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-cyan-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div class="card hover:border-purple-500/50 transition-colors">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400">舆情总提及量</p>
              <p class="text-3xl font-bold text-white mt-2">{{ formatNumber(overview.sentiment.total_mentions) }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
          </div>
        </div>

        <div class="card hover:border-emerald-500/50 transition-colors">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400">正面占比</p>
              <p class="text-3xl font-bold text-white mt-2">{{ positiveRatio }}%</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div class="card hover:border-amber-500/50 transition-colors">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-slate-400">今日爬虫任务</p>
              <p class="text-3xl font-bold text-white mt-2">{{ todayTaskCount }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 中间区域: 左侧竞品列表 + 右侧舆情饼图 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 竞品列表 -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-white">竞品列表</h2>
            <router-link to="/competitors" class="text-sm text-cyan-400 hover:text-cyan-300">查看全部</router-link>
          </div>
          <div v-if="overview.competitors.length === 0" class="py-8 text-center text-slate-500">
            暂无竞品数据
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="comp in overview.competitors"
              :key="comp.slug"
              @click="router.push(`/competitors/${comp.slug}`)"
              class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 cursor-pointer transition-colors border border-transparent hover:border-cyan-500/30"
            >
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center text-cyan-400 font-bold text-sm">
                  {{ comp.name.charAt(0) }}
                </div>
                <div>
                  <p class="text-sm font-medium text-white">{{ comp.name }}</p>
                  <p class="text-xs text-slate-500">{{ comp.company }}</p>
                </div>
              </div>
              <span class="badge badge-info">{{ comp.category }}</span>
            </div>
          </div>
        </div>

        <!-- 舆情分布饼图 -->
        <div class="card">
          <h2 class="text-lg font-semibold text-white mb-4">舆情分布</h2>
          <div v-if="totalSentiment === 0" class="py-8 text-center text-slate-500">
            暂无舆情数据
          </div>
          <VChart v-else :option="pieOption" style="height: 320px;" autoresize />
        </div>
      </div>

      <!-- 爬虫任务统计 -->
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-white">爬虫任务统计</h2>
          <router-link to="/spiders" class="text-sm text-cyan-400 hover:text-cyan-300">查看全部</router-link>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="rounded-lg bg-slate-800/50 p-4 text-center">
            <p class="text-sm text-slate-400">总任务数</p>
            <p class="text-2xl font-bold text-white mt-1">{{ overview.spiders.total_tasks }}</p>
          </div>
          <div class="rounded-lg bg-slate-800/50 p-4 text-center">
            <p class="text-sm text-slate-400">运行中</p>
            <p class="text-2xl font-bold text-cyan-400 mt-1">{{ overview.spiders.running_tasks }}</p>
          </div>
          <div class="rounded-lg bg-slate-800/50 p-4 text-center">
            <p class="text-sm text-slate-400">24h成功</p>
            <p class="text-2xl font-bold text-emerald-400 mt-1">{{ overview.spiders.success_tasks_24h }}</p>
          </div>
          <div class="rounded-lg bg-slate-800/50 p-4 text-center">
            <p class="text-sm text-slate-400">24h失败</p>
            <p class="text-2xl font-bold text-red-400 mt-1">{{ overview.spiders.failed_tasks_24h }}</p>
          </div>
        </div>
        <div v-if="overview.spiders.next_scheduled" class="mt-4 text-xs text-slate-500">
          下次调度: <span class="font-mono text-slate-400">{{ overview.spiders.next_scheduled }}</span>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card text-center py-12">
      <p class="text-slate-400">数据加载失败</p>
      <button class="btn btn-primary mt-4" @click="fetchData">重新加载</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { dashboardApi, type DashboardOverview } from '@/api/modules'

use([CanvasRenderer, PieChart, TitleComponent, TooltipComponent, LegendComponent])

const router = useRouter()
const loading = ref(false)
const overview = ref<DashboardOverview | null>(null)

const totalSentiment = computed(() => {
  if (!overview.value) return 0
  return overview.value.sentiment.total_mentions
})

const positiveRatio = computed(() => {
  if (!overview.value) return 0
  return overview.value.sentiment.positive_pct
})

const todayTaskCount = computed(() => {
  if (!overview.value) return 0
  return overview.value.spiders.total_tasks
})

const pieOption = computed(() => {
  const s = overview.value?.sentiment
  const positive = s?.positive_pct ?? 0
  const neutral = s?.neutral_pct ?? 0
  const negative = s?.negative_pct ?? 0
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}%',
    },
    legend: {
      orient: 'horizontal',
      bottom: 10,
      textStyle: { color: '#94a3b8' },
    },
    series: [
      {
        name: '舆情分布',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#111827',
          borderWidth: 2,
        },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 16, fontWeight: 'bold', color: '#f1f5f9' },
        },
        data: [
          { value: positive, name: '正面', itemStyle: { color: '#10b981' } },
          { value: neutral, name: '中性', itemStyle: { color: '#94a3b8' } },
          { value: negative, name: '负面', itemStyle: { color: '#ef4444' } },
        ],
      },
    ],
  }
})

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

async function fetchData() {
  loading.value = true
  try {
    overview.value = await dashboardApi.overview()
  } catch (err: any) {
    console.error('Dashboard数据加载失败:', err)
    overview.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
