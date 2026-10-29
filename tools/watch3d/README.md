# The watch model

`build_watch.py` builds the Caseback watch in Blender and exports it. Run it inside Blender (Scripting > Run Script, or
`exec(open('.../build_watch.py').read())`), with Blender 4.2 or later; it needs numpy (bundled) and the IBM Plex Mono font from
the app's resources.

It writes:

| File | Used by |
|---|---|
| `tools/watch3d/out/caseback-watch.glb` | any web or 3D use (glTF); not used by anything today |
| `apps/ios/Caseback/Resources/CasebackWatch.usdz` | the iOS app (SceneKit, `Blobs/Watch3D.swift`) |
| `apps/ios/Caseback/Resources/CasebackStudio.hdr` | the studio the reflections come from |
| `CasebackWatch.blend`, `leather_grain_normal.png` | the source scene and the leather texture |

Units: the case radius is 1. Dial towards +Z, 12 o'clock towards +Y, crown towards +X (before the export rotation, see the script).
The three hands are separate nodes (`hand_hour`, `hand_minute`, `hand_second`) with their origin on the dial axis. The disc the
blobs make sits on the caseback plate at z = -0.20, which is flat on purpose.
