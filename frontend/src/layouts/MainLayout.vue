<template>
  <div class="flex h-screen w-full overflow-hidden bg-[var(--color-bg)]">
    <!-- Sidebar -->
    <aside
      class="flex h-screen w-60 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)]"
    >
      <!-- Logo -->
      <div class="flex h-16 shrink-0 items-center gap-3 border-b border-[var(--color-border)] px-5">
        <div
          class="flex h-9 w-9 items-center justify-center rounded-lg shadow-lg"
          style="background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));"
        >
          <svg class="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
            />
          </svg>
        </div>
        <div class="flex flex-col leading-tight">
          <span class="text-[15px] font-semibold tracking-wide text-[var(--color-text)]">AI竞品追踪</span>
          <span class="text-[10px] uppercase tracking-[0.15em] text-[var(--color-text-muted)]">Competitor Tracker</span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto px-3 py-4">
        <p class="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
          导航
        </p>
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="group relative mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200"
          :class="
            isActive(item.path)
              ? 'font-medium'
              : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text)]'
          "
          :style="navItemStyle(item.path, false)"
        >
          <span
            v-if="isActive(item.path)"
            class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--color-primary)]"
          ></span>
          <svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
            <path
              v-for="d in item.icon"
              :key="d"
              :d="d"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span>{{ item.label }}</span>
        </router-link>

        <template v-if="authStore.isAdmin">
          <p class="mb-2 mt-5 px-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
            管理
          </p>
          <router-link
            v-for="item in adminItems"
            :key="item.path"
            :to="item.path"
            class="group relative mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-200"
            :class="
              isActive(item.path)
                ? 'font-medium'
                : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text)]'
            "
            :style="navItemStyle(item.path, true)"
          >
            <span
              v-if="isActive(item.path)"
              class="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--color-secondary)]"
            ></span>
            <svg class="h-[18px] w-[18px] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
              <path
                v-for="d in item.icon"
                :key="d"
                stroke-linecap="round"
                stroke-linejoin="round"
                :d="d"
              />
            </svg>
            <span>{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <!-- User info & quota -->
      <div class="shrink-0 border-t border-[var(--color-border)] p-3">
        <div class="rounded-lg bg-[var(--color-bg-tertiary)] p-3">
          <div class="mb-2.5 flex items-center gap-2.5">
            <div
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
              style="background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));"
            >
              {{ userInitials }}
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13px] font-medium text-[var(--color-text)]">
                {{ authStore.user?.name || '用户' }}
              </p>
              <p class="truncate text-[11px] text-[var(--color-text-muted)]">
                {{ authStore.user?.email }}
              </p>
            </div>
            <span
              class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
              :style="authStore.isAdmin
                ? 'background: rgba(139,92,246,0.15); color: var(--color-secondary);'
                : 'background: rgba(6,182,212,0.15); color: var(--color-primary);'"
            >
              {{ authStore.user?.role }}
            </span>
          </div>
          <!-- Quota bar -->
          <div>
            <div class="mb-1 flex items-center justify-between text-[11px]">
              <span class="text-[var(--color-text-muted)]">今日配额剩余</span>
              <span class="font-medium text-[var(--color-text)]">
                {{ authStore.quotaRemaining }} / {{ authStore.user?.daily_quota ?? 0 }}
              </span>
            </div>
            <div class="h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg)]">
              <div
                class="h-full rounded-full transition-all duration-500"
                :style="`width: ${quotaPercent}%; background: linear-gradient(90deg, var(--color-primary), var(--color-secondary));`"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
      <!-- Top bar -->
      <header
        class="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-6 backdrop-blur-md"
        style="background: rgba(10, 14, 26, 0.8);"
      >
        <div class="flex items-center gap-2 text-sm">
          <span class="font-medium text-[var(--color-text)]">{{ currentPageTitle }}</span>
        </div>
        <div class="flex items-center gap-3">
          <!-- Quota badge -->
          <div
            class="flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3 py-1.5"
          >
            <svg class="h-4 w-4 text-[var(--color-primary)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
              />
            </svg>
            <span class="text-xs text-[var(--color-text-muted)]">剩余配额</span>
            <span class="text-sm font-semibold text-[var(--color-primary)]">{{ authStore.quotaRemaining }}</span>
          </div>
          <!-- Logout -->
          <button
            class="btn btn-secondary"
            title="退出登录"
            @click="handleLogout"
          >
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
              />
            </svg>
            <span class="text-xs">退出</span>
          </button>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto overflow-x-hidden">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

interface NavItem {
  path: string
  label: string
  icon: string[]
}

const navItems: NavItem[] = [
  {
    path: '/',
    label: 'Dashboard',
    icon: [
      'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z',
    ],
  },
  {
    path: '/competitors',
    label: '竞品管理',
    icon: [
      'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.75 6.75 0 0111.715-4.548m0 0c.44-.39.99-.683 1.59-.857m-4.99 2.563a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0z',
    ],
  },
  {
    path: '/sentiment',
    label: '舆情面板',
    icon: [
      'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
    ],
  },
  {
    path: '/spiders',
    label: '爬虫任务',
    icon: [
      'M12 12.75c1.148 0 2.278.08 3.383.237 1.037.146 1.866.966 1.866 2.013 0 3.728-2.35 6.75-5.25 6.75S6.75 18.728 6.75 15c0-1.046.83-1.867 1.866-2.013A24.204 24.204 0 0112 12.75zm0 0c2.883 0 5.647.508 8.207 1.44a23.91 23.91 0 01-1.152 6.06M12 12.75c-2.883 0-5.647.508-8.208 1.44.125 2.104.52 4.136 1.153 6.06M12 12.75a2.25 2.25 0 002.248-2.354M12 12.75a2.25 2.25 0 01-2.248-2.354M12 8.25c.995 0 1.971-.08 2.922-.236.403-.066.74-.358.795-.762a3.778 3.778 0 00-.399-2.25M12 8.25c-.995 0-1.97-.08-2.922-.236-.402-.066-.74-.358-.795-.762a3.778 3.778 0 01.399-2.25M12 8.25a2.25 2.25 0 00-2.248 2.146M12 8.25a2.25 2.25 0 012.248 2.146M8.683 5a6.032 6.032 0 01-1.155-.1 2.5 2.5 0 01-.36-.07 2.251 2.251 0 011.515-2.236m4.434 2.406a6.032 6.032 0 001.155-.1 2.5 2.5 0 00.36-.07 2.251 2.251 0 00-1.515-2.236',
    ],
  },
  {
    path: '/profile',
    label: '用户中心',
    icon: [
      'M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z',
    ],
  },
  {
    path: '/payment',
    label: '充值',
    icon: [
      'M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z',
    ],
  },
]

const adminItems: NavItem[] = [
  {
    path: '/audit',
    label: '审计日志',
    icon: [
      'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
    ],
  },
  {
    path: '/admin',
    label: '系统管理',
    icon: [
      'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z',
      'M15 12a3 3 0 11-6 0 3 3 0 016 0z',
    ],
  },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(path + '/')
}

function navItemStyle(path: string, isAdmin = false): Record<string, string> {
  if (!isActive(path)) return {}
  const color = isAdmin ? 'var(--color-secondary)' : 'var(--color-primary)'
  const tint = isAdmin ? 'rgba(139,92,246,0.12)' : 'rgba(6,182,212,0.12)'
  return { background: tint, color }
}

const userInitials = computed(() => {
  const name = authStore.user?.name || authStore.user?.email || 'U'
  return name.charAt(0).toUpperCase()
})

const quotaPercent = computed(() => {
  const total = authStore.user?.daily_quota ?? 0
  if (!total) return 0
  const used = authStore.user?.quota_used ?? 0
  const remaining = Math.max(0, total - used)
  return Math.round((remaining / total) * 100)
})

const routeTitleMap: Record<string, string> = {
  '/': 'Dashboard 概览',
  '/competitors': '竞品管理',
  '/sentiment': '舆情面板',
  '/spiders': '爬虫任务',
  '/profile': '用户中心',
  '/payment': '充值中心',
  '/audit': '审计日志',
  '/admin': '系统管理',
}

const currentPageTitle = computed(() => {
  const match = Object.keys(routeTitleMap).find((p) => isActive(p))
  return match ? routeTitleMap[match] : 'AI竞品追踪'
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
