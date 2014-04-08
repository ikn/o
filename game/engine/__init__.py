import pygame as pg

from . import game, sched, evt, gfx, text, util, settings
from .conf import conf

__all__ = ('conf', 'init', 'quit')

pg.mixer.pre_init(buffer = 1024)


def init ():
    """Initialise the game engine."""
    pg.init()
    if conf.WINDOW_ICON is not None:
        pg.display.set_icon(pg.image.load(conf.WINDOW_ICON))
    if conf.WINDOW_TITLE is not None:
        pg.display.set_caption(conf.WINDOW_TITLE)


def quit ():
    """Uninitialise the game engine."""
    pg.quit()
