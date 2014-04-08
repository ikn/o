"""Basic graphic representing an image.

---NODOC---

TODO:
 - a solution to the rotation problem (jaggy edges if they were the surface borders)
 - why can't we move rotate earlier?
 - use subsurface for crop transform (but requires rect to be within surface)
 - GraphicView probably doesn't work if in different manager - need to have own _dirty?
 - something that wraps a Graphic to be a copy of it, like Animation does, and has .graphic setter - for use in other classes
    - use in Animation, etc.

---NODOC---

"""

from math import sin, cos, pi

import pygame as pg
from pygame import Rect

from ..conf import conf
from ..util import (ir, pos_in_rect, align_rect, normalise_colour, has_alpha,
                    blank_sfc, combine_drawn)


class Graphic (object):
    """Something that can be drawn to the screen.

Graphic(img, pos=(0, 0), layer=0, pool=conf.DEFAULT_RESOURCE_POOL,
        res_mgr=conf.GAME.resources)

:arg img: surface or filename (under :data:`conf.IMG_DIR`) to load.  If a
          surface, it should be already converted for blitting.
:arg pos: initial ``(x, y)`` position.  The existence of a default is because
          you might use :meth:`align` immediately on adding to a
          :class:`GraphicsManager <engine.gfx.container.GraphicsManager>`.
:arg layer: the layer to draw in, lower being closer to the 'front'. This can
            actually be any hashable object except ``None``, as long as all
            layers used in the same
            :class:`GraphicsManager <engine.gfx.container.GraphicsManager>` can
            be ordered with respect to each other.
:arg pool: :class:`ResourceManager <engine.res.ResourceManager>` resource pool
           name to cache any loaded images in.
:arg res_mgr: :class:`ResourceManager <engine.res.ResourceManager>` instance to
              use to load any images.

Many properties of a graphic, such as :attr:`pos` and :attr:`size`, can be
changed in two main ways: by setting the attribute directly, or by calling the
corresponding method.  The former is more natural, and is useful for
:meth:`sched.Scheduler.interp() <engine.sched.Scheduler.interp>`, while the
latter all return the graphic, and so can be chained together.

Position and size can also be retrieved and altered using list indexing, like
with Pygame rects.  Altering size in any way applies the :meth:`resize`
transformation.

:meth:`resize`, :meth:`crop`, :meth:`flip`, :meth:`opacify` and :meth:`rotate`
correspond to builtin transforms (see :meth:`transform`).

"""

    is_view = False
    _builtin_transforms = ('crop', 'flip', 'tint', 'resize', 'rotate')

    def __init__ (self, img, pos=(0, 0), layer=0,
                  pool=conf.DEFAULT_RESOURCE_POOL, res_mgr=None):
        self._resource_pool = pool
        self._resource_manager = res_mgr
        if isinstance(img, basestring):
            #: Filename of the loaded image, or ``None`` if a surface was
            #: given.
            self.fn = img
            img = self._load_img(img)
        else:
            self.fn = None
        self._orig_sfc = self._surface = img
        # postrot is the rect drawn in
        self._postrot_rect = self._rect = Rect(pos, img.get_size())
        self._last_postrot_rect = Rect(self._postrot_rect)
        #: :attr:`rect` at the time of the last draw.
        self.last_rect = Rect(self._rect)
        self._anchor = (0, 0)
        self._rot_anchor = 'center'
        self._rot_offset = (0, 0) # postrot_pos = pos + rot_offset
        self._must_apply_rot = False
        #: A list of transformations applied to the graphic.  Always contains
        #: the builtin transforms as strings (though they do nothing
        #: by default); other transforms are added through :meth:`transform`,
        #: and are functions.
        self.transforms = list(self._builtin_transforms)
        self._last_transforms = list(self.transforms)
        # {function: (args, previous_surface, resulting_surface, apply_fn,
        #             undo_fn)}
        # last 2 None for non-builtins
        self._transforms = {}
        # {function: (args, previous_size, resulting_size, apply_fn, undo_fn)}
        # last 4 None for non-builtins
        self._queued_transforms = {}
        #: Whether the graphic is completely opaque; do not change.
        self.opaque = not has_alpha(img)
        self._manager = None
        self._mgr_requires = False
        self._layer = layer
        #: When blitting the surface, this is passed as the ``special_flags``
        #: argument.
        self._last_blit_flags = self.blit_flags = 0
        #: Whether currently (supposed to be) visible on-screen.
        self.visible = True
        #: Whether this graphic was visible at the time of the last draw; do
        #: not change.
        self.was_visible = False
        self._scale = (1, 1)
        self._cropped_rect = None
        self._flipped = (False, False)
        self._tint_colour = (255, 255, 255, 255)
        self._angle = 0
        self._scale_fn = pg.transform.smoothscale
        self._rotate_fn = lambda sfc, angle: \
            pg.transform.rotozoom(sfc, angle * 180 / pi, 1)
        self._rotate_threshold = 2 * pi / 500
        self._orig_dirty = False # where original surface is changed
        # where final surface is changed; gets used (and reset) by manager
        self._dirty = []
        # {cb: evts}
        self._cbs = {}
        # {evt: cbs}
        self._evts = {}

    def __getitem__ (self, i):
        if isinstance(i, slice):
            # Rect is weird and only accepts slices through slice syntax
            # this is the easiest way around it (and slicing doesn't work with
            # Python 3 anyway)
            r = self._rect
            return [r[i] for i in range(4)[i]]
        else:
            return self._rect[i]

    def __setitem__ (self, i, v):
        r = Rect(self._rect)
        if isinstance(i, slice):
            for v_i, r_i in enumerate(range(4)[i]):
                r[r_i] = v[v_i]
        else:
            r[i] = v
        self.rect = r

    @property
    def orig_sfc (self):
        """The surface before any transforms.

When setting this, the surface should be already converted for blitting.

"""
        return self._orig_sfc

    @orig_sfc.setter
    def orig_sfc (self, sfc):
        size = sfc.get_size()
        old_sfc = self._orig_sfc
        self._orig_sfc = sfc
        if size != old_sfc.get_size():
            self.size_changed(size)
        self._orig_dirty = True
        self._call_cbs('change orig', old_sfc, sfc)

    @property
    def surface (self):
        """The (possibly transformed) surface that will be used for drawing.

Accessing this will cause all queued transformations to be applied.

"""
        self.render()
        return self._surface

    # appearance properties

    @property
    def rect (self):
        """``pygame.Rect`` giving the on-screen area covered.

May be set directly, but not altered in-place.

This is actually the rect before rotation, which is probably what you want,
really.  To get the real rect, use :attr:`postrot_rect`.

"""
        return self._rect

    @rect.setter
    def rect (self, rect):
        # need to set dirty in old and new rects (if changed)
        rect = Rect(rect)
        old_rect = self._rect
        self._rect = Rect(rect.topleft, self._rect.size)
        if rect.size != old_rect.size:
            self.resize(*rect.size)

    @property
    def x (self):
        """``x`` co-ordinate of the top-left corner of :attr:`rect`."""
        return self._rect[0]

    @x.setter
    def x (self, x):
        r = Rect(self._rect)
        r[0] = x
        self.rect = r

    @property
    def y (self):
        """``y`` co-ordinate of the top-left corner of :attr:`rect`."""
        return self._rect[1]

    @y.setter
    def y (self, y):
        r = Rect(self._rect)
        r[1] = y
        self.rect = r

    @property
    def pos (self):
        """``(``:attr:`x` ``,`` :attr:`y` ``)``."""
        return self._rect.topleft

    @pos.setter
    def pos (self, pos):
        self.rect = (pos, self._rect.size)

    @property
    def w (self):
        """Width of :attr:`rect`; uses :meth:`resize`."""
        return self._rect[2]

    @w.setter
    def w (self, w):
        r = Rect(self._rect)
        r[2] = w
        self.rect = r

    @property
    def h (self):
        """Height of :attr:`rect`; uses :meth:`resize`."""
        return self._rect[3]

    @h.setter
    def h (self, h):
        r = Rect(self._rect)
        r[3] = h
        self.rect = r

    @property
    def size (self):
        """``(``:attr:`w` ``,`` :attr:`h` ``)``."""
        return self._rect.size

    @size.setter
    def size (self, size):
        self.rect = (self._rect.topleft, size)

    @property
    def scale_x (self):
        """Scaling ratio of the graphic on the x-axis; uses :meth:`rescale`."""
        return self._scale[0]

    @scale_x.setter
    def scale_x (self, scale_x):
        self.rescale(scale_x, self._scale[1])

    @property
    def scale_y (self):
        """Scaling ratio of the graphic on the y-axis; uses :meth:`rescale`."""
        return self._scale[1]

    @scale_y.setter
    def scale_y (self, scale_y):
        self.rescale(self._scale[0], scale_y)

    @property
    def scale (self):
        """``(``:attr:`scale_x` ``,`` :attr:`scale_y` ``)``.

Can be set to a single number to scale by in both dimensions.

"""
        return self._scale

    @scale.setter
    def scale (self, scale):
        if isinstance(scale, (int, float)):
            self.rescale(scale, scale)
        else:
            self.rescale(*scale)

    @property
    def cropped_rect (self):
        """The rect currently cropped to."""
        if self._cropped_rect is None:
            return Rect((0, 0), self.sz_before_transform('crop'))
        else:
            return self._cropped_rect

    @cropped_rect.setter
    def cropped_rect (self, rect):
        self.crop(rect)

    @property
    def flipped_x (self):
        """Whether flipped on the x-axis."""
        return self._flipped[0]

    @flipped_x.setter
    def flipped_x (self, flipped_x):
        self.flip(flipped_x, self._flipped[1])

    @property
    def flipped_y (self):
        """Whether flipped on the y-axis."""
        return self._flipped[0]

    @flipped_x.setter
    def flipped_y (self, flipped_y):
        self.flip(self._flipped[0], flipped_y)

    @property
    def flipped (self):
        """``(``:attr:`flipped_x` ``,`` :attr:`flipped_y` ``)``.

Can be set to a single value to apply to both dimensions.

"""
        return self._flipped

    @flipped.setter
    def flipped (self, flipped):
        if isinstance(flipped, (bool, int)):
            self.flip(flipped, flipped)
        else:
            self.flip(*flipped)

    @property
    def tint_colour (self):
        """Tinted colour of the graphic, as taken by
:func:`engine.util.normalise_colour`."""
        return self._tint_colour

    @tint_colour.setter
    def tint_colour (self, colour):
        self.tint(colour)

    @property
    def opacity (self):
        """Opacity of the graphic, from ``0`` (transparent) to ``255``."""
        return self._tint_colour[3]

    @opacity.setter
    def opacity (self, opacity):
        self.opacify(opacity)

    @property
    def angle (self):
        """Current rotation angle, anti-clockwise in radians.

Also see :attr:`rot_anchor`.

"""
        return self._angle

    @angle.setter
    def angle (self, angle):
        self.rotate(angle)

    @property
    def postrot_rect (self):
        """``pygame.Rect`` giving the on-screen area covered after rotation."""
        self.render()
        return self._postrot_rect

    @property
    def anchor (self):
        """The point within :attr:`rect` to fix in place when size changes.

This is a position as taken by :func:`engine.util.pos_in_rect` (where the
``rect`` argument will be :attr:`rect`).  Defaults to ``(0, 0)``.

"""
        return self._anchor

    @anchor.setter
    def anchor (self, anchor):
        self._anchor = anchor
        self.retransform('resize')

    @property
    def rot_anchor (self):
        """Like :attr:`anchor`, used for rotation.

Defaults to ``'center'``.

"""
        return self._rot_anchor

    @rot_anchor.setter
    def rot_anchor (self, anchor):
        self._rot_anchor = anchor
        self.retransform('rotate')

    @property
    def scale_fn (self):
        """Function to use for scaling.

Defaults to ``pygame.transform.smoothscale`` (and should have the same
signature as this default).

"""
        return self._scale_fn

    @scale_fn.setter
    def scale_fn (self, scale_fn):
        self._scale_fn = scale_fn
        self.retransform('resize')

    @property
    def rotate_fn (self):
        """Function to use for rotating.

Uses ``pygame.transform.rotozoom`` by default.  Takes the surface and angle (as
passed to :meth:`rotate`) and returns the new rotated surface.

"""
        return self._rotate_fn

    @rotate_fn.setter
    def rotate_fn (self, rotate_fn):
        self._rotate_fn = rotate_fn
        self.retransform('rotate')

    @property
    def rotate_threshold (self):
        """Only rotate when the angle changes by this much.

Defaults to ``2 * pi / 500``."""
        return self._rotate_threshold

    @rotate_threshold.setter
    def rotate_threshold (self, rotate_threshold):
        self._rotate_threshold = rotate_threshold
        self.retransform('rotate')

    # other properties

    @property
    def manager (self):
        """The thing that 'owns' this graphic.

This is usually a
:class:`GraphicsManager <engine.gfx.container.GraphicsManager>` instance, or
``None``, but may be any other object (only really useful with
:meth:`require`).  If this object has ``'add'``, ``'rm'`` or ``'orig_size'``
attributes, these must be implemented like in
:class:`GraphicsManager <engine.gfx.container.GraphicsManager>`.

This property may be changed directly.

"""
        return self._manager

    @manager.setter
    def manager (self, manager):
        if manager is not self._manager and self._mgr_requires:
            raise RuntimeError('tried to change manager on manager-locked '
                               'graphic')
        if hasattr(self._manager, 'rm'):
            self._manager.rm(self)
        if hasattr(self._manager, 'add'):
            manager.add(self) # sets ._manager
        else:
            self._manager = manager

    @property
    def layer (self):
        """As taken by the constructor."""
        return self._layer

    @layer.setter
    def layer (self, layer):
        if layer != self._layer:
            # change layer in gm by removing, setting attribute, then adding
            m = self._manager
            if hasattr(m, 'rm'):
                m.rm(self)
            self._layer = layer
            if hasattr(m, 'add'):
                m.add(self)

    def require (self, manager):
        """Set :attr:`manager` to the given manager, and lock it.

If the graphic's manager is locked, trying to change its manager raises
RuntimeError.

"""
        self.manager = manager
        self._mgr_requires = True

    # movement

    def move_to (self, x = None, y = None):
        """Move to the given position.

move_to([x][, y]) -> self

Omitted arguments are unchanged.

"""
        r = Rect(self._rect)
        if x is not None:
            r[0] = x
        if y is not None:
            r[1] = y
        self.rect = r
        return self

    def move_by (self, dx = 0, dy = 0):
        """Move by the given number of pixels.

move_by(dx = 0, dy = 0) -> self

"""
        self.rect = self._rect.move(dx, dy)
        return self

    def align (self, alignment = 0, pad = 0, offset = 0, within = None):
        """Position this graphic within a rect.

align(alignment = 0, pad = 0, offset = 0,
      within = self.manager.orig_sfc.get_rect()) -> self

All arguments are as taken by :func:`engine.util.align_rect`.

"""
        if within is None:
            if not hasattr(self._manager, 'orig_size'):
                raise TypeError('received no \'within\' argument and manager '
                                'has no \'orig_size\' attribute')
            within = Rect((0, 0), self._manager.orig_size)
        self.pos = align_rect(self._rect, within, alignment, pad, offset)
        return self

    # transform

    """Doc for _gen_mods_* methods.

Each builtin transform requires a _gen_mods_<transform> method, as follows:

_gen_mods_<transform>(src_sz, first_time, last_args, *args)
    -> ((apply_fn, undo_fn), dest_sz)

src_sz: size before the transform.
first_time: whether this is the first time these modifiers have been generated.
last_args: transform arguments at the time of the last modifier generation, or
           None.  Guaranteed to be non-None if first_time is False

If first_time is False and the modifiers would not be different from
previously, the return value may be None.

apply_fn, undo_fn: functions that take the Graphic instance and apply or undo
                   modifiers that the transform requires (such as setting
                   transform attributes like angle).
dest_sz: the size after the transform.

"""

    def last_transform_args (self, transform_fn):
        """Return the last (tuple of) arguments passed to the given transform.

This is all arguments passed to the transform when it was last applied/queued.
Takes a transform function as taken by :meth:`transform`.  If it has not been
applied/queued yet, the return value is ``None`` (builtin transformations are
always applied).

"""
        try:
            return self._queued_transforms[transform_fn][0]
        except KeyError:
            try:
                return self._transforms[transform_fn][0]
            except KeyError:
                return None

    def _sfc_before_transform (self, transform_fn):
        """Get queued/applied previous surface (size) for a transform function.

Loops backwards until the transform in question is not an unapplied builtin.
Transform may be an index in transforms.

Returns (sfc, is_size), or (None, None) if the transform doesn't exist.

"""
        t_ks = self.transforms
        if isinstance(transform_fn, int):
            i = transform_fn
            if i < 0 or i >= len(self.transforms):
                return (None, None)
        else:
            try:
                i = self.transforms.index(transform_fn)
            except ValueError:
                return (None, None)
        q = self._queued_transforms
        ts = self._transforms
        while True:
            if i == 0:
                # first transform
                return (self._orig_sfc, False)
            else:
                # use previous transform's final surface
                i -= 1
                fn = t_ks[i]
                if fn in q:
                    if isinstance(fn, basestring):
                        return (q[fn][1], True)
                    # else doesn't store size: continue
                elif fn in ts:
                    return (ts[fn][1], False)
                # else continue

    def sfc_before_transform (self, transform_fn):
        """Return the value of :attr:`surface` before the given transform.

Takes a transform function as taken by :meth:`transform`, or an index in
:attr:`transforms`.  If it has not been applied/queued yet, the return value is
``None`` (builtin transformations are always applied).  Calling this causes all
queued transformations to be applied.

"""
        self.render()
        # now queue is empty, so is_size will be False
        sfc, is_size = self._sfc_before_transform(transform_fn)
        assert not is_size
        return sfc

    def sz_before_transform (self, transform_fn):
        """Return the value of :attr:`size` before the given transform.

Takes a transform function as taken by :meth:`transform`.  If it has not been
applied/queued yet, the return value is ``None`` (builtin transformations are
always applied).  Unlike :meth:`sfc_before_transform`, calling this does not
apply queued transformations.

"""
        sz, is_size = self._sfc_before_transform(transform_fn)
        if sz is not None and not is_size:
            sz = sz.get_size()
        return sz

    def _undo_transforms (self, transform_fn, include=True):
        """Undo modifiers up to the given transform.

transform_fn may be an index in transforms.

include: whether to undo for the given transform.

"""
        t_ks = self.transforms
        q = self._queued_transforms
        ts = self._transforms
        if isinstance(transform_fn, int):
            i = transform_fn
        else:
            i = t_ks.index(transform_fn)
        if not include:
            i += 1
        for fn in reversed(t_ks[i:]):
            if isinstance(fn, basestring):
                if fn in q:
                    q[fn][4](self)
                elif fn in ts:
                    ts[fn][4](self)
                # else non-applied builtin
            # else non-builtin: nothing to undo

    def _apply_transforms (self, transform_fn, regen, include=True):
        """Apply modifiers from the given transforms.

transform_fn may be an index in transforms.

regen: whether to force regeneration of transform modifiers.
include: whether to apply for the given transform.

"""
        t_ks = self.transforms
        q = self._queued_transforms
        ts = self._transforms
        if isinstance(transform_fn, int):
            i = transform_fn
        else:
            i = t_ks.index(transform_fn)
        if not include:
            i += 1
        src_sz = self.sz_before_transform(i)
        for fn in t_ks[i:]:
            if isinstance(fn, basestring):
                if fn in q:
                    pool = q
                elif fn in ts:
                    pool = ts
                else:
                    # non-applied builtin
                    continue
                args, src, dest, apply_fn, undo_fn = pool[fn]
                if regen:
                    gen_mods = getattr(self, '_gen_mods_' + fn)
                    mods, dest_sz = gen_mods(src_sz, False, args, *args)
                    if mods is not None:
                        apply_fn, undo_fn = mods
                elif pool == q:
                    dest_sz = dest
                else:
                    dest_sz = dest.get_size()
                apply_fn(self)
                # update in transform store
                if pool == q:
                    src = src_sz
                    dest = dest_sz
                pool[fn] = (args, src, dest, apply_fn, undo_fn)
                src_sz = dest_sz
            # else non-builtin: nothing to apply

    def transform (self, transform_fn, *args, **kwargs):
        """Apply a transformation to the graphic.

transform(transform_fn, *args[, position][, before][, after]) -> self

:arg transform_fn: a function to apply a transform, or a string for a builtin
                   transform such as ``'resize'`` (see class documentation).
:arg args: passed to the transformation function as positional arguments, after
           compulsory arguments.
:arg position: the index in :attr:`transforms` to insert this transform at.  If
               not given, the transform is appended to the end if new (not in
               transforms already), else left where it is.
:arg before: if ``position`` is not given, this gives the transform function
             (as in :attr:`transforms`) to insert this transform before.  If
             ``before`` is not in :attr:`transforms`, the transform is put at
             the end.
:arg after: if ``position`` and ``before`` are not given, insert after this
            transform function, or at the end if it doesn't exist.

Builtin transforms should not be moved after rotation (``'rotate'``); behaviour
in this case is undefined.

Calls ``transform_fn(src, dest, dirty, last_args, *args)`` to apply the
transformation, where:

- ``src`` is the surface before this transformation was last applied (or the
  current surface if it never has been).
- ``dest`` is the surface last produced by this transformation, or ``None`` if
  the transform is new.
- ``last_args`` is the ``args`` passed to this method when this transformation
  was last applied, as a tuple (or ``None`` if it never has been).
- ``args`` is as passed to this method.
- ``dirty`` defines what has changed in ``src`` since the last time this
  transform was applied---``True`` if the whole surface has changed, or a list
  of rects, or ``False`` if nothing has changed.  This allows for partial
  transformations by altering ``dest``, if given.

``transform_fn`` should return ``(sfc, dirty)``, where:

- ``sfc`` is the resulting pygame Surface.
- ``dirty`` is a corresponding definition of changed areas in the resulting
  surface - everything that changed since 'last time', which is the result
  after the last time the transform was performed, or the result before the
  transform is performed, if it hasn't been performed before.

``src`` should never be altered, but may be returned as ``sfc`` if the
transform does nothing.  Possible modes of operation are:

- full transform: return ``(new_sfc, True)``.
- partial transform: return ``(dest, new_dirty)`` (``new_dirty`` might also be
  ``False`` here).
- do nothing: return ``(src, dirty)``.

If creating and returning a new surface, it should already be converted for
blitting.

"""
        old_final_size = self._rect.size

        # add to/reorder transforms list, and queue for transforming later
        t_ks = self.transforms
        q = self._queued_transforms
        ts = self._transforms
        exists = True
        try:
            last_index = t_ks.index(transform_fn)
        except ValueError:
            exists = False
        else:
            if transform_fn in q:
                data = q[transform_fn]
            elif transform_fn in ts:
                data = ts[transform_fn]
            else:
                exists = False
            if exists:
                old_data = self.untransform(transform_fn)
                if old_data is not None:
                    ts[transform_fn] = old_data
            if transform_fn in t_ks:
                # has to be a builtin: untransform won't remove it
                t_ks.pop(last_index)
        # determine index
        i = kwargs.get('position')
        if i is None:
            fn = kwargs.get('before')
            if fn is not None:
                try:
                    i = t_ks.index(fn)
                except ValueError:
                    pass
            else:
                fn = kwargs.get('after')
                try:
                    i = t_ks.index(fn) + 1
                except ValueError:
                    pass
        if i is None:
            i = last_index if last_index is not None else len(t_ks)
        # generate modifiers
        builtin = isinstance(transform_fn, basestring)
        if builtin:
            src_sz = self.sz_before_transform(i)
            gen_mods = getattr(self, '_gen_mods_' + transform_fn)
            mods, dest_sz = gen_mods(src_sz, not exists,
                                     data[0] if exists else None, *args)
            if mods is None:
                # retrieve from queue/transforms
                apply_fn = data[3]
                undo_fn = data[4]
            else:
                apply_fn, undo_fn = mods
        else:
            src_sz = dest_sz = apply_fn = undo_fn = None
        # add the transform
        q[transform_fn] = (args, src_sz, dest_sz, apply_fn, undo_fn)
        if i == len(t_ks):
            t_ks.append(transform_fn)
            if builtin:
                # apply modifier
                apply_fn(self)
        else:
            if builtin:
                # undo modifiers up to insertion point
                self._undo_transforms(i)
            t_ks.insert(i, transform_fn)
            if builtin:
                # apply modifier, then reapply following modifiers
                apply_fn(self)
                self._apply_transforms(i, src_sz != dest_sz, False)

        final_size = self._rect.size
        if final_size != old_final_size:
            self._call_cbs('resize', old_final_size, final_size)
        return self

    def retransform (self, transform_fn):
        """Reapply the given transformation (if already applied).

retransform(transform_fn) -> self

:arg transform_fn: a transformation function as taken by :meth:`transform`.

"""
        t_ks = self.transforms
        ts = self._transforms
        q = self._queued_transforms
        if transform_fn in ts:
            if isinstance(transform_fn, basestring):
                # no need to handle mods if not builtin, since then _gen_mods
                # args don't change for any builtins
                self._undo_transforms(transform_fn)
                args, src, dest, apply_fn, undo_fn = ts[transform_fn]
                # queue for full retransform
                if isinstance(transform_fn, basestring):
                    q[transform_fn] = (args, src.get_size(), dest.get_size(),
                                       apply_fn, undo_fn)
                else:
                    q[transform_fn] = (args, None, None, None, None)
                self._apply_transforms(transform_fn,
                                       src.get_size() != dest.get_size())
            # remove last_args to force retransform
            del ts[transform_fn]
        # else nothing to do
        return self

    def untransform (self, transform_fn):
        """Remove an applied transformation.

untransform(transform_fn) -> self

:arg transform_fn: a transformation function as taken by :meth:`transform`.

"""
        t_ks = self.transforms
        ts = self._transforms
        q = self._queued_transforms
        if transform_fn not in ts and transform_fn not in q:
            return
        if isinstance(transform_fn, basestring):
            # don't remove builtins from transforms list
            self._undo_transforms(transform_fn)
            if transform_fn in q:
                src_sz, dest_sz = q[transform_fn][1:3]
            else:
                src, dest = ts[transform_fn][1:3]
                src_sz = src.get_size()
                dest_sz = dest.get_size()
            self._apply_transforms(transform_fn, src_sz != dest_sz, False)
        else:
            # no need to handle mods if not builtin, since then _gen_mods args
            # don't change for any builtins
            t_ks.remove(transform_fn)
        # remove data
        if transform_fn in q:
            del q[transform_fn]
        return ts.pop(transform_fn, None)

    def size_changed (self, size):
        """Tell the graphic that the original size has changed.

:arg size: the new original size to use.

'Original' means before any transforms.  This method is for use by subclasses,
to call when :attr:`orig_sfc` will change, but will not be set until
:meth:`render` is called to avoid unnecessary computations.  The new position
is determined by :attr:`anchor`.

"""
        old_final_size = self._rect.size
        got_transforms = bool(self.transforms)
        if got_transforms:
            self._undo_transforms(0)
        # compute offset due to anchor
        old_size = self.size
        old_ox, old_oy = pos_in_rect(self.anchor, self._rect)
        new_ox, new_oy = pos_in_rect(self.anchor, size)
        x, y = self._rect.topleft
        self._rect = Rect((x + old_ox - new_ox, y + old_oy - new_oy), size)
        if got_transforms:
            self._apply_transforms(0, True)

        self._call_cbs('resize orig', old_size, size)
        final_size = self._rect.size
        if final_size != old_final_size:
            self._call_cbs('resize', old_final_size, final_size)

    def _load_img (self, fn, force_load = False):
        # load image from disk/cache
        resources = self._resource_manager
        if resources is None:
            resources = conf.GAME.resources
        return resources.img(fn, pool = self._resource_pool,
                             force_load = force_load)

    def reload (self):
        """Reload from disk if possible.

If successful, all transformations are reapplied afterwards, if any.

"""
        if self.fn is not None:
            # this calls a setter
            self.orig_sfc = self._load_img(self.fn, True)

    def _gen_mods_resize (self, src_sz, first_time, last_args, w, h,
                          scale=False):
        # mods are size-dependent, so they always change
        ax, ay = pos_in_rect(self.anchor, ((0, 0), src_sz), True)
        ow, oh = src_sz
        if scale:
            w = ir(scale[0] * ow)
            h = ir(scale[1] * oh)
        else:
            if w is None:
                w = ow
            elif w is False:
                w = ir(ow * float(h) / oh)
            if h is None:
                h = oh
            elif h is False:
                h = ir(oh * float(w) / ow)
            scale = (float(w) / ow, float(h) / oh)
        ox = ir((1 - scale[0]) * ax)
        oy = ir((1 - scale[1]) * ay)

        def apply_fn (g):
            g._scale = scale
            x, y = g._rect.topleft
            g._rect = Rect(x + ox, y + oy, w, h)

        def undo_fn (g):
            g._scale = (1, 1)
            x, y = g._rect.topleft
            g._rect = Rect(x - ox, y - oy, ow, oh)

        return ((apply_fn, undo_fn), (w, h))

    def _resize (self, src, dest, dirty, last_args, w, h, scale=False):
        start_w, start_h = src.get_size()

        def parse_args (w, h, scale):
            if scale:
                w = ir(scale[0] * start_w)
                h = ir(scale[1] * start_h)
            else:
                if w is None:
                    w = start_w
                elif w is False:
                    w = ir(start_w * float(h) / start_h)
                if h is None:
                    h = start_h
                elif h is False:
                    h = ir(start_h * float(w) / start_w)
            return (w, h)

        w, h = parse_args(w, h, scale)
        new_dirty = True
        if dirty is not True and last_args is not None:
            if (w, h) == parse_args(*last_args):
                # same as last time
                if dirty:
                    # transform dirty rects
                    scale = (float(w) / start_w, float(h) / start_h)
                    new_dirty = []
                    for r in dirty:
                        new_dirty.append(Rect(*(
                            ir(x * scale[i % 2]) for i, x in enumerate(r)
                        )).inflate(2, 2))
                    # but do full transform
                else:
                    return (dest, False)

        if w == start_w and h == start_h:
            # transform does nothing
            return (src, new_dirty if last_args is None else True)

        # full transform
        return (self.scale_fn(src, (w, h)), new_dirty)

    def resize (self, w=None, h=None, scale=False):
        """Resize the graphic.

resize([w][, h]) -> self

:arg w: the new width.
:arg h: the new height.

No scaling occurs in omitted dimensions.  Also see :attr:`anchor`.

"""
        return self.transform('resize', w, h, scale)

    def rescale (self, w=1, h=1):
        """A convenience wrapper around :meth:`resize` to scale by a ratio.

rescale(w=1, h=1) -> self

:arg w: the new width; ratio of the width before scaling.
:arg h: the new height; ratio of the height before scaling.

"""
        return self.resize(None, None, (w, h))

    def resize_both (self, w=False, h=False):
        """Resize with constant aspect ratio.

resize_both([w][, h]) -> self

:arg w: the new width; pass only one of ``w`` and ``h``.
:arg h: the new height.

"""
        if w is False and h is False:
            raise TypeError('expected only one of w or h')
        return self.resize(w, h)

    def rescale_both (self, scale=1):
        """A convenience wrapper around :meth:`rescale` to scale the same on
both axes.

rescale_both(scale=1) -> self

:arg scale: ratio to scale both width and height by.

"""
        return self.rescale(scale, scale)

    def _gen_mods_crop (self, src_sz, first_time, last_args, rect):
        rect = Rect(rect)
        if first_time or Rect(last_args[0]) != rect:

            def apply_fn (g):
                g._rect = g._rect.move(rect.x, rect.y)
                g._cropped_rect = rect

            def undo_fn (g):
                g._rect = g._rect.move(-rect.x, -rect.y)
                g._cropped_rect = None

            mods = (apply_fn, undo_fn)
        else:
            mods = None
        return (mods, rect.size)

    def _crop (self, src, dest, dirty, last_args, rect):
        start = src.get_rect()
        rect = Rect(rect)
        if dirty is not True and last_args is not None:
            if Rect(last_args[0]) == rect:
                # same size as last time
                if dirty:
                    # clip dirty rects inside cropped rect; if there's a
                    # border, it remains empty as before, so isn't dirtied
                    new_dirty = []
                    offset = (-rect.x, -rect.y)
                    for r in dirty:
                        r = r.clip(rect)
                        if r:
                            s = r.move(offset)
                            new_dirty.append(s)
                            dest.blit(src, s, r)
                    return (dest, new_dirty)
                else:
                    return (dest, False)

        if start == rect:
            # no cropping occurs
            return (src, dirty if last_args is None else True)

        # do a full transform
        if start.contains(rect) and not has_alpha(src):
            new_sfc = pg.Surface(rect.size)
        else:
            # not (no longer) opaque
            new_sfc = blank_sfc(rect.size)
        new_sfc.blit(src, ((0, 0), rect.size), rect)
        return (new_sfc, True)

    def crop (self, rect):
        """Crop the surface to the given rect.

crop(rect) -> self

``rect`` need not be contained in the current surface rect.

"""
        return self.transform('crop', Rect(rect))

    def _gen_mods_flip (self, src_sz, first_time, last_args, x=False, y=False):
        if first_time or last_args != (x, y):

            def apply_fn (g):
                g._flipped = (x, y)

            def undo_fn (g):
                g._flipped = (False, False)

            mods = (apply_fn, undo_fn)
        else:
            mods = None
        return (mods, src_sz)

    def _flip (self, src, dest, dirty, last_args, x=False, y=False):
        if dirty is not True and last_args is not None and last_args == (x, y):
            if dirty:
                # check if a partial transform would be quicker
                w, h = src.get_rect().size
                alpha = has_alpha(src)
                k = 5 if alpha else 3.5
                if k * sum(r[2] * r[3] for r in dirty) ** .75 < w * h ** .75:
                    # it would (this is all empirical and quite rough)
                    new_dirty = []
                    flip = pg.transform.flip
                    for r in dirty:
                        # copy this rect to a new surface
                        sfc = pg.Surface(r.size)
                        if alpha:
                            sfc = sfc.convert_alpha()
                        sfc.blit(src, (0, 0), r)
                        # transform the rect
                        r = Rect((w - r.x - r.w if x else r.x,
                                  h - r.y - r.h if y else r.y), r.size)
                        new_dirty.append(r)
                        # flip and blit to destination
                        dest.blit(flip(sfc, x, y), r)
                    return (dest, new_dirty)
            else:
                return (dest, False)

        if not x and not y:
            # transform does nothing
            return (src, dirty if last_args is None else True)

        # do a full transform
        new_sfc = pg.transform.flip(src, x, y)
        return (new_sfc, True)

    def flip (self, x = False, y = False):
        """Flip the graphic over either axis.

flip(x = False, y = False) -> self

:arg x: whether to flip over the x-axis.
:arg y: whether to flip over the y-axis.

"""
        return self.transform('flip', bool(x), bool(y))

    def _gen_mods_tint (self, src_sz, first_time, last_args, colour):
        colour = normalise_colour(colour)
        if first_time or normalise_colour(last_args[0]) != colour:

            def apply_fn (g):
                g._tint_colour = colour

            def undo_fn (g):
                g._tint_colour = (255, 255, 255, 255)

            mods = (apply_fn, undo_fn)
        else:
            mods = None
        return (mods, src_sz)

    def _tint (self, src, dest, dirty, last_args, colour):
        colour = normalise_colour(colour)
        if (dirty is False and last_args is not None and
            normalise_colour(last_args[0]) == colour):
            return (dest, False)

        if colour == (255, 255, 255, 255):
            # transform does nothing
            return (src, dirty if last_args is None else True)

        # full transform
        if not has_alpha(src):
            src = src.convert_alpha()
        new_sfc = pg.Surface(src.get_size()).convert_alpha()
        new_sfc.fill(colour)
        if colour[3] > 0:
            new_sfc.blit(src, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        return (new_sfc, True)

    def tint (self, colour):
        """Set tint colour, as taken by :func:`engine.util.normalise_colour`.

tint(colour) -> self

This doesn't actually add any colour; it just alters the amount of colour in
each channel.

"""
        return self.transform('tint', colour)

    def opacify (self, opacity):
        """Set opacity, from ``0`` (transparent) to ``255``.

opacify(opacity) -> self

(Sorry about the name---``fade`` would be nice, but conflicts with
:meth:`GraphicsManager.fade() <engine.gfx.container.GraphicsManager.fade>`.)

"""
        return self.transform('tint', self._tint_colour[:3] + (opacity,))

    def _gen_mods_rotate (self, src_sz, first_time, last_args, angle):
        # - dest_sz will never get used: all following transforms are
        #   guaranteed to be non-builtins, if the user does nothing silly
        # - mods are size-dependent, so they always change
        # - computation of rot_offset happens at draw time, since it's only
        #   needed then, and only internally

        def apply_fn (g):
            g._angle = angle
            g._must_apply_rot = True

        def undo_fn (g):
            g._angle = 0
            g._rot_offset = (0, 0)
            g._must_apply_rot = False

        return ((apply_fn, undo_fn), src_sz)

    def _rotate (self, src, dest, dirty, last_args, angle):
        if not dirty and last_args is not None:
            # if last_angle == angle, then surface size didn't change, so
            # neither did the centre point
            if abs(angle - last_args[0]) < self.rotate_threshold:
                # no change to result
                return (dest, False)

        if abs(angle) < self.rotate_threshold:
            # transform does nothing
            return (src, dirty if last_args is None else True)

        # do a full transform
        # if not already alpha and we might end up with borders, convert to
        # alpha
        if angle % (pi / 2) != 0 and not has_alpha(src):
            src = src.convert_alpha()
        new_sfc = self.rotate_fn(src, angle)
        return (new_sfc, True)

    def rotate (self, angle):
        """Rotate the graphic.

rotate(angle) -> self

:arg angle: the angle in radians to rotate to, anti-clockwise from the original
            graphic.

Also see :attr:`rot_anchor`.

"""
        return self.transform('rotate', angle)

    # drawing

    def _opaque_in (self, rect):
        """Whether this draws opaque pixels in the whole of the given rect."""
        return self.opaque and self._postrot_rect.contains(rect)

    def snapshot (self, copy = True):
        """Return a copy of this graphic.

The copy is shallow, which means the new graphic will not appear to be
transformed, even if this one is, but will be an exact copy of the *current
state*.

:arg copy: whether to copy the final surface of this graphic/initial surface of
           the returned graphic.  Since under some circumstances, this graphic
           can modify its final surface, this is often necessary.  However, if
           you do not plan to modify this graphic further and will not alter
           the inital surface (:attr:`orig_sfc`) of the returned graphic, you
           maybe safely pass ``False`` for reduced CPU and memory usage.

"""
        self.render()
        sfc = self._surface.copy() if copy else self._surface
        g = Graphic(sfc, self._postrot_rect.topleft, self._layer,
                    self.blit_flags)
        for attr in ('visible', 'scale_fn', 'rotate_fn', 'rotate_threshold',
                     'anchor', 'rot_anchor'):
            setattr(g, attr, getattr(self, attr))
        return g

    def view (self):
        """Return a 'view' to this graphic.

This is a wrapper around the graphic that allows assigning a different position
and visibility (:attr:`visible`, :attr:`layer`, etc.) without affecting the
original graphic (or any other wrappers).  It is a subclass of this graphic's
class.

Changes to the image represented by either the wrapper or the original graphic
affect both instances.  This includes both transformations and changes to the
original surface.

This may not be used on subclasses that define a ``child`` property.

"""
        parent_cls = type(self)

        class GraphicView (parent_cls):
            is_view = True
            _faked_attrs = ('_rect', 'last_rect', '_postrot_rect',
                            '_last_postrot_rect', '_manager', 'visible',
                            'was_visible', '_layer')

            def __init__ (self, graphic):
                #: The ``graphic`` argument taken by the constructor.
                while graphic.is_view:
                    graphic = graphic.child
                self.child = graphic
                for attr in self._faked_attrs:
                    setattr(self, attr, getattr(graphic, attr))
                self._manager = None

            def __getattr__ (self, attr):
                # existing attributes are returned without a call here
                return getattr(self.child, attr)

            def __setattr__ (self, attr, val):
                # set on this instance if this is an outer attribute or a
                # property, else set on the contained graphic
                if (attr == 'child' or attr in self._faked_attrs or
                    hasattr(type(self.child), attr)):
                    parent_cls.__setattr__(self, attr, val)
                else:
                    setattr(self.child, attr, val)

        return GraphicView(self)

    def dirty (self, *rects):
        """Mark some or all of the graphic as changed.

This is to be used when you alter the original surface (:attr:`orig_sfc`)---do
not alter any other (transformed) surfaces.  Takes any number of rects to flag
as dirty.  If none are given, the whole of the graphic is flagged.

"""
        dirty = [Rect(r) for r in rects] if rects else True
        self._orig_dirty = combine_drawn(self._orig_dirty, dirty)
        self._call_cbs('draw orig')

    def render (self):
        """Update the final surface.

This propagates changes from queued transformations and changes to the original
surface.

"""
        t_ks = self.transforms
        last_t_ks = self._last_transforms
        q = self._queued_transforms
        ts = self._transforms
        self._queued_transforms = {}
        # work out where to start (re)applying transforms from
        dirty = self._orig_dirty
        self._orig_dirty = False
        if dirty:
            i = 0
        elif q:
            i = min(t_ks.index(fn) for fn in q)
            i = min(i, *(last_t_ks.index(fn) for fn in q if fn in last_t_ks))
        else:
            i = len(t_ks)
        # apply transforms
        orig_final_sfc = self._surface
        before_rot = sfc = self._orig_sfc
        passed_rot = False
        for j, fn in enumerate(t_ks):
            if fn != last_t_ks[j]:
                # differ from last transform order at this point
                dirty = True
                i = j
            if not dirty and fn not in q and fn in ts:
                # nothing is different at this point
                # grab surface to start next transform at
                sfc = ts[fn][2]
                if not passed_rot:
                    if fn == 'rotate':
                        passed_rot = True
                    else:
                        before_rot = sfc
            if j < i:
                continue
            if fn in ts:
                # done this transform before
                last_args, src, dest, apply_fn, undo_fn = ts[fn]
            else:
                last_args = dest = None
            if fn in q:
                # got new args
                args, src_sz, dest_sz, apply_fn, undo_fn = q[fn]
            elif last_args is not None:
                # transform with same args
                args = last_args
            else:
                # does nothing
                continue
            f = getattr(self, '_' + fn) if isinstance(fn, basestring) else fn
            new_sfc, dirty = f(sfc, dest, dirty, last_args, *args)
            if dirty or dest is None:
                # transformed for the first time or something changed in
                # retransforming
                # have modifier functions following code above
                ts[fn] = (args, sfc, new_sfc, apply_fn, undo_fn)
            sfc = new_sfc
            if not passed_rot:
                if fn == 'rotate':
                    passed_rot = True
                else:
                    before_rot = sfc
        if len(last_t_ks) > len(t_ks):
            # might have just removed transforms from the end
            dirty = True

        self._last_transforms = list(t_ks)
        if self._must_apply_rot:
            self._must_apply_rot = False
            # compute draw offset due to rotation
            angle = ts['rotate'][0][0]
            w_orig, h_orig = before_rot.get_size()
            w, h = sfc.get_size()
            ax, ay = pos_in_rect(self.rot_anchor, (w_orig, h_orig))
            # v = c - about
            vx = w_orig / 2. - ax
            vy = h_orig / 2. - ay
            # c_new - about_new = v.rotate(angle)
            s = sin(angle)
            c = cos(angle)
            ax_new = w / 2. - (c * vx + s * vy)
            ay_new = h / 2. - (-s * vx + c * vy)
            # about = offset + about_new
            self._rot_offset = (ir(ax - ax_new), ir(ay - ay_new))
        if dirty:
            self._dirty = combine_drawn(self._dirty, dirty)
            # change current surface and rect
            self._surface = sfc
            self.opaque = not has_alpha(sfc)
            self._rect = r = Rect(self._rect.topleft, before_rot.get_size())
            self._postrot_rect = pr = r.move(self._rot_offset)
            pr.size = sfc.get_size()
            if sfc != orig_final_sfc:
                self._call_cbs('change', orig_final_sfc, sfc)
            else:
                self._call_cbs('draw')

    def _pre_draw (self):
        """Called by
:class:`GraphicsManager <engine.gfx.container.GraphicsManager>` before
drawing."""
        self.render()
        dirty = self._dirty
        if self._rect != self.last_rect:
            dirty = True
            self._postrot_rect = Rect(
                self._rect.move(self._rot_offset).topleft,
                self._postrot_rect.size
            )
        if self.blit_flags != self._last_blit_flags:
            dirty = True
            self._last_blit_flags = self.blit_flags
        # fastdraw needs dirty to be a list
        if dirty:
            pr = self._postrot_rect
            if dirty is True:
                dirty = [self._last_postrot_rect, pr]
            else:
                # translate dirty rects
                pr = pr.topleft
                dirty = [d_r.move(pr) for d_r in dirty]
        else:
            dirty = []
        self._dirty = dirty

    def _draw (self, dest, rects):
        """Draw the graphic.

_draw(dest, rects)

dest: pygame.Surface to draw to.
rects: list of rects to draw in.

Should never alter any state that is not internal to the graphic.

"""
        sfc = self._surface
        blit = dest.blit
        pr = self._postrot_rect
        offset = (-pr[0], -pr[1])
        for r in rects:
            blit(sfc, r, r.move(offset), self.blit_flags)
        self._last_postrot_rect = pr
        self.last_rect = self._rect

    def cb (self, cb, *evts):
        """Register a callback for a number of events.

cb(cb, *evts) -> self

:arg cb: callback function; it is called with the event name followed by
         event-specific arguments.  If this callback was already registered,
         the previous set of events specified is overridden.
:arg evts: event names to register the callback for; if none are given, it is
           called for all event types.

Event types:

draw
    The content of :attr:`surface` changed without the surface itself changing.

    Arguments: surface.
draw orig
    The content of :attr:`orig_sfc` changed without the surface itself
    changing.

    Arguments: surface.
change
    :attr:`surface` changed to a different surface.

    Arguments: old surface, new surface.
change orig
    :attr:`orig_sfc` changed to a different surface.

    Arguments: old surface, new surface.
resize
    :attr:`surface` changed to a different surface with a different size.

    Arguments: old size, new size (both ``(width, height)``).
resize orig
    :attr:`orig_sfc` changed to a different surface with a different size.

    Arguments: old size, new size (both ``(width, height)``).

"""
        self.rm_cbs(cb)
        self._cbs[cb] = evts if evts else None
        if not evts:
            evts = (None,)
        all_evts = self._evts
        for evt in evts:
            all_evts.setdefault(evt, set()).add(cb)
        return self

    def rm_cbs (self, *cbs):
        """Remove any number of callbacks registered with events.

rm_cbs(*cbs) -> self

Missing items are ignored.

"""
        all_cbs = self._cbs
        all_evts = self._evts
        for cb in cbs:
            if cb in all_cbs:
                evts = all_cbs[cb]
                del all_cbs[cb]
                if evts is None:
                    evts = (evts,)
                for evt in evts:
                    all_evts[evt].remove(cb)
                    if not all_evts[evt]:
                        del all_evts[evt]
        return self

    def _call_cbs (self, evt, *args):
        """Call callbacks registered for the given event."""
        for cb in self._evts.get(evt, set()).union(
            self._evts.get(None, set())
        ):
            cb(evt, *args)
