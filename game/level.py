from math import atan2, pi

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
        self.update_pos()
        x, y = self.pos
        self.set_pos((x, y))
        self.update_pos()
        dx, dy = self.border_offset = (x - self.pos[0], y - self.pos[1])
        # load first level
        self.init()

    def init (self):
        self.dirty = True
        self.resetting = True
        self.balls = []
        data = conf.LEVELS[self.ident]
        # centre level on the screen
        w, h = conf.RES_F
        sx, sy = data['size']
        self.tl = ((w - sx) / 2, (h - sy) / 2)
        self.rect = pg.Rect(0, 0, sx, sy)
        # objects
        sz = conf.GOAL_SIZE
        self.goals = [pg.Rect(pos, sz) for pos in data['goals']]
        self.balls = [Ball(self, pos, vel) for pos, vel in data['balls']]
        if conf.DEBUG and len(self.goals) != len(self.balls):
            print 'warning: {} goals, {} balls'.format(len(self.goals), len(self.balls))
        self.platforms = Rects('platform', data['platforms'])
        self.spikes = Rects('spikes', data['spikes'])
        # indicate to move to start position
        rects = [b.rect for b in self.balls]
        self.reset_rect = rects[0].unionall(rects[1:])

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

    def update_pos (self, pos = None):
        if pos is None:
            x, y = self.tl
            geom = self.x_window.get_geometry()
            pos = (geom.x - x, geom.y - y)
        self.pos = tuple(pos)
        self.win_rect = pg.Rect(pos, conf.RES)

    def resolve_cols (self):
        bs = self.balls
        for b in bs:
            rect = b.rect
            vel = b.vel
            expel = tuple(self.platforms.rects)
            orig_expel = list(expel)
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
            success = True
            if rect.collidelist(orig_expel) != -1 or any(not r.contains(rect) for r in keep_in) or rect.collidelist(self.spikes.rects) != -1:
                self.init()
                success = False
        return success

    def update (self):
        # screen position
        old_pos = self.pos
        old_res = self.win_rect.size
        self.update_pos()
        pos = self.pos
        if old_pos != pos:
            self.dirty = True
        if self.resetting:
            if self.win_rect.contains(self.reset_rect):
                self.resetting = False
        else:
            # ball position
            for b in self.balls:
                b.update()
            res = self.win_rect.size
            if old_pos == pos and old_res == res:
                if not self.resolve_cols():
                    return
            else:
                new_res = conf.RES
                conf.RES = old_res
                # move window one pixel at a time
                move = [pos[0] - old_pos[0], pos[1] - old_pos[1]]
                dirn = [1 if x > 0 else -1 for x in move]
                move = [abs(x) for x in move]
                ratio = None if move[0] == 0 else (float(move[1]) / move[0])
                pos = list(old_pos)
                while move != [0, 0]:
                    r = None if move[0] == 0 else (float(move[1]) / move[0])
                    if r == ratio:
                        axis = move[1] > move[0]
                    else:
                        axis = r is None or r > ratio
                    move[axis] -= 1
                    pos[axis] += dirn[axis]
                    self.update_pos(pos)
                    if not self.resolve_cols():
                        conf.RES = new_res
                        self.update_pos()
                        return
                # resize window one pixel at a time
                move = [res[0] - old_res[0], res[1] - old_res[1]]
                dirn = [1 if x > 0 else -1 for x in move]
                move = [abs(x) for x in move]
                ratio = None if move[0] == 0 else (float(move[1]) / move[0])
                res = list(old_res)
                while move != [0, 0]:
                    r = None if move[0] == 0 else (float(move[1]) / move[0])
                    if r == ratio:
                        axis = move[1] > move[0]
                    else:
                        axis = r is None or r > ratio
                    move[axis] -= 1
                    res[axis] += dirn[axis]
                    conf.RES = res
                    self.update_pos(pos)
                    if not self.resolve_cols():
                        conf.RES = new_res
                        self.update_pos()
                        return
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
            self.dirty = False
            rtn = True
            # background
            screen.fill((0, 0, 0))
            screen.fill((255, 255, 255), self.rect.move(offset))
            # goals
            for r in self.goals:
                screen.fill((255, 150, 0), r.move(offset))
            # spikes
            self.spikes.draw(screen, offset)
            # platforms
            self.platforms.draw(screen, offset)
            if self.resetting:
                w = self.win_rect
                r = self.reset_rect
                if w.colliderect(r):
                    # target rect
                    screen.fill((255, 0, 0), self.reset_rect.move(offset))
                else:
                    # arrow
                    rx, ry = r.center
                    wx, wy = w.center
                    x, y, ww, wh = w
                    dx = rx - wx
                    dy = ry - wy
                    angle = -atan2(dy, dx) * 180 / pi - 90
                    img = pg.transform.rotozoom(self.game.img('arrow.png'), angle, 1)
                    sx, sy = img.get_size()
                    d = dx * dx + dy * dy
                    dx = ir(float(ww - sx) * dx / d ** .5)
                    dy =  ir(float(wh - sy) * dy / d ** .5)
                    pos = ((ww + dx - sx) / 2, (wh + dy - sy) / 2)
                    screen.blit(img, pos)
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
