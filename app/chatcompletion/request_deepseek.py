"""DeepSeek请求数据格式化"""

from typing import Dict, List, Any,Tuple

# DeepSeek 支持的参数列表
DEEPSEEK_SUPPORTED_PARAMS = [
    "messages",
    "model",
    "frequency_penalty",
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "presence_penalty",
    "stop",
    "stream",
    "stream_options",
    "response_format",
    "tools",
    "tool_choice",
    "logprobs",
    "top_logprobs"
]

# 参数名称映射（OpenAI 参数名 -> DeepSeek 参数名）
PARAM_MAPPING = {
    "max_completion_tokens": "max_tokens"
}

def format_deepseek_request(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    model_arg: Dict[str, Any],
    stream: bool = True
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """格式化 DeepSeek 请求数据

    Args:
        model: 模型名称
        messages: 消息列表
        model_arg: 模型参数
        stream: 是否流式输出

    Returns:
        格式化后的请求数据
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 基础请求结构
    data = {
        "model": model,
        "messages": messages,
        "stream": stream
    }

    # 处理支持的参数
    for param in DEEPSEEK_SUPPORTED_PARAMS:
        if param in model_arg and model_arg[param] is not None:
            data[param] = model_arg[param]

    # 处理参数映射
    for openai_param, deepseek_param in PARAM_MAPPING.items():
        if openai_param in model_arg and model_arg[openai_param] is not None:
            # 如果目标参数尚未设置，则使用映射的参数值
            if deepseek_param not in data or data[deepseek_param] is None:
                data[deepseek_param] = model_arg[openai_param]

    return headers,data
