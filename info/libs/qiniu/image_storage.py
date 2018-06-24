# ！/usr/bin/env python
# _*_ coding:utf-8 _*_
# @Time   : 2018/6/20 18:49
# @Author : Jerome
# -*- coding: utf-8 -*-

import logging

import qiniu
from qiniu import Auth, put_data

# 需要填写你的 Access Key 和 Secret Key
access_key = "yV4GmNBLOgQK-1Sn3o4jktGLFdFSrlywR2C-hvsW"
secret_key = "bixMURPL6tHjrb8QKVg2tm7n9k8C7vaOeQ4MEoeW"
bucket_name = "ihome"


def storage(data):
    try:
        q = qiniu.Auth(access_key, secret_key)
        # key = 'hello'
        # data = 'hello qiniu!'
        token = q.upload_token(bucket_name)
        ret, info = qiniu.put_data(token, None, data)
        print(ret, info)
    except Exception as e:
        raise e

    if info.status_code != 200:
        raise Exception("上传图片失败")
    return ret["key"]


if __name__ == '__main__':
    with open("./2.png", "rb") as f:
        file_data = f.read()
        storage(file_data)
