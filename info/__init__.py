# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/11 11:42
# @Author : Jerome
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from flask_session import Session
# from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf, CSRFProtect
from info.config import Config_dict
from redis import *
from flask_sqlalchemy import SQLAlchemy


# 在外面定义全局变量, 为了其他模块导入变量的时候能够找到
# 但是为了根据配置创建对应的对象, 绑定/初始化在创建app的函数内操作
# python3的特性, 可以利用行末注释, 标明变量的类型, 这样pycharm就能自动补全

db = SQLAlchemy()
redis_store = None  # type:StrictRedis


def creat_app(config_name):
    global redis_store

    # 初始化app对象并加载配置文件
    app = Flask(__name__)
    app.config.from_object(Config_dict[config_name])

    # 初始化db对象并绑定app
    db.init_app(app)
    # 连接redis获取对象, 是用来存储对象用的
    redis_store = StrictRedis(host="127.0.0.1", port=6379, decode_responses=True)

    # 设置Session
    Session(app)

    # 开启CSRF保护
    CSRFProtect(app)

    @app.after_request
    def add_token(response):
        csrf_token = generate_csrf()
        # print(csrf_token)
        response.set_cookie("csrf_token", csrf_token)
        return response

    # 导入视图文件夹的视图函数并注册到app对象上
    from info.views.index import index_blue
    from info.views.passport import passport_blue
    from info.views.news import news_blue
    from info.views.profile import profile_blue
    from info.views.admin import admin_blue
    app.register_blueprint(index_blue)
    app.register_blueprint(passport_blue)
    app.register_blueprint(news_blue)
    app.register_blueprint(profile_blue)
    app.register_blueprint(admin_blue)

    # 注册模板过滤器
    from info.libs.filter.common import do_index_class
    app.add_template_filter(do_index_class, "index_class")

    setup_log(config_name)

    # 捕捉异常并处理
    @app.errorhandler(404)
    def handler_404(e):
        return render_template("news/error/404.html")

    return app


def setup_log(config_name):
    """配置日志"""
    # 设置日志的记录等级
    logging.basicConfig(level=Config_dict[config_name].LOG_LEVEL)  # 调试debug级
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)