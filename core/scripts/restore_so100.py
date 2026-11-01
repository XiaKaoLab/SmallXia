"""下载固定上游版本的 SO-100 URDF/网格并记录 SHA256。
Created on 2026-11-01; Updated on 2026-11-01
@author: https://github.com/Linmoqian
"""

import hashlib
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree


class SO100Assets:
    commit = "a758567c3978dfeefe282ede0500085a48fe8f78"
    repository = "TheRobotStudio/SO-ARM100"

    def __init__(self) -> None:
        self.directory = Path(__file__).resolve().parents[1] / "assets" / "so100"

    def download(self, relative: str, remote: str | None = None) -> tuple[str, str]:
        target = self.directory / relative
        if not target.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError("资源路径越界")
        source = remote or f"Simulation/SO100/{relative}"
        if target.is_file():
            return relative, hashlib.sha256(target.read_bytes()).hexdigest()
        for host in ("cdn.jsdelivr.net", "fastly.jsdelivr.net", "gcore.jsdelivr.net"):
            cdn = f"https://{host}/gh/{self.repository}@{self.commit}/{source}"
            try:
                with urlopen(cdn, timeout=20) as response:
                    data = response.read()
                if data.startswith(b"version https://git-lfs.github.com"):
                    raise ValueError("CDN 返回 LFS 指针")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                return relative, hashlib.sha256(data).hexdigest()
            except Exception:
                pass
        url = f"https://api.github.com/repos/{self.repository}/contents/{source}?ref={self.commit}"
        metadata = self.fetch_json(url)
        if target.is_file():
            existing = target.read_bytes()
            if hashlib.sha1(f"blob {len(existing)}\0".encode() + existing).hexdigest() == metadata["sha"]:
                return relative, hashlib.sha256(existing).hexdigest()
        if metadata.get("content"):
            data = base64.b64decode(metadata["content"])
        else:
            data = base64.b64decode(self.fetch_json(metadata["git_url"])["content"])
        if data.startswith(b"version https://git-lfs.github.com"):
            url = f"https://media.githubusercontent.com/media/{self.repository}/{self.commit}/{source}"
            with urlopen(url, timeout=60) as response:
                data = response.read()
        target.parent.mkdir(parents=True, exist_ok=True)
        blob_hash = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if not metadata.get("content", "").startswith("dmVyc2lvbi") and blob_hash != metadata["sha"]:
            raise ValueError(f"上游 Git blob 校验失败: {relative}")
        target.write_bytes(data)
        return relative, hashlib.sha256(data).hexdigest()

    @staticmethod
    def fetch_json(url: str) -> dict:
        failure = None
        for _ in range(3):
            try:
                with urlopen(url, timeout=30) as response:
                    return json.load(response)
            except Exception as error:
                failure = error
        raise RuntimeError(f"资源请求失败: {url}") from failure

    def restore(self) -> None:
        urdf, digest = self.download("so100.urdf")
        root = ElementTree.parse(self.directory / urdf).getroot()
        names = sorted({mesh.attrib["filename"] for mesh in root.findall(".//mesh")})
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes = dict(pool.map(self.download, names))
        hashes[urdf] = digest
        license_name, license_hash = self.download("LICENSE", "LICENSE")
        hashes[license_name] = license_hash
        (self.directory / "provenance.json").write_text(json.dumps({
            "repository": f"https://github.com/{self.repository}", "commit": self.commit,
            "model": "SO-100 follower", "sha256": hashes,
        }, indent=2), encoding="utf-8")
        print(f"SO-100 assets ready: {len(names)} meshes, commit {self.commit}")


if __name__ == "__main__":
    SO100Assets().restore()
