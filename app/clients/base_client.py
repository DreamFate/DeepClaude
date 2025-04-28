"""基础客户端类"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List, Tuple

import aiohttp
from aiohttp.client_exceptions import ClientError, ServerTimeoutError

from app.utils.logger import logger

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
        timeout: Optional[aiohttp.ClientTimeout] = None,
        proxy: Optional[str] = None,
    ):
        """初始化基础客户端

        Args:
            api_key: API密钥
            api_url: API地址
            timeout: 请求超时设置,None则使用默认值
            proxy: 代理服务器地址，例如 "http://127.0.0.1:7890"
        """
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.proxy = proxy
        # 创建连接池，可在多次请求中复用
        self.connector = aiohttp.TCPConnector(limit=100, force_close=False)
        self.session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(connector=self.connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            self.session = None

    async def close(self):
        """关闭客户端连接"""
        if self.session:
            await self.session.close()
            self.session = None

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

        params = ["temperature", "top_p", "presence_penalty", "frequency_penalty"]
        for param in params:
            if model_arg.get(param) is not None:
                data[param] = model_arg[param]
        return data

    async def _make_request(
        self, headers: Dict[str, str], data: Dict[str, Any], timeout: Optional[aiohttp.ClientTimeout] = None,
        buffer_size: int = 8192
    ) -> AsyncGenerator[bytes, None]:
        """发送请求并处理响应

        Args:
            headers: 请求头
            data: 请求数据
            timeout: 当前请求的超时设置,None则使用实例默认值
            buffer_size: 读取缓冲区大小，默认8KB

        Yields:
            bytes: 原始响应数据

        Raises:
            aiohttp.ClientError: 客户端错误
            ServerTimeoutError: 服务器超时
            Exception: 其他异常
        """
        request_timeout = timeout or self.timeout
        proxy_url = self._get_proxy_url()

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(connector=self.connector)

            async with self.session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=request_timeout,
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

            # 确保会话被关闭
            if self.session:
                await self.session.close()
                self.session = None

            raise

    async def _make_non_streaming_request(
        self, headers: Dict[str, str], data: Dict[str, Any], timeout: Optional[aiohttp.ClientTimeout] = None
    ) -> bytes:
        """发送非流式请求并处理完整响应

        Args:
            headers: 请求头
            data: 请求数据
            timeout: 当前请求的超时设置,None则使用实例默认值

        Returns:
            bytes: 完整的响应数据

        Raises:
            aiohttp.ClientError: 客户端错误
            ServerTimeoutError: 服务器超时
            Exception: 其他异常
        """
        request_timeout = timeout or self.timeout
        proxy_url = self._get_proxy_url()

        try:
            if not self.session:
                self.session = aiohttp.ClientSession(connector=self.connector)

            async with self.session.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=request_timeout,
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

            # 确保会话被关闭
            if self.session:
                await self.session.close()
                self.session = None

            raise

    @abstractmethod
    async def stream_chat(
        self, messages: List[Dict[str, str]], model: str
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
        self, messages: List[Dict[str, str]], model: str
    ) -> Dict[str, Any]:
        """非流式对话，由子类实现

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数

        Returns:
            Dict[str, Any]: 完整的响应数据
        """
