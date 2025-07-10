"""
SQLite数据库连接池实现
"""

import sqlite3
import threading
import time
from typing import List, Optional, Dict
import os
from app.utils.logger import logger

class SQLiteConnectionPool:
    """SQLite数据库连接池"""

    def __init__(self, db_path: str, max_connections: int = 5):
        """初始化连接池

        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数
        """
        self.db_path = db_path
        self.max_connections = max_connections

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # 连接池
        self.pool: List[Optional[sqlite3.Connection]] = [None] * max_connections
        # 可用连接索引
        self.available: List[int] = list(range(max_connections))
        # 连接使用状态
        self.in_use: Dict[int, bool] = {i: False for i in range(max_connections)}

        # 线程锁，保证线程安全
        self.lock = threading.RLock()

        logger.info("SQLite连接池初始化完成，最大连接数: %s", max_connections)

    def _create_connection(self, index: int) -> Optional[sqlite3.Connection]:
        """创建新的数据库连接

        Args:
            index: 连接在池中的索引

        Returns:
            Optional[sqlite3.Connection]: 新创建的连接，失败则返回None
        """
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # 启用外键约束
            conn.execute("PRAGMA foreign_keys = ON")
            # 设置行工厂，返回字典而不是元组
            conn.row_factory = sqlite3.Row

            self.pool[index] = conn
            # logger.debug("创建连接 #%s 成功", index)
            return conn
        except sqlite3.Error as e:
            logger.error("创建连接 #%s 失败: %s", index, e)
            return None

    def _check_connection(self, index: int) -> bool:
        """检查连接是否有效

        Args:
            index: 连接在池中的索引

        Returns:
            bool: 连接是否有效
        """
        conn = self.pool[index]
        if conn is None:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except sqlite3.Error:
            return False

    def get_connection(self, max_wait=5, retry_interval=0.1) -> Optional[sqlite3.Connection]:
        """获取一个可用的数据库连接，如果没有可用连接则等待

        Args:
            max_wait: 最大等待时间（秒）
            retry_interval: 重试间隔（秒）

        Returns:
            Optional[sqlite3.Connection]: 数据库连接，如果超时仍无可用连接则返回None
        """
        wait_time = 0
        while wait_time < max_wait:
            with self.lock:
                if self.available:
                    index = self.available.pop(0)

                    # 检查连接是否存在且有效
                    if self.pool[index] is None or not self._check_connection(index):
                        # 连接不存在或无效，创建新连接
                        conn = self._create_connection(index)
                        if conn is None:
                            # 创建失败，将索引放回可用列表
                            self.available.append(index)
                            time.sleep(retry_interval)
                            wait_time += retry_interval
                            continue

                    # 标记为使用中
                    self.in_use[index] = True
                    # logger.debug("获取连接 #%s，剩余可用连接: %s", index, len(self.available))
                    return self.pool[index]

            # 没有可用连接，等待后重试
            time.sleep(retry_interval)
            wait_time += retry_interval

        logger.warning("等待可用连接超时(%s秒)", max_wait)
        return None

    def release_connection(self, conn: sqlite3.Connection):
        """释放连接回连接池

        Args:
            conn: 要释放的连接
        """
        with self.lock:
            for i, pool_conn in enumerate(self.pool):
                if pool_conn is conn:
                    if i not in self.available:
                        self.available.append(i)
                    self.in_use[i] = False
                    # logger.debug("释放连接 #%s，当前可用连接: %s", i, len(self.available))
                    return

            logger.warning("尝试释放不属于连接池的连接")

    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            for i, conn in enumerate(self.pool):
                if conn is not None:
                    try:
                        conn.close()
                        logger.debug("关闭连接 #%s", i)
                    except sqlite3.Error as e:
                        logger.error("关闭连接 #%s 失败: %s", i, e)
                    self.pool[i] = None

            self.available = list(range(self.max_connections))
            self.in_use = {i: False for i in range(self.max_connections)}

            logger.info("所有数据库连接已关闭")


class DBConnection:
    """数据库连接包装器，用于自动获取和释放连接"""

    def __init__(self, pool: SQLiteConnectionPool):
        """初始化

        Args:
            pool: 数据库连接池
        """
        self.pool = pool
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """进入上下文时获取连接"""
        self.conn = self.pool.get_connection()
        if self.conn:
            self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时释放连接"""
        if self.cursor:
            self.cursor.close()

        if self.conn:
            if exc_type:
                # 发生异常，回滚事务
                try:
                    logger.info("回滚事务")
                    self.conn.rollback()
                except sqlite3.Error:
                    logger.error("回滚事务失败")
            else:
                # 正常退出，提交事务
                try:
                    self.conn.commit()
                except sqlite3.Error:
                    logger.error("提交事务失败")

            self.pool.release_connection(self.conn)

        self.cursor = None
        self.conn = None

    def execute(self, sql, params=None):
        """执行SQL语句

        Args:
            sql: SQL语句
            params: 参数

        Returns:
            cursor对象
        """
        if not self.cursor:
            raise sqlite3.Error("数据库连接未初始化")

        if params:
            return self.cursor.execute(sql, params)
        return self.cursor.execute(sql)

    def fetchone(self):
        """获取一条记录"""
        if not self.cursor:
            raise sqlite3.Error("数据库连接未初始化")
        return self.cursor.fetchone()

    def fetchall(self):
        """获取所有记录"""
        if not self.cursor:
            raise sqlite3.Error("数据库连接未初始化")
        return self.cursor.fetchall()

    def commit(self):
        """提交事务"""
        if not self.conn:
            raise sqlite3.Error("数据库连接未初始化")
        self.conn.commit()

    def rollback(self):
        """回滚事务"""
        if not self.conn:
            raise sqlite3.Error("数据库连接未初始化")
        self.conn.rollback()


# 全局连接池实例
DB_POOL = None

def get_db_pool(db_path=None, max_connections=5):
    """获取全局数据库连接池实例

    Args:
        db_path: 数据库文件路径，仅在首次调用时有效
        max_connections: 最大连接数，仅在首次调用时有效

    Returns:
        SQLiteConnectionPool: 数据库连接池实例
    """
    pool = globals()["DB_POOL"]
    if pool is None:
        if db_path is None:
            # 默认数据库路径
            db_path = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(__file__))),
                "data",
                "deepclaude.db"
            )
        globals()["DB_POOL"] = SQLiteConnectionPool(db_path, max_connections)
    return globals()["DB_POOL"]

def get_db_connection():
    """获取数据库连接

    Returns:
        DBConnection: 数据库连接包装器
    """
    return DBConnection(get_db_pool())

def close_db_pool():
    """关闭数据库连接池"""
    pool = globals()["DB_POOL"]
    if pool:
        pool.close_all()
        globals()["DB_POOL"] = None
