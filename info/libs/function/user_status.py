# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/16 17:51
# @Author : Jerome
import functools
from flask import session, g


def user_login_data(f):
    """装饰器:
    1. 通过从session中取用户id
    2. 向数据库中查询数据对象
    3. 将查询的结果添加到 g变量当中"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # 获取到当前登录用户的id
        user_id = session.get("user_id")
        user = None

        # 通过id获取用户信息
        if user_id:
            from info.models import User
            user = User.query.get(user_id)

        g.user = user
        return f(*args, **kwargs)

    return wrapper
