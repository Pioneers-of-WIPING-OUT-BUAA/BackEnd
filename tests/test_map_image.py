import cv2
import numpy as np


def test_non_square_map_conversion_and_metadata(robot, tmp_path):
    info = {"height": 2, "width": 3, "origin": {"position": {"x": -1, "y": -2}}, "resolution": 0.05}
    robot.map_service.call.return_value = {"map": {"info": info, "data": [-1, 0, 100, 50, -1, 0]}}
    assert robot.save_map_local("map", tmp_path) == info
    image = cv2.imread(str(tmp_path / "map.png"), cv2.IMREAD_GRAYSCALE)
    np.testing.assert_array_equal(image, [[155, 127, 255], [127, 255, 55]])
    assert robot.map_service.call.call_args.kwargs["timeout"] > 0


def test_pose_service_uses_call_with_timeout(robot):
    robot.current_pose_service.call.return_value = {"pose": {"x": 1}}
    assert robot.get_current_pose() == {"x": 1}
    assert robot.current_pose_service.call.call_args.kwargs["timeout"] > 0
