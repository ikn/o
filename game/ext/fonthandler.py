"""Font handler by Joseph Lansdowne.

The Fonts class in this module can serve as a font cache, but the real point of
this is to render multi-line text with alignment and shadow and stuff.

Release: 5.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

"""

from os.path import isfile, abspath, sep as path_sep, join as join_path

import pygame


class Fonts (dict):
    """Collection of pygame.font.Font instances.

    CONSTRUCTOR

Fonts(*font_dirs)

font_dirs: directories to find fonts - so you can just pass the font's filename
           when adding a font.

Use the dict interface to register fonts:

    fonts['some name'] = (filename, size[, bold = False])

where the arguments are as taken by pygame.font.Font.  All directories in
font_dirs are searched for the filename, unless it contains a path separator.
If so, or if the search yields no results, it is used as the whole path
(absolute or relative).

Retrieving the font again yields a pygame.font.Font instance.  Assigning two
different names to the same set of arguments makes the same instance available
under both without loading the file twice.

    METHODS

render

    ATTRIBUTES

font_dirs: as given.  You may alter this list directly.

"""

    def __init__ (self, *font_dirs):
        self.font_dirs = list(font_dirs)
        self._fonts_by_args = {}

    def __setitem__ (self, name, data):
        # standardise data so we can be sure whether we already have it
        if len(data) == 2:
            fn, size = data
            bold = False
        else:
            fn, size, bold = data
        size = int(size)
        bold = bool(bold)
        # find font file
        orig_fn, fn = fn, None
        temp_fn = None
        if path_sep not in orig_fn:
            # search registered dirs
            for d in self.font_dirs:
                temp_fn = join_path(d, orig_fn)
                if isfile(temp_fn):
                    fn = temp_fn
                    break
        if fn is None:
            # wasn't in any registered dirs
            fn = orig_fn
        fn = abspath(fn)
        # load this font if we haven't already
        data = (fn, size, bold)
        font = self._fonts_by_args.get(data, None)
        if font is None:
            font = pygame.font.Font(fn, size, bold = bold)
            self._fonts_by_args[data] = font
        # store
        dict.__setitem__(self, name, font)

    def render (self, font, text, colour, shadow = None, width = None,
                just = 0, minimise = False, line_spacing = 0, aa = True,
                bg = None, pad = (0, 0, 0, 0)):
        """Render text from a font.

render(font, text, colour[, shadow][, width], just = 0, minimise = False,
       line_spacing = 0, aa = True[, bg], pad = (0, 0, 0, 0))
    -> (surface, num_lines)

font: name of a registered font.
text: text to render.
colour: (R, G, B) tuple.
shadow: to draw a drop-shadow: (colour, offset) tuple, where offset is (x, y).
width: maximum width of returned surface (wrap text).  ValueError is raised if
       any words are too long to fit in this width.
just: if the text has multiple lines, justify: 0 = left, 1 = centre, 2 = right.
minimise: if width is set, treat it as a minimum instead of absolute width
          (that is, shrink the surface after, if possible).
line_spacing: space between lines, in pixels.
aa: whether to anti-alias the text.
bg: background colour; defaults to alpha.
pad: (left, top, right, bottom) padding in pixels.  Can also be one number for
     all sides or (left_and_right, top_and_bottom).  This treats shadow as part
     of the text.

surface: pygame.Surface containing the rendered text.
num_lines: final number of lines of text.

Newline characters split the text into lines (along with anything else caught
by str.splitlines), as does the width restriction.

"""
        font = self[font]
        lines = []
        if shadow is None:
            offset = (0, 0)
        else:
            shadow_colour, offset = shadow
        if isinstance(pad, int):
            pad = (pad, pad, pad, pad)
        elif len(pad) == 2:
            pad = tuple(pad)
            pad = pad + pad
        else:
            pad = tuple(pad)
        if width is not None:
            width -= pad[0] + pad[2]

        # split into lines
        text = text.splitlines()
        if width is None:
            width = max(font.size(line)[0] for line in text)
            lines = text
            minimise = True
        else:
            for line in text:
                if font.size(line)[0] > width:
                    # wrap
                    words = line.split(' ')
                    # check if any words won't fit
                    for word in words:
                        if font.size(word)[0] >= width:
                            e = '\'{0}\' doesn\'t fit on one line'.format(word)
                            raise ValueError(e)
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
        if minimise:
            width = max(font.size(line)[0] for line in lines)

        # simple case: just one line and no shadow or padding and bg is opaque
        # or fully transparent bg
        if len(lines) == 1 and pad == (0, 0, 0, 0) and shadow is None \
           and (bg is None or len(bg) == 3 or bg[3] in (0, 255)):
            if bg is None:
                sfc = font.render(lines[0], True, colour)
            else:
                sfc = font.render(lines[0], True, colour, bg)
            return (sfc, 1)
        # else create surface to blit all the lines to
        size = font.get_height()
        h = (line_spacing + size) * (len(lines) - 1) + font.size(lines[-1])[1]
        sfc = pygame.Surface((width + abs(offset[0]) + pad[0] + pad[2],
                             h + abs(offset[1]) + pad[1] + pad[3]))
        # to get transparency, need to be blitting to a converted surface
        sfc = sfc.convert_alpha()
        sfc.fill((0, 0, 0, 0) if bg is None else bg)
        # render and blit text
        todo = []
        if shadow is not None:
            todo.append((shadow_colour, 1))
        todo.append((colour, -1))
        n_lines = 0
        for colour, mul in todo:
            o = (max(mul * offset[0] + pad[0], 0),
                 max(mul * offset[1] + pad[1], 0))
            h = 0
            for line in lines:
                if line:
                    n_lines += 1
                    s = font.render(line, aa, colour)
                    if just == 2:
                        sfc.blit(s, (width - s.get_width() + o[0], h + o[1]))
                    elif just == 1:
                        sfc.blit(s, ((width - s.get_width()) / 2 + o[0],
                                     h + o[1]))
                    else:
                        sfc.blit(s, (o[0], h + o[1]))
                h += size + line_spacing
        return (sfc, n_lines)
