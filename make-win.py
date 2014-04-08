from sys import exit
from os import environ
from shutil import copy
from glob import glob
from subprocess import call

environ['cl'] = '/I..\sdl_include'
if call(('python', 'setup.py', 'build')) != 0:
    exit(1)
for f in glob('build\\lib*\\*.pyd'):
    copy(f, 'game\\engine\\gfx\\')
