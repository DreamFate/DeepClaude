# 使用 Python 3.11 slim 版本作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 创建数据目录
RUN mkdir -p /app/data

# 设置数据卷
VOLUME /app/data

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

# 复制项目文件
COPY ./app ./app

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
