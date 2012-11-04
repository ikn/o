"""Event scheduler by Joseph Lansdowne.

Uses Pygame's wait function if available, else the less accurate time.sleep.
To use something else, do:

import sched
sched.wait = wait_function

This function should take the number of milliseconds to wait for.  This will
always be an integer.

Python version: 2.
Release: 6-dev.

Licensed under the GNU General Public License, version 3; if this was not
included, you can find it here:
    http://www.gnu.org/licenses/gpl-3.0.txt

    CLASSES

Timer
Scheduler

"""

from time import time

try:
    from pygame.time import wait
except ImportError:
    from time import sleep

    def wait (t):
        sleep(int(t * 1000))


class Timer:
    """Simple timer.

Either call run once and stop if you need to, or step every time you've done
what you need to.

    CONSTRUCTOR

Timer(fps = 60)

fps: frames per second to aim for.

    METHODS

run
step
stop
set_fps

    ATTRIBUTES

fps: the current target FPS.  Use the set_fps method to change it.
frame: the current length of a frame in seconds.
t: the time at the last step, if using individual steps.

"""

    def __init__ (self, fps = 60):
        self.set_fps(fps)
        self.t = time()

    def run (self, cb, args = (), frames = None, seconds = None):
        """Run indefinitely or for a specified amount of time.

run(cb[, args][, frames][, seconds])

cb: a function to call every frame.
args: list of arguments to pass to cb.
frames: number of frames to run for.
seconds: number of seconds to run for; this can be a float, and is not wrapped
         to an integer number of frames: we wait for the remainder at the
         start.  If passed, frames is ignored.

"""
        self.stopped = False
        frame = self.frame
        if seconds is not None:
            frames = int(seconds / frame)
            # wait for remainder
            wait(int(1000 * (frames * frame - seconds)))
        finite = frames is not None
        if finite:
            frames = max(int(frames), 1)
        # main loop
        t0 = time()
        while not finite or frames:
            cb(*args)
            if self.stopped:
                break
            t = time()
            dt = t0 + frame - t
            if dt > 0:
                wait(int(1000 * dt))
                t0 = t + dt
            else:
                t0 = t
            if finite:
                frames -= 1
                if frames == 0:
                    break
                assert frames > 0

    def step (self):
        """Step forwards one frame."""
        t = time()
        dt = self.t + self.frame - t
        if dt > 0:
            wait(int(1000 * dt))
            self.t = t + dt
        else:
            self.t = t

    def stop (self):
        """Stop any current call to Timer.run."""
        self.stopped = True

    # we don't use the property builtin so there's no getter, to reduce
    # overhead there

    def set_fps (self, fps):
        """Set the target FPS."""
        self.fps = int(round(fps))
        self.frame = 1. / fps


class Scheduler ():
    """Simple event scheduler.

    CONSTRUCTOR

Scheduler(fps = 60)

fps: frames per second to aim for.

    METHODS

run
add_timeout
rm_timeout

    ATTRIBUTES

timer: Timer instance.  Use this to change the FPS or stop the scheduler.

"""

    def __init__ (self, fps = 60):
        self.timer = Timer(fps)
        self._cbs = {}
        self._max_id = 0

    def run (self, frames = None, seconds = None):
        """Start the scheduler.

run([frames][, seconds])

Arguments are as required by Timer.run.

"""
        self.timer.run(self._update, (), frames, seconds)

    def add_timeout (self, cb, args = (), frames = None, seconds = None,
                     repeat_frames = None, repeat_seconds = None):
        """Call a function after a delay.

add_timeout(cb[, args][, frames][, seconds][, repeat_frames][, repeat_seconds])
            -> ID

cb: the function to call.
args: list of arguments to pass to cb.
frames: number of frames to wait before calling.
seconds: number of seconds to wait before calling; this can be a float, and is
         wrapped to an integer number of frames.  If passed, frames is
         ignored.
repeat_frames: number of frames to wait between calls.
repeat_seconds: number of seconds to wait between calls; can be a float like
                seconds.  If passed, repeat_frames is ignored; if neither
                repeat_frames or repeat_seconds is passed, the initial time
                delay is used between calls.

ID: an ID to pass to rm_timeout.  This is guaranteed to be unique over time.

The called function can return a boolean True object to repeat the timeout;
otherwise it is removed.

"""
        if seconds is not None:
            frames = seconds * self.timer.fps
        frames = max(int(frames), 1)
        if repeat_seconds is not None:
            repeat_frames = repeat_seconds * self.timer.fps
        elif repeat_frames is None:
            repeat_frames = frames
        repeat_frames = max(int(repeat_frames), 1)
        self._cbs[self._max_id] = [frames, repeat_frames, cb, args]
        self._max_id += 1
        # ID is key in self._cbs
        return self._max_id - 1

    def rm_timeout (self, *ids):
        """Remove the timeouts with the given IDs."""
        for i in ids:
            try:
                del self._cbs[i]
            except KeyError:
                pass

    def _update (self):
        """Handle callbacks this frame."""
        rm = []
        # cbs might add/remove cbs, so use items instead of iteritems
        for i, (remain, total, cb, args) in self._cbs.items():
            remain -= 1
            if remain == 0:
                # call callback
                if cb(*args):
                    self._cbs[i][0] = total
                else:
                    rm.append(i)
            else:
                assert remain > 0
                self._cbs[i][0] = remain
        for i in rm:
            del self._cbs[i]
