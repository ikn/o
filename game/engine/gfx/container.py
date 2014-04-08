"""Graphics containers: :class:`GraphicsGroup` and :class:`GraphicsManager`.

---NODOC---

TODO:
 - make it possible for GM to have transparent BG (only if orig_sfc has alpha)
 - GraphicsGroup:
    - allow for transforms
    - internal layers (has allowed range in manager, and distributes graphics within it)
 - ignore off-screen (OoB) things (clip all dirty rects and discard zero-size ones)
    - do it before _pre_draw
 - GraphicsManager.offset to offset the viewing window (Surface.scroll is fast?)
    - supports parallax: set to {layer: ratio} or (function(layer) -> ratio) or set a Graphic property (make GraphicView have its own copy)
 - do something with/like dispman

---NODOC---

"""

import sys

import pygame as pg

from .. import sched
from ..util import ir, normalise_colour, blank_sfc, combine_drawn
try:
    from _gm import fastdraw
except ImportError:
    print >> sys.stderr, 'error: couldn\'t import _gm; did you remember to `make\'?'
    sys.exit(1)
from .graphic import Graphic
from .graphics import Colour


class GraphicsGroup (object):
    """Convenience wrapper for grouping a number of graphics in a simple way.

GraphicsGroup(x=0, y=0)

Arguments determine the group's position (:attr:`pos`); unlike for graphics,
this may be floating-point.

This is a ``{graphic: rel}`` mapping, where ``graphic`` is a
:class:`Graphic <engine.gfx.graphic.Graphic>` instance and ``rel`` is the
graphic's ``(x, y)`` position relative to this group.  Adding graphics is
possible with something like ``group[graphic] = rel`` (instead of using
:meth:`add`).

:attr:`graphic_attrs` contains some properties of this :class:`GraphicsGroup` which correspond to those of :class:`Graphic <engine.gfx.graphic.Graphic>`.
These can be set to apply to all contained graphics.

"""

    #: Attributes which are mapped to
    #: :class:`Graphic <engine.gfx.graphic.Graphic>` attributes.
    graphic_attrs = ('layer', 'visible', 'blit_flags', 'anchor', 'rot_anchor',
                     'scale_fn', 'rotate_fn', 'rotate_threshold')

    def __init__ (self, x=0, y=0):
        self._pos = [x, y]
        #: {graphic: rel}
        self._graphics = {}
        self._manager = None

    def __nonzero__ (self):
        return bool(self._graphics)

    def __contains__ (self, graphic):
        return graphic in self._graphics

    def __iter__ (self):
        return iter(self._graphics)

    def __len__ (self):
        return len(self._graphics)

    def __getitem__ (self, graphic):
        return self._graphics[graphic]

    def __setitem__ (self, graphic, rel):
        self.add(graphic, *rel)

    def __delitem__ (self, graphic):
        self.rm(graphic)

    def __setattr__ (self, attr, val):
        if attr in self.graphic_attrs:
            for g in self:
                setattr(g, attr, val)
        else:
            object.__setattr__(self, attr, val)

    @property
    def rect (self):
        """The ``pygame.Rect`` covered by graphics in this group.

The top-left of this is not necessarily the same as :attr:`pos`.

"""
        graphics = self._graphics.keys()
        if graphics:
            if len(graphics) == 1:
                return graphics[0]._rect
            else:
                return graphics[0]._rect.unionall(
                    [g._rect for g in graphics[1:]]
                )
        else:
            return pygame.Rect(0, 0, 0, 0)

    @property
    def x (self):
        """``x`` co-ordinate of the group's top-left corner."""
        return self._pos[0]

    @x.setter
    def x (self, x):
        self.pos = (x, self._pos[1])

    @property
    def y (self):
        """``y`` co-ordinate of the group's top-left corner."""
        return self._pos[1]

    @y.setter
    def y (self, y):
        self.pos = (self._pos[0], y)

    @property
    def pos (self):
        """``[``:attr:`x` ``,`` :attr:`y` ``]``."""
        return self._pos

    @pos.setter
    def pos (self, pos):
        x, y = pos
        self._pos = [x, y]
        # move graphics
        x = ir(x)
        y = ir(y)
        for g, (rel_x, rel_y) in self._graphics.iteritems():
            # rel_{x,y} are ints
            g.pos = (x + rel_x, y + rel_y)

    @property
    def w (self):
        """Width of :attr:`rect`."""
        return self.rect.width

    @property
    def h (self):
        """Height of :attr:`rect`."""
        return self.rect.height

    @property
    def size (self):
        """``(``:attr:`w` ``,`` :attr:`h` ``)``."""
        return self.rect.size

    def move_by (self, dx=0, dy=0):
        """Move by the given number of pixels."""
        self.pos = (self._pos[0] + dx, self._pos[1] + dy)

    def add (self, *graphics):
        """Add graphics.

Call either as ``add(graphic, dx=0, dy=0)`` for a single graphic, or pass any
number of arguments which are ``(graphic, dx=0, dy=0)`` tuples or just
``graphic``.  In each case:

:arg graphic: :class:`Graphic <engine.gfx.graphic.Graphic>` instance or
              the ``img`` argument to
              :class:`Graphic <engine.gfx.graphic.Graphic>` to create one.
:arg dx,dy: position relative to the group.

:return: a list of added :class:`Graphic <engine.gfx.graphic.Graphic>`
         instances (possibly created in this call), in the order given.

If any ``graphic`` is already in the group, this call changes its relative
position (and unspecified ``dx`` and ``dy`` are unchanged, rather than set to
``0``).

Note that graphics need not be added to a :class:`GraphicsManager` individually
---set this using :attr:`manager`.

"""
        if len(graphics) >= 2 and isinstance(graphics[1], (int, float)):
            graphics = (graphics,)
        rtn = []
        for graphic in graphics:
            # parse argument
            if isinstance(graphic, (Graphic, pg.Surface, basestring)):
                graphic = [graphic]
            else:
                graphic = list(graphic)
            if len(graphic) < 2:
                graphic.append(None)
            if len(graphic) < 3:
                graphic.append(None)
            graphic, dx, dy = graphic

            if not isinstance(graphic, Graphic):
                graphic = Graphic(graphic, pos)
            if self._manager is not None:
                self._manager.add(graphic)

            # determine new position for the graphic
            if graphic in self._graphics:
                if dx is None:
                    dx = self._graphics[graphic][0]
                if dy is None:
                    dy = self._graphics[graphic][1]
            else:
                if dx is None:
                    dx = 0
                if dy is None:
                    dy = 0
            rel = (ir(dx), ir(dy))
            pos = (ir(self._pos[0]) + rel[0], ir(self._pos[1]) + rel[1])

            self._graphics[graphic] = rel
            graphic.pos = pos
            rtn.append(graphic)
        return rtn

    def rm (self, *graphics):
        """Remove graphics previously added using :meth:`add`.

Raises ``KeyError`` for missing graphics.

"""
        gm = self._manager
        for g in graphics:
            del self._graphics[g]
            if gm is not None:
                gm.rm(g)

    @property
    def manager (self):
        """The :class:`GraphicsManager <engine.gfx.container.GraphicsManager>`
to put graphics in."""
        return self._manager

    @manager.setter
    def manager (self, manager):
        if manager is self._manager:
            return
        if self._manager is not None:
            self._manager.rm(*self._graphics)
        if manager is not None:
            manager.add(*self._graphics)
        self._manager = manager


class GraphicsManager (Graphic):
    """Draws things to a surface intelligently.

GraphicsManager(scheduler[, sfc], pos=(0, 0), layer=0)

:arg scheduler: a :class:`sched.Scheduler <engine.sched.Scheduler>` instance
                this manager should use for timing.
:arg sfc: the surface to draw to; can be a ``(width, height)`` tuple to create
          a new transparent surface of this size.  If not given or ``None``,
          nothing is drawn.  This becomes :attr:`orig_sfc` and can be changed
          using this attribute.

Other arguments are as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`. 
Since this is a :class:`Graphic <engine.gfx.graphic.Graphic>` subclass, it can
be added to other :class:`GraphicsManager` instances and supports
transformations.  None of this can be done until the manager has a surface,
however, and transformations are only applied in
:attr:`Graphic.surface <engine.gfx.graphic.Graphic.surface>`, not in
:attr:`orig_sfc`.

"""

    def __init__ (self, scheduler, sfc=None, pos=(0, 0), layer=0):
        #: The ``scheduler`` argument passed to the constructor.
        self.scheduler = scheduler
        self._init_as_graphic = False
        self._init_as_graphic_args = (pos, layer)
        self._orig_sfc = None
        self.orig_sfc = sfc # calls setter
        self._gm_dirty = False
        self._overlay = None
        self._fade_id = None
        self.fading = False
        #: ``{layer: graphics}`` dict, where ``graphics`` is a set of the
        #: graphics in layer ``layer``, each as taken by :meth:`add`.
        self.graphics = {}
        #: A list of layers that contain graphics, lowest first.
        self.layers = []

    @property
    def orig_sfc (self):
        """Like :attr:`Graphic.orig_sfc <engine.gfx.graphic.Graphic.orig_sfc>`.

This is the ``sfc`` argument passed to the constructor.  Retrieving this causes
all graphics to be drawn/updated first.

"""
        self.draw()
        return Graphic.orig_sfc.fget(self)

    @orig_sfc.setter
    def orig_sfc (self, sfc):
        if sfc is not None and not isinstance(sfc, pg.Surface):
            sfc = blank_sfc(sfc)
        if sfc is not self._orig_sfc:
            self._orig_sfc = sfc
            if sfc is not None:
                if self._init_as_graphic:
                    Graphic.orig_sfc.fset(self, sfc)
                else:
                    Graphic.__init__(self, sfc, *self._init_as_graphic_args)
                    self._init_as_graphic = True
                    del self._init_as_graphic_args

    @property
    def orig_size (self):
        """The size of the surface before any transforms."""
        return self._orig_sfc.get_size()

    @property
    def overlay (self):
        """A :class:`Graphic <engine.gfx.graphic.Graphic>` which is always
drawn on top, or ``None``.

There may only ever be one overlay; changing this attribute removes any
previous overlay from the :class:`GraphicsManager`.

"""
        return self._overlay

    @overlay.setter
    def overlay (self, overlay):
        # remove any previous overlay
        if self._overlay is not None:
            self.rm(self._overlay)
        # set now since used in add()
        self._overlay = overlay
        if overlay is not None:
            # remove any current manager
            overlay.manager = None
            # put in the reserved layer None (sorts less than any other object)
            overlay._layer = None
            # add to this manager
            self.add(overlay)

    def _set_layers_from_set (self, ls):
        if None in ls:
            ls.remove(None)
            self.layers = [None] + sorted(ls)
        else:
            self.layers = sorted(ls)

    def add (self, *graphics):
        """Add graphics.

Takes any number of :class:`Graphic <engine.gfx.graphic.Graphic>` instances,
and returns a list of added graphics.

"""
        all_gs = self.graphics
        ls = set(self.layers)
        for g in graphics:
            l = g.layer
            if l is None and g is not self._overlay:
                raise ValueError('a graphic\'s layer must not be None')
            if l in ls:
                all_gs[l].add(g)
            else:
                all_gs[l] = set((g,))
                ls.add(l)
            g._manager = self
            # don't draw over any possible previous location
            g.was_visible = False
        self._set_layers_from_set(ls)
        return graphics

    def rm (self, *graphics):
        """Remove graphics.

Takes any number of :class:`Graphic <engine.gfx.graphic.Graphic>` instances.
Missing graphics are ignored.

"""
        all_graphics = self.graphics
        ls = set(self.layers)
        for g in graphics:
            l = g.layer
            if l in ls:
                all_gs = all_graphics[l]
                if g in all_gs:
                    # remove from graphics
                    all_gs.remove(g)
                    g._manager = None
                    # draw over previous location
                    if g.was_visible:
                        self.dirty(g._last_postrot_rect)
                    # remove layer
                    if not all_gs:
                        del all_graphics[l]
                        ls.remove(l)
            # else not added: fail silently
        self._set_layers_from_set(ls)

    def fade_to (self, t, colour=(0, 0, 0), resolution = None):
        """Fade to a colour.

fade_to(t, colour=(0, 0, 0)[, resolution])

:arg t: how many seconds to take to reach ``colour``.
:arg colour: the ``(R, G, B[, A = 255])`` colour to fade to.
:arg resolution: as taken by
                 :meth:`Scheduler.interp() <engine.sched.Scheduler.interp>`.

If already fading, the current colour is used as the initial colour; otherwise,
the initial colour is taken to be ``(R, G, B, 0)`` for the given value of
``colour``.  After fading, the overlay persists; set :attr:`overlay` to
``None`` to remove it.

"""
        colour = normalise_colour(colour)
        if self._fade_id is None:
            # doesn't already exist
            initial_colour = colour[:3] + (0,)
        else:
            initial_colour = self._overlay.colour
        self.fade(sched.interp_linear(initial_colour, (colour, t)),
                  round_val = True, resolution = resolution)

    def fade_from (self, t, colour=None, resolution = None):
        """Fade from a colour to no overlay.

fade_from(t[, colour][, resolution])

:arg t: how many seconds to take to reach transparency.
:arg colour: the ``(R, G, B[, A = 255])`` colour to fade from; if not given,
             the current colour is used, else ``(0, 0, 0)``.
:arg resolution: as taken by
                 :meth:`Scheduler.interp() <engine.sched.Scheduler.interp>`.

Any running fade is canceled, and the final colour is taken to be
``(R, G, B, 0)`` for the given value of ``colour``.  After fading, the overlay
is removed.

"""
        if colour is None:
            if self._fade_id is None:
                # doesn't already exist
                colour = (0, 0, 0)
            else:
                colour = self._overlay.colour
        colour = normalise_colour(colour)
        final_colour = colour[:3] + (0,)

        def end ():
            self.cancel_fade()

        self.fade(sched.interp_linear(colour, (final_colour, t)), end=end,
                  round_val=True, resolution=resolution)

    def fade (self, get_val, *args, **kw):
        """Fade between colours.

Takes arguments like
:meth:`Scheduler.interp() <engine.sched.Scheduler.interp>`, with ``set_val``
omitted.

Any currently running fade will be canceled.  After fading, the overlay
persists; set :attr:`overlay` to ``None`` to remove it.

"""
        if self._fade_id is not None:
            # already fading
            self.cancel_fade()
        # set colour to initial colour
        val = get_val(0)
        if val is None:
            # interpolation already ended
            return
        self.overlay = Colour(val, self.orig_size)
        self._fade_id = self.scheduler.interp(
            get_val, (self._overlay, 'colour'), *args, **kw
        )
        self.fading = True

    def cancel_fade (self):
        """Cancel any currently running fade and remove the overlay."""
        if self._fade_id is not None:
            self.scheduler.rm_timeout(self._fade_id)
            self._fade_id = None
            self.fading = False
            self.overlay = None

    def dirty (self, *rects):
        """:inherit:"""
        if self._surface is None:
            # nothing to mark as dirty
            return
        if not rects:
            rects = True
        self._gm_dirty = combine_drawn(self._gm_dirty, rects)

    def draw (self, handle_dirty = True):
        """Update the display (:attr:`orig_sfc`).

:arg handle_dirty: whether to propagate changed areas to the transformation
                   pipeline implemented by
                   :class:`Graphic <engine.gfx.graphic.Graphic>`.  Pass
                   ``False`` if you don't intend to use this manager as a
                   graphic.

Returns ``True`` if the entire surface changed, or a list of rects that cover
changed parts of the surface, or ``False`` if nothing changed.

"""
        layers = self.layers
        sfc = self._orig_sfc
        if not layers or sfc is None:
            return False
        graphics = self.graphics
        dirty = self._gm_dirty
        self._gm_dirty = []
        if dirty is True:
            dirty = [sfc.get_rect()]
        elif dirty is False:
            dirty = []
        dirty = fastdraw(layers, sfc, graphics, dirty)
        if dirty and handle_dirty:
            Graphic.dirty(self, *dirty)
        if self._orig_dirty:
            dirty = combine_drawn(dirty, self._orig_dirty)
            if not handle_dirty:
                self._orig_dirty = False
        return dirty

    def render (self):
        """:inherit:"""
        self.draw()
        Graphic.render(self)
