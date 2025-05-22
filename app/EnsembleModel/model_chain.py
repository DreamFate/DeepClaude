from typing import List, Dict, Any, Union, AsyncGenerator
from app.EnsembleModel.model_processor import ModelProcessor
from app.EnsembleModel.model_context import ModelContext
from app.utils.logger import logger
import json
import asyncio

class ModelChain:
    """模型处理链管理器"""

    def __init__(self):
        """初始化模型链"""
        self.chain_head = None
        self.processors = []

    def add_processor(self, processor: ModelProcessor) -> 'ModelChain':
        """添加处理器到链中

        Args:
            processor: 要添加的处理器

        Returns:
            self，便于链式调用
        """
        self.processors.append(processor)

        if not self.chain_head:
            self.chain_head = processor
        else:
            # 找到链的末尾
            current = self.chain_head
            while current.next_processor:
                current = current.next_processor
            current.set_next(processor)

        return self

    async def process(
        self,
        messages: List[Dict[str, str]],
        model_arg: Dict[str, Any] = None,
        stream: bool = True
    ) -> Union[AsyncGenerator[bytes, None], Dict[str, Any]]:
        """处理完整的模型链

        Args:
            messages: 初始消息列表
            model_arg: 模型参数
            stream: 是否流式输出

        Returns:
            流式输出生成器或完整响应字典
        """
        if not self.chain_head:
            raise ValueError("模型链为空，请添加至少一个处理器")

        # 创建上下文
        context = ModelContext(messages, model_arg, stream)

        if stream:
            # 启动异步处理任务
            processing_task = asyncio.create_task(self.chain_head.process_chain(context))

            # 从输出队列获取结果
            while not context.completed and not context.is_error():
                try:
                    # 设置超时，避免无限等待
                    item = await asyncio.wait_for(context.output_queue.get(), timeout=0.1)
                    yield item
                except asyncio.TimeoutError:
                    # 检查处理任务是否完成或出错
                    if processing_task.done():
                        if processing_task.exception():
                            # 处理任务出错
                            error = str(processing_task.exception())
                            logger.error(f"处理任务出错: {error}")
                            error_response = {
                                "id": context.chat_id,
                                "object": "chat.completion.chunk",
                                "created": context.created_time,
                                "model": "error",
                                "error": {"message": error, "type": "processing_error"}
                            }
                            yield f"data: {json.dumps(error_response)}\n\n".encode("utf-8")
                        break

            # 如果处理出错，返回错误信息
            if context.is_error():
                error_response = {
                    "id": context.chat_id,
                    "object": "chat.completion.chunk",
                    "created": context.created_time,
                    "model": "error",
                    "error": {"message": context.error, "type": "processing_error"}
                }
                yield f"data: {json.dumps(error_response)}\n\n".encode("utf-8")

            # 发送结束标记
            yield b"data: [DONE]\n\n"
        else:
            # 非流式处理
            result_context = await self.chain_head.process_chain(context)

            # 如果处理出错，返回错误信息
            if result_context.is_error():
                return {
                    "id": result_context.chat_id,
                    "object": "chat.completion",
                    "created": result_context.created_time,
                    "model": "error",
                    "error": {"message": result_context.error, "type": "processing_error"}
                }

            # 返回完整响应
            last_processor = self.processors[-1] if self.processors else None
            model_name = last_processor.name if last_processor else "unknown"

            return {
                "id": result_context.chat_id,
                "object": "chat.completion",
                "created": result_context.created_time,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result_context.get_full_response(),
                            "reasoning_content": result_context.get_full_reasoning(),
                        },
                        "finish_reason": "stop",
                    }
                ],
                # 可以添加更多元数据
                "usage": result_context.metadata.get("usage", {})
            }