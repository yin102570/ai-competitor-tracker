# 第一轮核心功能实现报告

> 生成时间: 2026-07-11
> 范围: DeepSeek舆情分析 + 真实爬虫引擎 + 支付系统 + PostgreSQL就绪
> 状态: 代码实现完成，待环境安装后运行验证

---

## 1. 真实DeepSeek舆情分析引擎

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/core/deepseek_client.py` | DeepSeek API客户端封装（httpx连接复用、JSON结构化输出、错误处理） |
| `app/services/sentiment_engine.py` | AI情感分析引擎（Prompt工程 + 批量分析 + 竞品报告 + 降级方案） |

### 核心能力

| 功能 | Prompt策略 | 输出格式 |
|------|-----------|---------|
| 单条情感分析 | 系统提示词定义6维分析（分数/标签/置信度/主题/关键词/摘要） | JSON结构化 |
| 批量分析 | 一次请求最多20条文本，减少API调用 | JSON数组 |
| 竞品综合报告 | 5维分析（整体态势/优势/痛点/风险/趋势预判） | JSON结构化 |
| 降级方案 | API不可用时自动切换到规则引擎 | 兼容格式 |

### 已替换文件

- `app/services/sentiment_service.py` — `_analyze_text()` 从规则引擎替换为调用 `sentiment_engine.analyze_text()`

### API Key配置

- `.env` 文件已写入真实Key: `DEEPSEEK_API_KEY=sk-676ea...`
- 通过 `settings.deepseek_api_key` 注入，不硬编码

---

## 2. 真实爬虫引擎

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/spiders/__init__.py` | 模块导出 |
| `app/spiders/base_spider.py` | 基类: 重试(3次指数退避) + 限速(令牌桶2/s) + UA轮换(8种) + 代理池 + robots.txt |
| `app/spiders/httpx_spider.py` | httpx引擎: JSON/HTML混合解析, BeautifulSoup4 |
| `app/spiders/playwright_spider.py` | Playwright引擎: stealth反检测, 资源拦截, 交互动作序列 |
| `app/spiders/competitor_spider.py` | 竞品采集器: 6个AI产品配置, 定价解析, Arena排名, DB写入 |
| `app/spiders/sentiment_spider.py` | 舆情采集器: HackerNews/Reddit/Twitter/微博四源 + 去重 + DeepSeek分析 |

### 真实数据源

| 采集类型 | 数据源 | 引擎 |
|---------|--------|------|
| 竞品官网 | chatgpt.com, claude.ai, gemini.google.com 等 | httpx |
| App数据 | iTunes Lookup API | httpx |
| 舆情-HN | HackerNews Algolia API | httpx |
| 舆情-Reddit | Reddit .json API | httpx |
| 舆情-Twitter | Twitter/X搜索页 | Playwright |
| 舆情-微博 | 微博搜索页 | Playwright |
| 定价 | 各竞品/pricing页面 | httpx |
| 模型排名 | LMSYS Chatbot Arena (HuggingFace) | httpx |

### 已替换文件

- `app/services/spider_service.py` — `_simulate_execution()` 从模拟数据替换为调用真实爬虫引擎

---

## 3. 支付系统

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/models/payment.py` | PaymentPlan + PaymentOrder ORM模型, 4档预设套餐 |
| `app/schemas/payment.py` | Pydantic v2 Schema (订单/回调/退款) |
| `app/core/payment_config.py` | 微信v3(RSA-SHA256+AES-256-GCM) + 支付宝(RSA2) 签名工具 |
| `app/services/payment_service.py` | 业务逻辑 (创建订单/回调验签/配额增加/退款) |
| `app/api/v1/endpoints/payment.py` | 6个API端点 |

### 套餐设计

| 套餐 | 价格 | 配额 | 赠送 | 单价 |
|------|------|------|------|------|
| 体验版 | ¥10 | 20次 | — | ¥0.50/次 |
| 标准版 | ¥50 | 100次 | +20次 | ¥0.42/次 |
| 专业版 | ¥200 | 500次 | +100次 | ¥0.33/次 |
| 企业版 | ¥1000 | 3000次 | +1000次 | ¥0.25/次 |

### 安全机制

- 回调接口强制验签（微信v3签名+AES解密 / 支付宝RSA2）
- 配额变更使用 `SELECT ... FOR UPDATE` 行锁
- 回调幂等：已支付订单重复回调不重复加配额

---

## 4. PostgreSQL就绪

### 迁移方式

无需代码改动，仅需修改 `.env`:

```bash
# SQLite（开发环境）
DATABASE_URL=sqlite+aiosqlite:///./data/tracker.db

# PostgreSQL（生产环境）
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tracker
```

### 兼容性验证

- 全部ORM模型使用 `mapped_column`（SQLAlchemy 2.0标准）
- 无SQLite特有SQL（如 `PRAGMA`、`INSERT OR REPLACE`）
- `session.py` 已根据URL自动判断是否为SQLite
- 生产环境需额外安装: `pip install asyncpg`

---

## 5. 新增依赖

| 包 | 版本 | 用途 |
|---|------|------|
| beautifulsoup4 | 4.12.3 | HTML解析 |
| lxml | 5.3.0 | BS4解析后端 |
| cryptography | 44.0.0 | 微信支付RSA/AES |
| asyncpg | (需添加) | PostgreSQL异步驱动 |

---

## 6. 文件变更总览

| 操作 | 文件数 |
|------|--------|
| 新增 | 11 |
| 修改 | 5 |
| 总计 | 16 |

### 新增文件清单

```
app/core/deepseek_client.py          # DeepSeek API客户端
app/services/sentiment_engine.py      # AI情感分析引擎
app/spiders/__init__.py              # 爬虫模块导出
app/spiders/base_spider.py           # 爬虫基类
app/spiders/httpx_spider.py          # httpx引擎
app/spiders/playwright_spider.py     # Playwright引擎
app/spiders/competitor_spider.py     # 竞品采集器
app/spiders/sentiment_spider.py      # 舆情采集器
app/models/payment.py                # 支付ORM模型
app/schemas/payment.py               # 支付Schema
app/core/payment_config.py           # 支付配置/签名
app/services/payment_service.py      # 支付业务逻辑
app/api/v1/endpoints/payment.py      # 支付API路由
```

### 修改文件清单

```
.env                                 # 写入真实DeepSeek API Key
requirements.txt                     # 添加beautifulsoup4/lxml/cryptography
app/services/sentiment_service.py    # _analyze_text接入DeepSeek
app/services/spider_service.py       # _simulate_execution接入真实爬虫
app/models/__init__.py               # 导出Payment模型
app/api/v1/router.py                 # 注册payment路由
app/db/session.py                    # init_db导入payment模型
```

---

## 7. 待用户操作

| 序号 | 操作 | 说明 |
|------|------|------|
| 1 | 安装Python依赖 | `pip install -r requirements.txt` |
| 2 | 安装Playwright浏览器 | `playwright install chromium` |
| 3 | 配置支付密钥 | 在 `.env` 中填入微信/支付宝商户密钥 |
| 4 | （可选）配置PostgreSQL | 修改 `.env` DATABASE_URL + `pip install asyncpg` |

---

## 8. 下一步

第一轮核心后端已全部真实化。接下来进入**第二轮: 前端界面开发**（Vue3 + TypeScript + Tailwind CSS）。
