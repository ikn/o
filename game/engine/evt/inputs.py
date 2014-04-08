"""Input classes, representing filtered subsets of Pygame events."""

import sys

import pygame as pg

class _Unfilterable (object):
    pass

#: A value that an :class:`Input` cannot filter for.
UNFILTERABLE = _Unfilterable()

#: ``{device: allowed_mod_devices}`` for :class:`ButtonInput` instances.  An
#: input for :attr:`device <Input.device>` ``device`` may only have modifiers
#: with :attr:`device <Input.device>` in ``allowed_mod_devices``.
mod_devices = {
    'kbd': ('kbd',),
    'mouse': ('kbd', 'mouse'),
    'pad': ('pad',)
}


def _init_pad (dev_id=True):
    # 'pad' device initialisation function
    done = []
    todo = xrange(pg.joystick.get_count()) if dev_id is True else (dev_id,)
    for i in todo:
        try:
            pg.joystick.Joystick(i).init()
        except pg.error:
            pass
        else:
            done.append(i)
    return done


#: ``{device: init_fn}`` giving initialisation functions to initialise devices
#: where possible.  These functions take the ``Input.device_id`` to initialise
#: for, or no argument to initialise for all devices of this type, and should
#: return a sequence of device IDs that have been successfully initialised.
device_init_handlers = {
    'pad': _init_pad
}

class mbtn:
    """Contains mouse button aliases."""
    LEFT = 1
    MIDDLE = 2
    RIGHT = 3
    UP = 4
    DOWN = 5


def _pad_matches (device_id):
    # get the pygame.joystick.Joystick instances that match the given device_id
    if device_id is True:
        ids = xrange(pg.joystick.get_count())
    elif device_id is None:
        ids = ()
    else:
        ids = (device_id,)
    js = []
    for i in ids:
        try:
            js.append(pg.joystick.Joystick(i))
        except pg.error:
            print >> sys.stderr, 'warning: no such pad: {}'.format(i)
    return js


class Input (object):
    """Base class for handling input events.  Does nothing by itself.

Input(*pgevts)

:arg pgevts: Pygame event IDs to listen for.

If a subclass has a ``pgevts`` attribute, this is a list of events to add to
the argument at initialisation.

Comparing inputs for equality compares filters only (so inputs of different
types may be equal).

"""

    #: Number of components ('directions'/'button-likes') represented by this
    #: input.
    components = 0
    #: The string device name that this input type corresponds to (see
    #: :data:`inputs_by_name <engine.evt.conffile.inputs_by_name>`).
    device = None
    #: A value that the device ID will never take (see :attr:`device_id`).
    invalid_device_id = -1

    def __init__ (self, *pgevts):
        #: An ``{id: provided}`` dict of 'interfaces' this input provides, with
        #: keys ``'button'``, ``'axis'``, ``'relaxis'``.
        self.provides = {'button': False, 'axis': False, 'relaxis': False}
        #: Variable representing the current device ID; may be a string as a
        #: variable name, or ``None``.  See also
        #: :meth:`EventHandler.assign_devices()
        #: <engine.evt.handler.EventHandler.assign_devices>`).
        self.device_var = None
        #: A set of :class:`Event <engine.evt.evts.Event>` instances that
        #: contain this input, or ``None``.
        self.evts = set()
        pgevts = set(pgevts)
        if hasattr(self, 'pgevts'):
            pgevts.update(self.pgevts)
        #: A ``{pgevt_attr: val}`` dict that represents how events are filtered
        #: before being passed to this input (see :meth:`filter`).
        self.filters = {}
        if pgevts:
            self.filters['type'] = pgevts
        self._device_id = True

    def _str_dev_id (self):
        # device id/var for printing
        dev_id = self._device_id
        if dev_id is True:
            dev_id = '(any)'
        elif dev_id is None and self.device_var is not None:
            dev_id = '<{0}>'.format(self.device_var)
        return dev_id

    def _str (self, arg):
        # string representation with some contained data
        return '{0}({1})'.format(type(self).__name__, arg)

    def __str__ (self):
        return self._str(self.filters)

    def __repr__ (self):
        return str(self)

    def __eq__ (self, other):
        return isinstance(other, Input) and other.filters == self.filters

    def __hash__ (self):
        # required in Python 3 since have __eq__
        return id(self)

    def handle (self, pgevt):
        """Called by :class:`EventHandler <engine.evt.handler.EventHandler>`
with a ``pygame.event.Event``.

The passed event matches :attr:`filters`.

:return: whether anything in the input's state changed.

"""
        return False

    def _ehs (self):
        # get all handlers that contain this event
        ehs = set()
        for evt in self.evts:
            if evt.eh is not None:
                ehs.add(evt.eh)
        return ehs

    def filter (self, attr, *vals, **kw):
        """Filter events passed to this input.

filter(attr, *vals, refilter = False) -> self

:arg attr: Pygame event attribute to filter by.
:arg vals: allowed values of the given attribute for filtered events.
:arg refilter: if ``True``, replace previous filtering by ``attr`` with the
               given ``vals``, else add to the values already filtered by.

"""
        refilter = kw.get('refilter', False)
        if not vals:
            if refilter:
                # refilter to nothing, ie. remove all filtering
                self.unfilter(attr)
            # else nothing to do
            return self
        # wrap with removal from/readdition to handler
        for eh in self._ehs():
            eh._rm_inputs(self)
        if UNFILTERABLE in vals:
            raise ValueError('cannot filter for {0}'.format(UNFILTERABLE))
        if refilter:
            self.filters[attr] = set(vals)
        else:
            self.filters.setdefault(attr, set()).update(vals)
        for eh in self._ehs():
            eh._add_inputs(self)
        return self

    def unfilter (self, attr, *vals):
        """Remove filtering by the given attribute.

:arg attr: Pygame event attribute to modify filtering for.
:arg vals: values to remove filtering for.  If none are given, all filtering
           by ``attr`` is removed.

"""
        if attr not in self.filters:
            return self
        # wrap with removal from/readdition to handler
        for eh in self._ehs():
            eh._rm_inputs(self)
        got = self.filters[attr]
        if vals:
            # remove given values
            got.difference_update(vals)
            if not got:
                # no longer filtering by this attribute
                del self.filters[attr]
        else:
            # remove all
            del self.filters[attr]
        for eh in self._ehs():
            eh._add_inputs(self)
        return self

    @property
    def device_id (self):
        """The particular device that this input captures input for.

May be ``True``, in which case all such devices work through this input.

May be ``None``, in which case no input will be registered; this is done by
filtering by :attr:`invalid_device_id`.

Subclasses may set an attribute ``device_id_attr``, in which case setting this
attribute filters using ``device_id_attr`` as the event attribute and the set
value as the attribute value to filter by.  If a subclass does not provide
``device_id_attr`` and does not override the setter, this operation raises
``TypeError``.

"""
        return self._device_id

    @device_id.setter
    def device_id (self, device_id):
        if hasattr(self, 'device_id_attr'):
            if device_id is True:
                # sort by nothing to get all events
                ids = ()
            elif device_id is None:
                # sort by an invalid ID to make sure we get no events
                ids = (self.invalid_device_id,)
            else:
                ids = (device_id,)
            self.filter(self.device_id_attr, *ids, refilter = True)
            self._device_id = device_id
            self._init()
        else:
            raise TypeError('this Input type doesn\'t support device IDs')

    def normalise (self):
        """Determine and set the input's current state, if any.

This implementation does nothing.

"""
        pass

    def _init (self):
        # initialise the device/id associated with this input
        dev_id = self._device_id
        if dev_id is not None:
            init_fn = device_init_handlers.get(self.device)
            if init_fn is not None:
                ehs = self._ehs()

                if dev_id is True:
                    done = init_fn()
                else:
                    key = (self.device, dev_id)
                    if any(key in eh._init_data for eh in ehs):
                        # make sure every handler knows about this
                        done = (dev_id,)
                    else:
                        done = init_fn(dev_id)

                keys = [(dev_id, dev_id) for dev_id in done]
                for eh in ehs:
                    eh._init_data.update(keys)


class BasicInput (Input):
    """An input that handles raw Pygame events.

BasicInput(*pgevts)

:arg pgevts: Pygame event IDs to listen for.

"""

    def __init__ (self, *pgevts):
        #: Pygame event IDs as passed to the constructor.
        self.pgevts = pgevts
        Input.__init__(self, *pgevts)
        # stored Pygame events, used by Event
        self._pgevts = []

    def __str__ (self):
        return self._str(
            ', '.join(map(pg.event.event_name, self.pgevts)).upper()
        )

    def handle (self, pgevt):
        """:inherit:"""
        Input.handle(self, pgevt)
        self._pgevts.append(pgevt)
        return True

    def reset (self):
        """Clear cached Pygame events.

Called by the owning :class:`Event <engine.evt.evts.Event>`.

"""
        self._pgevts = []


class ButtonInput (Input):
    """Abstract base class representing a button-like action (:class:`Input`
subclass).

ButtonInput([button], *mods)

:arg button: button ID to listen for.  To use this, subclasses must set a
             ``button_attr`` property to filter by that Pygame event attribute
             with this ID as the value.  Otherwise, they must implement
             filtering themselves.
:arg mods: inputs to use as modifiers.  Each may be a :class:`ButtonInput`, a
           sequence of them, or ``(input, component)`` giving the component of
           the input to use (from ``0`` to ``input.components - 1``).

Subclasses must have a :attr:`device <Input.device>` in :data:`mod_devices`,
which restricts allowed devices of modifiers.

"""

    components = 1

    def __init__ (self, button = None, *mods):
        self._held = [False] * self.components
        #: Whether this input is acting as a modifier.
        self.is_mod = False
        #: ``{container: components}`` for each container (such as an
        #: :class:`Event <engine.evt.evts.Event>`, or another
        #: :class:`ButtonInput` as a modifier).  ``components`` is a sequence
        #: of the components of this input that the container uses.
        self.used_components = {}
        Input.__init__(self)
        self.provides['button'] = True
        if hasattr(self, 'button_attr') and button is not None:
            self.filter(self.button_attr, button)
        #: The button ID this input represents, as taken by the constructor.
        self.button = button

        mods = list(mods)
        mods_parsed = []
        for m in mods:
            # default to using component 0 of the modifier
            if isinstance(m, Input):
                m = (m, 0)
            elif len(m) == 1:
                m = (m[0], 0)
            # now we have a sequence
            if isinstance(m[1], Input):
                # sequence of mods
                mods.extend(m)
            else:
                # (mod, component)
                mods_parsed.append(m)
        if any(m.mods for m, c in mods_parsed):
            raise ValueError('modifiers cannot have modifiers')
        ds = mod_devices[self.device]
        for m, c in mods_parsed:
            if m.device not in ds:
                raise TypeError(
                    'the modifier {0} is for device {1}, which is not '
                    'compatible with {2} instances'
                    .format(m, m.device, type(self).__name__)
                )
        #: List of modifiers (:class:`ButtonInput` instances) that affect this
        #: input.
        self.mods = mods = []
        for m, c in mods_parsed:
            if c < 0 or c >= m.components:
                raise ValueError('{0} has no component {1}'.format(m, c))
            if not m.provides['button']:
                raise TypeError('input {0} cannot be a modifier'.format(m))
            # we're now the mod's container
            m.is_mod = True
            m.used_components[self] = (c,)
            mods.append(m)

    def __str__ (self):
        if hasattr(self, '_btn_name'):
            # make something like [mod1]...[modn]self to pass to Input._str
            # _btn_name should give form for displaying within type wrapper
            s = self._btn_name()
            for m in self.mods:
                if hasattr(m, '_mod_btn_name'):
                    # _mod_btn_name should give form for displaying as a mod
                    mod_s = m._mod_btn_name()
                else:
                    mod_s = str(m)
                s = '[{0}]{1}'.format(mod_s, s)
            return self._str(s)
        else:
            return Input.__str__(self)

    def held (self, container):
        """A list of the held state of this button for each component.

Each item is a bool that corresponds to the component in the same position in
:attr:`used_components` for the given container.

"""
        return [self._held[c] for c in self.used_components[container]]

    def down (self, component = 0, evt = True):
        """Set the given component's button state to down.

:arg evt: whether to let the containing event know about this.

"""
        self._held[component] = True
        # mods don't have events
        if evt and not self.is_mod:
            for evt in self.evts:
                if component in self.used_components[evt]:
                    evt.down(self, component)
            return True
        return False

    def up (self, component=0, evt=True):
        """Set the given component's button state to up.

:arg evt: whether to let the containing event know about this.

"""
        # don't allow an up without a down
        if self._held[component]:
            self._held[component] = False
            # mods don't have events
            if evt and not self.is_mod:
                for evt in self.evts:
                    if component in self.used_components[evt]:
                        evt.up(self, component)
                return True
        return False

    def set_held (self, held, evts=False, component=0):
        """Set the held state of the button on the given component.

:arg evts: whether to trigger button down/up events if the held state changes.

"""
        if held != self._held[0]:
            if evts:
                self.down() if held else self.up()
            else:
                self._held[0] = bool(held)

    def handle (self, pgevt, mods_match):
        """:meth:`Input.handle`.

:arg mods_match: whether the modifiers attached to this button are currently
                 active.

If a subclass has a ``down_pgevts`` attribute, this sets the button down on
component ``0`` for Pygame events with IDs in this list, and up on component
``0`` for all other events.  Otherwise, it does nothing.

"""
        rtn = Input.handle(self, pgevt)
        if hasattr(self, 'down_pgevts'):
            if pgevt.type in self.down_pgevts:
                if mods_match:
                    rtn |= self.down()
            else:
                rtn |= self.up()
        return rtn


class KbdKey (ButtonInput):
    """Keyboard key.

:arg key: the key code (required).

"""

    device = 'kbd'
    name = 'key'
    pgevts = (pg.KEYDOWN, pg.KEYUP)
    button_attr = 'key'
    down_pgevts = (pg.KEYDOWN,)

    def __init__ (self, key, *mods):
        ButtonInput.__init__(self, key, *mods)

    def _btn_name (self):
        return pg.key.name(self.button).upper()

    _mod_btn_name = _btn_name

    def normalise (self):
        """:inherit:"""
        ButtonInput.set_held(self, pg.key.get_pressed()[self.button])


class _SneakyMultiKbdKey (KbdKey):
    # KbdKey wrapper to handle multiple keys, for use as a modifier (held if
    # any key is held) - only for module.mod

    def __init__ (self, button, *buttons):
        KbdKey.__init__(self, buttons[0])
        self.filter(self.button_attr, *buttons[1:])
        self.button = button
        self._keys = buttons
        # track each key's held state
        self._held_multi = dict.fromkeys(buttons, False)

    def _btn_name (self):
        # grab name from attribute name in module.mod
        for attr, val in vars(mod).iteritems():
            if val is self:
                return attr

    _mod_btn_name = _btn_name

    def _update_held (self):
        self._held[0] = any(self._held_multi.itervalues())

    def handle (self, pgevt, mods_match):
        self._held_multi[pgevt.key] = pgevt.type in self.down_pgevts
        self._update_held()
        return False

    def normalise (self):
        """:inherit:"""
        held = pg.key.get_pressed()
        for k in self._keys:
            self._held_multi[k] = held[k]
        self._update_held()


class MouseButton (ButtonInput):
    """Mouse button.

The ``button`` argument is required, and is the mouse button ID.

"""

    device = 'mouse'
    name = 'button'
    pgevts = (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP)
    button_attr = 'button'
    down_pgevts = (pg.MOUSEBUTTONDOWN,)

    def __init__ (self, button, *mods):
        ButtonInput.__init__(self, button, *mods)

    def _btn_name (self):
        return '{0}'.format(self.button)

    def _mod_btn_name (self):
        return 'mouse button {0}'.format(self.button)

    def normalise (self):
        """:inherit:"""
        held = pg.mouse.get_pressed()
        b = self.button - 1
        if b >= len(held):
            print >> sys.stderr, 'warning: cannot determine held state of ' \
                                 '{0}'.format(self)
        # Pygame doesn't return states for some buttons, such as scroll wheels
        held = held[b] if b < len(held) else False
        ButtonInput.set_held(self, held)


class PadButton (ButtonInput):
    """Gamepad button.

PadButton(device_id, button, *mods)

:arg device_id: the gamepad's device ID, either a variable
                (:attr:`device_var <Input.device_var>`) or a non-string ID
                (:attr:`device_id <Input.device_id>`).
:arg button: as taken by :class:`ButtonInput`.
:arg mods: as taken by :class:`ButtonInput`.

"""

    device = 'pad'
    name = 'button'
    pgevts = (pg.JOYBUTTONDOWN, pg.JOYBUTTONUP)
    device_id_attr = 'joy'
    button_attr = 'button'
    down_pgevts = (pg.JOYBUTTONDOWN,)

    def __init__ (self, device_id, button, *mods):
        ButtonInput.__init__(self, button, *mods)
        if isinstance(device_id, basestring):
            self.device_id = None
            self.device_var = device_id
        else:
            self.device_id = device_id

    def _btn_name (self):
        return '{0}, {1}'.format(self._str_dev_id(), self.button)

    def _mod_btn_name (self):
        return 'pad {0} button {1}'.format(self._str_dev_id(), self.button)

    def normalise (self):
        """:inherit:"""
        for j in _pad_matches(self._device_id):
            try:
                held = j.get_button(self.button)
            except pg.error:
                print >> sys.stderr, \
                    'warning: cannot determine held state of {0} (gamepad ' \
                    'not initialised or no such button)'.format(self)
            else:
                ButtonInput.set_held(self, held)


class AxisInput (ButtonInput):
    """Abstract base class representing 2-component axes.

AxisInput([axis][, thresholds], *mods)

:arg axis: axis ID to listen for.  To use this, subclasses must set an
           ``axis_attr`` property to filter by that Pygame event attribute with
           this ID as the value, and with an attribute giving the axis's value.
           Otherwise, they must implement filtering themselves.
:arg thresholds: required if the axis is to act as a button.  For each axis
                 (that is, for each pair of :attr:`Input.components`), this
                 list has two elements: ``down`` followed by ``up``, positive
                 numbers giving the magnitude of the value of the axis in
                 either direction that triggers a button down or up event.  For
                 example, a 2-component axis might have ``(.6, .4)``.

                 A subclass with more than 2 components may pass a length-2
                 sequence here, which is expanded by assuming the same
                 thresholds for each axis.
:arg mods: as taken by :class:`ButtonInput`.  Only used if this axis is treated
           as a button.

Subclasses must have an even number of components.

"""

    components = 2

    def __init__ (self, axis = None, thresholds = None, *mods):
        self._pos = [0] * self.components
        if mods and thresholds is None:
            raise TypeError('an AxisInput must have thresholds defined to '
                            'have modifiers')
        ButtonInput.__init__(self, None, *mods)
        self.provides['axis'] = True
        if hasattr(self, 'axis_attr'):
            if axis is None:
                raise TypeError('expected axis argument')
            self.filter(self.axis_attr, axis)
        #: Axis ID, as passed to the constructor.
        self.axis = axis
        # same threshold for each axis if only given for one
        if thresholds is not None:
            if len(thresholds) == 2:
                thresholds *= (self.components // 2)
            if len(thresholds) != self.components:
                raise ValueError('invalid number of threshold arguments')
        else:
            # ButtonInput sets this to True
            self.provides['button'] = False
        #: As passed to the constructor.
        self.thresholds = thresholds
        self.deadzone = 0

    @property
    def pos (self):
        """Sequence of positions for each axis."""
        p = self._pos
        return [p[i + 1] - p[i] for i in xrange(self.components // 2)]

    @pos.setter
    def pos (self, pos):
        for axis, apos in enumerate(pos):
            if self.axis_motion(True, axis, apos):
                # HACK
                for evt in self.evts:
                    evt._changed = True

    @property
    def deadzone (self):
        """Axis value magnitude below which the value is mapped to ``0``;
defaults to ``0``.

Above this value, the mapped value increases linearly from ``0``.

"""
        return self._deadzone

    @deadzone.setter
    def deadzone (self, dz):
        n = self.components // 2
        if isinstance(dz, (int, float)):
            dz = (dz,) * n
        else:
            dz = tuple(dz)
        if len(dz) != n:
            raise ValueError('{0} deadzone must have {1} components'
                             .format(type(self).__name__, n))
        if any(x < 0 or x >= 1 for x in dz):
            raise ValueError('require 0 <= deadzone < 1')
        self._deadzone = dz

    def axis_motion (self, mods_match, axis, apos, btn_evts=False):
        """Signal a change in axis position.

:arg mods_match: as taken by :meth:`handle`.
:arg axis: the index of the axis to modify (a 2-component :class:`AxisInput`
           has one axis, with index ``0``).
:arg apos: the new axis position (``-1 <= apos <= 1``).
:arg btn_evts: whether to trigger button events (if possible).

"""
        # get magnitude in each direction
        pos = [0, 0]
        if apos > 0:
            pos[1] = apos
        else:
            pos[0] = -apos
        # apply deadzone (linear scale up from it)
        dz = self._deadzone
        for i in (0, 1):
            pos[i] = max(0, pos[i] - dz[axis]) / (1 - dz[axis]) # know dz != 1
        imn = 2 * axis
        imx = 2 * (axis + 1)
        old_pos = self._pos
        if pos != old_pos[imn:imx]:
            if self.provides['button']:
                # act as button
                down, up = self.thresholds[imn:imx]
                l = list(zip(xrange(imn, imx), old_pos[imn:imx], pos))
                # all up (towards 0/centre) first, then all down, to end up
                # held if move down
                for i, old, new in l:
                    if self._held[i] and old > up and new <= up:
                        self.up(i, btn_evts)
                if mods_match:
                    for i, old, new in l:
                        if old < down and new >= down:
                            self.down(i, btn_evts)
            for i, j in enumerate(xrange(imn, imx)):
                old_pos[j] = pos[i]
            return True
        else:
            # neither magnitude changed
            return False

    def handle (self, pgevt, mods_match):
        """:meth:`ButtonInput.handle`.

If a subclass has an ``axis_val_attr`` attribute, this value of this attribute
in the Pygame event is used as a list of axis positions (or just one, if a
number).  Otherwise, this method does nothing.

"""
        rtn = Input.handle(self, pgevt)
        if hasattr(self, 'axis_val_attr'):
            apos = getattr(pgevt, self.axis_val_attr)
            if isinstance(apos, (int, float)):
                apos = (apos,)
            if len(apos) != self.components // 2:
                raise ValueError(
                    'the event attribute given by the axis_val_attr attribute'
                    'has the wrong number of components'
                )
            for i, apos in enumerate(apos):
                rtn |= self.axis_motion(mods_match, i, apos, True)
        return rtn


class PadAxis (AxisInput):
    """Gamepad axis.

PadAxis(device_id, axis[, thresholds], *mods)

:arg device_id: the gamepad's device ID, either a variable
                (:attr:`device_var <Input.device_var>`) or a non-string ID
                (:attr:`device_id <Input.device_id>`).
:arg axis: as taken by :class:`AxisInput`.
:arg thresholds: as taken by :class:`AxisInput`.
:arg mods: as taken by :class:`ButtonInput`.

"""

    device = 'pad'
    name = 'axis'
    device_id_attr = 'joy'
    pgevts = (pg.JOYAXISMOTION,)
    axis_attr = 'axis'
    axis_val_attr = 'value'

    def __init__ (self, device_id, axis, thresholds = None, *mods):
        AxisInput.__init__(self, axis, thresholds, *mods)
        if isinstance(device_id, basestring):
            self.device_id = None
            self.device_var = device_id
        else:
            self.device_id = device_id

    def _mod_btn_name (self):
        return 'pad {0} axis {1}'.format(self._str_dev_id(), self.axis)

    def __str__ (self):
        return self._str('{0}, {1}'.format(self._str_dev_id(), self.axis))

    def normalise (self):
        """:inherit:"""
        for j in _pad_matches(self._device_id):
            try:
                apos = j.get_axis(self.axis)
            except pg.error:
                print >> sys.stderr, \
                    'warning: cannot determine held state of {0} (gamepad ' \
                    'not initialised or no such axis)'.format(self)
            else:
                self.pos = (apos,)


class PadHat (AxisInput):
    """Gamepad hat.

PadHat(device_id, axis[, thresholds], *mods)

:arg device_id: the gamepad's device ID, either a variable
                (:attr:`device_var <Input.device_var>`) or a non-string ID
                (:attr:`device_id <Input.device_id>`).
:arg hat: the hat ID to listen for.
:arg thresholds: as taken by :class:`AxisInput`.
:arg mods: as taken by :class:`ButtonInput`.

"""

    components = 4
    device = 'pad'
    name = 'hat'
    device_id_attr = 'joy'
    pgevts = (pg.JOYHATMOTION,)
    axis_attr = 'hat'
    axis_val_attr = 'value'

    def __init__ (self, device_id, hat, thresholds = None, *mods):
        AxisInput.__init__(self, hat, thresholds, *mods)
        if isinstance(device_id, basestring):
            self.device_id = None
            self.device_var = device_id
        else:
            self.device_id = device_id

    def _mod_btn_name (self):
        return 'pad {0} hat {1}'.format(self._str_dev_id(), self.axis)

    def __str__ (self):
        return self._str('{0}, {1}'.format(self._str_dev_id(), self.axis))

    def normalise (self):
        """:inherit:"""
        for j in _pad_matches(self._device_id):
            try:
                apos = j.get_hat(self.axis)
            except pg.error:
                print >> sys.stderr, \
                    'warning: cannot determine held state of {0} (gamepad ' \
                    'not initialised or no such hat)'.format(self)
            else:
                self.pos = (apos,)


class RelAxisInput (AxisInput):
    """Abstract base class representing 2-component relative axes.

RelAxisInput([relaxis][, bdy][, thresholds][, mods])

:arg relaxis: axis ID to listen for.  To use this, subclasses must set a
              ``relaxis_attr`` property to filter by that Pygame event
              attribute with this ID as the value, and with an attribute giving
              the axis's value.  Otherwise, they must implement filtering
              themselves.
:arg bdy: required if the relative axis is to act as an axis.  For each axis
          (each 2 components), this sequence contains a positive number giving
          the maximum magnitude of the axis.  The normalised axis position is
          then obtained by dividing by this value.
:arg thresholds: as taken by :class:`AxisInput`.
:arg mods: as taken by :class:`ButtonInput`.

A relative axis is one where events convey a change in the axis's value, rather
than its absolute position.  Subclasses must have an even number of components.

Note that using the same component of an instance of a subclass for two
different events (or using the same component twice for a single
:class:`MultiEvent <engine.evt.evts.MultiEvent>`) is not supported, and
behaviour in this case is undefined.

"""

    components = 2

    def __init__ (self, relaxis = None, bdy = None, thresholds = None, *mods):
        #: The change in each component since last :meth:`reset`.
        self.rel = [0, 0] * (self.components // 2)
        AxisInput.__init__(self, None, thresholds, *mods)
        self.provides['relaxis'] = True
        if hasattr(self, 'relaxis_attr'):
            if relaxis is None:
                raise TypeError('expected relaxis argument')
            self.filter(self.relaxis_attr, relaxis)
        #: Axis ID, as passed to the constructor.
        self.relaxis = relaxis
        if bdy is not None:
            if isinstance(bdy, (int, float)):
                bdy = (bdy,) * (self.components // 2)
            if len(bdy) != self.components // 2:
                raise ValueError('invalid number of bdy arguments')
            if any(b <= 0 for b in bdy):
                raise ValueError('all bdy elements must be greater than zero')
        else:
            # AxisInput sets this to True
            self.provides['axis'] = False
        #: As taken by the constructor.
        self.bdy = bdy

    def handle (self, pgevt, mods_match):
        """:inherit:"""
        rtn = Input.handle(self, pgevt)
        if hasattr(self, 'relaxis_val_attr'):
            rpos = getattr(pgevt, self.relaxis_val_attr)
            rel = self.rel
            # split relative axis motion into magnitudes in each direction
            for i in xrange(self.components // 2):
                if rpos[i] > 0:
                    rel[2 * i + 1] += rpos[i]
                else:
                    rel[2 * i] -= rpos[i]
            if self.provides['axis']:
                # act as axis (add relative pos to current pos)
                for i, (bdy, rpos) in enumerate(zip(self.bdy, rpos)):
                    # normalise and restrict magnitude to 1
                    apos = float(rpos) / bdy + self._pos[2 * i + 1] - \
                           self._pos[2 * i]
                    sgn = 1 if apos > 0 else -1
                    apos = sgn * min(sgn * apos, 1)
                    rtn |= self.axis_motion(mods_match, i, apos)
            else:
                rtn |= any(rpos)
        return rtn

    def reset (self, *components):
        """Reset values in :attr:`rel` to ``0`` for the given components.

Called by the owning :class:`Event <engine.evt.evts.Event>`.

If no components are given, reset in all components.

"""
        if not components:
            components = xrange(self.components)
        for c in components:
            self.rel[c] = 0

    def normalise (self):
        """:inherit:"""
        self.reset()
        self.pos = (0,) * (self.components // 2)
        self._held = [False] * self.components


class MouseAxis (RelAxisInput):
    """Represents both mouse axes.

MouseAxis([bdy][, thresholds], *mods)

:arg bdy: as taken by :class:`RelAxisInput`.
:arg thresholds: as taken by :class:`AxisInput`.
:arg mods: as taken by :class:`ButtonInput`.

"""

    components = 4
    device = 'mouse'
    name = 'axis'
    pgevts = (pg.MOUSEMOTION,)
    relaxis_val_attr = 'rel'

    def __init__ (self, bdy = None, thresholds = None, *mods):
        if isinstance(bdy, int):
            bdy = (bdy, bdy)
        RelAxisInput.__init__(self, None, bdy, thresholds, *mods)

    def _mod_btn_name (self):
        return 'mouse axis'

    def __str__ (self):
        return self._str('')


class _mod (object):
    @property
    def CTRL (self):
        return _SneakyMultiKbdKey(pg.KMOD_CTRL, pg.K_LCTRL, pg.K_RCTRL)

    @property
    def SHIFT (self):
        return _SneakyMultiKbdKey(pg.KMOD_SHIFT, pg.K_LSHIFT, pg.K_RSHIFT)

    @property
    def ALT (self):
        return _SneakyMultiKbdKey(pg.KMOD_ALT, pg.K_LALT, pg.K_RALT)

    @property
    def META (self):
        return _SneakyMultiKbdKey(pg.KMOD_META, pg.K_LMETA, pg.K_RMETA)

#: Contains objects that act as specific keyboard modifiers: CTRL, SHIFT, ALT,
#: META.
mod = _mod()
