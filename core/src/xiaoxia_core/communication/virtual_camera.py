"""保存虚拟相机装配参数，验证连杆、局部位姿和视场角。
Created on 2026-11-01; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""

from copy import deepcopy
from math import isfinite, pi
from threading import Lock


class VirtualCameraStore:
    def __init__(self, links: set[str]) -> None:
        self.links = links
        self._configuration = None
        self._lock = Lock()

    def configure(self, body: dict) -> dict:
        if not isinstance(body, dict) or not {"parent_link", "position", "rotation", "fov"} <= set(body) or set(body) - {"parent_link", "position", "rotation", "fov", "visible"}:
            raise ValueError("相机需要 parent_link、position、rotation 和 fov")
        if not isinstance(body["parent_link"], str) or body["parent_link"] not in self.links:
            raise ValueError("相机安装连杆不存在")
        for field, bound in (("position", 2.0), ("rotation", pi)):
            vector = body[field]
            if not isinstance(vector, list) or len(vector) != 3 or any(
                type(value) not in (int, float) or not isfinite(value) or abs(value) > bound for value in vector
            ):
                raise ValueError(f"{field} 必须是 ±{bound} 内的三维有限数值")
        if type(body["fov"]) not in (int, float) or not isfinite(body["fov"]) or not 10 <= body["fov"] <= 140:
            raise ValueError("视场角必须为 10～140 度")
        if type(body.get("visible", False)) is not bool:
            raise ValueError("visible 必须是布尔值")
        with self._lock:
            self._configuration = {**deepcopy(body), "visible": body.get("visible", False)}
            return deepcopy(self._configuration)

    def snapshot(self) -> dict | None:
        with self._lock:
            return deepcopy(self._configuration)
