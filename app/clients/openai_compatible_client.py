"""OpenAI 兼容格式的客户端类,用于处理符合 OpenAI API 格式的服务"""

import json
import time
from typing import AsyncGenerator, Optional, Dict, Any, List,Tuple

import aiohttp
from aiohttp.client_exceptions import ClientError

from app.clients.base_client import BaseClient
from app.utils.logger import logger
from app.chatcompletion.openai_compatible import (
    OpenAICompletion,
    OpenAIStreamCompletion, OpenAIStreamChoice,
    OpenAIStreamDelta, OpenAIChoice,OpenAIMessage
    )


class OpenAICompatibleClient(BaseClient):
    """OpenAI 兼容格式的客户端类

    用于处理符合 OpenAI API 格式的服务,如 Gemini 等
    """

    def __init__(
        self,
        api_key: str,
        api_url: str,
        timeout: Optional[aiohttp.ClientTimeout] = None,
        proxy: str = None,
    ):
        """初始化 OpenAI 兼容客户端

        Args:
            api_key: API密钥
            api_url: API地址
            timeout: 请求超时设置,None则使用默认值
            proxy: 代理服务器地址
        """
        super().__init__(api_key, api_url, timeout, proxy=proxy)

    def _format_data(self,model:str,messages:str,stream:bool = True) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """将数据格式化为 OpenAI API 可以接受的格式

        Args:
            model: 模型名称
            messages: 消息列表
            stream: 是否使用流式输出，默认为 True

        Returns:
            headers: 请求头
            data: 请求体
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "messages": messages,
            "stream": stream
        }
        return headers,data

    async def chat(
        self, messages: List[Dict[str, str]], model: str, model_arg: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """非流式对话

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            Dict[str, Any]: OpenAI 格式的完整响应

        Raises:
            ClientError: 请求错误
        """
        headers,data = self._format_data(model,messages,stream=False)
        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created_time = int(time.time())

        data = self._add_model_params(data, model_arg)
        try:
            response_bytes = await self._make_non_streaming_request(headers, data)

            # 解析响应
            response = json.loads(response_bytes.decode("utf-8"))
            choices = response["choices"]
            message = choices[0].get("message", {})
            content = message.get("content", None)
            reasoning_content = message.get("reasoning_content", None)

            # 使用基类的格式化方法重新格式化响应
            return OpenAICompletion(
                chat_id,
                created_time,
                model,
                choices=[OpenAIChoice(
                    index= choices.get("index", 0),
                    finish_reason=choices.get("finish_reason", None),
                    message=OpenAIMessage(
                        content=content,
                        reasoning_content=reasoning_content
                    )
                )]
            )

        except Exception as e:
            error_msg = f"Chat请求失败: {str(e)}"
            logger.error(error_msg)
            raise ClientError(error_msg) from e

    async def stream_chat(
        self, messages: List[Dict[str, str]], model: str, model_arg: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式对话

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数

        Yields:
            Dict[str, Any]: OpenAI 兼容格式的流式响应

        Raises:
            ClientError: 请求错误
        """
        headers, data = self._format_data(model, messages, stream=True)
        data = self._add_model_params(data, model_arg)
        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created_time = int(time.time())

        buffer = ""
        try:
            async for chunk in self._make_request(headers, data):
                buffer += chunk.decode("utf-8")

                # 处理 buffer 中的数据行
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    # 跳过空行和 data: [DONE] 行
                    if not line or line == "data: [DONE]":
                        continue

                    # 解析 SSE 数据
                    if line.startswith("data: "):
                        json_str = line[6:].strip()
                        response = json.loads(json_str)
                        if (
                            "choices" in response
                            and len(response["choices"]) > 0
                            and "delta" in response["choices"][0]
                        ):
                            delta = response["choices"][0]["delta"]
                            content = delta.get("content", None)
                            reasoning_content = delta.get("reasoning_content", None)
                            index = delta.get("index", 0)
                            finish_reason = delta.get("finish_reason", None)

                            # 使用基类的格式化方法重新格式化流式响应
                            yield OpenAIStreamCompletion(
                                chat_id,
                                created_time,
                                model,
                                choices=[OpenAIStreamChoice(
                                    delta=OpenAIStreamDelta(
                                        content=content,
                                        reasoning_content=reasoning_content
                                    ),
                                    index=index,
                                    finish_reason=finish_reason
                                )],
                            )

        except json.JSONDecodeError as e:
            error_msg = f"JSON解析错误: {str(e)}"
            logger.error(error_msg)
            raise ClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Stream chat请求失败: {str(e)}"
            logger.error(error_msg)
            raise ClientError(error_msg) from e