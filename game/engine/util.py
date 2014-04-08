# coding=utf-8
"""A number of utility functions."""

from random import random, randrange
from collections import defaultdict
from bisect import bisect
import inspect

import pygame as pg
from pygame import Rect

# be sure to change util.rst
__all__ = ('dd', 'takes_args', 'wrap_fn', 'ir', 'sum_pos', 'pos_in_rect',
           'normalise_colour', 'call_in_nest', 'bezier', 'randsgn', 'rand0',
           'weighted_rand', 'align_rect', 'position_sfc', 'convert_sfc',
           'combine_drawn', 'blank_sfc', 'Grid', 'InfiniteGrid')


# abstract


def dd (default, items = {}, **kwargs):
    """Create a ``collections.defaultdict`` with a static default.

dd(default[, items], **kwargs) -> default_dict

:arg default: the default value.
:arg items: dict or dict-like to initialise with.
:arg kwargs: extra items to initialise with.

:return: the created ``defaultdict``.

"""
    items = items.copy()
    items.update(kwargs)
    return defaultdict(lambda: default, items)


def takes_args (func):
    """Determine whether the given function takes any arguments.

:return: ``True`` if the function can take arguments, or if the result could
         not be determined (the argument is not a function, or not a
         pure-Python function), else ``False``.

"""
    try:
        args, varargs, kwargs, defaults = inspect.getargspec(func)
    except TypeError:
        return True
    want = 2 if inspect.ismethod(func) else 1
    return varargs is not None or len(args) >= want


def wrap_fn (func):
    """Return a function that calls ``func``, possibly omitting arguments.

wrap_fn(func) -> wrapper

When ``wrapper`` is called, it calls ``func`` (and returns its return value),
but only passes any arguments on to ``func`` if it is determined that ``func``
takes any arguments (using :func:`takes_args <engine.util.takes_args>`).

"""
    pass_args = takes_args(func)

    def wrapper (*args, **kwargs):
        if pass_args:
            return func(*args, **kwargs)
        else:
            return func()

    return wrapper


def ir (x):
    """Returns the argument rounded to the nearest integer.

This is about twice as fast as int(round(x)).

"""
    y = int(x)
    return (y + (x - y >= .5)) if x > 0 else (y - (y - x >= .5))


def sum_pos (*pos):
    """Sum all given ``(x, y)`` positions component-wise."""
    sx = sy = 0
    for x, y in pos:
        sx +=x
        sy +=y
    return (sx, sy)


def pos_in_rect (pos, rect, round_val=False):
    """Return the position relative to ``rect`` given by ``pos``.

:arg pos: a position identifier.  This can be:

    - ``(x, y)``, where each is either a number relative to ``rect``'s
      top-left, or the name of a property of ``pygame.Rect`` which returns a
      number.
    - a single number ``x`` that is the same as ``(x, x)``.
    - the name of a property of ``pygame.Rect`` which returns an ``(x, y)`` 
      sequence of numbers.

:arg rect: a Pygame-style rect, or just a ``(width, height)`` size to assume a
           rect with top-left ``(0, 0)``.
:arg round_val: whether to round the resulting numbers to integers before
                returning.

:return: the qualified position relative to ``rect``'s top-left, as ``(x, y)``
         numbers.

"""
    if len(rect) == 2 and isinstance(rect[0], (int, float)):
        # got a size
        rect = ((0, 0), rect)
    rect = Rect(rect)
    if isinstance(pos, basestring):
        x, y = getattr(rect, pos)
        x -= rect.left
        y -= rect.top
    elif isinstance(pos, (int, float)):
        x = y = pos
    else:
        x, y = pos
        if isinstance(x, basestring):
            x = getattr(rect, x) - rect.left
        if isinstance(y, basestring):
            y = getattr(rect, y) - rect.top
    return (ir(x), ir(y)) if round_val else (x, y)


def normalise_colour (c):
    """Turn a colour into ``(R, G, B, A)`` format with each number from ``0``
to ``255``.

Accepts 3- or 4-item sequences (if 3, alpha is assumed to be ``255``), or an
integer whose hexadecimal representation is ``0xrrggbbaa``, or a CSS-style
colour in a string (``'#rgb'``, ``'#rrggbb'``, ``'#rgba'``, ``'#rrggbbaa'``
- or without the leading ``'#'``).

"""
    if isinstance(c, int):
        a = c % 256
        c >>= 8
        b = c % 256
        c >>= 8
        g = c % 256
        c >>= 8
        r = c % 256
    elif isinstance(c, basestring):
        if c[0] == '#':
            c = c[1:]
        if len(c) < 6:
            c = list(c)
            if len(c) == 3:
                c.append('f')
            c = [x + x for x in c]
        else:
            if len(c) == 6:
                c = [c[:2], c[2:4], c[4:], 'ff']
            else: # len(c) == 8
                c = [c[:2], c[2:4], c[4:6], c[6:]]
        for i in xrange(4):
            x = 0
            for k, n in zip((16, 1), c[i]):
                n = ord(n)
                x += k * (n - (48 if n < 97 else 87))
            c[i] = x
        r, g, b, a = c
    else:
        r, g, b = c[:3]
        a = 255 if len(c) < 4 else c[3]
    return (r, g, b, a)


def call_in_nest (f, *args):
    """Collapse a number of similar data structures into one.

Used in ``interp_*`` functions.

call_in_nest(f, *args) -> result

:arg f: a function to call with elements of ``args``.
:arg args: each argument is a data structure of nested lists with a similar
           format.

:return: a new structure in the same format as the given arguments with each
         non-list object the result of calling ``f`` with the corresponding
         objects from each arg.

For example::

    >>> f = lambda n, c: str(n) + c
    >>> arg1 = [1, 2, 3, [4, 5], []]
    >>> arg2 = ['a', 'b', 'c', ['d', 'e'], []]
    >>> call_in_nest(f, arg1, arg2)
    ['1a', '2b', '3c', ['4d', '5e'], []]

One argument may have a list where others do not.  In this case, those that do
not have the object in that place passed to ``f`` for each object in the
(possibly further nested) list in the argument that does.  For example::

    >>> call_in_nest(f, [1, 2, [3, 4]], [1, 2, 3], 1)
    [f(1, 1, 1), f(2, 2, 1), [f(3, 3, 1),  f(4, 3, 1)]]

However, in arguments with lists, all lists must be the same length.

"""
    # Rect is a sequence but isn't recognised as collections.Sequence, so test
    # this way
    is_list = [(hasattr(arg, '__len__') and hasattr(arg, '__getitem__') and
                not isinstance(arg, basestring))
               for arg in args]
    if any(is_list):
        n = len(args[is_list.index(True)])
        # listify non-list args (assume all lists are the same length)
        args = (arg if this_is_list else [arg] * n
                for this_is_list, arg in zip(is_list, args))
        return [call_in_nest(f, *inner_args) for inner_args in zip(*args)]
    else:
        return f(*args)


# better for smaller numbers of points
def _bezier_recursive (t, *pts):
    if len(pts) > 3:
        return ((1 - t) * _bezier_recursive(t, *pts[:-1]) +
                t * _bezier_recursive(t, *pts[1:]))
    elif len(pts) == 3:
        a, b, c = pts
        ti = 1 - t
        return ti * ti * a + 2 * t * ti * b + t * t * c
    elif len(pts) == 2:
        return (1 - t) * pts[0] + t * pts[1]
    else:
        return pts[0]


# better for larger numbers of points
def _bezier_flat (t, *pts):
    n_pts = n = len(pts) - 1
    ti = 1 - t
    b = 0
    choose = 1

    # generate terms in pairs
    for i in xrange(n_pts // 2 + 1):
        b += choose * ti ** n * t ** i * pts[i]
        if i != n: # else this is the 'middle' term, which has no pair
            b += choose * ti ** i * t ** n * pts[n]
        choose = choose * n // (i + 1)
        n -= 1
    return b


def bezier (t, *pts):
    """Compute a 1D Bézier curve point.

:arg t: curve parameter.
:arg pts: points defining the curve.

"""
    if len(pts) >= 5: # empirical
        return _bezier_flat(t, *pts)
    elif pts:
        return _bezier_recursive(t, *pts)
    else:
        raise ValueError('expected at least one point')


# random


def randsgn ():
    """Randomly return ``1`` or ``-1``."""
    return 2 * randrange(2) - 1


def rand0 ():
    """Zero-centred random (``-1 <= x < 1``)."""
    return 2 * random() - 1


def weighted_rand (ws):
    """Return a weighted random choice.

weighted_rand(ws) -> index

:arg ws: weightings, either a list of numbers to weight by or a
         ``{key: weighting}`` dict for any keys.

:return: the chosen index in the list or key in the dict.

"""
    if isinstance(ws, dict):
        indices, ws = zip(*ws.iteritems())
    else:
        indices = range(len(ws))
    cumulative = []
    last = 0
    for w in ws:
        last += w
        cumulative.append(last)
    index = min(bisect(cumulative, cumulative[-1] * random()), len(ws) - 1)
    return indices[index]


# graphics


def align_rect (rect, within, alignment = 0, pad = 0, offset = 0):
    """Align a rect within another rect.

align_rect(rect, within, alignment = 0, pad = 0, offset = 0) -> pos

:arg rect: the Pygame-style rect to align.
:arg within: the rect to align ``rect`` within.
:arg alignment: ``(x, y)`` alignment; each is ``< 0`` for left-/top-aligned,
                ``0`` for centred, ``> 0`` for right-/bottom-aligned.  Can be
                just one number to use on both axes.
:arg pad: ``(x, y)`` padding to leave around the inner edge of ``within``.  Can
          be negative to allow positioning outside of ``within``, and can be
          just one number to use on both axes.
:arg offset: ``(x, y)`` amounts to offset by after all other positioning; can
             be just one number to use on both axes.

:return: the position the top-left corner of the rect should be moved to for
         the wanted alignment.

"""
    pos = alignment
    pos = [pos, pos] if isinstance(pos, (int, float)) else list(pos)
    if isinstance(pad, (int, float)):
        pad = (pad, pad)
    if isinstance(offset, (int, float)):
        offset = (offset, offset)
    rect = Rect(rect)
    sz = rect.size
    within = Rect(within)
    within = list(within.inflate(-2 * pad[0], -2 * pad[1]))
    for axis in (0, 1):
        align = pos[axis]
        if align < 0:
            x = 0
        elif align == 0:
            x = (within[2 + axis] - sz[axis]) / 2.
        else: # align > 0
            x = within[2 + axis] - sz[axis]
        pos[axis] = ir(within[axis] + x + offset[axis])
    return pos


def position_sfc (sfc, dest, alignment = 0, pad = 0, offset = 0, rect = None,
                  within = None, blit_flags = 0):
    """Blit a surface onto another with alignment.

position_sfc(sfc, dest, alignment = 0, pad = 0, offset = 0,
             rect = sfc.get_rect(), within = dest.get_rect(), blit_flags = 0)

``alignment``, ``pad``, ``offset``, ``rect`` and ``within`` are as taken by
:func:`align_rect <engine.util.align_rect>`.  Only the portion of ``sfc``
within ``rect`` is copied.

:arg sfc: source surface to copy.
:arg dest: destination surface to blit to.
:arg blit_flags: the ``special_flags`` argument taken by
                 ``pygame.Surface.blit``.

"""
    if rect is None:
        rect = sfc.get_rect()
    if within is None:
        within = dest.get_rect()
    dest.blit(sfc, align_rect(rect, within, alignment, pad, offset), rect,
              blit_flags)


def has_alpha (sfc):
    """Return if the given surface has transparency of any kind."""
    return sfc.get_alpha() is not None or sfc.get_colorkey() is not None


def convert_sfc (sfc):
    """Convert a surface for blitting."""
    return sfc.convert_alpha() if has_alpha(sfc) else sfc.convert()


def combine_drawn (*drawn):
    """Combine the given drawn flags.

These are as returned by :meth:`engine.game.World.draw`.

"""
    if True in drawn:
        return True
    rects = sum((list(d) for d in drawn if d), [])
    return rects if rects else False


def blank_sfc (size):
    """Create a transparent surface with the given ``(width, height)`` size."""
    sfc = pg.Surface(size).convert_alpha()
    sfc.fill((0, 0, 0, 0))
    return sfc


# layouts


class Grid (object):
    """A representation of a 2D grid of rectangular integer-sized tiles.

Used for aligning mouse input, graphics, etc. on a grid.

Grid(ntiles, tile_size, gap = 0)

:arg ntiles: ``(x, y)`` number of tiles in the grid, or a single number for a
             square grid.
:arg tile_size: ``(tile_width, tile_height)`` integers giving the size of every
                tile, or a single number for square tiles.  ``tile_width`` and
                ``tile_height`` can also be functions that take the column/row
                index and return the width/height of that column/row
                respectively, or lists (or anything supporting indexing) that
                perform the same task.
:arg gap: ``(col_gap, row_gap)`` integers giving the gap between columns and
          rows respectively, or a single number for the same gap in both cases.
          As with ``tile_size``, this can be a tuple of functions (or lists)
          which take the index of the preceding column/row and return the gap
          size.

``col`` and ``row`` arguments to all methods may be negative to wrap from the
end of the row/column, like list indices.

"""

    def __init__ (self, ntiles, tile_size, gap = 0):
        if isinstance(ntiles, int):
            ntiles = (ntiles, ntiles)
        else:
            ntiles = tuple(ntiles[:2])
        #: The ``(x, y)`` number of tiles in the grid.
        self.ntiles = ntiles

        def expand (obj, length):
            # expand an int/list/function to the given length
            if isinstance(obj, int):
                return (obj,) * length
            elif callable(obj):
                return tuple(obj(i) for i in xrange(length))
            else:
                return tuple(obj[:length])

        if isinstance(tile_size, int) or callable(tile_size):
            tx = ty = tile_size
        else:
            tx, ty = tile_size
        self._tile_size = (expand(tx, ntiles[0]), expand(ty, ntiles[1]))
        if isinstance(gap, int) or callable(tile_size):
            gx = gy = gap
        else:
            gx, gy = gap
        self._gap = (expand(gx, ntiles[0] - 1), expand(gy, ntiles[1] - 1))

    @property
    def ncols (self):
        """The number of tiles in a row."""
        return self.ntiles[0]

    @property
    def nrows (self):
        """The number of tiles in a column."""
        return self.ntiles[1]

    def _size (self, axis):
        return sum(self._tile_size[axis]) + sum(self._gap[axis])

    @property
    def w (self):
        """The total width of the grid."""
        return self._size(0)

    @property
    def h (self):
        """The total height of the grid."""
        return self._size(1)

    @property
    def size (self):
        """The total ``(width, height)`` size of the grid."""
        return (self.w, self.h)

    def _tile_pos (self, axis, index):
        return sum(ts + gap for ts, gap in zip(self._tile_size[axis][:index],
                                               self._gap[axis][:index]))

    def tile_x (self, col):
        """Get the x position of the tile in the column with the given index.

This is the position of the left side of the tile relative to the left side of
the grid.

"""
        return self._tile_pos(0, col)

    def tile_y (self, row):
        """Get the y position of the tile in the row with the given index.

This is the position of the top side of the tile relative to the top side of
the grid.

"""
        return self._tile_pos(1, row)

    def tile_pos (self, col, row):
        """Get the ``(x, y)`` position of the tile in the given column and row.

This is the top-left corner of the tile relative to the top-left corner of the
grid.

"""
        return (self.tile_x(col), self.tile_y(row))

    def tile_size (self, col, row):
        """Get the ``(width, height)`` size of the given tile."""
        return (self._tile_size[0][col], self._tile_size[1][row])

    def tile_rect (self, col, row):
        """Get a Pygame rect for the tile in the given column and row.

This is relative to the top-left corner of the grid.

"""
        return Rect(self.tile_pos(col, row), self.tile_size(col, row))

    def tile_rects (self, pos=False):
        """Iterator over :meth:`tile_rect <engine.util.Grid.tile_rect>` for all
tiles.

:arg pos: whether to yield ``(col, row, tile_rect)`` instead of just
          ``tile_rect``.

"""
        # FIXME: :meth:`tile_rect` doesn't work in doc
        ts = self._tile_size
        gap = self._gap
        x = 0
        # add extra element to gap so we iterate over the last tile
        for col, (w, gap_x) in enumerate(zip(ts[0], gap[0] + (0,))):
            y = 0
            for row, (h, gap_y) in enumerate(zip(ts[1], gap[1] + (0,))):
                r = Rect(x, y, w, h)
                yield (col, row, r) if pos else r
                y += h + gap_y
            x += w + gap_x

    def tile_at (self, x, y):
        """Return the ``(col, row)`` tile at the point ``(x, y)``, or
``None``."""
        if x < 0 or y < 0:
            return None
        pos = (x, y)
        tile = []
        for axis, pos in enumerate((x, y)):
            current_pos = 0
            ts = self._tile_size[axis]
            gap = self._gap[axis] + (0,)
            for i in xrange(self.ntiles[axis]):
                current_pos += ts[i]
                # now we're at the end of a tile
                if current_pos > pos:
                    # pos is within the previous tile
                    tile.append(i)
                    break
                current_pos += gap[i]
                # now we're at the start of a tile
                if current_pos > pos:
                    # pos is within the previous gap
                    return None
            else:
                # didn't find a tile: point is past the end
                return None
        return tuple(tile)

    def align (self, graphic, col, row, alignment=0, pad=0, offset=0):
        """Align a graphic or surface within a tile.

align(self, graphic, col, row, alignment=0, pad=0, offset=0) -> aligned_rect

``alignment``, ``pad`` and ``offset`` are as taken by
:func:`align_rect <engine.util.align_rect>`.

:arg graphic: a :class:`gfx.Graphic <engine.gfx.graphic.Graphic>` instance or a
              Pygame surface.  In the former case, the graphic is moved (but it
              is not cropped to fit in the tile).
:arg col: column of the tile.
:arg row: row of the tile.

:return: a Pygame rect clipped within the tile giving the area the graphic
         should be put in.

"""
        if isinstance(graphic, Graphic):
            rect = graphic.rect
        else:
            rect = graphic.get_rect()
        pos = align_rect(rect, self.tile_rect(col, row), alignment, pad,
                         offset)
        if isinstance(graphic, Graphic):
            graphic.pos = pos
        return Rect(pos, rect.size)


class InfiniteGrid (object):
    """A representation of an infinite 2D grid of rectangular tiles.

Grid(tile_size, gap=0)

:arg tile_size: ``(tile_width, tile_height)`` numbers giving the size of every
                tile, or a single number for square tiles.
:arg gap: ``(col_gap, row_gap)`` numbers giving the gap between columns and
          rows respectively, or a single number for the same gap in both cases.

The grid expands in all directions, so ``col`` and ``row`` arguments to methods
may be negative, and tile/gap sizes may be floats.

"""

    def __init__ (self, tile_size, gap=0):
        if isinstance(tile_size, (int, float)):
            tile_size = (tile_size, tile_size)
        else:
            tile_size = tuple(tile_size[:2])
        if any(x < 0 for x in tile_size):
            raise ValueError('tile sizes must be positive')
        #: ``tile_size`` as taken by the constructor.
        self.tile_size = tile_size
        if isinstance(gap, (int, float)):
            gap = (gap, gap)
        else:
            gap = tuple(gap[:2])
        if any(g < 0 for g in gap):
            raise ValueError('tile gaps must be positive')
        #: ``gap`` as taken by the constructor.
        self.gap = gap

    def tile_x (self, col):
        """Get the x position of the tile in the column with the given index.

This is the position of the left side of the tile relative to the left side of
column ``0``.

"""
        return (self.tile_size[0] * self.gap[0]) * col

    def tile_y (self, row):
        """Get the y position of the tile in the row with the given index.

This is the position of the top side of the tile relative to the top side of
row ``0``.

"""
        return (self.tile_size[1] * self.gap[1]) * row

    def tile_pos (self, col, row):
        """Get the ``(x, y)`` position of the tile in the given column and row.

This is the top-left corner of the tile relative to the top-left corner of the
tile ``(0, 0)``.

"""
        return (self.tile_x(col), self.tile_y(row))

    def tile_rect (self, col, row):
        """Get a Pygame-style rect for the tile in the given column and row.

This is relative to tile ``(0, 0)``, and elements can be floats.

"""
        return self.tile_pos(col, row) + self.tile_size

    def tile_rects (self, rect, pos=False):
        """Iterator over :meth:`tile_rect <engine.util.InfiniteGrid.tile_rect>`
for tiles that intersect ``rect``.

:arg rect: ``(x, y, w, h)`` with elements possibly floats.
:arg pos: whether to yield ``(col, row, tile_rect)`` instead of just
          ``tile_rect``.

"""
        # FIXME: :meth:`tile_rect` doesn't work in doc
        ts = self.tile_size
        gap = self.gap
        # compute offsets
        x0 = (rect[0] // (ts[0] + gap[0])) * (ts[0] + gap[0])
        y0 = (rect[1] // (ts[1] + gap[1])) * (ts[1] + gap[1])
        # do the loop
        xr = rect[0] + rect[2]
        yb = rect[1] + rect[3]
        x = x0
        col = 0
        while True:
            y = y0
            row = 0
            while True:
                yield (col, row, r) if pos else r
                y += ts[1] + gap[1]
                if y >= yb:
                    break
                row += 1
            x += ts[0] + gap[0]
            if x >= xr:
                break
            col += 1

    def tile_at (self, x, y):
        """Return the ``(col, row)`` tile at the point ``(x, y)``, or
``None``.

Returns ``None`` within gaps between tiles.

"""
        ts = self.tile_size
        gap = self.gap
        pos = (x, y)
        tile = []
        for axis in (0, 1):
            this_tile, offset = divmod(pos[axis], float(ts[axis] + gap[axis]))
            if offset < ts[axis]:
                # in the tile
                tile.append(this_tile)
            else:
                # in the gap
                return None
        return tuple(tile)

    def align (self, graphic, col, row, alignment=0, pad=0, offset=0):
        """Align a graphic or surface within a tile.

align(self, graphic, col, row, alignment=0, pad=0, offset=0) -> aligned_rect

``alignment``, ``pad`` and ``offset`` are as taken by
:func:`align_rect <engine.util.align_rect>`.

:arg graphic: a :class:`gfx.Graphic <engine.gfx.graphic.Graphic>` instance or a
              Pygame surface.  In the former case, the graphic is moved (but it
              is not cropped to fit in the tile).
:arg col: column of the tile.
:arg row: row of the tile.

:return: a Pygame rect clipped within the tile giving the area the graphic
         should be put in.

"""
        if isinstance(graphic, Graphic):
            rect = graphic.rect
        else:
            rect = graphic.get_rect()
        pos = align_rect(rect, self.tile_rect(col, row), alignment, pad,
                         offset)
        if isinstance(graphic, Graphic):
            graphic.pos = pos
        return Rect(pos, rect.size)
