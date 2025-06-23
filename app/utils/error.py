"""错误处理工具"""
import json
import aiohttp

class ClientAPIError(Exception):
    """自定义客户端API异常"""
    def __init__(self, status_code=500, error=None, detail=None):
        self.detail = detail
        self.status_code = status_code
        self.error = error

async def handle_http_error(response: aiohttp.ClientResponse):
    """
    处理HTTP响应错误，解析供应商返回的错误信息
    """
    status = response.status
    try:
        # 尝试解析为json
        error_body = await response.json()
        # 兼容常见供应商格式
        if "error" in error_body:
            error = error_body.get("error")
            # OpenAI: {"error": {"message": "...", "type": "...", "code": "..."}}
            error_message = str(error)
            # 处理常见的错误信息
            if "Input length" in error_message:
                detail = "错误可能情况：输入的上下文内容过长，超过了模型的最大处理长度限制。请减少输入内容或分段处理。"
            elif "InvalidParameter" in error_message:
                detail = "错误可能情况：请求参数无效，请检查输入内容。"
            elif "BadRequest" in error_message:
                detail = "错误可能情况：请求格式错误，请检查输入内容。"
            else:
                detail = None

        else:
            # 其他结构
            error = str(error_body)
            detail = None
    except (aiohttp.ContentTypeError, json.JSONDecodeError):
        # 不是json，直接取文本
        error = await response.text()
        detail = None

    raise ClientAPIError(status_code=status, error=error, detail=detail)
