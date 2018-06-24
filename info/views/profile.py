# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/20 10:08
# @Author : Jerome
from flask import Blueprint, g, redirect, render_template, request, jsonify, current_app, session, abort

from info import db, constants
from info.libs.function.user_status import user_login_data
from info.libs.qiniu.image_storage import storage
from info.models import Category, News, User
from info.response_code import RET

# 定义蓝图, 指定前缀/user处理此路径下的合法请求
profile_blue = Blueprint("profile", __name__, url_prefix='/user')


@profile_blue.route("/info")
@user_login_data
def get_user_info():
    """
    获取用户信息
    1. 获取到当前登录的用户模型
    2. 返回模型中指定内容
    :return:
    """
    user = g.user
    if not user:
        # 用户未登录，重定向到主页
        return redirect('/')

    data = {
        "user_info": user.to_dict(),
    }
    # 传送数据给前端填充并返回html文件给客户端
    return render_template("news/user.html", data=data)


@profile_blue.route('/base_info', methods=["POST", "GET"])
@user_login_data
def base_info():
    """展示用户的基础信息并提供修改"""
    # 取出user
    user = g.user

    # 处理GET请求返回网页
    if request.method == "GET":
        return render_template('news/user/user_base_info.html',
                               data={"user_info": user.to_dict()})

    # 接收post请求的参数
    recv_para = request.json
    nick_name = recv_para.get("nick_name")
    signature = recv_para.get("signature")
    gender = recv_para.get("gender")

    print("昵称:%s\n 签名:%s\n 性别:%s" % (nick_name, signature, gender))

    if not all([nick_name, signature, gender]):
        """判断参数是否齐全"""
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    if gender not in ("MAN", "WOMAN"):
        """判断参数是否错误"""
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 修改user的对应数据
    user.nick_name = nick_name
    user.signature = signature
    user.gender = gender

    # 提交修改
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    # 修改session中的用户昵称, 让页面获取修改后的昵称
    session["nick_name"] = nick_name

    return jsonify(errno=RET.OK, errmsg="修改成功")


@profile_blue.route('/pic_info', methods=["GET", "POST"])
@user_login_data
def pic_info():
    user = g.user

    if request.method == "GET":
        return render_template('news/user/user_pic_info.html',
                               data={"user_info": user.to_dict()})

    try:
        # 获取到客户端传过来的图片并读取内容
        avatar = request.files.get("avatar").read()

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.IOERR, errmsg="读取文件出错")

    try:
        key = storage(avatar)

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片出错")

    # 修改用户头像url的key
    user.avatar_url = key

    # 将数据保存到数据库
    try:
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户数据错误")

    print(user.to_dict()["avatar_url"])

    return jsonify(errno=RET.OK,
                   errmsg="图片上传成功",
                   data={"avatar_url": constants.QINIU_DOMIN_PREFIX + key})


@profile_blue.route('/pass_info', methods=["GET", "POST"])
@user_login_data
def pass_info():
    user = g.user

    if request.method == "GET":
        return render_template('news/user/user_pass_info.html')

    recv_para = request.json
    old_password = recv_para.get("old_password")
    new_password = recv_para.get("new_password")

    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    if not user.check_passowrd(old_password):
        return jsonify(errno=RET.PWDERR, errmsg="旧密码错误")

    user.password = new_password

    try:
        db.session.commit()

    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    return jsonify(errno=RET.OK, errmsg="保存成功")


@profile_blue.route('/collection')
@user_login_data
def user_collection():
    user = g.user

    # 提取分页查询的页数
    p = request.args.get("p")
    # 为了稳定, 将p转为int整形
    try:
        p = int(p)
    # 如果出错, 记录日志并强行赋值为1
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    # 定义默认参数
    collections_obj = []
    current_page = 1
    total_pages = 1

    # 尝试分页查询
    try:
        paginate = user.collection_news.paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)

        # 提取分页查询返回的结果
        collections_obj = paginate.items
        current_page = paginate.page
        total_pages = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 将新闻对象列表转为新闻字典列表
    collections_news_list = []
    for i in collections_obj:
        collections_news_list.append(i.to_dict())

    data = {"total_page": total_pages,
            "current_page": current_page,
            "collections": collections_news_list}

    return render_template('news/user/user_collection.html', data=data)


@profile_blue.route('/news_release', methods=["GET", "POST"])
@user_login_data
def news_release():

    # (1). 处理GET请求返回发布新闻的页面
    if request.method == "GET":

        # 1. 定义一个空列表保存新闻分类对象
        categories_obj = []

        try:
            # 2. 尝试获取所有的分类数据对象
            categories_obj = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)

        # 3. 定义列表保存分类数据
        categories_dicts = []
        for category in categories_obj:
            # 4. 获取字典并添加到分类数据列表
            categories_dicts.append(category.to_dict())

        # 5. 移除`最新`分类, 发布的时候不需要这个分类
        categories_dicts.pop(0)

        # 6. 返回内容
        return render_template('news/user/user_news_release.html',
                               data={"categories": categories_dicts})

    # (2). 处理POST请求发布新闻

    # 1. 获取要提交的数据
    title = request.form.get("title")  # 新闻标题
    source = "个人发布"  # 新闻来源
    digest = request.form.get("digest")  # 新闻摘要
    content = request.form.get("content")  # 新闻正文
    index_image = request.files.get("index_image")  # 新闻图片
    category_id = request.form.get("category_id")  # 新闻分类id

    print("标题:", title, "新闻来源:", source, "新闻摘要:", digest, "新闻正文:", content, "新闻分类id:", category_id)

    # 2. 判断数据是否有值
    if not all([title, source, digest, content, category_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    # 3. 尝试读取图片
    try:
        index_image = index_image.read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    # 4. 将标题图片上传到七牛
    try:
        key = storage(index_image)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

    # 5. 初始化新闻模型，并设置相关数据
    news = News()
    news.title = title
    news.digest = digest
    news.source = source
    news.content = content
    news.index_image_url = constants.QINIU_DOMIN_PREFIX + key
    news.category_id = category_id
    news.user_id = g.user.id
    news.status = 1  # 1代表待审核状态

    # 6. 保存到数据库
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    # 7. 返回结果
    return jsonify(errno=RET.OK, errmsg="发布成功，等待审核")


@profile_blue.route('/news_list')
@user_login_data
def news_list():
    # 1. 获取用户登录数据
    user = g.user

    # 2.从get请求中获取页数
    p = request.args.get("p", 1)

    # 3. 将参数p转为整形, 方便后面传参调用
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    # 4. 分页查询用户发布的所有新闻

    # 4.1 定义分页查询的默认参数
    news_obj = []
    current_page = 1
    total_page = 1

    try:
        paginate = News.query.filter(News.user_id == user.id)\
            .paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)

        # 4.3 获取当前页数据
        news_obj = paginate.items
        # 4.4 获取当前页
        current_page = paginate.page
        # 4.5 获取总页数
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)

    # 4.6 定义空列表保存所有新闻数据
    news_dict_li = []
    # 4.7 迭代所有的新闻对象, 调用dict方法获取新闻数据并添加到列表
    for news_item in news_obj:
        news_dict_li.append(news_item.to_review_dict())

    # 5. 定义data字典保存数据传给html模板填充数据
    data = {
        "news_list": news_dict_li,
        "total_page": total_page,
        "current_page": current_page
    }

    # 6. 将data传入html模板, 填充数据处理完毕以后返回html文件给客户端渲染
    return render_template('news/user/user_news_list.html', data=data)


@profile_blue.route('/user_follow')
@user_login_data
def user_follow():
    print("请求关注用户")
    # 获取页数
    p = request.args.get("p", 1)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    user = g.user

    follows = []
    current_page = 1
    total_page = 1
    try:
        paginate = user.followed.paginate(p, constants.USER_FOLLOWED_MAX_COUNT, False)
        # 获取当前页数据
        follows = paginate.items
        # 获取当前页
        current_page = paginate.page
        # 获取总页数
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    user_dict_li = []

    for follow_user in follows:
        user_dict_li.append(follow_user.to_dict())
    data = {
        "users": user_dict_li,
        "total_page": total_page,
        "current_page": current_page
    }
    print(data)
    return render_template('news/user/user_follow.html', data=data)


@profile_blue.route('/other_info')
@user_login_data
def other_info():
    """查看其他用户信息"""
    user = g.user

    # 获取其他用户id
    user_id = request.args.get("id")
    if not user_id:
        abort(404)

    # 查询用户模型
    other = None
    try:
        other = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
    if not other:
        abort(404)

    # 判断当前登录用户是否关注过该用户
    is_followed = False
    if g.user:
        if other.followers.filter(User.id == user.id).count() > 0:
            is_followed = True

    # 组织数据，并返回
    data = {
        "user_info": user.to_dict(),
        "other_info": other.to_dict(),
        "is_followed": is_followed
    }
    return render_template('news/other.html', data=data)


@profile_blue.route('/other_news_list')
def other_news_list():
    # 获取页数
    p = request.args.get("p", 1)
    user_id = request.args.get("user_id")
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if not all([p, user_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

    if not user:
        return jsonify(errno=RET.NODATA, errmsg="用户不存在")

    try:
        paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.OTHER_NEWS_PAGE_MAX_COUNT, False)
        # 获取当前页数据
        news_li = paginate.items
        # 获取当前页
        current_page = paginate.page
        # 获取总页数
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

    news_dict_li = []

    for news_item in news_li:
        news_dict_li.append(news_item.to_review_dict())
    data = {"news_list": news_dict_li, "total_page": total_page, "current_page": current_page}
    return jsonify(errno=RET.OK, errmsg="OK", data=data)