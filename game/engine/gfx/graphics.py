"""Specialised types of graphics.

---NODOC---

TODO:
 - Animation: rework to use Graphic callbacks
 - Tilemap:
    - should change if given Graphics change (tile_types), like Animation
        - graphic.require(tilemap)
        - see Animation.render()
        - note that any graphics passed have their managers removed (and so mustn't be locked)
    - should provide tile setters/getters
    - .update_from from_disk=True should call Graphic.reload() on graphics
    - only prerender tiles as requested
 - tiled graphic
    - graphic form is like Tilemap's tile_graphic
    - takes multiple rects to cover all of them with edges matching up
 - particle system
 - *Grid take (tiled graphic)/(args thereto) instead of just colour for bg

---NODOC---

"""

from os.path import splitext

import pygame as pg
from pygame import Rect

from ..conf import conf
from ..text import option_defaults as text_option_defaults
from .. import util as gameutil
from .graphic import Graphic


class Colour (Graphic):
    """A solid rect of colour.

Colour(colour, rect, layer=0)

:arg colour: a colour to draw, as accepted by
             :func:`engine.util.normalise_colour`.
:arg rect: Pygame-style rect to draw in, or just a ``(width, height)`` size to
           use a rect with position ``(0, 0)``.
:arg layer: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

:meth:`fill` corresponds to a builtin transform.

"""

    _i = Graphic._builtin_transforms.index('crop')
    _builtin_transforms = Graphic._builtin_transforms[:_i] + ('fill',) + \
                          Graphic._builtin_transforms[_i:]

    def __init__ (self, colour, rect, layer=0):
        if len(rect) == 2 and isinstance(rect[0], (int, float)):
            # just got size
            rect = ((0, 0), rect)
        rect = Rect(rect)
        # converts surface and sets opaque to True
        Graphic.__init__(self, pg.Surface(rect.size), rect.topleft, layer)
        self._colour = (0, 0, 0, 255)
        self.fill(colour)

    @property
    def colour (self):
        """As taken by constructor; set as necessary."""
        return self._colour

    @colour.setter
    def colour (self, colour):
        self.fill(colour)

    def _gen_mods_fill (self, src_sz, first_time, last_args, colour):
        colour = gameutil.normalise_colour(colour)
        if first_time or gameutil.normalise_colour(last_args[0]) != colour:

            def apply_fn (g):
                g._colour = colour

            def undo_fn (g):
                g._colour = (0, 0, 0, 255)

            mods = (apply_fn, undo_fn)
        else:
            mods = None
        return (mods, src_sz)

    def _fill (self, src, dest, dirty, last_args, colour):
        colour = gameutil.normalise_colour(colour)
        if colour == (0, 0, 0, 255):
            return (src, dirty)
        if dest is not None and src.get_size() == dest.get_size():
            # we can reuse dest
            last_colour = gameutil.normalise_colour(last_args[0])
            if colour[3] < 255 and not gameutil.has_alpha(dest):
                # newly transparent
                dest = dest.convert_alpha()
            if dirty is True or last_colour != colour:
                # need to refill everything
                dest.fill(colour)
                return (dest, True)
            elif dirty:
                # same colour, some areas changed
                for r in dirty:
                    dest.fill(colour, r)
                return (dest, dirty)
            else:
                # same as last time
                return (dest, False)
        # create new surface and fill
        new_sfc = pg.Surface(src.get_size())
        if colour[3] < 255:
            # non-opaque: need to convert to alpha
            new_sfc = new_sfc.convert_alpha()
        else:
            new_sfc = new_sfc.convert()
        new_sfc.fill(colour)
        return (new_sfc, True)

    def fill (self, colour):
        """Fill with the given colour (like :attr:`colour`)."""
        self.transform('fill', colour)
        self._colour = colour
        return self


class Text (Graphic):
    """Graphic displaying rendered text.

Text(text, renderer, pos=(0, 0), options={}, layer=0)

:arg text: text to render; may contain line breaks to display separate lines.
:arg renderer: :class:`text.TextRenderer <engine.text.TextRenderer>` instance
               or the name a renderer is stored under in
               :attr:`Game.text_renderers <engine.game.Game.text_renderers>`.
:arg pos: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.
:arg options: rendering options to override defaults, as taken by
              :meth:`TextRenderer.render() <engine.text.TextRenderer.render>`.
              All options can be get and set as properties of this instance,
              and all are guaranteed to exist, even if not given in this
              argument.
:arg layer: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

"""

    def __init__ (self, text, renderer, pos=(0, 0), options={}, layer=0):
        self._last_text = self._text = text
        self._renderer = None
        self.renderer = renderer # retrieves from game
        self._last_renderer = self._renderer
        self._options = dict(options)
        # want to always be normalised for better testing for changes
        self.renderer.normalise_options(self._options)
        self._last_options = self._options.copy()
        sfc, lines = self._render_text()
        #: Number of lines of text rendered.
        self.nlines = lines
        Graphic.__init__(self, sfc, pos, layer)

    def _update_rect (self):
        # set size from current text/renderer/options
        size = self._renderer.get_info(self._text, self._options)[2]
        if size != self.orig_sfc.get_size():
            # repositions based on anchor
            self.size_changed(size)

    @property
    def text (self):
        """Text to render (as taken by constructor)."""
        return self._text

    @text.setter
    def text (self, text):
        if text != self._text:
            self._text = text
            self._update_rect()

    @property
    def renderer (self):
        """:class:`text.TextRenderer <engine.text.TextRenderer>` instance to
use."""
        return self._renderer

    @renderer.setter
    def renderer (self, renderer):
        if isinstance(renderer, basestring):
            renderer = conf.GAME.text_renderers[renderer]
        old_renderer = self._renderer
        self._renderer = renderer
        # None if calling from constructor
        if old_renderer is not None and renderer != old_renderer:
            self._update_rect()

    def __getattr__ (self, attr):
        if attr in text_option_defaults:
            if attr in self._options:
                return self._options[attr]
            else:
                return getattr(self._renderer, attr) # guaranteed to exist
        else:
            return object.__getattribute__(self, attr)

    def __setattr__ (self, attr, val):
        if attr in text_option_defaults:
            opts = {attr: val}
            # make sure all stored options are normalised
            self._renderer.normalise_options(opts)
            val = opts[attr]
            if val != self._options.get(attr):
                self._options[attr] = val
                self._update_rect()
        else:
            object.__setattr__(self, attr, val)

    def _render_text (self):
        # actually render text, and return the result
        return self._renderer.render(self._text, self._options)

    def render (self):
        """:inherit:"""
        changed = False
        if self._last_text != self._text:
            changed = True
            self._last_text = self._text
        if self._last_renderer != self._renderer:
            changed = True
            self._last_renderer = self._renderer
        if self._last_options != self._options:
            changed = True
            self._last_options = self._options.copy()
        if changed:
            self.orig_sfc, self.nlines = self._render_text()
        # handles any earlier change to self.rect
        Graphic.render(self)


class Animation (Graphic):
    """An animated graphic.

Animation(imgs, pos=(0, 0), layer=0[, scheduler],
          pool=conf.DEFAULT_RESOURCE_POOL, res_mgr=conf.GAME.resources)

:arg imgs:
    a sequence of images as part of the animation; each can be a Pygame
    surface, a filename to load an surface from, or a
    :class:`Graphic <engine.gfx.graphic.Graphic>` instance (in which case it is
    removed from any
    :class:`GraphicsManager <engine.gfx.container.GraphicsManager>` it is in).
    Note that a :class:`util.Spritemap <engine.gfx.util.Spritemap>` instance is
    a valid form for this argument.
:arg scheduler: :class:`sched.Scheduler <engine.sched.Scheduler>` instance to
                use for timing; if not given, animations can only be played
                when the graphic is contained by a
                :class:`GraphicsManager <engine.gfx.container.GraphicsManager>`
                (and trying to do so otherwise raises ``RuntimeError``).

Other arguments are as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

Note that when an animation is playing and the image changes,
:attr:`Graphic.anchor <engine.gfx.graphic.Graphic.anchor>` is respected.

For example, to play the frames in a spritemap consisting of a single row::

    Animation(Spritemap('map.png', 4)).add('run', frame_time=.1).play('run')

"""
    def __init__ (self, imgs, pos=(0, 0), layer=0, scheduler=None,
                  pool=conf.DEFAULT_RESOURCE_POOL, res_mgr=None):
        self._resource_pool = pool
        self._resource_manager = res_mgr
        if len(imgs) == 0:
            raise ValueError('animation requires at least one image')
        load_img = self._load_img
        gs = []
        #: ``list`` of ``imgs`` as passed to the constructor, except that they
        #: are never filenames.
        self.graphics = gs
        for img in imgs:
            if isinstance(img, basestring):
                img = load_img(img)
            elif isinstance(img, Graphic):
                img.require(self)
            gs.append(img)
        # graphics is non-empty due to the exception above
        self._graphic = 0
        Graphic.__init__(self, self._get_sfc(0), pos, layer, pool, res_mgr)
        #: ``{name: (indices, frame_time)}`` frame sequences ('animations') as
        #: added through :meth:`add`.
        self.sequences = {}
        self._frame_time = None
        self._speed = 1
        #: The ``scheduler`` argument passed to the constructor.
        self.scheduler = scheduler

        #: The currently playing sequence (name), or ``None``.
        self.playing = None
        #: ``list`` of queued sequences to play after the current sequence has
        #: finished, each ``(name, repeat, frame_time, cb)`` as added through
        #: :meth:`queue`, starting with the first to be played.  Items may be
        #: removed manually.
        self.queued = []
        #: The current repeat of the playing sequence, starting from ``0`` if
        #: it hasn't started repeating yet, or ``None``.
        self.repeat = None
        #: The total number of repeats that will be performed for the currently
        #: playing sequence (not including the first playthrough), or ``True``
        #: if it will play forever, or ``None``.
        self.repeats = None
        #: The current frame in the currently playing sequence (within the
        #: current repeat), as an integer starting from ``0``, or ``None``.
        self.frame = None
        self._timer_id = None # scheduler timeout ID
        self._frame_time_source = None # 'default', 'sequence' or 'runtime'
        self._playing_frame_time = None # set when we start playing
        self._new_frame_time = None # set to flag a frame time change
        self._playing_cb = None

    @property
    def graphic (self):
        """The currently visible graphic, as an index in :attr:`graphics`."""
        return self._graphic

    @graphic.setter
    def graphic (self, i):
        i = int(i)
        if i == self._graphic:
            return
        self.orig_sfc = self._get_sfc(i)
        self._graphic = i

    @property
    def frame_time (self):
        """A default for the time between animation frames.

This is a value in seconds, that applies for all animation sequences.  If not
set, a value must be defined for each sequence.  Changes do not take effect
until the current frame has finished, if any is running.

"""
        return self._frame_time

    @frame_time.setter
    def frame_time (self, t):
        self._frame_time = t
        if self._frame_time_source == 'default':
            self._update_timer()

    @property
    def speed (self):
        """Running speed of any animation.

This is a multiplier, where ``1`` is the default speed, and anything higher
decreases frame times.  Changes do not take effect until the current frame has
finished, if any.

"""
        return self._speed

    @speed.setter
    def speed (self, speed):
        if speed <= 0:
            raise ValueError('speed must be positive')
        if speed != self._speed:
            self._speed = speed
            self._update_timer()

    def _get_sfc (self, i):
        # get the surface corresponding to the given index in self.graphics
        sfc = self.graphics[i]
        if isinstance(sfc, Graphic):
            sfc = sfc.surface
        return sfc

    def _get_sched (self):
        s = self.scheduler
        if s is None:
            if self._manager is None:
                raise RuntimeError('no scheduler is available')
            s = self._manager.scheduler
        return s

    def _update_timer (self):
        # update timer speed from data
        if self.playing is None:
            # nothing to do
            return
        if self._frame_time_source == 'default':
            t = self._frame_time
        else:
            # don't change if from sequence/runtime
            t = self._playing_frame_time
        # schedule for application next time we get a callback
        self._new_frame_time = float(t) / self._speed

    def add (self, name, *indices, **kwargs):
        """Add a sequence to :attr:`sequences` to play back later.

add(name, *indices[, frame_time]) -> self

:arg name: the name to give the sequence (any hashable object).  If a sequence
           with this name already exists, it is overwritten; if it is currently
           playing or queued, it is stopped/unqueued.
:arg indices: any number of indices in :attr:`graphics`, defining the sequence
              of frames, or pass none for all frames in order.
:arg frame_time: a default for the time between animation frames in seconds
                 whenever this sequence is played.  If not given, a value must
                 be defined either through the constructor or each time the
                 sequence is played.

"""
        if not indices:
            indices = range(len(self.graphics))
        if not indices:
            raise ValueError('a sequence must contain at least one frame')
        self.unqueue(name)
        if name == self.playing:
            self.stop()
        self.sequences[name] = (indices, kwargs.get('frame_time'))
        return self

    def add_multi (self, sequences):
        """Add a number of frame sequences.

add_multi(sequences) -> self

:arg sequences: ``{name: data}``, where ``data`` can be an ``indices`` ``list``
                or ``(indices[, frame_time])``, and each of these is as taken
                by :meth:`add`.

"""
        add = self.add
        for name, data in sequences.iteritems():
            if (data and (hasattr(data[0], '__len__') and
                          hasattr(data[0], '__getitem__'))):
                # got (indices, ...)
                if len(data) == 1:
                    indices = data[0]
                    frame_time = None
                elif len(data) == 2:
                    indices, frame_time = data
                else:
                    raise TypeError('invalid arguments: {0}'.format(data))
            else:
                # got indices
                indices = data
                frame_time = None
            self.add(name, *indices, frame_time=frame_time)
        return self

    def rm (self, *names):
        """Remove sequences with the given names.

rm(*names) -> self

Missing items are ignored.

"""
        seqs = self.sequences
        for name in names:
            if name in seqs:
                del seqs[name]
        return self

    def _next_frame (self):
        # called through scheduler to move to the next frame
        assert self.playing is not None
        indices = self.sequences[self.playing][0]
        self.frame += 1
        if self.frame == len(indices):
            # reached the end of the sequence
            if self.repeats is not True and self.repeat == self.repeats:
                # no repeats left
                self.playing = self.repeat = self.repeats = self.frame = None
                # no need to reset other attributes, since they're private
                if self._playing_cb is not None:
                    self._playing_cb()
                if self.playing is None and self.queued:
                    self.play(*self.queued.pop())
                return False
            else:
                self.repeat += 1
                self.frame = 0
        self.graphic = indices[self.frame]
        if self._new_frame_time is not None:
            # adjust speed for next frame
            self._timer_id = self._get_sched().add_timeout(
                self._next_frame, self._new_frame_time
            )
            self._new_frame_time = None
            return False
        else:
            return True

    def play (self, name, repeat=True, frame_time=None, cb=None):
        """Play a frame sequence.

play(name, repeat=True[, frame_time][, cb]) -> self

:arg name: sequence name to play.
:arg repeat: whether to repeat the sequence once it has finished.  ``True`` to
             repeat forever, else a number of repeats to perform (that is, the
             sequence is played ``(repeats + 1)`` times).  (``False`` is also
             valid.)
:arg frame_time: the time between animation frames in seconds.  If not given, a
                 value must be defined either as through the constructor or
                 in :meth:`add`.
:arg cb: a function to call when the animation ends (but not if it is stopped
         through :meth:`stop` or by starting another animation).

If a sequence is already being played, that sequence is canceled.

"""
        # cancel current sequence
        s = self._get_sched()
        if self.playing is not None:
            s.rm_timeout(self._timer_id)
        # initialise attributes
        self.playing = name
        self.repeat = 0
        if repeat is False:
            repeat = 0
        self.repeats = repeat
        self.frame = 0
        indices, seq_t = self.sequences[name]
        # show first frame now (sequences are guaranteed to have non-0 length)
        self.graphic = indices[0]
        if frame_time is None:
            if seq_t is None:
                if self._frame_time is None:
                    raise RuntimeError('no frame_time is defined (sequence: '
                                       '\'{0})\''.format(name))
                else:
                    frame_time = self._frame_time
                self._frame_time_source = 'default'
            else:
                frame_time = seq_t
                self._frame_time_source = 'sequence'
        else:
            self._frame_time_source = 'runtime'
        frame_time = float(frame_time) / self._speed
        # start the scheduler
        self._timer_id = s.add_timeout(self._next_frame, frame_time)
        self._playing_frame_time = frame_time
        self._playing_cb = cb
        return self

    def pause (self):
        """Pause the currently running sequence, if any.

pause() -> self

"""
        if self.playing is not None:
            self._get_sched().pause_timeout(self._timer_id)
        return self

    def unpause (self):
        """Unpause the currently running sequence, if paused.

unpause() -> self

"""
        if self.playing is not None:
            self._get_sched().unpause_timeout(self._timer_id)
        return self

    def stop (self, n_queued=0):
        """Stop the currently running sequence, if any.

stop(n_queued) -> self

:arg n_queued: the number of subsequent queued sequences to cancel after
               stopping the running sequence.

"""
        if self.playing:
            self._get_sched().rm_timeout(self._timer_id)
            self.playing = self.repeat = self.repeats = self.frame = None
            # no need to reset other attributes, since they're private
        for i in xrange(n_queued):
            self.queued.pop(0)
        if self.queued:
            self.play(*self.queued.pop())
        return self

    def queue (self, name, repeat=True, frame_time=None, cb=None):
        """Queue a frame sequence for playing after any running sequence.

queue(name, repeat=True[, frame_time][, cb]) -> self

Arguments are as taken by :meth:`play`.

"""
        if self.playing:
            self.queued.append((name, repeat, frame_time, cb))
        else:
            self.play(name, repeat, frame_time, cb)
        return self

    def queue_multi (self, *sequences):
        """Queue multiple frame sequences.

queue_multi(*sequences) -> self

:arg sequences: any number of ``(name, repeat=True[, frame_time][, cb])``
                tuples, where arguments are as taken by :meth:`play`.

"""
        queue = self.queue
        for args in sequences:
            queue(*args)
        return self

    def unqueue (self, *names):
        """Remove frame sequences from the queue by name.

unqueue(*names) -> self

:arg names: any number of sequence names; missing items are ignored.

"""
        queued = self.queued
        for name in names:
            # iterate in reverse to avoid changing indices as we remove items
            for i, data in reversed(list(enumerate(queued))):
                if data[0] == name:
                    queued.pop(i)
        return self

    def render (self):
        """:inherit:"""
        # set orig_dirty where the graphic is dirty, if a graphic
        g = self.graphics[self.graphic]
        if isinstance(g, Graphic):
            sfc = g.surface
            # after render() and before _pre_draw(), ._dirty is relative to
            # top-left = (0, 0)
            if g._dirty:
                orig_sfc = self._orig_sfc
                if sfc is orig_sfc:
                    # same, so need to flag dirty areas
                    if g._dirty is True:
                        self._orig_dirty = True
                    else:
                        self.dirty(*g._dirty)
                else:
                    # different, so change out the surface
                    self.orig_sfc = sfc
                g._dirty = []
        Graphic.render(self)


class Tilemap (Graphic):
    """A finite, flat grid of tiles.

Tilemap(grid, tile_data[, tile_types], pos=(0, 0), layer=0[, translate_type],
        cache_graphic=False, pool=conf.DEFAULT_RESOURCE_POOL,
        res_mgr=conf.GAME.resources)

:arg grid: a :class:`util.Grid <engine.util.Grid>` defining the size and shape
           of the tiles in the tilemap, or the ``tile_size`` argument to
           :class:`util.Grid <engine.util.Grid>` to create a new one with
           standard parameters.
:arg tile_data: a way of determining the tile type ID for each ``(x, y)`` tile
    in the grid, which is any object.  This can be:

        - a list of columns, where each column is a list of IDs;
        - a string with rows delimited by line breaks and each row a
          whitespace-delimited set of string IDs;
        - ``(s, col_delim, row_delim)`` to specify custom delimiter characters
          for a string ``s``, where either or both delimiters can be ``None``
          to split by whitespace/line breaks;
        - a filename from which to load a string with delimited IDs (the name
          may not contain whitespace);
        - ``(filename, col_delim, row_delim)`` for a custom-delimited string in
          a file;
        - a :class:`Graphic <engine.gfx.graphic.Graphic>`, Pygame surface or
          filename (may not contain whitespace) to load an image from, and use
          the ``(r, g, b[, a])`` colour tuples of the pixels in the surface as
          IDs;
        - if ``grid`` is a :class:`util.Grid <engine.util.Grid>`: a function
          that takes ``col`` and ``row`` arguments as column and row indices in
          the grid, and returns the corresponding tile type ID; or
        - if ``grid`` is not a :class:`util.Grid <engine.util.Grid>`:
          ``(get_tile_type, w, h)``, where get_tile_type is a function as
          defined previously, and ``w`` and ``h`` are the width and height of
          the grid, in tiles.

:arg tile_types: a ``tile_type_id -> tile_graphic`` mapping---either a function
    or an object that supports indexing.  If not given, the identity function
    is used.  ``tile_type_id`` is the tile type ID obtained from the
    ``tile_data`` argument.  ``tile_graphic`` determines how the tile should be
    drawn; it may be:

        - ``None`` for an an empty (transparent) tile;
        - a colour (as taken by :func:`engine.util.normalise_colour`) to fill
          with;
        - a :class:`Graphic <engine.gfx.graphic.Graphic>`, Pygame surface or
          filename to load from, to copy aligned to the centre of the tile,
          clipped to fit; or
        - ``(graphic, alignment=0, rect=graphic_rect)`` with ``alignment`` or
          ``rect`` in any order or omitted, and ``graphic`` as in the above
          form.  ``alignment`` is as taken by :func:`engine.util.align_rect`,
          and ``rect`` is the Pygame-style rect within the source surface of
          ``graphic`` to copy from.  Regardless of ``alignment``, ``rect`` is
          clipped to fit in the tile around its centre.

    Note that a :class:`util.Spritemap <engine.gfx.util.Spritemap>` is a valid
    form for this argument.

:arg pos,layer: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.
:arg translate_type: a function that takes tile type IDs obtained from the
                     ``tile_data`` argument and returns the ID to use with the
                     ``tile_types`` argument in obtaining ``tile_graphic``;
                     does nothing by default.
:arg cache_graphic: whether to cache and reuse ``tile_graphic`` for each tile
                    type.  You might want to pass ``True`` if requesting
                    ``tile_graphic`` from ``tile_types`` generates a surface.
                    If ``True``, tile type IDs must be hashable (after
                    translation by ``translate_type``).
:arg pool,res_mgr: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

This is meant to be used for static tilemaps---that is, where the appearance of
each tile type never changes.

"""

    def __init__ (self, grid, tile_data, tile_types=None, pos=(0, 0), layer=0,
                  translate_type=None, cache_graphic=False,
                  pool=conf.DEFAULT_RESOURCE_POOL, res_mgr=None):
        if tile_types is None:
            tile_types = lambda g: g
        elif not callable(tile_types):
            types = tile_types
            tile_types = lambda tile_type_id: types[tile_type_id]
        self._type_to_graphic = tile_types
        if translate_type is None:
            translate_type = lambda tile_type_id: tile_type_id
        self._translate_type = translate_type
        self._cache_graphic = cache_graphic
        self._cache = {}
        # set these before _parse_data, since it calls _load_img which uses
        # them - but can't init Graphic yet because we don't know the size
        self._resource_pool = pool
        self._resource_manager = res_mgr
        self._tile_data, ncols, nrows = self._parse_data(tile_data, grid,
                                                         False)
        if not isinstance(grid, gameutil.Grid):
            grid = gameutil.Grid((ncols, nrows), grid)
        #: The :class:`util.Grid <engine.util.Grid>` covered.
        self.grid = grid
        # apply initial data
        Graphic.__init__(self, gameutil.blank_sfc(grid.size), pos, layer, pool,
                         res_mgr)
        update = self._update
        tile_data = self._tile_data
        for col, row, tile_rect in grid.tile_rects(True):
            update(col, row, tile_data[col][row], tile_rect)

    def _parse_data (self, tile_data, grid, force_load):
        # parse tile data
        if not tile_data:
            return ([], 0, 0)
        if isinstance(tile_data, basestring):
            if (len(tile_data.split()) == 1 and
                splitext(tile_data)[1][1:].lower() in
                ('png', 'jpg', 'jpeg', 'gif')):
                # image file
                tile_data = self._load_img(tile_data, force_load=force_load)
            else:
                # string/text file
                tile_data = (tile_data, None, None)
        if isinstance(tile_data, Graphic):
            tile_data = tile_data.surface
        if isinstance(tile_data, pg.Surface):
            tile_data = [[tuple(c) for c in col]
                         for col in pg.surfarray.array3d(tile_data)]
        if isinstance(tile_data[0], basestring):
            s, col, row = tile_data
            if len(s.split()) == 1:
                with open(s) as f:
                    s = f.read(s)
            if row is None:
                s = s.splitlines()
            else:
                s = s.split(row)
            if col is None:
                tile_data = [l.split() for l in s]
            else:
                tile_data = [l.split(col) for l in s]
            # list of rows -> list of columns
            tile_data = zip(*tile_data)
        if callable(tile_data):
            if not isinstance(grid, gameutil.Grid):
                raise ValueError('got function for tile_data, but grid is ' \
                                 'not a Grid instance')
            tile_data = (tile_data, grid.ncols, grid.nrows)
        if callable(tile_data[0]):
            f, ncols, nrows = tile_data
            tile_data = []
            for i in xrange(ncols):
                col = []
                tile_data.append(col)
                for j in xrange(nrows):
                    col.append(f(i, j))
        # now tile_data is a list of columns
        ncols = len(tile_data)
        nrows = len(tile_data[0])
        if isinstance(grid, gameutil.Grid) and grid.ntiles != (ncols, nrows):
            msg = 'tile_data has invalid dimensions: got {0}, expected {1}'
            raise ValueError(msg.format((ncols, nrows), grid.ntiles))
        translate_type = self._translate_type
        tile_data = [[translate_type(tile_type_id) for tile_type_id in col]
                     for col in tile_data]
        return (tile_data, ncols, nrows)

    def _update (self, col, row, tile_type_id, tile_rect=None):
        if self._cache_graphic:
            if tile_type_id in self._cache:
                g = self._cache[tile_type_id]
            else:
                g = self._type_to_graphic(tile_type_id)
                self._cache[tile_type_id] = g
        else:
            g = self._type_to_graphic(tile_type_id)
        dest = self._orig_sfc
        if tile_rect is None:
            tile_rect = self.grid.tile_rect(col, row)
        if isinstance(g, (Graphic, pg.Surface, basestring)):
            g = (g,)
        if (g is not None and
            isinstance(g[0], (Graphic, pg.Surface, basestring))):
            sfc = g[0]
            if isinstance(sfc, basestring):
                sfc = self._load_img(sfc)
            elif isinstance(sfc, Graphic):
                sfc = sfc.surface
            if len(g) == 1:
                alignment = rect = None
            else:
                if isinstance(g[1], int) or len(g[1]) == 2:
                    alignment = g[1]
                    rect = None
                else:
                    alignment = None
                    rect = g[1]
                if len(g) == 3:
                    if rect is None:
                        rect = g[2]
                    else:
                        alignment = g[2]
            if alignment is None:
                alignment = 0
            if rect is None:
                rect = sfc.get_rect()
            # clip rect to fit in tile_rect
            dest_rect = Rect(rect)
            dest_rect.center = tile_rect.center
            fit = dest_rect.clip(tile_rect)
            rect = Rect(rect)
            rect.move_ip(fit.x - dest_rect.x, fit.y - dest_rect.y)
            rect.size = dest_rect.size
            # copy rect to tile_rect with alignment
            pos = gameutil.align_rect(rect, tile_rect, alignment)
            dest.blit(sfc, pos, rect)
        else:
            if g is None:
                g = (0, 0, 0, 0)
            # now we have a colour
            dest.fill(gameutil.normalise_colour(g), tile_rect)
        return tile_rect

    def __getitem__ (self, i):
        col, row = i
        return self._tile_data[col][row]

    def __setitem__ (self, i, tile_type_id):
        col, row = i
        tile_type_id = self._translate_type(tile_type_id)
        if tile_type_id != self._tile_data[col][row]:
            rect = self._update(col, row, tile_type_id)
            self._tile_data[col][row] = tile_type_id
            self.dirty(rect)

    def update_from (self, tile_data, from_disk=False):
        """Update tiles from a new set of data.

:arg tile_data: as taken by the constructor.
:arg from_disk: whether to force reloading from disk, if passing an image
                filename.

"""
        tile_data = self._parse_data(tile_data, self.grid, from_disk)[0]
        for i, col in enumerate(tile_data):
            for j, tile_type_id in enumerate(col):
                self[(i, j)] = tile_type_id


class Grid (Graphic):
    """Drawable wrapper for :class:`util.Grid <engine.util.Grid>`.

Grid(grid, gap_colour='aaa', bg_colour='0000', pos=(0, 0), layer=0)

:arg grid: a :class:`util.Grid <engine.util.Grid>` instance.
:arg gap_colour: colour in-between tiles, as accepted by
                 :func:`engine.util.normalise_colour`; may have alpha.
:arg bg_colour: colour within tiles, as accepted by
                :func:`engine.util.normalise_colour`.
:arg pos,layer: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

"""

    def __init__ (self, grid, gap_colour='aaa', bg_colour='0000', pos=(0, 0),
                  layer=0):
        gap_colour = gameutil.normalise_colour(gap_colour)
        bg_colour = gameutil.normalise_colour(bg_colour)
        sfc = pg.Surface(grid.size)
        sfc = (sfc.convert_alpha() if gap_colour[3] < 255 or bg_colour[3] < 255
                                   else sfc.convert())
        # fill with gaps and add in tiles
        sfc.fill(gap_colour)
        if bg_colour != gap_colour:
            for rect in grid.tile_rects():
                sfc.fill(bg_colour, rect)
        Graphic.__init__(self, sfc, pos, layer)


class InfiniteGrid (Graphic):
    """Drawable wrapper for
:class:`util.InfiniteGrid <engine.util.InfiniteGrid>`.

InfiniteGrid(grid, rect, gap_colour='aaa', bg_colour='0000', pos=(0, 0),
             layer=0)

:arg grid: a :class:`util.InfiniteGrid<engine.util.InfiniteGrid>` instance.
:arg rect: Pygame-style rect within ``grid`` to draw.
:arg gap_colour: colour in-between tiles, as accepted by
                 :func:`engine.util.normalise_colour`; may have alpha.
:arg bg_colour: colour within tiles, as accepted by
                :func:`engine.util.normalise_colour`.
:arg pos,layer: as taken by :class:`Graphic <engine.gfx.graphic.Graphic>`.

"""

    def __init__ (self, grid, rect, gap_colour='aaa', bg_colour='0000',
                  pos=(0, 0), layer=0):
        #: As passed to the constructor.
        self.grid = grid
        self._view_rect = self._gap_colour = self._bg_colour = None
        rect = Rect(rect)
        Graphic.__init__(self, pg.Surface(rect.size), pos, layer)
        self.gap_colour = gap_colour
        self.bg_colour = bg_colour
        self.view_rect = rect

    def _get_alpha (self):
        # determine whether orig_sfc will have any alpha
        return self._gap_colour[3] < 255 or self._bg_colour[3] < 255

    def _fix_alpha (self, sfc):
        # convert given surface (to be orig_sfc) to alpha if necessary
        if self._get_alpha() and not gameutil.has_alpha(sfc):
            sfc = sfc.convert_alpha()
        return sfc

    def _draw_tiles (self, sfc):
        # draw tiles on the given surface
        ir = gameutil.ir
        c = self._bg_colour
        if c != self._gap_colour:
            offset = (-self._view_rect.x, -self._view_rect.y)
            for r in self.grid.tile_rects(self._view_rect):
                sfc.fill(c, Rect([ir(x) for x in r]).move(offset))

    def _render_grid (self):
        # draw grid to a surface and set as orig_sfc
        size = self._view_rect.size
        if size != self._orig_sfc.get_size():
            sfc = pg.Surface(size)
            if self._get_alpha():
                sfc = sfc.convert_alpha()
        else:
            sfc = self._fix_alpha(self._orig_sfc)
        # draw grid to surface
        sfc.fill(self._gap_colour)
        self._draw_tiles(sfc)
        self.orig_sfc = sfc

    @property
    def view_rect (self):
        """As the ``rect`` argument taken by the constructor.

:attr:`Graphic.anchor <engine.gfx.graphic.Graphic.anchor>` is respected when
this is changed.

"""
        return self._view_rect

    @view_rect.setter
    def view_rect (self, rect):
        rect = Rect(rect)
        if rect != self._view_rect:
            self._view_rect = rect
            self._render_grid()

    @property
    def gap_colour (self):
        """As passed to the constructor."""
        return self._gap_colour

    @gap_colour.setter
    def gap_colour (self, colour):
        colour = gameutil.normalise_colour(colour)
        old_colour = self._gap_colour
        if colour != old_colour:
            self._gap_colour = colour
            if old_colour is not None:
                self._render_grid()
            # else we're still in the constructor

    @property
    def bg_colour (self):
        """As passed to the constructor."""
        return self._bg_colour

    @bg_colour.setter
    def bg_colour (self, colour):
        colour = gameutil.normalise_colour(colour)
        old_colour = self._bg_colour
        if colour != old_colour:
            self._bg_colour = colour
            if old_colour is not None:
                # no need to re-render: just re-fill tiles
                self._draw_tiles(self._fix_alpha(self._orig_sfc))
                self.dirty()
            # else we're still in the constructor
