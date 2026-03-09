# Houdini MotionCOPs Toolkit

Supports **Houdini 21.0** and above. All tools are built on Houdini's OpenCL-based Copernicus framework, providing:

- **Quick Results** — Professional-quality effects in minutes with intuitive controls
- **Lightning-Fast 4K** — 10-100x faster than VEX with real-time feedback at 4K
- **Animated Textures** — Time-based procedural effects for motion design

## Tool Catalog (32 Tools)

### Simulation & Growth
Growth Propagation · Reactiondiffusion Presets · Copernicus Solver *(SOP)*

### Dithering & Stylization
Risograph · Halftone Dither · Ordered Dither · Noise Dither · Dither Mono · Pixel Sorting

### Analysis & SDF
Gaussian Slope · Slope Visualize · Angle Quantize · Directional Occlusion · mc SDF Smooth Union

### Image Distortion & FX
mc Blackhole Distort · mc Ripple · mc Ripple Solver · mc Velocity Anti-Grid

### Point ↔ Layer Bridge
mc Mono to Points · mc Point to Density · mc Point to Shape · mc Point Velocity to Layer · mc Point Advect by Layer

### Time & Caching
Time Shift · Frame Blend · Cache · mc TOP Image Cache

### Utility
mc UV Adjust · mc Range Visualize · mc Flow Block Begin / End

### Kubelka-Munk Color Science
RGB to KM · KM to RGB · KM Converter · KM Blend

---

## Demos

### Growth Propagation

Generate organic spreading patterns — cellular growth, lightning, cracks, veins, and DLA-style structures. Supports directional fields and attractors for precise control. Inspired by Nick Taylor's Aelib, reimagined for COPs.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_02.gif" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_03.gif" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_dirControl_01.gif" width="270" height="270"/>

### Pixel Sorting

GPU-accelerated pixel sorting for glitch art, flowing textures, and stylized transitions. Real-time feedback even at high iteration counts. Mask by luminance or custom input, with built-in growth animation.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/pixelsorting/pixelsorting_mandril_v1.gif" width="320" height="320"/>

### Risograph

Instant risograph print aesthetic built on Kubelka-Munk color theory — real ink mixing, not RGB filters. Three modes: organic, halftone, or digital.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/mandril_v1_1k.png" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/pig_all_1080.png" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/ditherMode_v2_2k.png" width="270" height="405"/>

---

## Installation

1. Download and extract the repository to any location
2. In your Houdini home directory (e.g. `C:/Users/MY_USER/Documents/houdini21.0`), create a `packages` folder if it doesn't exist
3. Copy `MotionCOPs.json` into `packages/`
4. Edit the JSON file — set the path to your MotionCOPs directory

See the [Houdini docs](https://www.sidefx.com/docs/houdini/ref/plugins.html) for more on package files.
