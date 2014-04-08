import sys
from platform import system
import os
from os.path import sep, expanduser, join as join_path
from glob import glob

import pygame as pg

from . import settings
from .util import dd


def find_sounds (d):
    # find sounds in the given directory and group by base ID
    sounds = {}
    fns = glob(join_path(d, '*.ogg'))
    base = len(join_path(d, ''))
    for fn in fns:
        if os.path.isfile(fn):
            fn = fn[base:-4]
            for i in xrange(len(fn)):
                if fn[i:].isdigit():
                    # found a valid file
                    ident = fn[:i]
                    if ident:
                        n = sounds.get(ident, 0)
                        sounds[ident] = n + 1
    return sounds


def find_music (d):
    # find files in the given directory and group by subdirectory (nested)
    music = {}
    base = len(join_path(d, ''))
    for subdir, dirs, files in os.walk(d, followlinks=True):
        music[subdir[base:]] = [join_path(subdir, fn) for fn in files]
        # top-level only
        if subdir != d:
            del dirs[:]
    return music


class Conf (object):

    # the Game instance
    GAME = None
    IDENT = 'game'
    DEBUG = False
    FPS = dd(60) # per-world
    DROP_FRAMES = True
    MIN_FPS = dd(25) # per-world
    FPS_AVERAGE_RATIO = .3

    # paths
    # need to take care to get unicode path
    if system() == 'Windows':
        try:
            import ctypes
            n = ctypes.windll.kernel32.GetEnvironmentVariableW(u'APPDATA',
                                                               None, 0)
            if n == 0:
                raise ValueError()
        except Exception:
            # fallback (doesn't get unicode string)
            CONF_DIR = os.environ[u'APPDATA']
        else:
            buf = ctypes.create_unicode_buffer(u'\0' * n)
            ctypes.windll.kernel32.GetEnvironmentVariableW(u'APPDATA', buf, n)
            CONF_DIR = buf.value
        CONF_DIR = join_path(CONF_DIR, IDENT)
    else:
        CONF_DIR = join_path(os.path.expanduser(u'~'), '.config', IDENT)

    CONF = join_path(CONF_DIR, 'conf')
    DATA_DIR = os.path.dirname(sys.argv[0])
    if DATA_DIR:
        DATA_DIR += sep
    EVT_DIR = DATA_DIR + 'evt' + sep
    IMG_DIR = DATA_DIR + 'img' + sep
    SOUND_DIR = DATA_DIR + 'sound' + sep
    MUSIC_DIR = DATA_DIR + 'music' + sep
    FONT_DIR = DATA_DIR + 'font' + sep

    # display
    WINDOW_TITLE = ''
    WINDOW_ICON = None
    MOUSE_VISIBLE = dd(False) # per-world
    FLAGS = 0
    FULLSCREEN = False
    RESIZABLE = False # also determines whether fullscreen togglable
    RES_W = (960, 540)
    RES_F = None
    MIN_RES_W = (320, 180)
    ASPECT_RATIO = None

    # input
    GRAB_EVENTS = dd(False)
    GAME_EVENTS = '''
button _game_quit DOWN
    [ALT] kbd F4

button _game_minimise DOWN
    kbd F10

button _game_fullscreen DOWN
    kbd F11
    [ALT] kbd RETURN
    [ALT] kbd KP_ENTER
'''

    # audio
    VOLUME_SCALING = 2 # 0 is linear
    MUSIC = find_music(MUSIC_DIR)
    MUSIC_AUTOPLAY = dd(False) # False just pauses music; per-world
    MUSIC_VOLUME = dd(.7) # per-world
    EVENT_ENDMUSIC = pg.USEREVENT

    SOUNDS = find_sounds(SOUND_DIR)
    SOUND_VOLUME = dd(.7) # per-world
    SOUND_VOLUMES = dd(1)
    MAX_SOUNDS = {}
    SOUND_ALIASES = {}

    # resources
    DEFAULT_RESOURCE_POOL = 'global'
    # per-world, each {name: renderer}, where renderer is TextRenderer,
    # (font_filename, options) or just font_filename
    TEXT_RENDERERS = dd({})


conf = settings.SettingsManager(Conf, Conf.CONF, filter_caps=True)
