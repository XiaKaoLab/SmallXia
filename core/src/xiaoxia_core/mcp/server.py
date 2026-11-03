"""通过标准 MCP stdio 提供 table 模型、RL 与当前 WebView 积木工具。
Created on 2026-11-01; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import json
import os
from pathlib import Path
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP

from ..communication.motion_routes import MotionRouteClient
from ..contracts import Action
from ..safety import JointLimits
from .observation_tools import ObservationTools
from .blocks_tools import BlocksTools
from .rl_tools import RLTools
from .environment_tools import EnvironmentTools


class TableModelTools:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[4]
        self.limits = JointLimits.from_urdf(root / "table/public/robots/so100/so100_mid_calib.urdf")

    def table_get_state(self) -> dict:
        """查询仿真机械臂 table 的六轴目标角度，单位 rad。source=display_target，不是物理真机或渲染到位反馈。"""
        with urlopen("http://127.0.0.1:8766/api/v1/robots/table/state", timeout=1) as response:
            result = json.loads(response.read(65536))
        if result.get("physical") is not False or result.get("source") != "display_target" or result.get("unit") != "rad":
            raise ValueError("目标不是 table 显示模型")
        self.limits.validate(result["joint_positions"])
        return result

    def table_get_limits(self) -> dict:
        """返回 table SO100 模型六轴弧度限位；发送目标前读取，采用模型行程中点零位。"""
        return {name: {"lower": limit.lower, "upper": limit.upper, "unit": "rad"}
                for name, limit in self.limits.joints.items()}

    def table_move_joints(self, shoulder_pan: float, shoulder_lift: float,
                          elbow_flex: float, wrist_flex: float,
                          wrist_roll: float, gripper: float) -> dict:
        """设置 table 模型六轴绝对角度(rad)。仅显示；accepted 不表示渲染到位。不得自动重试失败动作。"""
        positions = dict(shoulder_pan=shoulder_pan, shoulder_lift=shoulder_lift,
                         elbow_flex=elbow_flex, wrist_flex=wrist_flex,
                         wrist_roll=wrist_roll, gripper=gripper)
        self.limits.validate(positions)
        token = os.environ.get("XIAOXIA_MOTION_TOKEN", "")
        with MotionRouteClient("http://127.0.0.1:8766", "table", self.limits, token=token) as client:
            client.send_action(Action(positions))
            return {**client.last_receipt, "physical": False, "render_reached": False}


def main() -> None:
    tools = TableModelTools()
    server = FastMCP("xiaoxia-table-model")
    server.tool()(EnvironmentTools().robot_get_environment)
    server.tool()(ObservationTools().robot_observe)
    server.tool()(ObservationTools().robot_list_cameras)
    for method in (tools.table_get_state, tools.table_get_limits, tools.table_move_joints):
        server.tool()(method)
    for provider, prefix in ((RLTools(), "rl_"), (BlocksTools(), "blocks_")):
        for name in dir(provider):
            if name.startswith(prefix):
                server.tool()(getattr(provider, name))
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
