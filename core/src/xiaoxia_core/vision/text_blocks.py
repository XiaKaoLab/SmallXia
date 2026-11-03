"""开放文字方块识别：通用 OCR、保守目标匹配与已标定平面定位。
Created on 2026-11-03; Updated on 2026-11-03
@author: https://github.com/Linmoqian
"""
import unicodedata
import numpy as np


class TextBlockReader:
    def __init__(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as error:
            raise ValueError('请安装核心包的 text-vision 可选依赖后使用文字识别') from error
        self.engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)

    @staticmethod
    def normalize(text):
        return ''.join(unicodedata.normalize('NFKC',text).casefold().split())

    def read(self,rgb,threshold=.8):
        if not isinstance(rgb,np.ndarray) or rgb.ndim!=3 or rgb.shape[2]!=3 or rgb.dtype!=np.uint8:
            raise ValueError('OCR 需要 uint8 RGB 图像')
        result,_=self.engine(np.ascontiguousarray(rgb[:,:,::-1]),text_score=0.,box_thresh=.3)
        detections=[]
        for box,text,raw_score in result or []:
            # rapidocr_onnxruntime 1.2.3 的 CTC decoder 在均值中额外加入一个 1e-50；
            # 移除此虚拟样本，保留真正字符概率均值，避免单字置信度被系统性减半。
            score=min(1.,float(raw_score)*(len(text)+1)/max(len(text),1))
            if not text or score<threshold:continue
            detections.append(dict(text=str(text),confidence=score,raw_decoder_score=float(raw_score),
                polygon=np.asarray(box).tolist(),pixel_center=np.asarray(box,dtype=float).mean(axis=0).tolist()))
        return detections

    def select(self,rgb,target,threshold=.8):
        detections=self.read(rgb,threshold)
        matches=[x for x in detections if self.normalize(x['text'])==self.normalize(target)]
        if len(matches)!=1:
            raise ValueError('未唯一识别目标文字，请调整视角或确认目标；不执行抓取')
        return matches[0],detections


class CalibratedPlane:
    """K 与 camera_to_world 必须来自标定；真实相机不能套用仿真外参。"""
    def __init__(self, intrinsic, camera_to_world, z):
        self.k=np.asarray(intrinsic,dtype=float);self.transform=np.asarray(camera_to_world,dtype=float);self.z=float(z)
        if self.k.shape!=(3,3) or self.transform.shape!=(4,4) or not np.isfinite(self.k).all() or not np.isfinite(self.transform).all():
            raise ValueError('需要有限的 3×3 内参与 4×4 相机外参')

    def locate(self,pixel):
        ray=self.transform[:3,:3] @ np.linalg.solve(self.k,np.r_[pixel,1.])
        origin=self.transform[:3,3]
        if abs(ray[2])<1e-8:raise ValueError('射线与桌面平行')
        distance=(self.z-origin[2])/ray[2]
        if distance<=0:raise ValueError('目标平面在相机后方')
        return origin+distance*ray
