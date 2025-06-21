from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class File(models.Model):
    """
    文件模型: 存储摄像头图片、地图等非结构化数据
    filename: 文件名
    oss_token: 文件在云存储上的唯一标识符
    upload_time: 上传时间
    """
    filename = models.CharField(max_length=100)
    oss_token = models.CharField(max_length=500)
    upload_time = models.DateTimeField(default=timezone.now)    
