# SPDX-License-Identifier: GPL-3.0-or-later
"""Kenney's CC0 images use ordinary UV textures supported by glTF."""
from pathlib import Path
import bpy

ROOT=Path(__file__).parent/'assets'/'kenney'/'PNG'
PALETTES=[('Light','Светлый',''),('Dark','Тёмный',''),('Orange','Оранжевый',''),
          ('Green','Зелёный',''),('Purple','Фиолетовый',''),('Red','Красный','')]
PATTERNS=[(f'{i:02d}',f'Рисунок {i:02d}','') for i in range(1,14)]


def texture_items(self,context):
    from .ui import icon
    return [(key,label,desc,icon('tex_'+self.palette+'_'+key),i) for i,(key,label,desc) in enumerate(PATTERNS)]


def apply_texture(obj):
    p=obj.bs
    name=f'BS_Kenney_{p.palette}_{p.texture}'+('_Water' if p.tag=='WATER' else '')
    mat=bpy.data.materials.get(name)
    if mat is None:
        path=ROOT/p.palette/f'texture_{p.texture}.png'
        if not path.is_file(): raise ValueError('Missing Kenney texture: '+str(path))
        mat=bpy.data.materials.new(name); mat.use_nodes=True
        nodes=mat.node_tree.nodes
        shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
        image=bpy.data.images.load(str(path),check_existing=True); image.pack()
        tex=nodes.new('ShaderNodeTexImage'); tex.image=image; nodes.active=tex
        tex.extension='REPEAT'; tex.interpolation='Linear'
        mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
        shader.inputs['Roughness'].default_value=.8
        if p.tag=='WATER':
            shader.inputs['Alpha'].default_value=.45; mat.surface_render_method='DITHERED'
        # Solid/material color mode remains useful without shader compilation.
        color={'Light':(.7,.7,.7,1),'Dark':(.2,.2,.2,1),'Orange':(.95,.45,.1,1),
               'Green':(.3,.7,.3,1),'Purple':(.6,.3,.8,1),'Red':(.8,.2,.2,1)}[p.palette]
        mat.diffuse_color=color
    obj.data.materials.clear(); obj.data.materials.append(mat)


def texture_changed(self,context):
    if self.enabled or self.id_data.get('bs_curve_wall'): apply_texture(self.id_data)
