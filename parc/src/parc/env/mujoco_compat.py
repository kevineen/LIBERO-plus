"""MuJoCo 3.x と robosuite 1.4 の mj_fullM シグネチャ差を吸収する。

robosuite 1.4 は旧 API: mj_fullM(model, mass_matrix, qM)
MuJoCo 3.10+ は新 API: mj_fullM(model, data, dst)
"""

from __future__ import annotations

_patched = False


def patch_robosuite_mj_fullM() -> bool:
    """Controller.update を新 API 対応に差し替える。成功なら True。"""
    global _patched
    if _patched:
        return True
    try:
        import mujoco
        import numpy as np
        from robosuite.controllers.base_controller import Controller
    except ImportError:
        return False

    def update(self, force: bool = False) -> None:  # noqa: ANN001
        if not (self.new_update or force):
            return
        self.sim.forward()

        self.ee_pos = np.array(self.sim.data.site_xpos[self.sim.model.site_name2id(self.eef_name)])
        self.ee_ori_mat = np.array(
            self.sim.data.site_xmat[self.sim.model.site_name2id(self.eef_name)].reshape([3, 3])
        )
        self.ee_pos_vel = np.array(self.sim.data.get_site_xvelp(self.eef_name))
        self.ee_ori_vel = np.array(self.sim.data.get_site_xvelr(self.eef_name))

        self.joint_pos = np.array(self.sim.data.qpos[self.qpos_index])
        self.joint_vel = np.array(self.sim.data.qvel[self.qvel_index])

        self.J_pos = np.array(
            self.sim.data.get_site_jacp(self.eef_name).reshape((3, -1))[:, self.qvel_index]
        )
        self.J_ori = np.array(
            self.sim.data.get_site_jacr(self.eef_name).reshape((3, -1))[:, self.qvel_index]
        )
        self.J_full = np.array(np.vstack([self.J_pos, self.J_ori]))

        nv = int(self.sim.model.nv)
        mass_matrix = np.ndarray(shape=(nv, nv), dtype=np.float64, order="C")
        model = getattr(self.sim.model, "_model", self.sim.model)
        data = getattr(self.sim.data, "_data", self.sim.data)
        try:
            # MuJoCo 3.x
            mujoco.mj_fullM(model, data, mass_matrix)
        except TypeError:
            # 旧 API フォールバック
            mujoco.mj_fullM(model, mass_matrix, self.sim.data.qM)
        mass_matrix = np.reshape(mass_matrix, (len(self.sim.data.qvel), len(self.sim.data.qvel)))
        self.mass_matrix = mass_matrix[self.qvel_index, :][:, self.qvel_index]
        self.new_update = False

    Controller.update = update  # type: ignore[method-assign]
    _patched = True
    return True
