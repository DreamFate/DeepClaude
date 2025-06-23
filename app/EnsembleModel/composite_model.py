"""简单组合模型，顺序执行推理模型和目标模型"""

from typing import List, Dict, Any,Optional,AsyncGenerator
import asyncio
import tiktoken
from app.clients.base_client import BaseClient
from app.utils.logger import logger
from app.utils.error import ClientAPIError

class CompositeModel:
    """简单组合模型，顺序执行推理模型和目标模型"""

    def __init__(
        self,
        reasoning_client: BaseClient,
        target_client: BaseClient,
    ):
        """初始化组合模型

        Args:
            reasoning_client: 推理模型客户端
            target_client: 目标模型客户端
        """
        self.reasoning_client = reasoning_client
        self.target_client = target_client

    async def stream_chat(
        self,
        chat_id: str,
        messages: List[Dict[str, str]],
        model: str,
        model_arg: Dict[str, Any] = None,
        other_params: Dict[str, Any] = None,
        cancel_flag: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """流式聊天完成

        Args:
            messages: 消息列表
            model_arg: 模型参数
            deepseek_model: DeepSeek模型名称（可选）
            claude_model: Claude模型名称（可选）

        Yields:
            Dict[str, str]: 流式响应数据
        """
        # 第一步：调用推理模型获取推理结果
        temp_content = ""

        try:
            # 获取推理模型和目标模型名称
            reasoning_model = other_params.get("reasoning_model")
            target_model = other_params.get("target_model")

            reasoning_cancel_flag = asyncio.Event()

            logger.info("推理模型%s输出开始", reasoning_model)
            # 流式调用推理模型
            async for chunk in self.reasoning_client.stream_chat(
                chat_id=chat_id,
                messages=messages,
                model=reasoning_model,
                model_arg=model_arg,
                other_params=other_params.get("reasoning_params"),
                cancel_flag=reasoning_cancel_flag
            ):
                # 如果取消标志被设置，就断开推理模型连接
                if cancel_flag.is_set():
                    reasoning_cancel_flag.set()
                    logger.info("用户取消请求")
                    return

                yield chunk

                # 解析内容
                delta = chunk.choices[0].delta
                content = delta.content
                reasoning_content = delta.reasoning_content

                if reasoning_content:
                    temp_content += reasoning_content

                # 如果推理模型的正式回答中有内容,我们就认为他思考链已经结束，就断开连接
                if content:
                    reasoning_cancel_flag.set()
                    logger.debug("推理模型已手动断开连接")
                    break

            if not temp_content:
                error_msg = "未能获取到有效的推理内容"
                logger.error(error_msg)
                raise ClientAPIError(error=error_msg)

            encoding = tiktoken.encoding_for_model("gpt-4o")
            input_tokens = encoding.encode(temp_content)
            logger.debug("输入 Tokens: %s", len(input_tokens))
            logger.debug("推理模型思考链: %s", temp_content)

            logger.info("思维链获取完毕,长度约为%s", len(temp_content))

            # 第二步：准备目标模型的输入
            target_messages = messages.copy()

            # 检查最后一条消息是否是用户消息
            if target_messages and target_messages[-1].get("role") == "user":
                # 获取原始用户问题
                original_user_content = target_messages[-1].get("content", "")

                combined_content = f"""
                ******The above is user information*****
                The following is the reasoning process of another model:****\n{temp_content}\n\n ****
                Based on this reasoning, combined with your knowledge,
                when the current reasoning conflicts with your knowledge,
                you are more confident that you can adopt your own knowledge,
                which is completely acceptable. Please provide the user with a complete answer directly.
                ***Notice, Here is your settings: SELF_TALK: off REASONING: off THINKING: off PLANNING: off THINKING_BUDGET: < 100 tokens ***:"""

                fixed_content = f"Here's my original input:\n{original_user_content}\n\n{combined_content}"

                target_messages[-1]["content"] = fixed_content
            else:
                raise ClientAPIError(error="未能获取到有效的用户消息")

            if cancel_flag.is_set():
                logger.info("用户取消请求")
                return

            # 第三步：流式调用目标模型
            logger.info("目标模型%s输出开始", target_model)

            target_cancel_flag = asyncio.Event()
            async for chunk in self.target_client.stream_chat(
                chat_id=chat_id,
                messages=target_messages,
                model=target_model,
                model_arg=model_arg,
                other_params=other_params.get("target_params"),
                cancel_flag=target_cancel_flag
            ):
                if cancel_flag.is_set():
                    target_cancel_flag.set()
                    logger.info("用户取消请求")
                    return
                yield chunk


        except Exception as e:
            error_msg = f"组合模型{model}请求处理异常: {str(e)}"
            logger.error(error_msg)
            raise
