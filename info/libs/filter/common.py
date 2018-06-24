# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/15 23:01
# @Author : Jerome


def do_index_class(index):
    """自定义过滤器，过滤点击排序html的class"""
    if index == 0:
        return "first"
    elif index == 1:
        return "second"
    elif index == 2:
        return "third"
    else:
        return ""