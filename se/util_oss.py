from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosClientError, CosServiceError
from se.exceptions import ExternalServiceError


class StorageError(ExternalServiceError):
    pass


@lru_cache(maxsize=1)
def _client(region, secret_id, secret_key):
    return CosS3Client(CosConfig(
        Region=region, SecretId=secret_id, SecretKey=secret_key,
        Scheme="https", Timeout=20,
    ))


def get_client():
    if not all((settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET_NAME)):
        raise StorageError("COS credentials and bucket must be configured.")
    return _client(settings.COS_REGION, settings.COS_SECRET_ID, settings.COS_SECRET_KEY)


def oss_download_url(oss_token):
    return cos_download_url(oss_token, expire=36000)


def cos_download_url(cos_key, expire=3600):
    return get_client().get_presigned_url(
        Method="GET", Bucket=settings.COS_BUCKET_NAME, Key=cos_key, Expired=expire,
    )


def get_oss_token(query_id, filename):
    return get_cos_key(query_id, filename)


def get_cos_key(query_id, filename):
    return f"{query_id}/{uuid4().hex}/{Path(filename).name}"


def oss_upload_local_file(path, oss_token):
    return cos_upload_local_file(path, oss_token)


def cos_upload_local_file(path, cos_key):
    if not Path(path).is_file():
        raise FileNotFoundError(f"Local file not found: {path}")
    try:
        return get_client().upload_file(
            Bucket=settings.COS_BUCKET_NAME, Key=cos_key, LocalFilePath=str(path),
            PartSize=5, MAXThread=2, EnableMD5=True,
        )
    except (CosServiceError, CosClientError) as exc:
        raise StorageError("COS upload failed.") from exc


def delete_object(cos_key):
    try:
        get_client().delete_object(Bucket=settings.COS_BUCKET_NAME, Key=cos_key)
    except (CosServiceError, CosClientError) as exc:
        raise StorageError("COS delete failed.") from exc
