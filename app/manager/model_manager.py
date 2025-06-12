"""模型管理器,参数验证和请求处理"""

from typing import Dict, Any, Tuple, List, Optional
import asyncio
import time
import aiohttp

from fastapi.responses import StreamingResponse

from app.utils.logger import logger
from app.db.db_manager import db_manager
from app.db.db_config import ModelConfig,ProviderConfig,CompositeModelConfig
from app.clients.claude_client import ClaudeClient
from app.clients.openai_compatible_client import OpenAICompatibleClient
from app.clients.deepseek_client import DeepSeekClient
from app.EnsembleModel.composite_model import CompositeModel


class ModelManager:
    """模型管理器，处理请求参数"""

    def __init__(self):
        """初始化模型管理器"""
        self.db_manager = db_manager
        # 获取系统配置信息
        self.config = self.get_system_config()
        # 请求取消映射，用于存储请求ID到取消事件的映射
        self.cancel_events: Dict[str, asyncio.Event] = {}
        # 创建TCP连接池
        self.connector = self._create_tcp_connector()

    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置信息

        Returns:
            Dict[str, Any]: 系统配置信息
        """
        return self.db_manager.get_all_settings()

    def get_model_details(
        self,
        model_name: str,
        model_type: str,
    ) -> Tuple[Dict[str, Any], str]:
        """获取模型详细配置

        Args:
            model_name: 模型名称
            model_type: 模型类型

        Returns:
            Tuple[Dict[str, Any], str]: (推理模型配置, 模型类型)

        Raises:
            ValueError: 模型不存在或无效
        """

        if model_type in ("reasoner", "general"):
            model =self.db_manager.get_model(model_name=model_name,is_valid=True)
            if not model:
                raise ValueError(f"模型 '{model_name}' 不存在")
            return model,model.model_type

        if model_type == "composite":
            model = self.db_manager.get_composite_model(model_name,is_valid=True)
            if not model:
                raise ValueError(f"组合模型 '{model_name}' 不存在")
            return model, "composite"

        model =self.db_manager.get_model(model_name=model_name,is_valid=True)
        if not model:
            model = self.db_manager.get_composite_model(model_name,is_valid=True)
            if not model:
                raise ValueError(f"模型 '{model_name}' 不存在")
            return model, "composite"
        return model, model.model_type

    def validate_and_prepare_params(
        self,
        body: Dict[str, Any],
    ) -> Tuple[List[Dict[str, str]], str, str, Dict[str, Optional[float]], bool]:
        """验证和准备请求参数

        Args:
            body: 请求体

        Returns:
            Tuple[List[Dict[str, str]], str, str, Dict[str, Optional[float]], bool]:
                (消息列表, 模型名称, 模型类型, 模型参数, 流式输出)

        Raises:
            ValueError: 参数验证失败时抛出
        """
        # 获取基础信息
        messages = body.get("messages")
        model = body.get("model")
        stream = body.get("stream", False)
        model_type: str = body.get("model_type", "")

        if not model:
            raise ValueError("必须指定模型名称")

        if not messages:
            raise ValueError("消息列表不能为空")

        # 提取所有模型参数，排除已经单独获取的参数
        model_args = {}
        excluded_keys = {"messages", "model", "stream", "model_type"}
        for key, value in body.items():
            if key not in excluded_keys:
                model_args[key] = value

        return messages, model, model_type, model_args, stream

    def create_instance(self, provider: ProviderConfig, model_format: str):
        """创建模型实例

        Args:
            provider_id: 供应商ID
            model_format: 模型格式

        Returns:
            Any: 模型实例
        """
        isproxy_open = self.config.get("proxy_address") if provider.is_proxy_open else None
        api_url = f"{provider.api_base_url}/{provider.api_request_address}"
        if model_format == "openai":
            instance = OpenAICompatibleClient(
                api_key=provider.api_key,
                api_url=api_url,
                connector=self.connector,
                proxy= isproxy_open,
            )
            return instance
        if model_format == "anthropic":
            instance = ClaudeClient(
                api_key=provider.api_key,
                api_url=api_url,
                connector=self.connector,
                proxy= isproxy_open,
            )
            return instance
        if model_format == "reasoner":
            instance = DeepSeekClient(
                api_key=provider.api_key,
                api_url=api_url,
                connector=self.connector,
                proxy= isproxy_open,
            )
            return instance

        raise ValueError(f"不支持的供应商格式: {model_format}")


    async def process_request(self, body: Dict[str, Any]) -> Any:
        """处理聊天完成请求

        Args:
            body: 请求体

        Returns:
            Any: 响应对象，可能是 StreamingResponse 或 Dict

        Raises:
            ValueError: 参数验证或处理失败时抛出
        """
        # 验证和准备参数
        messages, model, model_type, model_args, stream = self.validate_and_prepare_params(body)

        # 获取模型详细配置
        model_details, model_type = self.get_model_details(model, model_type)

        # 组合模型都用流式
        if model_type == "composite":
            return await self.composite_model_response(model,model_details, messages, model_args)

        return await self.default_response(model_details, messages, model_args, stream)


    async def default_response(
        self,
        model_details:ModelConfig,
        messages:List[Dict[str, str]],
        model_args:Dict[str, Any],
        stream:bool,
    ) -> Any:
        """处理默认响应"""

        provider: ProviderConfig = self.db_manager.get_provider(model_details.provider_id)
        model_instance = self.create_instance(provider, model_details.model_format)

        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"

        other_params = {
            "is_origin_reasoning": model_details.is_origin_reasoning,
        }

        # 原始输出
        if model_details.is_origin_output:
            if stream:
                headers,data = model_instance.format_data(
                    model_instance.api_key, model_details.model_id, messages,model_args, stream=True)
                return StreamingResponse(
                    model_instance.original_stream_chat(
                        headers=headers,
                        data=data,
                    ),
                    media_type="text/event-stream",
                )
            headers,data = model_instance.format_data(
                model_instance.api_key, model_details.model_id, messages,model_args, stream=False)
            return await model_instance.original_chat(
                headers=headers,
                data=data,
            )

        # 处理请求
        if stream:
            return StreamingResponse(
                model_instance.stream_chat(
                    chat_id=chat_id,
                    messages=messages,
                    model=model_details.model_id,
                    model_arg=model_args,
                    other_params=other_params,
                ),
                media_type="text/event-stream",
            )
        return await model_instance.chat(
            chat_id=chat_id,
            messages=messages,
            model=model_details.model_id,
            model_arg=model_args,
            other_params=other_params,
        )

    def composite_model_response(
        self,
        model:str,
        model_details:CompositeModelConfig,
        messages:List[Dict[str, str]],
        model_args:Dict[str, Any],
    ) -> Any:
        """处理组合模型请求

        Args:
            model: 模型名称
            model_details: 组合模型配置
            messages: 消息列表
            model_args: 模型参数
            stream: 是否流式输出

        Returns:
            Any: 组合模型实例
        """
        # 获取组合模型配置
        reasoner_model_id = model_details.reasoner_model_id
        general_model_id = model_details.general_model_id

        reasoner_model: Optional[ModelConfig] = self.db_manager.get_model(model_id=reasoner_model_id,is_valid=True)
        general_model: Optional[ModelConfig] = self.db_manager.get_model(model_id=general_model_id,is_valid=True)

        if not reasoner_model or not general_model:
            raise ValueError("组合模型配置不完整")

        # 获取reasoner实例
        reasoner_provider_id = reasoner_model.provider_id
        reasoner_model_format = reasoner_model.model_format
        reasoner_instance = self.create_instance(reasoner_provider_id, reasoner_model_format)

        # 获取general实例
        general_provider_id = general_model.provider_id
        general_model_format = general_model.model_format
        general_instance = self.create_instance(general_provider_id, general_model_format)

        composite_model = CompositeModel(
            reasoning_client=reasoner_instance,
            target_client=general_instance,
        )

        chat_id = f"chatcmpl-{hex(int(time.time() * 1000))[2:]}"

        other_params = {
            "reasoning_model": reasoner_model.model_id,
            "target_model": general_model.model_id,
            "reasoning_params": {
                "is_origin_reasoning": reasoner_model.is_origin_reasoning,
            },
            "target_params": None,
        }

        cancel_flag = self.register_cancel_event(chat_id)
        return StreamingResponse(composite_model.stream_chat(
                chat_id=chat_id,
                messages=messages,
                model=model,
                model_arg=model_args,
                other_params=other_params,
                cancel_flag=cancel_flag,
            ),
            media_type="text/event-stream",
        )

    def get_model_list(self) -> List[Dict[str, Any]]:
        """获取可用模型列表

        Returns:
            List[Dict[str, Any]]: 模型列表
        """
        models = []
        local_model = self.db_manager.get_all_models(is_valid=True)
        local_composite_model = self.db_manager.get_all_composite_models(is_valid=True)
        for model_id in local_model:
            models.append({
                "id": model_id,
                "object": "model",
                "created": 1740268800,
                "owned_by": "deepclaude",
                "permission": {
                    "id": "modelperm-{}".format(model_id),
                    "object": "model_permission",
                    "created": 1740268800,
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group": None,
                    "is_blocking": False
                },
                "root": "deepclaude",
                "parent": None
            })
        for model_id in local_composite_model:
            models.append({
                "id": model_id,
                "object": "model",
                    "created": 1740268800,
                    "owned_by": "deepclaude",
                    "permission": {
                        "id": "modelperm-{}".format(model_id),
                        "object": "model_permission",
                        "created": 1740268800,
                        "allow_create_engine": False,
                        "allow_sampling": True,
                        "allow_logprobs": True,
                        "allow_search_indices": False,
                        "allow_view": True,
                        "allow_fine_tuning": False,
                        "organization": "*",
                        "group": None,
                        "is_blocking": False
                    },
                    "root": "deepclaude",
                    "parent": None
                })
        return models



    def get_config(self) -> Dict[str, Any]:
        """获取当前配置

        Returns:
            Dict[str, Any]: 当前配置
        """
        # 每次都从文件重新加载最新配置
        self.config = self.db_manager.get_all_settings()
        return self.config

    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置

        Args:
            config: 新配置

        Raises:
            ValueError: 配置无效
        """
        # 验证配置
        if not isinstance(config, dict):
            raise ValueError("配置必须是字典")

        # 更新配置
        self.config = config

        # # 清空模型实例缓存，以便重新创建
        # self.model_cache.clear()
        # logger.info("配置已更新，模型实例缓存已清空")

        # # 保存配置到文件
        # with open(self.config_path, "w", encoding="utf-8") as f:
        #     json.dump(config, f, ensure_ascii=False, indent=4)

    def register_cancel_event(self, request_id: str) -> asyncio.Event:
        """注册一个取消事件

        Args:
            request_id: 请求ID

        Returns:
            asyncio.Event: 取消事件对象
        """
        event = asyncio.Event()
        self.cancel_events[request_id] = event
        return event

    def cancel_request(self, request_id: str) -> bool:
        """取消指定ID的请求

        Args:
            request_id: 要取消的请求ID

        Returns:
            bool: 是否成功取消
        """
        if request_id in self.cancel_events:
            self.cancel_events[request_id].set()
            logger.info("已触发请求 %s 的取消事件", request_id)
            return True
        return False

    def cleanup_cancel_event(self, request_id: str) -> None:
        """清理取消事件

        Args:
            request_id: 请求ID
        """
        if request_id in self.cancel_events:
            del self.cancel_events[request_id]
            logger.info("已清理请求 %s 的取消事件", request_id)

    def _create_tcp_connector(self) -> aiohttp.TCPConnector:
        """创建TCP连接池"""
        # 从配置中获取连接池参数
        config = self.config

        # 连接池大小限制
        limit = config.get("tcp_connector_limit").setting_value or 100
        # 每个主机的连接限制
        limit_per_host = config.get("tcp_connector_limit_per_host").setting_value or 0
        # 连接保持活跃时间(秒)
        keepalive_timeout = config.get("tcp_keepalive_timeout").setting_value or 30.0

        logger.info(
            "创建TCP连接池: limit=%s, limit_per_host=%s, keepalive_timeout=%s",
            limit, limit_per_host, keepalive_timeout
        )

        return aiohttp.TCPConnector(
            limit=limit,
            limit_per_host=limit_per_host,
            keepalive_timeout=keepalive_timeout,
            ssl=True,
            force_close=False,
            enable_cleanup_closed=True
        )

model_manager = ModelManager()
