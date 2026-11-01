"""后端限位审计、主从示教、ACT 训练和推理命令入口。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import argparse
import json
from pathlib import Path

from .act import ACTTrainer, ACTTrainingConfig
from .audit import LimitAudit
from .workflows import HardwareWorkflow, SimulationWorkflow


def main() -> None:
    core = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="SO 系列主从模仿学习")
    parser.add_argument("--urdf", type=Path, default=core / "assets/so100/so100.urdf")
    parser.add_argument("--report", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--calibration", type=Path, action="append", default=[])
    record = commands.add_parser("sim-record")
    record.add_argument("--dataset", type=Path, required=True)
    record.add_argument("--repo-id", default="local/so100-simulation")
    record.add_argument("--frames", type=int, default=60)
    record.add_argument("--episodes", type=int, default=2)
    train = commands.add_parser("train")
    train.add_argument("--dataset", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--steps", type=int, default=1000)
    train.add_argument("--batch-size", type=int, default=4)
    train.add_argument("--chunk-size", type=int, default=16)
    train.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    train.add_argument("--model-dim", type=int, default=128)
    replay = commands.add_parser("sim-rollout")
    replay.add_argument("--checkpoint", type=Path, required=True)
    replay.add_argument("--frames", type=int, default=30)
    for name in ("inspect", "teleop", "record", "rollout"):
        command = commands.add_parser(name)
        command.add_argument("--profile", type=Path, required=True)
        if name != "inspect":
            command.add_argument("--enable-motion", action="store_true")
            command.add_argument("--workspace-clear", action="store_true")
            command.add_argument("--seconds", type=float, default=10)
        if name == "record":
            command.add_argument("--dataset", type=Path, required=True)
            command.add_argument("--repo-id", required=True)
            command.add_argument("--episodes", type=int, default=1)
        if name == "rollout":
            command.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            report = LimitAudit().run(args.urdf, tuple(args.calibration))
        elif args.command == "sim-record":
            report = SimulationWorkflow(args.urdf).record(args.dataset, args.repo_id, args.frames, args.episodes)
        elif args.command == "train":
            report = ACTTrainer().train(ACTTrainingConfig(args.dataset, args.output, args.steps, args.batch_size, args.chunk_size, args.device, model_dim=args.model_dim))
        elif args.command == "sim-rollout":
            report = SimulationWorkflow(args.urdf).rollout(args.checkpoint, args.frames)
        else:
            workflow = HardwareWorkflow(args.profile)
            if args.command == "inspect":
                report = workflow.inspect()
            elif args.command == "rollout":
                report = workflow.rollout(args.checkpoint, args.seconds, motion_enabled=args.enable_motion and args.workspace_clear)
            else:
                report = workflow.record(getattr(args, "dataset", None), getattr(args, "repo_id", ""), args.seconds,
                    getattr(args, "episodes", 1), motion_enabled=args.enable_motion and args.workspace_clear)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    except (Exception, KeyboardInterrupt) as error:
        parser.exit(1, f"任务未完成: {error or '用户中断'}\n")


if __name__ == "__main__":
    main()
