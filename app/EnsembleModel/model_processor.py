
from abc import ABC, abstractmethod
from app.clients.base_client import BaseClient
from app.EnsembleModel.model_context import ModelContext
from app.utils.logger import logger

class ModelProcessor(ABC):
    """模型处理器基类"""

    def __init__(self, name: str, client: BaseClient):
        """初始化处理器

        Args:
            name: 处理器名称
            client: 客户端实例
        """
        self.name = name
        self.client = client
        self.next_processor = None

    def set_next(self, processor: 'ModelProcessor') -> 'ModelProcessor':
        """设置下一个处理器

        Args:
            processor: 下一个处理器

        Returns:
            下一个处理器实例，便于链式调用
        """
        self.next_processor = processor
        return processor

    @abstractmethod
    async def process(self, context: ModelContext) -> ModelContext:
        """处理当前阶段，由子类实现

        Args:
            context: 处理上下文

        Returns:
            更新后的上下文
        """

    async def process_chain(self, context: ModelContext) -> ModelContext:
        """处理整个责任链

        Args:
            context: 处理上下文

        Returns:
            处理完成的上下文
        """
        if context.is_error():
            logger.warning("跳过处理器 %s，因为上下文中有错误: %s", self.name, context.error)
            return context

        try:
            # 处理当前阶段
            context = await self.process(context)

            # 如果有下一个处理器，继续处理
            if self.next_processor and not context.is_error():
                return await self.next_processor.process_chain(context)

            return context

        except Exception as e:
            error_msg = f"处理器 {self.name} 处理失败: {str(e)}"
            logger.error(error_msg)
            context.set_error(error_msg)
            return context