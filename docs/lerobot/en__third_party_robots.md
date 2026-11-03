# 来源

https://hugging-face.cn/docs/lerobot/en/third_party_robots

# Third-Party Robots & Teleoperators

The LeRobot ecosystem extends far beyond its officially supported hardware. Thanks to LeRobot’s plugin architecture, the community has built integrations for a wide range of robot arms and teleoperation devices — from industrial manipulators to affordable hobbyist platforms, VR headsets, haptic devices, and full arm-plus-teleoperator kits. This page showcases community-maintained integrations you can use for teleoperation, data collection, and policy deployment.

> These projects are developed and maintained by third parties. Please refer to each repository for installation instructions, hardware requirements, and support.

Drop-in plugins are auto-discovered by package name: LeRobot imports any installed package prefixed with `lerobot_robot_` or `lerobot_teleoperator_`. Once installed, reference the `type` the plugin registers (see its README — it may differ from the package name) directly from any LeRobot command:

```
pip install lerobot_robot_<name> lerobot_teleoperator_<name>

lerobot-record \
    --robot.type=<robot_name> \
    --teleop.type=<teleoperator_name> \
    --dataset.repo_id=${HF_USER}/my-dataset \
    --dataset.num_episodes=5
```

> ⚠️ marks projects that are forks/extensions of LeRobot. They may require custom setup rather than working with an unmodified install. All other entries are drop-in plugins.

## Industrial & Collaborative Arms

| Project | Description |
| --- | --- |
| [lerobot-robot-xarm](https://github.com/SpesRobotics/lerobot-robot-xarm) | Plugin for the xArm collaborative arm series from [UFACTORY](https://www.ufactory.cc/). |
| [lerobot\_lebai](https://github.com/lebai-robotics/lerobot_lebai) | Plugin for the six-axis collaborative arms from [Lebai](https://lebai.ltd/en/). |
| [LeFranX](https://github.com/wengmister/LeFranX) ⚠️ | LeRobot extension for the [Franka](https://franka.de/) research arm, paired with the [RobotEra XHand](https://www.robotera.com/) hand for VR teleoperation. |

#### Universal Robots UR5e

| Project | Description |
| --- | --- |
| [UR5e-LeRobot](https://github.com/yechen056/UR5e-LeRobot) ⚠️ | LeRobot extension for the [Universal Robots UR5e](https://www.universal-robots.com/), with single-arm and bimanual support. |
| [lerobot\_ur5e\_auto](https://github.com/scy-v/lerobot_ur5e_auto) ⚠️ | LeRobot extension for a mobile [Universal Robots UR5e](https://www.universal-robots.com/), adding automated recording at scale with minimal supervision. |
| [lerobot\_robot\_ur5e](https://github.com/F-Fer/lerobot_ur5e_gello) | Plugin for the [Universal Robots UR5e](https://www.universal-robots.com/) with a [Robotiq](https://robotiq.com/) gripper, over RTDE control. |

## Research & Learning Arms

| Project | Description |
| --- | --- |
| [lerobot\_trossen](https://github.com/TrossenRobotics/lerobot_trossen) | Plugin for the WidowX and ALOHA-style arms from [Trossen Robotics](https://www.trossenrobotics.com/). |

#### AgileX Piper

| Project | Description |
| --- | --- |
| [lerobot\_robot\_piper (AgRobotics Research)](https://github.com/AgRoboticsResearch/lerobot_robot_piper) | Plugin for the [AgileX Piper](https://global.agilex.ai/) arm. |
| [lerobot\_robot\_piper (WeGo Robotics)](https://github.com/WeGo-Robotics/lerobot_robot_piper) | Plugin for the [AgileX Piper](https://global.agilex.ai/) arm, with multi-arm teleoperation, safety limits, and GUI tools. |

## Affordable & Hobbyist Arms

| Project | Description |
| --- | --- |
| [fashionstar-lerobot-robot-cello](https://github.com/servodevelop/fashionstar-lerobot-robot-cello) | Plugin for the StarAI Cello 6+1 degrees of freedom robot arm from [FashionStar](https://fashionstar.com.hk/). |
| [fashionstar-lerobot-robot-viola](https://github.com/servodevelop/fashionstar-lerobot-robot-viola) | Plugin for the compact StarAI Viola 6+1 degrees of freedom robot arm from [FashionStar](https://fashionstar.com.hk/). |

## Service, Mobile & Utility Robots

| Project | Description |
| --- | --- |
| [lerobot-robot-ugo-pro](https://github.com/ugo-plus/lerobot-robot-ugo-pro) | Plugin for the ugo Pro dual-arm service robot from [ugo](https://ugo.plus/products/ugo-pro/). |
| [lerobot\_robot\_lekiwi\_pincopen](https://github.com/zuoxingdong/lerobot_robot_lekiwi_pincopen) | Plugin for a LeKiwi mobile manipulator with a [PincOpen](https://github.com/pollen-robotics/PincOpen) gripper. |
| [lerobot-robot-dummy](https://github.com/KillingJacky/lerobot-robot-dummy) | Plugin simulating a robot for recording without hardware. Useful for debugging ! |

## Teleoperators

 

### VR & Motion Controllers

| Project | Description |
| --- | --- |
| [lerobot-teleoperator-teleop](https://github.com/SpesRobotics/lerobot-teleoperator-teleop) | Plugin turning a phone or VR headset into a teleoperator via [WebXR](https://immersiveweb.dev), wrapping the open-source [`teleop`](https://github.com/SpesRobotics/teleop) library. |
| [lerobot-teleoperator-spacemouse](https://github.com/Jas000n/lerobot-teleoperator-spacemouse) | Plugin for the [3Dconnexion SpaceMouse](https://3dconnexion.com/), with inverse kinematics for SO-ARMS robots. |
| [vr-teleop-kit](https://github.com/Dream-Machines-Robotics/vr-teleop-kit) | Plugin teleoperating arms from a [Meta Quest](https://www.meta.com/quest/) (WebXR), relying on URDF descriptions for inverse kinematics. |
| [lerobot-teleoperator-pico4](https://github.com/xensedyl/lerobot-teleoperator-pico4) | Plugin for the [PICO 4](https://www.picoxr.com/) VR headset, with a companion controller-free [hand-tracking variant](https://github.com/xensedyl/lerobot-teleoperator-pico4-hand). |

### Leader Arms

| Project | Description |
| --- | --- |
| [lerobot\_teleoperator\_gello](https://github.com/F-Fer/lerobot_ur5e_gello) | Plugin for the 7 degrees of freedom [GELLO](https://wuphilipp.github.io/gello_site/) teleoperator. |
| [lerobot\_teleoperator\_yamactiveleader](https://github.com/uynitsuj/lerobot_teleoperator_yamactiveleader) | Plugin for the active YAM teleoperator from [I2RT](https://i2rt.com/), a bilateral force-feedback arm. |
| [lerobot\_teleoperator\_omy](https://github.com/charlie8612/lerobot_teleoperator_omy) | Plugin for the OMY-L100 6 degrees of freedom teleoperator from [ROBOTIS](https://www.robotis.com/). |
| [lerobot-teleoperator-pipermate](https://pypi.org/project/lerobot-teleoperator-pipermate/) | Plugin for the PiperMate teleoperator ([FashionStar](https://fashionstar.com.hk/) UART servos), driving the [AgileX Piper](https://global.agilex.ai/) arm. |

### Haptic Devices

| Project | Description |
| --- | --- |
| [lerobot\_teleoperator\_inverse3](https://github.com/chohh7391/lerobot_teleoperator_inverse3) | Plugin for the [Haply Inverse3](https://www.haply.co/) haptic device, adding force-feedback teleoperation. |
| [lerobot\_teleoperator\_omega7](https://github.com/hzhz112/lerobot_teleoperator_omega7) | Plugin for the [Force Dimension omega.7](https://www.forcedimension.com/) haptic device, adding force-feedback teleoperation. |

### Networked & Remote

| Project | Description |
| --- | --- |
| [lerobot-teleoperator-livekit](https://pypi.org/project/lerobot-teleoperator-livekit/) | Plugin receiving teleoperation commands over a [LiveKit](https://livekit.io/) Portal (WebRTC) for remote control. |

## Full Kits (Robot + Teleoperator)

| Project | Description |
| --- | --- |
| [lerobot-arx5](https://github.com/villekuosmanen/lerobot-arx5) | Plugin for the [ARX5](https://www.arx-x.com/) arm: [`lerobot-arx5`](https://pypi.org/project/lerobot-robot-arx5/) robot arm with its [`lerobot-teleoperator-arx5`](https://pypi.org/project/lerobot-teleoperator-arx5/) teleoperator arm. |
| [Nextis-AIRA-3D](https://github.com/robertorobotics/Nextis-AIRA-3D) | Plugin for the 7 degrees of freedom arm from [Nextis](https://www.nextis.tech): robot arm `aira_follower` and teleoperator arm `aira_leader`. |
| [lerobot\_yam](https://github.com/pravsels/lerobot_yam) | Plugin suite for the YAM arm from [I2RT](https://i2rt.com/): robot arm `yam_follower` and teleoperator arm `yam_leader`. |
| [trlc-dk1](https://github.com/robot-learning-co/trlc-dk1) | Plugin for the development kit from [The Robot Learning Company](https://www.robot-learning.co/): single and bimanual arms follower/teleoperator types. |
| [hex\_lerobot\_drivers](https://github.com/hexfellow/hex_lerobot_drivers) | Plugin suite for [HEXFELLOW](https://hexfellow.com/) devices: robots, teleoperators, and cameras (see [Cameras & Sensors](en__third_party_sensors.md)). |
| [lerobot-robot-nexarm-follower](https://github.com/Hiwonder-official/lerobot-robot-nexarm-follower) | Plugin for the NexArm from [Hiwonder](https://www.hiwonder.com/): the [robot arm](https://github.com/Hiwonder-official/lerobot-robot-nexarm-follower) and its matching [teleoperator arm](https://github.com/Hiwonder-official/lerobot-teleoperator-nexarm-leader). |

## ROS 2 Bridges

| Project | Description |
| --- | --- |
| [leros2](https://github.com/ngres/leros2) | Plugin bridging ROS 2 topics and actions to LeRobot robots and teleoperators. |
| [lerobot\_robot\_ros2\_zenoh](https://github.com/ROBOTIS-GIT/lerobot_robot_ros2_zenoh) | Plugin bridging ROS 2 robots to LeRobot over [Zenoh](https://zenoh.io) pub/sub transport. |

## Contributing

Built your own LeRobot hardware integration? The plugin system makes it straightforward to add new robots and teleoperators — check out the [Bring Your Own Hardware](en__integrate_hardware.md) guide to get started, and share your project with the community!

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/third_party_robots.mdx)