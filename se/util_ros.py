import math
import time

import cv2
import numpy as np
import roslibpy
from django.http import HttpRequest
from roslibpy import ServiceRequest

from se.util_normal import get_user, failed_api_response, ErrorCode
from backend.settings import ROS_PORT, ROS_HOST

from enum import unique, Enum

from se.models.User import User
from se.models.Point import Point

from roslibpy.core import RosTimeoutError

from se.util_normal import success_api_response

def check_connect(user: User):
    ros_client = ROSClient()

    # 若client尚未建立，则建立
    if ros_client.client is None:
        try:
            ros_client.reset(host=ROS_HOST, port=ROS_PORT, user_id=user.id)
        except RosTimeoutError:
            return False
    
    # 确保client建立后进行连接，共有15次尝试机会
    count = 15
    while not ros_client.is_connect and count >= 0:
        time.sleep(0.15)
        count -= 1
    
    # 如果还是没连上，记连接失败
    if not ros_client.is_connect:
        ros_client.failed_count += 1
        # 如果3次都连接失败，则断开
        if ros_client.failed_count >= 3:
            ros_client.exit()
            return False
    
    ros_client.failed_count = 0
    return True


def use_ros(ctrl_msg, user):
    ros_client = ROSClient()
    if not check_connect(user):
        return failed_api_response(ErrorCode.ROS_CONNECT_FAILED, "与 ROS 连接失败，请检查网络或者硬件连接")

    res = ros_client.send_ctrl_req(ctrl_msg)

    if res["code"] != 0:
        print(f"[debug] ros_client.send_ctrl_req failed: {res}\nctrl_msg: {ctrl_msg}")
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, res["msg"])
    return success_api_response()


@unique
class CtrlType(Enum):    
    # STOP_FORCE = 0
    # EXIT = 1

    # USER_CTRL_START = 10
    # USER_CTRL_END = 11
    USER_CMD = 12
    USER_VOICE_CMD = 13
    # USER_GOTO_POINT = 14

    MAPPING_START = 20
    MAPPING_END = 21
    MAPPING_KEY_VEL_CMD = 22
    MAPPING_SAVE_MAP = 23

    NAV_START = 30
    NAV_END = 31 # 导航终止，状态机不再接收导航指令
    NAV_PATROL = 32
    # NAV_GOTO_POINT = 33
    NAV_STOP = 34 # 导航中止，状态机仍然接收导航指令
    # NAV_SET_CURR_POINT = 35
    # NAV_SET_POINT = 36
    # NAV_RENAME_POINT = 37
    # NAV_DELETE_POINT = 38
    # NAV_SELECT_MAP = 39

    # 需要加一些拾取相关的指令 todo
    PICK_TRIGGER = 40 # 触发拾取流程（检测到垃圾且决定拾取）（自动导航至目的地 -> 拾取垃圾 -> 导航到垃圾回收区 -> 扔垃圾）
    PICK_ABORT = 41   # 放弃本次拾取任务



DIRECTION = {
    "r": 0,
    "w": 1,
    "s": 2,
    "a": 3,
    "d": 4,
    "q": 5,
    "e": 6,
    "g": 7,
    "arm_out": 8,
    "arm_in": 9,
    "arm_up": 10,
    "arm_down": 11,
    "grip": 12,
    "release": 13,
    "arm_stop": 14,
}


class ROSClient(object):
    _instance = None
    _flag = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not ROSClient._flag:
            ROSClient._flag = True
            self.counter = 0
            self.failed_count = 0
            self.map_id = 0
            self.user_id = 0
            self.last_op_time = time.time()
            self.client = None
            self.map_service = None
            self.current_pose_service = None
            self.main_ctrl_service = None

    def reset(self, host, port, user_id):
        self.counter = 0
        self.failed_count = 0
        self.map_id = 0
        self.user_id = user_id
        self.client = roslibpy.Ros(host=host, port=port)
        self.map_service = roslibpy.Service(self.client, "/dynamic_map", "nav_msgs/GetMap")
        self.main_ctrl_service = roslibpy.Service(self.client, "/master_node", "Aft_g1/MasterNode")
        self.current_pose_service = roslibpy.Service(self.client, "/cur_pose", "Aft_g1/PoseSrv")
        self.client.run()

    def exit(self):
        self.client.terminate()
        self.counter = 0
        self.failed_count = 0
        self.map_id = 0
        self.user_id = 0
        self.last_op_time = time.time()
        self.client = None
        self.map_service = None
        self.main_ctrl_service = None

    @property
    def is_connect(self):
        if self.client is None:
            return False
        return self.client.is_connected

    def save_map_local(self, name):
        response = self.map_service.call(ServiceRequest({}))
        width = response["map"]["info"]["height"]
        height = response["map"]["info"]["width"]
        m = response["map"]["data"]
        m = np.array(m).reshape((width, height))
        tem = np.zeros((width, height))
        for i in range(width):
            for j in range(height):
                if m[i, j] == -1:
                    tem[width - 1 - i, j] = 127
                else:
                    tem[width - 1 - i, j] = 255 - (m[i, j] * 2)
        cv2.imwrite("./{}.png".format(name), tem)

    def get_current_pose(self):
        response = self.current_pose_service(ServiceRequest({}))
        return response["pose"]

    def send_ctrl_req(self, req: dict):
        """
        msg example:
        {
            "type": 1,
            "keyboard_ctrl_msg": {
                "direction": 1,
                "speed": 0.5,
            },
            "navigation_ctrl_msg": {
                "loop": 0,
                "pose_list": [
                    {
                        "position": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        },
                        "orientation": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "w": 0.0
                        },
                    },
                    {
                        "position": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        },
                        "orientation": {
                        "x": 0.0,
                        "y": 0.0,
                        "z": 0.0,
                        "w": 0.0
                        },
                    },
                ]
                "name_list": [
                    "航点1",
                    "航点2",
                ]
            },
            "command": "去xxx",
        }

        :param req: dict
        :return: None
        """
        req["id"] = self.counter
        self.counter += 1
        return self.main_ctrl_service.call(ServiceRequest(req))


def ctrl_template() -> dict:
    return {
        "type": 0,
        "keyboard_ctrl_msg": {
            "direction": 0,
            "speed": 0,
        },
        "navigation_ctrl_msg": {
            "loop": 0,
            "pose_list": [],
            "name_list": [],
        },
        "command": "",
    }

def pose_template() -> dict:
    return {
        "position": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        },
        "orientation": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "w": 0.0
        },
    }


def ros_quaternion_to_theta(quaternion: dict):
    q0 = quaternion["w"]
    q1 = quaternion["x"]
    q2 = quaternion["y"]
    q3 = quaternion["z"]
    theta = math.atan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (math.pow(q2, 2) + math.pow(q3, 2)))
    return theta


def ros_theta_to_quaternion(theta: float):
    return {
        "w": math.cos(theta / 2),
        "x": 0.0,
        "y": 0.0,
        "z": math.sin(theta / 2),
    }


def require_ros(func):
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = get_user(request)
        ros_client = ROSClient()
        if ros_client.client is None:
            ros_client.reset(host=ROS_HOST, port=ROS_PORT, user_id=user.id)
        if ros_client.client is not None and ros_client.user_id != user.id \
                and time.time() - ros_client.last_op_time < 300:
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "暂时无机器人可用，请稍候")
        return func(request, *args, **kwargs)

    return wrapper


def require_map_selected(func):
    def wrapper(request: HttpRequest, *args, **kwargs):
        ros_client = ROSClient()
        if ros_client.map_id == 0:
            return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "请先选择地图")
        return func(request, *args, **kwargs)

    return wrapper


def ros_wrap_point(x, y, theta):
    return {
        "position": {
            "x": x,
            "y": y,
            "z": 0.0,
        },
        "orientation": ros_theta_to_quaternion(theta),
    }


def pid2name(pid: int) -> str:
    return Point.objects.get(id=pid).name

def pid2pos(pid: int) -> dict:
    point = Point.objects.get(id=pid)
    res = {}
    res["position"] = {
        "x": point.px,
        "y": point.py,
        "z": 0.0,
    }
    res["orientation"] = {
        "x": point.ox,
        "y": point.oy,
        "z": point.oz,
        "w": point.ow,
    }
    return res

def point2pos(point: Point) -> dict:
    res = {}
    res["position"] = {
        "x": point.x,
        "y": point.y,
        "z": point.z,
    }
    res["orientation"] = {
        "x": point.ox,
        "y": point.oy,
        "z": point.oz,
        "w": point.ow,
    }
    return res

