# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/11 11:18
# @Author : Jerome
# from . import index_blue
from flask import Blueprint, current_app, request, jsonify, g
from flask import render_template

from info import constants
from info.libs.function.user_status import user_login_data
from info.models import User, News, Category, Comment, CommentLike
from info.response_code import RET


index_blue = Blueprint("index", __name__)


@index_blue.route('/favicon.ico')
def favicon():
    print(request.url)
    return current_app.send_static_file("news/favicon.ico")


@index_blue.route("/")
@user_login_data
def index():

    print(request.url)

    user = g.user

    # 获取点击排行数据
    news_obj = None  # 默认新闻列表为空

    try:
        """查询New新闻表, 点击量降序排列, 限定10条"""
        news_obj = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)

    click_news_list = []  # 定义一个空列表
    for news in news_obj if news_obj else []:
        """如果查询结果为True, 就迭代, 否则迭代[]
            每迭代一个数据对象, 就调用对象的to_basic_dict方法转为字典添加到list列表"""
        click_news_list.append(news.to_basic_dict())

    # 查询新闻分类数据

    # 1. 查询并获取所有的数据对象
    all_categories_obj = Category.query.all()

    # 2. 定义一个空列表, 接收每一个迭代的数据对象的信息
    categories_list = []
    # 3. 遍历取出每一个分类的数据对象, 获取信息并添加到列表
    for category in all_categories_obj:
        categories_list.append(category.to_dict())

    # data字典是需要传给HTML模版的渲染数据
    data = {
        # 如果user为true, value就是:user.to_dict(), 否则为空
        "user_info": user.to_dict() if user else None,
        "click_news_list": click_news_list,
        "categories": categories_list,
    }

    return render_template('news/index.html', data=data)


@index_blue.route("/newslist")
def newslist():

    print(request.url)

    cid = request.args.get("cid", 1)
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 10)

    print("cid:", cid, "page:", page, "per_page", per_page)

    try:
        cid = int(cid)
        page = int(page)
        per_page = int(per_page)

    except Exception as e:
        current_app.logger(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3. 分页查询新闻数据

    # filters = [News.status == 0]

    # 定义一个过滤列表, 储存过滤信息,
    # 默认只要状态为0, 也就是只要审核通过的新闻
    filters = [News.status == 0]

    # 如果新闻分类id不为1，那么添加至过滤列表
    if cid != 1:
        filters.append(News.category_id == cid)

    try:
        # filter通过*解包列表传入参数
        # 如果当前cid是1, 解出来就是空,这样就能在所有新闻中查询按时间倒叙查询数据
        # 如果不是1, 那么就得到对应的新闻分类cid, 这样就能查询对应新闻分类的时间倒序数据
        paginate_obj = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)

        # 获取查询出来的每一条数据对象
        items_obj = paginate_obj.items
        # 获取到总页数
        total_page = paginate_obj.pages
        # 获取当前的页面
        current_page = paginate_obj.page

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

    # 迭代所有的数据对象, 获取每一条新闻数据并添加到列表
    news_li = []
    for news in items_obj:
        news_li.append(news.to_basic_dict())

    # 4. 返回数据
    return jsonify(errno=RET.OK,
                   errmsg="OK",
                   total_page=total_page,
                   cur_page=current_page,
                   newsList=news_li,
                   currentCid=cid)
