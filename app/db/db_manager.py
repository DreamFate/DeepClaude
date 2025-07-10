"""
使用连接池的数据库管理器实现
"""

import uuid
from typing import Dict, Any, Optional,List

from app.db.db_pool import get_db_connection, close_db_pool,get_db_pool
from app.db.db_config import ProviderConfig,ModelConfig,CompositeModelConfig,SystemSetting
from app.utils.logger import logger
from app.utils.error import DBManagerError

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
        logger.info("关闭数据库连接池")

    def open_db_manager(self):
        """打开数据库连接池

        在应用程序启动时调用，确保所有数据库连接被正确打开
        """
        get_db_pool()
        logger.info("打开数据库连接池")

    def _init_system_settings(self):
        """初始化系统设置数据

        Args:
            db: 数据库连接
        """
        # 检查是否已有数据
        with get_db_connection() as db:
            # 先查出所有已存在的key
            db.execute("SELECT setting_key FROM system_settings")
            existing_keys = {row["setting_key"] for row in db.fetchall()}

            # 默认系统设置
            default_settings = [
                # 日志级别
                ("log_level", "INFO", "str"),
                # API密钥
                ("api_key", "123456", "str"),
                # 代理设置
                ("proxy_address", "127.0.0.1:7890", "str"),
                # TCP连接池设置
                ("tcp_connector_limit", "1000", "int"),
                ("tcp_connector_limit_per_host", "100", "int"),
                ("tcp_keepalive_timeout", "30.0", "float"),
            ]

            # 只插入缺失的key
            to_insert = [item for item in default_settings if item[0] not in existing_keys]
            for key, value, type_name in to_insert:
                db.execute(
                    """
                    INSERT INTO system_settings
                     (setting_key, setting_value, setting_type)
                     VALUES (?, ?, ?)
                    """,
                    (key, value, type_name)
                )
            if to_insert:
                logger.info("插入了 %d 条默认系统设置", len(to_insert))
            else:
                logger.info("所有默认系统设置已存在，无需插入")

    def _init_db(self):
        """初始化数据库，创建必要的表"""
        with get_db_connection() as db:
            # 创建供应商表
            db.execute('''
            CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL UNIQUE,  -- 供应商名称，如 'openai', 'anthropic', 'deepseek' 等
                api_key TEXT NOT NULL,               -- API密钥
                api_base_url TEXT NOT NULL,          -- 基础URL
                api_request_address TEXT NOT NULL,   -- 请求地址
                provider_format TEXT NOT NULL,       -- 供应商格式，如 'openrouter', 'anthropic', 'oneapi' , 'deepseek' 等
                is_proxy_open INTEGER,               -- 是否启用代理
                is_valid INTEGER NOT NULL,           -- 是否有效
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建models表
            db.execute('''
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                provider_id INTEGER NOT NULL,                   -- 对应的供应商ID
                model_type TEXT NOT NULL,                       -- 'reasoner' 或 'general'
                model_id TEXT NOT NULL,                         -- 模型ID
                model_name TEXT NOT NULL UNIQUE,                -- 模型名称
                model_format TEXT NOT NULL,                     -- 模型格式，如 'deepseek', 'anthropic', 'openai_compatible' 等
                model_custom_json TEXT,                         -- 自定义JSON
                is_valid INTEGER NOT NULL,                      -- 是否有效
                is_origin_reasoning INTEGER,                    -- 仅对推理模型有意义
                is_origin_output INTEGER,                       -- 是否使用原生输出
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provider_id) REFERENCES providers(id)
            )
            ''')

            # 创建composite_models表
            db.execute('''
            CREATE TABLE IF NOT EXISTS composite_models (
                id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL UNIQUE,                    -- 组合模型名称
                reasoner_model_id INTEGER NOT NULL,                 -- 推理模型ID
                general_model_id INTEGER NOT NULL,                  -- 通用模型ID
                is_valid INTEGER NOT NULL,                          -- 是否有效
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

    def get_all_providers(self, is_valid: Optional[bool] = None) -> List[ProviderConfig]:
        """获取所有供应商配置

        Args:
            is_valid: 是否只返回有效的供应商配置

        Returns:
            List[ProviderConfig]: 供应商配置列表
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

            sql += " ORDER BY is_valid DESC, created_at ASC "

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            result = []
            for row in rows:
                config = ProviderConfig.from_db_row(row)
                result.append(config)

            return result

    def get_provider(
        self,
        provider_name: Optional[str] = None,
        provider_id: Optional[str] = None
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

    def save_provider(self, config: ProviderConfig) -> dict:
        """保存供应商配置

        Args:
            config: 供应商配置

        Returns:
            str: 保存后的ID
        """

        db_dict = config.to_db_dict()
        # 先检查是否存在同名供应商（排除自身ID）
        existing = self.get_provider(provider_name=config.provider_name)
        if existing and existing.id != config.id:
            # 存在同名但不是自己，返回错误
            raise DBManagerError(f"供应商名称 '{config.provider_name}' 已存在")

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
                    is_proxy_open = :is_proxy_open,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """, db_dict)
            else:
                my_uuid = str(uuid.uuid4())
                db_dict["id"] = my_uuid
                # 插入
                db.execute("""
                INSERT INTO providers (
                    id, provider_name, api_key, api_base_url, api_request_address, provider_format, is_valid, is_proxy_open
                ) VALUES (:id, :provider_name, :api_key, :api_base_url, :api_request_address, :provider_format, :is_valid, :is_proxy_open)
                """, db_dict)

            # 获取最新数据
            db.execute("SELECT * FROM providers WHERE id = ?", (db_dict["id"],))
            row = db.fetchone()
            if row:
                return dict(row)
            # 如果查询失败，返回基本信息
            return {"id": db_dict["id"]}

    def delete_provider(self, provider_id: str) -> bool:
        """删除供应商配置

        Args:
            provider_id: 供应商ID

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            # 检查是否有模型依赖此供应商
            db.execute("SELECT COUNT(*) as count FROM models WHERE provider_id = ?", (provider_id,))
            row = db.fetchone()
            if row and row["count"] > 0:
                raise DBManagerError(f"无法删除供应商：有{row['count']}个模型依赖此供应商")

            db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
            return True

    # ===== Models 操作 =====

    def get_all_models(
        self,
        model_type:Optional[str]=None,
        is_valid:Optional[bool]=None
    ) -> List[ModelConfig]:
        """获取所有模型配置

        Args:
            model_type: 可选，模型类型过滤
            is_valid: 可选，是否只获取有效的模型

        Returns:
            List[ModelConfig]: 模型配置列表
        """
        with get_db_connection() as db:
            # 基础SQL查询
            sql = """
            SELECT id, model_id, model_name, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
            model_custom_json,
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

            sql += " ORDER BY is_valid DESC, created_at ASC "

            # 执行查询
            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            # 处理结果
            result = []
            for row in rows:
                result.append(ModelConfig.from_db_row(row))

            return result

    def get_model(
        self,
        model_name: Optional[str] = None,
        models_id: Optional[str] = None,
        is_valid: Optional[bool] = None
    ) -> Optional[ModelConfig]:
        """获取指定模型配置

        Args:
            model_name: 模型名称
            models_id: 模型ID
            is_valid: 是否只获取有效的模型

        Returns:
            Optional[ModelConfig]: 模型配置，如果不存在则返回None
        """
        with get_db_connection() as db:
            sql = """
            SELECT id, model_id, model_name, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
            model_custom_json,
            is_origin_output
            FROM models
            WHERE 1=1
            """

            params = []
            if model_name:
                sql += " AND model_name = ?"
                params.append(model_name)
            if models_id:
                sql += " AND id = ?"
                params.append(models_id)
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

    def save_model(self, config: ModelConfig) -> dict:
        """保存模型配置

        Args:
            config: 模型配置

        Returns:
            dict: 保存后的ID
        """
        db_dict = config.to_db_dict()
        # 先检查是否存在同名供应商（排除自身ID）
        existing = self.get_model(model_name=config.model_name)
        if existing and existing.id != config.id:
            # 存在同名但不是自己，返回错误
            raise DBManagerError(f"模型名称 '{config.model_name}' 已存在")

        with get_db_connection() as db:
            if config.id:
                # 更新
                db.execute('''
                UPDATE models SET
                    model_name = :model_name,
                    model_id = :model_id,
                    provider_id = :provider_id,
                    is_origin_reasoning = :is_origin_reasoning,
                    is_valid = :is_valid,
                    model_type = :model_type,
                    model_format = :model_format,
                    model_custom_json = :model_custom_json,
                    is_origin_output = :is_origin_output,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                ''', db_dict)
            else:
                my_uuid = str(uuid.uuid4())
                db_dict["id"] = my_uuid
                # 插入
                db.execute('''
                INSERT INTO models (
                    id, model_name, model_id, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
                    model_custom_json, is_origin_output
                ) VALUES (:id, :model_name, :model_id, :provider_id, :is_origin_reasoning, :is_valid, :model_type, :model_format, :model_custom_json, :is_origin_output)
                ''', db_dict)

            # 获取最新数据
            db.execute("SELECT * FROM models WHERE id = ?", (db_dict["id"],))
            row = db.fetchone()
            if row:
                return dict(row)
            # 如果查询失败，返回基本信息
            return {"id": db_dict["id"]}

    def delete_model(self, models_id: str) -> bool:
        """删除模型配置

        Args:
            models_id: 模型ID

        Returns:
            bool: 是否删除成功
        """
        with get_db_connection() as db:
            # 检查是否有模型依赖此供应商
            db.execute(
                """
                SELECT COUNT(*) as count FROM composite_models
                 WHERE general_model_id = ? OR reasoner_model_id = ?
                """,
                (models_id, models_id)
            )
            row = db.fetchone()
            if row and row["count"] > 0:
                raise DBManagerError(f"无法删除模型：有{row['count']}个组合模型依赖此供应商")

            db.execute("DELETE FROM models WHERE id = ?", (models_id,))
            return True

    # ===== Composite Models 操作 =====

    def get_all_composite_models(self, is_valid=None) -> List[CompositeModelConfig]:
        """获取所有组合模型配置

        Args:
            is_valid: 是否只获取有效的组合模型

        Returns:
            List[CompositeModelConfig]: 组合模型配置列表
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

            sql += " ORDER BY is_valid DESC, created_at ASC "

            if params:
                db.execute(sql, params)
            else:
                db.execute(sql)

            rows = db.fetchall()

            result = []
            for row in rows:
                config = CompositeModelConfig.from_db_row(row)
                result.append(config)

            return result

    def get_composite_model(
        self,
        model_name: Optional[str]=None,
        composite_models_id:Optional[str]=None,
        is_valid:Optional[bool]=None
    ) -> Optional[CompositeModelConfig]:
        """获取指定组合模型配置

        Args:
            model_name: 模型名称
            composite_models_id: 组合模型ID
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
            if composite_models_id:
                sql += " AND id = ?"
                params.append(composite_models_id)
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

    def save_composite_model(self, config: CompositeModelConfig) -> dict:
        """保存组合模型配置

        Args:
            config: 组合模型配置

        Returns:
            dict: 保存后的ID
        """
        db_dict = config.to_db_dict()
        # 先检查是否存在同名供应商（排除自身ID）
        existing = self.get_composite_model(model_name=config.model_name)
        if existing and existing.id != config.id:
            # 存在同名但不是自己，返回错误
            raise DBManagerError(f"组合模型名称 '{config.model_name}' 已存在")

        with get_db_connection() as db:
            if config.id:
                # 更新
                db.execute("""
                UPDATE composite_models SET
                    model_name = :model_name,
                    reasoner_model_id = :reasoner_model_id,
                    general_model_id = :general_model_id,
                    is_valid = :is_valid,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """, db_dict)
            else:
                my_uuid = str(uuid.uuid4())
                db_dict["id"] = my_uuid
                # 插入
                db.execute("""
                INSERT INTO composite_models (
                    id, model_name, reasoner_model_id, general_model_id, is_valid
                ) VALUES (:id, :model_name, :reasoner_model_id, :general_model_id, :is_valid)
                """, db_dict)

            # 获取最新数据
            db.execute("SELECT * FROM composite_models WHERE id = ?", (db_dict["id"],))
            row = db.fetchone()
            if row:
                return dict(row)
            # 如果查询失败，返回基本信息
            return {"id": db_dict["id"]}

    def delete_composite_model(self, composite_id: str) -> bool:
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
                result[setting.setting_key] = setting

            return result

    def save_setting(self, settings: List[SystemSetting]) -> bool:
        """保存系统设置

        Args:
            settings: 系统设置对象

        Returns:
            bool: 是否保存成功
        """


        with get_db_connection() as db:
            for setting in settings:
                db_dict = setting.to_db_dict()
                # 检查是否已存在
                db.execute("SELECT 1 FROM system_settings WHERE setting_key = ?",
                    (setting.setting_key,))
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

    def export_config(self) -> Dict[str, Any]:
        """导出所有配置

        Returns:
            Dict[str, Any]: 配置字典
        """
        providers = self.get_all_providers()
        result_providers = []
        for provider in providers:
            result_providers.append(provider.to_db_dict())
        models = self.get_all_models()
        result_models = []
        for model in models:
            result_models.append(model.to_db_dict())
        composite_models = self.get_all_composite_models()
        result_composite_models = []
        for composite_model in composite_models:
            result_composite_models.append(composite_model.to_db_dict())
        system = self.get_all_settings()
        result_system = []
        for _,setting in system.items():
            result_system.append(setting.to_db_dict())
        result = {
            "providers": result_providers,
            "models": result_models,
            "composite_models": result_composite_models,
            "system": result_system
        }
        return result

    def import_config(self, config: Dict[str, Any]) -> bool:
        """导入配置

        Args:
            config: 配置字典

        Returns:
            bool: 是否导入成功
        """
        with get_db_connection() as db:
            # 清空现有数据
            db.execute("DELETE FROM composite_models")
            db.execute("DELETE FROM models")
            db.execute("DELETE FROM providers")
            db.execute("DELETE FROM system_settings")

            # 导入供应商
            for provider_config in config.get("providers", {}):
                db.execute("""
                INSERT INTO providers (
                    id, provider_name, api_key, api_base_url, api_request_address, provider_format, is_valid, is_proxy_open
                ) VALUES (:id, :provider_name, :api_key, :api_base_url, :api_request_address, :provider_format, :is_valid, :is_proxy_open)
                """, provider_config)

            # 导入模型
            for model_config in config.get("models", {}):
                db.execute('''
                INSERT INTO models (
                    id, model_name, model_id, provider_id, is_origin_reasoning, is_valid, model_type, model_format,
                    is_origin_output
                ) VALUES (:id, :model_name, :model_id, :provider_id, :is_origin_reasoning, :is_valid, :model_type, :model_format, :is_origin_output)
                ''', model_config)

            # 导入组合模型
            for composite_config in config.get("composite_models", {}):
                db.execute("""
                INSERT INTO composite_models (
                    id, model_name, reasoner_model_id, general_model_id, is_valid
                ) VALUES (:id, :model_name, :reasoner_model_id, :general_model_id, :is_valid)
                """, composite_config)

            # 导入系统设置
            for setting_config in config.get("system", {}):
                db.execute("""
                INSERT INTO system_settings (
                    setting_key, setting_value, setting_type
                ) VALUES (:setting_key, :setting_value, :setting_type)
                """, setting_config)

            return True

db_manager = DBManager()
