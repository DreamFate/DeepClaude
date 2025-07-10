# 使用Node.js作为基础镜像
FROM node:20-alpine AS build

# 设置工作目录
WORKDIR /app

# 复制package.json和package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# 构建应用
RUN npm run build

# 生产环境
FROM node:20-alpine AS production

WORKDIR /app

# 从构建阶段复制构建结果
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package*.json ./
COPY --from=build /app/next.config.ts ./

# 只安装生产依赖
RUN npm ci --production

# 暴露端口
EXPOSE 3000

# 启动命令
CMD ["npm", "start"]