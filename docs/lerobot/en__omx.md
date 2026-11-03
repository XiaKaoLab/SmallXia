# 来源

https://hugging-face.cn/docs/lerobot/en/omx

# OMX

 ![OMX](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/lerobot/omx_mainimage.png) 

## Order and Assemble the parts

First, assemble the OMX hardware following the official assembly guide.

OMX Assembly Guide: <https://ai.robotis.com/omx/assembly_guide_omx.html>

OMX robots are shipped preconfigured from the factory. Motor IDs, communication parameters, and joint offsets are already set, so no additional motor setup or calibration is required before using LeRobot.

## Install LeRobot 🤗

To install LeRobot, follow our [Installation Guide](en__installation.md)

In addition to these instructions, you need to install the Dynamixel SDK:

```
pip install -e ".[dynamixel]"
```

 

## Connect the robot

To find the port for each bus servo adapter, run this script:

```
lerobot-find-port
```

This command runs and when prompted, disconnect the USB cable from either the leader or follower arm and press Enter. The output will show ‘The port of this MotorsBus is [port]’. This identifies the port for the disconnected arm. Repeat for the other arm to identify both ports.

Mac

Linux

Example output on macOS:

```
Finding all available ports for the MotorBus.
['/dev/tty.usbmodem575E0032081', '/dev/tty.usbmodem575E0031751']
Remove the USB cable from your MotorsBus and press Enter when done.

[...Disconnect corresponding leader or follower arm and press Enter...]

The port of this MotorsBus is /dev/tty.usbmodem575E0032081
Reconnect the USB cable.
```

Where the found port is: `/dev/tty.usbmodem575E0032081` corresponding to your leader or follower arm.

 

## Teleoperate

After identifying the correct ports, you can directly teleoperate the follower arm using the leader arm.

Mac

Linux

### Teleoperate without camera

```
lerobot-teleoperate \
  --robot.type=omx_follower \
  --robot.port=<your_follower_port> \
  --robot.id=omx_follower_arm \
  --teleop.type=omx_leader \
  --teleop.port=<your_leader_port> \
  --teleop.id=omx_leader_arm
```

During teleoperation, motions of the leader arm are mirrored in real time by the follower arm. OMX is already preconfigured, teleoperation can begin immediately without any calibration steps.

### Teleoperate with camera

You can also enable camera input during teleoperation by providing a camera configuration for the follower arm.

```
lerobot-teleoperate \
  --robot.type=omx_follower \
  --robot.port=<your_follower_port> \
  --robot.id=omx_follower_arm \
  --robot.cameras="{front: {type: opencv, index_or_path: '/dev/video0', width: 640, height: 480, fps: 30}}" \
  --teleop.type=omx_leader \
  --teleop.port=<your_leader_port> \
  --teleop.id=omx_leader_arm \
  --display_data=true
```

When the camera is enabled, the camera stream is displayed in real time and synchronized with the robot state. This setup is useful for visual monitoring and can be reused later for demonstration recording and imitation learning.

Congrats 🎉, your robot is all set to learn a task on its own.

> If you have any questions or need help, please reach out on [Discord](https://discord.com/invite/robotis).

 [Update on GitHub](https://github.com/huggingface/lerobot/blob/main/docs/source/https://hugging-face.cn/docs/lerobot/omxx)