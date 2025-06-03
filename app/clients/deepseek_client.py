"""DeepSeek API 客户端"""

import json
import time
from typing import AsyncGenerator,Dict,Any,Tuple

import aiohttp

from app.utils.logger import logger

from app.chatcompletion.openai_compatible import (
    OpenAICompletion,
    OpenAIStreamCompletion, OpenAIStreamChoice,
    OpenAIStreamDelta,OpenAIUsage,OpenAIChoice,OpenAIMessage
    )
from .base_client import BaseClient,handle_client_errors


class DeepSeekClient(BaseClient):
    """DeepSeek API 客户端"""
    def __init__(
        self,
        api_key: str,
        api_url: str,
        connector: aiohttp.TCPConnector,
        proxy: str = None,
    ):
        """初始化 DeepSeek 客户端

        Args:
            api_key: DeepSeek API密钥
            api_url: DeepSeek API地址
            connector: TCP连接器
            proxy: 代理服务器地址，例如 "http://127.0.0.1:7890"
        """
        super().__init__(api_key, api_url, connector=connector, proxy=proxy)

    def _format_data(
        self,
        model:str,
        messages:str,
        stream:bool = True
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """将数据格式化为 DeepSeek API 可以接受的格式

        Args:
            model: 模型名称
            messages: 消息列表

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

    @handle_client_errors(operation_name="流式对话")
    async def stream_chat(
        self,
        messages: list,
        model: str,
        model_arg: Dict[str, Any] = None,
        is_origin_reasoning: bool = True,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """流式对话

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            is_origin_reasoning: 是否使用原生推理，默认为 True

        Yields:
            tuple[str, str]: (内容类型, 内容)
                内容类型: "reasoning" 或 "content"
                内容: 实际的文本内容
        """

        headers, data = self._format_data(model,messages,stream=True)

        logger.debug("开始流式对话: ")

        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created_time = int(time.time())

        is_collecting_think = False
        temp_content = ""

        async for chunk in self._make_request(headers, data):
            chunk_str = chunk.decode("utf-8")

            lines = chunk_str.splitlines()
            for line in lines:
                data = self.parse_json_line(line)
                if data is None:
                    continue

                choices = data.get("choices")
                delta = choices[0].get("delta")

                if is_origin_reasoning:
                    yield OpenAIStreamCompletion(
                        id=chat_id,
                        created=created_time,
                        model=model,
                        provider_chat_id=choices[0].get("id"),
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
                            completion_tokens=choices[0].get("usage").get("completion_tokens"),
                            prompt_tokens=choices[0].get("usage").get("prompt_tokens"),
                            total_tokens=choices[0].get("usage").get("total_tokens")
                        ) if choices[0].get("usage") else None
                    )
                else:
                    original_content = delta.get("content")

                    # 这里为</think>结束,后面可能还有正文的内容,需要将temp_content和original_content拼接
                    if temp_content:
                        original_content = temp_content + original_content
                        temp_content = ""

                    if "<think>" in original_content:
                        is_collecting_think = True
                        # 这里一般有<think>,将会是第一个开始,就直接替换当作思考链的内容
                        original_content = original_content.replace("<think>", "", 1)

                    if "</think>" in original_content:
                        is_collecting_think = False
                        parts = original_content.split("</think>")
                        original_content = parts[0]
                        temp_content = "".join(parts[1:])

                    if is_collecting_think:
                        delta_data = OpenAIStreamDelta(
                            role=delta.get("role"),
                            reasoning_content=original_content
                        )
                    else:
                        delta_data = OpenAIStreamDelta(
                            role=delta.get("role"),
                            content=original_content,
                        )

                    yield OpenAIStreamCompletion(
                        id=chat_id,
                        created=created_time,
                        model=model,
                        provider_chat_id=choices[0].get("id"),
                        choices=[OpenAIStreamChoice(
                            delta=delta_data,
                            index=choices[0].get("index"),
                            finish_reason=choices[0].get("finish_reason")
                            )
                        ],
                        usage=OpenAIUsage(
                            completion_tokens=choices[0].get("usage").get("completion_tokens"),
                            prompt_tokens=choices[0].get("usage").get("prompt_tokens"),
                            total_tokens=choices[0].get("usage").get("total_tokens")
                        ) if choices[0].get("usage") else None
                    )

    @handle_client_errors(operation_name="非流式对话")
    async def chat(
        self,
        messages: list,
        model: str,
        model_arg: Dict[str, Any] = None,
        is_origin_reasoning: bool = True,
    ) -> Dict[str, Any]:
        """非流式对话

        Args:
            messages: 消息列表
            model: 模型名称
            model_arg: 模型参数元组[temperature, top_p, presence_penalty, frequency_penalty]
            is_origin_reasoning: 是否使用原生推理，默认为 True

        Returns:
            Dict[str, Any]: OpenAI 兼容格式的完整响应
        """
        # 准备请求数据
        headers, data = self._format_data(model, messages,stream=False)

        logger.debug("开始非流式对话")

        # 使用非流式请求方法获取完整响应
        response_bytes = await self._make_non_streaming_request(headers, data)
        response = json.loads(response_bytes.decode("utf-8"))

        # 处理响应
        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created = int(time.time())
        provider_chat_id = response.get("id")
        choices = response.get("choices")
        message = choices[0].get("message")
        content = message.get("content")
        reasoning_content = None

        if not content:
            logger.debug("DeepSeek响应中未找到有效内容")

        if is_origin_reasoning:
            # 处理原生推理内容
            reasoning_content = message.get("reasoning_content")
        else:
            # 处理非原生推理内容
            if "<think>" in content and "</think>" in content:
                # 提取推理内容
                think_start = content.find("<think>")
                think_end = content.find("</think>") + len("</think>")
                reasoning_content = content[think_start:think_end]
                # 移除推理内容
                content = content[:think_start] + content[think_end:]

        # 返回格式化的OpenAI兼容响应
        return OpenAICompletion(
            chat_id,
            created,
            model,
            provider_chat_id=provider_chat_id,
            choices=[OpenAIChoice(
                message=OpenAIMessage(
                    role=message.get("role"),
                    content=content,
                    reasoning_content=reasoning_content
                ),
                index=choices[0].get("index"),
                finish_reason=choices[0].get("finish_reason")
            )],
            usage=OpenAIUsage(
                completion_tokens=choices[0].get("usage").get("completion_tokens"),
                prompt_tokens=choices[0].get("usage").get("prompt_tokens"),
                total_tokens=choices[0].get("usage").get("total_tokens")
            ) if choices[0].get("usage") else None
        )
