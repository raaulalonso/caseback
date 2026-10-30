# Printable mocks of the disc and of the charging base

Two print files. The first is a plastic disc with the real outline, wall, floor, windows, contact holes, key notch, ribs and
snap, to hold, close and open before anything is machined. The face of each lid is flat, so it prints on the bed with
nothing to bridge. It has no board, no cell and no glass. The second is the charging base (the puck) with the key, the dish,
the pin bores and the pocket for the board, to check how the disc sits in it and to try the parts that will be bought.

## Files

| File | What it is |
|------|------------|
| `caseback_mock_A1_PETG.3mf` | One plate, already sliced for a Bambu Lab A1 with a 0.4 mm nozzle: the shell, three lids and the pad. Open it in Bambu Studio and print |
| `caseback_mock_shell.stl` | The shell, skin face down (cavity up) |
| `caseback_mock_lid_easy.stl`, `_standard.stl`, `_firm.stl` | The lid, face down on the bed, the face dead flat. They differ only in the height of the bead of the snap, and in 1, 2 or 3 small notches in the rim so they can be told apart |
| `caseback_mock_pad.stl` | A 16.9 mm disc, 0.4 mm thick, that stands in for the microsuction pad. It is taped to the flat face of a lid |
| `caseback_mock_puck_A1_PETG.3mf` | A second print file, sliced the same way: the body of the charging base and its bottom plate. Ø34 x 7 mm |
| `caseback_mock_puck_body.stl` | The body of the base with the key joined to it, bottom face on the bed (pocket open downwards) |
| `caseback_mock_puck_plate.stl` | The bottom plate, a plain disc Ø26.6 x 0.6 mm, without engraving |

Made by `../scripts/generate_mock.py`, which reuses the shell, lid and puck of `generate_disc.py`:

```
/Applications/Blender.app/Contents/MacOS/Blender -b --python generate_mock.py -- --out ../print
```

## Print settings (stored in the 3MF)

- Bambu Lab A1, 0.4 mm nozzle, Textured PEI plate (PETG is not accepted on the cool plate)
- PETG at 245 °C, 0.08 mm layers (0.2 mm the first), two walls, 15 % infill, no supports, no brim. The slicer reports no bridges and no warnings
- Walls are made with Arachne. The skirt of the lid comes out as a single line of 0.46 mm, the bead as lines of 0.52 to 0.58 mm
- All five parts: about 10 min 25 s and 2.1 g of filament

The 3MF carries its own G-code. For PLA, change the filament in Bambu Studio and slice again.

The puck plate uses the same machine and filament, with 0.12 mm layers and three walls (the bores are small and the wall
between a bore and the dish is thin). The slicer gives no warning. Body and plate together: about 17 min and 4.2 g.

## What is different from the real disc

The 0.4 mm nozzle cannot make a few things, so the mock changes only those:

| Real disc | Mock | Why |
|-----------|------|-----|
| Skirt of the lid 0.36 mm, 0.04 mm from the wall | 0.46 mm, 0.06 mm from the wall | Bambu Studio reports a floating region at a bead on a wall that is not thicker than its own line (0.42 mm); from 0.44 mm it does not |
| Bead 0.10 mm, 60° return flank | 0.09, 0.12 or 0.15 mm, 45° on both flanks | 45° is the flank that was checked in the slicer; the real 60° one has not been tried on a printed wall |
| Groove in the wall 0.10 mm deep | 0.15 mm, for the biggest bead (the wall keeps 0.65 mm) | One groove has to take all three lids |
| Skirt tip at 1.55 mm | 1.50 mm | Room for the 45° bead |
| CASEBACK name and mark on the skin face | none | The lines are 0.07 to 0.09 mm wide |
| Lid face with a Ø23 mm pad recess 0.3 mm deep and a rounded edge of 0.6 mm | Flat face, square edge | Printed face down, the roof of the recess is a 23 mm bridge floating 0.3 mm over the bed. A flat face is one solid layer on the bed |
| Skin-side edge radius 1.2 mm, inside corner of the shell 0.4 mm | Edge radius 0.5 mm, sharp inside corner | The mock is the model of 28 October and does not follow the final design |
| Pad Ø23 mm | Stand-in of Ø16.9 mm | Same reason |

The three lids go in against 0.03, 0.06 and 0.09 mm of interference (bead height minus the 0.06 mm of clearance). Closed, the
bead sits in the groove and the lip lands on the wall: an exact boolean of the closed assembly gives no overlap for any of the
three. The silicone gasket is not in the mock: the 0.1 mm where it goes stays empty.

The skirt reaches in to a radius of 11.18 mm and the real board is 11.2 mm, so **a real board does not fit in the mock**. For a
disc with a board, use the real skirt (0.36 mm) in a machined or resin part.

## Trying it

1. Print the plate. The pad prints as a separate disc; it is not glued, a small piece of tape holds it on the flat face of the lid.
2. Close the shell with the `easy` lid first: press with both thumbs on the face. It should go in with a small click and stay.
   Then try `standard` and `firm`.
3. If `easy` jams, the printer is making the skirt fat: print again with an XY contour compensation of -0.05 mm. If all three
   fall out, print again with +0.05 mm.
4. The real disc is meant to weigh about 3 g. The mock weighs about 1 g; lay one or two flat steel washers (weigh them) in
   the cavity before closing the lid.
5. With no recess, the pad stands 0.4 mm proud of the face, not the 0.1 mm of the drawing, so the closed disc is 3.4 mm thick
   with the pad on and 3.0 mm without it. Leave the pad off to check the real thickness.

## The charging base

The body prints as it is modelled, bottom face on the bed. The pocket for the puck board (Ø25.8 mm, 1.55 mm deep) is open to
the bed, so its roof is a bridge of about 26 mm; the cavity for the USB-C receptacle (9.6 x 7.9 mm) opens off the pocket
and has a bridge of its own. The slicer does not flag either, but PETG may sag on the big one: if the roof comes out wavy,
print again in PLA or with a lower bridge flow. The dish, the key and the two bores do not depend on it.

What is printed and what is not:

| Printed | Not printed, bought or drawn only |
|---------|-----------------------------------|
| Body: rim, dish, key, two bores for the charge contacts, pocket, cavity and flat for the USB-C | The spring pins (the bores are Ø1.24 mm, for pins of 1.0 to 1.3 mm), the puck board, the USB-C receptacle, the screws, the silicone foot |
| Bottom plate Ø26.6 x 0.6 mm | The engraving of the mark |

Trying it:

1. Lay the closed mock disc skin face down in the dish. The key must stop it turning and the disc should stand about 1.9 mm
   proud of the rim.
2. Push a loose spring pin into a bore and check that the plunger comes out about 0.35 mm over the dish floor and goes in
   flush when the disc is pressed.
3. Hold a USB-C breakout board in the pocket and check that the receptacle lines up with the flat on the rim.
4. If the bores are tight or loose for the pins you bought, change the radius 0.62 in `build_puck` of `generate_disc.py` and
   run `generate_mock.py` again.
