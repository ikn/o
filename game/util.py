from random import random, randrange
from collections import defaultdict
from bisect import bisect

import pygame as pg


# abstract


def dd (default, items = {}, **kwargs):
    """Create a collections.defaultdict with a static default.

dd(default[, items], **kwargs) -> default_dict

default: the default value.
items: dict or dict-like to initialise with.
kwargs: extra items to initialise with.

default_dict: the created defaultdict.

"""
    items.update(kwargs)
    return defaultdict(lambda: default, items)


def ir (x):
    """Returns the argument rounded to the nearest integer."""
    # this is about twice as fast as int(round(x))
    y = int(x)
    return (y + (x - y >= .5)) if x > 0 else (y - (y - x >= .5))


# random


def randsgn ():
    """Randomly return 1 or -1."""
    return 2 * randrange(2) - 1

def rand0 ():
    """Zero-centred random (-1 <= x < 1)."""
    return 2 * random() - 1


def rand_in (a, b):
    """Return a random number in a continuous range.

rand_in(a, b) -> num

where a <= num < b.

"""
    return a + random() * (b - a)


def weighted_rand (ws):
    """Return a weighted random choice.

weighted_rand(ws) -> index

ws: weightings, either a list of numbers to weight by or a {key: weighting}
    dict for any keys.

index: the chosen index in the list or key in the dict.

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


def position_sfc (sfc, dest, pos = 0, offset = (0, 0), rect = None,
                  dest_rect = None, blit_flags = 0):
    """Blit a surface onto another in a relative manner.

blit_centred(sfc, dest, pos = 0, offset = (0, 0)[, dest_rect], blit_flags = 0)

sfc, dest: blit sfc onto dest.
pos: where to position sfc relative to dest.  This is (x, y) for each axis,
     where for each, a number < 0 is top-/left-aligned, 0 is centred, and > 0
     is bottom-/right-aligned.  If not centred, the given edges of the surfaces
     are made to align.  This argument can also be just a number, to position
     in the same manner on both axes.
offset: an (x, y) amount to offset the blit position by.
rect: the rect within sfc to copy, defaulting to the whole surface.  If given,
      the edges of this rect are used for alignment, as opposed to the edges of
      the whole surface.  This can be larger than sfc.
dest_rect: the rect within dest to align to, instead of the whole surface.
           This only affects alignment, not whether anything is blitted outside
           this rect.  This can be larger than dest.
blit_flags: the special_flags argument taken by pygame.Surface.blit.

"""
    if rect is None:
        rect = sfc.get_rect()
    if isinstance(pos, (int, float)):
        pos = (pos, pos)
    if dest_rect is None:
        dest_rect = dest.get_rect()
    # get blit position
    p = []
    for sfc_w, dest_w, x, o in zip(rect[2:4], dest_rect[2:4], pos, offset):
        if x < 0:
            # top/left
            p.append(o)
        elif x == 0:
            # centre
            p.append((dest_w - sfc_w) / 2 + o)
        else:
            # bottom/right
            p.append(dest_w - sfc_w + o)
    # blit
    dest.blit(sfc, p, rect, blit_flags)


def convert_sfc (sfc):
    """Convert a surface for blitting."""
    if sfc.get_alpha() is None and sfc.get_colorkey() is None:
        sfc = sfc.convert()
    else:
        sfc = sfc.convert_alpha()
    return sfc
