<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">充值中心</h1>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      <span class="ml-3 text-slate-400">加载中...</span>
    </div>

    <template v-else>
      <!-- 套餐列表 -->
      <div>
        <h2 class="text-lg font-semibold text-white mb-4">选择套餐</h2>
        <div v-if="plans.length === 0" class="card py-12 text-center text-slate-500">
          暂无可用套餐
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div
            v-for="plan in plans"
            :key="plan.plan_type"
            class="card relative cursor-pointer transition-all hover:scale-[1.02]"
            :class="selectedPlan === plan.plan_type
              ? 'border-cyan-500 ring-2 ring-cyan-500/30'
              : 'hover:border-slate-600'"
            @click="selectedPlan = plan.plan_type"
          >
            <!-- 推荐标识 -->
            <div
              v-if="plan.plan_type === 'pro' || plan.plan_type === 'professional'"
              class="absolute -top-2 right-4 badge badge-warning"
            >
              推荐
            </div>

            <h3 class="text-lg font-bold text-white">{{ plan.name }}</h3>
            <p class="text-xs text-slate-500 mt-1">{{ plan.description }}</p>

            <div class="mt-4">
              <div class="flex items-baseline gap-1">
                <span class="text-sm text-slate-400">￥</span>
                <span class="text-3xl font-bold text-white">{{ plan.price }}</span>
              </div>
            </div>

            <div class="mt-4 space-y-2 text-sm border-t border-slate-700 pt-4">
              <div class="flex items-center justify-between">
                <span class="text-slate-400">基础配额</span>
                <span class="text-slate-200">{{ plan.quota }}</span>
              </div>
              <div v-if="plan.bonus > 0" class="flex items-center justify-between">
                <span class="text-slate-400">赠送配额</span>
                <span class="text-emerald-400">+{{ plan.bonus }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-400">总配额</span>
                <span class="text-cyan-400 font-bold">{{ plan.total_quota }}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-slate-400">单价</span>
                <span class="text-slate-300 text-xs">
                  ￥{{ (plan.price / plan.total_quota).toFixed(4) }}/次
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 支付方式 + 订单 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 支付方式 -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">支付方式</h3>
          <div class="space-y-3">
            <label
              class="flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors"
              :class="paymentChannel === 'wechat' ? 'border-emerald-500 bg-emerald-500/5' : 'border-slate-700 hover:border-slate-600'"
            >
              <input
                v-model="paymentChannel"
                type="radio"
                value="wechat"
                class="w-4 h-4 accent-emerald-500"
              />
              <div class="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                <svg class="w-6 h-6 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-7.062-6.122zm-2.882 3.041c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z" />
                </svg>
              </div>
              <div>
                <p class="text-white font-medium">微信支付</p>
                <p class="text-xs text-slate-500">推荐使用</p>
              </div>
            </label>

            <label
              class="flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors"
              :class="paymentChannel === 'alipay' ? 'border-cyan-500 bg-cyan-500/5' : 'border-slate-700 hover:border-slate-600'"
            >
              <input
                v-model="paymentChannel"
                type="radio"
                value="alipay"
                class="w-4 h-4 accent-cyan-500"
              />
              <div class="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center">
                <svg class="w-6 h-6 text-cyan-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M22.95 16.96c-.49.22-2.5.87-4.5 1.34-2.28.54-4.84.96-7.73.96-3.62 0-6.96-.62-9.46-2.16C.56 17.3 0 15.83 0 14.5c0-2.2 1.41-4.55 4.05-6.98 2.4-2.21 5.1-3.42 7.26-3.42 2.18 0 3.78 1.5 3.78 3.78 0 2.4-1.84 4.27-4.05 4.78.31.64 1.02 1.23 2.12 1.23 2.07 0 4.66-1.42 6.6-3.93C20.4 10.2 21.7 7.99 21.7 6.06c0-2.37-1.88-4.2-4.48-4.2-2.84 0-6.06 1.16-9.06 3.4C5.27 7.36 2.3 10.3.8 13.42c-.13.27-.52.17-.49-.13C.95 7.46 4.43 2.84 9.25.5 12.22-1.26 16.1-.32 18.3 1.9c2.2 2.23 2.2 6.2-.8 8.42-2.07 1.53-4.73 2.16-7.13 2.16-.27 0-.53-.01-.79-.04-1.9 1.43-3.6 2.57-3.6 4.14 0 1.43 1.46 2.35 4.85 2.35 3.33 0 7.2-1.17 10.06-2.62 2.26-1.15 2.82-1.7 2.62-.36z" />
                </svg>
              </div>
              <div>
                <p class="text-white font-medium">支付宝</p>
                <p class="text-xs text-slate-500">快捷支付</p>
              </div>
            </label>
          </div>

          <button
            class="btn btn-primary w-full mt-6"
            :disabled="!selectedPlan || creatingOrder"
            @click="handleCreateOrder"
          >
            {{ creatingOrder ? '创建订单中...' : '立即支付' }}
          </button>
        </div>

        <!-- 订单状态 -->
        <div class="card">
          <h3 class="text-lg font-semibold text-white mb-4">订单状态</h3>
          <div v-if="!currentOrder" class="py-8 text-center text-slate-500">
            暂无订单，请选择套餐并支付
          </div>
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">订单号</span>
              <span class="text-sm text-white font-mono">{{ currentOrder.order_no || currentOrder.id }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">套餐</span>
              <span class="text-sm text-white">{{ currentOrder.plan_name || selectedPlanName }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">金额</span>
              <span class="text-lg font-bold text-cyan-400">￥{{ currentOrder.amount || selectedPlanPrice }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">支付方式</span>
              <span class="text-sm text-white">{{ paymentChannel === 'wechat' ? '微信支付' : '支付宝' }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-slate-400">状态</span>
              <span :class="orderStatusClass(currentOrder.status)">
                {{ orderStatusLabel(currentOrder.status) }}
              </span>
            </div>

            <!-- 二维码区域 -->
            <div v-if="currentOrder.status === 'pending' && currentOrder.qr_code" class="flex flex-col items-center py-4">
              <div class="w-48 h-48 bg-white rounded-lg p-2">
                <img :src="currentOrder.qr_code" alt="支付二维码" class="w-full h-full" />
              </div>
              <p class="text-xs text-slate-400 mt-2">请使用{{ paymentChannel === 'wechat' ? '微信' : '支付宝' }}扫码支付</p>
            </div>

            <button
              v-if="currentOrder.status === 'pending'"
              class="btn btn-secondary w-full"
              :disabled="queryingOrder"
              @click="handleQueryOrder"
            >
              {{ queryingOrder ? '查询中...' : '刷新支付状态' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { paymentApi, type PaymentPlan } from '@/api/modules'

const loading = ref(false)
const creatingOrder = ref(false)
const queryingOrder = ref(false)
const plans = ref<PaymentPlan[]>([])
const selectedPlan = ref('')
const paymentChannel = ref('wechat')
const currentOrder = ref<any>(null)

const selectedPlanName = computed(() => {
  const plan = plans.value.find((p) => p.plan_type === selectedPlan.value)
  return plan?.name || ''
})

const selectedPlanPrice = computed(() => {
  const plan = plans.value.find((p) => p.plan_type === selectedPlan.value)
  return plan?.price || 0
})

function orderStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待支付',
    paid: '已支付',
    completed: '已完成',
    failed: '支付失败',
    cancelled: '已取消',
    expired: '已过期',
  }
  return map[status] || status
}

function orderStatusClass(status: string): string {
  const map: Record<string, string> = {
    pending: 'badge badge-warning',
    paid: 'badge badge-success',
    completed: 'badge badge-success',
    failed: 'badge badge-danger',
    cancelled: 'badge badge-info',
    expired: 'badge badge-info',
  }
  return map[status] || 'badge badge-info'
}

async function fetchPlans() {
  loading.value = true
  try {
    plans.value = await paymentApi.plans()
    if (plans.value.length > 0) {
      selectedPlan.value = plans.value[1]?.plan_type || plans.value[0].plan_type
    }
  } catch (err: any) {
    console.error('套餐加载失败:', err)
    plans.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreateOrder() {
  if (!selectedPlan.value) return
  creatingOrder.value = true
  try {
    const res: any = await paymentApi.createOrder(selectedPlan.value, paymentChannel.value)
    currentOrder.value = res
  } catch (err: any) {
    console.error('创建订单失败:', err)
    alert('创建订单失败: ' + (err.message || '未知错误'))
  } finally {
    creatingOrder.value = false
  }
}

async function handleQueryOrder() {
  if (!currentOrder.value?.order_no && !currentOrder.value?.id) return
  queryingOrder.value = true
  try {
    const orderNo = currentOrder.value.order_no || currentOrder.value.id
    const res: any = await paymentApi.queryOrder(orderNo)
    currentOrder.value = { ...currentOrder.value, ...res }
  } catch (err: any) {
    console.error('查询订单失败:', err)
    alert('查询失败: ' + (err.message || '未知错误'))
  } finally {
    queryingOrder.value = false
  }
}

onMounted(() => {
  fetchPlans()
})
</script>
