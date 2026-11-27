"""Environment of the reload authoring tools (rifle, SMG and shotgun): where the output goes, the raised drafts, the game
files and the weapon mesh and animation search paths. Import first in every script of this folder.

Each path is an entry of weapons.json paths (environment variable in brackets), read through common:
  OUT      reload_out [ROUND_OUT]       everything made is kept here. Default: the SMG and shotgun production folder.
                                        The rifle tools kept theirs in anim-work/rifle-reloads: set ROUND_OUT for them.
  RAISED   raised_drafts [RAISEDDRAFTS] raised pose drafts: <body>/raised_C_<gun>.glb
  GF       rreload_gamefiles [RRELOADGAMEFILES]   game files extracted for the reload builds
  GF0      gamefiles_root [GAMEFILESROOT]         the folder GF lives in (wmesh, wanim3, handguns-export)
  SMG_REF  smg_ref [SMGREF]             gun geometry json of the SMG and shotgun tools
WORK and AUTHORING default to OUT/work; WMESH and WANIM (mesh and animation search lists) are built from the paths above
unless set."""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')
TOOLS = os.path.dirname(os.path.dirname(HERE))
os.environ.setdefault('GA_TEST', '1')
for p in (TOOLS, TOOLS + '/authoring', TOOLS + '/authoring/author', TOOLS + '/authoring/lowered', HERE):
    if p not in sys.path: sys.path.insert(0, p)
import common
OUT = common.path('reload_out')                     # everything made is kept here
RAISED = common.path('raised_drafts')               # raised pose drafts: <body>/raised_C_<gun>.glb
GF0 = common.path('gamefiles_root')
GF = common.path('rreload_gamefiles')
SMG_REF = common.path('smg_ref')
os.environ.setdefault('WORK', OUT + '/work')
os.environ.setdefault('AUTHORING', OUT + '/work')
os.environ.setdefault('WMESH', ';'.join([GF0 + '/wmesh/glb', common.path('anim_work') + '/lowered/research/wmesh', GF0 + '/handguns-export/wmesh']))
os.environ.setdefault('WANIM', ';'.join([GF + '/wanim', GF0 + '/wanim3/glb', GF0 + '/handguns-export/wanim']))
