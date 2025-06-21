import time
import os
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST
from se.util_ros import (
    ROSClient, 
    check_connect, 
    require_ros,
    ctrl_template,
    CtrlType,
    use_ros,
    DIRECTION
)

from backend.settings import DEBUG

from se.util_normal import (
    success_api_response,
    failed_api_response,
    require_jwt,
    response_wrapper,
    get_user,
    ErrorCode,
    require_keys,
    parse_data,
    require_item_exist,
)

from roslibpy.core import RosTimeoutError

from se.models.Map import Map
from se.models.User import User
from se.models.File import File

@response_wrapper
@require_jwt()
@require_POST
@require_keys({"direction", "speed"})
@require_ros
def keyboard_ctrl(request: HttpRequest):
    """
    [POST] /api/ctrl/keyboard
    """
    template = ctrl_template()
    template["type"] = CtrlType.USER_CMD.value
    data = parse_data(request)
    
    dir = data["direction"]
    speed = data["speed"]

    if DIRECTION.get(dir, None) is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "方向走错了，一切努力都是徒劳")

    if not -1e-6 <= speed <= 0.3 + 1e-6:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "速度超过合理范围了")
    
    template["keyboard_ctrl_msg"]["direction"] = DIRECTION[dir]
    
    if DIRECTION[dir] >= 7:
        speed = 0

    template["keyboard_ctrl_msg"]["speed"] = speed

    return use_ros(template, get_user(request))


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"command"})
@require_ros
def command_ctrl(request: HttpRequest):
    """
    [POST] /api/ctrl/command
    """
    template = ctrl_template()
    template["type"] = CtrlType.USER_CMD.value
    
    data = parse_data(request)
    command = data["command"]

    # template["command"] = command

    # dir = 'r'
    # speed = 0.0        
    # if command.find("停") != -1:
    #     dir = 'r'
    #     speed = 0.0
    # elif command.find("前") != -1:
    #     dir = 'w'
    #     speed = 0.1
    # elif command.find("后") != -1:
    #     dir = 's'
    #     speed = 0.1
    # elif command.find("左") != -1 and command.find("转") != -1:
    #     dir = 'q'
    #     speed = 0.1
    # elif command.find("右") != -1 and command.find("转") != -1:
    #     dir = 'e'
    #     speed = 0.1
    # elif command.find("左") != -1:
    #     dir = 'a'
    #     speed = 0.1
    # elif command.find("右") != -1:
    #     dir = 'd'
    #     speed = 0.1
    # elif command.find("抓") != -1 or command.find("取") != -1 or command.find("拿") != -1 or command.find("夹") != -1:
    #     dir = 'g'
    #     speed = 0.0
    from se.api.qwen_api import voice2plan
    dir = voice2plan(command)
    speed = 0.0
    if dir == "r":
        speed = 0.0
    elif len(dir) == 1:
        speed = 0.1

    template["keyboard_ctrl_msg"]["direction"] = DIRECTION[dir]
    template["keyboard_ctrl_msg"]["speed"] = speed

    return use_ros(template, get_user(request))

