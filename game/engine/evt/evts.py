"""Event classes for connecting inputs with callbacks."""

import sys

import pygame as pg

from ..util import wrap_fn
from . import inputs

class bmode:
    """Contains :class:`Button` modes."""
    DOWN = 1
    UP = 2
    HELD = 4
    REPEAT = 8
    DBLCLICK = 16

#: ``{n_components: component_names}`` for event components, giving a sequence
#: of component names corresponding to their indices for an event's number of
#: components.
evt_component_names = {
    0: (),
    1: ('button',),
    2: ('neg', 'pos'),
    4: ('left', 'right', 'up', 'down')
}


class BaseEvent (object):
    """Abstract event base class.

Subclasses must implement methods :meth:`Event.add`, :meth:`Event.rm`, and
either :meth:`Event.gen_cb_args` or :meth:`respond`.

"""

    #: Like :attr:`Input.components <engine.evt.inputs.Input.components>`---the
    #: number of components the event can handle.
    components = 0

    def __init__ (self):
        #: Containing :class:`EventHandler <engine.evt.handler.EventHandler>`,
        #: or ``None``.
        self.eh = None
        #: dict whose keys are functions to call on input.
        # values are wrappers to call
        self.cbs = {}

    def _parse_input (self, i):
        # normalise the form of an input as taken by Event.add
        components = self.components
        # work out components and perform checks
        if isinstance(i, inputs.Input):
            if i.components != components:
                raise ValueError(
                    '{0} got a non-{1}-component input but no component '
                    'data'.format(type(self).__name__, components)
                )
            i = (i,)
        if len(i) == 1:
            i = (i[0], None)
        if len(i) == 2:
            i = (i[0], i[1], None)
        if i[1] is None:
            i = (i[0], range(components), i[2])
        if i[2] is None:
            i = (i[0], i[1], range(i[0].components))
        i, orig_evt_components, input_components = i
        if isinstance(orig_evt_components, (int, basestring)):
            orig_evt_components = (orig_evt_components,)
        if isinstance(input_components, int):
            input_components = (input_components,)
        evt_components = []
        c_by_name = None
        for ec in orig_evt_components:
            # translate from name
            if isinstance(ec, basestring):
                if c_by_name is None:
                    c_by_name = dict((v, i)
                        for i, v in enumerate(evt_component_names[components])
                    )
                try:
                    ec = c_by_name[ec]
                except KeyError:
                    raise ValueError('unknown component name: \'{0}\''
                                        .format(ec))
            # check validity
            if ec < 0 or ec >= components:
                raise ValueError('{0} has no component {1}'
                                    .format(self, ec))
            evt_components.append(ec)
        for ic in input_components:
            if ic < 0 or ic >= i.components:
                raise ValueError('{0} has no component {1}'.format(i, ic))
        if len(evt_components) != len(input_components):
            raise ValueError('component mismatch: {0}'
                                .format(i, evt_components, input_components))
        return (i, evt_components, input_components)

    def cb (self, *cbs):
        """Add any number of callbacks to :attr:`cbs`.

cb(*cbs) -> self

For all event types, if a callback is determined not to be able to take
arguments, it is not passed any.

"""
        all_cbs = self.cbs
        for cb in cbs:
            all_cbs[cb] = wrap_fn(cb)
        return self

    def rm_cbs (self, *cbs):
        """Remove any number of callbacks from :attr:`cbs`.

rm_cbs(*cbs) -> self

Missing items are ignored.

"""
        all_cbs = self.cbs
        for cb in cbs:
            if cb in all_cbs:
                del all_cbs[cb]
        return self

    def respond (self, changed):
        """Handle inputs and call callbacks.

:arg changed: whether any inputs changed in any way.

Called by the containing
:class:`EventHandler <engine.evt.handler.EventHandler>`, and guaranteed to be
called every time the handler is updated (which should happen every frame).

"""
        cbs = self.cbs.values()
        for args in self.gen_cb_args(changed):
            for cb in cbs:
                cb(*args)

    # dummy methods that inputs use

    def down (self, i, component):
        """Used by subclasses to handle
:class:`ButtonInput <engine.evt.inputs.ButtonInput>` instances.

:arg i: the calling input.
:arg component: the input's component that has been toggled down.

"""
        pass

    def up (self, i, component):
        """Used by subclasses to handle
:class:`ButtonInput <engine.evt.inputs.ButtonInput>` instances.

:arg i: the calling input.
:arg component: the input's component that has been toggled up.

"""
        pass


class Event (BaseEvent):
    """Connects inputs and callbacks.

Takes any number of inputs like :meth:`add`.

This event type calls callbacks with a single ``pygame.event.Event`` instance,
once for each event gathered by the inputs.

"""

    def __init__ (self, *inps):
        BaseEvent.__init__(self)
        #: ``{input: (evt_components, input_components)}`` (see :meth:`add`).
        self.inputs = {}
        self.add(*inps)

    def add (self, *inps):
        """Add inputs to this event.

add(*inps) -> new_inputs

:return: a list of inputs that weren't already registered with this event.

Takes any number of inputs or ``(input, evt_components = None,
input_components = None)`` tuples.

 - ``evt_components`` is a sequence of the component indices (or a single
   component index) of this event that this input provides data for.  Defaults
   to every component, in order.  Instead of indices, components can also be
   names from :data:`evt_component_names`.
 - ``input_components`` is a sequence of the component indices of (or a single
   component index) of the input to match up to ``evt_components``.  Defaults
   to every component of the input, in order.

If there is a mismatch in numbers of components, ``ValueError`` is raised.

"""
        parse_input = self._parse_input
        self_add = self.inputs.__setitem__
        eh_add = None if self.eh is None else self.eh._add_inputs
        new_inputs = []
        for i in inps:
            i, evt_components, input_components = parse_input(i)
            if not self.input_valid(i):
                raise TypeError('input {0} passed to {1} is invalid'
                                .format(i, type(self).__name__))
            # add if not already added
            if self not in i.evts:
                self_add(i, (evt_components, input_components))
                new_inputs.append(i)
                i.evts.add(self)
                if hasattr(i, 'used_components'):
                    i.used_components[self] = input_components
                if eh_add is not None:
                    eh_add(i)
        return new_inputs

    def rm (self, *inps):
        """Remove inputs from this event.

Takes any number of :class:`Input <engine.evt.inputs.Input>` instances and
ignores missing items.

"""
        self_rm = self.inputs.__delitem__
        eh_rm = None if self.eh is None else self.eh._rm_inputs
        for i in inps:
            if self in i.evts:
                assert i in self.inputs
                self_rm(i)
                i.evts.remove(self)
                if hasattr(i, 'used_components'):
                    del i.used_components[self]
                if eh_rm is not None:
                    eh_rm(i)

    def input_valid (self, i):
        """Check if the given input is valid for this event type."""
        return isinstance(i, inputs.BasicInput)

    def gen_cb_args (self, changed):
        """Generate sets of arguments to call callbacks with.

:arg changed: whether any inputs changed in any way.

This is implemented as an iterator, with each value a sequence of arguments to
pass to each callback.  Guaranteed to be called whenever
:meth:`BaseEvent.respond` is.

"""
        if changed:
            for i in self.inputs:
                # call once for each Pygame event stored
                for pgevt in i._pgevts:
                    yield (pgevt,)
                i.reset()


class MultiEvent (BaseEvent):
    """Base class for generating multiples of :class:`Event` subclasses.

MultiEvent(inps, *args, **kw)

:arg inps: a sequence of inputs as taken as arguments by :class:`Event`.
:arg args: positional arguments to pass to every sub-event on instantiation.
:arg kw: keyword arguments to pass to every sub-event.

Subclasses must define a ``child`` attribute giving the class that this is to
be a multiple of, and a ``multiple`` attribute giving the number of sub-events
to wrap.  They should take note of the behaviour of :meth:`gen_cb_args`,
possibly wrapping it.

"""

    def __init__ (self, inps, *args, **kw):
        self.components = self.multiple * self.child.components
        #: A list of sub-events, in order of the components they map to.
        self.evts = [self.child(*args, **kw) for i in xrange(self.multiple)]
        for evt in self.evts:
            evt._changed = False
        BaseEvent.__init__(self)
        self.add(*inps)

    @property
    def inputs (self):
        inps = set()
        for evt in self.evts:
            inps.update(evt.inputs)
        return inps

    @property
    def eh (self):
        return self._eh

    @eh.setter
    def eh (self, eh):
        # make events have the same handler, so inputs can let it know about
        # filtering changes
        self._eh = eh
        for evt in self.evts:
            evt.eh = eh

    def _parse_input (self, i):
        i, ecs, ics = BaseEvent._parse_input(self, i)
        return ((i,), ecs, ics)

    def add (self, *inps):
        """:inherit:"""
        parse_input = self._parse_input
        # args to pass to each event's add method
        arglists = [[] for i in xrange(self.multiple)]
        cs_per_evt = self.components // self.multiple
        for i in inps:
            i, evt_components, input_components = parse_input(i)
            # sort e/i components together, by e
            mixed_cs = sorted(zip(evt_components, input_components))
            # distribute input's components between events
            ecs = []
            ics = []
            current_evt_i = 0
            i_added = False
            for ec, ic in mixed_cs:
                evt_i = ec // cs_per_evt
                if evt_i != current_evt_i:
                    # moving on to a new event
                    if ecs:
                        arglists[current_evt_i].append(i + (ecs, ics))
                        ecs = []
                        ics = []
                    current_evt_i = evt_i
                ecs.append(ec % cs_per_evt)
                ics.append(ic)
            if ecs:
                arglists[current_evt_i].append(i + (ecs, ics))
        # add to events
        new_inputs = set()
        for evt, args in zip(self.evts, arglists):
            if args:
                new_inputs.update(evt.add(*args))
        return list(new_inputs)

    def rm (self, *inps):
        """:inherit:"""
        for evt in self.evts:
            evt.rm(*inps)

    def gen_cb_args (self, changed):
        """:meth:`Event.gen_cb_args`.

Argument lists are returned for each event, with the event's index inserted as
the first argument.

"""
        for i, evt in enumerate(self.evts):
            changed = evt._changed
            evt._changed = False
            for args in evt.gen_cb_args(changed):
                # args are (event index, *args)
                yield (i,) + tuple(args)


class Button (Event):
    """Button event.

Button(*items[, initial_delay][, repeat_delay][, dbl_click_time])

:arg items: each item is either an input as taken by :class:`Event`, or a
            button mode (one of :data:`bmode.DOWN`, :data:`bmode.UP`,
            :data:`bmode.HELD` and :data:`bmode.REPEAT`) or a bitwise-OR of
            button modes.
:arg initial_delay: if the :data:`bmode.REPEAT` mode is given, this is the
                    initial delay in seconds before a button starts repeating
                    while held.
:arg repeat_delay: like initial_delay, the time between repeats in seconds.
:arg dbl_click_time: if the :data:`bmode.DBLCLICK` mode is given, this is the
                     maximum delay in seconds between down events for a
                     double-click event to be registered.

Callbacks are called with ``{mode: count}`` for each ``mode`` given, where
``count`` is the number of occurrences of events corresponding to that mode
that have happened within the last frame.

The ``count`` for :data:`bmode.HELD` is only ever ``0`` or ``1``, and indicates
whether the button was held at the end of the frame.

The ``count`` for :data:`bmode.REPEAT` may only be ``> 1`` if either repeat
rate is greater than the current framerate.

The ``count`` for :data:`bmode.DBLCLICK` may only be ``> 1`` if at least 3 down
events are registered within a frame.

"""

    name = 'button'
    components = 1

    def __init__ (self, *items, **kw):
        modes = 0
        inps = []
        for item in items:
            if isinstance(item, int):
                modes |= item
            else:
                inps.append(item)
        if not modes:
            print >> sys.stderr, 'warning: no modes passed to Button event'
        Event.__init__(self, *inps)
        #: A bitwise-OR of all button modes passed to the constructor.
        self.modes = modes
        self._downevts = self._upevts = 0
        #: As passed to the constructor.
        self.initial_delay = kw.get('initial_delay')
        #: As passed to the constructor.
        self.repeat_delay = kw.get('repeat_delay')
        if modes & bmode.REPEAT and (self.initial_delay is None or
                                     self.repeat_delay is None):
            raise TypeError('initial_delay and repeat_delay arguments are '
                            'required if given the REPEAT mode')
        #: As passed to the constructor.
        self.dbl_click_time = kw.get('dbl_click_time')
        if modes & bmode.DBLCLICK and self.dbl_click_time is None:
            raise TypeError('dbl_click_time argument is required if given the '
                            'DBLCLICK mode')
        # whether currently repeating
        self._repeating = False
        # whether within the double-click timeout
        self._can_dbl_click = False

    def input_valid (self, i):
        """:inherit:"""
        return i.provides['button']

    def down (self, i, component):
        """:inherit:"""
        if component in self.inputs[i][1]:
            self._downevts += 1

    def up (self, i, component):
        """:inherit:"""
        if component in self.inputs[i][1]:
            self._upevts += 1
            # stop repeating if let go of all buttons at any point
            if (self.modes & bmode.REPEAT and
                not any(i.held(self)[0] for i in self.inputs)):
                self._repeating = False

    def gen_cb_args (self, changed):
        """:inherit:"""
        modes = self.modes
        if modes & (bmode.HELD | bmode.REPEAT):
            held = any(i.held(self)[0] for i in self.inputs)
        else:
            held = False
        if not changed and not held and not self._can_dbl_click:
            # nothing to do
            return
        # construct callback argument
        evts = {}
        downevts = self._downevts
        if modes & bmode.DOWN:
            evts[bmode.DOWN] = self._downevts
        if modes & bmode.UP:
            evts[bmode.UP] = self._upevts
        self._downevts = self._upevts = 0
        if modes & bmode.HELD:
            evts[bmode.HELD] = held
        if modes & bmode.REPEAT:
            n_repeats = 0
            if self._repeating:
                if held:
                    # continue repeating
                    if self.eh is None:
                        raise RuntimeError('cannot respond properly if not '
                                           'attached to an EventHandler')
                    t = self._repeat_remain
                    # use target framerate for determinism
                    t -= self.eh.scheduler.frame
                    if t < 0:
                        # repeat rate may be greater than the framerate
                        n_repeats, t = divmod(t, self.repeat_delay)
                        n_repeats = -int(n_repeats)
                    self._repeat_remain = t
                else:
                    # stop repeating
                    self._repeating = False
            elif held:
                # start repeating
                self._repeating = True
                self._repeat_remain = self.initial_delay
            evts[bmode.REPEAT] = n_repeats
        if modes & bmode.DBLCLICK:
            n_dbls = 0
            got = downevts > 0
            if not self._can_dbl_click:
                # handled the first down event
                downevts -= 1
            self._can_dbl_click = can = not (downevts % 2)
            if got:
                # got some presses
                if can:
                    # end on a first press: reset timer
                    self._dbl_click_remain = self.dbl_click_time
                if downevts > 0:
                    # got some second presses within the required time
                    n_dbls = (downevts + 1) / 2
            elif can:
                # reduce time left to click again
                self._dbl_click_remain -= self.eh.scheduler.frame
                if self._dbl_click_remain < 0:
                    self._can_dbl_click = False
            evts[bmode.DBLCLICK] = n_dbls
        if any(evts.itervalues()):
            yield (evts,)


class Button2 (MultiEvent):
    """A 2-component version of :class:`Button`.

Button2(*items[, initial_delay][, repeat_delay][, dbl_click_time])

Callbacks are called with ``(button, evts)``, where ``button`` is the button
this applies to (``0`` or ``1``) and ``evts`` is the argument passed by
:class:`Button`.

"""

    name = 'button2'
    child = Button
    multiple = 2

    def __init__ (self, *items, **kw):
        modes = 0
        inps = []
        for item in items:
            if isinstance(item, int):
                modes |= item
            else:
                inps.append(item)
        MultiEvent.__init__(self, inps, modes, **kw)


class Button4 (Button2):
    """A 4-component version of :class:`Button`.

Button4(*items[, initial_delay][, repeat_delay][, dbl_click_time])

Callbacks are called with ``(axis, dirn, evts)``, where we treat the 4 buttons
as being (left, up, right, down).  ``axis`` corresponds to the x or y axis
(``0`` (left, right) or ``1``) and ``dirn`` gives the button's direction
(``-1`` (left, up) or ``1``).  ``evts`` is the argument passed by
:class:`Button`.

"""

    name = 'button4'
    multiple = 4

    def gen_cb_args (self, changed):
        for args in Button2.gen_cb_args(self, changed):
            btn = args[0]
            yield ((1 if btn >= 2 else 0, 1 if btn % 2 else -1) +
                   tuple(args[1:]))


class Axis (Event):
    """Axis event.

The magnitude of the axis position for a button is ``1`` if it is held, else
``0``.

Callbacks are called every frame with the current axis position (after summing
over each registered input and restricting to ``-1 <= x <= 1``).

"""

    name = 'axis'
    components = 2

    def __init__ (self, *inps):
        Event.__init__(self, *inps)
        self._pos = 0

    def input_valid (self, i):
        """:inherit:"""
        return i.provides['axis'] or i.provides['button']

    def gen_cb_args (self, changed):
        """:inherit:"""
        if changed:
            # compute position: sum over every input
            pos = 0
            for i, (evt_components, input_components) \
                in self.inputs.iteritems():
                if i.provides['axis']:
                    # add current axis position for each component
                    for ec, ic in zip(evt_components, input_components):
                        pos += (2 * ec - 1) * i._pos[ic]
                else: # i.provides['button']
                    used_components = i.used_components[self]
                    # add 1 for each held component
                    for j, held in enumerate(i.held(self)):
                        c = used_components[j]
                        ic = input_components[c]
                        if ic in used_components and i._held[ic]:
                            pos += 2 * evt_components[c] - 1
            # clamp to [-1, 1]
            self._pos = pos = min(1, max(-1, pos))
        else:
            # use previous position
            pos = self._pos
        yield (pos,)


class Axis2 (MultiEvent):
    """A double :class:`Axis`.

Callbacks are called every frame with a list of axis positions for each of the
two axes.

"""
    name = 'axis2'
    child = Axis
    multiple = 2

    def __init__ (self, *inps):
        MultiEvent.__init__(self, inps)

    def gen_cb_args (self, changed):
        """:inherit:"""
        pos = [0] * self.multiple
        for evt_i, this_pos in MultiEvent.gen_cb_args(self, changed):
            pos[evt_i] += this_pos
        yield (pos,)


class RelAxis (Event):
    """Relative axis event.

Each input is scaled by a positive number (see :meth:`add` for details).

The magnitude of the relative position for an axis is its position, and for a
button is ``1`` if it is held, else ``0``.

Callbacks are called with the total, scaled relative change over all inputs
registered with this event.

"""
    name = 'relaxis'
    components = 2

    def __init__ (self, *inps):
        #: ``{scale: input}`` (see :meth:`add`).
        self.input_scales = {}
        Event.__init__(self, *inps)

    def add (self, *inps):
        """:meth:`Event.add`.

Inputs are
``(scale = 1, input, evt_components = None, input_components = None)``, where
``scale`` is a positive number to scale the relative axis's position by before
calling callbacks.

"""
        # extract and store scales before passing to Event.add
        real_inputs = []
        scale = self.input_scales
        for i in inps:
            if isinstance(i, inputs.Input):
                i = (i,)
            if isinstance(i[0], inputs.Input):
                i = (1,) + tuple(i)
            if i[0] < 0:
                raise ValueError("input scaling must be non-negative.")
            scale[i[1]] = i[0]
            real_inputs.append(i[1:])
        return Event.add(self, *real_inputs)

    def rm (self, *inps):
        """:inherit:"""
        Event.rm(self, *inps)
        # remove stored scales (no KeyError means all inputs exist)
        scale = self.input_scales
        for i in inps:
            del scale[i]

    def input_valid (self, i):
        """:inherit:"""
        return (i.provides['relaxis'] or i.provides['axis'] or
                i.provides['button'])

    def gen_cb_args (self, changed):
        """:inherit:"""
        rel = 0
        scale = self.input_scales
        # sum all relative positions
        for i, (evt_components, input_components) \
            in self.inputs.iteritems():
            this_rel = 0
            if i.provides['relaxis']:
                for ec, ic in zip(evt_components, input_components):
                    this_rel += (2 * ec - 1) * i.rel[ic]
                i.reset(*input_components)
            elif i.provides['axis']:
                # use axis position
                for ec, ic in zip(evt_components, input_components):
                    this_rel += (2 * ec - 1) * i._pos[ic]
            else: # i.provides['button']
                used_components = i.used_components[self]
                # use 1 for each held component
                for j, held in enumerate(i.held(self)):
                    c = used_components[j]
                    ic = input_components[c]
                    if ic in used_components and i._held[ic]:
                        this_rel += 2 * evt_components[c] - 1
            rel += this_rel * scale[i]
        if rel:
            yield (rel,)


class RelAxis2 (MultiEvent):
    """A double :class:`RelAxis`.

Callbacks are called every frame with a list of positions for each of the two
relative axes.

"""
    name = 'relaxis2'
    child = RelAxis
    multiple = 2

    def __init__ (self, *inps):
        MultiEvent.__init__(self, inps)

    def _parse_input (self, i):
        if isinstance(i, inputs.Input):
            i = (i,)
        if isinstance(i[0], inputs.Input):
            return MultiEvent._parse_input(self, i)
        else:
            scale = i[0]
            i, ecs, ics = MultiEvent._parse_input(self, i[1:])
            return ((scale,) + i, ecs, ics)

    def gen_cb_args (self, changed):
        """:inherit:"""
        rel = [0] * self.multiple
        for evt_i, this_rel in MultiEvent.gen_cb_args(self, changed):
            rel[evt_i] += this_rel
        yield (rel,)
