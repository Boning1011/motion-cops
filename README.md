# Houdini MotionCOPs Toolkit

All tools are built using Houdini 20.5's new OpenCL-based Copernicus framework, providing:

- **Quick Results**: Create professional-quality effects in minutes with simple, intuitive controls that require minimal setup time
  
- **Lightning-Fast 4K Performance**: 10-100x faster than VEX implementations with responsive real-time feedback even at 4K resolution

- **Animated Shader Textures**: Create evolving procedural effects perfect for motion design with time-based parameters that produce organic animations

## Featured Tools Included

- [Growth Propagation](#growth-propagation) - Create organic growth patterns and DLA-style structures
- [Pixel Sorting](#pixel-sorting) - Classic pixel sorting effect for image
- COPs Solver - Simulation in Copernicus
- Risograph
- Frame Blend
- Directional Occlusion
- Angle Quantize
- add MORE...

## Installation (Houdini Package)

- Download and extract the repository and move it to any location
- Create a folder called `packages` in your Houdini home directory (e.g. `C:/Users/MY_USER/Documents/houdini20.5`) if it does not exist already
- Copy the `MotionCOPs.json` file into the `packages` folder
- Edit the json file to point to the MotionCOPs parent directory (edit the "MotionCOPs" line)
- This package is designed for Houdini 20.5 (current) or higher (future versions)
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



