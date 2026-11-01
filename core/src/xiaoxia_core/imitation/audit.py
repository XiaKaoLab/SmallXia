"""审计模型编译限位和动作拒绝路径，明确物理标定的未验证状态。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import json
from dataclasses import asdict
from pathlib import Path

from ..contracts import Action
from ..safety import JOINTS, JointLimits
from ..simulation import MujocoSimulation, SimulationConfig


class LimitAudit:
    def run(self, urdf: Path, calibration_paths: tuple[Path, ...] = ()) -> dict:
        limits = JointLimits.from_urdf(urdf)
        rejected = accepted = 0
        with MujocoSimulation(SimulationConfig(urdf)) as simulation:
            compiled = simulation.diagnostics()["joint_ranges"]
            for name, limit in limits.joints.items():
                if any(abs(a - b) > 1e-8 for a, b in zip(compiled[name], (limit.lower, limit.upper), strict=True)):
                    raise RuntimeError(f"MuJoCo 编译后限位与 URDF 不一致: {name}")
                for endpoint in (limit.lower, limit.upper):
                    action = limits.midpoint()
                    action[name] = endpoint
                    simulation.send_action(Action(action))
                    accepted += 1
                for outside in (limit.lower - 0.001, limit.upper + 0.001):
                    action = limits.midpoint()
                    action[name] = outside
                    try:
                        simulation.send_action(Action(action))
                    except ValueError:
                        rejected += 1
                    else:
                        raise RuntimeError(f"越界动作未被拒绝: {name}")
        calibrations = []
        for path in calibration_paths:
            raw = json.loads(path.read_text(encoding="utf-8"))
            valid = set(raw) == set(JOINTS) and all(
                raw[name]["id"] == index and 0 <= raw[name]["range_min"] < raw[name]["range_max"] <= 4095
                for index, name in enumerate(JOINTS, 1)
            )
            calibrations.append({"path": str(path), "six_axis_encoder_range_valid": valid,
                                 "physical_identity_confirmed": False, "urdf_zero_mapping_verified": False})
        return {"model": str(urdf), "urdf_limits": {name: asdict(limit) for name, limit in limits.joints.items()},
                "compiled_ranges_match": True, "accepted_boundary_targets": accepted,
                "rejected_outside_targets": rejected, "physics_steps": 0,
                "calibrations": calibrations, "physical_limits_verified": False,
                "limitations": ["URDF limits are model constraints, not measured hard stops",
                                "URDF effort values are not verified STS3215 torque ratings",
                                "Real leader/follower ports, separate calibration and URDF zero/direction mapping required"]}
