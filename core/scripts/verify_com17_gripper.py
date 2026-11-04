"""功能：复用匹配的官方 EEPROM 校准，验证 COM17 夹爪小幅运动和编码器反馈，不依赖 URDF 映射。
Created on 2026-11-04; Updated on 2026-11-04
@author: https://github.com/Linmoqian
"""
import json
from pathlib import Path
from time import sleep
import yaml
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus


def main():
    core=Path(__file__).resolve().parents[1]
    config=yaml.safe_load((core/'configs/so100.local.yaml').read_text(encoding='utf-8'))
    follower=config['follower'];names=('shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper')
    expected=json.loads(Path(follower['calibration']).read_text(encoding='utf-8'))
    bus=FeetechMotorsBus(follower['port'],{n:Motor(i,'sts3215',MotorNormMode.DEGREES) for i,n in enumerate(names,1)})
    result={'port':follower['port'],'physical':True,'coordinate_basis':'official_encoder_ticks','joint':'gripper','calibration_written':False,'trajectory':[]}
    enabled=False
    try:
        bus.connect();bus.set_timeout(150)
        actual={n:vars(c) for n,c in bus.read_calibration().items()}
        if actual!=expected:raise ValueError('官方校准与 EEPROM 不匹配')
        if bus.read('Torque_Enable','gripper',normalize=False):raise ValueError('夹爪已由其他控制启用')
        if bus.read('Operating_Mode','gripper',normalize=False)!=0:raise ValueError('夹爪不是位置模式')
        before=bus.sync_read('Present_Position',normalize=False);result['before_ticks']=before
        origin=before['gripper'];row=actual['gripper']
        target=origin+35 if origin+35<=row['range_max']-5 else origin-35
        if not row['range_min']+5<=target<=row['range_max']-5:raise ValueError('夹爪当前位置没有微动空间')
        # 先将位置目标置于实测当前位置，避免使能时追逐旧目标。
        bus.write('Goal_Position','gripper',origin,normalize=False)
        enabled=True;bus.enable_torque('gripper')
        def move(goal):
            start=bus.read('Present_Position','gripper',normalize=False)
            for index in range(1,8):
                command=round(start+(goal-start)*index/7)
                bus.write('Goal_Position','gripper',command,normalize=False);sleep(.12)
                result['trajectory'].append({'command_tick':command,'measured_tick':bus.read('Present_Position','gripper',normalize=False)})
            sleep(.4)
            return bus.read('Present_Position','gripper',normalize=False)
        outward=move(target);result.update(target_tick=target,outward_tick=outward,measured_change_ticks=outward-origin,measured_change_deg=(outward-origin)*360/4095)
        returned=move(origin);result['returned_tick']=returned
        result['motion_observed']=abs(outward-origin)>=10
        result['returned']=abs(returned-origin)<=10
        result['status']='succeeded' if result['motion_observed'] and result['returned'] else 'feedback_not_reached'
        result['after_ticks']=bus.sync_read('Present_Position',normalize=False)
    except Exception as error:result.update(status='failed',error=str(error))
    finally:
        if bus.is_connected:
            try:
                if enabled:bus.disable_torque('gripper')
                result['final_gripper_torque']=bus.read('Torque_Enable','gripper',normalize=False)
            finally:bus.disconnect(disable_torque=False)
        result['disconnected']=not bus.is_connected
        output=core/'data/runtime/video_demo/com17-official-jog.json';output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
