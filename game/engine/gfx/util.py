"""Utilities for graphics."""

import pygame as pg

from ..conf import conf
from .. import util


class Spritemap (object):
    """A wrapper for spritesheets.

Spritemap(img[, ncols][, nrows][, sw][, sh], pad=0[, nsprites],
          pool=conf.DEFAULT_RESOURCE_POOL, res_mgr=conf.GAME.resources)

:arg img: a surface or filename to load from; this is a grid of sprites with
          the same size.
:arg ncols,sw: determines the the number of columns in the spritesheet;
               ``ncols`` is the number of columns and ``sw`` is the width of
               individual sprites, in pixels.  Only one is required, and both
               may be omitted if the spritesheet is a single column.
:arg nrows,sh: determines the the number of rows in the spritesheet; ``nrows``
               is the number of rows and ``sh`` is the height of individual
               sprites.  Only one is required, and both may be omitted if the
               spritesheet is a single row.
:arg pad: padding in pixels between each sprite.  This may be
          ``(col_gap, row_gap)``, or a single number for the same gap in both
          cases.
:arg nsprites: the number of sprites in the spritesheet.  If omitted, this is
               taken to be the maximum number of sprites that could fit on the
               spritesheet; if passed, and smaller than the maximum, the last
               sprites are ignored (see below for ordering).
:arg pool: :class:`ResourceManager <engine.res.ResourceManager>` resource pool
           name to cache any loaded images in.
:arg res_mgr: :class:`ResourceManager <engine.res.ResourceManager>` instance to
              use to load any images.

A spritemap provides ``__len__`` and ``__getitem__`` to obtain sprites, and so
iterating over all sprites is also supported.  Sprites are obtained from top to
bottom, left to right, in that order, and slices are as follows::

    spritemap[sprite_index] -> sfc
    spritemap[col, row] -> sfc

where ``sfc`` is a surface containing the sprite.  (The latter form is an
implicit ``tuple``, so ``spritemap[(col, row)]`` works as well.)

"""

    def __init__ (self, img, ncols=None, nrows=None, sw=None, sh=None, pad=0,
                  nsprites=None, pool=conf.DEFAULT_RESOURCE_POOL,
                  res_mgr=None):
        if isinstance(img, basestring):
            if res_mgr is None:
                res_mgr = conf.GAME.resources
            img = res_mgr.img(img, pool=pool)
        img_sz = img.get_size()
        if isinstance(pad, int):
            pad = (pad, pad)
        if pad[0] < 0 or pad[1] < 0:
            raise ValueError('padding must be positive')
        # get number of columns and rows and sprite size
        ncells = [ncols, nrows]
        ss = [sw, sh]
        for axis in (0, 1):
            n = ncells[axis]
            s_sz = ss[axis]
            i_sz = img_sz[axis]
            p = pad[axis]
            if n is not None:
                if (i_sz + p) % n != 0:
                    raise ValueError(
                        'invalid image size (dimension {0}): expected '
                        '({1}n-{2}), got {3}'.format(axis, n, p, i_sz)
                    )
                ss[axis] = (i_sz + p) // n - p
            elif s_sz is not None:
                if (i_sz + p) % (s_sz + p) != 0:
                    raise ValueError(
                        'invalid image size (dimension {0}): expected '
                        '({1}n-{2}), got {3}'.format(axis, s_sz + p, p, i_sz)
                    )
                ncells[axis] = (i_sz + p) // (s_sz + p)
            else:
                ncells[axis] = 1
                ss[axis] = i_sz
        self._ncells = ncells
        ncols, nrows = ncells
        ncells = ncols * nrows
        if nsprites is None or nsprites > ncells:
            nsprites = ncells
        #: The width of each sprite, in pixels.
        self.sprite_w = ss[0]
        #: The height of each sprite, in pixels.
        self.sprite_h = ss[1]
        #: ``(``:attr:`sprite_w` ``,`` :attr:`sprite_h` ``)``.
        self.sprite_size = tuple(ss)
        # copy to separate surfaces
        self._sfcs = sfcs = []
        tile_rect = util.Grid(ncells, ss, pad).tile_rect
        mk_sfc = util.blank_sfc if util.has_alpha(img) else pg.Surface
        for i in xrange(nsprites):
            rect = tile_rect(i % ncols, i // ncols)
            sfc = mk_sfc(rect.size)
            sfc.blit(img, (0, 0), rect)
            sfcs.append(sfc)

    def __len__ (self):
        return len(self._sfcs)

    def __getitem__ (self, i):
        ncols, nrows = self._ncells
        if not isinstance(i, int):
            col, row = i
            if col < 0:
                col += ncols
            if row < 0:
                row += nrows
            if (col < 0 or col >= ncols or row < 0 or row >= nrows):
                raise IndexError('spritemap index out of bounds')
            i = row * ncols + col
        return self._sfcs[i]
