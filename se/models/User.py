from datetime import timedelta

import jwt
from django.db import models
from django.utils import timezone

from backend import settings
from se.models.File import File

ROLE_NORMAL_USER = 0
ROLE_ADMIN = 1


class User(models.Model):
    """
    用户模型：
    username: 用户名，其实就是账号
    password_hash: 密码，这里存储的是加密后的密文
    role: 角色，分为管理员和普通用户
    created_at: 注册时间
    last_login: 最后登录时间
    # user_info: 用户自定义的介绍
    """
    ROLE_TYPE = [
        (ROLE_ADMIN, "管理员"),
        (ROLE_NORMAL_USER, "普通用户"),
    ]

    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    
    role = models.IntegerField(choices=ROLE_TYPE, default=ROLE_NORMAL_USER)
    created_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(default=timezone.now)

    @property
    def token(self):
        token = jwt.encode({
            'exp': timezone.now() - timedelta(hours=8) + timedelta(hours=24),
            'iat': timezone.now() - timedelta(hours=8),
            'username': self.username,
            'role': self.role,
        }, settings.SECRET_KEY, algorithm='HS256')
        return token
