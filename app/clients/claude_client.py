"""Claude API 客户端"""

import json
from typing import AsyncGenerator, Dict, Any, Tuple
import time
import aiohttp

from app.utils.logger import logger

from app.chatcompletion.openai_compatible import (
    OpenAICompletion, OpenAIChoice, OpenAIMessage,
    OpenAIStreamCompletion, OpenAIStreamChoice,
    OpenAIStreamDelta,OpenAIUsage
    )
from .base_client import BaseClient


class ClaudeClient(BaseClient):
    """Claude API 客户端"""
    def __init__(
        self,
        api_key: str,
        api_url: str,
        connector: aiohttp.TCPConnector,
        provider: str = "anthropic",
        proxy: str = None,
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
        self.provider = provider


    def _format_openrouter_data(
        self,messages: list,
        model_arg: Dict[str, Any],
        model: str,
        system_prompt: str = None,
        stream: bool = True
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        # 转换模型名称为 OpenRouter 格式
        model = "anthropic/" + model

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ErlichLiu/DeepClaude",  # OpenRouter 需要
            "X-Title": "DeepClaude",  # OpenRouter 需要
        }

        # 传递 OpenRouterOneAPI system prompt
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        data = {
            "model": model,  # OpenRouter 使用 anthropic/claude-3.5-sonnet 格式
            "messages": messages,
            "stream": stream,
        }
        data = self._add_model_params(data, model_arg)
        return headers,data

    def _format_oneapi_data(
        self,messages: list,
        model_arg: Dict[str, Any],
        model: str,
        system_prompt: str = None,
        stream: bool = True
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 传递 OneAPI system prompt
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        data = self._add_model_params(data, model_arg)
        return headers,data

    def _format_anthropic_data(
        self,messages: list,
        model_arg: Dict[str, Any],
        model: str,
        system_prompt: str = None,
        stream: bool = True
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream" if stream else "application/json",
        }

        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # Anthropic 原生 API 支持 system 参数
        if system_prompt:
            data["system"] = system_prompt

        data = self._add_model_params(data, model_arg)
        return headers,data

    def data_format(
        self,
        messages: list,
        model_arg: Dict[str, Any],
        model: str,
        system_prompt: str = None,
        stream: bool = True
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """数据格式化

        Args:
            messages: 消息列表
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            model: 模型名称。如果是 OpenRouter, 会自动转换为 'anthropic/claude-3.5-sonnet' 格式
            system_prompt: 系统提示
            stream: 是否使用流式输出，默认为 True

        Returns:
            tuple[str, str]: (内容类型, 内容)
                内容类型: "answer"
                内容: 实际的文本内容
        """
        formatters = {
            "openrouter": self._format_openrouter_data,
            "oneapi": self._format_oneapi_data,
            "anthropic": self._format_anthropic_data
        }

        formatter = formatters.get(self.provider)
        if not formatter:
            raise ValueError(f"不支持的Claude Provider: {self.provider}")

        return formatter(messages, model_arg, model, system_prompt, stream)

    async def chat(
        self,
        messages: list,
        model: str,
        model_arg: Dict[str, Any] = None,
        stream: bool = True,
        system_prompt: str = None
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
        headers, data = self.data_format(messages, model_arg, model, system_prompt, stream)
        logger.debug("开始对话: ")
        # 使用非流式请求方法获取完整响应
        response_bytes = await self._make_non_streaming_request(headers, data)

        # 解析响应
        response = json.loads(response_bytes.decode("utf-8"))
        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
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

    def parse_json_line(self,line):
        """解析 JSON 行"""
        if line.startswith("data: "):
            json_str = line[len("data: "):]
            if json_str == "[DONE]":
                return None
        else:
            json_str = line

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.error("无法解析JSON: %s", json_str)
            return None

    async def stream_chat(
        self,
        messages: list,
        model: str,
        model_arg: Dict[str, Any] = None,
        stream: bool = True,
        system_prompt: str = None,
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
        headers, data = self.data_format(messages, model_arg, model, system_prompt, stream)

        logger.debug("开始对话: ")

        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created = int(time.time())
        provider_chat_id = None
        role = None
        async for chunk in self._make_request(headers, data):
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
