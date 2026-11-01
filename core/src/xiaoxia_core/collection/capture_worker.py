"""隔离持有仿真或只读实机连接，消费采集命令并生成 LeRobot v3 数据集。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import sys
from pathlib import Path
from threading import Thread
from time import monotonic, sleep, time_ns

from ..contracts import Action
from ..imitation.api_worker import ImitationWorker
from ..imitation.dataset import DemonstrationWriter
from ..imitation.api_jobs import atomic_json
from .capture_queue import CaptureQueue
from .capture_sources import SimulationCaptureSource, HardwareCaptureSource


class CaptureWorker(ImitationWorker):
    def run(self):
        Thread(target=self.watch_parent, daemon=True).start()
        self.progress(status='running', phase='connecting')
        queue = CaptureQueue(Path(self.request['session_directory']))
        config = queue.config
        core = Path(__file__).resolve().parents[3]
        source = (SimulationCaptureSource if config['source'] == 'simulation' else HardwareCaptureSource)(config, core)
        writer = None
        source_closed = False
        total = episodes = 0
        last_frame = 0.0
        last_command = monotonic()
        images = self.directory / 'raw_images'
        images.mkdir()
        try:
            source.connect()
            queue.set(phase='ready', frames=0, episodes=0, episode_frames=0)
            self.progress(phase='ready')
            while True:
                command = queue.next()
                if not command:
                    if monotonic() - last_command > config['idle_timeout_s']:
                        raise TimeoutError('采集空闲超时；未完成的数据集不标记为可用')
                    sleep(0.05)
                    continue
                key, kind, body = command
                last_command = monotonic()
                try:
                    if kind == 'capture':
                        sleep(max(0, 1 / config['fps'] - (monotonic() - last_frame)))
                        observation = source.observation(images, total)
                        action = Action(body['action']) if config['record_actions'] else None
                        if writer is None:
                            writer = DemonstrationWriter(self.directory / 'dataset', f"local/{config['id']}", config['fps'],
                                source.transport.limits, observation, simulated=config['source'] == 'simulation',
                                robot_type='so100_mujoco' if config['source'] == 'simulation' else f'{source.workflow.config["robot"]}_follower',
                                use_videos=config['use_videos'], record_actions=config['record_actions'])
                            writer.metadata.update(state_source='mujoco_physics' if config['source'] == 'simulation' else 'calibrated_encoder_feedback',
                                action_semantics=('simulation_position_target' if config['source'] == 'simulation' else 'external_target_label_not_executed')
                                                 if config['record_actions'] else 'observation_only',
                                camera_joint_synchronized=config['source'] == 'simulation', physical=config['source'] == 'hardware')
                            atomic_json(self.directory / 'dataset/imitation.json', writer.metadata)
                        source.advance(action)
                        writer.append(observation, action, config['task'])
                        with (self.directory / 'acquisition.jsonl').open('a', encoding='utf-8') as stream:
                            stream.write(json.dumps({'frame': total, 'source_timestamp_ns': observation.timestamp_ns,
                                'received_at_ns': time_ns(), 'source': config['source'],
                                'camera_metadata': getattr(source, 'camera_metadata', {}), 'action_executed': config['source'] == 'simulation' and action is not None}) + '\n')
                        total += 1
                        last_frame = monotonic()
                        result = {'frames': total, 'episode_frames': writer.frames}
                    elif kind in ('save_episode', 'finish'):
                        if writer is None:
                            raise ValueError('尚未采集数据')
                        if writer.frames == 1:
                            raise ValueError('一个回合至少两帧，请继续采集')
                        if writer.frames:
                            writer.save_episode()
                            episodes += 1
                        if kind == 'finish':
                            writer.close()
                            writer = None
                            info = json.loads((self.directory / 'dataset/meta/info.json').read_text(encoding='utf-8'))
                            if not info['codebase_version'].startswith('v3.'):
                                raise RuntimeError('导出数据集不是 LeRobot v3')
                            result = {'dataset': str(self.directory / 'dataset'), 'frames': total, 'episodes': episodes,
                                      'format': info['codebase_version'], 'physical': config['source'] == 'hardware'}
                            source.close()
                            source_closed = True
                            queue.complete(key, 'succeeded', result)
                            queue.set(phase='completed', frames=total, episodes=episodes, episode_frames=0)
                            self.progress(status='succeeded', phase='completed', frames=total, episodes=episodes, result=result, finished_at_ns=time_ns())
                            return
                        result = {'frames': total, 'episodes': episodes}
                    else:
                        raise ValueError('未知采集命令')
                    queue.complete(key, 'succeeded', result)
                    queue.set(frames=total, episodes=episodes, episode_frames=writer.frames)
                    self.progress(phase='ready', frames=total, episodes=episodes)
                except ValueError as error:
                    queue.complete(key, 'failed', {'error': str(error)})
                    if kind == 'finish':
                        queue.set(finish_requested=False)
                    if kind == 'capture':
                        raise
                except Exception as error:
                    queue.complete(key, 'failed', {'error': str(error)})
                    raise
        except Exception as error:
            queue.set(phase='failed', error=str(error))
            self.progress(status='failed', error=f'{type(error).__name__}: {error}', finished_at_ns=time_ns())
            raise
        finally:
            try:
                if not source_closed:
                    source.close()
            finally:
                if writer:
                    writer.close()


if __name__ == '__main__':
    CaptureWorker(Path(sys.argv[1])).run()
