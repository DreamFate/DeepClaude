"""基础客户端类"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List, Tuple, Callable
import json
import functools

import aiohttp

from aiohttp.client_exceptions import ClientError, ServerTimeoutError

from app.utils.logger import logger

def handle_client_errors(operation_name: str):
    """处理客户端错误的装饰器

    Args:
        operation_name: 操作名称，用于日志记录
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except ServerTimeoutError as e:
                error_msg = f"{operation_name}请求超时: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e
            except ClientError as e:
                error_msg = f"{operation_name}客户端错误: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e
            except json.JSONDecodeError as e:
                error_msg = f"JSON 解析错误: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e
            except Exception as e:
                error_msg = f"{operation_name}请求处理异常: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e
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

    @handle_client_errors(operation_name="流式请求服务器")
    async def _make_request(
        self,
        headers: Dict[str, str],
        data: Dict[str, Any],
        buffer_size: int = 8192,
    ) -> AsyncGenerator[bytes, None]:
        """发送请求并处理响应

        Args:
            headers: 请求头
            data: 请求数据
            buffer_size: 读取缓冲区大小，默认8KB

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

                    # 流式读取响应内容
                    async for chunk in response.content.iter_chunked(buffer_size):
                        if chunk:  # 过滤空chunks
                            yield chunk

        except Exception as e:
            # 统一异常处理
            error_type = "请求超时" if isinstance(e, ServerTimeoutError) else \
                         "客户端错误" if isinstance(e, ClientError) else \
                         "请求处理异常"
            error_msg = f"{error_type}: {str(e)}"
            logger.error(error_msg)
            raise

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

        try:
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

        except Exception as e:
            # 统一异常处理
            error_type = "请求超时" if isinstance(e, ServerTimeoutError) else \
                         "客户端错误" if isinstance(e, ClientError) else \
                         "请求处理异常"
            error_msg = f"{error_type}: {str(e)}"
            logger.error(error_msg)

            raise

    async def original_chat(
        self,
        headers: Dict[str, Any],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """原始非流式对话

        Args:
            headers: 请求头
            data: 请求数据

        Returns:
            Dict[str, Any]: OpenAI 格式的完整响应
        """
        logger.debug("开始原始非流式对话: ")
        # 使用非流式请求方法获取完整响应
        try:
            response_bytes = await self._make_non_streaming_request(headers, data)

            # 解析响应
            response = json.loads(response_bytes.decode("utf-8"))

            return response
        except Exception as e:
            logger.error("原始非流式对话时出错: %s", e)
            raise ValueError("原始非流式对话时出错") from e

    async def original_stream_chat(
        self,
        headers: Dict[str, Any],
        data: Dict[str, Any],
    ) -> AsyncGenerator[tuple[str, str], None]:
        """原始流式对话

        Args:
            headers: 请求头
            data: 请求数据

        Yields:
            tuple[str, str]: (内容类型, 内容)
                内容类型: "answer"
                内容: 实际的文本内容
        """

        try:
            async for chunk in self._make_request(headers, data):
                chunk_str = chunk.decode("utf-8")
                if not chunk_str.strip():
                    continue

                yield chunk_str
        except Exception as e:
            # 致命错误，记录并抛出
            logger.error("原生流式对话过程中发生错误: %s", e)
            raise ValueError(f"原生流式对话过程中发生错误: {e}") from e


    @abstractmethod
    async def stream_chat(
        self, messages: List[Dict[str, str]], model: str, model_arg: Dict[str, Any] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """流式对话，由子类实现

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数

        Yields:
            tuple[str, str]: (内容类型, 内容)
        """

    @abstractmethod
    async def chat(
        self, messages: List[Dict[str, str]], model: str, model_arg: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """非流式对话，由子类实现

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数

        Returns:
            Dict[str, Any]: 完整的响应数据
        """
