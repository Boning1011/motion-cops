# Houdini MotionCOPs Toolkit

Supports **Houdini 21.0** and above. All tools are built on Houdini's OpenCL-based Copernicus framework, providing:

- **Quick Results**: Create professional-quality effects in minutes with simple, intuitive controls that require minimal setup time
  
- **Lightning-Fast 4K Performance**: 10-100x faster than VEX implementations with responsive real-time feedback even at 4K resolution

- **Animated Shader Textures**: Create evolving procedural effects perfect for motion design with time-based parameters that produce organic animations

## Tool Catalog (32 Tools)

### Dithering & Stylization (6)

| Tool | Description | Inputs |
|------|-------------|--------|
| **Risograph** | Full risograph print pipeline — ink palette, layer separation, dithering, offset | 1 |
| **Halftone Dither** | Halftone dot patterns with size, noise, rotation, and blur controls | 1 |
| **Ordered Dither** | Bayer-matrix ordered dithering with configurable block scale and quant levels | 1 |
| **Noise Dither** | Noise-based stochastic dithering | 1 |
| **Dither Mono** | Simple monochrome threshold dithering with pre-processing | 1 |
| **Pixel Sorting** | GPU pixel sorting for glitch art — directional, masked, with growth animation | 2 |

### Kubelka-Munk Color Science (4)

| Tool | Description | Inputs |
|------|-------------|--------|
| **RGB to KM** | Convert RGB to Kubelka-Munk scattering/absorption color space | 1 |
| **KM to RGB** | Convert Kubelka-Munk back to RGB | 1 |
| **KM Converter** | Bidirectional RGB ↔ KM conversion | 1 |
| **KM Blend** | Physically-based color blending in KM space (with mask) | 3 |

### Point ↔ Layer Bridge (5)

| Tool | Description | Inputs |
|------|-------------|--------|
| **mc Mono to Points** | Convert monochrome image to point cloud with relaxation | 1 |
| **mc Point to Density** | Rasterize points into a density field layer | 2 |
| **mc Point to Shape** | Rasterize points as shapes with velocity | 1 |
| **mc Point Velocity to Layer** | Write point velocity data into a COP layer | 2 |
| **mc Point Advect by Layer** | Advect points using a velocity layer (wind, drag, max speed) | 2 |

### Image Distortion & FX (4)

| Tool | Description | Inputs |
|------|-------------|--------|
| **mc Blackhole Distort** | Gravitational lens-style distortion with strength, radius, falloff | 2 |
| **mc Ripple** | Procedural ripple wave effect (speed, damping, iterations) | 3 |
| **mc Ripple Solver** | Time-stepping ripple simulation with reset and time scale | 2 |
| **mc Velocity Anti-Grid** | Remove grid artifacts from velocity fields | 1 |

### Simulation & Growth (3)

| Tool | Description | Inputs |
|------|-------------|--------|
| **Growth Propagation** | Organic growth patterns — DLA, veins, cracks, lightning | 5 |
| **Reactiondiffusion Presets** | Preset library for reaction-diffusion patterns | 0 |
| **Copernicus Solver** *(SOP)* | SOP-level simulation framework for Copernicus networks | 4 |

### Analysis & SDF (5)

| Tool | Description | Inputs |
|------|-------------|--------|
| **Gaussian Slope** | Slope detection via Gaussian kernel (detail, scale, rotation) | 1 |
| **Slope Visualize** | Quick slope direction visualization | 1 |
| **Angle Quantize** | Quantize gradient angles to fixed increments with magnitude mixing | 1 |
| **Directional Occlusion** | Directional ambient occlusion from heightfield | 2 |
| **mc SDF Smooth Union** | Smooth boolean union for SDF layers with anti-aliasing | 2 |

### Time & Caching (4)

| Tool | Description | Inputs |
|------|-------------|--------|
| **Time Shift** | Frame offset / retime with clamping options | 1 |
| **Frame Blend** | Temporal blending across frames | 1 |
| **Cache** | In-memory COP frame caching with auto-clear | 1 |
| **mc TOP Image Cache** | TOP-driven disk cache for COP sequences | 1 |

### Utility (3)

| Tool | Description | Inputs |
|------|-------------|--------|
| **mc UV Adjust** | Masked UV rotation and length remapping | 2 |
| **mc Range Visualize** | False-color visualization of value ranges via ramp | 1 |
| **mc Flow Block Begin / End** | Loop control blocks for iterative COP processing | — |

## Installation (Houdini Package)

- Download and extract the repository and move it to any location
- Create a folder called `packages` in your Houdini home directory (e.g. `C:/Users/MY_USER/Documents/houdini21.0`) if it does not exist already
- Copy the `MotionCOPs.json` file into the `packages` folder
- Edit the json file to point to the MotionCOPs parent directory (edit the "MotionCOPs" line)
- This package is designed for Houdini 21.0 or higher
- For more information on how package files work, see the [official Houdini documentation](https://www.sidefx.com/docs/houdini/ref/plugins.html)

## Demos


### Growth Propagation
Generate organic spreading patterns from simple masks to complex vein structures. Inspired by Nick Tylor's Aelib but completely reimagined for COPs.

- **Versatile Effects**: Create cellular growth, lightning, cracks, veins, and DLA-style structures with a single tool
- **Directional Control**: Shape growth patterns with directional fields and attractors
- **Animation Ready**: Perfect for evolving textures in motion graphics projects
  
<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_02.gif" width="300" height="300"/><img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_03.gif" width="300" height="300"/><img src="https://github.com/Boning1011/motion-cops/blob/main/demo/growth_propagation/growth_dirControl_01.gif" width="300" height="300"/>

### Pixel Sorting

A fast OpenCL implementation of the classic pixel sorting effect - widely used for creating glitch art, flowing textures, and stylized transitions. 

- **Performance Boost**: Get real-time feedback even with high iteration counts thanks to GPU acceleration
- **Simple Masking System**: Easily control where sorting occurs using luminance values or custom masks  
- **Animation Ready**: Create evolving effects with built-in growth animation parameters

<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/pixelsorting/pixelsorting_mandril_v1.gif" width="320" height="320"/>

### Risograph

The node that makes EVERYTHING look good. Instant risograph print look (that trendy aesthetic everyone wants). Built on actual print physics (how real ink behaves on paper).

- Real ink colors that mix naturally - not those fake RGB filters

- Gorgeous texture and grain that adds $$$ production value

- Three styles: organic, halftone, or digital


<img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/mandril_v1_1k.png" width="320" height="320"/><img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/pig_all_1080.png" width="320" height="320"/><img src="https://github.com/Boning1011/motion-cops/blob/main/demo/risograph/ditherMode_v2_2k.png" width="410" height="614"/>



