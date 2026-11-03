# 来源

https://hugging-face.cn/docs/lerobot/en/third_party_sensors

# Third-Party Cameras & Sensors

The LeRobot ecosystem extends far beyond its natively supported cameras (OpenCV, Intel RealSense, ZMQ, Reachy 2). Thanks to LeRobot’s plugin architecture, the community has built drop-in camera and sensor integrations — from depth cameras to vision-based tactile sensors. This page showcases community-maintained camera and sensor integrations you can use for teleoperation, data collection, and policy deployment.

> These projects are developed and maintained by third parties. Please refer to each repository for installation instructions, hardware requirements, and support.

Drop-in plugins are auto-discovered by package name: LeRobot imports any installed package prefixed with `lerobot_camera_`. Once installed, reference the camera `type` the plugin registers (see its README — it may differ from the package name) directly from any LeRobot command:

```
pip install lerobot_camera_<name>

lerobot-record \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.cameras="{ front: {type: <name>, width: 640, height: 480, fps: 30} }" \
    --dataset.repo_id=${HF_USER}/my-dataset \
    --dataset.num_episodes=5
```

 

## Tactile Sensors

| Project | Description |
| --- | --- |
| [lerobot-camera-xense](https://github.com/xensedyl/lerobot-camera-xense) | Plugin for [Xense](https://www.xenserobotics.com/) vision-based tactile sensors, exposing rectified/difference images, depth, and 2D markers. |

## Depth Cameras

| Project | Description |
| --- | --- |
| [lerobot\_camera\_berxel](https://github.com/hexfellow/hex_lerobot_drivers/tree/main/lerobot_camera_berxel) | Plugin for the [Berxel](https://www.berxel.com/) depth camera, part of the broader [HEXFELLOW](https://hexfellow.com/) driver suite. |

## Networked Cameras

| Project | Description |
| --- | --- |
| [lerobot\_camera\_zmq](https://github.com/F-Fer/lerobot_ur5e_gello) | Plugin streaming [Stereolabs ZED](https://www.stereolabs.com/) and USB camera frames from a Raspberry Pi over the network. |

## Virtual Cameras

| Project | Description |
| --- | --- |
| [lerobot\_camera\_dummy](https://github.com/hexfellow/hex_lerobot_drivers/tree/main/lerobot_camera_dummy) | Plugin simulating a camera for recording without hardware. Useful for debugging ! |

## Contributing

Built your own LeRobot camera or sensor integration? Package it as an installable `lerobot_camera_<name>` plugin and it will be auto-discovered by the LeRobot CLI — see the [Bring Your Own Hardware](en__integrate_hardware.md) guide and the [Cameras](en__cameras.md) reference to get started, then share your project with the community!

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/third_party_sensors.mdx)