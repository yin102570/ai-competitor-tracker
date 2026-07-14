# ============================================================
# 前端 Dockerfile - 多阶段构建
# ============================================================

# 阶段1: 构建
FROM node:22-alpine AS builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline
COPY frontend/ .
RUN npm run build

# 阶段2: 运行时
FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY docker/nginx/conf.d/frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
