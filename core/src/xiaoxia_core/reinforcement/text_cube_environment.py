"""通用文字方块抓取场景：复用机械臂动力学，独立刚体碰撞与目标条件。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
from xml.etree import ElementTree as ET
import mujoco
import numpy as np
from .ball_environment import BallPickupEnvironment


class TextCubeEnvironment(BallPickupEnvironment):
    version = 'so101_letter_cubes_v1'
    letters = ('A', 'B', 'C')
    radius = .016
    half_size = .015
    display_texts = ("A","B","C")
    grasp_offsets = {letter: (0,0,0) for letter in letters}

    def extend_scene(self, mjcf):
        super().extend_scene(mjcf)
        visual = mjcf.find('visual')
        if visual is None: visual = ET.SubElement(mjcf,'visual')
        settings = visual.find('global')
        if settings is None: settings = ET.SubElement(visual,'global')
        settings.set('offwidth','1024');settings.set('offheight','1024')
        from PIL import Image, ImageDraw, ImageFont
        asset = mjcf.find('asset')
        if asset is None: asset = ET.SubElement(mjcf, 'asset')
        from io import BytesIO
        self.scene_assets = {}
        font_path = 'C:/Windows/Fonts/msyhbd.ttc'
        world = mjcf.find('worldbody')
        ET.SubElement(world,'camera',name='letter_overhead',pos='.2 0 .45',quat='1 0 0 0',fovy='34')
        world.remove(world.find("body[@name='pickup_ball']"))
        for letter in self.letters:
            image = Image.new('RGB',(256,256),(244,224,174))
            draw = ImageDraw.Draw(image)
            text=self.display_texts[self.letters.index(letter)]
            font = ImageFont.truetype(font_path, min(150, int(210/max(len(text),1))))
            draw.text((128,128),text,font=font,anchor='mm',fill=(170,30,24))
            path = f'letter_{letter}.png'
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            self.scene_assets[path] = buffer.getvalue()
            ET.SubElement(asset,'texture',name=f'letter_{letter}_texture',type='2d',file=str(path))
            ET.SubElement(asset,'material',name=f'letter_{letter}_material',texture=f'letter_{letter}_texture',texuniform='false')
            name = 'pickup_ball' if letter == 'A' else f'letter_{letter}'
            body = ET.SubElement(world,'body',name=name,pos=f'{.35 + .1*self.letters.index(letter)} .1 .02')
            ET.SubElement(body,'freejoint',name='pickup_ball_free' if letter == 'A' else f'letter_{letter}_free')
            ET.SubElement(body,'geom',name='pickup_ball_geom' if letter == 'A' else f'letter_{letter}_geom',
                type='box',size='.015 .015 .015',mass='.012',friction='1.5 .02 .002',condim='4',
                priority='1',solref='.008 1',material=f'letter_{letter}_material')

    def reset_episode(self, position=None):
        model,data = self._state()
        self.target_letter = getattr(self, 'requested_letter', 'random')
        if self.target_letter == 'random':
            self.target_letter = str(self.random.choice(self.letters))
        self.letter_bodies = {letter: mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,
            'pickup_ball' if letter == 'A' else f'letter_{letter}') for letter in self.letters}
        body = self.letter_bodies[self.target_letter]
        self.ball_joint = int(model.body_jntadr[body])
        self.target_geom_ids = set(range(int(model.body_geomadr[body]),int(model.body_geomadr[body]+model.body_geomnum[body])))
        self.ball_geom = min(self.target_geom_ids)
        # 父类负责关节随机姿态与奖励初始化；最终再随机摆放三个字母并重算初始参考。
        super().reset_episode(position=position)
        slots = self.random.permutation(3)
        for index,letter in enumerate(self.letters):
            address = model.jnt_qposadr[model.body_jntadr[self.letter_bodies[letter]]]
            xy = [self.random.uniform(.185,.215), (int(slots[index])-1)*.05 + self.random.uniform(-.003,.003)]
            if letter == self.target_letter and position is not None:
                xy = position
            angle = self.random.uniform(-.35,.35)
            data.qpos[address:address+3] = [*xy,self.floor_z+self.half_size+.001]
            data.qpos[address+3:address+7] = [np.cos(angle/2),0,0,np.sin(angle/2)]
            dof = model.jnt_dofadr[model.body_jntadr[self.letter_bodies[letter]]]
            data.qvel[dof:dof+6] = 0
        mujoco.mj_forward(model,data)
        self._physics_step(track_hold=False)
        self.initial_ball_position = self.ball_position()
        self.spawn_position = self.initial_ball_position.copy()
        from .pickup_reward import PickupReward
        self.reward = PickupReward(float(np.linalg.norm(self.ball_position()-data.site_xpos[self.tip])),
            float(np.linalg.norm(data.site_xmat[self.tip].reshape(3,3)[:,2]-[0,0,1])))
        self.wrong_contact_steps = 0
        return self.state()

    def select_body(self, body):
        """仅在视觉定位结束后绑定被选物体，用于物理接触与得分；不参与视觉分类。"""
        self.target_letter = next(letter for letter,value in self.letter_bodies.items() if value == body)
        self.ball_joint = int(self._model.body_jntadr[body])
        self.target_geom_ids = {int(self._model.body_geomadr[body])}
        self.ball_geom = min(self.target_geom_ids)
        self.initial_ball_position = self.ball_position()
        self.spawn_position = self.initial_ball_position.copy()
        from .pickup_reward import PickupReward
        self.reward = PickupReward(float(np.linalg.norm(self.ball_position()-self._data.site_xpos[self.tip])),
            float(np.linalg.norm(self._data.site_xmat[self.tip].reshape(3,3)[:,2]-[0,0,1])))

    def ball_position(self):
        body = self.letter_bodies[self.target_letter]
        return self._data.xpos[body] + self._data.xmat[body].reshape(3,3) @ np.asarray(self.grasp_offsets[self.target_letter])

    def advance(self, action):
        state,reward,terminated,truncated,success = super().advance(action)
        wrong = False
        model,data = self._state()
        for contact in data.contact:
            if contact.efc_address < 0 or contact.dist > 0: continue
            bodies = {int(model.geom_bodyid[contact.geom1]),int(model.geom_bodyid[contact.geom2])}
            if bodies & self.jaws and any(self.letter_bodies[x] in bodies for x in self.letters if x != self.target_letter):
                wrong = True
        penalty = -.25 if wrong else 0.
        self.wrong_contact_steps += int(wrong)
        reward += penalty
        self.return_ += penalty
        self.last_reward_terms['wrong_letter_contact'] = penalty
        return state,reward,terminated,truncated,success

    def observe_ball_image(self, rgb):
        # 此奖励只表示文字颜色进入腕部画面；文字身份由独立 OCR 选择器处理。
        super().observe_ball_image(rgb)

    def snapshot(self):
        snapshot = super().snapshot()
        snapshot.update(target_text=self.display_texts[self.letters.index(self.target_letter)], task='text_cube_pickup',
            wrong_contact_steps=getattr(self,'wrong_contact_steps',0),
            objects=[{'letter':self.display_texts[self.letters.index(letter)],'position':self._data.xpos[body].tolist(),
                'quaternion':self._data.xquat[body].tolist(),'target':letter==self.target_letter,
                'half_size':self.half_size} for letter,body in self.letter_bodies.items()])
        return snapshot


