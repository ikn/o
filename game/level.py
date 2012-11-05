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

def resolve_col (expel, keep_in, rect, vel):
    for i in rect.collidelistall(expel):
        e_x0, e_y0, w, h = expel[i]
        e_x1, e_y1 = e_x0 + w, e_y0 + h
        r_x0, r_y0, w, h = rect
        r_x1, r_y1 = r_x0 + w, r_y0 + h
        x, axis, dirn = min((r_x1 - e_x0, 0, -1), (r_y1 - e_y0, 1, -1),
                            (e_x1 - r_x0, 0, 1), (e_y1 - r_y0, 1, 1))
        rect[axis] += dirn * x
        vel[axis] *= -1
    for r in keep_in:
        if not r.contains(rect):
            k_x0, k_y0, w, h = r
            k_x1, k_y1 = k_x0 + w, k_y0 + h
            r_x0, r_y0, w, h = rect
            r_x1, r_y1 = r_x0 + w, r_y0 + h
            for x, axis, dirn in (
                (r_x1 - k_x1, 0, -1), (r_y1 - k_y1, 1, -1),
                (k_x0 - r_x0, 0, 1), (k_y0 - r_y0, 1, 1)
            ):
                if x > 0:
                    rect[axis] += dirn * x
                    vel[axis] *= -1
    if rect.collidelist(expel) != -1 or any(not r.contains(rect) for r in keep_in):
        print 'die'

class Ball (object):
    def __init__ (self, level, pos):
        self.level = level
        self.last_rect = self.rect = pg.Rect(pos, conf.BALL_SIZE)
        self.vel = list(conf.BALL_VEL)

    def update (self):
        r, v = self.rect, self.vel
        self.last_rect = pg.Rect(r)
        r[0] += v[0]
        r[1] += v[1]
        resolve_col(self.level.platforms.rects, (self.level.rect,), r, v)

    def draw (self, screen, offset):
        screen.fill((255, 0, 0), self.rect.move(offset))


class Rects (object):
    def __init__ (self, draw_type, rects):
        self.rects = [pg.Rect(r) for r in rects]
        self.colour = conf.RECT_COLOURS[draw_type]

    def draw (self, screen, offset):
        c = self.colour
        for r in self.rects:
            screen.fill(c, r.move(offset))


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
        # wait for up to a second for window to move to starting position
        for i in xrange(50):
            if self.pos == pos:
                break
            pg.time.wait(20)
            self.update_pos()
        # objects
        self.ball = Ball(self, data['ball'])
        self.platforms = Rects('platform', data['platforms'])

    def set_pos (self, pos):
        dx1, dy1 = self.border_offset
        dx2, dy2 = self.tl
        self.x_window.configure(x = pos[0] + dx1 + dx2, y = pos[1] + dy1 + dy2)
        self.x_display.flush()

    def update_pos (self):
        x, y = self.tl
        geom = self.x_window.get_geometry()
        self.pos = (geom.x - x, geom.y - y)
        self.rect = pg.Rect(self.pos, conf.RES)

    def update (self):
        # screen position
        old_pos = self.pos
        self.update_pos()
        if old_pos != self.pos:
            self.dirty = True
        # ball position
        self.ball.update()

    def draw (self, screen):
        offset = (-self.pos[0], -self.pos[1])
        b = self.ball
        if self.dirty:
            # background
            self.dirty = False
            screen.fill((255, 255, 255))
            rtn = True
            # rects
            self.platforms.draw(screen, offset)
        else:
            # background
            r = b.last_rect.union(b.rect).move(offset)
            screen.fill((255, 255, 255), r)
            rtn = r
        # ball
        b.draw(screen, offset)
        return rtn
