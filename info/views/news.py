# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/16 17:06
# @Author : Jerome
from flask import Blueprint, current_app, request, jsonify, g, abort
from flask import render_template
from info import constants, db
from info.libs.function.user_status import user_login_data
from info.models import News, Comment, CommentLike, User
from info.response_code import RET

news_blue = Blueprint("news", __name__, url_prefix='/news')


@news_blue.route('/<int:news_id>')
@user_login_data
def news_detail(news_id):
    """处理每一个新闻详情页面请求的视图函数"""
    news_obj = None
    try:
        """通过接收的新闻id查询news数据对象"""
        news_obj = News.query.get(news_id)

        print("请求新闻成功, id: ", news_id)

    except Exception as e:
        current_app.logger(e)
        abort(404)

    if not news_obj:
        """查询结果为空"""
        abort(404)

    # 将当前新闻的点击量 + 1
    news_obj.clicks += 1
    db.session.commit()

    # 为当前页面获取点击排行数据
    news_list_obj = None  # 默认新闻列表对象为空, 用来存数据对象
    try:
        news_list_obj = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)

    click_news_list = []  # 定义一个空列表, 用来存新闻
    for i in news_list_obj:
        click_news_list.append(i.to_basic_dict())

    # # 定义一个变量, 保存用户对当前新闻的收藏情况, 默认为False
    # is_collected = False
    # # 判断用户是否收藏过该新闻
    # if g.user:
    #     if news_obj in g.user.collection_news:
    #         is_collected = True

    # 当前登录用户是否关注当前新闻作者
    is_followed = False
    # 判断用户是否收藏过该新闻
    is_collected = False
    if g.user:
        if news_obj in g.user.collection_news:
            is_collected = True

        if news_obj.user:
            if news_obj.user.followers.filter(User.id == g.user.id).count() > 0:
                is_followed = True

    # 获取当前新闻的评论
    comments_obj = []  # 用来储存查询到的所有评论数据对象
    try:
        comments_obj = Comment.query.filter(Comment.news_id == news_id).order_by(Comment.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)

    # 评论点赞
    # 使用装饰器后从g变量中获取user数据对象
    user = g.user

    all_comment_like_id = []
    if user:
        # 用列表推导式获取当前页面所有评论的id
        comment_id_list = [i.id for i in comments_obj]
        if len(comment_id_list) > 0:
            all_comment_like_obj = CommentLike.query.filter(CommentLike.comment_id in comment_id_list,
                                                            CommentLike.user_id == user.id).all()
            all_comment_like_id = [i.comment_id for i in all_comment_like_obj]

    comment_info = []  # 用来储存所有评论数据对象的数据信息
    for i in comments_obj:
        comment_dict = i.to_dict()
        comment_dict["is_like"] = False
        if i.id in all_comment_like_id:
            comment_dict["is_like"] = True
        comment_info.append(comment_dict)

    # 定义data字典, 用来与html交互数据
    data = {
        "user_info": user.to_dict() if user else None,  # 用户信息
        "news": news_obj.to_dict(),  # 新闻数据对象
        "click_news_list": click_news_list,  # 点击量排行前十的新闻
        "comments": comment_info,  # 新闻的评论信息
        "is_collected": is_collected,  # 当前用户对该新闻的收藏情况
        "is_followed": is_followed  # 当前用户是否关注了当前新闻的作者
    }

    return render_template('news/detail.html', data=data)


@news_blue.route("/news_collect", methods=["POST"])
@user_login_data
def news_collect():
    recv_para = request.json
    news_id = recv_para.get("news_id")
    action = recv_para.get("action")

    print("新闻id: ", news_id, "请求操作的动作", action)

    user = g.user

    # 验证用户是否登录
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 验证提交的参数是否齐全
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 验证提交的动作是否合法
    if action not in ("collect", "cancel_collect"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询欲收藏的新闻是否存在
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻数据不存在")

    print(user.id)

    if action == "collect":
        user.collection_news.append(news)
    else:
        user.collection_news.remove(news)

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存失败")

    return jsonify(errno=RET.OK, errmsg="操作成功")


@news_blue.route("/news_comment", methods=["POST"])
@user_login_data
def news_comment():
    recv_para = request.json
    news_id = recv_para.get("news_id")
    comment = recv_para.get("comment")
    parent_id = recv_para.get("parent_id")

    print("新闻id: %s\n评论的内容: %s\n上一楼层的id: %s" % (news_id, comment, parent_id))

    user = g.user

    # 验证用户是否登录
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 验证提交的参数是否齐全
    if not all([news_id, comment]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 查询评论的新闻是否存在
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据失败")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="该新闻不存在")

    # 初始化模型，保存数据
    comments = Comment()
    comments.user_id = user.id
    comments.news_id = news_id
    comments.content = comment
    if parent_id:
        comments.parent_id = parent_id

    # 保存到数据库
    try:
        db.session.add(comments)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存评论数据失败")

    # 返回响应
    return jsonify(errno=RET.OK, errmsg="评论成功", data=comments.to_dict())


@news_blue.route("/comment_like", methods=["POST"])
@user_login_data
def comment_likes():
    # 接收参数
    recv_para = request.json
    comment_id = recv_para.get("comment_id")
    news_id = recv_para.get("news_id")
    action = recv_para.get("action")

    print("评论id: %s\n新闻id: %s\n操作: %s" % (comment_id, news_id, action))

    # 检查用户是否登录
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    # 验证提交的参数是否齐全
    if not all([comment_id, news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 验证提交的动作是否合法
    if action not in ("add", "remove"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询想要点赞的评论是否存在
    try:
        comment = Comment.query.get(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")
    if not comment:
        return jsonify(errno=RET.NODATA, errmsg="该新闻不存在")

    if action == "add":
        # 从评论点赞表中获取数据对象
        comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=user.id).first()

        if not comment_like:
            """不存在就创建评论点赞数据并添加"""
            comment_like = CommentLike()
            comment_like.comment_id = comment_id
            comment_like.user_id = user.id
            db.session.add(comment_like)
            # 增加点赞条数
            comment.like_count += 1
    else:
        # 删除点赞数据
        comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=g.user.id).first()
        if comment_like:
            db.session.delete(comment_like)
            # 减小点赞条数
            comment.like_count -= 1

    try:
        """提交修改"""
        db.session.commit()
    except Exception as e:
        """出错回滚"""
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="操作失败")

    return jsonify(errno=RET.OK, errmsg="操作成功")


@news_blue.route('/followed_user', methods=["POST"])
@user_login_data
def followed_user():
    """关注/取消关注用户"""
    if not g.user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    user_id = request.json.get("user_id")
    action = request.json.get("action")

    if not all([user_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    if action not in ("follow", "unfollow"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询到关注的用户信息
    try:
        target_user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据库失败")

    if not target_user:
        return jsonify(errno=RET.NODATA, errmsg="未查询到用户数据")

    # 根据不同操作做不同逻辑
    if action == "follow":
        if target_user.followers.filter(User.id == g.user.id).count() > 0:
            return jsonify(errno=RET.DATAEXIST, errmsg="当前已关注")
        target_user.followers.append(g.user)
    else:
        if target_user.followers.filter(User.id == g.user.id).count() > 0:
            target_user.followers.remove(g.user)
        else:
            return jsonify(errno=RET.DATAEXIST, errmsg="用户未关注")

    # 保存到数据库
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据保存错误")

    return jsonify(errno=RET.OK, errmsg="操作成功")
