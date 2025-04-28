"""Claude API 客户端"""

import json
from typing import AsyncGenerator, Dict, Any, Tuple

from app.utils.logger import logger

from .base_client import BaseClient


class ClaudeClient(BaseClient):
    """Claude API 客户端"""
    def __init__(
        self,
        api_key: str,
        api_url: str,
        provider: str = "anthropic",
        proxy: str = None,
    ):
        """初始化 Claude 客户端

        Args:
            api_key: Claude API密钥
            api_url: Claude API地址
            provider: API提供商，支持 anthropic、openrouter、oneapi
            proxy: 代理服务器地址
        """
        super().__init__(api_key, api_url, proxy=proxy)
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
            "max_tokens": 8192,
            "stream": stream,
        }

        # Anthropic 原生 API 支持 system 参数
        if system_prompt:
            data["system"] = system_prompt

        # Anthropic目前只支持温度
        model_arg_anthropic = {
            "temperature":  model_arg.get("temperature"),
            "top_p": model_arg.get("top_p")
        }

        data = self._add_model_params(data, model_arg_anthropic)
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

        Yields:
            tuple[str, str]: (role, content) 消息元组
                role: 角色
                content: 实际的文本内容
        """
        headers, data = self.data_format(messages, model_arg, model, system_prompt, stream)
        logger.debug("开始对话: ")
        # 使用非流式请求方法获取完整响应
        try:
            response_bytes = await self._make_non_streaming_request(headers, data)

            # 解析响应
            response = json.loads(response_bytes.decode("utf-8"))

            if self.provider in ("openrouter", "oneapi"):
                content =  response.get("choices", [{}])[0].get("message", {}).get("content", "")
            elif self.provider == "anthropic":
                content = response.get("content", [{}])[0].get("text", "")
            else:
                raise ValueError(f"不支持的Claude Provider: {self.provider}")

            if content:
                yield "answer", content
            else:
                logger.warning("%s响应中未找到有效内容", self.provider)
        except (KeyError, IndexError) as e:
            logger.error("解析%s响应时出错: %s", self.provider, e)
            raise ValueError(f"无法解析{self.provider}的响应格式") from e

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
        async for chunk in self._make_request(headers, data):
            chunk_str = chunk.decode("utf-8")
            if not chunk_str.strip():
                continue

            for line in chunk_str.split("\n"):
                if line.startswith("data: "):
                    json_str = line[6:]  # 去掉 'data: ' 前缀
                    if json_str.strip() == "[DONE]":
                        return

                    try:
                        data = json.loads(json_str)
                        if self.provider in ("openrouter", "oneapi"):
                            # OpenRouter/OneApi 格式
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        elif self.provider == "anthropic":
                            # Anthropic 格式
                            if data.get("type") == "content_block_delta":
                                content = data.get("delta", {}).get("text", "")
                            else:
                                raise ValueError( f"Anthropic 格式错误: {data}" )
                        else:
                            raise ValueError( f"不支持的Claude Provider: {self.provider}" )
                        if content:
                            yield "answer", content
                        else:
                            logger.warning("%s响应中未找到有效内容", self.provider)
                    except (KeyError, IndexError) as e:
                        logger.error("解析%s响应时出错: %s", self.provider, e)
                        raise ValueError(f"无法解析{self.provider}的响应格式") from e
