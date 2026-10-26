# MotionCOPs

Ready-to-use tools for Houdini Copernicus, built in daily production by [Bo-Ning Li](https://boningli.com).

## Recent practical features

- **Batch media paste** — **Ctrl+V** images and videos straight into COPs. [Details](docs/media-paste.md)
- **LUT grading** — apply `.cube` LUTs and adjust their intensity. [Example](Example_LUTs.hiplc)
- **2D → 3D volumes** — stack animated images into volumes, with a CPU sparse VDB option.

**Houdini 21 & 22** · [Install MotionCOPs](#installation) · [Project page](https://boningli.com/rnd/motion-cops)

**Inside:** organic growth · stylization · dithering & risograph · glitch · Kubelka-Munk color · SOP ↔ image bridges · time & caching utilities

![MotionCOPs](demo/banner.png)

## Work made with MotionCOPs

MotionCOPs is built through production. Each piece below was made primarily with tools from the library; all visual work shown is my own. The toolkit and the images evolved together across commissioned installations, large-format screen work, and self-directed studies.

<p align="center">
  <img src="demo/selected_work/edge-of-chaos-fluid.webp" width="100%" alt="Edge-of-Chaos Fluid — a blue, green, black, and white fluid-field composition made with MotionCOPs"/>
  <br/>
  <sub><strong>Edge-of-Chaos Fluid</strong> — the project cover and a key production study: a reusable Copernicus fluid system developed with MotionCOPs workflows.</sub>
</p>

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="demo/selected_work/23-springs.webp" width="100%" alt="23.Springs permanent LED installation for Granite Properties"/>
      <br/>
      <sub><strong>23.Springs / Granite Properties</strong> — MotionCOPs-driven image processing and procedural distortion for a permanent 8K installation.</sub>
    </td>
    <td width="50%" valign="top">
      <img src="demo/selected_work/offf-barcelona.webp" width="100%" alt="OFFF Barcelona Screen projection driven by a monochrome fluid field"/>
      <br/>
      <sub><strong>OFFF Barcelona Screen</strong> — the fluid system adapted through MotionCOPs for a large-format façade projection.</sub>
    </td>
  </tr>
</table>

<p align="center">
  <img src="demo/selected_work/field-study-panoramic.webp" width="100%" alt="Panoramic monochrome field study made with MotionCOPs"/>
  <br/>
  <sub><strong>Field study / GitHub banner</strong> — a panoramic simulation study developed with MotionCOPs field-processing tools.</sub>
</p>

<p align="center">
  <img src="demo/selected_work/fluid-field-study.webp" width="100%" alt="Monochrome fluid-field study made with MotionCOPs"/>
  <br/>
  <sub><strong>Fluid-field study</strong> — a finished image from the same production-tested Copernicus workflow.</sub>
</p>

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="demo/selected_work/contour-study-dark.webp" width="100%" alt="Dark procedural contour study made with MotionCOPs"/>
      <br/>
      <sub><strong>Contour study I</strong> — feedback, edge analysis, and repeated line structures generated in MotionCOPs.</sub>
    </td>
    <td width="50%" valign="top">
      <img src="demo/selected_work/contour-study-light.webp" width="100%" alt="Light procedural contour study made with MotionCOPs"/>
      <br/>
      <sub><strong>Contour study II</strong> — a second parameter state from the same procedural system.</sub>
    </td>
  </tr>
</table>

## Toolkit at a glance

<img src="demo/all_nodes.png" width="500" alt="All MotionCOPs nodes"/>

> Supports Houdini 21 & 22. Jump to [Installation](#installation).

---

## Showcase

### Swirl

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/swirl/swirl.gif" width="540"/>

### Growth Propagation

Generate organic spreading patterns — cellular growth, lightning, cracks, veins, and DLA-style structures. Supports directional fields and attractors for precise control. Inspired by Nick Taylor's Aelib, reimagined for COPs.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_02.gif" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_03.gif" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_dirControl_01.gif" width="270" height="270"/>

### Ripple

GPU-based ripple simulation for water surfaces, shockwaves, and reactive wave patterns — driven by `mc Ripple Solver` directly inside the Copernicus network.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/ripple/ripple.png" width="540"/>

### Analysis

Slope, occlusion, and SDF tools treat images as fields rather than pixels — useful for terrain-style studies, directional lighting, and fractal growth structures.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/analysis/dune.jpg" width="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/analysis/crystal_growth_01.png" width="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/analysis/crystal_growth_02.png" width="270"/>

### Pixel Sorting

GPU-accelerated pixel sorting for glitch art, flowing textures, and stylized transitions. Mask by luminance or custom input, with built-in growth animation.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/pixelsorting/pixelsorting_mandril_v1.gif" width="320" height="320"/>

### Risograph

Instant risograph print aesthetic built on Kubelka-Munk color theory — real ink mixing, not RGB filters. Three modes: organic, halftone, or digital.

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/mandril_v1_1k.png" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/pig_all_1080.png" width="270" height="270"/> <img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/ditherMode_v2_2k.png" width="270" height="405"/>

---

## Tool Catalog

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

## Installation

1. Download and extract the repository to any location
2. In your Houdini home directory (e.g. `C:/Users/MY_USER/Documents/houdini22.0`), create a `packages` folder if it doesn't exist
3. Copy `MotionCOPs.json` into `packages/`
4. Edit the JSON file — set the path to your MotionCOPs directory

See the [Houdini docs](https://www.sidefx.com/docs/houdini/ref/plugins.html) for more on package files.

### Paste images and videos into COPs

Copy files, then **Ctrl+V** in a COPs network; **Ctrl+Z** undoes the batch.
See the [media paste guide](docs/media-paste.md) for details and checks.
