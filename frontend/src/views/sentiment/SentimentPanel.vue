<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">舆情面板</h1>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <template v-else-if="dashboard">
      <!-- 顶部统计 -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="card">
          <p class="text-sm text-slate-400">总提及量</p>
          <p class="text-3xl font-bold text-white mt-2">{{ formatNumber(dashboard.overview.total_mentions) }}</p>
        </div>
        <div class="card border-l-4" style="border-left-color: #10b981;">
          <p class="text-sm text-slate-400">正面</p>
          <div class="flex items-end gap-2 mt-2">
            <p class="text-3xl font-bold text-emerald-400">{{ dist.positive }}</p>
            <p class="text-sm text-slate-500 mb-1">{{ distRatio.positive }}%</p>
          </div>
        </div>
        <div class="card border-l-4" style="border-left-color: #94a3b8;">
          <p class="text-sm text-slate-400">中性</p>
          <div class="flex items-end gap-2 mt-2">
            <p class="text-3xl font-bold text-slate-300">{{ dist.neutral }}</p>
            <p class="text-sm text-slate-500 mb-1">{{ distRatio.neutral }}%</p>
          </div>
        </div>
        <div class="card border-l-4" style="border-left-color: #ef4444;">
          <p class="text-sm text-slate-400">负面</p>
          <div class="flex items-end gap-2 mt-2">
            <p class="text-3xl font-bold text-red-400">{{ dist.negative }}</p>
            <p class="text-sm text-slate-500 mb-1">{{ distRatio.negative }}%</p>
          </div>
        </div>
      </div>

      <!-- 情感分布环形图 + 趋势图 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 环形图 -->
        <div class="card">
          <h2 class="text-lg font-semibold text-white mb-4">情感分布</h2>
          <VChart :option="donutOption" style="height: 300px;" autoresize />
        </div>

        <!-- 趋势堆叠面积图 -->
        <div class="card lg:col-span-2">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-white">30天舆情趋势</h2>
            <span class="text-xs text-slate-500">{{ trendData?.time_range }}</span>
          </div>
          <div v-if="trendLoading" class="flex items-center justify-center py-12">
            <div class="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <VChart v-else-if="trendData && trendData.data.length > 0" :option="trendChartOption" style="height: 300px;" autoresize />
          <div v-else class="py-12 text-center text-slate-500">暂无趋势数据</div>
        </div>
      </div>

      <!-- 各竞品舆情概览卡片 -->
      <div>
        <h2 class="text-lg font-semibold text-white mb-4">各竞品舆情概览</h2>
        <div v-if="dashboard.competitors.length === 0" class="card py-8 text-center text-slate-500">
          暂无竞品舆情数据
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="comp in dashboard.competitors"
            :key="comp.slug"
            class="card hover:border-cyan-500/50 cursor-pointer transition-colors"
            @click="router.push(`/competitors/${comp.slug}`)"
          >
            <div class="flex items-center justify-between mb-3">
              <h3 class="font-medium text-white">{{ comp.slug }}</h3>
              <span class="text-xs text-slate-500">{{ comp.mention_count }} 条提及</span>
            </div>
            <!-- 情感得分 -->
            <div class="mb-3">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs text-slate-400">情感得分</span>
                <span class="text-sm font-bold" :class="scoreColorClass(comp.sentiment_score)">
                  {{ comp.sentiment_score }}/100
                </span>
              </div>
              <div class="w-full h-2 rounded-full bg-slate-700 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="scoreBarClass(comp.sentiment_score)"
                  :style="{ width: comp.sentiment_score + '%' }"
                ></div>
              </div>
            </div>
            <!-- 热点事件 -->
            <div v-if="comp.hot_events && comp.hot_events.length > 0" class="space-y-1">
              <p class="text-xs text-slate-400 mb-1">热点事件</p>
              <div
                v-for="(event, idx) in comp.hot_events.slice(0, 2)"
                :key="idx"
                class="text-xs text-slate-300 truncate"
              >
                <span class="text-slate-500 mr-1">-</span>{{ event.title }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 热门话题标签云 -->
      <div class="card">
        <h2 class="text-lg font-semibold text-white mb-4">热门话题</h2>
        <div v-if="dashboard.overview.trending_topics.length === 0" class="py-8 text-center text-slate-500">
          暂无热门话题
        </div>
        <div v-else class="flex flex-wrap gap-3">
          <span
            v-for="(topic, idx) in dashboard.overview.trending_topics"
            :key="idx"
            class="px-4 py-2 rounded-full text-sm font-medium cursor-pointer transition-all hover:scale-105"
            :style="tagCloudStyle(idx)"
            @click="analyzeText = topic"
          >
            {{ topic }}
          </span>
        </div>
      </div>

      <!-- 文本分析 -->
      <div class="card">
        <h2 class="text-lg font-semibold text-white mb-4">AI文本情感分析</h2>
        <div class="space-y-4">
          <div>
            <textarea
              v-model="analyzeText"
              class="input"
              rows="4"
              placeholder="输入要分析的文本，由DeepSeek提供情感分析能力..."
            ></textarea>
          </div>
          <div class="flex items-center justify-between">
            <p class="text-xs text-slate-500">基于 DeepSeek 大模型进行深度情感分析</p>
            <button
              class="btn btn-primary"
              :disabled="!analyzeText.trim() || analyzing"
              @click="handleAnalyze"
            >
              {{ analyzing ? '分析中...' : '开始分析' }}
            </button>
          </div>

          <!-- 分析结果 -->
          <div v-if="analyzeResult" class="p-4 rounded-lg bg-slate-800/50 border border-slate-700 space-y-3">
            <div class="flex items-center gap-3">
              <span class="text-sm text-slate-400">分析结果:</span>
              <span
                class="badge"
                :class="analyzeResult.sentiment === 'positive' ? 'badge-success' : analyzeResult.sentiment === 'negative' ? 'badge-danger' : 'badge-info'"
              >
                {{ sentimentLabel(analyzeResult.sentiment) }}
              </span>
              <span v-if="analyzeResult.score !== undefined" class="text-sm text-slate-300">
                置信度: {{ (analyzeResult.score * 100).toFixed(1) }}%
              </span>
            </div>
            <div v-if="analyzeResult.keywords && analyzeResult.keywords.length > 0" class="flex flex-wrap gap-2">
              <span class="text-xs text-slate-500">关键词:</span>
              <span
                v-for="(kw, idx) in analyzeResult.keywords"
                :key="idx"
                class="px-2 py-0.5 rounded text-xs bg-cyan-500/10 text-cyan-400"
              >
                {{ kw }}
              </span>
            </div>
            <div v-if="analyzeResult.analysis" class="text-sm text-slate-300 leading-relaxed">
              <p class="text-xs text-slate-500 mb-1">DeepSeek深度分析:</p>
              {{ analyzeResult.analysis }}
            </div>
            <div v-if="analyzeResult.summary" class="text-sm text-slate-300 leading-relaxed">
              <p class="text-xs text-slate-500 mb-1">摘要:</p>
              {{ analyzeResult.summary }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card text-center py-12">
      <p class="text-slate-400">舆情数据加载失败</p>
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
import { PieChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { sentimentApi, type SentimentDashboard, type SentimentTrends } from '@/api/modules'
import dayjs from 'dayjs'

use([CanvasRenderer, PieChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const router = useRouter()
const loading = ref(false)
const trendLoading = ref(false)
const analyzing = ref(false)
const dashboard = ref<SentimentDashboard | null>(null)
const trendData = ref<SentimentTrends | null>(null)
const analyzeText = ref('')
const analyzeResult = ref<any>(null)

const dist = computed(() => {
  return dashboard.value?.overview.sentiment_distribution || { positive: 0, neutral: 0, negative: 0 }
})

const totalMentions = computed(() => {
  return dist.value.positive + dist.value.neutral + dist.value.negative
})

const distRatio = computed(() => {
  if (totalMentions.value === 0) return { positive: '0', neutral: '0', negative: '0' }
  return {
    positive: ((dist.value.positive / totalMentions.value) * 100).toFixed(1),
    neutral: ((dist.value.neutral / totalMentions.value) * 100).toFixed(1),
    negative: ((dist.value.negative / totalMentions.value) * 100).toFixed(1),
  }
})

const donutOption = computed(() => {
  const d = dist.value
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#111827', borderWidth: 2 },
        label: {
          show: true,
          position: 'center',
          formatter: `{a|${formatNumber(dashboard.value?.overview.total_mentions || 0)}}\n{b|总提及}`,
          rich: {
            a: { fontSize: 24, fontWeight: 'bold', color: '#f1f5f9', lineHeight: 32 },
            b: { fontSize: 12, color: '#94a3b8' },
          },
        },
        emphasis: { label: { show: true } },
        data: [
          { value: d.positive, name: '正面', itemStyle: { color: '#10b981' } },
          { value: d.neutral, name: '中性', itemStyle: { color: '#94a3b8' } },
          { value: d.negative, name: '负面', itemStyle: { color: '#ef4444' } },
        ],
      },
    ],
  }
})

const trendChartOption = computed(() => {
  if (!trendData.value) return {}
  const dates = trendData.value.data.map((d) => dayjs(d.date).format('MM-DD'))
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['正面', '中性', '负面'],
      textStyle: { color: '#94a3b8' },
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [
      {
        name: '正面',
        type: 'line',
        stack: 'total',
        smooth: true,
        data: trendData.value.data.map((d) => d.positive),
        itemStyle: { color: '#10b981' },
        areaStyle: { color: 'rgba(16,185,129,0.2)' },
      },
      {
        name: '中性',
        type: 'line',
        stack: 'total',
        smooth: true,
        data: trendData.value.data.map((d) => d.neutral),
        itemStyle: { color: '#94a3b8' },
        areaStyle: { color: 'rgba(148,163,184,0.2)' },
      },
      {
        name: '负面',
        type: 'line',
        stack: 'total',
        smooth: true,
        data: trendData.value.data.map((d) => d.negative),
        itemStyle: { color: '#ef4444' },
        areaStyle: { color: 'rgba(239,68,68,0.2)' },
      },
    ],
  }
})

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function sentimentLabel(s: string): string {
  const map: Record<string, string> = {
    positive: '正面',
    neutral: '中性',
    negative: '负面',
  }
  return map[s] || s
}

function scoreColorClass(score: number): string {
  if (score >= 70) return 'text-emerald-400'
  if (score >= 40) return 'text-amber-400'
  return 'text-red-400'
}

function scoreBarClass(score: number): string {
  if (score >= 70) return 'bg-emerald-500'
  if (score >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

function tagCloudStyle(idx: number): Record<string, string> {
  const colors = [
    'rgba(6,182,212,0.15)', 'rgba(139,92,246,0.15)', 'rgba(16,185,129,0.15)',
    'rgba(245,158,11,0.15)', 'rgba(236,72,153,0.15)',
  ]
  const textColors = ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899']
  const sizes = ['0.875rem', '1rem', '1.125rem', '0.9rem', '1.25rem']
  const colorIdx = idx % colors.length
  return {
    background: colors[colorIdx],
    color: textColors[colorIdx],
    fontSize: sizes[idx % sizes.length],
  }
}

async function fetchData() {
  loading.value = true
  try {
    dashboard.value = await sentimentApi.dashboard()
  } catch (err: any) {
    console.error('舆情面板加载失败:', err)
    dashboard.value = null
  } finally {
    loading.value = false
  }
}

async function fetchTrends() {
  trendLoading.value = true
  try {
    trendData.value = await sentimentApi.trends(30)
  } catch (err: any) {
    console.error('趋势数据加载失败:', err)
    trendData.value = null
  } finally {
    trendLoading.value = false
  }
}

async function handleAnalyze() {
  if (!analyzeText.value.trim()) return
  analyzing.value = true
  analyzeResult.value = null
  try {
    const res: any = await sentimentApi.analyze(analyzeText.value)
    analyzeResult.value = res
  } catch (err: any) {
    console.error('文本分析失败:', err)
    alert('分析失败: ' + (err.message || '未知错误'))
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchTrends()
})
</script>
