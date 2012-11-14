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
        self.rect = self.last_rect = self.orig_rect = pg.Rect(pos, conf.BALL_SIZE)
        self.vel = list(vel)
        self.squish_vel = [0] * 4
        self.squish = [0] * 4

    def push (self, axis, dirn, other_ball):
        v = self.vel
        self.squish_vel[axis + dirn + 1] += conf.BALL_SQUISH
        if v[axis] and (v[axis] > 0) == (dirn == -1):
            self.level.game.play_snd('bounce')
        v[axis] = dirn * abs(v[axis])

    def move (self, axis, x):
        self.orig_rect[axis] += x
        self.rect[axis] += x

    def update (self):
        # move
        r, v = self.orig_rect, self.vel
        r[0] += v[0]
        r[1] += v[1]
        # squish
        s = self.squish
        sv = self.squish_vel
        e = conf.BALL_ELAST
        k = conf.BALL_STIFFNESS
        m = conf.MAX_SQUISH
        for i in xrange(4):
            sv[i] *= e
            sv[i] -= k * s[i]
            s[i] += sv[i]
            s[i] = min(s[i], m)
        # update rect
        r = list(r)
        for i, dx in enumerate(self.squish):
            if i < 2:
                r[i] += dx
            r[2 + (i % 2)] -= dx
        r = pg.Rect([ir(x) for x in r])
        self.rect = r

    def pre_draw (self):
        l = self.last_rect
        self.last_rect = self.rect
        #print l, self.rect
        #print self.level.platforms.rects
        return l.union(self.rect)

    def draw (self, screen, offset):
        screen.fill(conf.BALL_COLOUR, self.rect.move(offset))


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
        self.tl = (0, 0)
        self.update_pos()
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
                b.move(axis, dirn * x)
                other_b = expel_types[i]
                b.push(axis, dirn, other_b is not None)
                if other_b is not None:
                    other_b.push(axis, -dirn, True)
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
                            b.move(axis, dirn * x)
                            b.push(axis, dirn, False)
            success = True
            if rect.collidelist(orig_expel) != -1 or any(not r.contains(rect) for r in keep_in) or rect.collidelist(self.spikes.rects) != -1:
                self.game.play_snd('die')
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
                self.dirty = True
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
                    self.game.play_snd('goal')
                    if not self.goals:
                        self.progress()

    def draw (self, screen):
        offset = (-self.pos[0], -self.pos[1])
        if self.dirty:
            self.dirty = False
            rtn = True
            # background
            screen.fill(conf.SOLID_COLOUR)
            screen.fill(conf.BG_COLOUR, self.rect.move(offset))
            # goals
            for r in self.goals:
                screen.fill(conf.GOAL_COLOUR, r.move(offset))
            # spikes
            self.spikes.draw(screen, offset)
            # platforms
            self.platforms.draw(screen, offset)
            if self.resetting:
                w = self.win_rect
                r = self.reset_rect
                if w.colliderect(r):
                    # target rect
                    t = self.reset_rect.move(offset)
                    screen.fill(conf.START_RECT_BORDER_COLOUR, t)
                    b = conf.START_RECT_BORDER_WIDTH
                    screen.fill(conf.START_RECT_COLOUR, t.inflate(-2 * b, -2 * b))
                else:
                    # arrow
                    wx, wy = w.center
                    rx, ry = r.center
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
            for b in self.balls:
                b.pre_draw()
            # balls
            for b in self.balls:
                b.draw(screen, offset)
        elif not self.resetting:
            # background
            rtn = []
            for b in self.balls:
                r = b.pre_draw()
                r.move_ip(offset)
                screen.fill(conf.BG_COLOUR, r)
                rtn.append(r)
            # balls
            for b in self.balls:
                b.draw(screen, offset)
        else:
            rtn = False
        return rtn
