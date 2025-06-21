# from datetime import timedelta, datetime

# from django.http import HttpRequest, HttpResponse
# from django.utils.encoding import escape_uri_path
# import oss2
# import os

# from backend.settings import (
#     OSS_SECRET_ID,
#     OSS_SECRET_KEY,
#     OSS_ENDPOINT,
#     OSS_BUCKET_NAME,
# )    

# auth = oss2.Auth(OSS_SECRET_ID, OSS_SECRET_KEY)
# bucket = oss2.Bucket(auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET_NAME)




from datetime import datetime
import os

from qcloud_cos import CosConfig, CosS3Client  # pip install cos-python-sdk-v5
from qcloud_cos.cos_exception import CosServiceError, CosClientError

# Django settings.py 里放这些，不要硬编码
from backend.settings import (
    COS_SECRET_ID,
    COS_SECRET_KEY,
    COS_REGION,        # 例如 "ap-beijing"
    COS_BUCKET_NAME,   # 注意必须带 AppID，如 "mybucket-1250123456"
)

# COS_SECRET_ID = "AKIDBF7870oQwgMrCdv8CMvKWYJJJQTQDmS3"
# COS_SECRET_KEY = "Y1LTORN6cxIUTZaiv1xsjR2Sfi1Vq5DE"
# COS_REGION = "ap-beijing"
# COS_BUCKET_NAME = "db-course-1319328397"

# ---------- 初始化客户端 ----------
_config = CosConfig(
    Region=COS_REGION,
    SecretId=COS_SECRET_ID,
    SecretKey=COS_SECRET_KEY,
    Token=None,
    Scheme="https",
)

cos_client = CosS3Client(_config)

# ---------- 生成下载 URL ----------
def oss_download_url(oss_token: str) -> str:
    return cos_download_url(oss_token, expire=36000)

def cos_download_url(cos_key: str, expire: int = 3600) -> str:
    """生成 COS 对象临时下载链接（默认 1 h 失效）"""
    return cos_client.get_presigned_url(               # 官方接口
        Method="GET",
        Bucket=COS_BUCKET_NAME,
        Key=cos_key,
        Expired=expire,
    )  

# ---------- 生成对象 key ----------
def get_oss_token(query_id: int, filename: str) -> str:
    return get_cos_key(query_id, filename)

def get_cos_key(query_id: int, filename: str) -> str:
    """统一对象命名：query_id/时间戳/文件名（特殊字符转下划线）"""
    for ch in {" ", "(", ")", "/"}:
        filename = filename.replace(ch, "_")
    ts = int(datetime.utcnow().timestamp() * 1000)
    return f"{query_id}/{ts}/{filename}"


# ---------- 上传本地文件 ----------
def oss_upload_local_file(path: str, oss_token: str):
    cos_upload_local_file(path, oss_token)

def cos_upload_local_file(path: str, cos_key: str):
    """上传本地文件到 COS，>20 MB 自动走分片"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Local file not found: {path}")

    try:
        # 高级接口：小文件走简单上传，大文件自动分片断点续传
        cos_client.upload_file(                         # :contentReference[oaicite:1]{index=1}
            Bucket=COS_BUCKET_NAME,
            Key=cos_key,
            LocalFilePath=path,
            PartSize=5 * 1024 * 1024,   # 5 MB 分片
            MAXThread=8,
            EnableMD5=False,
        )
    except (CosServiceError, CosClientError) as e:
        # 留好日志，方便定位 403/404/超时等典型事故
        raise RuntimeError(f"COS upload failed: {e}") from e



if __name__ == "__main__":
    print(get_oss_token(0, "114514.jpg"))




# def oss_download(oss_token: str, filename: str) -> HttpResponse:
#     """
#     download file from Aliyun OSS
#     """
#     try:
#         result = bucket.get_object(oss_token)
#         content = result.read()
#         response = HttpResponse(content)
#         response["Content-Type"] = "application/octet-stream"
#         response["Content-Disposition"] = "attachment;filename*=utf-8''{}".format(escape_uri_path(filename))
#         return response
#     except oss2.exceptions.NoSuchKey:
#         return HttpResponse("File not found", status=404)


# def oss_upload(oss_token: str, request: HttpRequest) -> HttpResponse:
#     """
#     upload file from HttpRequest to OSS
#     """
#     try:
#         file_obj = request.FILES["file"]
#         bucket.put_object(oss_token, file_obj)
#         return HttpResponse("Upload successful", status=200)
#     except Exception as e:
#         return HttpResponse(f"Upload failed: {e}", status=500)


# def oss_download_to_local(oss_token: str, save_path: str):
#     """
#     download file from OSS to local
#     """
#     try:
#         result = bucket.get_object(oss_token)
#         with open(save_path, 'wb') as f:
#             f.write(result.read())
#         # print(f"[下载成功] 保存到 {save_path}")
#     except oss2.exceptions.NoSuchKey:
#         # print(f"[错误] 文件不存在：{oss_token}")
#         pass
    