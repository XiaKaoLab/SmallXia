# SO-ARM-101 model source

- Upstream: https://github.com/TheRobotStudio/SO-ARM100
- Commit: a758567c3978dfeefe282ede0500085a48fe8f78 (confirmed from GitHub API on 2026-11-01)
- URDF: Simulation/SO101/so101_new_calib.urdf, unchanged upstream file.
- Meshes: Simulation/SO101/assets/*.stl referenced by that URDF.
- Mesh acquisition: copied from the existing D:/project/FastUMI/assets/so101/meshes cache after GitHub network requests failed. Its fixed-commit provenance and SHA256 values are retained in upstream-cache-provenance.json.
- License: Apache-2.0, upstream LICENSE included.
- Runtime needs no external network: URDF and all 13 referenced meshes are bundled here.

Mesh SHA256 values were compared against the cache provenance on 2026-11-01; all 13 matched.

