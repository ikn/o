import Xlib.display
import pygame as pg

from conf import conf
from util import ir

def get_win_frame (root, win):
    while True:
        parent = win.query_tree().parent
        if parent == root:
            break
        win = parent
    return win


class Ball (object):
    def __init__ (self, level, pos):
        self.level = level
        self.last_rect = self.rect = pg.Rect(pos, conf.BALL_SIZE)
        self.vel = conf.BALL_VEL

    def update (self):
        r, v = self.rect, self.vel
        l = pg.Rect(r)
        r[0] += v[0]
        r[1] += v[1]
        #self.rect = rects.collide(r)
        self.last_rect = l

    def draw (self, screen, offset):
        screen.fill((255, 0, 0), self.rect.move(offset))


class Rects (object):
    def __init__ (self, draw_type, *rects):
        self.rects = [pg.Rect(r) for r in rects]
        self.colour = conf.RECT_COLOURS[draw_type]


class Level (object):
    def __init__ (self, game, event_handler, ident = 0):
        self.game = game
        self.ident = ident
        # position
        w_id = pg.display.get_wm_info()['window']
        self.x_display = Xlib.display.Display()
        self.x_root = self.x_display.screen().root
        self.x_window = get_win_frame(self.x_root, self.x_display.create_resource_object('window', w_id))
        # work out and store window border size
        w, h = conf.RES_F
        ww, wh = conf.RES
        x = w / 2 - ww / 2
        y = h / 2 - wh / 2
        self.border_offset = (0, 0)
        self.tl = (0, 0)
        self.set_pos((x, y))
        self.update_pos()
        dx, dy = self.border_offset = (x - self.pos[0], y - self.pos[1])
        # load first level
        self.init()

    def init (self):
        self.dirty = True
        data = conf.LEVELS[self.ident]
        # centre level on the screen
        w, h = conf.RES_F
        sx, sy = data['size']
        self.tl = ((w - sx) / 2, (h - sy) / 2)
        # window position
        pos = data['pos']
        self.set_pos(pos)
        self.update_pos()
        # objects
        self.ball = Ball(self, data['ball'])

    def set_pos (self, pos):
        dx1, dy1 = self.border_offset
        dx2, dy2 = self.tl
        self.x_window.configure(x = pos[0] + dx1 + dx2, y = pos[1] + dy1 + dy2)
        self.x_display.flush()

    def update_pos (self):
        x, y = self.tl
        geom = self.x_window.get_geometry()
        self.pos = (geom.x - x, geom.y - y)

    def update (self):
        old_pos = self.pos
        self.update_pos()
        if old_pos != self.pos:
            self.dirty = True
        self.ball.update()

    def draw (self, screen):
        offset = (-self.pos[0], -self.pos[1])
        b = self.ball
        if self.dirty:
            # background
            self.dirty = False
            screen.fill((255, 255, 255))
            rtn = True
        else:
            # background
            r = b.last_rect.union(b.rect)
            screen.fill((255, 255, 255), r)
            rtn = r
        # ball
        b.draw(screen, offset)
        return rtn
