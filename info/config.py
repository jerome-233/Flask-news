# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/11 10:05
# @Author : Jerome
import redis
import logging


class Config(object):
    SECRET_KEY = "sfwefw12123"
    # 连接MySQL
    SQLALCHEMY_DATABASE_URI = "mysql://root:199601@127.0.0.1:3306/news"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    # redis配置信息
    redis_host = "127.0.0.1"
    redis_port = 6379
    # session类型：redis, 让session保存到redis当中
    SESSION_TYPE = "redis"
    # session的过期时间, 秒
    PERMANENT_SESSION_LIFETIME = 86400 * 2
    # 开启session签名, 加密cookie的session_id
    SESSION_USE_SIGNER = True
    # 初始化session-redis
    # 这个redis对象是用来储存flask_session
    SESSION_REDIS = redis.StrictRedis(host=redis_host, port=redis_port)
    # 开启日志


class ProductionConfig(Config):
    """最终上线产品配置类"""
    DEBUG = False


class DevelopementConfig(Config):
    """最终上线产品配置类"""
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


Config_dict = {
    "production": ProductionConfig,
    "developement": DevelopementConfig
}
