from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from se.api import qwen_api


def test_vision_request_uses_configured_model_and_both_images(monkeypatch, settings):
    settings.OPENROUTER_MODEL = "test/model"
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="是"))]
    )
    monkeypatch.setattr(qwen_api, "get_client", lambda: client)
    assert qwen_api.infer("image-one", "image-two", "test") == "是"
    request = client.chat.completions.create.call_args.kwargs
    assert request["model"] == "test/model"
    assert [part["image_url"]["url"] for part in request["messages"][1]["content"][:2]] == ["image-one", "image-two"]


@pytest.mark.parametrize("result, expected", [("w", "w"), ("ARM_STOP", "arm_stop"), ("move forward", "r")])
def test_voice_output_is_allowlisted(monkeypatch, result, expected):
    monkeypatch.setattr(qwen_api, "_complete", lambda content: result)
    assert qwen_api.voice2plan("test") == expected


def test_unknown_detection_output_is_not_reported_as_safe(monkeypatch):
    monkeypatch.setattr(qwen_api, "infer", lambda *args: "possibly")
    with pytest.raises(qwen_api.AIServiceError):
        qwen_api.detect_fire("image")


def test_missing_credentials_fail_before_network(settings):
    settings.OPENROUTER_API_KEY = ""
    with pytest.raises(qwen_api.AIServiceError, match="not configured"):
        qwen_api.get_client()
