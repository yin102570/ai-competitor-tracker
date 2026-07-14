# 阶段七：部署与运维

> 生成时间: 2026-07-11
> 架构: Docker Compose 多容器部署
> 组件: FastAPI + Celery + Redis + Nginx

---

## 1. 部署架构

```
                    ┌─────────┐
                    │ Client  │
                    └────┬────┘
                         │ :80 / :443
                    ┌────┴────┐
                    │  Nginx  │  反向代理 + SSL + WebSocket
                    └────┬────┘
                         │ :8000
                ┌────────┴────────┐
                │   FastAPI       │  REST API + WebSocket
                │   (4 workers)    │
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
    │  SQLite   │ │   Redis   │ │  Celery   │
    │  (数据卷)  │ │ (JWT黑名单 │ │  Worker   │
    └───────────┘ │  消息队列) │ │  (爬虫)   │
                  └───────────┘ └───────────┘
```

---

## 2. 快速启动

### 2.1 前置条件

| 依赖 | 版本 | 说明 |
|------|------|------|
| Docker | >= 24.0 | 容器运行时 |
| Docker Compose | >= 2.20 | V2插件或独立安装 |
| Git | >= 2.30 | 代码管理 |

### 2.2 环境配置

```bash
# 1. 克隆项目
git clone <repo-url> ai-competitor-tracker
cd ai-competitor-tracker

# 2. 复制环境变量模板
cp backend/.env.example .env

# 3. 编辑 .env（必须修改的项）
#    - JWT_SECRET_KEY: 生成随机256位密钥
#    - DEEPSEEK_API_KEY: 填入真实API Key
#    - DATABASE_URL: 生产环境建议PostgreSQL
#    - REDIS_URL: Redis连接地址

# 4. 生成JWT密钥（Linux/Mac）
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2.3 一键启动

```bash
# 开发环境（仅 backend + redis）
bash scripts/start.sh dev

# 生产环境（全部组件）
bash scripts/start.sh prod
```

### 2.4 Docker命令

```bash
# 构建并启动
docker compose -f docker/docker-compose.yml up -d --build

# 查看状态
docker compose -f docker/docker-compose.yml ps

# 查看日志
docker compose -f docker/docker-compose.yml logs -f backend
docker compose -f docker/docker-compose.yml logs -f celery-worker

# 停止
docker compose -f docker/docker-compose.yml down

# 停止并清除数据
docker compose -f docker/docker-compose.yml down -v
```

---

## 3. 运维操作

### 3.1 健康检查

```bash
# 容器级别
docker compose ps

# 应用级别
curl http://localhost/health
curl http://localhost/api/v1/admin/health

# 详细健康（需认证）
curl -H "Authorization: Bearer <token>" http://localhost/api/v1/admin/health
```

### 3.2 日志管理

| 日志位置 | 内容 | 轮转策略 |
|---------|------|---------|
| `logs/app.log` | 应用日志（RotatingFileHandler） | 10MB/文件，最多5个 |
| Docker stdout | 容器标准输出 | `docker compose logs` |
| `nginx-logs/` | Nginx访问/错误日志 | Docker卷 |

```bash
# 实时查看应用日志
docker compose logs -f --tail=100 backend

# 查看Celery任务日志
docker compose logs -f --tail=100 celery-worker

# 查看Nginx日志
docker compose exec nginx cat /var/log/nginx/access.log
```

### 3.3 数据备份

```bash
# 手动触发备份（API）
curl -X POST http://localhost/api/v1/admin/backup \
  -H "Authorization: Bearer <token>"

# 查看备份文件
ls -la backups/

# 恢复备份（SQLite）
docker compose exec backend sqlite3 /app/data/tracker.db < backups/backup_xxx.sql
```

### 3.4 配额重置

配额由Celery Beat自动每日重置（UTC+8 00:00），也可手动触发：

```bash
docker compose exec celery-worker celery -A app.workers.celery_app call app.workers.maintenance_tasks.reset_daily_quota
```

### 3.5 扩缩容

```bash
# 增加worker副本
docker compose up -d --scale celery-worker=3

# 增加backend副本（需Nginx负载均衡）
docker compose up -d --scale backend=2
```

---

## 4. 监控告警

### 4.1 关键指标

| 指标 | 告警阈值 | 监控方式 |
|------|---------|---------|
| API响应时间 | P95 > 500ms | Nginx access_log $request_time |
| 错误率 | > 5% | /api/v1/admin/health |
| 数据库连接 | 耗尽 | Docker healthcheck |
| Redis连接 | 断开 | /api/v1/admin/health components |
| Celery队列积压 | > 100 | `celery -A app.workers.celery_app inspect active` |
| 磁盘空间 | > 80% | `df -h` |

### 4.2 扩展入口

```python
# 未来可接入:
# - Prometheus + Grafana（指标采集和仪表盘）
# - Sentry（异常追踪）
# - ELK Stack（日志聚合）
# - PagerDuty/企业微信（告警通知）
```

---

## 5. 回滚方案

### 5.1 版本回滚

```bash
# 查看镜像历史
docker compose images

# 回滚到上一版本
docker compose down
docker tag ai-competitor-tracker-backend:latest ai-competitor-tracker-backend:rollback
docker compose up -d --build
```

### 5.2 数据库回滚

```bash
# 1. 停止写入
docker compose stop backend celery-worker

# 2. 恢复备份
docker compose exec backend cp /app/backups/backup_xxx.sql /tmp/restore.sql
docker compose exec backend sqlite3 /app/data/tracker.db < /tmp/restore.sql

# 3. 重启
docker compose up -d
```

---

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `docker/backend/Dockerfile` | 多阶段构建（builder→runtime） |
| `docker/docker-compose.yml` | 5服务编排（backend/celery/beat/redis/nginx） |
| `docker/nginx/nginx.conf` | Nginx主配置（安全头/Gzip/日志格式） |
| `docker/nginx/conf.d/default.conf` | 站点配置（反向代理/WebSocket/SSL） |
| `backend/app/workers/__init__.py` | Celery应用配置（Beat定时任务） |
| `backend/app/workers/spider_tasks.py` | 爬虫任务（三引擎调度） |
| `backend/app/workers/maintenance_tasks.py` | 维护任务（配额重置/备份/清理） |
| `scripts/start.sh` | 一键启动脚本（dev/prod模式） |
| `backend/logging.conf` | Python日志配置（轮转/分级） |
| `.dockerignore` | Docker构建排除列表 |

---

## 7. Celery Beat 定时任务

| 任务 | 周期 | 队列 | 说明 |
|------|------|------|------|
| `spider-full-crawl` | 6小时 | spiders | 全量竞品数据抓取 |
| `spider-sentiment-incremental` | 30分钟 | spiders | 舆情增量采集 |
| `reset-daily-quota` | 24小时 | default | 用户配额重置 |
| `daily-backup` | 24小时 | default | 自动数据备份 |
| `cleanup-old-audit-logs` | 1小时 | default | 清理90天前审计日志 |

---

**阶段七部署与运维完成。全部10个部署文件就绪，支持Docker一键部署。**
