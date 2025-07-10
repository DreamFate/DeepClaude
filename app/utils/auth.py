"""认证模块，用于验证 API 密钥"""

from typing import Optional
from datetime import datetime, timedelta, timezone
import os
import hashlib
import jwt

from dotenv import load_dotenv

from fastapi import HTTPException, Header,Request


from app.utils.logger import logger
from app.manager.model_manager import model_manager



async def verify_api_key(authorization: Optional[str] = Header(None)) -> None:
    """验证API密钥

    Args:
        authorization (Optional[str], optional): Authorization header中的API密钥. Defaults to Header(None).

    Raises:
        HTTPException: 当Authorization header缺失或API密钥无效时抛出401错误
    """
    if authorization is None:
        logger.warning("请求缺少Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    api_key = authorization.replace("Bearer ", "").strip()
    if api_key != model_manager.config.get("api_key").setting_value:
        logger.warning("无效的API密钥: %s", api_key)
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    logger.info("API密钥验证通过")

# 加载环境变量
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "a7e2f8d1c6b3e5a9d8c2f5e7b1a3d6c9")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", str(7 * 24 * 60)))

def get_api_key_hash():
    """获取当前系统API密钥的哈希值"""
    # 获取API密钥设置
    api_key = model_manager.config.get("api_key").setting_value
    if not api_key:
        return None
    # 计算哈希值

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

def generate_token(data: dict):
    """生成JWT令牌"""
    to_encode = data.copy()
    # 设置过期时间
    expire = datetime.now(tz=timezone.utc)+ timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    # 添加API密钥哈希
    api_key_hash = get_api_key_hash()
    if api_key_hash:
        to_encode.update({"api_key_hash": api_key_hash})

    # 生成令牌
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 验证API密钥哈希
        if "api_key_hash" in payload:
            current_api_key_hash = get_api_key_hash()
            if current_api_key_hash and payload["api_key_hash"] != current_api_key_hash:
                logger.warning("API密钥已更改，令牌无效")
                return None

        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user(request: Request):
    """从请求中获取当前用户"""
    # 尝试从cookie中获取令牌
    token = request.cookies.get("auth_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="未提供认证令牌"
        )

    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="认证令牌无效或已过期"
        )

    return payload
