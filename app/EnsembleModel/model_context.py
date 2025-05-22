""" 模型处理上下文，在责任链中传递 """

from typing import List, Dict, Any
import asyncio
import time

class ModelContext:
    """模型处理上下文，在责任链中传递"""

    def __init__(
        self,
        messages: List[Dict[str, str]],
        model_arg: Dict[str, Any] = None,
        stream: bool = True
    ):
        """初始化上下文

        Args:
            messages: 初始消息列表
            model_arg: 模型参数
            stream: 是否流式输出
        """
        self.messages = messages
        self.model_arg = model_arg or {}
        self.stream = stream

        # 生成会话ID和时间戳
        self.chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"
        self.created_time = int(time.time())

        # 处理结果
        self.reasoning_content = []
        self.response_content = []

        # 流式输出队列
        self.output_queue = asyncio.Queue() if stream else None

        # 处理状态
        self.completed = False
        self.error = None

        # 元数据
        self.metadata = {}

    def add_reasoning(self, content: str):
        """添加推理内容"""
        self.reasoning_content.append(content)

    def add_response(self, content: str):
        """添加响应内容"""
        self.response_content.append(content)

    def get_full_reasoning(self) -> str:
        """获取完整推理内容"""
        return "".join(self.reasoning_content)

    def get_full_response(self) -> str:
        """获取完整响应内容"""
        return "".join(self.response_content)

    def set_error(self, error: str):
        """设置错误信息"""
        self.error = error

    def is_error(self) -> bool:
        """检查是否有错误"""
        return self.error is not None
