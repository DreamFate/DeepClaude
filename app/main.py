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

from typing import List
import logging
import atexit
import io
import json
from fastapi.responses import StreamingResponse

from fastapi import Depends, FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.utils.auth import (
    verify_api_key, generate_token, verify_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.utils.logger import logger
from app.utils.error import ClientAPIError,DBManagerError
from app.db.db_manager import db_manager
from app.manager.model_manager import model_manager
from app.db.db_config import ProviderConfig,ModelConfig,CompositeModelConfig,SystemSetting



# 版本信息
VERSION = "v1.0.1"

# 显示当前的版本
logger.info("当前版本: %s", VERSION)

db_manager.open_db_manager()

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

# # 静态文件目录
# static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
# # 挂载静态文件目录
# app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
    - stream: 是否使用流式输出（可选，默认为 True）
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
    except ValueError as e:
        # 处理参数验证错误
        logger.error("参数验证错误: %s", str(e))
        return JSONResponse(
            status_code=400,
            content={
                "error": str(e),
                "detail": "参数错误",
            }
        )
    except ClientAPIError as e:
        # 处理已知的客户端错误
        logger.error("处理请求时发生客户端错误: %s", str(e))
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": e.error,
                "detail": e.detail,
            }
        )
    except Exception as e:
        # 处理未预期的错误
        logger.exception("处理请求时发生未预期错误")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "detail": "其他错误",
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
            return JSONResponse(
                status_code=400,
                content={
                    "error": "缺少请求chat_id",
                    "detail": "其他错误",
                }
            )

        success = model_manager.cancel_request(chat_id)

        if success:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": f"请求 {chat_id} 已取消",
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"未找到请求 {chat_id} 或已完成",
                }
            )
    except Exception as e:
        logger.exception("取消请求时发生错误")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "detail": "其他错误",
            }
        )


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
        logger.exception("获取模型列表时发生错误")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "detail": "其他错误",
            }
        )


@app.post("/auth/verify")
async def verify_key(request: Request, response: Response):
    """验证API密钥"""
    try:
        body = await request.json()
        api_key = body.get("apiKey")
        if not api_key:
            raise HTTPException(status_code=400, detail="API密钥不能为空")

        valid_api_key = model_manager.config.get("api_key").setting_value
        if api_key != valid_api_key:
            raise HTTPException(status_code=401, detail="API密钥不正确")

        # 生成令牌
        token_data = {"sub": "user", "api_key": api_key}
        token = generate_token(token_data)

        # 设置cookie
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=False,  # 在生产环境中设置为True
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES
        )

        return {"success": True}
    except Exception as e:
        logger.exception("验证API密钥时发生错误%s" ,str(e))
        return {"success": False}


@app.get("/auth/status")
async def check_auth_status(request: Request):
    """检查认证状态"""
    try:
        # 从cookie中获取令牌
        token = request.cookies.get("auth_token")

        if not token:
            return {"authenticated": False}

        # 验证令牌
        payload = verify_token(token)
        if not payload:
            return {"authenticated": False}

        return {"authenticated": True}

    except Exception as e:
        logger.exception("检查认证状态时发生错误%s" ,str(e))
        return {"authenticated": False}


@app.post("/auth/logout")
async def logout(response: Response):
    """登出并清除认证令牌"""
    try:
        # 清除认证令牌cookie
        response.delete_cookie(
            key="auth_token",
            httponly=True,
            secure=False,  # 在生产环境中设置为True
            samesite="lax"
        )
        return {"success": True}
    except Exception as e:
        logger.exception("登出时发生错误%s" ,str(e))
        return {"success": False}

@app.get("/providers/get_all_providers", dependencies=[Depends(get_current_user)])
async def get_all_providers():
    """获取所有供应商配置"""
    return model_manager.db_manager.get_all_providers()

@app.get("/providers/get_all_valid_provider", dependencies=[Depends(get_current_user)])
async def get_all_valid_provider():
    """获取所有有效的供应商配置"""
    providers = model_manager.db_manager.get_all_providers(is_valid=True)
    result = []
    for provider in providers:
        result.append({
            "id": provider.id,
            "provider_name": provider.provider_name
        })
    return result

@app.get("/providers/get_provider_for_id/{provider_id}", dependencies=[Depends(get_current_user)])
async def get_provider_for_id(provider_id: int):
    """获取指定供应商配置"""
    return model_manager.db_manager.get_provider(provider_id=provider_id)

@app.get("/providers/get_provider_for_name/{provider_name}", dependencies=[Depends(get_current_user)])
async def get_provider_for_name(provider_name: str):
    """获取指定供应商配置"""
    return model_manager.db_manager.get_provider(provider_name=provider_name)

@app.post("/providers/save_provider", dependencies=[Depends(get_current_user)])
async def save_provider(provider: ProviderConfig):
    """保存供应商配置"""
    try:
        return model_manager.db_manager.save_provider(provider)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.delete("/providers/delete_provider/{provider_id}", dependencies=[Depends(get_current_user)])
async def delete_provider(provider_id: int):
    """删除供应商配置"""
    try:
        return model_manager.db_manager.delete_provider(provider_id)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.get("/models/get_all_models", dependencies=[Depends(get_current_user)])
async def get_all_models():
    """获取所有模型配置"""
    return model_manager.db_manager.get_all_models()

@app.get("/models/get_all_models/{model_type}", dependencies=[Depends(get_current_user)])
async def get_all_models_by_type(model_type: str):
    """获取指定类型的所有模型配置"""
    return model_manager.db_manager.get_all_models(model_type=model_type)

@app.get("/models/get_all_valid_models", dependencies=[Depends(get_current_user)])
async def get_all_valid_models():
    """获取所有有效的模型配置"""
    models = model_manager.db_manager.get_all_models(is_valid=True)
    result = {"reasoner": [], "general": []}
    for model in models:
        info = {"id": model.id, "model_name": model.model_name}
        if model.model_type == "reasoner":
            result["reasoner"].append(info)
        elif model.model_type == "general":
            result["general"].append(info)
    return result

@app.get("/models/get_model_for_id/{model_id}", dependencies=[Depends(get_current_user)])
async def get_model_for_id(model_id: int):
    """获取指定模型配置"""
    return model_manager.db_manager.get_model(models_id=model_id)

@app.get("/models/get_model_for_name/{model_name}", dependencies=[Depends(get_current_user)])
async def get_model_for_name(model_name: str):
    """获取指定模型配置"""
    return model_manager.db_manager.get_model(model_name=model_name)

@app.post("/models/save_model", dependencies=[Depends(get_current_user)])
async def save_model(model: ModelConfig):
    """保存模型配置"""
    try:
        return model_manager.db_manager.save_model(model)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.delete("/models/delete_model/{model_id}", dependencies=[Depends(get_current_user)])
async def delete_model(model_id: int):
    """删除模型配置"""
    try:
        return model_manager.db_manager.delete_model(model_id)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.get("/composite_models/get_all_composite_models", dependencies=[Depends(get_current_user)])
async def get_all_composite_models():
    """获取所有组合模型配置"""
    return model_manager.db_manager.get_all_composite_models()

@app.get("/composite_models/get_composite_model_for_id/{composite_model_id}", dependencies=[Depends(get_current_user)])
async def get_composite_model_for_id(composite_model_id: int):
    """获取指定组合模型配置"""
    return model_manager.db_manager.get_composite_model(composite_models_id=composite_model_id)

@app.get("/composite_models/get_composite_model_for_name/{composite_model_name}", dependencies=[Depends(get_current_user)])
async def get_composite_model_for_name(composite_model_name: str):
    """获取指定组合模型配置"""
    return model_manager.db_manager.get_composite_model(model_name=composite_model_name)

@app.post("/composite_models/save_composite_model", dependencies=[Depends(get_current_user)])
async def save_composite_model(composite_model: CompositeModelConfig):
    """保存组合模型配置"""
    try:
        return model_manager.db_manager.save_composite_model(composite_model)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.delete("/composite_models/delete_composite_model/{composite_model_id}", dependencies=[Depends(get_current_user)])
async def delete_composite_model(composite_model_id: int):
    """删除组合模型配置"""
    try:
        return model_manager.db_manager.delete_composite_model(composite_model_id)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.get("/system_settings/get_all_settings", dependencies=[Depends(get_current_user)])
async def get_all_settings():
    """获取所有系统设置"""
    settings = model_manager.db_manager.get_all_settings()
    return {
        "api_key": settings.get("api_key").setting_value,
        "proxy_address": settings.get("proxy_address").setting_value,
        "log_level": settings.get("log_level").setting_value,
        "tcp_connector_limit": settings.get("tcp_connector_limit").setting_value,
        "tcp_connector_limit_per_host": settings.get("tcp_connector_limit_per_host").setting_value,
        "tcp_keepalive_timeout": settings.get("tcp_keepalive_timeout").setting_value
    }

@app.get("/system_settings/get_setting_for_key/{setting_key}", dependencies=[Depends(get_current_user)])
async def get_setting_for_key(setting_key: str):
    """获取指定系统设置"""
    return model_manager.db_manager.get_setting(setting_key)

@app.post("/system_settings/save_setting", dependencies=[Depends(get_current_user)])
async def save_setting(setting: List[SystemSetting]):
    """保存系统设置"""
    try:
        return model_manager.db_manager.save_setting(setting)
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.post("/system_settings/save_api_key", dependencies=[Depends(get_current_user)])
async def save_api_key(setting: List[SystemSetting], response: Response):
    """保存api_key"""
    try:
        if setting[0].setting_key != "api_key":
            raise DBManagerError("不是api_key设置")
        setting[0].setting_type = "str"
        model_manager.db_manager.save_setting(setting)
        model_manager.update_config()
        # 清除认证令牌cookie
        response.delete_cookie(
            key="auth_token",
            httponly=True,
            secure=False,  # 在生产环境中设置为True
            samesite="lax"
        )
        return {"success": True}


    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.post("/system_settings/set_log_level", dependencies=[Depends(get_current_user)])
async def set_log_level(setting: List[SystemSetting]):
    """设置日志级别"""
    try:
        if setting[0].setting_key != "log_level":
            raise DBManagerError("不是日志级别设置")
        if setting[0].setting_value not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise DBManagerError("不是日志级别设置")
        setting[0].setting_type = "str"
        model_manager.db_manager.save_setting(setting)
        model_manager.set_log_level()
        return JSONResponse(
            status_code = 200,
            content = {
                "message": "日志级别设置成功"
            }
        )
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.post("/system_settings/set_tcp_connector", dependencies=[Depends(get_current_user)])
async def set_tcp_connector(setting: List[SystemSetting]):
    """设置tcp连接池参数"""
    try:
        lists = []
        for item in setting:
            if item.setting_key in [
                "tcp_connector_limit",
                "tcp_connector_limit_per_host",
                "tcp_keepalive_timeout"
            ]:
                lists.append(item)
        if len(lists) != 3:
            raise DBManagerError("不是tcp连接池参数设置")
        model_manager.db_manager.save_setting(lists)
        model_manager.set_tcp_connector()
        return JSONResponse(
            status_code = 200,
            content = {
                "message": "tcp连接池参数设置成功"
            }
        )
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.get("/system_settings/export_config", dependencies=[Depends(get_current_user)])
async def export_config():
    """导出配置"""
    try:
        config_data = model_manager.db_manager.export_config()
        file_like = io.BytesIO(
            json.dumps(config_data, ensure_ascii=False, indent=2).encode("utf-8")
        )
        return StreamingResponse(
            file_like,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=config.json"}
        )
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )

@app.post("/system_settings/import_config", dependencies=[Depends(get_current_user)])
async def import_config(request: Request):
    """导入配置"""
    try:
        body = await request.json()
        config_data = body.get("config")
        if not config_data:
            raise HTTPException(status_code=400, detail="配置数据不能为空")
        model_manager.db_manager.import_config(config_data)
        model_manager.update_config()
        model_manager.set_log_level()
        model_manager.set_tcp_connector()
        return {"message": "配置导入成功"}
    except DBManagerError as e:
        return JSONResponse(
            status_code = e.status_code,
            content = {
                "message": e.message
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content = {
                "message": "意料之外错误,请联系管理员 " + str(e)
            }
        )
