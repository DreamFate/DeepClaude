"""数据库配置"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json

@dataclass
class ModelConfig:
    """模型配置"""
    id: Optional[int] = None
    model_name: str = ""
    model_id: str = ""
    provider_id: Optional[int] = None
    model_type: str = ""
    model_format: str = ""
    is_origin_reasoning: bool = False
    is_valid: bool = False
    is_origin_output: bool = False


    @classmethod
    def from_db_row(cls, row: Dict[str, Any]):
        """从数据库行创建模型配置对象"""
        return cls(
            id=row["id"],
            model_name=row["model_name"],
            model_id=row["model_id"],
            provider_id=row["provider_id"],
            model_type=row["model_type"],
            model_format=row["model_format"],
            is_origin_reasoning=bool(row["is_origin_reasoning"]),
            is_valid=bool(row["is_valid"]),
            is_origin_output=bool(row["is_origin_output"]),
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库字典"""
        return {
            "id": self.id,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "model_type": self.model_type,
            "model_format": self.model_format,
            "is_origin_reasoning": 1 if self.is_origin_reasoning else 0,
            "is_valid": 1 if self.is_valid else 0,
            "is_origin_output": 1 if self.is_origin_output else 0,
        }

@dataclass
class ProviderConfig:
    """供应商配置数据类"""
    id: Optional[int] = None
    provider_name: str = ""
    api_key: str = ""
    api_base_url: str = ""
    api_request_address: str = ""
    provider_format: str = ""
    is_proxy_open: bool = False
    is_valid: bool = False

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]):
        """从数据库行创建供应商配置对象

        Args:
            row: 数据库查询结果行

        Returns:
            ProviderConfig: 供应商配置对象
        """
        return cls(
            id=row["id"],
            provider_name=row["provider_name"],
            api_key=row["api_key"],
            api_base_url=row["api_base_url"],
            api_request_address=row["api_request_address"],
            provider_format=row["provider_format"],
            is_valid=bool(row["is_valid"]),
            is_proxy_open=bool(row["is_proxy_open"]),
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库字典

        Returns:
            Dict[str, Any]: 适用于数据库操作的字典
        """
        return {
            "id": self.id,
            "provider_name": self.provider_name,
            "api_key": self.api_key,
            "api_base_url": self.api_base_url,
            "api_request_address": self.api_request_address,
            "provider_format": self.provider_format,
            "is_valid": 1 if self.is_valid else 0,
            "is_proxy_open": 1 if self.is_proxy_open else 0
        }

@dataclass
class CompositeModelConfig:
    """组合模型配置数据类"""
    id: Optional[int] = None
    model_name: str = ""
    reasoner_model_id: int = 0
    general_model_id: int = 0
    is_valid: bool = False

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]):
        """从数据库行创建组合模型配置对象

        Args:
            row: 数据库查询结果行

        Returns:
            CompositeModelConfig: 组合模型配置对象
        """
        return cls(
            id=row["id"],
            model_name=row["model_name"],
            reasoner_model_id=row["reasoner_model_id"],
            general_model_id=row["general_model_id"],
            is_valid=bool(row["is_valid"])
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库字典

        Returns:
            Dict[str, Any]: 适用于数据库操作的字典
        """
        return {
            "id": self.id,
            "model_name": self.model_name,
            "reasoner_model_id": self.reasoner_model_id,
            "general_model_id": self.general_model_id,
            "is_valid": 1 if self.is_valid else 0
        }

class SystemSetting:
    """系统设置数据类"""
    key: str = ""
    value: Any = None
    type_name: str = "str"

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]):
        """从数据库行创建系统设置对象

        Args:
            row: 数据库查询结果行

        Returns:
            SystemSetting: 系统设置对象
        """
        setting = cls(
            key=row["setting_key"],
            type_name=row["setting_type"]
        )

        # 根据类型转换值
        value = row["setting_value"]
        if setting.type_name == "int":
            setting.value = int(value)
        elif setting.type_name == "float":
            setting.value = float(value)
        elif setting.type_name == "bool":
            setting.value = value.lower() in ("true", "1", "yes")
        elif setting.type_name == "json":
            setting.value = json.loads(value)
        else:
            setting.value = value

        return setting

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库字典

        Returns:
            Dict[str, Any]: 适用于数据库操作的字典
        """
        # 确定值的类型和字符串表示
        if isinstance(self.value, int) and self.type_name != "bool":
            type_name = "int"
            str_value = str(self.value)
        elif isinstance(self.value, float):
            type_name = "float"
            str_value = str(self.value)
        elif isinstance(self.value, bool):
            type_name = "bool"
            str_value = "true" if self.value else "false"
        elif isinstance(self.value, (dict, list)):
            type_name = "json"
            str_value = json.dumps(self.value, ensure_ascii=False)
        else:
            type_name = "str"
            str_value = str(self.value)

        return {
            "setting_key": self.key,
            "setting_value": str_value,
            "setting_type": type_name
        }
