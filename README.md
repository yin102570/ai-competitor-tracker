# AI竞品追踪 - 智能对标分析系统

基于 FastAPI + Vue3 + Celery 构建的AI竞品情报平台。集成多源爬虫、DeepSeek 大模型情感分析、实时舆情监控与可视化看板。

## 功能特性

### 核心功能
- **竞品管理**：支持竞品信息的增删改查、分类管理、活跃状态监控
- **舆情监控**：实时采集多平台舆情数据，AI情感分析（正面/中性/负面）
- **爬虫任务**：支持多种爬虫类型（Playwright/Httpx），定时调度，任务状态追踪
- **数据看板**：综合统计、趋势图表、竞品对比、热门话题可视化
- **用户系统**：注册登录、配额管理、支付充值、权限控制
- **审计日志**：完整操作记录，支持查询追溯

### 技术亮点
- **多源爬虫**：支持静态页面（Httpx）和动态渲染（Playwright）
- **AI分析**：集成 DeepSeek 大模型进行深度情感分析
- **异步架构**：FastAPI + SQLAlchemy 2.0 异步 ORM
- **任务队列**：Celery + Redis 实现分布式任务调度
- **现代化前端**：Vue3 + TypeScript + Tailwind CSS + ECharts

## 技术栈

### 后端
- **框架**：FastAPI
- **ORM**：SQLAlchemy 2.0 (Async)
- **任务队列**：Celery + Redis
- **数据库**：SQLite / PostgreSQL
- **AI**：DeepSeek API
- **爬虫**：Playwright + Httpx
- **测试**：Pytest

### 前端
- **框架**：Vue 3 + TypeScript
- **构建工具**：Vite
- **状态管理**：Pinia
- **UI样式**：Tailwind CSS
- **图表**：ECharts 5
- **HTTP客户端**：Axios

### 部署
- **容器化**：Docker + Docker Compose
- **反向代理**：Nginx
- **支持平台**：Windows / Linux

## 项目结构

```
ai-competitor-tracker/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/v1/         # API 端点
│   │   ├── core/           # 核心配置、安全、依赖
│   │   ├── db/             # 数据库配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   ├── spiders/        # 爬虫模块
│   │   └── workers/        # Celery 任务
│   ├── tests/              # 测试用例
│   └── requirements.txt    # Python 依赖
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── api/           # API 接口
│   │   ├── components/    # 通用组件
│   │   ├── layouts/       # 布局组件
│   │   ├── router/        # 路由配置
│   │   ├── stores/        # 状态管理
│   │   ├── styles/        # 全局样式
│   │   └── views/         # 页面视图
│   └── package.json       # Node 依赖
├── docker/                 # Docker 配置
│   ├── docker-compose.yml
│   ├── backend/
│   ├── frontend/
│   └── nginx/
└── scripts/               # 启动脚本
```

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- Redis
- (可选) Docker

### 本地开发

#### 1. 克隆项目
```bash
git clone https://github.com/yin102570/ai-competitor-tracker.git
cd ai-competitor-tracker
```

#### 2. 后端启动
```bash
cd backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 配置数据库、Redis、DeepSeek API Key

# 启动 Redis（如本地未运行）
# Windows: 使用 redis 目录下的 redis-server.exe
# Linux: redis-server

# 启动 Celery Worker
celery -A app.workers worker --loglevel=info

# 启动 Celery Beat（定时任务）
celery -A app.workers beat --loglevel=info

# 启动 FastAPI 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. 前端启动
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173 查看应用

### Docker 部署

```bash
# 一键启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### Windows 快速启动

项目提供了多个批处理脚本：
- `一键启动所有服务.bat` - 启动完整服务栈
- `快速开发启动.bat` - 开发环境快速启动
- `局域网共享部署.bat` - 局域网访问部署
- `Docker公网部署.bat` - 公网 Docker 部署

## API 文档

启动后端服务后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 主要 API 端点

- `/api/v1/auth` - 认证相关（登录、注册）
- `/api/v1/competitors` - 竞品管理
- `/api/v1/sentiment` - 舆情数据
- `/api/v1/spiders` - 爬虫任务
- `/api/v1/dashboard` - 看板数据
- `/api/v1/users` - 用户管理
- `/api/v1/payment` - 支付相关
- `/api/v1/admin` - 管理员功能
- `/api/v1/audit` - 审计日志

## 配置说明

### 环境变量 (.env)

```bash
# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/tracker.db

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# DeepSeek API
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 应用配置
APP_NAME=AI竞品追踪
DEBUG=true
```

## 测试

```bash
cd backend

# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_auth.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

## 开发计划

- [x] 基础架构搭建
- [x] 用户认证系统
- [x] 竞品管理模块
- [x] 爬虫任务系统
- [x] 舆情分析引擎
- [x] 数据看板
- [x] 支付充值系统
- [x] 审计日志
- [x] Docker 部署
- [ ] 多语言支持
- [ ] 移动端适配
- [ ] 更多数据源接入

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过 GitHub Issues 反馈。
