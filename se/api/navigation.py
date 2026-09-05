import time
import os
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from se.util_ros import (
    ROSClient, 
    check_connect, 
    require_ros,
    ctrl_template,
    CtrlType,
    use_ros,
    DIRECTION,
    pid2name,
    pid2pos,
    point2pos,
    ros_wrap_point,
    ros_quaternion_to_theta
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
)

from roslibpy.core import RosTimeoutError

from se.models.Map import Map
from se.models.User import User
from se.models.File import File
from se.models.Point import Point

from se.util_oss import (
    oss_download_url,
)


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Map, "id", "query_id")
@require_ros
def start_nav(request: HttpRequest, query_id):
    """
    [GET] /api/navigation/start/<int:query_id>
    """
    template = ctrl_template()
    template["type"] = CtrlType.NAV_START.value
    map_obj = Map.objects.get(id = query_id)

    template['navigation_ctrl_msg']['name_list'].append(map_obj.name)

    ros_client = ROSClient()
    user = get_user(request)
    response = use_ros(template, user)
    if response["success"]:
        ros_client.map_id = map_obj.id
    return response


@response_wrapper
@require_jwt()
@require_GET
@require_ros
def end_nav(request: HttpRequest):
    """
    [GET] /api/navigation/end
    """
    template = ctrl_template()
    template["type"] = CtrlType.NAV_END.value

    user = get_user(request)
    response = use_ros(template, user)
    if response["success"]:
        ROSClient().map_id = 0
    return response


# def move(request: HttpRequest):
#     """
#     [POST] /api/navigation/move
#     """
# 不实现了

@response_wrapper
@require_jwt()
@require_POST
@require_keys({"path"})
@require_ros
def patrol(request: HttpRequest):
    """
    [POST] /api/navigation/patrol
    """
    data = parse_data(request)
    path = data["path"]
    loop = data.get("loop", 0)
    if not isinstance(path, list) or not 1 <= len(path) <= 500 \
            or any(type(pid) is not int or pid <= 0 for pid in path):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "请提供有效航点列表")
    if type(loop) is not int or loop not in (0, 1):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "循环模式只能为0或1")
    map_id = ROSClient().map_id
    if not map_id or data.get("map", map_id) != map_id:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "请先选择正确的导航地图")
    points = Point.objects.filter(mmap_id=map_id).in_bulk(path)
    if any(pid not in points for pid in path):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "航点不存在或不属于当前地图")
    template = ctrl_template()
    template["type"] = CtrlType.NAV_PATROL.value
    template["navigation_ctrl_msg"]["name_list"] = [points[pid].name for pid in path]
    template["navigation_ctrl_msg"]["pose_list"] = [points[pid].pose for pid in path]
    template["navigation_ctrl_msg"]["loop"] = loop

    user = get_user(request)
    return use_ros(template, user)

@response_wrapper
@require_jwt()
@require_GET
@require_ros
def stop_nav(request: HttpRequest):
    """
    [GET] /api/navigation/stop
    """
    template = ctrl_template()
    template["type"] = CtrlType.NAV_STOP.value

    user = get_user(request)
    return use_ros(template, user)


@response_wrapper
@require_jwt()
@require_POST
@require_keys({"name", "x", "y", "theta"})
@require_item_exist(Map, "id", "query_id")
def mark_point(request: HttpRequest, query_id):
    """
    [POST] /api/navigation/mark/<int:query_id>
    """
    data = parse_data(request)
    name = data["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 50 \
            or not all(is_finite_number(data[key]) for key in ("x", "y", "theta")):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "航点名称或坐标无效")

    if Point.objects.filter(mmap_id=query_id, name=name).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "航点名称已存在")

    pos = ros_wrap_point(data["x"], data["y"], data["theta"])

    point = Point.objects.create(
        mmap_id = query_id,
        name = name,
        px = pos['position']['x'],
        py = pos['position']['y'],
        pz = pos['position']['z'],
        ox = pos['orientation']['x'],
        oy = pos['orientation']['y'],
        oz = pos['orientation']['z'],
        ow = pos['orientation']['w'],
    )    

    return success_api_response({"id": point.id})



@response_wrapper
@require_jwt()
@require_POST
@require_keys({"id", "name"})
def rename_point(request: HttpRequest):
    """
    [POST] /api/navigation/rename
    """
    data = parse_data(request)
    if type(data["id"]) is not int or not isinstance(data["name"], str) or not 1 <= len(data["name"].strip()) <= 50:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "航点编号或名称无效")
    point = Point.objects.filter(id=data["id"]).first()
    if point is None:
        return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "航点不存在")

    if Point.objects.filter(mmap_id=point.mmap_id, name=data["name"]).exclude(id=point.id).exists():
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "目标航点名称已存在")

    point.name = data["name"]
    point.save()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(Point, "id", "query_id")
def delete_point(request: HttpRequest, query_id):
    """
    [DELETE] /api/navigation/delete/<int:query_id>
    """
    point = Point.objects.get(id=query_id)
    point.delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_GET
def get_map_list(request: HttpRequest):
    """
    [GET] /api/navigation/map_list
    """
    def map2dict(map_obj: Map):
        return {
            "id": map_obj.id,
            "name": map_obj.name,
            "url": oss_download_url(map_obj.file.oss_token),
            "x": map_obj.x,
            "y": map_obj.y,
            "resolution": map_obj.resolution,
        }

    data = {"maps": list(map(map2dict, Map.objects.select_related("file").all()))}
    return success_api_response(data)


@response_wrapper
@require_jwt()
@require_GET
@require_item_exist(Map, "id", "query_id")
def get_point_list(request: HttpRequest, query_id):
    """
    [POST] /api/navigation/point_list/<int:query_id>
    """
    def point2dict(point_obj: Point):
        return {
            "id": point_obj.id,
            "name": point_obj.name,
            "x": point_obj.px,
            "y": point_obj.py,
            "theta": ros_quaternion_to_theta({
                "x": 0,
                "y": 0,
                "z": point_obj.oz,
                "w": point_obj.ow,
            })
        }
    point_list = Point.objects.filter(mmap_id=query_id).order_by("id")

    data = {"points": list(map(point2dict, point_list))}
    return success_api_response(data)

