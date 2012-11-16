from platform import system
import os
from os.path import sep, expanduser, join as join_path
from collections import defaultdict
from glob import glob

import pygame as pg

import settings
from util import dd


class Conf (object):

    IDENT = 'o'
    USE_SAVEDATA = False
    USE_FONTS = False

    # save data
    SAVE = ()
    # need to take care to get unicode path
    if system() == 'Windows':
        try:
            import ctypes
            n = ctypes.windll.kernel32.GetEnvironmentVariableW(u'APPDATA', None, 0)
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

    # data paths
    DATA_DIR = ''
    IMG_DIR = DATA_DIR + 'img' + sep
    SOUND_DIR = DATA_DIR + 'sound' + sep
    MUSIC_DIR = DATA_DIR + 'music' + sep
    FONT_DIR = DATA_DIR + 'font' + sep

    # display
    WINDOW_ICON = None #IMG_DIR + 'icon.png'
    WINDOW_TITLE = 'o'
    MOUSE_VISIBLE = dd(True) # per-backend
    FLAGS = 0
    FULLSCREEN = False
    RESIZABLE = True # also determines whether fullscreen togglable
    RES_W = (80, 60)
    RES_F = pg.display.list_modes()[0]
    RES = RES_W
    MIN_RES_W = (40, 40)
    ASPECT_RATIO = None

    # timing
    FPS = dd(60) # per-backend

    # debug
    DEBUG = False
    PROFILE_STATS_FILE = '.profile_stats'
    DEFAULT_PROFILE_TIME = 5

    # input
    KEYS_NEXT = (pg.K_RETURN, pg.K_SPACE, pg.K_KP_ENTER)
    KEYS_BACK = (pg.K_ESCAPE, pg.K_BACKSPACE)
    KEYS_MINIMISE = (pg.K_F10,)
    KEYS_FULLSCREEN = (pg.K_F11, (pg.K_RETURN, pg.KMOD_ALT, True),
                    (pg.K_KP_ENTER, pg.KMOD_ALT, True))
    KEYS_LEFT = (pg.K_LEFT, pg.K_a, pg.K_q)
    KEYS_RIGHT = (pg.K_RIGHT, pg.K_d, pg.K_e)
    KEYS_UP = (pg.K_UP, pg.K_w, pg.K_z, pg.K_COMMA)
    KEYS_DOWN = (pg.K_DOWN, pg.K_s, pg.K_o)
    KEYS_DIRN = (KEYS_LEFT, KEYS_UP, KEYS_RIGHT, KEYS_DOWN)

    # audio
    MUSIC_AUTOPLAY = False # just pauses music
    MUSIC_VOLUME = dd(.5) # per-backend
    SOUND_VOLUME = .5
    EVENT_ENDMUSIC = pg.USEREVENT
    SOUND_VOLUMES = dd(1)
    # generate SOUNDS = {ID: num_sounds}
    SOUNDS = {}
    ss = glob(join_path(SOUND_DIR, '*.ogg'))
    base = len(join_path(SOUND_DIR, ''))
    for fn in ss:
        fn = fn[base:-4]
        for i in xrange(len(fn)):
            if fn[i:].isdigit():
                # found a valid file
                ident = fn[:i]
                if ident:
                    n = SOUNDS.get(ident, 0)
                    SOUNDS[ident] = n + 1

    # text rendering
    # per-backend, each a {key: value} dict to update fonthandler.Fonts with
    REQUIRED_FONTS = dd({})

    # graphics
    BG_COLOUR = (255, 255, 220)
    SOLID_COLOUR = (10, 10, 10)
    RECT_COLOURS = {'platform': SOLID_COLOUR, 'spikes': (170, 40, 40)}
    BALL_COLOUR = (80, 30, 80)
    GOAL_COLOUR = (230, 120, 50)
    START_RECT_COLOUR = (230, 230, 120)
    START_RECT_BORDER_COLOUR = (190, 190, 90)
    START_RECT_BORDER_WIDTH = 1

    # gameplay
    BALL_SIZE = (8, 8)
    BALL_SQUISH = .5
    BALL_ELAST = .85
    BALL_STIFFNESS = .1
    MAX_SQUISH = 2
    GOAL_SIZE = (16, 16)

    # levels
    # pos: of screen top-left
    # balls: each is (pos, vel)
    LEVELS = [{
        'size': (300, 300),
        'goals': [(250, 167)],
        'balls': [((20, 20), (1, -1))],
        'platforms': [
            (50, 0, 150, 150), (50, 200, 150, 100), (200, 0, 100, 100),
            (200, 250, 100, 50)
        ], 'spikes': []
    }, {
        'size': (300, 300),
        'goals': [(250, 167)],
        'balls': [((20, 20), (1, -1))],
        'platforms': [
            (50, 0, 150, 150), (50, 200, 150, 100), (200, 0, 100, 100),
            (200, 250, 100, 50)
        ], 'spikes': [(50, 150, 150, 5)]
    }, {
        'size': (500, 330),
        'goals': [(450, 182)],
        'balls': [((20, 20), (1, -1))],
        'platforms': [
            (50, 0, 300, 150), (50, 230, 300, 100), (350, 0, 150, 100),
            (350, 280, 150, 50)
        ], 'spikes': [
            (50, 150, 100, 5), (150, 225, 100, 5), (250, 150, 100, 5)
        ]
    }, {
        'size': (600, 155),
        'goals': [(310, 69)],
        'balls': [((30, 20), (-1, 0))],
        'platforms': [
            (60, 0, 30, 70), (60, 85, 30, 70), (140, 30, 25, 95),
            (225, 0, 25, 70), (225, 85, 25, 70), (305, 50, 25, 15),
            (305, 90, 25, 15), (335, 50, 215, 20), (335, 85, 215, 20)
        ], 'spikes': [
            (165, 30, 5, 25), (165, 100, 5, 25), (220, 0, 5, 70),
            (220, 85, 5, 70), (300, 50, 5, 55), (595, 0, 5, 155)
        ]
    }, {
        'size': (400, 400),
        'goals': [(30, 120), (250, 60)],
        'balls': [((140, 50), (1, -1)), ((192, 50), (-1, 1))],
        'platforms': [
            (160, 0, 20, 290), (160, 290, 150, 20)
        ], 'spikes': []
    }, {
        'size': (400, 300),
        'goals': [(30, 250), (354, 250)],
        'balls': [((170, 50), (-1, -1)), ((222, 50), (-1, 1))],
        'platforms': [
            (190, 0, 20, 300), (50, 140, 140, 15), (210, 140, 140, 15)
        ], 'spikes': [(50, 155, 140, 5), (210, 155, 140, 5)]
    }
    # TODO: have to make window small to avoid spikes?
    ]


def translate_dd (d):
    if isinstance(d, defaultdict):
        return defaultdict(d.default_factory, d)
    else:
        # should be (default, dict)
        return dd(*d)
conf = dict((k, v) for k, v in Conf.__dict__.iteritems()
            if k.isupper() and not k.startswith('__'))
types = {
    defaultdict: translate_dd
}
if Conf.USE_SAVEDATA:
    conf = settings.SettingsManager(conf, Conf.CONF, Conf.SAVE, types)
else:
    conf = settings.DummySettingsManager(conf, types)
