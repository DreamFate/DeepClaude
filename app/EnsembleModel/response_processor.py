from app.EnsembleModel.model_processor import ModelProcessor
from app.EnsembleModel.model_context import ModelContext
from app.utils.logger import logger
import json
from typing import List, Dict


class ResponseProcessor(ModelProcessor):
    """响应模型处理器"""

    async def process(self, context: ModelContext) -> ModelContext:
        """处理响应阶段

        Args:
            context: 处理上下文

        Returns:
            更新后的上下文
        """
        logger.info(f"开始 {self.name} 响应处理")

        try:
            # 准备响应模型的输入消息
            response_messages = self._prepare_messages(context.messages, context.get_full_reasoning())

            # 使用客户端的流式或非流式聊天方法
            if context.stream:
                async for response in self.client.stream_chat(
                    messages=response_messages,
                    model=self.name,
                    model_arg=context.model_arg
                ):
                    # 从响应中提取内容
                    if response.get("choices") and response["choices"][0].get("delta"):
                        delta = response["choices"][0]["delta"]

                        if delta.get("content"):
                            content = delta["content"]
                            context.add_response(content)

                            # 将格式化的响应放入队列
                            await context.output_queue.put(
                                f"data: {json.dumps(response)}\n\n".encode("utf-8")
                            )
            else:
                # 非流式处理
                response = await self.client.chat(
                    messages=response_messages,
                    model=self.name,
                    model_arg=context.model_arg
                )

                if response.get("choices") and response["choices"][0].get("message"):
                    message = response["choices"][0]["message"]
                    content = message.get("content", "")
                    context.add_response(content)

            context.completed = True
            logger.info(f"{self.name} 响应处理完成")
            return context

        except Exception as e:
            error_msg = f"{self.name} 响应处理错误: {str(e)}"
            logger.error(error_msg)
            context.set_error(error_msg)
            raise

    def _prepare_messages(self, messages: List[Dict[str, str]], reasoning: str) -> List[Dict[str, str]]:
        """准备响应模型的输入消息

        Args:
            messages: 原始消息列表
            reasoning: 推理内容

        Returns:
            处理后的消息列表
        """
        # 复制消息列表
        processed_messages = messages.copy()

        # 提取系统消息
        system_content = ""
        non_system_messages = []

        for message in processed_messages:
            if message.get("role") == "system":
                system_content += message.get("content", "") + "\n"
            else:
                non_system_messages.append(message)

        # 更新为不包含系统消息的列表
        processed_messages = non_system_messages

        # 确保消息列表不为空
        if not processed_messages:
            # 如果没有消息，创建一个默认的用户消息
            processed_messages = [{"role": "user", "content": "请提供回答"}]

        # 获取最后一个消息
        last_message = processed_messages[-1]

        # 如果最后一个消息是用户消息，添加推理内容
        if last_message.get("role") == "user":
            original_content = last_message["content"]
            combined_content = (
                f"Here's my original input:\n{original_content}\n\n"
                f"Here's my another model's reasoning process:\n{reasoning}\n\n"
                f"Based on this reasoning, provide your response directly to me:"
            )
            last_message["content"] = combined_content

        # 返回处理后的消息列表和系统提示
        return processed_messages