import json
import math
import re
from functools import wraps
from enum import unique, Enum

import jwt
from django.db import models
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods

from se.models.User import ROLE_ADMIN, User
from backend import settings
from se.exceptions import ExternalServiceError, InvalidInputError
from roslibpy.core import RosTimeoutError


@unique
class ErrorCode(Enum):
    """
    api error code enumeration
    """
    # 请求成功
    SUCCESS_CODE = 200_00
    # 通用的客户端请求错误
    BAD_REQUEST_ERROR = 400_00
    # 请求参数合法性错误
    INVALID_REQUEST_ARGUMENT_ERROR = 400_01
    # 请求参数校验失败
    INVALID_REQUEST_ARGS = 400_02
    # token过期
    TOKEN_EXPIRED = 401_00
    # 用户权限不足
    REFUSE_ACCESS_ERROR = 403_00
    # 数据库中不存在该对象
    ITEM_NOT_FOUND_ERROR = 404_01
    # 数据库中存在该对象
    ITEM_ALREADY_EXIST_ERROR = 404_02
    # 与ROS建立连接失败
    ROS_CONNECT_FAILED = 500_01
    UPSTREAM_ERROR = 502_00
    TOO_MANY_REQUESTS = 429_00


def _api_response(success, data) -> dict:
    return {'success': success, 'data': data}


def success_api_response(data=None) -> dict:
    """
    wrap a success response dict obj
    :param data: requested data
    :return: an api response dictionary
    """
    if data is None:
        data = {"success": True}
    return _api_response(True, data)


def failed_api_response(code, error_msg=None) -> dict:
    """
    wrap an failed response dict obj
    :param code: error code, refers to ErrorCode, can be an integer or a str (error name)
    :param error_msg: external error information
    :return: an api response dictionary
    """
    if isinstance(code, str):
        code = ErrorCode[code]
    elif isinstance(code, int):
        code = ErrorCode(code)
    if error_msg is None:
        error_msg = str(code)
    else:
        error_msg = str(code) + ': ' + error_msg
    status_code = code.value // 100
    detailed_code = code.value
    return _api_response(
        success=False,
        data={
            'code': status_code,
            'detailed_error_code': detailed_code,
            'error_msg': error_msg
        })


def response_wrapper(func):
    """
    decorate a given api-function, parse its return value from a dict to a HttpResponse
    :param func: an api-function
    :return: wrapped function
    """

    @wraps(func)
    def _inner(*args, **kwargs):
        try:
            _response = func(*args, **kwargs)
        except (ExternalServiceError, RosTimeoutError):
            _response = failed_api_response(ErrorCode.UPSTREAM_ERROR, "外部服务调用失败，请稍后重试")
        except InvalidInputError as exc:
            _response = failed_api_response(ErrorCode.INVALID_REQUEST_ARGS, str(exc))
        if isinstance(_response, dict):
            if _response['success']:
                _response = JsonResponse(_response['data'])
            else:
                status_code = _response.get("data").get("code")
                _response = JsonResponse(_response['data'])
                _response.status_code = status_code
        return _response

    return _inner


# pylint:disable=R0911
def require_jwt(admin=False):
    """
    decorator to varify the request jwt token
    :param admin: need admin authority
    :return: wrapped function
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request: HttpRequest, *args, **kwargs):
            try:
                auth = request.META.get('HTTP_AUTHORIZATION').split(" ")
                if len(auth) != 2:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")
            except AttributeError:
                return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "缺少AUTHORIZATION头")

            if auth[0] == "Bearer":
                try:
                    dic = jwt.decode(auth[1], settings.SECRET_KEY, algorithms='HS256')
                    username = dic.get("username", None)
                    role = dic.get("role", None)
                except jwt.ExpiredSignatureError:
                    return failed_api_response(ErrorCode.TOKEN_EXPIRED, "Token过期")
                except jwt.InvalidTokenError:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")

                if username is None or role is None:
                    return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "无效的token")

                user = User.objects.filter(username=username).first()
                if user is None:
                    return failed_api_response(ErrorCode.TOKEN_EXPIRED, "用户不存在，请重新登录")
                request.se_user = user
                if admin and user.role != ROLE_ADMIN:
                    return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "需要管理员权限")

                return view_func(request, *args, **kwargs)
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "错误的AUTHORIZATION头")

        return _wrapped_view

    return decorator


def validate_request(func):
    """
    decorator to validate request with func
    :param func: check function
    :return: wrapped function
    """

    def decorator(function):
        def wrapper(request: HttpRequest, *args, **kwargs):
            if func(request):
                return function(request, *args, **kwargs)
            return failed_api_response(ErrorCode.INVALID_REQUEST_ARGUMENT_ERROR, "非法请求")

        return wrapper

    return decorator


def require_item_exist(model: models.Model, field: str, item: str):
    """
    decorator to check if the query item exist
    :param model: query model
    :param field: query model field
    :param item: request filed (defined in urls.py)
    :return: wrapped function
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            item_id = kwargs.get(item)
            kwargs.pop(item, None)
            if not model.objects.filter(**{field: item_id}).exists():
                return failed_api_response(ErrorCode.ITEM_NOT_FOUND_ERROR, "对象不存在")
            return func(request, item_id, *args, **kwargs)

        return wrapper

    return decorator


def require_item_miss(model: models.Model, field: str, item: str):
    """
    decorator to check if the query item not exist
    :param model: query model
    :param field: query model field
    :param item: request filed (defined in urls.py)
    :return: wrapped function
    """

    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            item_id = kwargs.get(item)
            kwargs.pop(item, None)
            if model.objects.filter(**{field: item_id}).exists():
                return failed_api_response(ErrorCode.ITEM_ALREADY_EXIST_ERROR, "对象已存在")
            return func(request, item_id, *args, **kwargs)

        return wrapper

    return decorator


def parse_data(request: HttpRequest):
    """
    parse request body and return a dict
    :param request: HttpRequest
    :return: request body dict if success else None
    """
    if not hasattr(request, "_se_json_data"):
        try:
            data = json.loads(request.body.decode("utf-8"))
            request._se_json_data = data if isinstance(data, dict) else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            request._se_json_data = None
    return request._se_json_data


def require_keys(key_set: set):
    """
    decorator to check if request body contain keys
    :param key_set: key set
    :return: wrapped function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            data = parse_data(request)
            if data is None:
                return failed_api_response(ErrorCode.BAD_REQUEST_ERROR)
            for key in key_set:
                if data.get(key, None) is None:
                    return failed_api_response(ErrorCode.BAD_REQUEST_ERROR, "缺少必要字段")
            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def filter_data(data: dict, key_set: set) -> None:
    """
    pop key-value from the data whose key not in key_set
    :param data: origin dict
    :param key_set: key set
    :return: None
    """
    remove_keys: set = set()
    for key in data.keys():
        if key not in key_set:
            remove_keys.add(key)
    for key in remove_keys:
        data.pop(key, None)


def wrapped_api(api_dict: dict):
    """
    wrap apis together with 4 methods(get/post/put/delete)
    :param api_dict: dict as {'get': get_api, 'post': post_api ...}
    :return: an api
    """
    assert isinstance(api_dict, dict)
    api_dict = {k.upper(): v for k, v in api_dict.items()}
    assert set(api_dict.keys()).issubset(['GET', 'POST', 'PUT', 'DELETE'])

    @require_http_methods(api_dict.keys())
    def _api(request, *args, **kwargs):
        return api_dict[request.method](request, *args, **kwargs)

    return _api


def get_user(request: HttpRequest) -> User:
    """
    parse request token and return user
    :param request: HttpRequest
    :return: user
    """
    if hasattr(request, "se_user"):
        return request.se_user
    auth = request.META.get('HTTP_AUTHORIZATION').split(" ")
    dic = jwt.decode(auth[1], settings.SECRET_KEY, algorithms='HS256')
    username = dic.get("username", None)
    user = User.objects.get(username=username)
    request.se_user = user
    return user


def is_finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def valid_map_name(value):
    return isinstance(value, str) and re.fullmatch(r"[\w-]{1,100}", value) is not None
