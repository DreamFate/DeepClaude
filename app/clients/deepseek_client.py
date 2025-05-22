"""DeepSeek API 客户端"""

import json
import time
from typing import AsyncGenerator,Dict,Any,Tuple
from aiohttp.client_exceptions import ClientError

from app.utils.logger import logger
from .base_client import BaseClient


class DeepSeekClient(BaseClient):
    """DeepSeek API 客户端"""
    def __init__(
        self,
        api_key: str,
        api_url: str,
        proxy: str = None,
    ):
        """初始化 DeepSeek 客户端

        Args:
            api_key: DeepSeek API密钥
            api_url: DeepSeek API地址
            proxy: 代理服务器地址
        """
        super().__init__(api_key, api_url, proxy=proxy)

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

        async for chunk in self._make_request(headers, data):
            chunk_str = chunk.decode("utf-8")

            try:
                lines = chunk_str.splitlines()
                for line in lines:
                    if line.startswith("data: "):
                        json_str = line[len("data: ") :]
                        if json_str == "[DONE]":
                            return

                        data = json.loads(json_str)
                        if (
                            data
                            and data.get("choices")
                            and data["choices"][0].get("delta")
                        ):
                            delta = data["choices"][0]["delta"]

                            if is_origin_reasoning:
                                # 处理 reasoning_content
                                if delta.get("reasoning_content"):
                                    content = delta["reasoning_content"]
                                    logger.debug("提取推理内容：%s", content)
                                    yield self.format_openai_compatible_stream_response(
                                        chat_id,
                                        created_time,model,
                                        content="",
                                        reasoning_content=content
                                    )
                                if delta.get("reasoning_content") is None and delta.get(
                                    "content"
                                ):
                                    content = delta["content"]
                                    logger.info("提取内容信息，推理阶段结束: %s", content)
                                    yield self.format_openai_compatible_stream_response(
                                        chat_id,
                                        created_time,model,
                                        content=content
                                    )
                            else:
                                accumulated_content = ""
                                is_collecting_think = False
                                # 处理其他模型的输出
                                content = delta.get("content","")
                                if content == "":  # 只跳过完全空的字符串
                                    continue
                                logger.debug("非原生推理内容：%s", content)
                                accumulated_content += content

                                if "<think>" in content and not is_collecting_think:
                                    # 开始收集推理内容
                                    logger.debug("开始收集推理内容")
                                    is_collecting_think = True
                                    yield self.format_openai_compatible_stream_response(
                                        chat_id,
                                        created_time,
                                        model,
                                        content="",
                                        reasoning_content=content
                                    )
                                elif is_collecting_think:
                                    if "</think>" in content:
                                        # 推理内容结束
                                        logger.debug("推理内容结束")
                                        is_collecting_think = False
                                        yield self.format_openai_compatible_stream_response(
                                            chat_id,
                                            created_time,
                                            model,
                                            content="",
                                            reasoning_content=content
                                        )
                                        # 输出空的 content 来触发 Claude 处理
                                        yield self.format_openai_compatible_stream_response(
                                            chat_id,
                                            created_time,
                                            model,
                                            content=""
                                        )
                                        # 重置累积内容
                                        accumulated_content = ""
                                    else:
                                        # 继续收集推理内容
                                        yield self.format_openai_compatible_stream_response(
                                            chat_id,
                                            created_time,
                                            model,
                                            content="",
                                            reasoning_content=content
                                        )
                                else:
                                    # 普通内容
                                    yield self.format_openai_compatible_stream_response(
                                        chat_id,
                                        created_time,
                                        model,
                                        content=content
                                    )

            except json.JSONDecodeError as e:
                error_msg = f"JSON 解析错误: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e
            except Exception as e:
                error_msg = f"Stream chat请求失败: {str(e)}"
                logger.error(error_msg)
                raise ClientError(error_msg) from e

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
        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        created_time = int(time.time())

        try:
            # 使用非流式请求方法获取完整响应
            response_bytes = await self._make_non_streaming_request(headers, data)
            response = json.loads(response_bytes.decode("utf-8"))

            # 处理响应
            message = response["choices"][0]["message"]
            content = message.get("content", "")
            reasoning_content = None

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
            return self.format_openai_compatible_response(
                chat_id,
                created_time,
                model,
                content,
                reasoning_content
            )

        except json.JSONDecodeError as e:
            error_msg = f"JSON 解析错误: {str(e)}"
            logger.error(error_msg)
            raise ClientError(error_msg) from e
        except Exception as e:
            error_msg = f"Chat请求失败: {str(e)}"
            logger.error(error_msg)
            raise ClientError(error_msg) from e
