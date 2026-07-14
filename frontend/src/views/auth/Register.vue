<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--color-bg)] px-4 py-8">
    <!-- Background decoration -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        class="absolute -left-40 -top-40 h-96 w-96 rounded-full opacity-20 blur-3xl"
        style="background: var(--color-secondary);"
      ></div>
      <div
        class="absolute -bottom-40 -right-40 h-96 w-96 rounded-full opacity-20 blur-3xl"
        style="background: var(--color-primary);"
      ></div>
      <div
        class="absolute left-1/2 top-1/2 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-5 blur-3xl"
        style="background: var(--color-secondary);"
      ></div>
    </div>

    <div class="relative z-10 w-full max-w-md">
      <!-- Logo & Title -->
      <div class="mb-8 text-center">
        <div
          class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow-xl"
          style="background: linear-gradient(135deg, var(--color-secondary), var(--color-primary));"
        >
          <svg class="h-7 w-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M18 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM3 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 019.374 21c-2.331 0-4.512-.645-6.374-1.766z"
            />
          </svg>
        </div>
        <h1 class="text-2xl font-bold tracking-wide text-[var(--color-text)]">创建账号</h1>
        <p class="mt-2 text-sm text-[var(--color-text-muted)]">加入 AI竞品追踪，开启智能监测</p>
      </div>

      <!-- Card -->
      <div class="card" style="box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.5);">
        <form class="space-y-5" @submit.prevent="handleRegister">
          <!-- Name -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-[var(--color-text)]">姓名</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">
                <svg class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                  />
                </svg>
              </span>
              <input
                v-model.trim="form.name"
                type="text"
                class="input pl-10"
                placeholder="请输入您的姓名"
                :class="errors.name ? 'border-[var(--color-danger)]' : ''"
                @input="clearError('name')"
              />
            </div>
            <p v-if="errors.name" class="mt-1.5 text-xs text-[var(--color-danger)]">{{ errors.name }}</p>
          </div>

          <!-- Email -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-[var(--color-text)]">邮箱</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">
                <svg class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"
                  />
                </svg>
              </span>
              <input
                v-model.trim="form.email"
                type="email"
                class="input pl-10"
                placeholder="you@example.com"
                :class="errors.email ? 'border-[var(--color-danger)]' : ''"
                @blur="validateEmail"
                @input="clearError('email')"
              />
            </div>
            <p v-if="errors.email" class="mt-1.5 text-xs text-[var(--color-danger)]">{{ errors.email }}</p>
          </div>

          <!-- Password -->
          <div>
            <label class="mb-1.5 block text-sm font-medium text-[var(--color-text)]">密码</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">
                <svg class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                  />
                </svg>
              </span>
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="input px-10"
                placeholder="至少8位，含大小写和数字"
                :class="errors.password ? 'border-[var(--color-danger)]' : ''"
                @input="onPasswordInput"
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
                @click="showPassword = !showPassword"
              >
                <svg v-if="!showPassword" class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <svg v-else class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
                  />
                </svg>
              </button>
            </div>

            <!-- Strength meter -->
            <div v-if="form.password" class="mt-2">
              <div class="flex gap-1">
                <div
                  v-for="i in 4"
                  :key="i"
                  class="h-1 flex-1 rounded-full transition-all duration-300"
                  :style="i <= passwordScore ? strengthBarStyle : 'background: var(--color-border);'"
                ></div>
              </div>
              <p class="mt-1.5 text-[11px]" :style="`color: ${strengthColor};`">
                密码强度：{{ strengthLabel }}
              </p>
            </div>

            <!-- Requirements checklist -->
            <ul class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
              <li class="flex items-center gap-1.5" :style="`color: ${checks.length ? 'var(--color-success)' : 'var(--color-text-muted)'};`">
                <svg v-if="checks.length" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <svg v-else class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="9" />
                </svg>
                至少8位字符
              </li>
              <li class="flex items-center gap-1.5" :style="`color: ${checks.upper ? 'var(--color-success)' : 'var(--color-text-muted)'};`">
                <svg v-if="checks.upper" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <svg v-else class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="9" />
                </svg>
                包含大写字母
              </li>
              <li class="flex items-center gap-1.5" :style="`color: ${checks.lower ? 'var(--color-success)' : 'var(--color-text-muted)'};`">
                <svg v-if="checks.lower" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <svg v-else class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="9" />
                </svg>
                包含小写字母
              </li>
              <li class="flex items-center gap-1.5" :style="`color: ${checks.digit ? 'var(--color-success)' : 'var(--color-text-muted)'};`">
                <svg v-if="checks.digit" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <svg v-else class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="9" />
                </svg>
                包含数字
              </li>
            </ul>

            <p v-if="errors.password" class="mt-1.5 text-xs text-[var(--color-danger)]">{{ errors.password }}</p>
          </div>

          <!-- Error message -->
          <transition name="fade">
            <div
              v-if="error"
              class="flex items-start gap-2 rounded-lg border p-3"
              style="background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.3);"
            >
              <svg class="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-danger)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
              <span class="text-xs text-[var(--color-danger)]">{{ error }}</span>
            </div>
          </transition>

          <!-- Submit -->
          <button
            type="submit"
            class="btn btn-primary w-full py-2.5"
            :disabled="authStore.loading"
          >
            <svg
              v-if="authStore.loading"
              class="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ authStore.loading ? '注册中...' : '注册' }}
          </button>
        </form>
      </div>

      <!-- Footer link -->
      <p class="mt-6 text-center text-sm text-[var(--color-text-muted)]">
        已有账号？
        <router-link to="/login" class="font-medium text-[var(--color-primary)] transition-colors hover:underline">
          去登录
        </router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const form = reactive({
  name: '',
  email: '',
  password: '',
})

const errors = reactive({
  name: '',
  email: '',
  password: '',
})

const error = ref('')
const showPassword = ref(false)

const checks = computed(() => ({
  length: form.password.length >= 8,
  upper: /[A-Z]/.test(form.password),
  lower: /[a-z]/.test(form.password),
  digit: /\d/.test(form.password),
}))

const passwordScore = computed(() => {
  return Object.values(checks.value).filter(Boolean).length
})

const strengthLabel = computed(() => {
  if (!form.password) return ''
  const labels = ['很弱', '较弱', '一般', '良好', '强']
  return labels[passwordScore.value] || '很弱'
})

const strengthColor = computed(() => {
  if (!form.password) return 'var(--color-text-muted)'
  switch (passwordScore.value) {
    case 0:
    case 1:
      return 'var(--color-danger)'
    case 2:
      return 'var(--color-warning)'
    case 3:
      return 'var(--color-primary)'
    case 4:
      return 'var(--color-success)'
    default:
      return 'var(--color-text-muted)'
  }
})

const strengthBarStyle = computed(() => {
  return `background: ${strengthColor.value};`
})

function onPasswordInput() {
  errors.password = ''
  error.value = ''
}

function clearError(field: 'name' | 'email' | 'password') {
  errors[field] = ''
  error.value = ''
}

function validateName(): boolean {
  if (!form.name) {
    errors.name = '请输入姓名'
    return false
  }
  if (form.name.length < 2) {
    errors.name = '姓名至少2个字符'
    return false
  }
  errors.name = ''
  return true
}

function validateEmail(): boolean {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!form.email) {
    errors.email = '请输入邮箱'
    return false
  }
  if (!re.test(form.email)) {
    errors.email = '邮箱格式不正确'
    return false
  }
  errors.email = ''
  return true
}

function validatePassword(): boolean {
  if (!form.password) {
    errors.password = '请输入密码'
    return false
  }
  if (!checks.value.length) {
    errors.password = '密码至少需要8位字符'
    return false
  }
  if (!checks.value.upper || !checks.value.lower) {
    errors.password = '密码需同时包含大小写字母'
    return false
  }
  if (!checks.value.digit) {
    errors.password = '密码需包含数字'
    return false
  }
  errors.password = ''
  return true
}

async function handleRegister() {
  error.value = ''
  const ok = validateName() && validateEmail() && validatePassword()
  if (!ok) return

  try {
    await authStore.register(form.email, form.password, form.name)
    router.push('/')
  } catch (e: any) {
    error.value = e?.message || '注册失败，请稍后重试'
  }
}
</script>
