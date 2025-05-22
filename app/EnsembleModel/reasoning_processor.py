from app.EnsembleModel.model_processor import ModelProcessor
from app.EnsembleModel.model_context import ModelContext
from app.utils.logger import logger
import json

class ReasoningProcessor(ModelProcessor):
    """推理模型处理器"""

    async def process(self, context: ModelContext) -> ModelContext:
        """处理推理阶段

        Args:
            context: 处理上下文

        Returns:
            更新后的上下文
        """
        logger.info(f"开始 {self.name} 推理处理")

        try:
            # 使用客户端的流式聊天方法
            async for response in self.client.stream_chat(
                messages=context.messages,
                model=self.name,
                model_arg=context.model_arg
            ):
                # 客户端已经处理为统一格式的响应
                # 从响应中提取内容
                if response.get("choices") and response["choices"][0].get("delta"):
                    delta = response["choices"][0]["delta"]

                    # 处理推理内容
                    if delta.get("reasoning_content"):
                        reasoning_content = delta["reasoning_content"]
                        context.add_reasoning(reasoning_content)

                        # 如果是流式输出，将格式化的响应放入队列
                        if context.stream:
                            await context.output_queue.put(
                                f"data: {json.dumps(response)}\n\n".encode("utf-8")
                            )

                    # 处理普通内容（如果有）
                    if delta.get("content") and delta["content"].strip():
                        # 如果推理模型也生成了内容，可以选择忽略或保存
                        pass

            logger.info(f"{self.name} 推理处理完成")
            return context

        except Exception as e:
            error_msg = f"{self.name} 推理处理错误: {str(e)}"
            logger.error(error_msg)
            context.set_error(error_msg)
            raise