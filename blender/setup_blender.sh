#!/bin/sh
# Blender (bpy) をクラウド環境に入れる。環境の Setup script にも貼れる。
set -e
[ -x /opt/blender-venv/bin/python ] || python3 -m venv /opt/blender-venv
/opt/blender-venv/bin/pip install -q bpy
printf '#!/bin/sh\nexec /opt/blender-venv/bin/python "$@"\n' > /usr/local/bin/blender-py
chmod +x /usr/local/bin/blender-py
blender-py -c "import bpy; print('Blender', bpy.app.version_string)"
