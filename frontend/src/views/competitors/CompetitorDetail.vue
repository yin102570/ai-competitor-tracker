<template>
  <div class="p-6 space-y-6">
    <!-- 返回按钮 -->
    <button class="text-slate-400 hover:text-cyan-400 text-sm flex items-center gap-1" @click="router.back()">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
      返回列表
    </button>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <template v-else-if="competitor">
      <!-- 顶部信息 -->
      <div class="card">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-4">
            <div class="w-16 h-16 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 flex items-center justify-center text-cyan-400 font-bold text-2xl">
              {{ competitor.name.charAt(0) }}
            </div>
            <div>
              <h1 class="text-2xl font-bold text-white">{{ competitor.name }}</h1>
              <p class="text-slate-400 mt-1">{{ competitor.company }}</p>
              <div class="flex items-center gap-2 mt-2">
                <span class="badge badge-info">{{ competitor.category }}</span>
                <span :class="competitor.is_active ? 'badge badge-success' : 'badge badge-danger'">
                  {{ competitor.is_active ? '活跃' : '停用' }}
                </span>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <button
              class="btn btn-secondary"
              :disabled="triggering"
              @click="handleTriggerSpider"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {{ triggering ? '触发中...' : '触发爬虫' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tab导航 -->
      <div class="flex gap-1 border-b border-slate-700">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
          :class="activeTab === tab.key
            ? 'text-cyan-400 border-cyan-400'
            : 'text-slate-400 border-transparent hover:text-slate-200'"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 基本信息 -->
      <div v-if="activeTab === 'info'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="card">
          <h3 class="text-sm text-slate-400 mb-3">Web流量</h3>
          <div v-if="competitor.web_traffic" class="space-y-3">
            <div>
              <p class="text-3xl font-bold text-white">{{ formatNumber(competitor.web_traffic.monthly_visits) }}</p>
              <p class="text-xs text-slate-500 mt-1">月访问量</p>
            </div>
            <span :class="trendBadgeClass(competitor.web_traffic.trend)">
              趋势: {{ competitor.web_traffic.trend }}
            </span>
          </div>
          <p v-else class="text-slate-500 py-4">暂无流量数据</p>
        </div>

        <div class="card">
          <h3 class="text-sm text-slate-400 mb-3">App下载量</h3>
          <div v-if="competitor.app_downloads" class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-slate-300">iOS</span>
              <span class="text-lg font-semibold text-white">{{ formatNumber(competitor.app_downloads.ios) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-slate-300">Android</span>
              <span class="text-lg font-semibold text-white">{{ formatNumber(competitor.app_downloads.android) }}</span>
            </div>
          </div>
          <p v-else class="text-slate-500 py-4">暂无下载数据</p>
        </div>

        <div class="card">
          <h3 class="text-sm text-slate-400 mb-3">定价信息</h3>
          <div v-if="competitor.pricing_info" class="space-y-2">
            <div
              v-for="(value, key) in competitor.pricing_info"
              :key="key"
              class="flex items-center justify-between p-2 rounded bg-slate-800/50"
            >
              <span class="text-slate-300 text-sm">{{ key }}</span>
              <span class="text-white text-sm font-medium">{{ value }}</span>
            </div>
          </div>
          <p v-else class="text-slate-500 py-4">暂无定价数据</p>
        </div>

        <div v-if="competitor.description" class="card lg:col-span-3">
          <h3 class="text-sm text-slate-400 mb-3">竞品描述</h3>
          <p class="text-slate-300 leading-relaxed">{{ competitor.description }}</p>
        </div>
      </div>

      <!-- 历史数据 -->
      <div v-if="activeTab === 'history'" class="card">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-white">历史数据趋势</h3>
          <select v-model="historyDays" class="input !w-auto" @change="fetchHistory">
            <option :value="7">近7天</option>
            <option :value="30">近30天</option>
            <option :value="90">近90天</option>
          </select>
        </div>
        <div v-if="historyLoading" class="flex items-center justify-center py-12">
          <div class="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
        <div v-else-if="historyData && historyData.length > 0">
          <VChart :option="historyChartOption" style="height: 400px;" autoresize />
        </div>
        <div v-else class="py-12 text-center text-slate-500">暂无历史数据</div>
      </div>

      <!-- 舆情事件 -->
      <div v-if="activeTab === 'events'" class="card">
        <h3 class="text-lg font-semibold text-white mb-4">舆情事件</h3>
        <div v-if="eventsLoading" class="flex items-center justify-center py-12">
          <div class="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
        <div v-else-if="eventsList && eventsList.length > 0" class="space-y-3">
          <div
            v-for="event in eventsList"
            :key="event.id || event.title"
            class="p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-slate-600 transition-colors"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <h4 class="text-white font-medium">{{ event.title }}</h4>
                <p v-if="event.summary" class="text-slate-400 text-sm mt-1">{{ event.summary }}</p>
              </div>
              <span
                v-if="event.sentiment"
                :class="sentimentBadgeClass(event.sentiment)"
                class="ml-4 shrink-0"
              >
                {{ sentimentLabel(event.sentiment) }}
              </span>
            </div>
            <div class="flex items-center gap-4 mt-2 text-xs text-slate-500">
              <span v-if="event.source">来源: {{ event.source }}</span>
              <span v-if="event.published_at">{{ formatTime(event.published_at) }}</span>
              <span v-if="event.impact" class="text-amber-400">影响: {{ event.impact }}</span>
            </div>
          </div>
        </div>
        <div v-else class="py-12 text-center text-slate-500">暂无舆情事件</div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card text-center py-12">
      <p class="text-slate-400">竞品数据加载失败</p>
      <button class="btn btn-primary mt-4" @click="fetchDetail">重新加载</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { competitorApi, sentimentApi, spiderApi, type Competitor } from '@/api/modules'
import dayjs from 'dayjs'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const competitor = ref<Competitor | null>(null)
const activeTab = ref<'info' | 'history' | 'events'>('info')
const triggering = ref(false)

const tabs = [
  { key: 'info' as const, label: '基本信息' },
  { key: 'history' as const, label: '历史数据' },
  { key: 'events' as const, label: '舆情事件' },
]

// 历史数据
const historyLoading = ref(false)
const historyData = ref<any[]>([])
const historyDays = ref(30)

// 舆情事件
const eventsLoading = ref(false)
const eventsList = ref<any[]>([])

const slug = computed(() => route.params.slug as string)

const historyChartOption = computed(() => {
  const dates = historyData.value.map((d: any) => dayjs(d.date).format('MM-DD'))
  const visits = historyData.value.map((d: any) => d.web_visits || d.monthly_visits || 0)
  const mentions = historyData.value.map((d: any) => d.mentions || 0)

  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['Web访问量', '提及量'],
      textStyle: { color: '#94a3b8' },
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: [
      {
        type: 'value',
        name: '访问量',
        axisLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      {
        type: 'value',
        name: '提及量',
        axisLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Web访问量',
        type: 'line',
        smooth: true,
        data: visits,
        itemStyle: { color: '#06b6d4' },
        areaStyle: { color: 'rgba(6,182,212,0.1)' },
      },
      {
        name: '提及量',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: mentions,
        itemStyle: { color: '#8b5cf6' },
        areaStyle: { color: 'rgba(139,92,246,0.1)' },
      },
    ],
  }
})

function formatNumber(n: number): string {
  if (!n) return '0'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function trendBadgeClass(trend: string): string {
  if (trend === 'up' || trend === 'rising') return 'badge badge-success'
  if (trend === 'down' || trend === 'falling') return 'badge badge-danger'
  return 'badge badge-info'
}

function sentimentBadgeClass(s: string): string {
  const map: Record<string, string> = {
    positive: 'badge badge-success',
    neutral: 'badge badge-info',
    negative: 'badge badge-danger',
  }
  return map[s] || 'badge badge-info'
}

function sentimentLabel(s: string): string {
  const map: Record<string, string> = {
    positive: '正面',
    neutral: '中性',
    negative: '负面',
  }
  return map[s] || s
}

async function fetchDetail() {
  loading.value = true
  try {
    competitor.value = await competitorApi.get(slug.value)
  } catch (err: any) {
    console.error('竞品详情加载失败:', err)
    competitor.value = null
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res: any = await competitorApi.history(slug.value, historyDays.value)
    historyData.value = res.data || res || []
  } catch (err: any) {
    console.error('历史数据加载失败:', err)
    historyData.value = []
  } finally {
    historyLoading.value = false
  }
}

async function fetchEvents() {
  eventsLoading.value = true
  try {
    const res: any = await sentimentApi.events(slug.value, 1, 20)
    eventsList.value = res.items || res.data || res || []
  } catch (err: any) {
    console.error('舆情事件加载失败:', err)
    eventsList.value = []
  } finally {
    eventsLoading.value = false
  }
}

async function handleTriggerSpider() {
  triggering.value = true
  try {
    await spiderApi.trigger({ competitor_slug: slug.value, task_type: 'full' })
    alert('爬虫任务已触发')
  } catch (err: any) {
    console.error('触发爬虫失败:', err)
    alert('触发失败: ' + (err.message || '未知错误'))
  } finally {
    triggering.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'history' && historyData.value.length === 0) {
    fetchHistory()
  }
  if (tab === 'events' && eventsList.value.length === 0) {
    fetchEvents()
  }
})

onMounted(() => {
  fetchDetail()
})
</script>
