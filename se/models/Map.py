from django.db import models

from se.models.File import File
from django.utils import timezone

class Map(models.Model):
    """
    地图模型：
    name: 地图名
    file: 地图文件，外键关联到File模型
    init_x: 地图初始x坐标
    init_y: 地图初始y坐标
    """
    name = models.CharField(max_length=100)
    file = models.ForeignKey(to=File, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    x = models.FloatField(default=0.0)
    y = models.FloatField(default=0.0)