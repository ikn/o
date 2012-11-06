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
    def __init__ (self, level, pos, vel):
        self.level = level
        self.last_rect = self.rect = pg.Rect(pos, conf.BALL_SIZE)
        self.vel = list(vel)

    def update (self):
        r, v = self.rect, self.vel
        self.last_rect = pg.Rect(r)
        r[0] += v[0]
        r[1] += v[1]

    def draw (self, screen, offset):
        screen.fill((0, 0, 255), self.rect.move(offset))


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
        self.rect = pg.Rect(0, 0, sx, sy)
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
        sz = conf.GOAL_SIZE
        self.goals = [pg.Rect(pos, sz) for pos in data['goals']]
        self.balls = [Ball(self, pos, vel) for pos, vel in data['balls']]
        if conf.DEBUG and len(self.goals) != len(self.balls):
            print 'warning: {} goals, {} balls'.format(len(self.goals), len(self.balls))
        self.platforms = Rects('platform', data['platforms'])

    def reset (self):
        # TODO: add arrow pointing towards starting position and smallest rect
        # containing balls in red, then call init once window contains this
        # rect
        pass

    def progress (self):
        self.ident += 1
        if self.ident >= len(conf.LEVELS):
            self.game.quit_backend()
        else:
            self.init()

    def set_pos (self, pos):
        dx1, dy1 = self.border_offset
        dx2, dy2 = self.tl
        self.x_window.configure(x = pos[0] + dx1 + dx2, y = pos[1] + dy1 + dy2)
        self.x_display.flush()

    def update_pos (self):
        x, y = self.tl
        geom = self.x_window.get_geometry()
        self.pos = (geom.x - x, geom.y - y)
        self.win_rect = pg.Rect(self.pos, conf.RES)

    def resolve_cols (self):
        bs = self.balls
        for b in bs:
            rect = b.rect
            vel = b.vel
            expel = tuple(self.platforms.rects)
            expel_types = [None] * len(expel)
            b_data = [(this_b, this_b.rect) for this_b in bs if this_b is not b]
            if b_data:
                b_types, b_rects = zip(*b_data)
                expel_types += b_types
                expel += b_rects
            for i in rect.collidelistall(expel):
                e_x0, e_y0, w, h = expel[i]
                e_x1, e_y1 = e_x0 + w, e_y0 + h
                r_x0, r_y0, w, h = rect
                r_x1, r_y1 = r_x0 + w, r_y0 + h
                x, axis, dirn = min((r_x1 - e_x0, 0, -1), (r_y1 - e_y0, 1, -1),
                                    (e_x1 - r_x0, 0, 1), (e_y1 - r_y0, 1, 1))
                rect[axis] += dirn * x
                vel[axis] *= -1
                other_b = expel_types[i]
                if other_b is not None:
                    other_b.vel[axis] *= -1
            keep_in = (self.win_rect, self.rect)
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
                self.reset()

    def update (self):
        # screen position
        old_pos = self.pos
        self.update_pos()
        if old_pos != self.pos:
            self.dirty = True
        # ball position
        for b in self.balls:
            b.update()
        self.resolve_cols()
        # win condition
        for b in self.balls:
            col = b.rect.collidelistall(self.goals)
            if col:
                self.goals.pop(col.pop(0))
                self.balls.remove(b)
                self.dirty = True
                if not self.goals:
                    self.progress()

    def draw (self, screen):
        offset = (-self.pos[0], -self.pos[1])
        if self.dirty:
            # background
            self.dirty = False
            screen.fill((0, 0, 0))
            screen.fill((255, 255, 255), self.rect.move(offset))
            rtn = True
            # goals
            for r in self.goals:
                screen.fill((255, 150, 0), r.move(offset))
            # rects
            self.platforms.draw(screen, offset)
        else:
            # background
            rtn = []
            for b in self.balls:
                r = b.last_rect.union(b.rect).move(offset)
                screen.fill((255, 255, 255), r)
                rtn.append(r)
        # balls
        for b in self.balls:
            b.draw(screen, offset)
        return rtn
