import mujoco, numpy as np
from PIL import Image
m = mujoco.MjModel.from_xml_path("menagerie/unitree_go2/scene.xml")
m.vis.global_.offwidth, m.vis.global_.offheight = 2400, 1600
d = mujoco.MjData(m)
k = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_KEY, "home")
mujoco.mj_resetDataKeyframe(m, d, k if k >= 0 else 0); mujoco.mj_forward(m, d)
floor = [i for i in range(m.ngeom) if m.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE]
for i in floor: m.geom_rgba[i, 3] = 0
r = mujoco.Renderer(m, 1600, 2400)
cam = mujoco.MjvCamera(); cam.lookat[:] = d.qpos[:3] + [0, 0, -0.02]; cam.distance = 1.25; cam.azimuth = 215; cam.elevation = -22
r.update_scene(d, cam); rgb = r.render()
r.enable_segmentation_rendering(); r.update_scene(d, cam); seg = r.render(); r.disable_segmentation_rendering()
alpha = ((seg[..., 0] >= 0) & ~np.isin(seg[..., 0], floor)).astype(np.uint8) * 255
im = Image.fromarray(np.dstack([rgb, alpha]), "RGBA"); im = im.crop(im.getbbox())
im.save("go2-render.png"); print(im.size)
