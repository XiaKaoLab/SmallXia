# SO-ARM-101 model source

- Upstream: https://github.com/TheRobotStudio/SO-ARM100
- Commit: a758567c3978dfeefe282ede0500085a48fe8f78 (confirmed from GitHub API on 2026-11-01)
- URDF: Simulation/SO101/so101_new_calib.urdf, unchanged upstream file.
- Meshes: Simulation/SO101/assets/*.stl referenced by that URDF.
- Mesh acquisition: copied from the existing D:/project/FastUMI/assets/so101/meshes cache after GitHub network requests failed. Its fixed-commit provenance and SHA256 values are retained in upstream-cache-provenance.json.
- License: Apache-2.0, upstream LICENSE included.
- Runtime needs no external network: URDF and all 13 referenced meshes are bundled here.

Mesh SHA256 values were compared against the cache provenance on 2026-11-01; all 13 matched.



## Optional wrist camera mount

`camera/wrist_camera_mount_so101.stl` is the unchanged upstream `Optional/Wrist_Cam_Mount_32x32_UVC_Module/stl/Wrist_Cam_Mount_32x32_UVC_Module_SO101.stl` at the same pinned commit. See camera/provenance.json for SHA256, bounds and units.

When camera display is explicitly enabled, the fallback loader checks whether the URDF already references a camera mount. Otherwise it replaces only the original wrist-roll printed visual, retaining the servo and moving jaw. It inherits that visual's position/quaternion/scale and converts the print mesh from millimeters to meters without recentering. Hiding the camera restores the original printed visual. No URDF source or collision geometry was modified.

The optional mesh shares the original printed visual's main X bounds and maximum Z after unit conversion. It adds a camera support extending to Y=89.36899 mm. This supports using the existing CAD frame, but is not a measured optical-center calibration. Camera body, lens and optical pose remain virtual approximations.
