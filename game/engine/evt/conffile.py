"""Parse configuration strings to events and vice versa.

A configuration string defines events, which contain inputs.  If an input or
event class has a ``name`` attribute, it is 'named' and is supported in
configuration strings (these can be found in :data:`inputs_by_name` and
:data:`evts_by_name`).

Commenting is shell syntax: the ``#`` character indicates that the rest of the
line is a comment, unless it is quoted.  Whitespace outside of quotes
(including blank lines) is ignored.

Events
------

Each event line is followed by zero or more input lines which are added to that
event.  Lines are made up of words, and shell-like quoting is supported.  An
event line follows the form

.. code-block:: none

    <type> <name> [args...]

where ``<type>`` is the class's ``name`` attribute (a key in
:data:`evts_by_name`) and ``<name>`` is the name to give to the event
(see :meth:`EventHandler.add() <engine.evt.handler.EventHandler.add>`).
``args`` depends on ``type``:

- ``button*`` events take any number of button modes from
  :class:`evts.bmode <engine.evt.evts.bmode>` (``DOWN``, ``HELD``, etc.).
  If ``REPEAT`` is included, the initial and repeat delays must follow these,
  in seconds.  If ``DBLCLICK`` is included, the double-click delay must follow,
  in seconds
- other event types take no extra arguments.

Inputs
------

Input lines follow the form

.. code-block:: none

    [event components...] [modifiers...] [scale*]<device> [device ID] \
[type[:input components...]] [args...]

where:

- ``event components`` are named components of the event this input is inside
  to attach the input to (see
  :data:`evts.evt_component_names <engine.evt.evts.evt_component_names>`).  If
  none are given, all components of the event are used in order.
- ``modifiers`` is zero or more whitespace-separated modifier definitions.
  Each is within square ``[]`` brackets and is an input definition.  The device
  must match the input (see
  :data:`inputs.mod_devices <engine.evt.inputs.mod_devices>`), and may be
  omitted if it is the same.  The device ID should be omitted, as it must be
  the same as the input's.  A modifier may also be one of the names in
  :class:`inputs.mod <engine.evt.inputs.mod>`.
- ``scale`` is required for events of type ``'relaxis*'`` (see
  :class:`RelAxis <engine.evt.evts.RelAxis>`) and no others (the ``*`` in this
  argument is a literal character).
- ``device`` is the ``device`` attribute of the input class, found in
  :data:`inputs_by_name`.
- ``device ID`` determines which device to listen for input from, and defaults
  to ``True`` (see
  :attr:`Input.device_id <engine.evt.inputs.Input.device_id>`).  This is only
  allowed for inputs with ``device`` ``'pad'``.  This may also be a device
  variable (:attr:`Input.device_var <engine.evt.inputs.Input.device_var>`) in
  ``<>``, eg. ``'<x>'`` for variable ``'x'``.
- ``type`` is the ``name`` attribute of the input class, found in
  :data:`inputs_by_name`.  It may be omitted if the given ``device`` has only
  one possible ``type``.
- ``input components`` defines the components of the input to use as a
  comma-separated string of indices.  The number given must match up with
  ``event components``, and the default is all components of the input, in
  order.
- ``args`` depends on ``device`` and ``type``:

    - ``kbd key``, ``mouse button`` and ``pad *`` take a key/button ID.  As
      well as number identifiers, keys may be Pygame names (without the ``K_``
      prefix) and mouse buttons may be names in
      :class:`inputs.mbtn <engine.evt.inputs.mbtn>`.
    - if the event is an axis or a button,
      :class:`RelAxisInput <engine.evt.inputs.RelAxisInput>` subclasses take a
      ``boundary`` argument giving the maximum displacement of the axis from
      ``0``.
    - if the event is a button,
      :class:`AxisInput <engine.evt.inputs.AxisInput>` and
      :class:`RelAxisInput <engine.evt.inputs.RelAxisInput>` subclasses take
      thresholds arguments ``down`` and ``up``, giving the point at which the
      button is triggered and released.

  These are taken by the input classes, so see their documentation for more
  details.

Examples
--------

This defines a number of input methods for a ``'walk'`` event:

.. code-block:: sh

    axis walk
       neg kbd LEFT
       pos kbd RIGHT
       # WASD
       neg kbd a
       pos kbd d
       neg pos pad axis 0
       # axis value depends on mouse position
       neg pos mouse axis:0,1 100

The following defines tile-like movement (also useful for menus).

.. code-block:: sh

    button4 move DOWN REPEAT .3 .2
        left kbd LEFT
        right kbd RIGHT
        up kbd UP
        down kbd DOWN
        # recall that .6 .4 are axis toggle thresholds
        left right pad axis 0 .6 .4
        up down pad axis 1 .6 .4

    # hold a button to speed up
    button4 move_fast DOWN REPEAT .2 .1
        left [CTRL] kbd LEFT
        right [CTRL] kbd RIGHT
        up [CTRL] kbd UP
        down [CTRL] kbd DOWN
        # modifier might be a shoulder button or something
        left right [button 4] pad axis 0 .6 .4
        up down [button 4] pad axis 1 .6 .4

This might be useful for moving a cursor (note that the mouse is treated
differently than for the ``axis`` event above):

.. code-block:: sh

    relaxis2 move
        left 5*kbd LEFT
        right 5*kbd RIGHT
        up 5*kbd UP
        down 5*kbd DOWN
        left right 5*pad axis 0
        up down 5*pad axis 1
        left right mouse axis:0,1
        up down mouse axis:2,3

RTS-like unit selection:

.. code-block:: sh

    # drag out a box to select units
    button select DOWN UP
        mouse button LEFT

    # hold ctrl to drag out another box and add to the selection
    button add DOWN UP
        [CTRL] mouse button LEFT

    # order selected units to do something
    button action DOWN
        mouse button RIGHT

Reference
---------

"""

import sys
import shlex
from StringIO import StringIO

import pygame as pg

from . import inputs, evts

#: A ``{cls.device: {cls.name: cls}}`` dict of usable named
#: :class:`Input <engine.evt.inputs.Input>` subclasses.
inputs_by_name = {}
for i in vars(inputs).values(): # copy or it'll change size during iteration
    if (isinstance(i, type) and not i.__name__.startswith('_') and
        issubclass(i, inputs.Input) and hasattr(i, 'name')):
        inputs_by_name.setdefault(i.device, {})[i.name] = i
del i
#: A ``{cls.name: cls}`` dict of usable named
#: :class:`BaseEvent <engine.evt.evts.BaseEvent>` subclasses.
evts_by_name = dict(
    (evt.name, evt) for evt in vars(evts).values()
    if (isinstance(evt, type) and
        (issubclass(evt, evts.BaseEvent) and hasattr(evt, 'name')))
)

_input_identifiers = {
    inputs.KbdKey: lambda k: getattr(pg, 'K_' + k),
    inputs.MouseButton: lambda k: getattr(inputs.mbtn, k),
    inputs.PadButton: {}.__getitem__,
    inputs.PadAxis: {}.__getitem__,
    inputs.PadHat: {}.__getitem__
}


def _parse_input (lnum, n_components, words, scalable, device = None,
                  device_id = None):
    # parse an input declaration line; words is non-empty; returns input
    # find the device
    device_i = None
    for i, w in enumerate(words):
        if scalable and '*' in w:
            w = w[w.find('*') + 1:]
        if w in inputs_by_name:
            device_i = i
            break
    if device_i is None:
        if device is None:
            raise ValueError('line {0}: input declaration contains no '
                             'device'.format(lnum))
        # else device was given, so may omit it
        pre_dev = []
    else:
        device = words[device_i]
        pre_dev = words[:device_i]
        words = words[device_i + 1:]
    # parse relaxis scale
    scale = None
    if scalable and '*' in device:
        i = device.find('*')
        scale_s = device[:i]
        device = device[i + 1:]
        if i:
            try:
                scale = float(scale_s)
            except ValueError:
                raise ValueError('line {0}: invalid scaling value'
                                 .format(lnum))
    # everything before device and before the first '[' is a component
    for w_i, w in enumerate(pre_dev):
        if w.startswith('['):
            # found a modifier
            break
    else:
        w_i = len(pre_dev) # else will be (len - 1)
    evt_components = pre_dev[:w_i]
    if not evt_components:
        # use all components: let the event check for mismatches
        evt_components = None
    # separate out modifiers
    all_mod_words = []
    in_mod = False
    for w in pre_dev[w_i:]:
        if not in_mod:
            if w.startswith('['):
                # start of mod
                in_mod = True
                mod_words = []
                w = w[1:]
            else:
                raise ValueError('line {0}: expected a modifier, got \'{1}\''
                                 .format(lnum, w))
        if in_mod:
            if w.endswith(']'):
                # end of mod
                if w[:-1]:
                    mod_words.append(w[:-1])
                all_mod_words.append(mod_words)
                in_mod = False
            else:
                # continuation
                mod_words.append(w)
    if in_mod:
        raise ValueError('line {0}: mod not closed'.format(lnum))

    # find the name
    names = inputs_by_name[device]
    name_i = None
    for i, w in enumerate(words):
        if ':' in w:
            w = w[:w.find(':')]
        if w in names:
            name_i = i
            break
    input_components = None
    if name_i is None:
        name = None
    else:
        name = words[name_i]
        # parse input components
        if ':' in name:
            i = name.find(':')
            ics_s = name[i + 1:]
            name = name[:i]
            if ics_s:
                # comma-separated ints
                try:
                    # int() handles whitespace fine
                    input_components = [int(ic) for ic in ics_s.split(',')]
                except ValueError:
                    raise ValueError('line {0}: invalid input components'
                                     .format(lnum))
    if not name:
        # name empty or entire argument omitted
        if len(names) == 1:
            # but there's only one choice
            name = names.keys()[0]
        else:
            raise ValueError('line {0}: input declaration contains no name'
                             .format(lnum))
    cls = names[name]
    # only device ID preceeds name
    if name_i is None or name_i == 0:
        device_id = True
    elif name_i == 1:
        if device_id is not None:
            print >> sys.stderr, 'warning: got device ID for modifier; ' \
                                 'ignoring'
        else:
            if cls not in (inputs.PadButton, inputs.PadAxis, inputs.PadHat):
                print >> sys.stderr, 'warning: got device ID for input ' \
                                     'that doesn\'t support it; ignoring'
            device_id = words[0]
            if device_id and device_id[0] == '<' and device_id[-1] == '>':
                device_id = device_id[1:-1]
            else:
                try:
                    device_id = int(device_id)
                except ValueError:
                    raise ValueError('line {0}: invalid device ID: \'{1}\''
                                     .format(lnum, device_id))
    else:
        raise ValueError('line {0}: too many arguments between device and name'
                         .format(lnum))
    if name_i is not None:
        words = words[name_i + 1:]

    # now just arguments remain
    if cls in (inputs.PadButton, inputs.PadAxis, inputs.PadHat):
        args = [device_id]
    else:
        args = []
    if cls in _input_identifiers:
        # first is an identifier
        src = _input_identifiers[cls]
        if not words:
            raise ValueError('line {0}: too few arguments'.format(lnum))
        try:
            ident = src(words[0])
        except (AttributeError, KeyError):
            try:
                ident = int(words[0])
            except ValueError:
                raise ValueError('line {0}: invalid {1} code'
                                 .format(lnum, name))
        args.append(ident)
        words = words[1:]
    if cls in (inputs.KbdKey, inputs.MouseButton, inputs.PadButton):
        # no more args
        if words:
            raise ValueError('line {0}: too many arguments'.format(lnum))
    elif cls in (inputs.PadAxis, inputs.PadHat, inputs.MouseAxis):
        if cls is inputs.MouseAxis:
            # next arg is optional boundary
            if words:
                try:
                    bdy = float(words[0])
                except ValueError:
                    raise ValueError('line {0}: invalid \'boundary\' argument'
                                     .format(lnum))
                words = words[1:]
            else:
                bdy = None
            args.append(bdy)
        # next args are optional thresholds
        thresholds = []
        if words:
            # let the input check values/numbers of components
            for w in words:
                try:
                    thresholds.append(float(w))
                except ValueError:
                    raise ValueError('line {0}: invalid \'threshold\' argument'
                                     .format(lnum))
        if not thresholds:
            thresholds = None
        args.append(thresholds)

    # parse modifiers and add to args
    mod_num = 1
    for mod_words in all_mod_words:
        if len(mod_words) == 1 and hasattr(inputs.mod, mod_words[0]):
            # got a multi-modifier
            mod_i = getattr(inputs.mod, mod_words[0])
            mod_ics = (0,)
        else:
            # parse the mod's words like any other input
            mod_i, mod_ecs, mod_ics = _parse_input(
                '{0}[mod {1}]'.format(lnum, mod_num), 1, mod_words, False,
                device, device_id
            )
            mod_num += 1
            if (mod_ecs not in (None, (0,)) or
                (mod_ics is None and mod_i.components > 1) or
                (mod_ics is not None and len(mod_ics) > 1)):
                raise ValueError('line {0}: modifier cannot use more '
                                 'than one component'.format(lnum))
            if mod_ics is None:
                # mod_i has 1 component, so use that
                mod_ics = (0,)
        # now mod_ics is a length-1 sequence (can never be length-0)
        args.append((mod_i, mod_ics[0]))

    return ((() if scale is None else (scale,)) +
            (cls(*args), evt_components, input_components))


def _parse_evthead (lnum, words):
    # parse first line of an event declaration
    # words is non-empty and first is guaranteed to be a valid event type
    # returns (cls, name, args)
    evt_type = words[0]
    # get name
    if len(words) < 2:
        raise ValueError('line {0}: expected name for event'.format(lnum))
    name = words[1]
    if not name:
        raise ValueError('line {0}: invalid event name: \'{0}\''.format(lnum))
    words = words[2:]
    # parse args according to event type
    args = []
    kwargs = {}
    if evt_type in ('axis', 'axis2', 'relaxis', 'relaxis2'):
        if words:
            raise ValueError('line {0}: axis and relaxis events take no '
                             'arguments'.format(lnum))
    elif evt_type in ('button', 'button2', 'button4'):
        # args are modes, last few may be repeat/double-click delays
        delays = []
        for i in xrange(len(words)):
            if hasattr(evts.bmode, words[i]):
                args.append(getattr(evts.bmode, words[i]))
            else:
                # check for float
                if i < len(words) - 3:
                    raise ValueError('line {0}: invalid event arguments'
                                     .format(lnum))
                # got one: do the last part of the loop
                for w in words[i:]:
                    try:
                        delays.append(float(w))
                    except ValueError:
                        raise ValueError('line {0}: invalid event arguments'
                                         .format(lnum))
                break
        # work out which delay is which
        kwargs.update(dict(zip([
            (),
            ('dbl_click_time',),
            ('initial_delay', 'repeat_delay'),
            ('dbl_click_time', 'initial_delay', 'repeat_delay'),
        ][len(delays)], delays)))
    else:
        raise ValueError('line {0}: unknown event type \'{1}\''
                         .format(lnum, evt_type))
    return (evts_by_name[evt_type], name, args, kwargs)


def parse (config):
    """Parse an event configuration.

parse(config) -> parsed

:arg config: an open file-like object (with a ``readline`` method).

:return: ``{name: event}`` for each named
         :class:`BaseEvent <engine.evt.evts.BaseEvent>` instance.

"""
    parsed = {} # events
    evt_cls = None
    lnum = 1
    while True:
        line = config.readline()
        if not line:
            # end of file
            break
        words = shlex.split(line, True)
        if words:
            if words[0] in evts_by_name:
                # new event: create and add current event
                if evt_cls is not None:
                    parsed[evt_name] = evt_cls(*args, **kwargs)
                evt_cls, evt_name, args, kwargs = _parse_evthead(lnum, words)
                if evt_name in parsed:
                    raise ValueError('line {0}: duplicate event name: \'{1}\''
                                     .format(lnum, evt_name))
                scalable = evt_cls.name in ('relaxis', 'relaxis2')
            else:
                if evt_cls is None:
                    raise ValueError('line {0}: expected event'.format(lnum))
                # input line
                if issubclass(evt_cls, evts.MultiEvent):
                    n_cs = evt_cls.multiple * evt_cls.child.components
                else:
                    n_cs = evt_cls.components
                args.append(_parse_input(lnum, n_cs, words, scalable))
        # else blank line
        lnum += 1
    if evt_cls is not None:
        parsed[evt_name] = evt_cls(*args, **kwargs)
    return parsed


def parse_s (config):
    """Parse an event configuration from a string.

parse(config) -> parsed

:arg config: the string to parse

:return: ``{name: event}`` for each named
         :class:`BaseEvent <engine.evt.evts.BaseEvent>` instance.

"""
    return parse(StringIO(config))
