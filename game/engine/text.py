"""Multi-line text rendering."""

import pygame as pg

from .conf import conf
from .util import normalise_colour

#: Default values for text rendering options.  Value::
#:
#:  {
#:      'colour': '000',
#:      'shadow': None,
#:      'width': None,
#:      'just': 0,
#:      'minimise': False,
#:      'line_spacing': 0,
#:      'aa': True,
#:      'bg': None,
#:      'pad': (0, 0, 0, 0),
#:      'wrap': 'char'
#:  }
# be sure to update res._mk_text_keys if these change
option_defaults = {
    'text_size': 12,
    'colour': '000',
    'shadow': None,
    'width': None,
    'just': 0,
    'minimise': False,
    'line_spacing': 0,
    'aa': True,
    'bg': (0, 0, 0, 0),
    'pad': (0, 0, 0, 0),
    'wrap': 'char'
}


class TextRenderer (object):
    """Render text to a surface.

TextRenderer(font, options={}, pool=conf.DEFAULT_RESOURCE_POOL,
             res_mgr=conf.GAME.resources)

:arg font: font filename to use, under :data:`conf.FONT_DIR`.
:arg options: dict giving rendering parameters.  These act as default values in
              the same argument to :meth:`render`.  All options can be
              retrieved as properties of this instance (and all are guaranteed
              to exist), but cannot be changed.
:arg pool: :class:`ResourceManager <engine.res.ResourceManager>` resource pool
           name to cache any loaded Pygame fonts in.
:arg res_mgr: :class:`ResourceManager <engine.res.ResourceManager>` instance to
              use to load any Pygame fonts.

"""

    def __init__ (self, font, options={}, pool=conf.DEFAULT_RESOURCE_POOL,
                  res_mgr=None):
        self._font = font
        self._defaults = option_defaults.copy()
        self._defaults.update(options)
        self.normalise_options(self._defaults)
        self._resource_pool = pool
        self._resource_manager = res_mgr

    def __eq__ (self, other):
        # equal if we would render the exact same thing
        if isinstance(other, TextRenderer):
            return (self._font == other._font and
                    self._defaults == other._defaults)
        else:
            return False

    def __getattr__ (self, attr):
        if attr in option_defaults:
            return self._defaults.get(attr, option_defaults[attr])
        else:
            return object.__getattribute__(self, attr)

    def _get_font (self, opts):
        # load the font required for the given (normalised) options
        if self._resource_manager is None:
            resources = conf.GAME.resources
        else:
            resources = self._resource_manager
        return resources.font(self._font, opts['text_size'],
                              pool=self._resource_pool)

    def render (self, text, options={}, **kwargs):
        """Render text to a surface.

render(text, options={}, **kwargs) -> (surface, num_lines)

:arg text: text to render; may contain line breaks to display separate lines.
:arg options: dict giving rendering parameters; those omitted default to the
              value given in the ``options`` argument to the constructor, and
              then the values in :data:`option_defaults`.
:arg kwargs: options can also be passed as keyword arguments, with the option's
             name as the argument's name.  If an option is given both in
             ``options`` and as a keyword argument, the keyword argument takes
             precedence.

Options available:

:arg text_size: text size, in points.
:arg colour: text colour, as taken by
             :func:`util.normalise_colour <engine.util.normalise_colour>`.
             Alpha seems to be unsupported by Pygame.
:arg shadow: to draw a drop-shadow: ``(colour, offset)`` tuple, where
             ``offset`` is ``(x, y)``.
:arg width: maximum width of returned surface (also see ``wrap``).  This
            excludes padding (``pad``).
:arg just: if the text has multiple lines, justify: ``0`` = left, ``1`` =
           centre, ``2`` = right.
:arg minimise: if width is set, treat it as a minimum instead of absolute width
               (that is, shrink the surface after, if possible).
:arg line_spacing: space between lines, in pixels.
:arg aa: whether to anti-alias the text.
:arg bg: background colour.
:arg pad: ``(left, top, right, bottom)`` padding in pixels.  Can also be one
          number for all sides or ``(left_and_right, top_and_bottom)``.  This
          treats shadow as part of the text.
:arg wrap:
    text wrapping mode (only used if ``width`` is given); one of:

        - ``'char'`` (default): wrap words and wrap within words if necessary.
        - ``'word'``: wrap words only; raises ``ValueError`` if any words won't
          fit on a single line.
        - ``'none'``: don't wrap: if ``width`` is given, allow text to fall off
          the end of the surface.

:return: ``surface`` is the ``pygame.Surface`` containing the rendered text and
         ``num_lines`` is the final number of lines of text.

"""
        opts = self.mk_options(options, **kwargs)
        self.normalise_options(opts)
        font = self._get_font(opts)
        colour = normalise_colour(opts['colour'])
        if opts['shadow'] is None:
            shadow_colour = None
            offset = (0, 0)
        else:
            shadow_colour, offset = opts['shadow']
        just = opts['just']
        minimise = opts['minimise']
        if opts['width'] is None:
            minimise = True
        line_spacing = opts['line_spacing']
        aa = opts['aa']
        bg = opts['bg']
        pad = opts['pad']

        lines, text_size, sfc_size = self.get_info(text, opts)
        width = text_size[0]

        opaque = len(bg) == 3 or bg[3] == 255
        # simple case: just one line and want to minimise width and no shadow
        # or padding and bg is opaque (Pygame seems not to do alpha bg)
        if (len(lines) == 1 and minimise and pad == (0, 0, 0, 0) and
            shadow_colour is None and opaque):
            sfc = font.render(lines[0], True, colour, bg)
            return (sfc, 1)
        # else create surface to blit all the lines to
        sfc = pg.Surface(sfc_size)
        if not opaque:
            sfc = sfc.convert_alpha()
        sfc.fill(bg)
        # render and blit text
        line_height = font.get_height()
        todo = []
        if shadow_colour is not None:
            todo.append((shadow_colour, offset))
        todo.append((colour, (0, 0)))
        n_lines = 0
        for colour, o in todo:
            o = (o[0] + pad[0], o[1] + pad[1])
            h = 0
            for line in lines:
                if line:
                    n_lines += 1
                    s = font.render(line, aa, colour)
                    if just == 2:
                        sfc.blit(s, (width - s.get_width() + o[0], h + o[1]))
                    elif just == 1:
                        sfc.blit(s, ((width - s.get_width()) // 2 + o[0],
                                     h + o[1]))
                    else:
                        sfc.blit(s, (o[0], h + o[1]))
                h += line_height + line_spacing
        return (sfc, n_lines)

    def get_info (self, text, options={}, **kwargs):
        """Get results for render arguments without actually rendering.

get_info(text, options={}, **kwargs) -> (lines, text_size, sfc_size)

Arguments are as taken by :meth:`render`.

:return:
    - ``lines``: a list of string lines the text would be split into.
    - ``text_size``: the resulting ``(width, height)`` size of the text within
                     the surface that would be returned, excluding any shadow.
    - ``sfc_size``: the resulting size of the surface.

Like :meth:`render`, raises ``ValueError`` if wrapping fails.

"""
        opts = self.mk_options(options, **kwargs)
        self.normalise_options(opts)
        font = self._get_font(opts)
        offset = (0, 0) if opts['shadow'] is None else opts['shadow'][1]
        width = opts['width']
        wrap = opts['wrap']
        pad = opts['pad']

        # split into lines
        lines = text.splitlines()
        if width is not None:
            text = lines
            lines = []
            for line in text:
                if wrap != 'none' and font.size(line)[0] > width:
                    # wrap
                    words = line.split(' ')
                    # check if any words won't fit
                    # can't use for as we'll change the list during iteration
                    i = 0
                    while i < len(words):
                        word = words[i]
                        if font.size(word)[0] > width:
                            if wrap == 'word':
                                raise ValueError('\'{0}\' doesn\'t fit on one '
                                                 'line'.format(word))
                            else: # wrap == 'char'
                                for j in xrange(len(word) - 1, -1, -1):
                                    if font.size(word[:j])[0] <= width:
                                        break
                                else: # can't be an empty string
                                    j = 1
                                words[i] = word[:j]
                                remain = word[j:]
                                if remain:
                                    words.insert(i + 1, remain)
                        i += 1
                    # build line
                    build = ''
                    for word in words:
                        temp = build + ' ' if build else build
                        temp += word
                        if font.size(temp)[0] < width:
                            build = temp
                        else:
                            lines.append(build)
                            build = word
                    lines.append(build)
                else:
                    lines.append(line)
        if width is None or opts['minimise']:
            width = max(font.size(line)[0] for line in lines)

        # compute sizes
        line_height = font.get_height()
        n = len(lines)
        height = max(n * line_height + (n - 1) * opts['line_spacing'], 0)
        sfc_size = (width + abs(offset[0]) + pad[0] + pad[2],
                    height + abs(offset[1]) + pad[1] + pad[3])

        return (lines, (width, height), sfc_size)

    def mk_options (self, options={}, **kwargs):
        """Generate a full set of rendering options given an options dict.

mk_options(options={}, **kwargs) -> new_options

Arguments are as taken by :meth:`render`.

:return: The completed dict of rendering options, with defaults filled in.

"""
        opts = self._defaults.copy()
        opts.update(options, **kwargs)
        return opts

    def normalise_options (self, options={}):
        """Normalise a (possibly incomplete) renderer options dict, in-place.

Arguments are as taken by :meth:`render`.

This involves making every option hashable and putting it in a standard format.

"""
        o = options
        if 'text_size' in o:
            o['text_size'] = int(o['text_size'])
        if 'colour' in o:
            o['colour'] = normalise_colour(o['colour'])
        shadow = o.get('shadow')
        if shadow is not None:
            shadow = (normalise_colour(shadow[0]), tuple(shadow[1][:2]))
        o['shadow'] = shadow
        if o.get('width') is not None:
            o['width'] = int(o['width'])
        if 'just' in o:
            o['just'] = int(o['just'])
        if 'minimise' in o:
            o['minimise'] = bool(o['minimise'])
        if 'line_spacing' in o:
            o['line_spacing'] = int(o['line_spacing'])
        if 'aa' in o:
            o['aa'] = bool(o['aa'])
        if 'bg' in o:
            o['bg'] = normalise_colour(o['bg'])
        if 'pad' in o:
            pad = o['pad']
            if isinstance(pad, int):
                pad = (pad, pad, pad, pad)
            elif len(pad) == 2:
                pad = tuple(pad)
                pad = pad + pad
            else:
                pad = tuple(pad)
            o['pad'] = pad
        if 'wrap' in o and o['wrap'] not in ('char', 'word', 'none'):
            raise ValueError('unknown wrap mode: \'{0}\''.format(o['wrap']))
