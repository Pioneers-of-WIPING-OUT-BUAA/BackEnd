from django.db import models
from django.utils import timezone

from se.models.File import File




class Log(models.Model):
    """
    日志模型：
    detail: 操作详情，如： 等
    
    """
    EVENT_TYPE = [
        (1, "发现明火"),
        (2, "发现烟雾"),
        (3, "发现陌生人"),
        (4, "发现垃圾"),
    ] 
    event_type = models.IntegerField(choices=EVENT_TYPE, default=0)
    detail = models.CharField(max_length=100)
    time = models.DateTimeField(default=timezone.now)
    x = models.FloatField(default=0.0)
    y = models.FloatField(default=0.0)
    file = models.ForeignKey(to=File, null=True, on_delete=models.SET_NULL)