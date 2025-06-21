from django.urls import path
from .views import add_one

from se.api.auth import login, register, update_password, get_user_detail
from se.api.connect import connect_ros, free_ros, get_ros_status
from se.api.map import start_mapping, stop_mapping, save_map, map_move, delete_map, change_map_init
from se.api.user_ctrl import keyboard_ctrl, command_ctrl
from se.api.navigation import start_nav, end_nav, patrol, stop_nav, mark_point, rename_point, delete_point, get_map_list, get_point_list
from se.api.detect import upload_face, delete_face, get_face_list, detect, get_log_list, get_latest_log, begin_log, end_log, get_log_flag


urlpatterns = [
    # test api
    path('add_one/', add_one),

    # auth api
    path("auth/login", login),
    path("auth/register", register),
    path("auth/update", update_password),
    path("auth/detail", get_user_detail),

    # connect api
    path("ros/connect", connect_ros),
    path("ros/free", free_ros),
    path("ros/connect_status", get_ros_status),

    # map api
    path("mapping/start", start_mapping),
    path("mapping/stop", stop_mapping),
    path("mapping/save", save_map),
    path("mapping/move", map_move),
    path("mapping/delete/<int:map_id>", delete_map),
    path("mapping/origin", change_map_init),

    # ctrl api
    path("user_ctrl/keyboard", keyboard_ctrl),
    path("user_ctrl/command", command_ctrl),

    # navigation api
    path("navigation/start/<int:query_id>", start_nav),
    path("navigation/end", end_nav),
    path("navigation/patrol", patrol),
    path("navigation/stop", stop_nav),
    path("navigation/mark/<int:query_id>", mark_point),
    path("navigation/rename", rename_point),
    path("navigation/delete/<int:query_id>", delete_point),
    path("navigation/map_list", get_map_list),
    path("navigation/point_list/<int:query_id>", get_point_list),


    # face api
    path("face/upload/<str:name>", upload_face),
    path("face/delete/<int:query_id>", delete_face),
    path("face/list", get_face_list),
    
    # detect api
    path("detect/upload", detect),

    # log api
    path("log/list", get_log_list),
    path("log/latest", get_latest_log),

    path("log/begin", begin_log),
    path("log/end", end_log),
    path("log/flag", get_log_flag),
]
