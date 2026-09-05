import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from se.api import detect
from se.api.qwen_api import AIServiceError
from se.models.File import File
from se.models.Log import Log


def jpeg(color="white"):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(buffer, format="JPEG")
    return SimpleUploadedFile("image.jpg", buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def detection(monkeypatch):
    monkeypatch.setattr(detect, "LOGFLAG", True)
    monkeypatch.setattr(detect, "oss_download_url", lambda token: "https://test.invalid/" + token)
    upload, delete = Mock(), Mock()
    monkeypatch.setattr(detect, "oss_upload_local_file", upload)
    monkeypatch.setattr(detect, "delete_object", delete)
    for name in ("detect_fire", "detect_smoke", "detect_stranger", "detect_rubbish"):
        monkeypatch.setattr(detect, name, lambda *args: False)
    return upload, delete


@pytest.mark.django_db
def test_detection_uses_real_position_and_uploads_once(client, detection, monkeypatch):
    monkeypatch.setattr(detect, "detect_fire", lambda *args: True)
    monkeypatch.setattr(detect, "detect_smoke", lambda *args: True)
    response = client.post("/api/detect/upload", {"file": jpeg(), "pos": json.dumps([1.25, -2.5, 0])})
    assert response.status_code == 200
    assert response.json()["stranger"] is None
    assert list(Log.objects.values_list("x", "y")) == [(1.25, -2.5), (1.25, -2.5)]
    assert File.objects.count() == 1
    upload, delete = detection
    upload.assert_called_once()
    delete.assert_not_called()
    assert not Path(upload.call_args.args[0]).exists()


@pytest.mark.django_db
def test_negative_detection_removes_unused_cloud_object(client, detection):
    assert client.post("/api/detect/upload", {"file": jpeg(), "pos": "[0,0,0]"}).status_code == 200
    upload, delete = detection
    delete.assert_called_once_with(upload.call_args.args[1])
    assert File.objects.count() == 0


@pytest.mark.django_db
def test_failed_model_is_502_and_cleans_up(client, detection, monkeypatch):
    monkeypatch.setattr(detect, "detect_fire", Mock(side_effect=AIServiceError("offline")))
    response = client.post("/api/detect/upload", {"file": jpeg(), "pos": "[0,0,0]"})
    assert response.status_code == 502
    detection[1].assert_called_once()
    assert Log.objects.count() == 0


@pytest.mark.parametrize("position", ["null", "[1,2]", "[1,2,NaN]", "invalid"])
def test_invalid_position_is_rejected_before_upload(client, detection, position):
    assert client.post("/api/detect/upload", {"file": jpeg(), "pos": position}).status_code == 400
    detection[0].assert_not_called()


def test_missing_or_invalid_face_upload(authenticated, detection):
    assert authenticated.post("/api/face/upload/test").status_code == 400
    invalid = SimpleUploadedFile("image.jpg", b"not an image")
    assert authenticated.post("/api/face/upload/test", {"file": invalid}).status_code == 400
    detection[0].assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_concurrent_detection_requests_use_distinct_images(detection, monkeypatch):
    barrier = Barrier(2)
    observed = []

    def upload(path, token):
        observed.append((path, token, Path(path).read_bytes()))
        barrier.wait(timeout=5)

    monkeypatch.setattr(detect, "oss_upload_local_file", upload)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(Client().post, "/api/detect/upload", {"file": jpeg(color), "pos": "[0,0,0]"}) for color in ("white", "black")]
        assert [future.result().status_code for future in futures] == [200, 200]
    assert len({item[0] for item in observed}) == 2
    assert len({item[1] for item in observed}) == 2
    assert len({item[2] for item in observed}) == 2
    assert all(not Path(item[0]).exists() for item in observed)
