import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { auth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
      },
      {
        path: 'competitors',
        name: 'Competitors',
        component: () => import('@/views/competitors/CompetitorList.vue'),
      },
      {
        path: 'competitors/:slug',
        name: 'CompetitorDetail',
        component: () => import('@/views/competitors/CompetitorDetail.vue'),
      },
      {
        path: 'sentiment',
        name: 'Sentiment',
        component: () => import('@/views/sentiment/SentimentPanel.vue'),
      },
      {
        path: 'spiders',
        name: 'Spiders',
        component: () => import('@/views/spiders/SpiderTasks.vue'),
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/Profile.vue'),
      },
      {
        path: 'payment',
        name: 'Payment',
        component: () => import('@/views/user/Payment.vue'),
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('@/views/admin/AuditLogs.vue'),
        meta: { admin: true },
      },
      {
        path: 'admin',
        name: 'AdminConfig',
        component: () => import('@/views/admin/AdminConfig.vue'),
        meta: { admin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.public) {
    next()
    return
  }

  if (to.meta.auth && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  if (to.meta.admin && !authStore.isAdmin) {
    next('/')
    return
  }

  next()
})

export default router
