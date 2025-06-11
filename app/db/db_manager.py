"""
使用连接池的数据库管理器实现
"""

import sqlite3
import logging
from typing import Dict, Any, Optional,Callable
import functools

from app.utils.db_pool import get_db_connection, close_db_pool,get_db_pool
from app.db.db_config import ProviderConfig,ModelConfig,CompositeModelConfig,SystemSetting

# 设置日志
logger = logging.getLogger("db_manager_pool")

# 在文件顶部添加自定义异常类
class DBManagerError(Exception):
    """数据库管理器中的非数据库相关错误"""

def handle_db_errors(operation_name: str):
    """处理数据库错误的装饰器

    Args:
        operation_name: 操作名称，用于日志记录
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except sqlite3.Error as e:
                error_msg = f"{operation_name},有数据库相关错误: {str(e)}"
                logger.error(error_msg)
                raise sqlite3.Error(error_msg) from e
            except Exception as e:
                error_msg = f"{operation_name},有其他错误: {str(e)}"
                logger.error(error_msg)
                raise DBManagerError(error_msg) from e
        return wrapper
    return decorator


class DBManager:
    """使用连接池的数据库管理器"""

    def __init__(self, db_path=None):
        """初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认为None，使用默认路径
        """
        # 数据库路径
        self.db_path = db_path

        # 初始化数据库表
        self._init_db()
        self._init_system_settings()

    # 应用程序关闭时关闭连接池
    def close_db_manager(self):
        """关闭数据库连接池

        在应用程序关闭时调用，确保所有数据库连接被正确关闭
        """
        close_db_pool()

    def open_db_manager(self):
        """打开数据库连接池

        在应用程序启动时调用，确保所有数据库连接被正确打开
        """
        get_db_pool()

    @handle_db_errors("初始化系统设置")
    def _init_system_settings(self):
        """初始化系统设置数据

        Args:
            db: 数据库连接
        """
        # 检查是否已有数据
        with get_db_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM system_settings")
            row = cursor.fetchone()
            if row and row["count"] > 0:
                logger.debug("系统设置数据已存在，跳过默认设置")
                return

            # 默认系统设置
            default_settings = [
                # 日志级别
                ("log_level", "INFO", "str"),
                # 允许的源
                ("allow_origins", "[\"*\"]", "json"),
                # API密钥
                ("api_key", "123456", "str"),
                # 代理设置
                ("proxy_open", "false", "bool"),
                ("proxy_address", "127.0.0.1:7890", "str"),
                # 缓存大小
                ("model_cache_size", "5", "int"),
                # 保存deepseek token
                ("save_deepseek_tokens", "false", "bool"),
                ("save_deepseek_tokens_max_tokens", "5", "int"),
            ]

            # 插入默认设置
            for key, value, type_name in default_settings:
                cursor.execute("""
                INSERT OR IGNORE INTO system_settings (setting_key, setting_value, setting_type)
                VALUES (?, ?, ?)
                """, (key, value, type_name))

            logger.info("初始化了 %d 条系统设置数据",len(default_settings))

    @handle_db_errors("初始化数据库")
    def _init_db(self):
        """初始化数据库，创建必要的表"""
        with get_db_connection() as db:
            # 创建供应商表
            db.execute('''
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_name TEXT NOT NULL UNIQUE,  -- 供应商名称，如 'openai', 'anthropic', 'deepseek' 等
                api_key TEXT NOT NULL,               -- API密钥
                api_base_url TEXT NOT NULL,          -- 基础URL
                api_request_address TEXT NOT NULL,   -- 请求地址
                provider_format TEXT NOT NULL,       -- 供应商格式，如 'openrouter', 'anthropic', 'oneapi' , 'deepseek' 等
                is_proxy_open INTEGER,               -- 是否启用代理
                is_valid INTEGER NOT NULL            -- 是否有效
            )
            ''')

            # 创建models表
            db.execute('''
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,                   -- 对应的供应商ID
                model_type TEXT NOT NULL,                       -- 'reasoner' 或 'general'
                model_id TEXT NOT NULL,                         -- 模型ID
                model_name TEXT NOT NULL UNIQUE,                -- 模型名称
                model_format TEXT NOT NULL,                     -- 模型格式，如 'deepseek', 'anthropic', 'openai_compatible' 等
                is_valid INTEGER NOT NULL,                      -- 是否有效
                is_origin_reasoning INTEGER,                    -- 仅对推理模型有意义
                is_origin_output INTEGER,                       -- 是否使用原生输出
                FOREIGN KEY (provider_id) REFERENCES providers(id)
            )
            ''')

            # 创建composite_models表
            db.execute('''
            CREATE TABLE IF NOT EXISTS composite_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE,                    -- 组合模型名称
                reasoner_model_id INTEGER NOT NULL,                 -- 推理模型ID
                general_model_id INTEGER NOT NULL,                  -- 通用模型ID
                is_valid INTEGER NOT NULL,                          -- 是否有效
                FOREIGN KEY (reasoner_model_id) REFERENCES models(id),
                FOREIGN KEY (general_model_id) REFERENCES models(id)
            )
            ''')

            # 创建system_settings表
            db.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,                    -- 设置值
                setting_type TEXT NOT NULL                      -- 用于指示值的类型（整数、布尔、字符串等）
            )
            ''')

            logger.info("数据库初始化成功")

    # ===== Providers 操作 =====

    @handle_db_errors("获取所有供应商配置")
    def get_all_providers(self, is_valid: Optional[bool] = None) -> Dict[str, ProviderConfig]:
        """获取所有供应商配置

        Args:
            is_valid: 是否只返回有效的供应商配置

        Returns:
            Dict[str, ProviderConfig]: 供应商配置字典，键为供应商名称
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, provider_name, api_key, api_base_url, api_request_address, provider_format, is_valid, is_proxy_open
            FROM providers
            WHERE 1=1
            """

            params = []
            if is_valid:
                sql += " AND is_valid = ?"
                params.append(is_valid)

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            result = {}
            for row in rows:
                config = ProviderConfig.from_db_row(row)
                result[config.provider_name] = config

            return result

    @handle_db_errors("获取指定供应商配置")
    def get_provider(
        self,
        provider_name: Optional[str] = None,
        provider_id: Optional[int] = None
    ) -> Optional[ProviderConfig]:
        """获取指定供应商配置

        Args:
            provider_name: 供应商名称
            provider_id: 供应商ID

        Returns:
            Optional[ProviderConfig]: 供应商配置，如果不存在则返回None
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, provider_name, api_key, api_base_url, api_request_address, provider_format, is_valid, is_proxy_open
            FROM providers
            WHERE 1=1
            """

            params = []
            if provider_name:
                sql += " AND provider_name = ?"
                params.append(provider_name)
            if provider_id:
                sql += " AND id = ?"
                params.append(provider_id)

            db.execute(sql, params)

            row = db.fetchone()

            if row:
                return ProviderConfig.from_db_row(row)
            return None

    @handle_db_errors("保存供应商配置")
    def save_provider(self, config: ProviderConfig) -> bool:
        """保存供应商配置

        Args:
            config: 供应商配置

        Returns:
            bool: 是否保存成功
        """

        db_dict = config.to_db_dict()

        with get_db_connection() as db:
            if config.id:
                # 更新
                db.execute("""
                UPDATE providers SET
                    provider_name = :provider_name,
                    api_key = :api_key,
                    api_base_url = :api_base_url,
                    api_request_address = :api_request_address,
                    provider_format = :provider_format,
                    is_valid = :is_valid,
                    is_proxy_open = :is_proxy_open
                WHERE id = :id
                """, db_dict)
            else:
                # 插入
                db.execute("""
                INSERT INTO providers (
                    provider_name, api_key, api_base_url, api_request_address, provider_format, is_valid, is_proxy_open
                ) VALUES (:provider_name, :api_key, :api_base_url, :api_request_address, :provider_format, :is_valid, :is_proxy_open)
                """, db_dict)
            return True

    @handle_db_errors("删除供应商配置")
    def delete_provider(self, provider_id: int) -> bool:
        """删除供应商配置

        Args:
            provider_id: 供应商ID

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
            return True

    # ===== Models 操作 =====

    @handle_db_errors("获取所有模型配置")
    def get_all_models(
        self,
        model_type:Optional[str]=None,
        is_valid:Optional[bool]=None
    ) -> Dict[str, ModelConfig]:
        """获取所有模型配置

        Args:
            model_type: 可选，模型类型过滤
            is_valid: 可选，是否只获取有效的模型

        Returns:
            Dict[str, ModelConfig]: 模型配置字典，键为模型名称
        """
        with get_db_connection() as db:
            # 基础SQL查询
            sql = """
            SELECT id, model_id, model_name, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
            is_origin_output
            FROM models
            WHERE 1=1
            """

            # 添加过滤条件
            params = []
            if model_type:
                sql += " AND model_type = ?"
                params.append(model_type)
            if is_valid:
                is_valid_int = 1 if is_valid else 0
                sql += " AND is_valid = ?"
                params.append(is_valid_int)

            # 执行查询
            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            # 处理结果
            result = {}
            for row in rows:
                config = ModelConfig.from_db_row(row)
                result[config.model_name] = config

            return result

    @handle_db_errors("获取指定模型配置")
    def get_model(
        self,
        model_name: Optional[str] = None,
        model_id: Optional[str] = None,
        is_valid: Optional[bool] = None
    ) -> Optional[ModelConfig]:
        """获取指定模型配置

        Args:
            model_name: 模型名称
            model_id: 模型ID

        Returns:
            Optional[ModelConfig]: 模型配置，如果不存在则返回None
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, model_id, model_name, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
            is_origin_output
            FROM models
            WHERE 1=1
            """

            params = []
            if model_name:
                sql += " AND model_name = ?"
                params.append(model_name)
            if model_id:
                sql += " AND model_id = ?"
                params.append(model_id)
            if is_valid:
                sql += " AND is_valid = ?"
                params.append(is_valid)

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            row = db.fetchone()

            if row:
                return ModelConfig.from_db_row(row)
            return None

    @handle_db_errors("保存模型配置")
    def save_model(self, config: ModelConfig) -> bool:
        """保存模型配置

        Args:
            config: 模型配置

        Returns:
            bool: 是否保存成功
        """
        db_dict = config.to_db_dict()

        with get_db_connection() as db:
            if config.id:
                # 更新
                db.execute('''
                UPDATE models SET
                    model_id = :model_id,
                    provider_id = :provider_id,
                    is_origin_reasoning = :is_origin_reasoning,
                    is_valid = :is_valid,
                    model_type = :model_type,
                    model_format = :model_format,
                    is_origin_output = :is_origin_output
                WHERE id = :id
                ''', db_dict)
            else:
                # 插入
                db.execute('''
                INSERT INTO models (
                    model_name, model_id, api_key, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
                    is_origin_output
                ) VALUES (:model_name, :model_id, :api_key, :provider_id, :is_origin_reasoning, :is_valid, :model_type, :model_format, :is_origin_output)
                ''', db_dict)

            return True

    @handle_db_errors("删除模型配置")
    def delete_model(self, models_id: int) -> bool:
        """删除模型配置

        Args:
            models_id: 模型ID

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            db.execute("DELETE FROM models WHERE id = ?", (models_id,))
            return True

    # ===== Composite Models 操作 =====

    @handle_db_errors("获取所有组合模型配置")
    def get_all_composite_models(self, is_valid=None) -> Dict[str, CompositeModelConfig]:
        """获取所有组合模型配置

        Args:
            is_valid: 是否只获取有效的组合模型

        Returns:
            Dict[str, CompositeModelConfig]: 组合模型配置字典，键为模型名称
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, model_name, is_valid,
                    reasoner_model_id,
                    general_model_id
            FROM composite_models
            WHERE 1=1
            """

            params = []
            if is_valid:
                sql += " AND is_valid = ?"
                params.append(is_valid)

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            result = {}
            for row in rows:
                config = CompositeModelConfig.from_db_row(row)
                result[config.model_name] = config

            return result

    @handle_db_errors("获取指定组合模型配置")
    def get_composite_model(
        self,
        model_name: Optional[str]=None,
        model_id:Optional[str]=None,
        is_valid:Optional[bool]=None
    ) -> Optional[CompositeModelConfig]:
        """获取指定组合模型配置

        Args:
            model_name: 模型名称
            model_id: 模型ID
            is_valid: 是否只获取有效的组合模型

        Returns:
            Optional[CompositeModelConfig]: 组合模型配置，如果不存在则返回None
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, model_name, is_valid,
                    reasoner_model_id,
                    general_model_id
            FROM composite_models
            WHERE 1=1
            """

            params = []
            if model_name:
                sql += " AND model_name = ?"
                params.append(model_name)
            if model_id:
                sql += " AND model_id = ?"
                params.append(model_id)
            if is_valid:
                sql += " AND is_valid = ?"
                params.append(is_valid)

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            row = db.fetchone()

            if row:
                return CompositeModelConfig.from_db_row(row)
            return None

    @handle_db_errors("保存组合模型配置")
    def save_composite_model(self, config: CompositeModelConfig) -> bool:
        """保存组合模型配置

        Args:
            config: 组合模型配置

        Returns:
            bool: 是否保存成功
        """
        db_dict = config.to_db_dict()

        with get_db_connection() as db:
            if config.id:
                # 更新
                db.execute("""
                UPDATE composite_models SET
                    reasoner_model_id = :reasoner_model_id,
                    general_model_id = :general_model_id,
                    is_valid = :is_valid
                WHERE id = :id
                """, db_dict)
            else:
                # 插入
                db.execute("""
                INSERT INTO composite_models (
                    model_name, reasoner_model_id, general_model_id, is_valid
                ) VALUES (:model_name, :reasoner_model_id, :general_model_id, :is_valid)
                """, db_dict)

            return True

    @handle_db_errors("删除组合模型配置")
    def delete_composite_model(self, composite_id: int) -> bool:
        """删除组合模型配置

        Args:
            composite_id: 组合模型ID

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            db.execute("DELETE FROM composite_models WHERE id = ?", (composite_id,))
            return True

    # ===== 系统设置操作 =====

    @handle_db_errors("获取系统设置")
    def get_setting(self, key: str) -> Optional[SystemSetting]:
        """获取系统设置

        Args:
            key: 设置键名

        Returns:
            Optional[SystemSetting]: 设置值，如果不存在则返回None
        """
        with get_db_connection() as db:
            db.execute(
                "SELECT setting_value, setting_type FROM system_settings WHERE setting_key = ?",
                (key)
            )
            row = db.fetchone()

            if row:
                return SystemSetting.from_db_row(row)

            return None

    @handle_db_errors("获取所有系统设置")
    def get_all_settings(self) -> Dict[str, SystemSetting]:
        """获取所有系统设置

        Returns:
            Dict[str, SystemSetting]: 系统设置字典
        """
        with get_db_connection() as db:
            db.execute("SELECT setting_key, setting_value, setting_type FROM system_settings")
            rows = db.fetchall()

            result = {}
            for row in rows:
                setting = SystemSetting.from_db_row(row)
                result[setting.key] = setting

            return result

    @handle_db_errors("保存系统设置")
    def save_setting(self, setting: SystemSetting) -> bool:
        """保存系统设置

        Args:
            setting: 系统设置对象

        Returns:
            bool: 是否保存成功
        """
        db_dict = setting.to_db_dict()

        with get_db_connection() as db:
            # 检查是否已存在
            db.execute("SELECT 1 FROM system_settings WHERE setting_key = ?", (setting.key,))
            exists = db.fetchone() is not None

            if exists:
                # 更新
                db.execute("""
                UPDATE system_settings SET
                    setting_value = :setting_value,
                    setting_type = :setting_type
                WHERE setting_key = :setting_key
                """, db_dict)
            else:
                # 插入
                db.execute("""
                INSERT INTO system_settings (
                    setting_key, setting_value, setting_type
                ) VALUES (:setting_key, :setting_value, :setting_type)
                """, db_dict)

            return True

    @handle_db_errors("删除系统设置")
    def delete_setting(self, key: str) -> bool:
        """删除系统设置

        Args:
            key: 设置键名

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            db.execute("DELETE FROM system_settings WHERE setting_key = ?", (key,))
            return True

    # ===== 配置导入导出 =====

    @handle_db_errors("导出所有配置")
    def export_config(self) -> Dict[str, Any]:
        """导出所有配置

        Returns:
            Dict[str, Any]: 配置字典
        """
        result = {
            "providers": self.get_all_providers(),
            "models": self.get_all_models(),
            "composite_models": self.get_all_composite_models(),
            "system": self.get_all_settings()
        }
        return result

    @handle_db_errors("导入配置")
    def import_config(self, config: Dict[str, Any]) -> bool:
        """导入配置

        Args:
            config: 配置字典

        Returns:
            bool: 是否导入成功
        """
        with get_db_connection() as db:
            # 清空现有数据
            db.execute("DELETE FROM providers")
            db.execute("DELETE FROM models")
            db.execute("DELETE FROM composite_models")
            db.execute("DELETE FROM system_settings")

            # 导入供应商
            for provider_config in config.get("providers", {}).values():
                self.save_provider(ProviderConfig.from_db_row(provider_config))

            # 导入模型
            for model_config in config.get("models", {}).values():
                self.save_model(ModelConfig.from_db_row(model_config))

            # 导入组合模型
            for composite_config in config.get("composite_models", {}).values():
                self.save_composite_model(CompositeModelConfig.from_db_row(composite_config))

            # 导入系统设置
            for setting_config in config.get("system", {}).values():
                self.save_setting(SystemSetting.from_db_row(setting_config))

            return True
