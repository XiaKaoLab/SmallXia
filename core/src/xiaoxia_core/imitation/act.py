"""用 LeRobot ACT 完成真实参数更新、检查点保存与有界关节策略推理。
Created on 2026-11-01; Updated on 2026-11-05
@author: https://github.com/Linmoqian
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from math import isfinite

from ..contracts import Action, Observation
from ..inference import Policy
from ..safety import JOINTS, JointLimit, JointLimits


@dataclass(frozen=True)
class ACTTrainingConfig:
    dataset: Path
    output: Path
    steps: int = 1000
    batch_size: int = 4
    chunk_size: int = 16
    device: str = "cpu"
    learning_rate: float = 1e-4
    model_dim: int = 128

    def __post_init__(self) -> None:
        if min(self.steps, self.batch_size, self.chunk_size) < 1 or self.model_dim % 4 or self.model_dim < 16:
            raise ValueError("训练步数、批量、动作分块及模型维度无效")
        if not isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("学习率必须为正数")


class JointNormalizer:
    def __init__(self, metadata: dict, device: str) -> None:
        import torch
        self.lower = torch.tensor([metadata["limits"][name]["lower"] for name in JOINTS], device=device)
        self.width = torch.tensor([metadata["limits"][name]["upper"] - metadata["limits"][name]["lower"] for name in JOINTS], device=device)

    def normalize(self, value):
        return 2 * (value - self.lower) / self.width - 1

    def unnormalize(self, value):
        return (value + 1) * self.width / 2 + self.lower


class ACTTrainer:
    def train(self, config: ACTTrainingConfig, *, progress=None) -> dict:
        # 禁止 Transformers 为本次 PyTorch 工作流额外初始化本机 TensorFlow。
        os.environ.setdefault("USE_TF", "0")
        import torch
        from torch.utils.data import DataLoader
        from lerobot.configs.types import FeatureType, PolicyFeature
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy

        if config.output.exists():
            raise FileExistsError(config.output)
        metadata = json.loads((config.dataset / "imitation.json").read_text(encoding="utf-8"))
        if metadata["joints"] != list(JOINTS) or metadata["unit"] != "radian":
            raise ValueError("数据集关节顺序或单位不匹配")
        dataset = LeRobotDataset(metadata["repo_id"], root=config.dataset,
                    delta_timestamps={"action": [index / metadata["fps"] for index in range(config.chunk_size)]}, download_videos=False)
        if dataset.num_frames < config.chunk_size:
            raise ValueError("数据集帧数少于动作分块长度")
        inputs = {"observation.state": PolicyFeature(FeatureType.STATE, (6,))}
        for name, shape in metadata["images"].items():
            inputs[f"observation.images.{name}"] = PolicyFeature(FeatureType.VISUAL, (shape[2], shape[0], shape[1]))
        if not metadata["images"]:
            inputs["observation.environment_state"] = PolicyFeature(FeatureType.ENV, (6,))
        torch.manual_seed(42)
        policy_config = ACTConfig(input_features=inputs, output_features={"action": PolicyFeature(FeatureType.ACTION, (6,))},
            device=config.device, push_to_hub=False, pretrained_backbone_weights=None, chunk_size=config.chunk_size,
            n_action_steps=1, dim_model=config.model_dim, n_heads=4, dim_feedforward=config.model_dim * 4,
            n_encoder_layers=2, n_decoder_layers=1, n_vae_encoder_layers=2)
        policy = ACTPolicy(policy_config).to(config.device)
        optimizer = torch.optim.AdamW(policy.parameters(), lr=config.learning_rate)
        normalizer = JointNormalizer(metadata, config.device)
        loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True, num_workers=0)
        iterator = iter(loader)
        losses = []
        policy.train()
        for step in range(config.steps):
            try:
                raw = next(iterator)
            except StopIteration:
                iterator = iter(loader)
                raw = next(iterator)
            batch = {key: raw[key].to(config.device) for key in (*inputs, "action", "action_is_pad")}
            for key in ("observation.state", "observation.environment_state", "action"):
                if key in batch:
                    batch[key] = normalizer.normalize(batch[key])
            optimizer.zero_grad(set_to_none=True)
            loss, _ = policy(batch)
            if not torch.isfinite(loss):
                raise RuntimeError("训练损失非有限值")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            if progress is not None:
                progress(step + 1, losses[-1])
        policy.save_pretrained(config.output)
        metadata["normalization"] = "joint_limits_linear_minus1_plus1_v1"
        (config.output / "imitation.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        report = {"steps": config.steps, "first_loss": losses[0], "last_loss": losses[-1],
                  "checkpoint": str(config.output), "simulated_data": metadata["simulated"], "mode": metadata["observation_mode"],
                  "quality_validated": False}
        (config.output / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


class ACTJointPolicy(Policy):
    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._policy = None

    def load(self, checkpoint: Path) -> None:
        os.environ.setdefault("USE_TF", "0")
        import torch
        if self.device == 'cpu':
            threads = int(os.environ.get('XIAOXIA_INFERENCE_THREADS', '2'))
            if threads < 1: raise ValueError('推理线程数必须为正整数')
            torch.set_num_threads(threads)
        from lerobot.policies.act.modeling_act import ACTPolicy
        self._policy = None
        metadata = json.loads((checkpoint / "imitation.json").read_text(encoding="utf-8"))
        if metadata.get("normalization") != "joint_limits_linear_minus1_plus1_v1" or metadata["joints"] != list(JOINTS) or metadata["unit"] != "radian":
            raise ValueError("检查点归一化、关节顺序或单位不匹配")
        self.metadata = metadata
        self.limits = JointLimits({name: JointLimit(**values) for name, values in metadata["limits"].items()})
        self.normalizer = JointNormalizer(metadata, self.device)
        self._policy = ACTPolicy.from_pretrained(checkpoint, local_files_only=True).to(self.device).eval()
        self.reset()

    def warmup(self) -> None:
        """只预热计算，不发送动作；清空预热产生的动作队列。"""
        import numpy as np
        images = {name: np.zeros(shape, dtype=np.uint8) for name, shape in self.metadata['images'].items()}
        try:
            self.predict(Observation(0, self.limits.midpoint()), images=images)
        finally:
            self.reset()

    def reset(self) -> None:
        if self._policy is not None:
            self._policy.reset()

    def predict(self, observation: Observation, *, images=None) -> Action:
        import numpy as np
        import torch
        from PIL import Image
        if self._policy is None:
            raise RuntimeError("请先加载 ACT 检查点")
        self.limits.validate(observation.joint_positions)
        state = torch.tensor([observation.joint_positions[name] for name in JOINTS], device=self.device)
        batch = {"observation.state": self.normalizer.normalize(state).unsqueeze(0)}
        if not self.metadata["images"]:
            batch["observation.environment_state"] = batch["observation.state"].clone()
        for name, shape in self.metadata["images"].items():
            if images is not None:
                pixels = np.array(images[name], dtype=np.uint8, copy=True)
            else:
                with Image.open(observation.image_paths[name]) as image:
                    pixels = np.array(image.convert("RGB"), copy=True)
            if list(pixels.shape) != shape:
                raise ValueError(f"推理图像尺寸不匹配: {name}")
            batch[f"observation.images.{name}"] = torch.from_numpy(pixels).permute(2, 0, 1).float().unsqueeze(0).to(self.device) / 255
        with torch.inference_mode():
            prediction = self.normalizer.unnormalize(self._policy.select_action(batch)[0]).cpu().tolist()
        action = Action(dict(zip(JOINTS, prediction, strict=True)))
        self.limits.validate(action.joint_positions)
        return action
