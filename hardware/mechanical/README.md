# Caseback Mechanical

## Parts

1. **Sensor disc (V0)**: two-piece shell (skin-side bottom, caseback-side top) held by 2 x M1 screws, gasket groove in the
   bottom rim, cell pocket, PPG window seat, two charge-pad recesses and a keying notch.
2. **Softband pocket (V0)**: simplified TPU strap blank with a moulded housing for the disc. No retention lip is modelled.
3. **Charging puck**: Ø38 x 8 mm, dish sized to the disc, key tab, two pogo bores. The disc has no ferromagnetic
   part; it rests in the dish by the weight of the watch. The current design charges through the skin face.

## V0 geometry (as built by `generate_enclosure.py`)

Z = 0 is the skin face, +Z is towards the caseback. All numbers are checked by `check_geometry.py`.

| Feature | Value |
|---------|-------|
| Outer Ø x height | 34.0 x 4.0 mm |
| Floor (skin side) | 0.9 mm |
| Cavity | Ø28.6, z 0.9 to 2.7 = **1.8 mm high** |
| Roof | 1.3 mm, **0.9 mm** under the pad recess |
| Pad recess | Ø22 x 0.4 mm (z 3.6 to 4.0), does not breach the roof |
| Rim | 2.7 mm: 0.95 web, 0.8 mm groove, 0.95 web |
| Parting line | z = 2.0. Inner web rises 0.5 mm as a lip into the lid (0.15 mm clearance) |
| Gasket groove | 0.8 wide x 0.6 deep in the bottom rim face, for a 0.8 mm cord (25 % squeeze) |
| PPG window | Ø3.6 aperture, Ø4.4 x 0.4 seat (0.4 mm radial ledge, ledge 0.9 mm thick) for a glass or PMMA window up to Ø4.3 x 0.4. Centre at y = +8 mm so the cell fits beside it |
| Screws | 2 x M1 x 3 at (±9.5, +8): Ø1.2 hole, Ø2.2 x 0.8 counterbore, Ø0.8 pilot in the bottom boss. **Plastic, brass or titanium, never steel** |
| Charge pads | 2.4 x 1.2 x 0.3 mm recesses on the skin face, 8 mm pitch at y = -12.6 |
| Keying notch | 3.0 wide x 0.9 deep x 1.0 high in the rim at -Y, so the disc seats in one orientation only (about ±2 deg of play) |
| Puck | Ø38 x 8 mm, dish Ø34.6 x 1.6 (0.3 mm per side), key tab 2.2 wide x 0.8 high, pogo bores Ø1.2 |

## Design rules

These are the rules of the V0 prototype. The V1 disc (Ø25 x 3.1 mm, snap-fit lid, no screws) is in `scripts/generate_disc.py`,
with its stack and its checks in `hardware/v1-pcb/board_v01.py`.

- **Optical window** flush on the **wrist side** (bottom): 3-4 mm clear aperture for PPG LEDs/photodiode; no metal over optics.
- **Microsuction pad** on the **watch side** (top): Ø22 mm recess 0.4 mm deep so the pad sits flush and does not rock
  on the caseback. The roof under the recess must stay ≥ 0.9 mm.
- **No ferromagnetic steel** near a mechanical watch movement (titanium, brass, aluminium or plastic; no magnet on the disc).
  M1 screws must be non-magnetic.
- Wall ≥ 0.9 mm on every printed part (FDM V0; the SLS minimum of 0.6 mm is the V1 rule).
- 2 x M1 screws plus the lip hold the lid; the screws are on the +Y side only, so the far side relies on the lip.

## Orientation

```
        ┌─────────────────┐
        │  microsuction   │  ← contacts caseback (UP)
        │  top shell      │
        │  PCB + battery  │
        │  PPG window     │  ← contacts skin (DOWN)
        └─────────────────┘
```

## Files

| File | Status |
|------|--------|
| `scripts/generate_enclosure.py` | Blender Python: V0 disc (two shells), puck and softband. Headless: `blender -b --python scripts/generate_enclosure.py -- [--out-dir DIR] [--blend FILE] [--h MM] [--cell NAME] [--tag TXT]` |
| `scripts/check_geometry.py` | Stdlib + numpy: reads `stl/` and prints the wall, floor, roof, pocket, puck-fit and keying checks. Exit code 1 on failure |
| `scripts/caseback_v0_mechanical.blend` | Generated V0 scene (disc bottom and top in assembly position, puck and softband offset) |
| `stl/caseback_v0_{bottom,top,puck,band}.stl` | Millimetre STLs of the V0 parts in assembly orientation, plus `caseback_v0_params.json` (input of the checker) |
| `scripts/generate_v1.py` | Blender Python: V1 concept disc (Ø32 x 2.7 mm) with shell, lid, gasket, pad, PCB, optics and battery; also builds exploded and half-section copies. Headless: `blender -b scripts/caseback_v1_concept.blend --python scripts/generate_v1.py -- --blend scripts/caseback_v1_concept.blend` (open the existing blend so its camera and lights are kept) |
| `scripts/caseback_v1_concept.blend` | Generated V1 scene (collections `Caseback_V1_Assembled`, `_Exploded`, `_Section`) |
| `scripts/generate_disc.py`, `scripts/board_parts.py` | Blender Python for the current design (disc design 1): shell, snap-fit lid, pad, cell, the charger (D59; the code calls it the puck), with the hook and the latch that hold the disc, and the real KiCad board with a model of every part on it. Needs KiCad 10 (`KICAD_CLI`, `KICAD_PY`). Headless: `blender -b --python scripts/generate_disc.py -- [--render DIR] [--only a,b] [--stl DIR] [--blend FILE] [--samples N] [--scale F]` |
| `scripts/export_web.py` | Blender Python: the assembled disc of design 1 as `web/public/models/disc.glb` for the home page of the website, one node per part, the cell drawn again with `generate_disc.build_cell` (no KiCad needed), weighted normals, ambient occlusion baked into the vertex colours with Cycles, compressed with gltfpack (npx). Headless: `blender -b scripts/caseback_disc_design1.blend --python scripts/export_web.py`. Run it again when the blend changes |
| `renders/disc_*.jpg`, `renders/board_*.jpg` | Cycles renders of design 1 and of the board, from `generate_disc.py` (`disc_edge_section.jpg` shows the edge radii in section). No watch is drawn |
| `stl/disc_*.stl`, `stl/puck_*.stl` | Parts of design 1 for printing and the solid fit dummy for the pad tests, from `generate_disc.py --stl` |
| `scripts/band_v01.py`, `scripts/generate_band.py` | The band (D58): a woven strap that starts in one end of a silicone holder round the disc, goes once round the wrist, passes through a steel buckle moulded into the other end and holds on itself by hook-and-loop; the disc's skin face stands out of the holder, so the charger clicks onto the disc without taking it out of the band. `band_v01.py` holds the numbers and the checks (standard library only: `python3 band_v01.py`); `generate_band.py` is the Blender model of it with the disc and the charger. Headless: `blender -b --python scripts/generate_band.py -- [--render DIR] [--stl DIR] [--blend FILE] [--only a,b] [--samples N] [--scale S] [--simple]` |
| `renders/band_*.jpg`, `stl/band_*.stl` | Renders of the band (from outside, from inside, the holder with the disc, the buckle, the free end open, the charger clicked onto the disc inside the band) and the STL of the holder and the buckle, from `generate_band.py` |
| `scripts/generate_mock.py`, `print/` | Printable mocks of design 1 for a 0.4 mm nozzle: the shell, three lids with different snap tightness and a pad stand-in (`caseback_mock_A1_PETG.3mf`), and the body and bottom plate of the charging base (`caseback_mock_puck_A1_PETG.3mf`), both sliced for a Bambu Lab A1 in PETG. What it changes from the real parts, and how to try it, is in `print/README.md`. Headless: `blender -b --python scripts/generate_mock.py -- --out ../print` |
| `renders/v1_*.png` | Eevee renders of the V1 concept (watch side, skin side, inside, exploded, section). |

Regenerate and check:

```
blender -b --python scripts/generate_enclosure.py
python3 scripts/check_geometry.py
```

Print the lid upside down (recess on the bed) and the bottom shell skin face down.
The files in `print/` are sliced for a Bambu Lab A1 (Bambu Studio 2.8.2, 0.4 mm nozzle, PETG).

## Print settings (FDM V0)

- Material: **PETG** or **TPU 95A** for band; disc can be PETG
- Layer 0.12-0.16 mm, 3 perimeters, 25 % gyroid
- Support only for puck cavity
