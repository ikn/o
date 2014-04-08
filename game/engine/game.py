"""Main loop and world handling.

Only one :class:`Game` instance should ever exist, and it stores itself in
:data:`conf.GAME`.  Start the game with :func:`run` and use the :class:`Game`
instance for changing worlds and handling the display.

"""

import sys
import os
from random import choice, randrange
from math import exp

import pygame as pg
from pygame.display import update as update_display

from .conf import conf
from .sched import Scheduler
from . import evt, gfx, res, text
from .util import ir, convert_sfc


def run (*args, **kwargs):
    """Run the game.

Takes the same arguments as :class:`Game`, with an optional keyword-only
argument ``t`` to run for this many seconds.

"""
    t = kwargs.pop('t', None)
    global restarting
    restarting = True
    while restarting:
        restarting = False
        Game(*args, **kwargs).run(t)


class _ClassProperty (property):
    """Decorator to create a static property."""

    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


class World (object):
    """A world base class; to be subclassed.

World(scheduler, evthandler, resources)

:arg scheduler: the :class:`sched.Scheduler <engine.sched.Scheduler>` instance
                this world should use for timing.
:arg evthandler: the
                 :class:`evt.EventHandler <engine.evt.handler.EventHandler>`
                 instance this world should use for input.  Event names
                 prefixed with ``_game`` are reserved.
:arg resources: the :class:`res.ResourceManager <engine.res.ResourceManager>`
                instance this world should use for loading resources.

.. attribute:: id

   A unique identifier used for some settings in :mod:`conf`.

   This is a class property---it is independent of the instance.

   A subclass may define an ``_id`` class attribute (not instance attribute).
   If so, that is returned; if not, ``world_class.__name__.lower()`` is
   returned.

"""

    def __init__ (self, scheduler, evthandler, resources, *args, **kwargs):
        #: :class:`sched.Scheduler <engine.sched.Scheduler>` instance taken by
        #: the constructor.
        self.scheduler = scheduler
        #: :class:`evt.EventHandler <engine.evt.handler.EventHandler>` instance
        #: taken by the constructor.
        self.evthandler = evthandler
        #: :class:`gfx.GraphicsManager <engine.gfx.container.GraphicsManager>`
        #: instance used for drawing by default (by, eg. entities).
        self.graphics = gfx.GraphicsManager(scheduler)
        #: :class:`gfx.GraphicsManager <engine.gfx.container.GraphicsManager>`
        #: instance used as the world's output to the screen.  This is the same
        #: instance as :attr:`graphics` by default.
        self.display = self.graphics
        #: :class:`res.ResourceManager <engine.res.ResourceManager>` instance
        #: taken by the constructor.
        self.resources = resources
        #: ``set`` of :class:`Entity <engine.entity.Entity>` instances in this
        #: world.
        self.entities = set()

        self._initialised = False
        self._extra_args = (args, kwargs)
        self._music_evt = self.evthandler.add((conf.EVENT_ENDMUSIC,))[0]
        # {sound_id: [(sound, vol)]}, vol excluding the world's sound volume
        self._sounds = {}
        self._avg_draw_time = scheduler.frame
        self._since_last_draw = 0

    @_ClassProperty
    @classmethod
    def id (cls):
        # doc is in the class(!)
        if hasattr(cls, '_id'):
            return cls._id
        else:
            return cls.__name__.lower()

    @property
    def fps (self):
        """The current draw rate, an average based on
:data:`conf.FPS_AVERAGE_RATIO`.

If this is less than :data:`conf.FPS`, then we're dropping frames.

For the current update FPS, use the
:attr:`Timer.current_fps <engine.sched.Timer.current_fps>` of
:attr:`scheduler`.  (If this indicates the scheduler isn't running at full
speed, it may mean the draw rate is dropping to :data:`conf.MIN_FPS`.)

"""
        return 1 / self._avg_draw_time

    def init (self, *args, **kwargs):
        """Called when this first becomes the active world (before
:meth:`select`).

This receives the extra arguments passed in constructing the world through the
:class:`Game` instance.

"""
        pass

    def select (self):
        """Called whenever this becomes the active world."""
        pass

    def _select (self):
        """Called by the game when becomes the active world."""
        ident = self.id
        pg.event.set_grab(conf.GRAB_EVENTS[ident])
        pg.mouse.set_visible(conf.MOUSE_VISIBLE[ident])
        if conf.MUSIC_AUTOPLAY[ident]:
            self.play_music()
        else:
            pg.mixer.music.stop()
        pg.mixer.music.set_volume(self.scale_volume(self.music_volume))

        if not self._initialised:
            self.init(*self._extra_args[0], **self._extra_args[1])
            self._initialised = True
            del self._extra_args
        self.evthandler.normalise()
        self.select()

    def pause (self):
        """Called to pause the game when the window loses focus."""
        pass

    def update (self):
        """Called every frame to makes any necessary changes."""
        pass

    def _update (self):
        """Called by the game to update."""
        for e in list(self.entities):
            e.update()
        self.update()

    def _handle_slowdown (self):
        """Return whether to draw this frame."""
        s = self.scheduler
        elapsed = s.elapsed
        if elapsed is None:
            # haven't completed a frame yet
            return True
        frame_t = s.current_frame_time
        target_t = s.frame
        # compute rolling frame average for drawing, but don't store it just
        # yet
        r = conf.FPS_AVERAGE_RATIO
        draw_t = ((1 - r) * self._avg_draw_time +
                  r * (self._since_last_draw + elapsed))

        if frame_t <= target_t or abs(frame_t - target_t) / target_t < .1:
            # running at (near enough (within 1% of)) full speed, so draw
            draw = True
        else:
            if draw_t >= 1. / conf.MIN_FPS[self.id]:
                # not drawing would make the draw FPS too low, so draw anyway
                draw = True
            else:
                draw = False
        draw |= not conf.DROP_FRAMES
        if draw:
            # update rolling draw frame average
            self._avg_draw_time = draw_t
            self._since_last_draw = 0
        else:
            # remember frame time for when we next draw
            self._since_last_draw += elapsed
        return draw

    def draw (self):
        """Draw to the screen.

:return: a flag indicating what changes were made: ``True`` if the whole
         display needs to be updated, something falsy if nothing needs to be
         updated, else a list of rects to update the display in.

This method should not change the state of the world, because it is not
guaranteed to be called every frame.

"""
        dirty = self.display.draw(False)
        return dirty

    def quit (self):
        """Called when this is removed from the currently running worlds.

Called before removal---when :attr:`Game.world` is still this world.

"""
        pass

    def add (self, *entities):
        """Add any number of :class:`Entity <engine.entity.Entity>` instances
to the world.

An entity may be in only one world at a time.  If a given entity is already in
another world, it is removed from that world.

Each entity passed may also be a sequence of entities to add.

"""
        entities = list(entities)
        all_entities = self.entities
        for e in entities:
            if hasattr(e, '__len__') and hasattr(e, '__getitem__'):
                entities.extend(e)
            else:
                if e.world is not None:
                    e.world.rm(e)
                if e.graphics.manager is None:
                    e.graphics.manager = self.graphics
                # else manager was explicitly set, so don't change it
                all_entities.add(e)
                e.world = self
                e.added()

    def rm (self, *entities):
        """Remove any number of entities from the world.

Missing entities are ignored.

Each entity passed may also be a sequence of entities to remove.

"""
        entities = list(entities)
        all_entities = self.entities
        for e in entities:
            if hasattr(e, '__len__') and hasattr(e, '__getitem__'):
                entities.extend(e)
            else:
                if e in all_entities:
                    all_entities.remove(e)
                e.world = None
                # unset gm even if it's not this world's main manager
                e.graphics.manager = None

    def use_pools (self, *pools):
        """Tell the resource manager that this world is using the given pools.

This means the resources in the pool will not be removed from cache until this
world drops the pool.

"""
        for pool in pools:
            self.resources.use(pool, self)

    def drop_pools (self, *pools):
        """Stop using the given pools of the resource manager."""
        for pool in pools:
            self.resources.drop(pool, self)

    @property
    def music_volume (self):
        """The world's music volume, before scaling.

This is actually :data:`conf.MUSIC_VOLUME`, and changing it alters that value,
and also changes the volume of currently playing music.

"""
        return conf.MUSIC_VOLUME[self.id]

    @music_volume.setter
    def music_volume (self, volume):
        i = self.id
        if volume > 1:
            print >> sys.stderr, 'warning: music volume greater than 1'
        if volume != conf.MUSIC_VOLUME[i]:
            conf.MUSIC_VOLUME[i] = volume
            conf.changed('MUSIC_VOLUME')
            pg.mixer.music.set_volume(volume)

    @property
    def snd_volume (self):
        """The world's base sound volume.

This is actually :data:`conf.SOUND_VOLUME`, and changing it alters that value,
and also changes the volume of currently playing sounds.

"""
        return conf.SOUND_VOLUME[self.id]

    @snd_volume.setter
    def snd_volume (self, volume):
        i = self.id
        if volume != conf.SOUND_VOLUME[i]:
            conf.SOUND_VOLUME[i] = volume
            conf.changed('SOUND_VOLUME')
            # reset playing sound volumes
            for base_id, snds in self._sounds.iteritems():
                for snd, vol in snds:
                    # vol excludes the world's volume
                    vol *= volume
                    vol = self.scale_volume(vol)
                    if vol > 1:
                        print >> sys.stderr, ('warning: sound volume greater '
                                              'than 1')
                    snd.set_volume(volume * vol)

    def play_music (self, group=None, loop=True, cb=None):
        """Randomly play music from a group.

play_music([group], loop=True[, cb])

:arg group: music group to play from, as keys in :data:`conf.MUSIC`; defaults
            to :attr:`id`, and then `''` (the root directory of
            :data:`conf.MUSIC_DIR`) if there is no such group.
:arg loop: whether to play multiple tracks.  If ``True``, play random tracks
           sequentially until the active world changes, music from a different
           group is played, or the Pygame mixer is manually stopped.  If a
           number, play that many randomly selected tracks (if falsy, do
           nothing).
:arg cb: a function to call when all the music has been played, according to
         the value of ``loop``.  Called even if no music is played (if there is
         none in this group, or ``loop`` is falsy).

Raises ``KeyError`` if the given group does not exist.

"""
        if group is None:
            group = self.id
            if group not in conf.MUSIC:
                group = ''
        # raises KeyError
        fns = conf.MUSIC[group]
        if not fns or not loop:
            # no files or don't want to play anything: do nothing
            if cb is not None:
                cb()
            return

        # modifying variables in closures is painful
        loop = [loop]
        def end_cb ():
            if loop[0] is not True:
                loop[0] -= 1
            if loop[0]:
                play_next()
            elif cb is not None:
                cb()

        def play_next ():
            pg.mixer.music.load(choice(fns))
            pg.mixer.music.play()

        play_next()
        self._music_evt.rm_cbs(*self._music_evt.cbs)
        self._music_evt.cb(end_cb)

    def play_snd (self, base_id, volume=1):
        """Play a sound.

play_snd(base_id, volume=1)

:arg base_id: the identifier of the sound to play (we look for ``base_id + i``
              for a number ``i``---there are as many sounds as set in
              :data:`conf.SOUNDS`).  If this is not in :data:`conf.SOUNDS`, it
              is used as the whole filename (without ``'.ogg'``).
:arg volume: amount to scale the playback volume by.

"""
        alias = base_id
        if base_id in conf.SOUND_ALIASES:
            base_id = conf.SOUND_ALIASES[base_id]
        volume *= conf.SOUND_VOLUMES[alias]
        if base_id in conf.SOUNDS:
            ident = randrange(conf.SOUNDS[base_id])
            base_id += str(ident)
        # else not a random sound
        # load sound, and make a copy so we can play/stop instances separately
        # (without managing channels, at least)
        snd = self.resources.snd(base_id + '.ogg')
        snd = pg.mixer.Sound(snd.get_buffer()
                             if hasattr(snd, 'get_buffer') else snd.get_raw())
        # store sound, and stop oldest if necessary
        playing = self._sounds.setdefault(alias, [])
        if alias in conf.MAX_SOUNDS:
            assert len(playing) <= conf.MAX_SOUNDS[alias]
            if len(playing) == conf.MAX_SOUNDS[alias] and playing:
                playing.pop(0)[0].stop()
        else:
            i = 0
            while i < len(playing):
                if playing[i][0].get_num_channels() == 0:
                    # sound is no longer playing, so remove it
                    playing.pop(i)
                else:
                    i += 1
        playing.append((snd, volume))
        # play
        volume *= conf.SOUND_VOLUME[self.id]
        volume = self.scale_volume(volume)
        if volume > 1:
            print >> sys.stderr, 'warning: sound volume greater than 1'
        snd.set_volume(volume)
        snd.play()

    def _get_base_ids (self, *base_ids, **kwargs):
        # takes (*base_ids, exclude=False) to get the base_ids this represents
        if not base_ids:
            return self._sounds.keys()
        if kwargs.get('exclude', False):
            return list(set(self._sounds.keys()).difference(base_ids))
        else:
            return base_ids

    def _get_playing_snds (self):
        # get {sound: channel} for all playing sounds
        C = pg.mixer.Channel
        snds = {}
        for i in xrange(pg.mixer.get_num_channels()):
            c = C(i)
            s = c.get_sound()
            if s is not None:
                snds[s] = c

    def _with_channels (self, method, *base_ids, **kwargs):
        # call a method on matching sounds' channels
        # avoids code duplication in .*pause_snds()
        base_ids = self._get_base_ids(*base_ids,
                                      exclude=kwargs.get('exclude', False))
        playing = self._get_playing_snds()
        all_snds = self._sounds
        if not base_ids:
            base_ids = self._sounds.keys()
        for base_id in base_ids:
            for snd, vol in all_snds[base_id]:
                if snd in playing:
                    getattr(playing[snd], method)()

    def pause_snds (self, *base_ids, **kwargs):
        """Pause sounds with the given IDs, else pause all sounds.

pause_snds(*base_ids, exclude=False)

:arg base_ids: any number of ``base_id`` arguments as taken by
               :meth:`play_snd`; if none are given, apply to all.
:arg exclude: if ``True``, apply to all but those in ``base_ids``.

"""
        self._with_channels('pause', *base_ids,
                            exclude=kwargs.get('exclude', False))

    def unpause_snds (self, *base_ids, **kwargs):
        """Unpause sounds with the given IDs, else unpause all sounds.

unpause_snds(*base_ids, exclude=False)

:arg base_ids: any number of ``base_id`` arguments as taken by
               :meth:`play_snd`; if none are given, apply to all.
:arg exclude: if ``True``, apply to all but those in ``base_ids``.

"""
        self._with_channels('unpause', *base_ids,
                            exclude=kwargs.get('exclude', False))

    def stop_snds (self, *base_ids, **kwargs):
        """Stop all playing sounds with the given IDs, else stop all sounds.

stop_snds(*base_ids, exclude=False)

:arg base_ids: any number of ``base_id`` arguments as taken by
               :meth:`play_snd`; if none are given, apply to all.
:arg exclude: if ``True``, apply to all but those in ``base_ids``.

"""
        all_snds = self._sounds
        for base_id in self._get_base_ids(
            *base_ids, exclude=kwargs.get('exclude', False)
        ):
            for snd, vol in all_snds.pop(base_id, ()):
                snd.stop()

    def scale_volume (self, vol):
        """Called to scale audio volumes before using them.

The result should be between ``0`` and ``1``.  The default implementation does

::

    (exp(conf.VOLUME_SCALING * vol) - 1) / (exp(conf.VOLUME_SCALING) - 1)

or no scaling if :data:`conf.VOLUME_SCALING` is ``0``.

"""
        scale = conf.VOLUME_SCALING
        if scale == 0:
            return vol
        else:
            return (exp(scale * vol) - 1) / (exp(scale) - 1)


class Game (object):
    """Handles worlds.

Takes the same arguments as :meth:`create_world` and passes them to it.

"""

    def __init__ (self, *args, **kwargs):
        conf.GAME = self
        conf.RES_F = pg.display.list_modes()[0]
        self._quit = False
        self._update_again = False
        #: The currently running world.
        self.world = None
        #: A list of previous (nested) worlds, most 'recent' last.
        self.worlds = []

        # load display settings
        #: The main Pygame surface.
        self.screen = None
        self.refresh_display()
        #: :class:`res.ResourceManager <engine.res.ResourceManager>` instance
        #: used for caching resources.
        self.resources = res.ResourceManager()
        self.resources.use(conf.DEFAULT_RESOURCE_POOL, self)
        self._using_pool = conf.DEFAULT_RESOURCE_POOL
        #: ``{name: renderer}`` dict of
        #: :class:`text.TextRenderer <engine.text.TextRenderer>` instances
        #: available for referral by name in the ``'text'`` resource loader.
        self.text_renderers = {}

        self._init_cbs()
        # set up music
        pg.mixer.music.set_endevent(conf.EVENT_ENDMUSIC)
        # start first world
        self.start_world(*args, **kwargs)

    def _init_cbs (self):
        # set up settings callbacks
        conf.on_change('DEFAULT_RESOURCE_POOL', self._change_resource_pool,
                       source=self)
        conf.on_change('FULLSCREEN', self.refresh_display,
                       lambda: conf.RESIZABLE, source=self)

        def change_res_w ():
            if not conf.FULLSCREEN:
                self.refresh_display()

        conf.on_change('RES_W', change_res_w, source=self)

        def change_res_f ():
            if conf.FULLSCREEN:
                self.refresh_display()

        conf.on_change('RES_F', change_res_f, source=self)

    def _change_resource_pool (self, new_pool):
        # callback: after conf.DEFAULT_RESOURCE_POOL change
        self.resources.drop(self._using_pool, self)
        self.resources.use(new_pool, self)
        self._using_pool = new_pool

    # world handling

    def create_world (self, cls, *args, **kwargs):
        """Create a world.

create_world(cls, *args, **kwargs) -> world

:arg cls: the world class to instantiate; must be a :class:`World` subclass.
:arg args: positional arguments to pass to the constructor.
:arg kwargs: keyword arguments to pass to the constructor.

:return: the created world.

A world is constructed by::

    cls(scheduler, evthandler, *args, **kwargs)

where ``scheduler`` and ``evthandler`` are as taken by :class:`World` (and
should be passed to that base class).

"""
        scheduler = Scheduler()
        scheduler.add_timeout(self._update, frames=1)
        eh = evt.EventHandler(scheduler)
        eh.add(
            (pg.QUIT, self.quit),
            (pg.ACTIVEEVENT, self._active_cb),
            (pg.VIDEORESIZE, self._resize_cb)
        )
        eh.load_s(conf.GAME_EVENTS)
        eh['_game_quit'].cb(self.quit)
        eh['_game_minimise'].cb(self.minimise)
        eh['_game_fullscreen'].cb(self._toggle_fullscreen)
        # instantiate class
        world = cls(scheduler, eh, self.resources, *args, **kwargs)
        scheduler.fps = conf.FPS[world.id]
        return world

    def _select_world (self, world):
        """Set the given world as the current world."""
        if self.world is not None:
            self._update_again = True
            self.world.scheduler.stop()
        self.world = world
        world.display.orig_sfc = self.screen
        world.display.dirty()
        # create text renderers required by this world
        for name, r in conf.TEXT_RENDERERS[world.id].iteritems():
            if not isinstance(r, text.TextRenderer):
                if isinstance(r, basestring):
                    r = (r,)
                r = text.TextRenderer(*r)
            self.text_renderers[name] = r
        world._select()

    def start_world (self, *args, **kwargs):
        """Store the current world (if any) and switch to a new one.

Takes a :class:`World` instance, or the same arguments as :meth:`create_world`
to create a new one.

:return: the new current world.

"""
        if self.world is not None:
            self.worlds.append(self.world)
        return self.switch_world(*args, **kwargs)

    def switch_world (self, world, *args, **kwargs):
        """End the current world and start a new one.

Takes a :class:`World` instance, or the same arguments as :meth:`create_world`
to create a new one.

:return: the new current world.

"""
        if not isinstance(world, World):
            world = self.create_world(world, *args, **kwargs)
        self._select_world(world)
        return world

    def get_worlds (self, ident, current = True):
        """Get a list of running worlds, filtered by identifier.

get_worlds(ident, current = True) -> worlds

:arg ident: the world identifier (:attr:`World.id`) to look for.
:arg current: include the current world in the search.

:return: the world list, in order of time started, most recent last.

"""
        worlds = []
        current = [{'world': self.world}] if current else []
        for data in self.worlds + current:
            world = data['world']
            if world.id == ident:
                worlds.append(world)
        return worlds

    def quit_world (self, depth = 1):
        """Quit the currently running world.

quit_world(depth = 1) -> worlds

:arg depth: quit this many (nested) worlds.

:return: a list of worlds that were quit, in the order they were quit.

If this quits the last (root) world, exit the game.

"""
        if depth < 1:
            return []
        old_world = self.world
        old_world.quit()
        if self.worlds:
            self._select_world(self.worlds.pop())
        else:
            self.quit()
        return [old_world] + self.quit_world(depth - 1)

    # display

    def refresh_display (self):
        """Update the display mode from :mod:`conf`."""
        # get resolution and flags
        flags = conf.FLAGS
        if conf.FULLSCREEN:
            flags |= pg.FULLSCREEN
            r = conf.RES_F
        else:
            w = max(conf.MIN_RES_W[0], conf.RES_W[0])
            h = max(conf.MIN_RES_W[1], conf.RES_W[1])
            r = (w, h)
        if conf.RESIZABLE:
            flags |= pg.RESIZABLE
        ratio = conf.ASPECT_RATIO
        if ratio is not None:
            # lock aspect ratio
            r = list(r)
            r[0] = min(r[0], r[1] * ratio)
            r[1] = min(r[1], r[0] / ratio)
        conf.RES = r
        self.screen = pg.display.set_mode(conf.RES, flags)
        if self.world is not None:
            self.world.display.dirty()

    def toggle_fullscreen (self):
        """Toggle fullscreen mode."""
        conf.FULLSCREEN = not conf.FULLSCREEN

    def _toggle_fullscreen (self, *args):
        # callback: keyboard shortcut pressed
        if conf.RESIZABLE:
            self.toggle_fullscreen()

    def minimise (self):
        """Minimise the display."""
        pg.display.iconify()

    def _active_cb (self, event):
        """Callback to handle window focus loss."""
        if event.state == 2 and not event.gain:
            self.world.pause()

    def _resize_cb (self, event):
        """Callback to handle a window resize."""
        conf.RES_W = (event.w, event.h)
        self.refresh_display()

    def _update (self):
        """Update worlds and draw."""
        self._update_again = True
        while self._update_again:
            self._update_again = False
            self.world.evthandler.update()
            # if a new world was created during the above call, we'll end up
            # updating twice before drawing
            if not self._update_again:
                self.world._update()
        if self.world._handle_slowdown():
            drawn = self.world.draw()
            # update display
            if drawn is True:
                update_display()
            elif drawn:
                if len(drawn) > 60: # empirical - faster to update everything
                    update_display()
                else:
                    update_display(drawn)
        return True

    # running

    def run (self, t = None):
        """Main loop.

run([t])

:arg t: stop after this many seconds (else run forever).

"""
        self.resources.use(conf.DEFAULT_RESOURCE_POOL, self)
        self._using_pool = conf.DEFAULT_RESOURCE_POOL
        self._init_cbs()
        while not self._quit and (t is None or t > 0):
            t = self.world.scheduler.run(seconds = t)
        self.resources.drop(conf.DEFAULT_RESOURCE_POOL, self)
        self._using_pool = None
        conf.rm_cbs(self)

    def quit (self):
        """Quit the game."""
        self.world.scheduler.stop()
        self._quit = True

    def restart (self):
        """Restart the game."""
        global restarting
        restarting = True
        self.quit()
