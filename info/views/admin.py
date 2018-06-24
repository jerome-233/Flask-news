# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/20 22:26
# @Author : Jerome
from flask import Blueprint, current_app, request, jsonify, g, session, redirect, url_for
from flask import render_template

from info import constants, db
from info.libs.function.user_status import user_login_data
from info.libs.qiniu.image_storage import storage
from info.models import User, News, Category
from info.response_code import RET

import time
from datetime import datetime, timedelta

admin_blue = Blueprint("admin", __name__, url_prefix='/admin')


@admin_blue.before_request
def before_request():
    """每一次请求之前执行的钩子, 用来校验当前用户是否有权限访问"""

    # 判断如果不是登录页面的请求
    if not request.url.endswith(url_for("admin.admin_login")):

        # 从session中取值判断当前用户的权限
        user_id = session.get("user_id")
        is_admin = session.get("is_admin", False)

        if not user_id:
            # 说明当前用户为登录, 让其登录后台
            return redirect("/admin/login")

        if not is_admin:
            # 说明当前用户不是管理员，直接重定向到主页
            return redirect('/')


@admin_blue.route('/login', methods=["GET", "POST"])
def admin_login():
    """管理员用户登录"""
    if request.method == "GET":
        # 去 session 中取指定的值
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin", False)

        # 如果用户id存在，并且是管理员，那么直接跳转管理后台主页, 否则登录
        if user_id and is_admin:
            return redirect(url_for('admin.admin_index'))

        return render_template('admin/login.html')

    # 取到登录的参数
    username = request.form.get("username")
    password = request.form.get("password")

    if not all([username, password]):
        return render_template('admin/login.html', errmsg="参数不足")

    try:
        user = User.query.filter(User.mobile == username).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template('admin/login.html', errmsg="数据查询失败")

    if not user:
        return render_template('admin/login.html', errmsg="用户不存在")

    if not user.check_passowrd(password):
        return render_template('admin/login.html', errmsg="密码错误")

    if not user.is_admin:
        return render_template('admin/login.html', errmsg="用户权限错误")

    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["is_admin"] = True

    # 跳转到后台管理主页
    return redirect(url_for('admin.admin_index'))


@admin_blue.route('/index')
@user_login_data
def admin_index():
    """管理员用户主页"""
    user = g.user
    return render_template('admin/index.html', user=user.to_dict())


@admin_blue.route("/user_count")
def user_count():
    """统计用户数量"""

    # 1. 定义默认参数
    day_count = 0
    mon_count = 0
    total_count = 0
    active_count = []
    active_time = []

    # 2. 获取当前的格式化时间
    now_time = time.localtime()

    # 3. 尝试查询获取用户总人数
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)

    # 4. 尝试查询获取当天新增用户数

    # 4.1 使用当前格式化时间生成当天的起始时间(str类型)
    today_begin_str = "%d-%02d-%02d" % (now_time.tm_year, now_time.tm_mon, now_time.tm_mday)
    print(today_begin_str)
    # 4.2 使用strptime()方法将当天的时间转为时间元组, 方便查询时去比较时间
    today_begin_time = datetime.strptime(today_begin_str, "%Y-%m-%d")
    print(today_begin_time)

    # 4.3 通过限定条件: 尝试查询所有符合条件的用户并计数统计
    # 1) 不是管理员用户,
    # 2) 创建时间大于当天起始时间
    try:
        day_count = User.query.filter(User.is_admin == False, User.create_time >= today_begin_time).count()
    except Exception as e:
        current_app.logger.error(e)

    # 5. 统计当月增加的用户总数

    # 5.1 使用当前格式化时间生成当月的起始时间(str类型)
    mon_begin_str = "%d-%02d-01" % (now_time.tm_year,
                                    now_time.tm_mon)
    # 5.2 使用strptime()方法将当月起始时间转为时间元组, 方便查询时去比较时间
    mon_begin_time = datetime.strptime(mon_begin_str, "%Y-%m-%d")

    # 5.3 通过限定条件: 尝试查询所有符合条件的用户并计数统计
    # 1) 不是管理员用户,
    # 2) 创建时间大于当月起始时间
    try:
        mon_count = User.query.filter(User.is_admin == False,
                                      User.create_time >= mon_begin_time).count()
    except Exception as e:
        current_app.logger.error(e)

    # 6. 统计一个月内用户活跃情况

    # 6.1 迭代最近31天每一天的用户活跃数与日期
    for i in range(0, 31):
        # 6.2 生成当日的起始时间
        day_begin_time = today_begin_time - timedelta(days=i)
        # 6.3 生成当日的结束时间
        day_end_time = today_begin_time - timedelta(days=(i - 1))
        # 6.4 通过时间约束查询当日的活跃用户数
        active_user = User.query.filter(User.is_admin == False,
                                        User.last_login >= day_begin_time,
                                        User.last_login < day_end_time).count()
        # 6.5 添加数据至列表
        active_count.append(active_user)
        # 6.6 strftime方法按照指定格式转换当前时间并添加到列表
        active_time.append(day_begin_time.strftime("%Y-%m-%d"))

    # 7. 为了便于查阅数据, 反转列表
    active_count.reverse()
    active_time.reverse()

    data = {
        "total_count": total_count,
        "day_count": day_count,
        "mon_count": mon_count,
        "active_count": active_count,
        "active_time": active_time
    }

    return render_template("admin/user_count.html", data=data)


@admin_blue.route('/user_list')
def user_list():
    """获取用户列表"""
    # 1. 获取参数
    page = request.args.get("p", 1)
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    # 2. 设置变量默认值
    users_obj = []
    current_page = 1
    total_page = 1

    # 3. 查询数据
    try:
        # 3.1 分页查询数据
        paginate = User.query.filter(User.is_admin == False) \
            .order_by(User.last_login.desc()) \
            .paginate(page, constants.ADMIN_USER_PAGE_MAX_COUNT, False)

        # 3.2 提取分页查询数据内容
        users_obj = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)

    # 4. 将模型列表转成字典列表
    users_list = []
    for user in users_obj:
        users_list.append(user.to_admin_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "users": users_list
    }

    return render_template('admin/user_list.html', data=data)


@admin_blue.route('/news_review')
def news_review():
    """返回待审核新闻列表"""
    # 提取请求的参数
    page = request.args.get("p", 1)
    keywords = request.args.get("keywords", "")
    # 将提取的参数转为整形
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    # 定义分页查询默认参数
    news_obj = []
    current_page = 1
    total_page = 1

    # 尝试分页查询新闻数据, 查询条件如下:
    #  1) 新闻状态不为0, 也就是查询未审核和未通过的新闻
    #  2) 标题中包含指定搜索关键字的新闻
    #  3) 根据发布时间倒叙排列
    #  4) 分页一次查询10条数据
    try:
        paginate = News.query.filter(News.status != 0, News.title.contains(keywords)) \
            .order_by(News.create_time.desc()) \
            .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

        # 从分页查询的结果中提取数据
        news_obj = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 将新闻对象列表转换为新闻字典列表
    news_dict_list = []
    for news in news_obj:
        news_dict_list.append(news.to_review_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": news_dict_list
    }

    return render_template('admin/news_review.html', data=data)


@admin_blue.route('/news_review_detail', methods=["GET", "POST"])
def news_review_detail():
    """新闻详情审核"""

    # (1) 处理客户端审核新闻页面的请求
    if request.method == "GET":
        # 1. 获取新闻id
        news_id = request.args.get("news_id")
        if not news_id:
            return redirect("/admin/news_review")

        # 2. 通过id查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        # 3. 判断新闻是否存在
        if not news:
            return redirect("/admin/news_review")

        # 4. 返回数据
        data = {"news": news.to_dict()}
        return render_template('admin/news_review_detail.html', data=data)

    # (2) 处理审核操作的POST请求

    # 1.获取参数
    news_id = request.json.get("news_id")
    action = request.json.get("action")

    # 2.判断参数完整性
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3. 判断参数合法性
    if action not in ("accept", "reject"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 尝试查询新闻是否存在
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)

    # 5. 判断新闻是否存在
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

    # 6.根据不同的状态设置不同的值
    if action == "accept":
        news.status = 0
    else:
        # 拒绝通过，需要获取原因
        reason = request.json.get("reason")
        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        news.reason = reason
        news.status = -1

    # 7. 尝试提交事务到数据库执行修改操作
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据保存失败")

    return jsonify(errno=RET.OK, errmsg="操作成功")


@admin_blue.route('/news_edit')
def news_edit():
    """返回新闻列表"""
    # 1. 提取参数
    page = request.args.get("p", 1)
    keywords = request.args.get("keywords", "")

    # 2. 转换参数类型为int
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    # 3. 定义默认参数
    news_list = []
    current_page = 1
    total_page = 1
    filters = []

    # 4. 查询获取新闻数据
    try:
        # 4.1 如果有搜索过滤关键词
        if keywords:
            # 4.1.1添加关键词的检索选项
            filters.append(News.title.contains(keywords))

        # 4.2 使用过滤器后分页查询数据
        paginate = News.query.filter(*filters) \
            .order_by(News.create_time.desc()) \
            .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

        # 4.3 从分页查询的结果中提取数据
        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    except Exception as e:
        current_app.logger.error(e)

    # 5. 转换数据对象列表为数据字典列表
    news_dict_list = []
    for news in news_list:
        news_dict_list.append(news.to_basic_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": news_dict_list
    }

    return render_template('admin/news_edit.html', data=data)


@admin_blue.route('/news_edit_detail', methods=["GET", "POST"])
def news_edit_detail():
    """新闻编辑详情"""
    # (1) 处理客户端请求编辑新闻页面的请求
    if request.method == "GET":
        # 1. 获取参数
        news_id = request.args.get("news_id")

        # 2. 判断参数是否齐全
        if not news_id:
            return redirect("/admin/news_edit")

        # 3. 尝试查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)
        # 3.1 参数不存在
        if not news:
            return redirect("/admin/news_edit")

        # 4. 查询分类的数据
        categories = Category.query.all()

        # 5. 将分类数据对象列表转为数据字典列表
        categories_li = []
        for category in categories:
            c_dict = category.to_dict()
            # 5.1 默认分类的选择开关为否, 开关作用是供前端判断当前新闻的分类并选中它
            c_dict["is_selected"] = False
            # 5.2 如果当前迭代出来的分类id和当前编辑新闻id一样, 改为True
            if category.id == news.category_id:
                c_dict["is_selected"] = True
            categories_li.append(c_dict)

        # 6. 移除`最新`分类
        categories_li.pop(0)

        data = {
            "news": news.to_dict(),
            "categories": categories_li}

        return render_template('admin/news_edit_detail.html', data=data)

    # (2) 处理客户端编辑新闻后提交的POST请求
    news_id = request.form.get("news_id")
    title = request.form.get("title")
    digest = request.form.get("digest")
    content = request.form.get("content")
    index_image = request.files.get("index_image")
    category_id = request.form.get("category_id")

    # 1 判断数据是否有值
    if not all([title, digest, content, category_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

    # 2. 尝试查询新闻
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
    # 2.1 判断新闻是否存在
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到新闻数据")

    # 3. 尝试接收并读取图片
    if index_image:
        try:
            index_image = index_image.read()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        # 3.1 将标题图片上传到七牛
        try:
            key = storage(index_image)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")
        # 3.2 修改新闻照片的url请求地址
        news.index_image_url = constants.QINIU_DOMIN_PREFIX + key

    # 4. 修改相关数据
    news.title = title
    news.digest = digest
    news.content = content
    news.category_id = category_id

    # 5. 提交事务, 使修改生效
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    # 6. 返回结果
    return jsonify(errno=RET.OK, errmsg="编辑成功")


@admin_blue.route('/news_type')
def get_news_type():
    # 获取所有的分类数据
    categories = Category.query.all()

    # 将分类对象列表转为分类字典列表
    categories_dicts = []
    for category in categories:
        cate_dict = category.to_dict()
        categories_dicts.append(cate_dict)

    # 删除第一条数据-"最新"
    categories_dicts.pop(0)

    # 返回内容
    return render_template('admin/news_type.html',
                           data={"categories": categories_dicts})


@admin_blue.route('/add_category', methods=["POST"])
def add_category():
    """修改或者添加分类"""

    category_id = request.json.get("id")
    category_name = request.json.get("name")

    if not category_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 根据是否有分类id判断操作的类型
    if category_id:

        try:
            category = Category.query.get(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

        if not category:
            return jsonify(errno=RET.NODATA, errmsg="未查询到分类信息")

        category.name = category_name

    else:
        # 如果没有分类id，则是添加分类
        category = Category()
        category.name = category_name
        db.session.add(category)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

    return jsonify(errno=RET.OK, errmsg="保存数据成功")
