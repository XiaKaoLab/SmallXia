"""向 Agent 暴露现有 RL 会话、人工反馈、学习器/执行者和任务 API。
Created on 2026-11-02; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from ..reinforcement.client import ReinforcementClient


class RLTools:
    def __init__(self):
        self.client = ReinforcementClient()

    def rl_train_ball(self, num_envs: int = 4, rounds: int = 100, device: str = 'cpu',
                      seed: int = 42, demonstration_episodes: int = 8,
                      pretraining_updates: int = 200, corrective_demonstrations: bool = False,
                      stop_on_success: bool = False, minimum_online_updates: int = 2000,
                      warm_start_job_id: str | None = None,
                      demonstration_job_id: str | None = None) -> dict:
        """仿真抓球：采集成功示教并保存归档，预训练、SAC 在线采集训练和 ONNX 导出。num_envs=环境数(1–16)，rounds=每环境回合数。优化可用 warm_start_job_id 接续权重、demonstration_job_id 复用数据；corrective_demonstrations 配合 stop_on_success 启用阶段评估和纠正标签采集。stop_on_success 是训练达到课程评估门槛后提前结束整个训练，不是抓到球就截断单个回合；成功还需持续夹持抬升。seed 控制随机种子，任务完成不代表成功率达标。"""
        return self.client.train_ball(
            num_envs=num_envs, rounds=rounds, device=device, seed=seed,
            demonstration_episodes=demonstration_episodes, pretraining_updates=pretraining_updates,
            corrective_demonstrations=corrective_demonstrations, stop_on_success=stop_on_success,
            minimum_online_updates=minimum_online_updates, warm_start_job_id=warm_start_job_id,
            demonstration_job_id=demonstration_job_id,
        )

    def rl_capabilities(self) -> dict:
        """读取 RL 后端与执行范围，当前是 table 的关节增量 SAC，非实机。"""
        return self.client.request('capabilities')

    def rl_export_onnx(self, training_job_id: str) -> dict:
        """将已完成的抓球训练权重导出 ONNX，返回后台导出任务；需查询成功后使用。"""
        return self.client.export_onnx(training_job_id)

    def rl_predict_onnx(self, model_job_id: str, states: list[list[float]],
                        images: list[list[list[list[float]]]] | None = None) -> dict:
        """ONNX推理六轴增量，states维度按模型manifest（新版31维）；视觉策略同时需要 images=[batch,3,64,64] RGB，范围[0,1]，不发送运动。"""
        return self.client.predict_onnx(model_job_id, states, images)

    def rl_rollout_onnx(self, model_job_id: str, rounds: int = 1, seed: int = 42,
                        suite: str = 'clean', playback_speed: float = 1.0) -> dict:
        """独立 MuJoCo ONNX 抓球评估，不训练、不操作真机。suite 为 clean/noisy/grid（grid 固定35轮）；seed 应与训练不同。playback_speed=0 批量评估，默认1正常速度。返回任务ID，需查询成功率等实际结果。失败终态如 recover 只说明终止时阶段，不能据此断定唯一失败根因。"""
        return self.client.rollout_onnx(model_job_id, rounds=rounds, seed=seed,
                                        suite=suite, playback_speed=playback_speed)

    def rl_create_session(self, task: str, fps: int = 2, cameras: list[str] | None = None,
                          roi: dict | None = None, max_joint_step_rad: float = 0.02, max_episode_steps: int = 40) -> dict:
        """创建 RL 会话但不运动、不训练。虚拟画面最高2FPS；相机与 ROI 使用已有配置。"""
        return self.client.create_session(task, fps=fps, cameras=cameras or [], roi=roi or {},
            max_joint_step_rad=max_joint_step_rad, max_episode_steps=max_episode_steps)

    def rl_get_session(self, session_id: str) -> dict:
        """查询 RL 会话状态、转换数量、奖励和人工接管比例。"""
        return self.client.session(session_id)

    def rl_list_sessions(self) -> dict:
        """列出本机已有 RL 会话，不启动任何任务。"""
        return self.client.request('sessions')

    def rl_step(self, session_id: str, action: list[float], demonstration: bool = False) -> dict:
        """执行一个 table 模型 RL 步并记录数据；action为六维[-1,1]增量。仅在用户要求运动/采样时调用，不自动重试。"""
        return self.client.step(session_id, action, 'demonstration' if demonstration else 'online')

    def rl_intervene(self, session_id: str, enabled: bool, joint_positions: dict | None = None) -> dict:
        """开启/解除人工接管；开启后无有效目标则保持。目标为六轴rad，有效期1秒。"""
        return self.client.intervene(session_id, enabled, joint_positions)

    def rl_feedback(self, session_id: str, success: bool, transition_id: int, truncated: bool = False) -> dict:
        """根据用户明确给出的成功/失败标注最新转换并结束 episode，不能自行臆测任务成功。"""
        return self.client.feedback(session_id, success, transition_id=transition_id, truncated=truncated)

    def rl_label_reward(self, session_id: str, reward: int) -> dict:
        """依据用户标注保存当前相机画面奖励标签0/1，不结束episode；不要自行编造标签。"""
        return self.client.label(session_id, reward)

    def rl_reset(self, session_id: str) -> dict:
        """停止 actor 后开启新 episode，清除接管，不发送归位动作。"""
        return self.client.reset(session_id)

    def rl_start_learner(self, session_id: str, steps: int = 1000, batch_size: int = 16, device: str = 'cpu',
                         demonstration_session_ids: list[str] | None = None) -> dict:
        """显式启动后台 SAC 训练；返回任务，不代表训练完成或策略有效。只在用户要求训练时调用。"""
        return self.client.learner(session_id, steps=steps, batch_size=batch_size, device=device,
                                   demonstration_session_ids=demonstration_session_ids or [])

    def rl_start_actor(self, session_id: str, learner_job_id: str, steps: int = 40, device: str = 'cpu',
                       reward_job_id: str | None = None, success_threshold: float = 0.7) -> dict:
        """启动会实际移动 table 的后台策略执行者。只在用户明确要求运行策略时调用，非实机。"""
        options = {'steps': steps, 'device': device, 'success_threshold': success_threshold}
        if reward_job_id:
            options['reward_job_id'] = reward_job_id
        return self.client.actor(session_id, learner_job_id, **options)

    def rl_predict(self, session_id: str, learner_job_id: str, device: str = 'cpu') -> dict:
        """后台预测一次归一化动作，不执行；返回任务ID，需继续查询任务结果。"""
        return self.client.predict(session_id, learner_job_id, device)

    def rl_train_reward(self, session_id: str, steps: int = 1000, batch_size: int = 16, device: str = 'cpu') -> dict:
        """使用已有成功/失败标签启动视觉奖励训练。返回后台任务，效果未验收。"""
        return self.client.train_reward(session_id, steps=steps, batch_size=batch_size, device=device)

    def rl_get_job(self, job_id: str) -> dict:
        """查询 RL 任务的进度、loss、权重版本、错误或最终结果。"""
        return self.client.job(job_id)

    def rl_stop_job(self, job_id: str) -> dict:
        """停止指定 RL 后台任务；已提交的模型目标保留。"""
        return self.client.stop_job(job_id)

    def rl_stop_session(self, session_id: str) -> dict:
        """停止 RL 会话与关联后台任务，不是硬件急停。"""
        return self.client.stop_session(session_id)
