from unittest.mock import Mock

import pytest

from se import util_oss


def test_object_keys_cannot_collide_or_contain_parent_paths():
    first = util_oss.get_oss_token(0, "../frame.jpg")
    second = util_oss.get_oss_token(0, "../frame.jpg")
    assert first != second
    assert first.startswith("0/") and first.endswith("/frame.jpg")
    assert ".." not in first


def test_upload_uses_sdk_megabyte_units(monkeypatch, tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"test")
    client = Mock()
    monkeypatch.setattr(util_oss, "get_client", lambda: client)
    util_oss.oss_upload_local_file(image, "test-key")
    assert client.upload_file.call_args.kwargs["PartSize"] == 5


def test_missing_storage_configuration_fails_explicitly(settings):
    settings.COS_SECRET_ID = ""
    with pytest.raises(util_oss.StorageError, match="configured"):
        util_oss.get_client()
