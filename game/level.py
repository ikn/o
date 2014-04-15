from math import atan2, pi

import pygame as pg
import Xlib.display

from .engine import conf, gfx, util
from .engine.game import World
from .engine.entity import Entity


def get_win_frame (root, win):
    while True:
        parent = win.query_tree().parent
        if parent == root:
            break
        win = parent
    return win


class Ball (Entity):
    def __init__ (self, pos, vel):
        Entity.__init__(self)
        self.graphics.pos = pos
        self.graphic = self.graphics.add(gfx.Colour(
            conf.BALL_COLOUR, (conf.BALL_SIZE, conf.BALL_SIZE),
            conf.LAYERS['ball']
        ))[0]
        self.graphic.anchor = 0
        self.vel = list(vel)

    @property
    def rect (self):
        return self.graphics.rect

    def push (self, axis, dirn, other_ball):
        v = self.vel
        if v[axis] and (v[axis] > 0) == (dirn == -1):
            self.world.play_snd('bounce')
        v[axis] = dirn * abs(v[axis])

    def move (self, axis, dx):
        dp = [0, 0]
        dp[axis] = dx
        self.graphics.move_by(*dp)

    def update_active (self):
        self.graphics.move_by(*self.vel)


class Rects (Entity):
    def __init__ (self, c, rects):
        Entity.__init__(self)
        for r in rects:
            r = pg.Rect(r)
            self.graphics.add(gfx.Colour(c, r.size, conf.LAYERS['rect']),
                              *r.topleft)

    @property
    def rects (self):
        return [g.rect for g in self.graphics]


def update_display ():
    conf.GAME.refresh_display()
    return True


class Level (World):
    def init (self, ident=0):
        # update display frequency often - sometimes the pygame display isn't
        # the actual window size, and this matters here
        self.scheduler.add_timeout(update_display, .1)

        self.ident = ident
        data = conf.LEVELS[ident]

        self.goals = [gfx.Colour(
            conf.GOAL_COLOUR, (pos, conf.GOAL_SIZE), conf.LAYERS['goal']
        ) for pos in data['goals']]
        self.balls = [Ball(pos, vel) for pos, vel in data['balls']]
        if len(self.goals) != len(self.balls):
            print 'warning: {} goals, {} balls'.format(len(self.goals),
                                                       len(self.balls))
        self.platforms = Rects(conf.RECT_COLOURS['platform'],
                               data['platforms'])
        self.spikes = Rects(conf.RECT_COLOURS['spikes'], data['spikes'])

        # graphics
        conf.RES_W = data.get('res', conf.DEFAULT_RES)
        conf.RESIZABLE = data.get('resizable', True)
        gs = self.graphics
        self.bg, self.graphics, self.arrow = gs.add(
            gfx.Colour(conf.SOLID_COLOUR, gs.orig_size, 1),
            gfx.GraphicsManager(self.scheduler, data['size']),
            gfx.Graphic('arrow.png', layer=-1).align(within=gs.rect)
        )
        self.graphics.add(
            gfx.Colour(conf.BG_COLOUR, data['size'], conf.LAYERS['bg'])
        )[0].anchor = 0
        self.add(self.platforms, self.spikes, *self.balls)
        self.graphics.add(*self.goals)

        # indicate to move to start position
        self.resetting = True
        rects = [b.rect for b in self.balls]
        rect = rects[0].unionall(rects[1:])
        pos = rect.topleft
        rect.topleft = (0, 0)
        sfc = util.blank_sfc(rect.size)
        sfc.fill(conf.START_RECT_BORDER_COLOUR, rect)
        b = conf.START_RECT_BORDER_WIDTH
        sfc.fill(conf.START_RECT_COLOUR, rect.inflate(-2 * b, -2 * b))
        self.reset_box = gfx.Graphic(sfc, pos, conf.LAYERS['reset rect'])
        self.graphics.add(self.reset_box)

        self.manager = self.graphics
        self.graphics = gs

        # set up xlib
        w_id = pg.display.get_wm_info()['window']
        x_display = Xlib.display.Display()
        x_root = x_display.screen().root
        self.x_window = get_win_frame(
            x_root, x_display.create_resource_object('window', w_id)
        )

        # centre level on the screen
        w, h = conf.RES_F
        sx, sy = data['size']
        # the top-left of the level on the screen
        self.tl = ((w - sx) / 2, (h - sy) / 2)
        # the level boundary in physics space
        self.rect = pg.Rect(0, 0, sx, sy)
        # win_rect: visible window rect in physics space
        # pos: win_rect.topleft
        self.update_pos()

    def progress (self):
        self.ident += 1
        if self.ident >= len(conf.LEVELS):
            conf.GAME.quit_world()
        else:
            conf.GAME.switch_world(Level, self.ident)

    def update_pos (self, pos=None):
        if pos is None:
            x, y = self.tl
            geom = self.x_window.get_geometry()
            pos = (geom.x - x, geom.y - y)
        self.pos = pos
        self.win_rect = pg.Rect(pos, self.graphics.orig_size)
        self.bg.size = self.graphics.orig_size

    def resolve_cols (self):
        bs = self.balls
        success = True

        for b in bs:
            rect = b.rect
            expel = tuple(self.platforms.rects)
            orig_expel = tuple(expel)
            expel_types = [None] * len(expel)
            b_data = [(this_b, this_b.rect)
                        for this_b in bs if this_b is not b]
            if b_data:
                b_types, b_rects = zip(*b_data)
                expel_types += b_types
                expel += b_rects

            for i in b.rect.collidelistall(expel):
                e_x0, e_y0, w, h = expel[i]
                e_x1, e_y1 = e_x0 + w, e_y0 + h
                r_x0, r_y0, w, h = b.rect
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
                if not r.contains(b.rect):
                    k_x0, k_y0, w, h = r
                    k_x1, k_y1 = k_x0 + w, k_y0 + h
                    r_x0, r_y0, w, h = b.rect
                    r_x1, r_y1 = r_x0 + w, r_y0 + h
                    for x, axis, dirn in (
                        (r_x1 - k_x1, 0, -1), (r_y1 - k_y1, 1, -1),
                        (k_x0 - r_x0, 0, 1), (k_y0 - r_y0, 1, 1)
                    ):
                        if x > 0:
                            b.move(axis, dirn * x)
                            b.push(axis, dirn, False)

            if (b.rect.collidelist(orig_expel) != -1 or
                any(not r.contains(b.rect) for r in keep_in) or
                b.rect.collidelist(self.spikes.rects) != -1):
                success = False

        return success

    def update_physics (self, old_rect):
        old_pos = old_rect.topleft
        old_res = old_rect.size
        pos = self.pos

        # ball position
        for b in self.balls:
            b.update_active()
        res = self.win_rect.size

        if old_pos == pos and old_res == res:
            if not self.resolve_cols():
                self.play_snd('die')
                conf.GAME.switch_world(Level, self.ident)
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
                    self.play_snd('die')
                    conf.GAME.switch_world(Level, self.ident)
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
                self.update_pos(pos)
                if not self.resolve_cols():
                    self.play_snd('die')
                    conf.GAME.switch_world(Level, self.ident)
                    return

    def update (self):
        old_rect = self.win_rect
        self.update_pos()
        self.manager.pos = (-self.pos[0], -self.pos[1])

        if self.resetting:
            w = self.win_rect
            r = self.reset_box.rect
            if w.contains(r):
                self.resetting = False
                self.manager.rm(self.reset_box)
                self.graphics.rm(self.arrow)
            else:
                # update arrow graphic
                wx, wy = w.center
                rx, ry = r.center
                x, y, ww, wh = w
                if old_rect.size != w.size:
                    self.arrow.align()
                self.arrow.angle = -atan2(ry - wy, rx - wx) - pi / 2
                self.arrow.visible = not w.colliderect(r)

        if not self.resetting:
            self.update_physics(old_rect)
            # remove touched goals and balls
            for b in self.balls:
                col = b.rect.collidelistall([g.rect for g in self.goals])
                if col:
                    self.graphics.rm(self.goals.pop(col.pop(0)))
                    self.balls.remove(b)
                    self.rm(b)
                    self.play_snd('goal')
            # win condition
            if not self.goals:
                self.progress()
