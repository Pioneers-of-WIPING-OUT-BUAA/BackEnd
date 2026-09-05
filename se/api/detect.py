import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore, Lock

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from PIL import Image, UnidentifiedImageError

from se.api.qwen_api import detect_fire, detect_smoke, detect_stranger, detect_rubbish
from se.exceptions import InvalidInputError
from se.models.Face import Face
from se.models.File import File
from se.models.Log import Log
from se.util_normal import (
    success_api_response, failed_api_response, require_jwt, response_wrapper,
    ErrorCode, require_item_exist, is_finite_number,
)
from se.util_oss import oss_download_url, get_oss_token, oss_upload_local_file, delete_object


LOGFLAG = False
_log_lock = Lock()
_detection_slots = BoundedSemaphore(2)
_executor = ThreadPoolExecutor(max_workers=8)
logger = logging.getLogger(__name__)


def _save_jpeg(upload, directory):
    if upload is None or upload.size > 8 * 1024 * 1024:
        raise InvalidInputError("请上传不超过8MB的JPEG图片")
    try:
        with Image.open(upload) as image:
            if image.format != "JPEG" or image.width * image.height > 20000000:
                raise InvalidInputError("请上传有效JPEG图片")
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidInputError("图片内容无效") from exc
    upload.seek(0)
    path = Path(directory) / "image.jpg"
    with path.open("wb") as target:
        for chunk in upload.chunks():
            target.write(chunk)
    return str(path)


def _remove_unreferenced_image(token):
    try:
        delete_object(token)
    except Exception:
        logger.exception("Failed to remove an unused detection image")


@response_wrapper
@require_jwt()
@require_POST
def upload_face(request: HttpRequest, name: str):
    if not 1 <= len(name.strip()) <= 50:
        raise InvalidInputError("人脸名称无效")
    token = get_oss_token(0, f"{name}.jpg")
    with TemporaryDirectory(prefix="ros-face-") as directory:
        path = _save_jpeg(request.FILES.get("file"), directory)
        oss_upload_local_file(path, token)
    try:
        with transaction.atomic():
            file_obj = File.objects.create(filename=f"{name}.jpg", oss_token=token)
            face = Face.objects.create(name=name, file=file_obj, in_white_list=True)
    except Exception:
        _remove_unreferenced_image(token)
        raise
    return success_api_response({"id": face.id})


@response_wrapper
@require_jwt()
@require_http_methods(["DELETE"])
@require_item_exist(Face, "id", "query_id")
def delete_face(request: HttpRequest, query_id):
    Face.objects.get(id=query_id).delete()
    return success_api_response()


@response_wrapper
@require_jwt()
@require_GET
def get_face_list(request: HttpRequest):
    faces = Face.objects.filter(in_white_list=True).select_related("file")
    return success_api_response({"faces": [
        {"id": face.id, "name": face.name, "url": oss_download_url(face.file.oss_token)}
        for face in faces
    ]})


@response_wrapper
@require_POST
def detect(request: HttpRequest):
    if not LOGFLAG:
        return success_api_response(dict.fromkeys(("fire", "smoke", "stranger", "rubbish"), False))
    try:
        pos = json.loads(request.POST.get("pos", "null"))
    except json.JSONDecodeError as exc:
        raise InvalidInputError("位置数据无效") from exc
    if not isinstance(pos, list) or len(pos) != 3 or not all(is_finite_number(value) for value in pos):
        raise InvalidInputError("请提供三个有限数值组成的位置坐标")
    if not _detection_slots.acquire(blocking=False):
        return failed_api_response(ErrorCode.TOO_MANY_REQUESTS, "识别任务繁忙，请稍后重试")
    token = get_oss_token(0, "detect.jpg")
    uploaded = False
    retained = False
    try:
        with TemporaryDirectory(prefix="ros-detect-") as directory:
            path = _save_jpeg(request.FILES.get("file"), directory)
            oss_upload_local_file(path, token)
            uploaded = True
            url = oss_download_url(token)
            face = Face.objects.filter(in_white_list=True).select_related("file").first()
            futures = {
                "fire": _executor.submit(detect_fire, url),
                "smoke": _executor.submit(detect_smoke, url),
                "rubbish": _executor.submit(detect_rubbish, url),
            }
            if face is not None:
                futures["stranger"] = _executor.submit(detect_stranger, url, oss_download_url(face.file.oss_token))
            # Wait for every reader before deleting its shared cloud image.
            try:
                flags = {name: future.result() for name, future in futures.items()}
            finally:
                for future in futures.values():
                    try:
                        future.result()
                    except Exception:
                        pass
            flags.setdefault("stranger", None)
            events = [
                (1, "发现明火", flags["fire"]), (2, "发现烟雾", flags["smoke"]),
                (3, "发现陌生人", flags["stranger"]), (4, "发现垃圾", flags["rubbish"]),
            ]
            if any(flag for _, _, flag in events):
                with transaction.atomic():
                    file_obj = File.objects.create(filename="detect.jpg", oss_token=token)
                    Log.objects.bulk_create([
                        Log(event_type=event_type, detail=detail, file=file_obj, x=pos[0], y=pos[1])
                        for event_type, detail, flag in events if flag
                    ])
                retained = True
            return success_api_response(flags)
    finally:
        if uploaded and not retained:
            _remove_unreferenced_image(token)
        _detection_slots.release()


def log2dict(log):
    if log is None:
        return None
    return {
        "id": log.id, "event_type": log.event_type, "detail": log.detail,
        "time": log.time, "x": log.x, "y": log.y,
        "url": oss_download_url(log.file.oss_token) if log.file_id else None,
    }


@response_wrapper
@require_jwt()
@require_GET
def get_log_list(request: HttpRequest):
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 50))
    except (TypeError, ValueError) as exc:
        raise InvalidInputError("分页参数无效") from exc
    if page < 1 or not 1 <= page_size <= 100:
        raise InvalidInputError("页码必须大于0，每页最多100条日志")
    logs = Log.objects.select_related("file").order_by("-id")
    total = logs.count()
    offset = (page - 1) * page_size
    return success_api_response({
        "logs": [log2dict(log) for log in logs[offset:offset + page_size]],
        "total": total, "page": page, "page_size": page_size,
    })


@response_wrapper
@require_jwt()
@require_GET
def get_latest_log(request: HttpRequest):
    return success_api_response({"log": log2dict(Log.objects.select_related("file").order_by("-id").first())})


@response_wrapper
@require_jwt()
@require_POST
def begin_log(request: HttpRequest):
    global LOGFLAG
    with _log_lock:
        if LOGFLAG:
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "日志记录已在进行中")
        LOGFLAG = True
    return success_api_response({"message": "日志记录已开始"})


@response_wrapper
@require_jwt()
@require_POST
def end_log(request: HttpRequest):
    global LOGFLAG
    with _log_lock:
        if not LOGFLAG:
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, "日志记录未开始")
        LOGFLAG = False
    return success_api_response({"message": "日志记录已结束"})


@response_wrapper
@require_jwt()
@require_GET
def get_log_flag(request: HttpRequest):
    return success_api_response({"log": LOGFLAG})
