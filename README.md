# Houdini OpenCL COPS Toolkit

All tools in this toolkit are built using Houdini 20.5's new OpenCL-based Copernicus framework, providing:

- **Quick Results**: Create professional-quality effects in minutes with simple, intuitive controls that require minimal setup time
  
- **Lightning-Fast 4K Performance**: 10-100x faster than VEX implementations with responsive real-time feedback even at 4K resolution

- **Animated Shader Textures**: Create evolving procedural effects perfect for motion design with time-based parameters that produce organic animations

# Installation (Houdini Package)

- Download and extract the repository and move it to any location
- Create a folder called `packages` in your Houdini home directory (e.g. `C:/Users/MY_USER/Documents/houdini20.5`) if it does not exist already
- Copy the `CopernicusToolkit.json` file into the `packages` folder
- Edit the json file to point to the Copernicus Toolkit parent directory (edit the "COPERNICUS_TOOLKIT" line)
- This package is designed for Houdini 20.5 (current) or higher (future versions)
- For more information on how package files work, see the [official Houdini documentation](https://www.sidefx.com/docs/houdini/ref/plugins.html)

## Tools Included

- [Growth Propagation](#growth-propagation) - Create organic growth patterns and DLA-style structures
- [Pixel Sorting](#pixel-sorting) - Advanced pixel manipulation algorithms


### Growth Propagation
Generate organic spreading patterns from simple masks to complex vein structures. Inspired by Nick Tylor's Aelib but completely reimagined for COPs.

- **Versatile Effects**: Create cellular growth, lightning, cracks, veins, and DLA-style structures with a single tool
- **Directional Control**: Shape growth patterns with directional fields and attractors
- **Animation Ready**: Perfect for evolving textures in motion graphics projects
  
<img src="https://github.com/Boning1011/copernicus-toolkit/blob/main/demo/growth_propagation/growth_02.gif" width="320" height="320"/><img src="https://github.com/Boning1011/copernicus-toolkit/blob/main/demo/growth_propagation/growth_03.gif" width="320" height="320"/><img src="https://github.com/Boning1011/copernicus-toolkit/blob/main/demo/growth_propagation/growth_dirControl_01.gif" width="320" height="320"/>

### Pixel Sorting

A fast OpenCL implementation of the classic pixel sorting effect - widely used for creating glitch art, flowing textures, and stylized transitions. 

- **Performance Boost**: Get real-time feedback even with high iteration counts thanks to GPU acceleration
- **Simple Masking System**: Easily control where sorting occurs using luminance values or custom masks  
- **Animation Ready**: Create evolving effects with built-in growth animation parameters


