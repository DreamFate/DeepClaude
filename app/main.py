"""
DeepClaude API 主模块

这个模块是DeepClaude应用的入口点，负责初始化FastAPI应用、
配置中间件、设置路由和管理应用生命周期。

主要功能：
- 初始化数据库连接池和模型管理器
- 配置CORS中间件和日志级别
- 提供API端点用于模型调用和配置管理
- 管理应用的启动和关闭过程
"""
import os
import logging
import atexit

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from aiohttp.client_exceptions import ClientError

from app.utils.auth import verify_api_key
from app.utils.logger import logger
from app.db.db_manager import db_manager
from app.manager.model_manager import model_manager



# 版本信息
VERSION = "v1.0.1"

# 显示当前的版本
logger.info("当前版本: %s", VERSION)

db_manager.open_db_manager()
#model_manager.test_data()

logger.setLevel(getattr(logging, model_manager.config.get("log_level").setting_value, logging.INFO))

# 创建 FastAPI 应用
app = FastAPI(title="DeepClaude API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 在程序退出时关闭数据库连接池
atexit.register(db_manager.close_db_manager)

# 验证日志级别
logger.debug("当前日志级别为 DEBUG")
logger.info("开始请求")

@app.get("/", dependencies=[Depends(verify_api_key)])
async def root():
    """API根路径访问处理

    返回API欢迎信息和版本号
    """
    logger.info("访问了根路径")
    return {"message": "Welcome to DeepClaude API", "version": VERSION}


@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request):
    """处理聊天完成请求，使用 ModelManager 进行处理

    请求体格式应与 OpenAI API 保持一致，包含：
    - messages: 消息列表
    - model: 模型名称（必需）
    - model_type: 模型类型(可选,为AiPotluck准备)
    - stream: 是否使用流式输出（可选，默认为 True)
    - temperature: 随机性 (可选)
    - top_p: top_p (可选)
    - presence_penalty: 话题新鲜度（可选）
    - frequency_penalty: 频率惩罚度（可选）
    """
    try:
        # 获取请求体
        body = await request.json()
        # 使用 ModelManager 处理请求，ModelManager 将处理不同的模型组合
        response = await model_manager.process_request(body)
        return response
    except ClientError as e:
        # 处理已知的客户端错误

        error_message = str(e)
        error_code = e.status_code if hasattr(e, 'status_code') else 500
        error_type = e.error_type if hasattr(e, 'error_type') else "其他错误"
        error_info={
            "error": {
                "message": error_message,
                "type": error_type,
                "code": error_code
            }
        }

        # 处理常见的错误信息
        if "Input length" in error_message:
            error_info["message_details"] = "输入的上下文内容过长，超过了模型的最大处理长度限制。请减少输入内容或分段处理。"
        elif "InvalidParameter" in error_message:
            error_info["message_details"] = "请求参数无效，请检查输入内容。"
        elif "BadRequest" in error_message:
            error_info["message_details"] = "请求格式错误，请检查输入内容。"

        logger.error("客户端错误: %s - %s", error_type, str(e))
        return JSONResponse(
            status_code=error_code,
            content={
                "error": {
                    "message": error_info,
                    "type": error_type,
                    "code": error_code
                }
            }
        )
    except Exception as e:
        # 处理未预期的错误
        logger.error("处理请求时发生未预期错误: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "其他错误",
                    "code": 500
                }
            }
        )

@app.post("/v1/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_request(request: Request):
    """取消正在进行的请求

    请求体应包含：
    - request_id: 要取消的请求ID
    """
    try:
        body = await request.json()
        chat_id = body.get("chat_id")

        if not chat_id:
            return {"status": "error", "message": "缺少请求chat_id"}

        success = model_manager.cancel_request(chat_id)

        if success:
            return {"status": "success", "message": f"请求 {chat_id} 已取消"}
        else:
            return {"status": "error", "message": f"未找到请求 {chat_id} 或已完成"}
    except Exception as e:
        logger.error("取消请求时发生错误: %s", e)
        return {"status": "error", "message": str(e)}


@app.get("/v1/models", dependencies=[Depends(verify_api_key)])
async def list_models():
    """获取可用模型列表

    使用 ModelManager 获取从配置文件中读取的模型列表
    返回格式遵循 OpenAI API 标准
    """
    try:
        models = model_manager.get_model_list()
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error("获取模型列表时发生错误: %s", e)
        return {"error": str(e)}

@app.get("/config")
async def config_page():
    """配置页面

    返回配置页面的 HTML
    """
    try:
        html_path = os.path.join(static_dir, "index.html")
        if not os.path.exists(html_path):
            logger.error("HTML 文件不存在: %s", html_path)
            return {"error": "配置页面文件不存在"}
        return FileResponse(html_path)
    except Exception as e:
        logger.error("返回配置页面时发生错误: %s", e)
        return {"error": str(e)}

@app.get("/v1/config", dependencies=[Depends(verify_api_key)])
async def get_config():
    """获取模型配置

    返回当前的模型配置数据
"""
    try:
        # 使用 ModelManager 获取配置
        config = model_manager.get_config()
        return config
    except Exception as e:
        logger.error("获取配置时发生错误: %s", e)
        return {"error": str(e)}

@app.post("/v1/config", dependencies=[Depends(verify_api_key)])
async def update_config(request: Request):
    """更新模型配置

    接收并保存新的模型配置数据
    """
    try:
        # 获取请求体
        body = await request.json()

        # 使用 ModelManager 更新配置
        model_manager.update_config(body)

        return {"message": "配置已更新"}
    except Exception as e:
        logger.error("更新配置时发生错误: %s", e)
        return {"error": str(e)}
