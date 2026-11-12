"""Environment of the rifle reload tools: this build copy (gg-work/reloads), its work folder, the rifle meshes and
weapon anims, test guns on. Import first in every script of this folder."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
TOOLS = os.path.dirname(os.path.dirname(HERE))
OUT = 'C:/Modding/anim-work/rifle-reloads'            # everything made is kept here
RAISED = 'C:/Modding/anim-work/raised/clips'          # raised pose drafts: <body>/raised_C_<gun>.glb
GF = 'C:/Modding/_tools/gamefiles/ga-reloads'
RIFLE = 'C:/Modding/gg-work/raised/work/rifle'
os.environ.setdefault('GA_TEST', '1')
os.environ.setdefault('WORK', 'C:/Modding/gg-work/build-reloads')
os.environ.setdefault('AUTHORING', 'C:/Modding/gg-work/build-reloads/authoring')
os.environ.setdefault('WMESH', 'C:/Modding/_tools/gamefiles/wmesh/glb;C:/Modding/anim-work/lowered/research/wmesh;' + RIFLE + '/wmesh')
os.environ.setdefault('WANIM', GF + '/wanim;C:/Modding/_tools/gamefiles/wanim3/glb')
for p in (TOOLS, TOOLS + '/authoring', TOOLS + '/authoring/author', TOOLS + '/authoring/lowered', HERE):
    if p not in sys.path: sys.path.insert(0, p)
import common
