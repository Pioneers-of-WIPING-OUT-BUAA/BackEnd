import time
import os
from backend.settings import ROS_HOST, ROS_PORT
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST
from se.util_ros import ROSClient, check_connect
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
def connect_ros(request: HttpRequest):
    """
    [GET] /api/ros/connect
    """
    ros_client = ROSClient()
    user = get_user(request)
    
    if ros_client.client is None:
        ros_client.reset(host=ROS_HOST, port=ROS_PORT, user_id=user.id)
    else:
        # 如果当前连接的用户不是当前用户，则重置连接
        if ros_client.user_id != user.id:
            if time.time() - ros_client.last_op_time < 300:
                return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "暂时无机器人可用，请稍候")
            else:
                try:
                    ros_client.reset(host=ROS_HOST, port=ROS_PORT, user_id=user.id)
                except RosTimeoutError:
                    failed_api_response(ErrorCode.ROS_CONNECT_FAILED, "ROS连接失败，请检查相关配置是否正确以及网络是否连通")
    
    # 检查一下连接是否成功
    flag = ros_client.user_id == user.id and check_connect(user)
    if not flag:
        return failed_api_response(ErrorCode.ROS_CONNECT_FAILED, "ROS连接失败，请检查相关配置是否正确以及网络是否连通")
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
    if ROSClient().client is None or ROSClient().user_id != user_id:
        return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "状态错误！")
    # 如果是当前用户，则释放连接
    ROSClient().exit()
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
