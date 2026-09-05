import json
from unittest.mock import Mock

import pytest
from roslibpy import ServiceResponse
from roslibpy.core import RosTimeoutError

from se.api import navigation
from se.models.File import File
from se.models.Log import Log
from se.models.Map import Map
from se.models.Point import Point
from se.util_ros import check_connect


@pytest.mark.parametrize("body", [b"[]", b"1", b"null", b"broken", b"\xff", b'"text"'])
def test_invalid_json_is_a_client_error(client, body):
    assert client.post("/api/auth/login", body, content_type="application/json").status_code == 400


def test_deleted_user_token_is_rejected(authenticated, user):
    user.delete()
    assert authenticated.get("/api/auth/detail").status_code == 401


def test_empty_latest_log_and_log_without_image(authenticated):
    assert authenticated.get("/api/log/latest").json() == {"log": None}
    Log.objects.create(detail="no image")
    assert authenticated.get("/api/log/latest").json()["log"]["url"] is None


def test_log_pagination_uses_constant_queries(authenticated, django_assert_num_queries):
    image = File.objects.create(filename="image.jpg", oss_token="image")
    Log.objects.bulk_create([Log(detail=str(index), file=image) for index in range(12)])
    with django_assert_num_queries(3):
        response = authenticated.get("/api/log/list", {"page": 2, "page_size": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 12 and len(data["logs"]) == 5
    assert [log["detail"] for log in data["logs"]] == ["6", "5", "4", "3", "2"]


def test_disconnected_robot_never_reports_success(robot, user):
    robot.client.is_connected = False
    assert [check_connect(user) for _ in range(5)] == [False] * 5
    assert robot.failed_count == 5
    robot.client.is_connected = True
    assert check_connect(user) is True
    assert robot.failed_count == 0


def test_service_timeout_becomes_502(authenticated, robot):
    robot.main_ctrl_service.call.side_effect = RosTimeoutError("timed out")
    response = authenticated.post("/api/user_ctrl/keyboard", {"direction": "w", "speed": 0.1}, content_type="application/json")
    assert response.status_code == 502


def test_disconnect_does_not_stop_reactor(authenticated, robot):
    connection = robot.client
    assert authenticated.get("/api/ros/free").status_code == 200
    connection.close.assert_called_once()
    connection.terminate.assert_not_called()
    assert robot.current_pose_service is None


@pytest.mark.parametrize("speed", ["fast", True, [], float("nan"), float("inf"), -0.1, 0.4])
def test_invalid_speed_never_reaches_robot(authenticated, robot, speed):
    response = authenticated.post("/api/user_ctrl/keyboard", json.dumps({"direction": "w", "speed": speed}), content_type="application/json")
    assert response.status_code == 400
    robot.main_ctrl_service.call.assert_not_called()


def create_map(name="map"):
    image = File.objects.create(filename=name + ".png", oss_token=name)
    return Map.objects.create(name=name, file=image)


def create_point(mmap, name, x=0):
    return Point.objects.create(mmap=mmap, name=name, px=x, py=0, pz=0, ox=0, oy=0, oz=0, ow=1)


def test_duplicate_and_unsafe_map_names(authenticated, robot):
    create_map()
    assert authenticated.post("/api/mapping/save", {"name": "map"}, content_type="application/json").status_code == 404
    for name in ["../outside", "map;touch test", "", "a/b"]:
        assert authenticated.post("/api/mapping/save", {"name": name}, content_type="application/json").status_code == 400
    robot.main_ctrl_service.call.assert_not_called()


def test_mark_requires_existing_map_and_finite_coordinates(authenticated):
    assert authenticated.post("/api/navigation/mark/1", {}, content_type="application/json").status_code == 400
    payload = {"name": "point", "x": 0, "y": 0, "theta": 0}
    assert authenticated.post("/api/navigation/mark/999", payload, content_type="application/json").status_code == 404
    mmap = create_map()
    payload["x"] = "invalid"
    assert authenticated.post(f"/api/navigation/mark/{mmap.id}", payload, content_type="application/json").status_code == 400


def test_rename_is_scoped_to_map_and_allows_noop(authenticated):
    point = create_point(create_map("one"), "first")
    create_point(create_map("two"), "shared")
    for name in ["shared", "shared"]:
        response = authenticated.post("/api/navigation/rename", {"id": point.id, "name": name}, content_type="application/json")
        assert response.status_code == 200


def test_patrol_preserves_order_repeated_points_and_loop(authenticated, robot, django_assert_num_queries):
    mmap = create_map()
    first, second = create_point(mmap, "first", 1), create_point(mmap, "second", 2)
    robot.map_id = mmap.id
    with django_assert_num_queries(2):
        response = authenticated.post("/api/navigation/patrol", {"path": [second.id, first.id, second.id], "loop": 0}, content_type="application/json")
    assert response.status_code == 200
    command = robot.main_ctrl_service.call.call_args.args[0]["navigation_ctrl_msg"]
    assert command["name_list"] == ["second", "first", "second"]
    assert command["loop"] == 0


def test_patrol_rejects_points_from_other_map(authenticated, robot):
    robot.map_id = create_map("one").id
    point = create_point(create_map("two"), "elsewhere")
    response = authenticated.post("/api/navigation/patrol", {"path": [point.id]}, content_type="application/json")
    assert response.status_code == 400
    robot.main_ctrl_service.call.assert_not_called()


def test_failed_navigation_start_preserves_selected_map(authenticated, robot):
    mmap = create_map()
    robot.main_ctrl_service.call.return_value = ServiceResponse({"code": 1, "msg": "wrong state"})
    assert authenticated.get(f"/api/navigation/start/{mmap.id}").status_code == 400
    assert robot.map_id == 0


def test_map_listing_joins_files(authenticated, django_assert_num_queries):
    for name in ("one", "two", "three"):
        create_map(name)
    with django_assert_num_queries(2):
        response = authenticated.get("/api/navigation/map_list")
    assert len(response.json()["maps"]) == 3
