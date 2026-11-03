# 来源

https://hugging-face.cn/docs/lerobot/en/index

# LeRobot

[![LeRobot, Hugging Face Robotics Library](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/lerobot/lerobot-logo-thumbnail.png)](https://huggingface.co/lerobot)

**State-of-the-art machine learning for real-world robotics**

🤗 LeRobot provides a hardware-agnostic, Python-native interface for controlling real robots - from affordable arms like the SO-ARM101 to full humanoids. Plus the tools to record, store, and share the datasets they generate. Every dataset uses the standardized **LeRobotDataset** format (synchronized video + action/state data) and can be streamed directly from the [Hugging Face Hub](https://huggingface.co/lerobot).

🤗 On top of that data, LeRobot implements state-of-the-art policies - from lightweight imitation-learning models like ACT to large vision-language-action models like π₀ and SmolVLA - all trainable, shareable, and deployable with the same handful of CLI commands.

The goal: lower the barrier to entry for robotics, so that everyone can contribute to, and benefit from, shared datasets and pretrained models.

[![Discord](https://img.shields.io/badge/Discord-Join_the_Community-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/s3KuuzsPFb) [![X (Twitter)](https://img.shields.io/badge/X-Follow_%40LeRobotHF-black?style=flat&logo=x&logoColor=white)](https://x.com/LeRobotHF) [![Hugging Face Hub](https://img.shields.io/badge/HF_Hub-Models_%26_Datasets-FFD21E?style=flat)](https://huggingface.co/lerobot)

![Reachy 2 Demo](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/lerobot/robots_control_video.webp)

## How It Works

**Teleoperate → Record → Train → Deploy**

1. **Teleoperate** - control the robot yourself (with a leader arm, keyboard, or phone) so it can learn from your movements.
2. **Record** - each demonstration is saved as a dataset: synchronized camera video plus the actions you took.
3. **Train** - a policy (the neural network that will control the robot) learns to imitate your demonstrations.
4. **Deploy** - run the trained policy on the robot and watch it complete the task on its own.

## Get Started

New here? [Install LeRobot](en__installation.md), then pick your path:

🔧 I have a robot

LeRobot supports a wide range of arms and mobile robots. Popular picks:

* [SO-101](en__so101.md) - our flagship, low-cost arm
* [LeKiwi](en__lekiwi.md) - a mobile base with an arm on top
* [Koch v1.1](en__koch.md) - a long-time community favorite
* or find yours under **Robots** in the sidebar

Once it's assembled and calibrated, record a dataset and train your first
policy with the [imitation learning tutorial](en__il_robots.md) - or
skip the CLI entirely with [LeLab](en__lelab.md), a browser GUI for
the same workflow.

💻 No hardware yet

You can still train and evaluate policies without owning a robot:

* train on an existing [LeRobot dataset](https://huggingface.co/datasets?other=LeRobot) from the Hub
* evaluate in [simulation](en__envhub.md), against benchmarks like
  LIBERO or Meta-World
* try the free [Colab notebooks](en__notebooks.md) - nothing to
  install

🤝 I want to contribute

Start with the [Contributing guide](en__contributing.md), then [add a new policy](en__bring_your_own_policies.md) or [bring your own hardware](en__integrate_hardware.md).

## Explore the Docs

[📋 Cheat Sheet

Every LeRobot CLI command, copy-paste ready.](en__cheat-sheet.md) [🖥️ Compute & Hardware Guide

Which policy fits your GPU, and how long training takes.](en__hardware_guide.md) [🗂️ LeRobotDataset

Load, stream, and visualize robot datasets from the Hub.](en__lerobot-dataset-v3.md) [🖼 LeLab

A browser GUI for calibrating, recording, and training - no CLI required.](en__lelab.md) [🧠 Policies

Start with ACT, our recommended first policy - or browse SmolVLA, π₀, and
more in the sidebar.](en__act.md) [🎮 Simulation & Benchmarks

Train and evaluate in simulated environments before touching real
hardware.](en__envhub.md)

## Common Problems

Running into issues? A few of the most frequent ones:

* **Blurry or unusable camera footage** - lighting matters more than resolution. See the [Cameras](en__cameras.md) guide.
* **Build or install errors** (`cmake`, `ffmpeg`, CUDA) - see the Troubleshooting section of the [Installation guide](en__installation.md#troubleshooting).
* **Not sure which policy fits your GPU** - check the [Compute & Hardware Guide](en__hardware_guide.md).
* **Still stuck?** Ask on [Discord](https://discord.gg/s3KuuzsPFb) - the community (and the LeRobot team) is there to help.

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/index.mdx)