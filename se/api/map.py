import time
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST, require_http_methods
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
    is_finite_number,
    valid_map_name,
)

from roslibpy.core import RosTimeoutError

from se.models.Map import Map
from se.models.User import User
from se.models.File import File

from se.util_oss import (
    oss_download_url,
    get_oss_token,
    oss_upload_local_file,
)

@response_wrapper
@require_jwt()
@require_GET
@require_ros
def start_mapping(request: HttpRequest):
    """
    [GET] /api/mapping/start
    """
    template = ctrl_template()
    template["type"] = CtrlType.MAPPING_START.value

    user = get_user(request)
    return use_ros(template, user)


@response_wrapper
@require_jwt()
@require_GET
@require_ros
def stop_mapping(request: HttpRequest):
    """
    [GET] /api/mapping/stop
    """
    template = ctrl_template()
    template["type"] = CtrlType.MAPPING_END.value

    user = get_user(request)
    return use_ros(template, user)


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"name"})
@require_ros
def save_map(request: HttpRequest):
    """
    /api/mapping/save
    """
    data = parse_data(request)
    name = data["name"]
    if not valid_map_name(name):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "地图名只能包含字母、数字、汉字、下划线和连字符，长度不超过100")

    if Map.objects.filter(name=name).exists():
        return failed_api_response(ErrorCode.ITEM_ALREADY_EXIST_ERROR, "地图名称已存在")
    
    template = ctrl_template()
    template["type"] = CtrlType.MAPPING_SAVE_MAP.value
    template["navigation_ctrl_msg"]["name_list"].append(name)

    res = use_ros(template, get_user(request))
    if not res["success"]:
        return res
    
    ros_client = ROSClient()
    filename = "{}.png".format(name)
    oss_token = get_oss_token(0, filename)
    with TemporaryDirectory(prefix="ros-map-") as directory:
        info = ros_client.save_map_local(name, directory)
        oss_upload_local_file(str(Path(directory) / filename), oss_token)
    with transaction.atomic():
        file_obj = File.objects.create(filename=filename, oss_token=oss_token)
        origin = info["origin"]["position"]
        map_obj = Map.objects.create(
            file=file_obj, name=name, x=origin["x"], y=origin["y"], resolution=info["resolution"],
        )

    return success_api_response({
        "id": map_obj.id,
        "url": oss_download_url(file_obj.oss_token),
    })


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"direction", "speed"})
@require_ros
def map_move(request: HttpRequest):
    """
    [POST] /api/mapping/move
    """
    template = ctrl_template()
    template["type"] = CtrlType.MAPPING_KEY_VEL_CMD.value
    data = parse_data(request)
    
    dir = data["direction"]
    speed = data["speed"]

    if dir == "g":
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "建图模式下你抓取什么啊？")
    if not isinstance(dir, str) or DIRECTION.get(dir, None) is None:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "方向走错了，一切努力都是徒劳")

    if not is_finite_number(speed) or not 0 <= speed <= 0.3 + 1e-6:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "速度超过合理范围了")
    
    template["keyboard_ctrl_msg"]["direction"] = DIRECTION[dir]
    template["keyboard_ctrl_msg"]["speed"] = speed

    return use_ros(template, get_user(request))


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
def delete_map(request: HttpRequest, map_id):
    """
    [DELETE] /api/mapping/delete
    """
    Map.objects.filter(id=map_id).delete()
    return success_api_response()

@response_wrapper
@require_jwt()
@require_POST
@require_keys({"x", "y", "name"})
def change_map_init(request: HttpRequest):
    """
    [POST] /api/mapping/origin
    """
    data = parse_data(request)
    if not isinstance(data["name"], str) or not all(is_finite_number(data[key]) for key in ("x", "y")):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "地图名称或坐标无效")
    if not Map.objects.filter(name=data["name"]).exists():
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "地图不存在")
    
    map_obj = Map.objects.filter(name = data["name"]).first()
    map_obj.x = data["x"]
    map_obj.y = data["y"]
    map_obj.save()
    return success_api_response()
