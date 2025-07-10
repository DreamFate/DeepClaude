# 多阶段构建 - 前端构建阶段
FROM node:20-alpine AS frontend-builder

# 设置工作目录
WORKDIR /app

# 复制前端代码
COPY ./admin-ui/package*.json ./
RUN npm ci
COPY ./admin-ui ./
RUN npm run build

# 后端阶段
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir \
    aiohttp==3.11.11 \
    colorlog==6.9.0 \
    fastapi==0.115.8 \
    python-dotenv==1.0.1 \
    pyyaml==6.0.2 \
    tiktoken==0.8.0 \
    "uvicorn[standard]" \
    pyjwt==2.8.0

# 复制后端代码
COPY ./app ./app

# 安装 Nginx
RUN apt-get update && apt-get install -y nginx

# 复制前端构建结果到Nginx目录
COPY --from=frontend-builder /app/.next /var/www/html/.next
COPY --from=frontend-builder /app/public /var/www/html/public

# 创建Nginx配置
RUN echo 'server {\n\
    listen 80;\n\
    server_name _;\n\
    \n\
    location / {\n\
        root /var/www/html;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    \n\
    location /api/ {\n\
        proxy_pass http://localhost:8000/;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
}' > /etc/nginx/sites-available/default

# 创建启动脚本
RUN echo '#!/bin/bash\n\
# 启动后端服务\n\
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &\n\
# 启动Nginx\n\
nginx -g "daemon off;"' > /start.sh && chmod +x /start.sh

# 暴露端口
EXPOSE 80 8000

# 启动命令
CMD ["/start.sh"]