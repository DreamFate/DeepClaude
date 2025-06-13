"""基础客户端类"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List, Tuple, Callable
import json
import functools
import asyncio
import inspect
import aiohttp
from app.chatcompletion.openai_compatible import (
    OpenAICompletion,
    OpenAIStreamCompletion,
)

from aiohttp.client_exceptions import ClientError, ServerTimeoutError

from app.utils.logger import logger

def handle_all_client_errors(operation_name, e):
    """处理客户端错误"""
    if isinstance(e, ServerTimeoutError):
        error_msg = f"{operation_name}请求超时: {str(e)}"
    elif isinstance(e, ClientError):
        error_msg = f"{operation_name}客户端错误: {str(e)}"
    elif isinstance(e, json.JSONDecodeError):
        error_msg = f"JSON 解析错误: {str(e)}"
    else:
        error_msg = f"{operation_name}请求处理异常: {str(e)}"
    logger.error(error_msg)
    raise ClientError(error_msg) from e

def handle_client_errors(operation_name: str):
    """处理客户端错误的装饰器

    Args:
        operation_name: 操作名称，用于日志记录
    """
    def decorator(func: Callable):
        if inspect.isasyncgenfunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                except Exception as e:
                    handle_all_client_errors(operation_name, e)
            return wrapper
        else:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    handle_all_client_errors(operation_name, e)
            return wrapper
    return decorator

class BaseClient(ABC):
    """基础客户端类"""

    # 默认超时设置(秒)
    # total: 总超时时间
    # connect: 连接超时时间
    # sock_read: 读取超时时间
    # sock_connect: 套接字连接超时时间
    DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=600, connect=10, sock_read=500, sock_connect=10)

    def __init__(
        self,
        api_key: str,
        api_url: str,
        connector: aiohttp.TCPConnector,
        timeout: Optional[aiohttp.ClientTimeout] = None,
        proxy: Optional[str] = None,
    ):
        """初始化基础客户端

        Args:
            api_key: API密钥
            api_url: API地址
            connector: TCP连接器
            timeout: 请求超时设置,None则使用默认值
            proxy: 代理服务器地址，例如 "http://127.0.0.1:7890"
        """
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.proxy = proxy
        self.connector = connector

    def _get_proxy_url(self) -> Optional[str]:
        """获取格式化的代理URL

        Returns:
            Optional[str]: 格式化后的代理URL或None
        """
        if not self.proxy:
            return None
        if not self.proxy.startswith(('http://', 'https://', 'socks://', 'socks5://')):
            proxy_url = f"http://{self.proxy}"
        else:
            proxy_url = self.proxy
        logger.info("使用代理: %s", proxy_url)
        return proxy_url

    def _add_model_params(self, data, model_arg):
        """添加模型参数到请求数据中"""
        if model_arg is None:
            return data

        # 将model_arg中的所有键值对添加到data中
        for key, value in model_arg.items():
            if value is not None:
                data[key] = value

        return data

    def parse_json_line(self, line):
        """解析 JSON 行"""
        line = line.strip()
        if not line:
            return None

        if line.startswith("data: "):
            json_str = line[len("data: "):]
            if json_str == "[DONE]":
                return json_str
        else:
            json_str = line
        try:
            json_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug("JSON 解析错误: %s", e)
            return None
        return json_data

    async def _make_request(
        self,
        headers: Dict[str, str],
        data: Dict[str, Any],
        buffer_size: int = 8192,
        cancel_flag: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[bytes, None]:
        """发送请求并处理响应

        Args:
            headers: 请求头
            data: 请求数据
            buffer_size: 读取缓冲区大小，默认8KB
            cancel_flag: 取消标志，用于取消请求

        Yields:
            bytes: 原始响应数据

        Raises:
            aiohttp.ClientError: 客户端错误
            ServerTimeoutError: 服务器超时
            asyncio.CancelledError: 请求被取消
            Exception: 其他异常
        """
        proxy_url = self._get_proxy_url()

        try:
            async with aiohttp.ClientSession(connector=self.connector, connector_owner=False) as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout,
                    proxy=proxy_url
                ) as response:
                    # 检查响应状态
                    if not response.ok:
                        error_text = await response.text()
                        error_msg = f"API 请求失败: 状态码 {response.status}, 错误信息: {error_text}"
                        logger.error(error_msg)
                        raise ClientError(error_msg)

                    # 流式读取响应内容
                    async for chunk in response.content.iter_chunked(buffer_size):
                        if cancel_flag and cancel_flag.is_set():
                            logger.debug("请求被用户取消，正在关闭连接")
                            response.release()
                            break
                        if chunk:  # 过滤空chunks
                            yield chunk
        except Exception as e:
            handle_all_client_errors("流式请求", e)

    @handle_client_errors(operation_name="非流式请求")
    async def _make_non_streaming_request(
        self,
        headers: Dict[str, str],
        data: Dict[str, Any],
    ) -> bytes:
        """发送非流式请求并处理完整响应

        Args:
            headers: 请求头
            data: 请求数据

        Returns:
            bytes: 完整的响应数据

        Raises:
            aiohttp.ClientError: 客户端错误
            ServerTimeoutError: 服务器超时
            Exception: 其他异常
        """
        proxy_url = self._get_proxy_url()

        async with aiohttp.ClientSession(connector=self.connector) as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=self.timeout,
                proxy=proxy_url
            ) as response:
                # 检查响应状态
                if not response.ok:
                    error_text = await response.text()
                    error_msg = f"API 请求失败: 状态码 {response.status}, 错误信息: {error_text}"
                    logger.error(error_msg)
                    raise ClientError(error_msg)

                # 读取完整响应内容
                return await response.read()

    @handle_client_errors(operation_name="原始非流式对话")
    async def original_chat(
        self,
        headers: Dict[str, str],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """原始非流式对话

        Args:
            headers: 请求头
            data: 请求体

        Returns:
            Dict[str, Any]: 完整响应
        """

        response_bytes = await self._make_non_streaming_request(headers, data)

        response = json.loads(response_bytes.decode("utf-8"))

        return response

    @handle_client_errors(operation_name="原始流式对话")
    async def original_stream_chat(
        self,
        headers: Dict[str, str],
        data: Dict[str, Any],
        cancel_flag: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[str, None]:
        """原始流式对话

        Args:
            headers: 请求头
            data: 请求体
            cancel_flag: 取消标志，用于取消请求

        Yields:
            str: (内容类型, 内容)
        """
        async for chunk in self._make_request(headers, data,cancel_flag=cancel_flag):
            chunk_str = chunk.decode("utf-8")
            if not chunk_str.strip():
                continue

            yield chunk_str

    @abstractmethod
    def format_data(
        self,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        model_arg: Dict[str, Any],
        stream: bool,
        other_params: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """格式化数据"""


    @abstractmethod
    async def stream_chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any],
        other_params: Dict[str, Any] = None,
        cancel_flag: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[OpenAIStreamCompletion, None]:
        """流式对话，由子类实现

        Args:
            chat_id: 对话ID
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数
            other_params: 其他参数
            cancel_flag: 取消标志，用于取消请求

        Yields:
            tuple[str, str]: (内容类型, 内容)
        """

    @abstractmethod
    async def chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any],
        other_params: Dict[str, Any] = None
    ) -> OpenAICompletion:
        """非流式对话，由子类实现

        Args:
            chat_id: 对话ID
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数
            other_params: 其他参数

        Returns:
            Dict[str, Any]: 完整的响应数据
        """
