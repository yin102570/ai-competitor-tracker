import api from './index'

// ============================================================
// 认证相关API
// ============================================================

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface UserProfile {
  id: number
  email: string
  name: string
  role: string
  daily_quota: number
  quota_used: number
  quota_remaining: number
  is_active: boolean
  created_at: string
}

export const authApi = {
  login: (data: LoginRequest) => api.post<any, LoginResponse>('/api/v1/auth/login', data),
  refresh: () => api.post('/api/v1/auth/refresh'),
  getApiKeys: () => api.get('/api/v1/auth/api-key'),
  createApiKey: (name: string) => api.post('/api/v1/auth/api-key', { name }),
}

export const userApi = {
  register: (data: { email: string; password: string; name: string }) =>
    api.post<any, UserProfile>('/api/v1/users/register', data),
  getMe: () => api.get<any, UserProfile>('/api/v1/users/me'),
  updateMe: (data: { name?: string }) => api.put('/api/v1/users/me', data),
  getQuota: (userId: number) => api.get(`/api/v1/users/${userId}/quota`),
  updateRole: (userId: number, role: string) => api.put(`/api/v1/users/${userId}/role`, { role }),
}

// ============================================================
// 竞品相关API
// ============================================================

export interface Competitor {
  slug: string
  name: string
  company: string
  category: string
  web_traffic?: { monthly_visits: number; trend: string }
  app_downloads?: { ios: number; android: number }
  pricing_info?: any
  description?: string
  is_active: boolean
  updated_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const competitorApi = {
  list: (params?: { page?: number; size?: number; category?: string }) =>
    api.get<any, PaginatedResponse<Competitor>>('/api/v1/competitors', { params: { page: params?.page, page_size: params?.size, category: params?.category } }),
  get: (slug: string) => api.get<any, Competitor>(`/api/v1/competitors/${slug}`),
  create: (data: Partial<Competitor>) => api.post('/api/v1/competitors', data),
  update: (slug: string, data: Partial<Competitor>) => api.put(`/api/v1/competitors/${slug}`, data),
  delete: (slug: string) => api.delete(`/api/v1/competitors/${slug}`),
  benchmark: (slugs: string[]) => api.post('/api/v1/competitors/benchmark', { slugs }),
  history: (slug: string, days?: number) => api.get(`/api/v1/competitors/${slug}/history`, { params: { days } }),
}

// ============================================================
// 舆情相关API
// ============================================================

export interface SentimentDashboard {
  overview: {
    total_mentions: number
    sentiment_distribution: { positive: number; neutral: number; negative: number }
    trending_topics: string[]
  }
  competitors: Array<{
    slug: string
    sentiment_score: number
    mention_count: number
    hot_events: Array<{ title: string; impact: string }>
  }>
  updated_at: string
}

export interface SentimentTrends {
  time_range: string
  data: Array<{
    date: string
    positive: number
    neutral: number
    negative: number
    total: number
  }>
  topics: string[]
}

export const sentimentApi = {
  dashboard: () => api.get<any, SentimentDashboard>('/api/v1/sentiment/dashboard'),
  trends: (days?: number, competitorSlug?: string) =>
    api.get<any, SentimentTrends>('/api/v1/sentiment/trends', { params: { days, competitor_slug: competitorSlug } }),
  analyze: (text: string, competitorSlug?: string) =>
    api.post('/api/v1/sentiment/analyze', { text, competitor_slug: competitorSlug }),
  events: (slug: string, page?: number, pageSize?: number) =>
    api.get(`/api/v1/sentiment/${slug}/events`, { params: { page, page_size: pageSize } }),
}

// ============================================================
// 爬虫相关API
// ============================================================

export const spiderApi = {
  trigger: (data: { competitor_slug: string; task_type: string }) =>
    api.post('/api/v1/spiders/trigger', data),
  getTask: (taskId: string) => api.get(`/api/v1/spiders/${taskId}/status`),
  listTasks: (params?: { competitor_slug?: string; status?: string; page?: number; page_size?: number }) =>
    api.get('/api/v1/spiders/tasks', { params: { ...params, page_size: params?.page_size || 10 } }),
  retry: (taskId: string) => api.post(`/api/v1/spiders/${taskId}/retry`),
  schedule: () => api.get('/api/v1/spiders/schedule'),
}

// ============================================================
// Dashboard相关API
// ============================================================

export interface DashboardCompetitor {
  slug: string
  name: string
  category: string
  monthly_visits: number
  sentiment_score: number
  trend: string
  hot_events: string[]
  company?: string
}

export interface DashboardSentiment {
  total_mentions: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
  trending_topics: string[]
  alert_count: number
}

export interface DashboardSpiders {
  total_tasks: number
  running_tasks: number
  success_tasks_24h: number
  failed_tasks_24h: number
  next_scheduled: string
}

export interface DashboardSystem {
  version: string
  uptime_seconds: number
  api_requests_24h: number
}

export interface DashboardOverview {
  competitors: DashboardCompetitor[]
  sentiment: DashboardSentiment
  spiders: DashboardSpiders
  system: DashboardSystem
  updated_at: string
}

export const dashboardApi = {
  overview: () => api.get<any, DashboardOverview>('/api/v1/dashboard/overview'),
}

// ============================================================
// 支付相关API
// ============================================================

export interface PaymentPlan {
  plan_type: string
  name: string
  price: number
  quota: number
  bonus: number
  total_quota: number
  description: string
}

export const paymentApi = {
  plans: () => api.get<any, PaymentPlan[]>('/api/v1/payment/plans'),
  createOrder: (planType: string, channel: string) =>
    api.post('/api/v1/payment/orders', { plan_type: planType, channel }),
  queryOrder: (orderNo: string) => api.get(`/api/v1/payment/orders/${orderNo}`),
}

// ============================================================
// 审计/管理API
// ============================================================

export const auditApi = {
  logs: (params?: any) => api.get('/api/v1/audit/logs', { params }),
  stats: (days?: number) => api.get('/api/v1/audit/stats', { params: { days } }),
}

export const adminApi = {
  config: () => api.get('/api/v1/admin/config'),
  updateConfig: (data: any) => api.put('/api/v1/admin/config', data),
  backup: () => api.post('/api/v1/admin/backup'),
  health: () => api.get('/api/v1/admin/health'),
}
