"""Claude请求数据格式化"""

from typing import Dict, List, Any, Tuple

# Claude 支持的参数列表
CLAUDE_SUPPORTED_PARAMS = [
    "model",
    "messages",
    "max_tokens",
    "container",
    "mcp_servers",
    "metadata",
    "service_tier",
    "stop_sequences",
    "stream",
    "system",
    "temperature",
    "thinking",
    "tool_choice",
    "tools",
    "top_p",
    "top_k"
]

# 参数名称映射（OpenAI 参数名 -> Claude 参数名）
PARAM_MAPPING = {
    "max_completion_tokens": "max_tokens",
    "stop": "stop_sequences"
}

def format_claude_request(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    model_arg: Dict[str, Any],
    stream: bool = True
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """格式化 Claude 请求数据

    Args:
        api_key: API密钥
        model: 模型名称
        messages: 消息列表
        model_arg: 模型参数
        stream: 是否流式输出

    Returns:
        headers: 请求头
        data: 请求体
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # 复制消息列表，避免修改原始列表
    messages_copy = messages.copy()

    # 查找并提取 system 消息
    system_content = None
    for i, message in enumerate(messages_copy):
        if message.get("role") == "system":
            system_content = message.get("content", "")
            # 从消息列表中移除 system 消息
            messages_copy.pop(i)
            break

    # 基础请求结构
    data = {
        "model": model,
        "messages": messages_copy,
        "stream": stream
    }

    # 如果找到 system 消息，添加到 data 中
    if system_content:
        data["system"] = system_content

    # 处理支持的参数
    for param in CLAUDE_SUPPORTED_PARAMS:
        if param in model_arg and model_arg[param] is not None:
            data[param] = model_arg[param]

    # 处理参数映射
    for openai_param, claude_param in PARAM_MAPPING.items():
        if openai_param in model_arg and model_arg[openai_param] is not None:
            # 如果目标参数尚未设置，则使用映射的参数值
            if claude_param not in data or data[claude_param] is None:
                data[claude_param] = model_arg[openai_param]

    # 确保 max_tokens 有默认值
    if "max_tokens" not in data or data["max_tokens"] is None:
        data["max_tokens"] = 8192

    return headers, data
