"""功能：失能后持续只读关节反馈，再次控制前释放串口；不使能、不发送运动。
Created on 2026-11-05; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""
from threading import Event


class PassiveFeedback:
    def __init__(self):
        self.stop = Event()

    def run(self, arm, publish):
        while not self.stop.is_set():
            try:
                arm.connect()
                while not self.stop.is_set():
                    observation = arm.read_observation()
                    publish(observation.joint_positions, None)
                    self.stop.wait(.05)
            except Exception as error:
                publish(None, str(error))
            finally:
                # 未调用 arm.arm()，disconnect 仅关闭只读总线，不改写力矩。
                try: arm.disconnect()
                except Exception as error: publish(None, str(error))
            self.stop.wait(1)
