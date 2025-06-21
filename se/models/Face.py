from django.utils import timezone
from django.db import models

from se.models.File import File


class Face(models.Model):
    """
    人脸模型：
    name: 名字
    # encoding: 二进制形式的编码后的人脸数据
    file: 对应的文件
    """
    name = models.CharField(max_length=50)
    # encodings = models.BinaryField()
    file = models.ForeignKey(to=File, on_delete=models.PROTECT)
    in_white_list = models.BooleanField(default=False)
    upload_time = models.DateTimeField(default=timezone.now)    
