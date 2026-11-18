# Landing-page background image prompts

Style reference: the two attached 3D renders (twisted glass ribbon with one ultramarine-blue core; frosted glass cubes on a blue acrylic plinth).

## Shared style block (append to every prompt)

> Photorealistic 3D render, frosted and clear glass with soft refraction, a single saturated deep ultramarine-blue (#0014DC, pure saturated cobalt, no purple tint) accent, everything else white and pale cool grey, seamless light-grey studio backdrop (#F2F3F6), soft diffused top-left lighting, gentle long shadow, subtle iridescent pink-violet edge reflections, shallow depth of field, minimal, premium fintech aesthetic, ultra clean, no text, no logos, no people, no UI, 16:9, 3840x2160.

## 1. Hero twisting ribbon — empty space on the LEFT

A tall twisting ribbon of translucent clear glass spiraling around a solid deep ultramarine-blue silk-like core, positioned in the right third of the frame, rising off the top and bottom edges. The entire left 55% of the image is clean empty light-grey backdrop with only a faint soft shadow gradient. + shared style block.

## 2. Frosted glass cube cluster — empty space on the RIGHT

A floating 2×2×2 cluster of frosted-glass cubes with ultramarine-to-violet gradient interiors hovering above a rounded white slab on a blue acrylic base, positioned in the left third of the frame with a soft long shadow falling left. The right 55% of the image is clean empty pale backdrop. + shared style block.

## 3. Flowing glass bands — empty space on the RIGHT

Several thin, wide ribbons of clear glass sweeping in from the left edge in a smooth S-curve, interlaced with one thick ultramarine-blue ribbon, all cropped by the left and bottom frame edges, fading softly into the pale backdrop toward the right. The right 55% is empty and quiet. + shared style block.

## 4. Floating glass orbs & rings — empty space on the LEFT

A loose arrangement of translucent glass rings, a pair of frosted spheres and one solid deep ultramarine-blue torus floating at different depths, clustered in the right third of the frame, the largest partly cropped by the right edge. The left 55% is empty pale backdrop with a very soft vignette. + shared style block.

## 5. Inverse cube — solid blue background, subject centered (CTA / banner)

Photorealistic 3D render, a floating 2×2×2 cluster of frosted and clear glass cubes with soft refraction, centered in the frame and hovering above a rounded white slab on a clear-white acrylic base. The background is a seamless solid flat deep ultramarine-blue (#0014DC, pure saturated cobalt, no purple tint) studio backdrop with no gradient or texture. The glass cubes are white and pale cool grey with subtle iridescent pink-violet edge reflections and faint blue light transmitted through them, so they read clearly against the blue. Soft diffused top-left lighting, gentle deep-blue shadow beneath the base, shallow depth of field, minimal, premium fintech aesthetic, ultra clean, no text, no logos, no people, no UI, 16:9, 3840x2160.

## Line-art feature illustrations (white outline on black)

For feature grids (security, speed, support…). Generate one per feature, same style block each time so they read as a set.

### Line-art style block (append to every prompt)

> Isometric technical line drawing, thin uniform white hairline strokes (1px look, no fill, no shading, no gradients), wireframe with hidden edges visible through the shapes, precise geometric construction, solid near-black background (#15130D), single object centered with generous empty margin, minimal, architectural blueprint feel, no text, no color, 1:1, 2048x2048.

### Prompts

1. **Secure data** — A hexagonal wireframe cage enclosing a cluster of six cubes meeting at a central vertex, like an exploded isometric snowflake of boxes. + line-art block.
2. **Account protection** — A large wireframe sphere with two tilted elliptical rings orbiting nested spheres inside it, concentric layers visible through each other. + line-art block.
3. **Multi-factor authentication** — Concentric circular segmented rings, each ring rotated at a different angle with notched gaps like a vault dial, a small hollow circle at the center. + line-art block.
4. **24/7 support** — Three chunky rounded-capsule bars stacked and offset in an S shape, extruded in isometric view, outlines only. + line-art block.
5. **Loans / growth (extra)** — A stepped isometric staircase of wireframe blocks rising left to right with a thin diagonal arc passing through it. + line-art block.

Usage: place on `.section-dark` (see `tokens.css`) at ~160px, caption below in Phonic 20px white, centered.

## Usage

Set as `background-image` on `.section-art` (see `tokens.css`). Copy goes where the image is empty: prompts 2 and 3 (empty right) use `.art-clear-right`; prompts 1 and 4 (empty left) use `.art-clear-left`. Export at 2400px wide, WebP, ≤250 KB; keep `--bg-alt` as the fallback colour.
