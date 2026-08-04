"""Build or refresh the MC Texture to Volume CPU SOP HDA."""

import os

import hou


ASSET_NAME = "boning::mc_texture_to_volume_cpu::1.0"
ASSET_LABEL = "MC Texture to Volume CPU"
LIBRARY = "C:/Users/boning/Documents/GitHub/motion-cops/otls/sop_boning.mc_texture_to_volume_cpu.1.0.hdalc"
MODULE_SOURCE = "C:/Users/boning/Documents/GitHub/motion-cops/scripts/mc_texture_to_volume_cpu.py"
INSTANCE_PATH = "/obj/geo1/mc_texture_to_volume_cpu1"


def button(name, label, function_name):
    parm = hou.ButtonParmTemplate(name, label)
    parm.setScriptCallback(
        'exec(kwargs["node"].type().definition().sections()["PythonModule"].contents());{}(kwargs)'.format(
            function_name
        )
    )
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


parent = hou.node("/obj/geo1")
if parent is None:
    raise hou.NodeError("Missing /obj/geo1")
if hou.node(INSTANCE_PATH) is not None:
    raise hou.NodeError("{} already exists".format(INSTANCE_PATH))
if os.path.exists(LIBRARY):
    raise hou.NodeError("Asset library already exists: {}".format(LIBRARY))

subnet = parent.createNode("subnet", "mc_texture_to_volume_cpu1")
subnet.setPosition(hou.Vector2(-4.0, -4.0))

cache = subnet.createNode("stash", "cpu_volume_cache")
cache.setComment("Full-resolution dense volume stored in CPU RAM")

preview = subnet.createNode("volumeresample", "viewport_preview_resample")
preview.setInput(0, cache)
preview.setParms({"fixedresample": 1, "uniformsamples": 4, "samplediv": 256})

visualize = subnet.createNode("volumevisualization", "viewport_density_visualization")
visualize.setInput(0, preview)
visualize.setParms({"densityfield": "density", "densityscale": 1.0})

preview_output = subnet.createNode("output", "VIEWPORT_PREVIEW")
preview_output.parm("outputidx").set(0)
preview_output.setInput(0, visualize)

full_output = subnet.createNode("output", "FULL_CPU_VOLUME")
full_output.parm("outputidx").set(1)
full_output.setInput(0, cache)

cache.setPosition(hou.Vector2(0.0, 2.0))
preview.setPosition(hou.Vector2(-1.5, 0.5))
visualize.setPosition(hou.Vector2(-1.5, -1.0))
preview_output.setPosition(hou.Vector2(-1.5, -2.5))
full_output.setPosition(hou.Vector2(1.5, -2.5))

asset = subnet.createDigitalAsset(
    name=ASSET_NAME,
    hda_file_name=LIBRARY,
    description=ASSET_LABEL,
    min_num_inputs=0,
    max_num_inputs=0,
    compress_contents=True,
    ignore_external_references=True,
)
definition = asset.type().definition()
definition.setMaxNumOutputs(2)

source_folder = hou.FolderParmTemplate("source", "Source")
cop_source = hou.StringParmTemplate(
    "cop_source",
    "COP Source",
    1,
    default_value=("/obj/geo1/copnet1/reactiondiffusion_block_end1",),
    string_type=hou.stringParmType.NodeReference,
)
cop_source.setTags({"opfilter": "!!COP!!", "oprelative": "."})
source_folder.addParmTemplate(cop_source)
source_folder.addParmTemplate(
    hou.IntParmTemplate("output_index", "Output Index", 1, default_value=(0,), min=0, max=16)
)
source_folder.addParmTemplate(button("inspect", "Inspect Source", "inspect_source"))

range_folder = hou.FolderParmTemplate("frame_range", "Frame Range")
range_folder.addParmTemplate(
    hou.IntParmTemplate("start_frame", "Start Frame", 1, default_value=(1,))
)
range_folder.addParmTemplate(
    hou.IntParmTemplate("end_frame", "End Frame", 1, default_value=(256,))
)
range_folder.addParmTemplate(
    hou.IntParmTemplate("frame_step", "Frame Step", 1, default_value=(1,), min=1, max=100)
)
range_folder.addParmTemplate(
    hou.ToggleParmTemplate("reset_source", "Reset Source Simulation", default_value=True)
)

volume_folder = hou.FolderParmTemplate("volume", "Volume")
volume_folder.addParmTemplate(
    hou.FloatParmTemplate("xy_size", "XY Size", 1, default_value=(2.0,), min=0.0001, max=100.0)
)
volume_folder.addParmTemplate(
    hou.StringParmTemplate("volume_name", "Volume Name", 1, default_value=("density",))
)
volume_folder.addParmTemplate(
    hou.MenuParmTemplate(
        "channel",
        "Source Channel",
        ("first", "r", "g", "b", "a", "luma"),
        ("First", "Red", "Green", "Blue", "Alpha", "Luminance"),
        default_value=0,
    )
)
volume_folder.addParmTemplate(
    hou.ToggleParmTemplate("flip_y", "Flip Source Y", default_value=False)
)

build_folder = hou.FolderParmTemplate("build_options", "Build")
build_folder.addParmTemplate(
    hou.FloatParmTemplate(
        "memory_limit_gib", "Raw Volume Limit (GiB)", 1, default_value=(32.0,), min=0.1, max=128.0
    )
)
build_folder.addParmTemplate(
    hou.IntParmTemplate(
        "preview_resolution", "Preview Max Resolution", 1, default_value=(256,), min=16, max=1024
    )
)
build_folder.addParmTemplate(
    hou.FloatParmTemplate(
        "preview_density", "Preview Density", 1, default_value=(1.0,), min=0.0, max=100.0
    )
)
build_folder.addParmTemplate(
    hou.ToggleParmTemplate("show_when_finished", "Show Preview When Finished", default_value=True)
)
build_folder.addParmTemplate(button("build", "Build CPU Volume", "build"))
build_folder.addParmTemplate(button("cancel", "Cancel Build", "cancel"))
build_folder.addParmTemplate(button("clear", "Clear CPU Cache", "clear"))
status = hou.StringParmTemplate(
    "status", "Status", 1, default_value=("Not built. Click Inspect Source or Build CPU Volume.",)
)
build_folder.addParmTemplate(status)

ptg = hou.ParmTemplateGroup()
ptg.append(source_folder)
ptg.append(range_folder)
ptg.append(volume_folder)
ptg.append(build_folder)
definition.setParmTemplateGroup(ptg)

module_text = hou.readFile(MODULE_SOURCE)
definition.addSection("PythonModule", module_text)
definition.addSection("EditableNodes", "cpu_volume_cache")
definition.addSection(
    "Help",
    """= MC Texture to Volume CPU =

Streams an animated Copernicus layer sequence into one dense Float32 Houdini
volume stored in CPU memory. The builder reads one frame at a time, so it does
not retain the complete image sequence on the GPU.

@parameters

COP Source:
    Animated Copernicus layer to sample.
Start/End Frame:
    Inclusive frame range used as the Z axis.
Build CPU Volume:
    Advances the Houdini timeline one frame at a time so simulation blocks cook
    normally, then streams each displayed COP slice into CPU RAM. The internal
    Stash is replaced only after a successful build.
Cancel Build:
    Stops an active build and preserves the previous cached volume.
Preview Max Resolution:
    Output 1 is a resampled viewport proxy. Output 2 is the untouched dense
    CPU volume for downstream processing and rendering.
Show Preview When Finished:
    Switches the SOP display flag to this asset after a successful build.

@outputs

output1:
    VIEWPORT_PREVIEW - resampled and visualized for interactive display.
output2:
    FULL_CPU_VOLUME - full-resolution dense Float32 volume from the CPU Stash.

Memory note: 512^3 Float32 is 0.5 GiB raw; 1024^3 is 4 GiB raw. Building and
stashing can temporarily use roughly twice the raw size. Viewport display may
still allocate a GPU texture, which is why the first output is a proxy.
""",
)

preview = asset.node("viewport_preview_resample")
preview.parm("samplediv").setExpression('ch("../preview_resolution")', hou.exprLanguage.Hscript)
visualize = asset.node("viewport_density_visualization")
visualize.parm("densityfield").setExpression('chs("../volume_name")', hou.exprLanguage.Hscript)
visualize.parm("densityscale").setExpression('ch("../preview_density")', hou.exprLanguage.Hscript)

definition.updateFromNode(asset)
definition.setMaxNumOutputs(2)
definition.setParmTemplateGroup(ptg)
definition.addSection("PythonModule", module_text)
definition.addSection("EditableNodes", "cpu_volume_cache")
definition.save(LIBRARY)
asset.matchCurrentDefinition()
asset.setColor(hou.Color(0.22, 0.48, 0.72))
asset.setUserData("nodeshape", "tabbed_left")
asset.setSelected(True, clear_all_selected=True)

print({
    "asset": asset.path(),
    "library": definition.libraryFilePath(),
    "outputs": definition.maxNumOutputs(),
    "parms": [p.name() for p in definition.parmTemplateGroup().parmTemplates()],
    "editable_nodes": definition.sections()["EditableNodes"].contents(),
})
