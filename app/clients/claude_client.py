"""Claude API 客户端"""

import json
from typing import AsyncGenerator, Dict, Any,Optional,Tuple,List
import time

import asyncio
import aiohttp

from app.utils.logger import logger

from app.chatcompletion.openai_compatible import (
    OpenAICompletion, OpenAIChoice, OpenAIMessage,
    OpenAIStreamCompletion, OpenAIStreamChoice,
    OpenAIStreamDelta,OpenAIUsage
    )
from app.chatcompletion.request_claude import format_claude_request
from .base_client import BaseClient, handle_client_errors


class ClaudeClient(BaseClient):
    """Claude API 客户端"""
    def __init__(
        self,
        api_key: str,
        api_url: str,
        connector: aiohttp.TCPConnector,
        proxy: Optional[str] = None,
    ):
        """初始化 Claude 客户端

        Args:
            api_key: Claude API密钥
            api_url: Claude API地址
            connector: TCP连接器
            provider: API提供商，支持 anthropic、openrouter、oneapi
            proxy: 代理服务器地址
        """
        super().__init__(api_key, api_url, connector=connector, proxy=proxy)

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
        headers,data = format_claude_request(api_key, model, messages, model_arg, stream)
        return headers,data

    @handle_client_errors("Claude非流式输出")
    async def chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any] = None,
        other_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """非流式对话

        Args:
            messages: 消息列表
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            model: 模型名称
            stream: 是否使用流式输出，默认为 True
            system_prompt: 系统提示

        Returns:
            Dict[str, Any]: OpenAI 格式的完整响应
        """

        headers,data = self.format_data(self.api_key, model, messages, model_arg, stream=False)
        logger.debug("开始对话: ")
        # 使用非流式请求方法获取完整响应
        response_bytes = await self._make_non_streaming_request(headers, data)

        # 解析响应
        response = json.loads(response_bytes.decode("utf-8"))
        created = int(time.time())
        content = response.get("content", "")

        return OpenAICompletion(
            chat_id,
            created,
            model,
            provider_chat_id=response.get("id"),
            choices=[OpenAIChoice(
                message=OpenAIMessage(
                    role=response.get("role"),
                    content=content[0].get("text"),
                    reasoning_content=content[0].get("thinking")
                ),
                finish_reason=response.get("stop_reason")
            )],
            usage=OpenAIUsage(
                completion_tokens=response.get("usage").get("output_tokens"),
                prompt_tokens=response.get("usage").get("input_tokens")
            ) if response.get("usage") else None
        )

    @handle_client_errors("Claude流式输出")
    async def stream_chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any] = None,
        other_params: Dict[str, Any] = None,
        cancel_flag: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """流式对话

        Args:
            messages: 消息列表
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            model: 模型名称
            stream: 是否使用流式输出，默认为 True
            system_prompt: 系统提示

        Yields:
            tuple[str, str]: (内容类型, 内容)
                内容类型: "answer"
                内容: 实际的文本内容
        """

        headers,data = self.format_data(self.api_key, model, messages, model_arg, stream=True)

        logger.debug("开始对话: ")

        created = int(time.time())
        provider_chat_id = None
        role = None
        async for chunk in self._make_request(headers, data,cancel_flag=cancel_flag):
            chunk_str = chunk.decode("utf-8")
            lines = chunk_str.splitlines()

            for line in lines:
                data = self.parse_json_line(line)
                if data is None:
                    continue

                chat_type = data.get("type")
                if chat_type == "message_start":
                    messages = data.get("messages")
                    provider_chat_id = messages[0].get("id")
                    role = messages[0].get("role")

                delta = data.get("delta")
                # 这里跳过一些start和ping相关的数据,现阶段不去获取,用不上
                if delta is None:
                    continue

                # 这里跳过使用tool_use工具生成的内容,现阶段不去获取,用不上
                if delta.get("type") == "input_json_delta":
                    continue

                yield OpenAIStreamCompletion(
                        id=chat_id,
                        created=created,
                        model=model,
                        provider_chat_id=provider_chat_id,
                        choices=[OpenAIStreamChoice(
                            delta=OpenAIStreamDelta(
                                role=role,
                                content=delta.get("text"),
                                reasoning_content=delta.get("thinking")
                                ),
                            index=data.get("index"),
                            finish_reason=delta.get("stop_reason")
                            )
                        ],
                        usage=OpenAIUsage(
                            completion_tokens=data.get("usage").get("output_tokens"),
                            prompt_tokens=data.get("usage").get("input_tokens")
                        ) if data.get("usage") else None
                    )
