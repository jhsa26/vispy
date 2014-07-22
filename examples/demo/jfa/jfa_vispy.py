# -*- coding: utf-8 -*-
"""
Demo of jump flooding algoritm for EDT using GLSL
Author: Stefan Gustavson (stefan.gustavson@gmail.com)
2010-08-24. This code is in the public domain.

Adapted to `vispy` by Eric Larson <larson.eric.d@gmail.com>.

This version is a vispy-ized translation of the OSX C code to Python.
"""

import numpy as np
from os import path as op
from PIL import Image
import time
from vispy.app import Canvas
from vispy.gloo import (Program, VertexShader, FragmentShader, FrameBuffer,
                        VertexBuffer, IndexBuffer, Texture2D, gl, set_viewport,
                        DepthBuffer)
from vispy.util import get_data_file

this_dir = op.dirname(__file__)

# GL_CLAMP_TO_BORDER = 33069
# GL_RG16 = 33324
# GL_TEXTURE_BORDER_COLOR = 4100


class JFACanvas(Canvas):
    def __init__(self):
        Canvas.__init__(self, size=(512, 512), show=True, close_keys='escape')
        self.t0 = 0.0
        self.frames = 0
        self.use_shaders = True
        self.texture_size = (0, 0)
        self._init = False

    def _show_fps(self):
        """Calculate and report texture size and frames per second"""
        t = time.time()
        if (t - self.t0) > 1.:
            fps = self.frames / (t - self.t0)
            self.title = ("%sx%s texture, %.1f FPS"
                          % (self.texture_size[0], self.texture_size[1], fps))
            self.t0 = t
            self.frames = 0
        self.frames += 1

    def _setup_textures(self, fname):
        img = Image.open(get_data_file('jfa/' + fname))
        w, h = img.size
        self.texture_size = (w, h)
        data = np.array(img, np.ubyte)[::-1].copy()
        self.orig_tex = Texture2D(data, format=gl.GL_LUMINANCE)
        self.orig_tex.wrapping = gl.GL_REPEAT
        self.orig_tex.interpolation = gl.GL_NEAREST

        self.comp_texs = []
        data = np.zeros((w, h, 3), np.float32)
        for _ in range(2):
            tex = Texture2D(data, format=gl.GL_RGB)  # XXX RG16
            tex.interpolation = gl.GL_NEAREST
            tex.wrapping = gl.GL_CLAMP_TO_EDGE  # XXX BORDER
            self.comp_texs.append(tex)
        for program in self.programs:
            program['texw'] = self.texture_size[0]
            program['texh'] = self.texture_size[1]
        self.comp_depth = DepthBuffer(self.texture_size)

    def on_initialize(self, event):
        self._init = True
        with open(op.join(this_dir, 'vertex_vispy.glsl'), 'r') as fid:
            vert = VertexShader(fid.read().decode('ASCII'))
        with open(op.join(this_dir, 'fragment_seed.glsl'), 'r') as f:
            frag_seed = FragmentShader(f.read().decode('ASCII'))
        with open(op.join(this_dir, 'fragment_flood.glsl'), 'r') as f:
            frag_flood = FragmentShader(f.read().decode('ASCII'))
        with open(op.join(this_dir, 'fragment_display.glsl'), 'r') as f:
            frag_display = FragmentShader(f.read().decode('ASCII'))
        self.programs = [Program(vert, frag_seed),
                         Program(vert, frag_flood),
                         Program(vert, frag_display)]
        # Initialize variables
        self._setup_textures('shape1.tga')
        self.fbo = FrameBuffer()
        vtype = np.dtype([('position', 'f4', 2), ('texcoord', 'f4', 2)])
        vertices = np.zeros(4, dtype=vtype)
        vertices['position'] = [[-1., -1.], [1., -1.], [1., 1.], [-1., 1.]]
        vertices['texcoord'] = [[0., 0.], [1., 0.], [1., 1.], [0., 1.]]
        vertices = VertexBuffer(vertices)
        for program in self.programs:
            program['step'] = 0
            program.bind(vertices)

    def on_draw(self, event):
        idx = IndexBuffer(np.array([[0, 1, 2], [0, 2, 3]], np.uint32))
        if not self._init:
            self.on_initialize(event)
        self._show_fps()
        if not self.use_shaders:
            self.programs[2]['texture'] = self.orig_tex
        else:
            self.fbo.color_buffer = self.comp_texs[0]
            self.fbo.depth_buffer = self.comp_depth
            last_rend = 0
            self.fbo.activate()
            set_viewport(0, 0, *self.texture_size)
            self.programs[0]['texture'] = self.orig_tex
            self.programs[0].draw(indices=idx, mode='triangles')
            self.fbo.deactivate()
            stepsize = (np.array(self.texture_size) // 2).max()
            while stepsize > 0:
                self.programs[1]['step'] = stepsize
                self.programs[1]['texture'] = self.comp_texs[last_rend]
                last_rend = 1 if last_rend == 0 else 0
                self.fbo.color_buffer = self.comp_texs[last_rend]
                self.fbo.activate()
                set_viewport(0, 0, *self.texture_size)
                self.programs[1].draw(indices=idx, mode='triangles')
                self.fbo.deactivate()
                stepsize //= 2
            self.programs[2]['texture'] = self.comp_texs[last_rend]
        set_viewport(0, 0, *self.size)
        self.programs[2].draw(indices=idx, mode='triangles')
        self.update()

    def on_key_press(self, event):
        if event.key.name in '1234':
            fname = "shape%s.tga" % event.key.name
            self._setup_textures(fname)
        elif event.key == 'F1':
            self.use_shaders = True
        elif event.key == 'F2':
            self.use_shaders = False


c = JFACanvas()
c.app.run()
