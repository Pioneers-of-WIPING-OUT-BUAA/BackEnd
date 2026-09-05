import time
from unittest.mock import Mock

import pytest
from roslibpy import ServiceResponse

from se.models.User import User
from se.util_ros import ROSClient


@pytest.fixture
def user(db):
    return User.objects.create(username="review", password="unused")


@pytest.fixture
def authenticated(client, user):
    client.defaults["HTTP_AUTHORIZATION"] = "Bearer " + user.token
    return client


@pytest.fixture
def robot(monkeypatch, user):
    monkeypatch.setattr(ROSClient, "_instance", None)
    monkeypatch.setattr(ROSClient, "_flag", False)
    robot = ROSClient()
    robot.client = Mock(is_connected=True)
    robot.user_id = user.id
    robot.last_op_time = time.time()
    robot.main_ctrl_service = Mock()
    robot.main_ctrl_service.call.return_value = ServiceResponse({"code": 0, "msg": "ok"})
    robot.current_pose_service = Mock()
    robot.map_service = Mock()
    return robot
