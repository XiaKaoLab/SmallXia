"""使用 LeRobot 原生 SAC 计算损失、优化策略与目标网络并发布原子权重快照。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
from ..imitation.api_jobs import atomic_json


def make_policy(config, device):
    from lerobot.configs.types import FeatureType, PolicyFeature
    from lerobot.policies.sac.configuration_sac import SACConfig, ActorNetworkConfig, CriticNetworkConfig, PolicyConfig
    from lerobot.policies.sac.modeling_sac import SACPolicy
    inputs = {'observation.state': PolicyFeature(FeatureType.STATE, (config.get('state_dim', 6),))}
    inputs.update({f'observation.images.{camera}': PolicyFeature(FeatureType.VISUAL, (3, 64, 64))
                   for camera in config['cameras']})
    settings = SACConfig(input_features=inputs, output_features={'action': PolicyFeature(FeatureType.ACTION, (6,))},
        device=device, shared_encoder=config.get('shared_encoder', True), push_to_hub=False, use_torch_compile=False, freeze_vision_encoder=False,
        vision_encoder_name=None, latent_dim=128, image_encoder_hidden_dim=16, temperature_init=0.01,
        actor_network_kwargs=ActorNetworkConfig(hidden_dims=[128, 128]),
        critic_network_kwargs=CriticNetworkConfig(hidden_dims=[128, 128]),
        policy_kwargs=PolicyConfig(std_min=config.get('actor_std_min', -5), std_max=config.get('actor_std_max', 2)))
    return SACPolicy(settings).to(device)


class SACLearner:
    def __init__(self, config, device):
        import torch
        self.policy = make_policy(config, device)
        parameters = self.policy.get_optim_params()
        self.optimizers = {key: torch.optim.Adam([value] if key == 'temperature' else value, lr=3e-4)
                           for key, value in parameters.items()}
        self.device = device
        self.bc_optimizer = None

    def update(self, batch, demonstration_batch=None, bc_weight=.5):
        import torch
        self.policy.train()
        metrics = {}
        for model in ('critic', 'actor', 'temperature'):
            optimizer = self.optimizers[model]
            optimizer.zero_grad(set_to_none=True)
            loss = self.policy(batch, model=model)[f'loss_{model}']
            if model == 'actor' and demonstration_batch is not None:
                actor = self.policy.actor
                features = actor.encoder(demonstration_batch['state'])
                predicted = torch.tanh(actor.mean_layer(actor.network(features)))
                bc_loss = torch.nn.functional.mse_loss(predicted, demonstration_batch['action'])
                loss = loss + bc_weight * bc_loss
                metrics['loss_bc'] = float(bc_loss.detach().cpu())
            if not torch.isfinite(loss):
                raise ValueError('SAC 损失非有限值')
            loss.backward()
            parameters = [parameter for group in optimizer.param_groups for parameter in group['params']]
            torch.nn.utils.clip_grad_norm_(parameters, 40, error_if_nonfinite=True)
            optimizer.step()
            metrics[f'loss_{model}'] = float(loss.detach().cpu())
        self.policy.update_target_networks()
        return metrics

    def behavior_clone(self, observations, actions):
        import torch
        self.policy.train()
        actor = self.policy.actor
        if self.bc_optimizer is None:
            self.bc_optimizer = torch.optim.Adam(actor.parameters(), lr=3e-4) if self.policy.shared_encoder else self.optimizers['actor']
        optimizer = self.bc_optimizer
        optimizer.zero_grad(set_to_none=True)
        features = actor.encoder(observations)
        predicted = torch.tanh(actor.mean_layer(actor.network(features)))
        loss = torch.nn.functional.mse_loss(predicted, actions)
        if not torch.isfinite(loss):
            raise ValueError('示教损失非有限值')
        loss.backward()
        parameters = [p for group in optimizer.param_groups for p in group['params']]
        torch.nn.utils.clip_grad_norm_(parameters, 40, error_if_nonfinite=True)
        optimizer.step()
        self.policy.update_target_networks()
        return float(loss.detach().cpu())

    def publish(self, directory, step):
        import torch
        name = f'policy-{step:08d}.pt'
        path = directory / name
        temporary = path.with_suffix('.tmp')
        torch.save({key: value.detach().cpu() for key, value in self.policy.state_dict().items()}, temporary)
        temporary.replace(path)
        atomic_json(directory / 'weights.json', {'step': step, 'file': name})
        # 保留当前与前一份，给执行者留出读取窗口。
        old = sorted(directory.glob('policy-*.pt'))
        for candidate in old[:-2]:
            try:
                candidate.unlink()
            except OSError:
                pass
        return str(path)


def reward_network(cameras):
    from torch import nn
    return nn.Sequential(nn.Conv2d(3 * cameras, 16, 5, stride=2), nn.ReLU(),
        nn.Conv2d(16, 32, 3, stride=2), nn.ReLU(), nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(32, 1))
