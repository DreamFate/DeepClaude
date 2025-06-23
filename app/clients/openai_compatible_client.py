"""OpenAI 兼容格式的客户端类,用于处理符合 OpenAI API 格式的服务"""

import json
import time
from typing import AsyncGenerator, Optional, Dict, Any, List,Tuple


import asyncio
import aiohttp

from app.utils.logger import logger

from app.clients.base_client import BaseClient
from app.chatcompletion.openai_compatible import (
    OpenAICompletion,
    OpenAIStreamCompletion, OpenAIStreamChoice,
    OpenAIStreamDelta, OpenAIChoice,OpenAIMessage,OpenAIUsage
    )


class OpenAICompatibleClient(BaseClient):
    """OpenAI 兼容格式的客户端类

    用于处理符合 OpenAI API 格式的服务,如 Gemini 等
    """

    def __init__(
        self,
        api_key: str,
        api_url: str,
        connector: aiohttp.TCPConnector,
        timeout: Optional[aiohttp.ClientTimeout] = None,
        proxy: Optional[str] = None,
    ):
        """初始化 OpenAI 兼容客户端

        Args:
            api_key: API密钥
            api_url: API地址
            timeout: 请求超时设置,None则使用默认值
            proxy: 代理服务器地址
        """
        super().__init__(api_key, api_url, connector=connector, timeout=timeout, proxy=proxy)

    def format_data(
        self,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        model_arg: Dict[str, Any],
        stream: bool,
        other_params: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
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
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        data = self._add_model_params(data, model_arg)
        return headers,data

    async def chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any] = None,
        other_params: Dict[str, Any] = None,
    ) -> OpenAICompletion:
        """非流式对话

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            other_params: 其他参数
            cancel_flag: 取消标志

        Returns:
            Dict[str, Any]: OpenAI 格式的完整响应

        Raises:
            ClientError: 请求错误
        """
        headers,data = self.format_data(self.api_key, model,messages,model_arg,stream=False)
        created_time = int(time.time())

        data = self._add_model_params(data, model_arg)

        response_bytes = await self._make_non_streaming_request(headers, data)

        # 解析响应
        response = json.loads(response_bytes.decode("utf-8"))
        choices = response["choices"]
        message = choices[0].get("message", {})
        content = message.get("content")
        reasoning_content = message.get("reasoning_content")

        # 使用基类的格式化方法重新格式化响应
        return OpenAICompletion(
            chat_id,
            created_time,
            model,
            provider_chat_id=response.get("id"),
            choices=[OpenAIChoice(
                index= choices.get("index"),
                finish_reason=choices.get("finish_reason"),
                message=OpenAIMessage(
                    content=content,
                    reasoning_content=reasoning_content
                )
            )],
            usage=OpenAIUsage(
                completion_tokens=response.get("usage").get("completion_tokens"),
                prompt_tokens=response.get("usage").get("prompt_tokens"),
                total_tokens=response.get("usage").get("total_tokens")
            ) if response.get("usage") else None
        )

    async def stream_chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any] = None,
        other_params: Dict[str, Any] = None,
        cancel_flag: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[OpenAIStreamCompletion, None]:
        """流式对话

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            other_params: 其他参数
            cancel_flag: 取消标志

        Yields:
            OpenAIStreamCompletion: OpenAI 兼容格式的流式响应

        Raises:
            ClientError: 请求错误
        """
        headers, data = self.format_data(self.api_key, model, messages,model_arg, stream=True)
        data = self._add_model_params(data, model_arg)
        created = int(time.time())

        async for chunk in self._make_request(headers, data, cancel_flag=cancel_flag):
            chunk_str = chunk.decode("utf-8")

            lines = chunk_str.splitlines()
            for line in lines:
                data = self.parse_json_line(line)
                if data is None:
                    continue

                if data == "[DONE]":
                    logger.debug("流式对话结束")
                    break

                choices = data.get("choices")
                delta = choices[0].get("delta")

                yield OpenAIStreamCompletion(
                    id=chat_id,
                    created=created,
                    model=model,
                    provider_chat_id=data.get("id"),
                    choices=[OpenAIStreamChoice(
                        delta=OpenAIStreamDelta(
                            role=delta.get("role"),
                            content=delta.get("content"),
                            reasoning_content=delta.get("reasoning_content")
                            ),
                        index=choices[0].get("index"),
                        finish_reason=choices[0].get("finish_reason")
                        )
                    ],
                    usage=OpenAIUsage(
                        completion_tokens=data.get("usage").get("completion_tokens"),
                        prompt_tokens=data.get("usage").get("prompt_tokens"),
                        total_tokens=data.get("usage").get("total_tokens")
                    ) if data.get("usage") else None
                )
