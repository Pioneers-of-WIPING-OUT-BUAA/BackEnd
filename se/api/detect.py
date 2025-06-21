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

from se.api.qwen_api import detect_fire, detect_smoke, detect_stranger, detect_rubbish

from backend.settings import DEBUG, LOGFLAG

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
from se.models.Face import Face
from se.models.Log import Log

from se.util_oss import (
    oss_download_url,
    get_oss_token,
    oss_upload_local_file,
)

from concurrent.futures import ThreadPoolExecutor

@response_wrapper
@require_jwt()
@require_POST
def upload_face(request: HttpRequest, name: str):
    """
    [POST] /api/face/upload/<str:name>
    """
    file = request.FILES.get("file")
    if not file.name.endswith(".jpg"):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "目前只支持jpg格式的图片")
    
    with open("tmp.jpg", "wb") as f:
        for line in file.chunks():
            f.write(line)
    
    new_file = "{}.jpg".format(name)

    file_name = new_file
    oss_token = get_oss_token(0, file_name)
    oss_upload_local_file("tmp.jpg", oss_token=oss_token)

    file_obj = File.objects.create(filename=file_name, oss_token=oss_token)
    face_obj = Face.objects.create(name=name, file=file_obj, in_white_list=True)

    return success_api_response(data={"id": face_obj.id})


@response_wrapper
@require_jwt()
@require_item_exist(Face, "id", "query_id")
def delete_face(request: HttpRequest, query_id):
    """
    [DELETE] /api/face/delete/<int:query_id>
    """
    Face.objects.get(id=query_id).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_GET
def get_face_list(request: HttpRequest):
    """
    [GET] /api/face/list
    """
    def face2dict(face: Face) -> dict:
        return {
            "id": face.id,
            "name": face.name,
            "url": oss_download_url(face.file.oss_token),
        }
    
    faces = Face.objects.filter(in_white_list=True)
    res = {
        "faces": list(map(face2dict, faces))
    }
    return success_api_response(res)



@response_wrapper
@require_POST
def detect(request: HttpRequest):
    """
    [POST] /api/detect/upload
    """
    if not LOGFLAG:
        return success_api_response({
            "fire": False,
            "smoke": False,
            "stranger": False,
            "rubbish": False,
        })
    
    # print(request)  
    # data = parse_data(request)
    # pos = data['pos']
    import random
    p = random.random()
    if p < 0.05:
        x = random.uniform(-2, -1)
    elif p < 0.2:
        x = random.uniform(-1, 0)
    elif p < 0.7:
        x = random.uniform(0, 1)
    else:
        x = random.uniform(1, 2)

    p = random.random()
    if p < 0.05:
        y = random.uniform(-3, -1)
    elif p < 0.2:
        y = random.uniform(-1, 0)
    elif p < 0.7:
        y = random.uniform(0, 1)
    else:
        y = random.uniform(1, 3)    



    now_time = time.time()

    file = request.FILES.get("file")
    if not file.name.endswith(".jpg"):
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "目前只支持jpg格式的图片")
    
    with open("detect.jpg", "wb") as f:
        for line in file.chunks():
            f.write(line)

    tmp_oss_token = "0/1749531183635/114514.jpg"

    oss_upload_local_file("detect.jpg", oss_token=tmp_oss_token)
    detect_url = oss_download_url(tmp_oss_token)

    # detect_path = os.path.abspath("detect.jpg")

    # latest_face = Face.objects.order_by("-upload_time").first()
    # print(Face.objects.count())
    latest_face = Face.objects.first()
    white_url = oss_download_url(latest_face.file.oss_token)
    # oss_token = latest_face.file.oss_token
    # white_path = detect_path.replace("detect.jpg", "white.jpg")
    # oss_download(oss_token, white_path)
    print("detect_url:", white_url)

    
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_fire = executor.submit(detect_fire, detect_url)
        future_smoke = executor.submit(detect_smoke, detect_url)
        future_stranger = executor.submit(detect_stranger, detect_url, white_url)
        future_rubbish = executor.submit(detect_rubbish, detect_url)

        fire_flag = future_fire.result()
        smoke_flag = future_smoke.result()
        stranger_flag = future_stranger.result()
        rubbish_flag = future_rubbish.result()
    
    if fire_flag:
        oss_token = get_oss_token(0, "detect-fire.jpg")
        oss_upload_local_file("detect.jpg", oss_token=oss_token)
        file_obj = File.objects.create(
            filename="detect-fire.jpg",
            oss_token=oss_token,
        )
        Log.objects.create(
            event_type=1,
            detail="发现明火",
            file=file_obj,
            x=x,
            y=y,
        )

    if smoke_flag:
        oss_token = get_oss_token(0, "detect-smoke.jpg")
        oss_upload_local_file("detect.jpg", oss_token=oss_token)
        file_obj = File.objects.create(
            filename="detect-smoke.jpg",
            oss_token=oss_token,
        )
        Log.objects.create(
            event_type=2,
            detail="发现烟雾",
            file=file_obj,
            x=x,
            y=y,
        )

    if stranger_flag:
        oss_token = get_oss_token(0, "detect-stranger.jpg")
        oss_upload_local_file("detect.jpg", oss_token=oss_token)
        file_obj = File.objects.create(
            filename="detect-stranger.jpg",
            oss_token=oss_token,
        )
        Log.objects.create(
            event_type=3,
            detail="发现陌生人",
            file=file_obj,
            x=x,
            y=y,
        )
    
    if rubbish_flag:
        oss_token = get_oss_token(0, "detect-rubbish.jpg")
        oss_upload_local_file("detect.jpg", oss_token=oss_token)
        file_obj = File.objects.create(
            filename="detect-rubbish.jpg",
            oss_token=oss_token,
        )
        Log.objects.create(
            event_type=4,
            detail="发现垃圾",
            file=file_obj,
            x=x,
            y=y,
        )

    return success_api_response({
        "fire": fire_flag,
        "smoke": smoke_flag,
        "stranger": stranger_flag,
        "rubbish": rubbish_flag,
    })


def log2dict(log: Log) -> dict:
    return {
        "id": log.id,
        "event_type": log.event_type,
        "detail": log.detail,
        "time": log.time,
        "x": log.x,
        "y": log.y,
        "url": oss_download_url(log.file.oss_token),
    }


@response_wrapper
@require_jwt()
@require_GET
def get_log_list(request: HttpRequest):
    """
    [GET] /api/log/list
    """
    # Log.objects.all().delete()
    logs = Log.objects.all().order_by("-id")
    return success_api_response({"logs": list(map(log2dict, logs))})


@response_wrapper
@require_jwt()
@require_GET
def get_latest_log(request: HttpRequest):
    """
    [GET] /api/log/latest
    """
    log = Log.objects.all().order_by("-id").first()
    return success_api_response({"log": log2dict(log)})


@response_wrapper
@require_jwt()
@require_POST
def begin_log(request: HttpRequest):
    """
    [GET] /api/log/begin
    """
    global LOGFLAG
    if not LOGFLAG:
        LOGFLAG = True
        return success_api_response({"message": "日志记录已开始"})
    else:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "日志记录已在进行中，请勿重复开始")

@response_wrapper
@require_jwt()
@require_POST
def end_log(request: HttpRequest):
    """
    [GET] /api/log/end
    """
    global LOGFLAG
    if LOGFLAG:
        LOGFLAG = False
        return success_api_response({"message": "日志记录已结束"})
    else:
        return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "日志记录未开始，请勿重复结束")


@response_wrapper
@require_jwt()
@require_GET
def get_log_flag(request: HttpRequest):
    """
    [GET] /api/log/flag
    """
    return success_api_response({'log': LOGFLAG})
