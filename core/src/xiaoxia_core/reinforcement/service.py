"""提供人机回环强化学习会话、人工反馈、奖励训练与 Actor/Learner 路由。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import re
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from threading import RLock
from time import time_ns
from uuid import uuid4

from ..imitation.api_jobs import ImitationJobs, atomic_json, identifier
from .environment import TableRLEnvironment
from .replay import ReplayStore
from .onnx_api import BallOnnxAPI


class ReinforcementAPI:
    prefix = '/api/v1/reinforcement'

    def __init__(self, root, limits, frames, routes, authorization):
        self.root = root
        (root / 'sessions').mkdir(parents=True, exist_ok=True)
        self.limits = limits
        self.environment = TableRLEnvironment(limits, frames, routes, authorization)
        self.jobs = ImitationJobs(root / 'jobs', worker_module='xiaoxia_core.reinforcement.worker', max_running=3)
        self.onnx = BallOnnxAPI(self.jobs)
        self._lock = RLock()

    def store(self, session_id):
        return ReplayStore(self.root / 'sessions' / identifier(session_id))

    @staticmethod
    def integer(body, name, default, lower, upper):
        value = body.get(name, default)
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f'{name} 必须为 {lower}–{upper} 的整数')
        return value

    def create(self, body):
        cameras = body.get('cameras', [])
        if not isinstance(cameras, list) or len(cameras) > 2 or any(not isinstance(camera, str) or not (camera in ('virtual', 'real') or re.fullmatch('opencv_[0-9a-f]{16}', camera)) for camera in cameras) or len(set(cameras)) != len(cameras):
            raise ValueError('cameras 需要最多两个已发现的相机 ID，且不能重复')
        fps = self.integer(body, 'fps', 2, 1, 2 if 'virtual' in cameras else 30)
        scale = body.get('max_joint_step_rad', 0.02)
        if type(scale) not in (int, float) or not isfinite(scale) or not 0 < scale <= min(0.1, 0.25 / fps):
            raise ValueError('max_joint_step_rad 必须为正数，且不超过 0.1 和 0.25/fps')
        task = body.get('task')
        if not isinstance(task, str) or not task.strip() or len(task) > 500:
            raise ValueError('task 需要 1–500 字描述')
        roi = body.get('roi', {})
        if not isinstance(roi, dict) or any(camera not in cameras for camera in roi):
            raise ValueError('ROI 只能配置会话包含的相机')
        for box in roi.values():
            if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box) or min(box[:2]) < 0 or min(box[2:]) <= 0:
                raise ValueError('ROI 为 [top,left,height,width]，坐标非负、尺寸为正整数')
        session_id = uuid4().hex
        directory = self.root / 'sessions' / session_id
        directory.mkdir()
        config = {'id': session_id, 'task': task, 'fps': fps, 'cameras': cameras, 'roi': roi,
                  'image_size': 64, 'max_joint_step_rad': scale,
                  'max_episode_steps': self.integer(body, 'max_episode_steps', 40, 1, 10000),
                  'action_space': 'normalized_joint_delta', 'backend': 'lerobot_sac',
                  'target': 'table', 'physical': False, 'camera_joint_synchronized': False,
                  'created_at_ns': time_ns(), 'limits': {name: {'lower': limit.lower, 'upper': limit.upper}
                                                       for name, limit in self.limits.joints.items()}}
        atomic_json(directory / 'session.json', config)
        return ReplayStore(directory).summary()

    def related_jobs(self, session_id):
        for path in self.jobs.root.glob('*/request.json'):
            request = json.loads(path.read_text(encoding='utf-8'))
            if request.get('session_id') == session_id:
                yield self.jobs.get(path.parent.name)

    def launch(self, role, body):
        with self._lock:
            session_id = identifier(body.get('session_id'))
            store = self.store(session_id)
            if any(job['kind'] == role and job['status'] in ('queued', 'running') for job in self.related_jobs(session_id)):
                raise ValueError('同一会话的该角色任务已在运行')
            device = body.get('device', 'cpu')
            if device not in ('cpu', 'cuda'):
                raise ValueError('device 需要 cpu 或 cuda')
            payload = {'session_id': session_id, 'session_directory': str(store.directory), 'device': device,
                       'steps': self.integer(body, 'steps', 1000 if role != 'actor' else 40, 1, 100000),
                       'batch_size': self.integer(body, 'batch_size', 16, 2, 128)}
            if role == 'reward':
                labels = store.labels()
                if not store.config['cameras'] or {label['reward'] for label in labels} != {0, 1}:
                    raise ValueError('奖励分类器需要相机以及成功/失败两类图像标签')
                payload['labels_snapshot'] = labels
            if role == 'learner':
                payload['idle_timeout_s'] = self.integer(body, 'idle_timeout_s', 300, 5, 3600)
                payload['checkpoint_interval'] = self.integer(body, 'checkpoint_interval', 50, 1, 10000)
                ids = body.get('demonstration_session_ids', [])
                if not isinstance(ids, list) or len(ids) > 4:
                    raise ValueError('demonstration_session_ids 最多四个会话')
                payload['demonstration_directories'] = []
                for value in ids:
                    demonstration = self.store(value)
                    for key in ('cameras', 'roi', 'max_joint_step_rad'):
                        if demonstration.config[key] != store.config[key]:
                            raise ValueError('离线示教的相机、ROI 和动作尺度必须与当前会话一致')
                    payload['demonstration_directories'].append(str(demonstration.directory))
            if role in ('actor', 'predict'):
                if role == 'actor' and store.control()['status'] != 'ready':
                    raise ValueError('请先 reset 会话')
                if role == 'actor' and any(job['kind'] == 'actor' and job['status'] in ('queued', 'running') for job in self.jobs.list()):
                    raise ValueError('table 同时只能运行一个执行者')
                learner_id = identifier(body.get('learner_job_id'))
                learner = self.jobs.get(learner_id)
                request = json.loads((self.jobs.root / learner_id / 'request.json').read_text(encoding='utf-8'))
                if learner['kind'] != 'learner' or learner['status'] not in ('queued', 'running', 'succeeded') or request['session_id'] != session_id:
                    raise ValueError('需要同一会话可用的 learner_job_id')
                payload['learner_directory'] = str(self.jobs.root / learner_id)
                threshold = body.get('success_threshold', 0.7)
                if type(threshold) not in (int, float) or not isfinite(threshold) or not 0 < threshold < 1:
                    raise ValueError('success_threshold 必须介于 0 和 1 之间')
                payload['success_threshold'] = threshold
                reward_id = body.get('reward_job_id')
                if reward_id:
                    reward = self.jobs.get(identifier(reward_id))
                    reward_request = json.loads((self.jobs.root / reward_id / 'request.json').read_text(encoding='utf-8'))
                    if reward['kind'] != 'reward' or reward['status'] != 'succeeded' or reward_request['session_id'] != session_id:
                        raise ValueError('需要同一会话成功完成的奖励分类器任务')
                    payload['reward_directory'] = str(self.jobs.root / reward_id)
            return self.jobs.start(role, payload)

    def handle(self, method, path, body=None):
        body = body or {}
        parts = path.removeprefix(self.prefix).strip('/').split('/')
        try:
            if method == 'GET':
                if parts == ['capabilities']:
                    return 200, {'backend': 'lerobot_sac', 'lerobot_version': version('lerobot'), 'target': 'table',
                        'physical': False, 'action_space': 'normalized_joint_delta', 'transport': 'HTTP+SQLite',
                        'reward_classifier': 'local_cnn', 'official_grpc_pipeline': False,
                        'ball_pickup': {'backend': 'mujoco+lerobot_sac', 'num_envs': [1, 16],
                            'rounds_per_env': [1, 10000], 'success_lift_m': 0.05, 'success_hold_s': 1,
                            'score': 'mean_episode_return_last_100', 'physical': False,
                            'environment_version': 'so101_pickup_v5_phase_sac', 'reward_version': 'pickup_v4_phase',
                            'cameras': ['wrist'], 'rgb_shape': [3, 64, 64], 'privileged_state': True,
                            'initial_demonstrations': 8, 'behavior_clone_updates': 200,
                            'observation_noise': True, 'state_dim': 31, 'strategy': 'phase_conditioned_sac',
                            'curriculum_levels': 3, 'acceptance': '100_clean_100_noisy_35_grid_all_success',
                            'success_requires': 'both_jaw_forces_over_0.01N_no_floor_contact_continuous_lift',
                            'onnx': {'automatic_export': True, 'state_dim': 31, 'action_dim': 6,
                                     'deterministic': True, 'runtime': 'onnxruntime'}}}
                if parts == ['sessions']:
                    return 200, {'sessions': [self.store(p.parent.name).summary() for p in (self.root / 'sessions').glob('*/session.json')]}
                if parts == ['jobs']:
                    return 200, {'jobs': self.jobs.list()}
                if len(parts) == 2 and parts[0] == 'sessions':
                    return 200, self.store(parts[1]).summary()
                if len(parts) == 2 and parts[0] == 'jobs':
                    return 200, self.jobs.get(parts[1])
                if len(parts) == 3 and parts[0] == 'sessions' and parts[2] == 'observation':
                    return 200, self.environment.observation(self.store(parts[1]))
                if len(parts) == 3 and parts[0] == 'sessions' and parts[2] == 'transitions':
                    return 200, {'transitions': self.store(parts[1]).rows(limit=100)}
            if method != 'POST':
                return 404, {'error': 'route_not_found'}
            if parts in (['onnx-exports'], ['onnx-predictions'], ['onnx-rollouts']):
                with self._lock:
                    if parts == ['onnx-exports']:
                        return 202, self.onnx.export(body)
                    if parts == ['onnx-predictions']:
                        return 200, self.onnx.predict(body)
                    return 202, self.onnx.rollout(body,
                        self.integer(body, 'rounds', 1, 1, 1000), self.integer(body, 'seed', 42, 0, 2147483647))
            if parts == ['ball-trainings']:
                with self._lock:
                    if any(job['kind'] in ('ball_pickup', 'ball_onnx_rollout') and job['status'] in ('queued', 'running') for job in self.jobs.list()):
                        raise ValueError('已有小球训练在运行，请先停止或等待完成')
                    device = body.get('device', 'cpu')
                    if device not in ('cpu', 'cuda'):
                        raise ValueError('device 需要 cpu 或 cuda')
                    count = self.integer(body, 'num_envs', 4, 1, 16)
                    rounds = self.integer(body, 'rounds', 100, 1, 10000)
                    if type(body.get('corrective_demonstrations', False)) is not bool:
                        raise ValueError('corrective_demonstrations 需要布尔值')
                    if type(body.get('stop_on_success', False)) is not bool:
                        raise ValueError('stop_on_success 需要布尔值')
                    warm = {}
                    if body.get('warm_start_job_id'):
                        source = self.jobs.root / identifier(body['warm_start_job_id'])
                        state = self.jobs.get(source.name)
                        if state['kind'] != 'ball_pickup' or state['status'] not in ('succeeded', 'cancelled', 'failed', 'interrupted'):
                            raise ValueError('接续权重需要已结束且存在完整权重的抓球训练')
                        config = json.loads((source / 'policy_config.json').read_text(encoding='utf-8'))
                        from .ball_environment import BallPickupEnvironment
                        if config.get('environment_version') != BallPickupEnvironment.version:
                            raise ValueError('旧权重使用不同的抓球物理与观测定义，请在新环境重新训练')
                        weights = json.loads((source / 'weights.json').read_text(encoding='utf-8'))
                        checkpoint = source / weights['file']
                        if not checkpoint.resolve().is_relative_to(source.resolve()) or not checkpoint.is_file():
                            raise ValueError('接续训练权重不可用')
                        warm = {'warm_start_checkpoint': str(checkpoint), 'warm_start_job_id': source.name}
                    if body.get('demonstration_job_id'):
                        source = self.jobs.root / identifier(body['demonstration_job_id'])
                        demo_config = json.loads((source / 'policy_config.json').read_text(encoding='utf-8'))
                        from .ball_environment import BallPickupEnvironment
                        if (demo_config.get('environment_version') != BallPickupEnvironment.version
                                or demo_config.get('demonstration_episodes', 0) < body.get('demonstration_episodes', 8)
                                or not (source / 'demonstrations.npz').is_file()):
                            raise ValueError('示教归档不兼容或数量不足')
                        warm['demonstration_directory'] = str(source)
                    return 202, self.jobs.start('ball_pickup', {
                        'task': '拿取小球', 'device': device, **warm,
                        'demonstration_episodes': self.integer(body, 'demonstration_episodes', 8, 8, 256),
                        'pretraining_updates': self.integer(body, 'pretraining_updates', 200, 200, 50000),
                        'stop_on_success': body.get('stop_on_success', False),
                        'corrective_demonstrations': body.get('corrective_demonstrations', False),
                        'minimum_online_updates': self.integer(body, 'minimum_online_updates', 2000, 500, 100000),
                        'num_envs': count, 'rounds': rounds,
                        'seed': self.integer(body, 'seed', 42, 0, 2147483647)},
                        initial_state={'task': '拿取小球', 'num_envs': count, 'rounds': rounds,
                            'completed_episodes': 0, 'total_episodes': count * rounds, 'progress': 0,
                            'score': None, 'successes': 0, 'physical': False})
            if parts == ['sessions']:
                return 201, self.create(body)
            if parts in (['learners'], ['actors'], ['reward-trainings'], ['predictions']):
                role = {'learners': 'learner', 'actors': 'actor', 'reward-trainings': 'reward', 'predictions': 'predict'}[parts[0]]
                return 202, self.launch(role, body)
            if len(parts) == 3 and parts[0] == 'jobs' and parts[2] == 'stop':
                return 200, self.jobs.stop(parts[1])
            if len(parts) == 3 and parts[0] == 'sessions':
                store = self.store(parts[1])
                endpoint = parts[2]
                if endpoint == 'step':
                    return 200, self.environment.step(store, body)
                if endpoint == 'intervention':
                    enabled = body.get('enabled')
                    if type(enabled) is not bool:
                        raise ValueError('enabled 需要布尔值')
                    target = body.get('joint_positions')
                    if target is not None:
                        if not isinstance(target, dict) or any(type(value) not in (int, float) for value in target.values()):
                            raise ValueError('joint_positions 需要六轴弧度目标')
                        self.limits.validate(target)
                    return 200, store.update_control(intervention=enabled, intervention_target=target,
                        intervention_expires_ns=time_ns() + 1000000000)
                if endpoint == 'feedback':
                    success = body.get('success')
                    if type(success) is not bool:
                        raise ValueError('success 需要布尔值')
                    with self.environment._step_lock:
                        current = store.control()
                        transition_id = self.integer(body, 'transition_id', current.get('last_transition_id', 0), 1, 10000000)
                        if transition_id != current.get('last_transition_id'):
                            raise ValueError('在线反馈只能标注当前 episode 的最新转换，避免误结束其他 episode')
                        truncated = body.get('truncated', False)
                        if type(truncated) is not bool:
                            raise ValueError('truncated 需要布尔值')
                        source = body.get('reward_source', 'human')
                        if source not in ('human', 'classifier'):
                            raise ValueError('reward_source 需要 human 或 classifier')
                        store.feedback(transition_id, success, truncated=truncated, reward_source=source)
                        return 200, store.update_control(status='ended')
                if endpoint == 'labels':
                    reward = body.get('reward')
                    if type(reward) is not int or reward not in (0, 1) or not store.config['cameras']:
                        raise ValueError('奖励标签需要相机与 reward=0 或 1')
                    return 201, {'label_id': store.label(self.environment.observation(store), reward)}
                if endpoint == 'reset':
                    with self._lock:
                        if any(job['kind'] == 'actor' and job['status'] in ('queued', 'running') for job in self.related_jobs(parts[1])):
                            raise ValueError('请先停止当前 actor 再 reset')
                        current = store.control()
                        return 200, store.update_control(status='ready', episode=current['episode'] + 1,
                            episode_steps=0, intervention=False, intervention_target=None, last_transition_id=None)
                if endpoint == 'stop':
                    with self.environment._step_lock:
                        store.update_control(status='stopped')
                    for job in self.related_jobs(parts[1]):
                        if job['status'] in ('queued', 'running'):
                            self.jobs.stop(job['id'])
                    return 200, store.summary()
            return 404, {'error': 'route_not_found'}
        except FileNotFoundError:
            return 404, {'error': 'resource_not_found'}
        except (ValueError, TypeError, KeyError) as error:
            return 422, {'error': str(error)}
        except OSError as error:
            return 503, {'error': str(error)}

    def close(self):
        self.jobs.close()
