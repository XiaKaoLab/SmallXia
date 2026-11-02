"""批量采集独立小球抓取环境，更新 SAC 策略并发布真实回合分数与进度。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
from time import monotonic

import numpy as np

from .ball_environment import BallPickupEnvironment
from .learning import SACLearner
from .ball_observation import BallObservation
from .ball_demonstration import BallDemonstrator
from .ball_evaluation import BallPolicyEvaluation
from .pickup_curriculum import PickupCurriculum
from ..imitation.api_jobs import atomic_json
from .preview import TrainingPreviewPublisher


class BallPickupTraining:
    def __init__(self, worker):
        self.worker = worker
        self.request = worker.request

    def run(self):
        import torch
        torch.set_num_threads(4)
        count, rounds = self.request['num_envs'], self.request['rounds']
        demo_count = self.request.get('demonstration_episodes', 8)
        pretraining = self.request.get('pretraining_updates', 200)
        stop_on_success = self.request.get('stop_on_success', False)
        atomic_json(self.worker.directory / 'policy_config.json', {'task': 'ball_pickup', 'cameras': ['wrist'],
            'environment_version': BallPickupEnvironment.version,
            **BallObservation.config, 'state_order': 'joint_positions_6,joint_velocities_6,ball_xyz_3,ball_minus_tip_xyz_3,phase_onehot_7,jaw_forces_2,hold_fraction_1,orientation_error_3',
            'action_space': 'normalized_joint_delta', 'action_scale': .08, 'num_envs': count, 'rounds': rounds,
            'observation_noise': BallObservation.noise, 'demonstration_episodes': demo_count, 'pretraining_updates': pretraining,
            'online_update_budget': 10000, 'critic_warmup_updates': 1000, 'bc_weight': 10., 'actor_update_interval': 2,
            'privileged_state': True, 'seed': self.request['seed'], 'physical': False})
        self.worker.progress(phase='initializing', task='拿取小球', num_envs=count, rounds=rounds,
                             environment_version=BallPickupEnvironment.version,
                             completed_episodes=0, total_episodes=count * rounds, progress=0, score=None,
                             score_source='episode_return', successes=0, physical=False)
        seed = self.request['seed']
        torch.manual_seed(seed)
        rng = random.Random(seed)
        urdf = Path(__file__).resolve().parents[4] / 'table/public/robots/so101/so101_new_calib.urdf'
        environments = BallPickupEnvironment.vector(urdf, count, seed)
        observers = []
        try:
            for i, env in enumerate(environments):
                observers.append(BallObservation(env, seed + 100000 + i))
            learner = SACLearner(BallObservation.config, self.request['device'])
            if self.request.get('warm_start_checkpoint'):
                learner.policy.load_state_dict(torch.load(self.request['warm_start_checkpoint'], map_location=self.request['device'], weights_only=True))
            preview = TrainingPreviewPublisher(self.worker.directory, kind='ball_pickup')
            self.worker.progress(reward_config=environments[0].reward.description())
            preview.publish(environments, force=True)
            replay = deque(maxlen=10000)
            hard_replay = deque(maxlen=2000)
            curriculum = PickupCurriculum()
            best_state, best_metric, regressions = None, (-1, -1, float('-inf')), 0
            demos = []
            self.worker.progress(phase='demonstrating', demonstration_successes=0)
            teacher = BallDemonstrator()
            demo_successes = 0
            if self.request.get('demonstration_directory'):
                archive = np.load(Path(self.request['demonstration_directory']) / 'demonstrations.npz', allow_pickle=False)
                try:
                    arrays = {key: archive[key] for key in archive.files}
                    demos = [({'observation.state': arrays['state'][i], BallObservation.camera_key: arrays['wrist'][i]},
                        arrays['action'][i], float(arrays['reward'][i]),
                        {'observation.state': arrays['next_state'][i], BallObservation.camera_key: arrays['next_wrist'][i]},
                        bool(arrays['done'][i])) for i in range(len(arrays['action']))]
                    if sum(row[4] for row in demos) < demo_count:
                        raise ValueError('归档的成功示教数量不足')
                    self.worker.progress(demonstration_successes=demo_count, demonstration_transitions=len(demos),
                        demonstration_reused=True)
                finally:
                    archive.close()
            else:
                for attempt in range(demo_count * 3):
                    env, observer = environments[0], observers[0]
                    env.reset_episode()
                    try:
                        trajectory = teacher.collect(env, observer)
                    except ValueError:
                        continue
                    if not trajectory:
                        continue
                    demo_successes += 1
                    demos.extend(trajectory)
                    preview.publish(environments, force=True)
                    self.worker.progress(demonstration_successes=demo_successes, demonstration_transitions=len(demos))
                    if demo_successes == demo_count:
                        break
                if demo_successes < demo_count:
                    raise ValueError(f'{demo_count * 3} 次尝试未取得 {demo_count} 轮成功示教')
            np.savez_compressed(self.worker.directory / 'demonstrations.npz',
                state=np.stack([r[0]['observation.state'] for r in demos]),
                wrist=np.stack([r[0][BallObservation.camera_key] for r in demos]),
                action=np.stack([r[1] for r in demos]), reward=np.asarray([r[2] for r in demos]),
                next_state=np.stack([r[3]['observation.state'] for r in demos]),
                next_wrist=np.stack([r[3][BallObservation.camera_key] for r in demos]),
                done=np.asarray([r[4] for r in demos]))
            self.worker.progress(phase='pretraining')
            evaluator = BallPolicyEvaluation(urdf, self.request['device'])
            evaluation_history = self.worker.directory / 'evaluations'
            evaluation_history.mkdir(exist_ok=True)
            evaluation = None
            validated = False
            plateau = False
            zero_success_evaluations = 0
            correction_labels = []
            pretraining_completed = 0
            if self.request.get('warm_start_checkpoint'):
                evaluation = evaluator.run(learner.policy, preview=preview, level=curriculum.level)
                atomic_json(evaluation_history / 'warm-start.json', evaluation)
                best_metric = (curriculum.level, evaluation['successes'], evaluation['score'])
                best_state = {key: value.detach().cpu().clone() for key, value in learner.policy.state_dict().items()}
                self.worker.progress(warm_start_successes=evaluation['successes'], evaluation_rounds=20)
            for step in range(pretraining):
                pretraining_completed = step + 1
                selected = PickupCurriculum.sample(demos, 64, rng)
                labels = [(r[0], r[1]) for r in selected]
                if correction_labels:
                    labels = labels[:32] + rng.sample(correction_labels, min(32, len(correction_labels)))
                bc_loss = learner.behavior_clone(BallObservation.batch([r[0] for r in labels], self.request['device']),
                    torch.as_tensor(np.stack([r[1] for r in labels]), device=self.request['device']))
                if (step + 1) % 100 == 0:
                    self.worker.progress(phase='pretraining', pretraining_step=step + 1,
                        pretraining_updates=pretraining, loss_bc=bc_loss)
                if (step + 1) % 1000 == 0:
                    learner.publish(self.worker.directory, step + 1)
                if stop_on_success and ((step + 1) % 1000 == 0 or step + 1 == pretraining):
                    self.worker.progress(phase='evaluating', pretraining_step=step + 1)
                    evaluation = evaluator.run(learner.policy, preview=preview, level=curriculum.level)
                    atomic_json(evaluation_history / f'pretrain-{step + 1:08d}.json', evaluation)
                    atomic_json(self.worker.directory / 'evaluation.json', evaluation)
                    self.worker.progress(evaluation_successes=evaluation['successes'], evaluation_rounds=20)
                    metric = (curriculum.level, evaluation['successes'], evaluation['score'])
                    if metric > best_metric:
                        best_metric = metric
                        best_state = {key: value.detach().cpu().clone() for key, value in learner.policy.state_dict().items()}
                        torch.save(best_state, self.worker.directory / 'best-policy.pt')

                    # 示教预训练只提供初始化；不能跳过在线 SAC 和最终全工作区验收。
                    if (self.request.get('corrective_demonstrations', False)
                            and evaluation['successes'] < evaluation['rounds']):
                        self.worker.progress(phase='correcting')
                        failed_positions = [row['snapshot']['spawn_position'][:2]
                            for row in evaluation['episodes'] if not row['success']]
                        for _ in range(8):
                            environments[0].reset_episode(position=rng.choice(failed_positions) if failed_positions else None)
                            try:
                                correction_labels.extend(teacher.corrections(environments[0], observers[0],
                                    learner.policy, self.request['device'], preview))
                            except ValueError:
                                continue
                        correction_labels = correction_labels[-10000:]
                        self.worker.progress(correction_labels=len(correction_labels))
            if best_state is not None:
                learner.policy.load_state_dict(best_state)
                for optimizer in learner.optimizers.values():
                    optimizer.state.clear()
            # 不把预训练期间失败混合执行的旧标签带入恢复后的最佳策略。
            correction_labels = []
            self.worker.progress(phase='warming_critic', critic_warmup_updates=0)
            for warmup in range(1000):
                selected = PickupCurriculum.sample(demos, 64, rng)
                tensor = lambda values: torch.as_tensor(np.asarray(values), dtype=torch.float32, device=self.request['device'])
                learner.update({'state': BallObservation.batch([row[0] for row in selected], self.request['device']),
                    'action': tensor([row[1] for row in selected]), 'reward': tensor([row[2] for row in selected]),
                    'next_state': BallObservation.batch([row[3] for row in selected], self.request['device']),
                    'done': tensor([row[4] for row in selected])}, update_actor=False)
                if (warmup + 1) % 100 == 0:
                    self.worker.progress(critic_warmup_updates=warmup + 1)
            if best_state is not None:
                # 保留刚完成预热的Critic，避免回滚至预训练时期的随机Q网络。
                best_state = {key: value.detach().cpu().clone() for key, value in learner.policy.state_dict().items()}
                torch.save(best_state, self.worker.directory / 'best-policy.pt')
            curriculum.configure(environments)
            for env in environments:
                env.reset_episode()
            scores = deque(maxlen=100)
            completed = [0] * count
            states = [observer.read() for observer in observers]
            successes = updates = transitions = 0
            last_publish = 0
            metrics = {}
            self.worker.progress(phase='collecting', snapshot=environments[0].snapshot())
            with ThreadPoolExecutor(max_workers=min(count, 8)) as pool:
                while min(completed) < rounds and not validated and not plateau and updates < 10000:
                    active = [index for index in range(count) if completed[index] < rounds]
                    observations = BallObservation.batch([states[index] for index in active], self.request['device'])
                    learner.policy.eval()
                    with torch.inference_mode():
                        distribution = learner.policy.actor(observations)
                        actions = distribution[0].detach().cpu().numpy()
                    futures = [pool.submit(environments[index].advance, actions[offset]) for offset, index in enumerate(active)]
                    for offset, index in enumerate(active):
                        state, reward, terminated, truncated, success = futures[offset].result()
                        state = observers[index].read()
                        reward += environments[index].last_visual_reward
                        row = (states[index], actions[offset], reward, state, terminated)
                        replay.append(row)
                        if any(environments[index].last_reward_terms.get(key, 0) < 0
                               for key in ('drop', 'empty_close', 'premature_close', 'timeout', 'floor_collision', 'alignment_stall')):
                            hard_replay.append(row)
                        transitions += 1
                        states[index] = state
                        if terminated or truncated:
                            scores.append(environments[index].return_)
                            completed[index] += 1
                            successes += int(success)
                            if completed[index] < rounds:
                                environments[index].reset_episode()
                                states[index] = observers[index].read()
                    if len(replay) >= 64:
                        selected = (PickupCurriculum.sample(replay, 16, rng) + PickupCurriculum.sample(demos, 32, rng)
                                    + PickupCurriculum.sample(hard_replay or replay, 16, rng))
                        tensor = lambda values: torch.as_tensor(np.asarray(values), dtype=torch.float32, device=self.request['device'])
                        anchor = PickupCurriculum.sample(demos, 32, rng)
                        labels = [(r[0], r[1]) for r in anchor]
                        if correction_labels:
                            labels += rng.sample(correction_labels, min(32, len(correction_labels)))
                        metrics = learner.update({'state': BallObservation.batch([row[0] for row in selected], self.request['device']),
                            'action': tensor([row[1] for row in selected]), 'reward': tensor([row[2] for row in selected]),
                            'next_state': BallObservation.batch([row[3] for row in selected], self.request['device']),
                            'done': tensor([row[4] for row in selected])},
                            demonstration_batch={'state': BallObservation.batch([r[0] for r in labels], self.request['device']),
                                                 'action': tensor([r[1] for r in labels])}, bc_weight=10., update_actor=updates % 2 == 0)
                        updates += 1
                        if stop_on_success and updates % 500 == 0:
                            self.worker.progress(phase='evaluating', curriculum_level=curriculum.level)
                            evaluation = evaluator.run(learner.policy, preview=preview, level=curriculum.level,
                                seed=20270000 + updates, noisy=curriculum.level == 2)
                            atomic_json(evaluation_history / f'online-{updates:08d}.json', evaluation)
                            atomic_json(self.worker.directory / 'evaluation.json', evaluation)
                            self.worker.progress(evaluation_successes=evaluation['successes'], evaluation_rounds=20)
                            zero_success_evaluations = zero_success_evaluations + 1 if evaluation['successes'] == 0 else 0
                            plateau = zero_success_evaluations >= 6
                            if plateau:
                                self.worker.progress(training_plateau=True, stop_reason='six_zero_success_validations')
                            metric = (curriculum.level, evaluation['successes'], evaluation['score'])
                            if metric > best_metric:
                                best_metric, regressions = metric, 0
                                best_state = {key: value.detach().cpu().clone() for key, value in learner.policy.state_dict().items()}
                                torch.save(best_state, self.worker.directory / 'best-policy.pt')
                            else:
                                regressions += 1
                            if curriculum.promote(evaluation):
                                curriculum.configure(environments)
                                self.worker.progress(curriculum_level=curriculum.level)
                            elif (curriculum.level == 2 and evaluation['successes'] == 20
                                  and updates >= self.request.get('minimum_online_updates', 2000)):
                                validated = True
                            elif regressions >= 3 and best_state is not None:
                                learner.policy.load_state_dict(best_state)
                                for optimizer in learner.optimizers.values():
                                    optimizer.state.clear()
                                regressions = 0
                                self.worker.progress(restored_best_policy=True)
                            if not validated and not plateau and self.request.get('corrective_demonstrations', False):
                                self.worker.progress(phase='correcting')
                                failed_positions = [row['snapshot']['spawn_position'][:2]
                                    for row in evaluation['episodes'] if not row['success']]
                                for _ in range(4):
                                    environments[0].reset_episode(position=rng.choice(failed_positions) if failed_positions else None)
                                    try:
                                        correction_labels.extend(teacher.corrections(environments[0], observers[0],
                                            learner.policy, self.request['device'], preview))
                                    except ValueError:
                                        continue
                                correction_labels = correction_labels[-10000:]
                                # 纠正采集改变了环境，清空当前观察并重置，不拼接不连续转换。
                                environments[0].reset_episode()
                                states[0] = observers[0].read()
                                self.worker.progress(correction_labels=len(correction_labels))
                        if updates % 200 == 0:
                            learner.publish(self.worker.directory, pretraining_completed + updates)
                    preview.set_camera_frame(states[0][BallObservation.camera_key], float(environments[0]._data.time))
                    preview.publish(environments)
                    if monotonic() - last_publish >= .5 or min(completed) >= rounds:
                        done = sum(completed)
                        self.worker.progress(phase='learning' if updates else 'collecting', completed_episodes=done,
                            progress=done / (count * rounds), score=float(np.mean(scores)) if scores else None,
                            current_score=float(environments[0].return_), successes=successes, success_rate=successes / done if done else 0,
                            reward_terms=environments[0].last_reward_terms,
                            env_rounds=completed, transitions=transitions, updates=updates,
                            snapshot=environments[0].snapshot(), **metrics)
                        last_publish = monotonic()
            if not validated and best_state is not None:
                learner.policy.load_state_dict(best_state)
            checkpoint = learner.publish(self.worker.directory, pretraining_completed + updates)
            preview.publish(environments, force=True)
            self.worker.progress(phase='exporting')
            from .onnx_export import BallOnnxExporter
            exported = BallOnnxExporter().export(Path(checkpoint), self.worker.directory, policy=learner.policy, config=BallObservation.config, environment_version=BallPickupEnvironment.version)
            return {'checkpoint': checkpoint, **exported, 'completed_episodes': sum(completed), 'successes': successes,
                    'score': float(np.mean(scores)) if scores else None, 'updates': updates, 'physical': False,
                    'online_budget_exhausted': updates >= 10000, 'training_plateau': plateau, 'curriculum_level': curriculum.level, 'minimum_online_updates': self.request.get('minimum_online_updates', 2000),
                    'evaluation': evaluation, 'task_success_validated': False, 'training_candidate_qualified': validated, 'stopped_on_success': validated}
        finally:
            for observer in observers:
                observer.close()
            for env in environments:
                env.disconnect()
