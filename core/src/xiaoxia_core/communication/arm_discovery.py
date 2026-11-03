"""功能：根据 USB 元数据、已有配置和控制会话排序机械臂串口，不打开设备。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""

from pathlib import Path
import yaml


class ArmPortDiscovery:
    def __init__(self, configs: Path) -> None:
        self.configs = configs

    def profiles(self) -> dict[str, list[str]]:
        ports: dict[str, list[str]] = {}
        for path in sorted(self.configs.glob('*.yaml')):
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8-sig')) or {}
                for role in ('leader', 'follower'):
                    arm = data.get(role, {})
                    port = arm.get('port') if isinstance(arm, dict) else None
                    if isinstance(port, str) and port:
                        ports.setdefault(port.upper(), []).append(f'{path.name}:{role}')
            except (OSError, ValueError, yaml.YAMLError, AttributeError):
                continue
        return ports

    def identify(self, devices, sessions=()) -> dict:
        configured = self.profiles()
        active = {s.get('port') for s in sessions if s.get('physical') is True
                  and s.get('status') in ('ready', 'moving')}
        candidates = []
        for device in devices:
            port = device.device
            description = device.description or ''
            manufacturer = getattr(device, 'manufacturer', None) or ''
            product = getattr(device, 'product', None) or ''
            identity = ' '.join((description, manufacturer, product)).lower()
            vid, pid = getattr(device, 'vid', None), getattr(device, 'pid', None)
            evidence, score, confidence = [], 0, 'unknown'
            bluetooth = any(value in identity for value in ('bluetooth', '蓝牙', 'bthenum'))
            if bluetooth:
                evidence.append('蓝牙虚拟串口，不优先作为 USB 机械臂候选')
            else:
                if vid is not None:
                    score = 20
                    evidence.append('USB 串口设备')
                if any(value in identity for value in ('ch340', 'ch341', 'ch343', 'ch910', 'ftdi', 'cp210', 'usb-enhanced-serial')):
                    score = max(score, 35)
                    evidence.append('常见 USB 串口适配器；也可能连接其他设备')
                if any(value in identity for value in ('feetech', 'waveshare', 'so-100', 'so-101', 'so100', 'so101')):
                    score = max(score, 55)
                    evidence.append('设备名称包含机械臂或控制板相关标识')
                matches = configured.get(port.upper(), [])
                if matches:
                    score = max(score, 70)
                    evidence.append('匹配已有机械臂配置：' + '、'.join(matches))
            if port in active:
                score, confidence = 100, 'connected'
                evidence.append('当前已有就绪的真机控制会话')
            elif score >= 55:
                confidence = 'likely'
            elif score:
                confidence = 'possible'
            candidates.append({
                'port': port, 'description': description, 'manufacturer': manufacturer,
                'product': product, 'vid': f'{vid:04X}' if vid is not None else None,
                'pid': f'{pid:04X}' if pid is not None else None,
                'serial_number': getattr(device, 'serial_number', None),
                'confidence': confidence, 'score': score, 'evidence': evidence,
            })
        candidates.sort(key=lambda candidate: (-candidate['score'], candidate['port']))
        best = candidates[0] if candidates else None
        unique = bool(best and best['score'] >= 55 and
                      (len(candidates) == 1 or best['score'] > candidates[1]['score']))
        return {'candidates': candidates, 'recommended_port': best['port'] if unique else None,
                'method': 'metadata_and_existing_configuration', 'opened_ports': False,
                'note': '推荐是候选判断；历史 COM 配置可能过期，USB 适配器名称不能证明电机身份。并列候选不自动选择。'}
