import os
from copy import deepcopy
import json
from collections import defaultdict


class JSONEncoder (json.JSONEncoder):
    """Extended json.JSONEncoder with support for sets and defaultdicts."""

    def default (self, o):
        if isinstance(o, set):
            return list(o)
        elif isinstance(o, defaultdict):
            return (o.default_factory(None), dict(o))
        else:
            return json.JSONEncoder.default(self, o)


class DummySettingsManager:
    """An object for handling settings.

    CONSTRUCTOR

DummySettingsManager(settings[, types])

settings: a dict used to store the settings, which are already set to default
          values.
types: the types of settings are preserved when changes are made by casting to
       their initial types.  For types for which this will not work, this
       argument can be passed as a {from_type: to_type} dict to use to_type
       whenever from_type would otherwise be used.

To restore a setting to its default value, delete it.

    METHODS

dump

"""

    def __init__ (self, settings, types):
        self._settings = settings
        self._defaults = deepcopy(settings)
        self._types = ts = {}
        for k, v in self._settings.iteritems():
            t = type(v)
            ts[k] = types.get(t, t)

    def __getattr__ (self, k):
        return self._settings[k]

    def __setattr__ (self, k, v):
        # set if private
        if k[0] == '_':
            self.__dict__[k] = v
            return (True, None)
        # ensure type
        try:
            v = self._types[k](v)
        except (TypeError, ValueError):
            # invalid: fall back to default
            v = self._defaults[k]
        # check if different
        if v == getattr(self, k):
            return (True, None)
        # store
        self._settings[k] = v
        return (False, v)

    def __delattr__ (self, k):
        setattr(self, k, self._defaults[k])

    def dump (self):
        """Force saving all settings."""
        pass


class SettingsManager (DummySettingsManager):
    """An object for handling settings; DummySettingsManager subclass.

    CONSTRUCTOR

SettingsManager(settings, fn, save[, types])

settings, types: as take by DummySettingsManager.
fn: filename to save settings in.
save: a list containing the names of the settings to save to fn (others are
      stored in memory only).

"""

    def __init__ (self, settings, fn, save, types = {}):
        DummySettingsManager.__init__(self, settings, types)
        self._fn = fn
        # create directory
        d = os.path.dirname(fn)
        try:
            os.makedirs(d)
        except OSError, e:
            if e.errno != 17: # 17 means already exists
                print 'warning: can\'t create directory: \'{0}\''.format(d)
        # load settings
        try:
            with open(fn) as f:
                settings = json.load(f)
        except IOError:
            print 'warning: can\'t read file: \'{0}\''.format(self._fn)
            settings = {}
        except ValueError:
            print 'warning: invalid JSON: \'{0}\''.format(self._fn)
            settings = {}
        for k, v in settings.iteritems():
            if k in save:
                DummySettingsManager.__setattr__(self, k, v)
        settings = self._settings
        self._save = dict((k, settings[k]) for k in save)

    def __setattr__ (self, k, v):
        done, v = DummySettingsManager.__setattr__(self, k, v)
        if done:
            return
        # save to file
        if k in self._save:
            print 'info: saving setting: \'{0}\''.format(k)
            self._save[k] = v
            self.dump(False)

    def dump (self, public = True):
        """Force saving all settings."""
        if public:
            print 'info: saving settings'
        try:
            with open(self._fn, 'w') as f:
                json.dump(self._save, f, indent = 4, cls = JSONEncoder)
        except IOError:
            print 'warning: can\'t write to file: \'{0}\''.format(self._fn)
