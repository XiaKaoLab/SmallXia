"""按抓取进展加分、按时间/动作/掉球/越界扣分，静止接触不持续加分。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class PickupRewardConfig:
    version: str = 'pickup_v3_visual'
    found_ball: float = 1.0
    empty_close_cost: float = .2
    approach_gain: float = 5.0
    first_grasp: float = 1.0
    lift_gain: float = 10.0
    success: float = 50.0
    time_cost: float = .01
    action_cost: float = .002
    drop_cost: float = 3.0
    failure_cost: float = 10.0
    timeout_cost: float = 2.0
    floor_force_cost: float = .05


class PickupReward:
    def __init__(self, distance):
        self.config = PickupRewardConfig()
        self.previous_distance = distance
        self.previous_lift = 0.0
        self.grasp_rewarded = False
        self.was_lifted = False
        self.ball_found_rewarded = False

    def calculate(self, *, distance, lift_fraction, grasped, success, failed, truncated, action, floor_force, ball_contact=False):
        settings = self.config
        lift = lift_fraction if grasped else 0.0
        dropped = self.was_lifted and (not grasped or lift_fraction < .1)
        terms = {
            'empty_close': -settings.empty_close_cost * min(1., max(0., -float(action[5])))
                if float(action[5]) < -.02 and not ball_contact else 0.0,
            'approach': settings.approach_gain * (self.previous_distance - distance),
            'first_grasp': settings.first_grasp if grasped and not self.grasp_rewarded else 0.0,
            'lift_progress': settings.lift_gain * (lift - self.previous_lift),
            'success': settings.success if success else 0.0,
            'time': -settings.time_cost,
            'action': -settings.action_cost * float(np.mean(np.square(action))),
            'drop': -settings.drop_cost if dropped else 0.0,
            'failure': -settings.failure_cost if failed else 0.0,
            'timeout': -settings.timeout_cost if truncated else 0.0,
            'floor_collision': -settings.floor_force_cost * min(floor_force, 20.0),
        }
        self.previous_distance, self.previous_lift = distance, lift
        self.grasp_rewarded |= grasped
        self.was_lifted = grasped and lift_fraction >= .1
        return float(sum(terms.values())), terms

    def observe_ball(self, visible):
        reward = self.config.found_ball if visible and not self.ball_found_rewarded else 0.0
        self.ball_found_rewarded |= visible
        return reward

    def description(self):
        return asdict(self.config)
