# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/13 20:37
# @Author : Jerome
import random
import re

from datetime import datetime
from flask import Blueprint, request, make_response, jsonify, current_app, session

from info import redis_store, constants, db
from info.libs.captcha.captcha import captcha
from info.models import User
from info.response_code import RET

passport_blue = Blueprint("passport", __name__, url_prefix='/passport')


@passport_blue.route("/image_code")
def creat_image_code():
    """前端在点击验证图片的时候回触发js点击事件
        1. 生成唯一的 uuid
        2. 以 get传参的方式拼接图片的请求链接地址
        3. 后台以 request.args.get("key")的方法取得参数:uuid
        4. 调用 captcha模块生成验证码
        5. 使用 make_response方法将得到图片验证码发送给前端"""

    # print("请求的URL为: ", request.url)

    # 从请求包体里面提取uuid, 用来绑定获得的验证码内容
    code_id = request.args.get("code_id")

    # print(code_id)

    if not code_id:
        """如果没获取到uuid说明前端js出了问题"""
        return jsonify(errno=RET.NODATA, errmsg="获取图片id错误")

    # 生成图片验证码,
    name, text, image = captcha.generate_captcha()

    print("验证码内容为: ", text)

    # 以image作为头部, 拼接唯一的uuid作为key, 将图片验证码内容储存到redis当中
    redis_store.set("image" + code_id, text, constants.SMS_CODE_REDIS_EXPIRES)

    # 生成响应包体发送给客户端
    response = make_response(image)
    return response


@passport_blue.route("/sms_code", methods=["POST"])
def creat_sms_code():

    # print("请求的URL为: ", request.url)

    # 从前端提交的ajax请求中使用json获取到json
    recv_para = request.json
    mobile = recv_para.get("mobile")
    image_code = recv_para.get("image_code")
    image_code_id = recv_para.get("image_code_id")

    # 判断前端传过来的参数是否齐全
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 判断手机号码是否合法
    if not re.match("1[34578]\d{9}$", mobile):
        return jsonify(errno=RET.DATAERR, errmsg="手机号码错误")

    # 从redis中取图片验证码并与传过来的验证码校验
    real_code = redis_store.get("image" + image_code_id)

    print("查询到的验证码: %s\n接收到的验证码: %s" % (real_code, image_code))

    if not real_code:
        return jsonify(errno=RET.DATAERR, errmsg="验证码过期")

    # 将两个渠道得到的验证码在全部转化为小写后进行匹配
    if real_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg="验证码错误")

    # 匹配成功了以后删除这个验证码
    redis_store.delete("image" + image_code_id)

    # 判断当前手机号码是否注册
    user = User.query.filter(User.mobile == mobile).first()

    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg="该手机号已注册, 请登录")

    # 生成随机验证码, 使用格式化占位符, 不足6位用0填充
    sms_code = "%06d" % random.randint(0, 999999)

    print("请求的短信验证码为: ", sms_code)

    """这一块应该是调用云服务商发送短信验证码"""

    # 将sms_code作为头部, 并且拼接用户手机号码, 作为key储存手机验证码
    redis_store.set("sms_code" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)

    return jsonify(errno=RET.OK, errmsg="发送成功")


@passport_blue.route("/register", methods=["POST"])
def register():

    # 提取前台传输过来的参数
    recv_para = request.json
    mobile = recv_para.get("mobile")
    sms_code = recv_para.get("sms_code")
    password = recv_para.get("password")

    print("手机:%s\n 验证码:%s\n 密码:%s" % (mobile, sms_code, password))

    # 判断传过来的参数是否齐全
    if not all([mobile, sms_code, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 判断手机号码是否合法
    if not re.match("1[34578]\d{9}$", mobile):
        return jsonify(errno=RET.DATAERR, errmsg="手机号码错误")

    # 通过手机号码拼接sms_code作为key去redis中查询短信验证码的值
    real_code = redis_store.get("sms_code" + mobile)

    print("查询的验证码: %s\n接收的验证码: %s" % (real_code, sms_code))

    if not real_code:
        """查询结果为空"""
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码不存在, 请重新获取")

    if real_code != sms_code:
        """取出了验证码, 匹配失败"""
        return jsonify(errno=RET.DATAERR, errmsg="验证码错误")

    # 匹配成功了以后删除这个验证码
    redis_store.delete("sms_code" + mobile)

    # 定义数据对象
    user = User()
    user.nick_name = mobile
    user.mobile = mobile
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
        print("用户%s数据插入成功" % mobile)

    except Exception as e:
        db.session.rollback()
        current_app.logger(e)
        return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")

    # 保存用户登录状态
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile

    # 返回注册结果
    return jsonify(errno=RET.OK, errmsg="注册成功")


@passport_blue.route("/login", methods=["POST"])
def login():

    print("请求的URL为: ", request.url)

    # 提取前台传输过来的参数
    recv_para = request.json
    mobile = recv_para.get("mobile")
    password = recv_para.get("password")

    print("请求登录用户的手机:%s\n 密码:%s" % (mobile, password))

    if not all([mobile, password]):
        """传输过来的参数不完整"""
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    user = User.query.filter_by(mobile=mobile).first()

    if not user:
        """通过手机号查询用户不存在"""
        return jsonify(errno=RET.USERERR, errmsg="用户不存在或未激活")

    if not user.check_passowrd(password):
        """密码错误"""
        return jsonify(errno=RET.PWDERR, errmsg="用户名/密码错误")

    # 保存用户登录状态
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["is_admin"] = user.is_admin

    # 记录用户最后一次登录时间
    user.last_login = datetime.now()

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)

    print("登录成功")

    return jsonify(errno=RET.OK, errmsg="登录成功")


@passport_blue.route("/logout", methods=["POST"])
def logout():

    session.pop('user_id', None)
    session.pop('nick_name', None)
    session.pop('mobile', None)
    session.pop('is_admin', None)

    print("用户退出成功")

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK")