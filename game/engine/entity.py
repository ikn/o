"""Entities: things that exist in the world."""

from .gfx import GraphicsGroup
from .util import ir


class Entity (object):
    """A thing that exists in the world.

Entity()

Currently, an entity is just a container of graphics.

"""

    def __init__ (self):
        #: The :class:`World <engine.game.World>` this entity is in.  This is
        #: set by the world when the entity is added or removed.
        self.world = None
        #: :class:`GraphicsGroup <engine.gfx.container.GraphicsGroup>`
        #: containing the entity's graphics, with ``x=0``, ``y=0``.
        self.graphics = GraphicsGroup()

    def added (self):
        """Called whenever the entity is added to a world.

This is called after :attr:`world` has been changed to the new world.

"""
        pass

    def update (self):
        """Called every frame to makes any necessary changes."""
        pass
