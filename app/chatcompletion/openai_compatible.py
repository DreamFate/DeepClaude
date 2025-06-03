"""OpenAI兼容的流式响应对象"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import time

@dataclass
class OpenAIStreamDelta:
    """OpenAI响应中的delta对象"""
    content: Optional[str] = None
    role: Optional[str] = None
    reasoning_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class OpenAIStreamChoice:
    """OpenAI响应中的choice对象"""
    index: int = 0
    delta: OpenAIStreamDelta = field(default_factory=OpenAIStreamDelta)
    finish_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        result = {k: v for k, v in asdict(self).items() if k != 'delta' and v is not None}
        result['delta'] = self.delta.to_dict()
        return result

@dataclass
class OpenAIMessage:
    """OpenAI响应中的message对象"""
    content: Optional[str] = None
    role: Optional[str] = None
    reasoning_content: Optional[str] = None
    type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class OpenAIChoice:
    """OpenAI响应中的choice对象"""
    index: int = 0
    finish_reason: Optional[str] = None
    message: OpenAIMessage = field(default_factory=OpenAIMessage)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        result = {k: v for k, v in asdict(self).items() if k != 'message' and v is not None}
        result['message'] = self.message.to_dict()
        return result

@dataclass
class PromptTokensDetails:
    """输入数据的Token细粒度分类"""
    audio_tokens: Optional[int] = None
    text_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    video_tokens: Optional[int] = None
    image_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class CompletionTokensDetails:
    """输出转换为Token后的详细信息"""
    accepted_prediction_tokens: Optional[int] = None
    audio_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    rejected_prediction_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class OpenAIUsage:
    """OpenAI响应中的usage对象，表示Token使用情况"""
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    completion_tokens_details: Optional[CompletionTokensDetails] = None
    prompt_tokens_details: Optional[PromptTokensDetails] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        result = {k: v for k, v in asdict(self).items()
                 if k not in ['completion_tokens_details', 'prompt_tokens_details'] and v is not None}

        if self.completion_tokens_details:
            result['completion_tokens_details'] = self.completion_tokens_details.to_dict()

        if self.prompt_tokens_details:
            result['prompt_tokens_details'] = self.prompt_tokens_details.to_dict()

        return result

@dataclass
class OpenAIStreamCompletion:
    """OpenAI兼容的流式响应对象"""
    id: str
    object: str = "chat.completion.chunk"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[OpenAIStreamChoice] = field(default_factory=list)
    # 这里为供应商拿回来的chat_id
    provider_chat_id: Optional[str] = None
    usage: Optional[OpenAIUsage] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        result = {k: v for k, v in asdict(self).items() if k != 'choices' and v is not None}
        result['choices'] = [choice.to_dict() for choice in self.choices]

        if self.usage:
            result['usage'] = self.usage.to_dict()

        return result

@dataclass
class OpenAICompletion:
    """OpenAI兼容的非流式响应对象"""
    id: str
    object: str = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[OpenAIChoice] = field(default_factory=list)
    # 这里为供应商拿回来的chat_id
    provider_chat_id: Optional[str] = None
    usage: Optional[OpenAIUsage] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，忽略None值"""
        result = {k: v for k, v in asdict(self).items() if k != 'choices' and v is not None}
        result['choices'] = [choice.to_dict() for choice in self.choices]

        if self.usage:
            result['usage'] = self.usage.to_dict()

        return result
