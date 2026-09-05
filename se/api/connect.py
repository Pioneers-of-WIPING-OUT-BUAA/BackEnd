import time
import os
from backend.settings import ROS_HOST, ROS_PORT
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST
from se.util_ros import ROSClient, check_connect, require_ros
from se.util_normal import (
    success_api_response,
    failed_api_response,
    require_jwt,
    response_wrapper,
    get_user,
    ErrorCode,
)
from roslibpy.core import RosTimeoutError



@response_wrapper
@require_jwt()
@require_GET
@require_ros
def connect_ros(request: HttpRequest):
    """
    [GET] /api/ros/connect
    """
    return success_api_response({"connect": True})


@response_wrapper
@require_jwt()
@require_GET
def free_ros(request: HttpRequest):
    """
    [GET] /api/ros/free
    """
    user_id = get_user(request).id
    # 先看看当前连接的用户是否是当前用户
    ros_client = ROSClient()
    with ros_client.lock:
        if ros_client.client is None or ros_client.user_id != user_id:
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "状态错误！")
        ros_client.exit()
    return success_api_response()

@response_wrapper
@require_jwt()
@require_GET
def get_ros_status(request: HttpRequest):
    """
    [GET] /api/ros/connect_status
    """
    is_connect = ROSClient().is_connect
    user_id_connect = ROSClient().user_id
    return success_api_response({"connect": is_connect, "user_id": user_id_connect})
