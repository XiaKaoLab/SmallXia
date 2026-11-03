"""功能：只读查询仿真和真机环境，区分串口发现与真实控制连接。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from ..communication.arm_discovery import ArmPortDiscovery


class EnvironmentTools:
    def robot_get_environment(self) -> dict:
        """查询仿真/真机状态并判断机械臂串口候选。综合 USB 名称、VID/PID、已有配置及连接会话，返回推荐端口、置信级别和依据；不打开串口、不使能、不运动。"""
        result = {
            'simulation': {'target': 'table', 'physical': False, 'status': 'unknown'},
            'hardware': {'physical': True, 'status': 'unknown', 'sessions': []},
            'serial_ports': [],
            'note': '仿真状态是显示目标；真机状态来自已有控制会话。检测到串口不等于机械臂连接成功。',
        }
        devices = []
        try:
            from serial.tools.list_ports import comports
            devices = list(comports())
            result['serial_ports'] = [{'port': p.device, 'description': p.description}
                                      for p in devices]
            result['serial_discovery'] = 'ok'
        except (ImportError, OSError):
            result['serial_discovery'] = 'unavailable'
        for key, path in (('simulation', '/api/v1/robots/table/state'),
                          ('hardware', '/api/v1/hardware/arms')):
            try:
                request = Request('http://127.0.0.1:8766' + path,
                                  headers={'Authorization': 'Bearer ' + os.environ.get('XIAOXIA_MOTION_TOKEN', '')})
                with urlopen(request, timeout=2) as response:
                    state = json.loads(response.read(262144))
                if key == 'simulation':
                    if state.get('physical') is not False or state.get('source') != 'display_target':
                        raise ValueError('仿真来源不匹配')
                    result[key].update(status='available', source='display_target')
                else:
                    result[key].update(status='queried', sessions=state['sessions'])
            except (URLError, OSError, ValueError, KeyError):
                result[key]['status'] = 'unknown'
        result['arm_discovery'] = ArmPortDiscovery(
            Path(__file__).resolve().parents[3] / 'configs',
        ).identify(devices, result['hardware']['sessions'])
        return result
