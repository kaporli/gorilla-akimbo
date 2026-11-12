"""Bakes a preview into a playable .blend: the scene of scene.py, keyframed on every frame instead of rendered.

usage: blender -b --factory-startup --python scene_bake.py -- config.json
config: the keys of scene.py plus blend (the .blend to write). Frame numbers are the clip frames (seq: the entry index).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import scene


def bake(cfg):
    state = scene.build(cfg); sc, arms, guns = state; tags = []
    for tag in scene.frames(cfg, state):
        for r in arms + [m for g in guns.values() for m in g[3]]:
            for pb in r.arm.pose.bones:
                pb.keyframe_insert('location', frame=tag); pb.keyframe_insert('rotation_quaternion', frame=tag); pb.keyframe_insert('scale', frame=tag)
        for g in guns.values():
            for o in g[1]:
                o.keyframe_insert('location', frame=tag); o.keyframe_insert('rotation_euler', frame=tag); o.keyframe_insert('scale', frame=tag)
        tags.append(tag)
    sc.frame_start, sc.frame_end = min(tags), max(tags); sc.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=cfg['blend'])
    print('DONE', len(tags), cfg['blend'])


if __name__ == '__main__':
    bake(scene.config())
