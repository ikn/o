import os

from .engine import conf


class Conf (object):
    IDENT = 'o'
    WINDOW_TITLE = ''
    #WINDOW_ICON = os.path.join(conf.IMG_DIR, 'icon.png')
    RES_W = (80, 60)
    MIN_RES_W = (40, 40)
    RESIZABLE = True

    # graphics
    BG_COLOUR = (255, 255, 220)
    SOLID_COLOUR = (10, 10, 10)
    RECT_COLOURS = {'platform': SOLID_COLOUR, 'spikes': (170, 40, 40)}
    BALL_COLOUR = (80, 30, 80)
    GOAL_COLOUR = (230, 120, 50)
    START_RECT_COLOUR = (230, 230, 120)
    START_RECT_BORDER_COLOUR = (190, 190, 90)
    START_RECT_BORDER_WIDTH = 1
    LAYERS = {
        'ball': -1,
        'reset rect': 0,
        'goal': 1,
        'rect': 1,
        'bg': 2
    }

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
    }]
