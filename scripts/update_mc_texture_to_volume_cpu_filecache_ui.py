"""Upgrade the live CPU texture-to-volume HDA to the File Cache-style UI."""

import hou


NODE_PATH = "/obj/geo1/mc_texture_to_volume_cpu1"
BUILD_SCRIPT = "C:/Users/boning/Documents/GitHub/motion-cops/scripts/build_mc_texture_to_volume_cpu.py"
MODULE_SOURCE = "C:/Users/boning/Documents/GitHub/motion-cops/scripts/mc_texture_to_volume_cpu.py"


builder_source = hou.readFile(BUILD_SCRIPT)
builder_helpers = builder_source.split("\nparent = hou.node", 1)[0]
exec(compile(builder_helpers, BUILD_SCRIPT, "exec"), globals())

node = hou.node(NODE_PATH)
if node is None:
    raise hou.NodeError("Missing {}".format(NODE_PATH))
definition = node.type().definition()

old_values = {
    "external_cop": node.evalParm("cop_source"),
    "frame_range": (
        float(node.evalParm("start_frame")),
        float(node.evalParm("end_frame")),
        float(node.evalParm("frame_step")),
    ),
    "image_size": float(node.evalParm("xy_size")),
    "volume_name": node.evalParm("volume_name"),
    "channel": int(node.evalParm("channel")),
    "flip_y": int(node.evalParm("flip_y")),
    "memory_limit_gib": float(node.evalParm("memory_limit_gib")),
    "preview_resolution": int(node.evalParm("preview_resolution")),
    "preview_density": float(node.evalParm("preview_density")),
}

full_cache = node.node("cpu_volume_cache")
old_preview_node = node.node("viewport_preview_resample")
full_geometry = full_cache.geometry().freeze()
preview_geometry = old_preview_node.geometry().freeze()

node.allowEditingOfContents()
full_cache = node.node("cpu_volume_cache")
full_cache.parm("stash").set(hou.Geometry())

preview_cache = node.node("viewport_preview_cache")
if preview_cache is None:
    preview_cache = node.createNode("stash", "viewport_preview_cache")
preview_cache.setComment("Progressive low-resolution viewport volume")
preview_cache.parm("stash").set(hou.Geometry())

preview_filter = node.node("viewport_preview_resample")
if preview_filter is not None:
    preview_filter.setName("viewport_preview_filter", unique_name=True)
else:
    preview_filter = node.node("viewport_preview_filter")
if preview_filter is None:
    preview_filter = node.createNode("volumeresample", "viewport_preview_filter")
preview_filter.setInput(0, preview_cache)
preview_filter.setParms({"fixedresample": 0, "scale": 1.0})

visualize = node.node("viewport_density_visualization")
visualize.setInput(0, preview_filter)
visualize.parm("densityfield").setExpression(
    'chs("../volume_name")', hou.exprLanguage.Hscript
)
visualize.parm("densityscale").setExpression(
    'ch("../preview_density")', hou.exprLanguage.Hscript
)

full_cache.setPosition(hou.Vector2(1.5, 2.0))
node.node("FULL_CPU_VOLUME").setPosition(hou.Vector2(1.5, -2.5))
preview_cache.setPosition(hou.Vector2(-1.5, 2.0))
preview_filter.setPosition(hou.Vector2(-1.5, 0.5))
visualize.setPosition(hou.Vector2(-1.5, -1.0))
node.node("VIEWPORT_PREVIEW").setPosition(hou.Vector2(-1.5, -2.5))

definition.updateFromNode(node)
definition.setMinNumInputs(0)
definition.setMaxNumInputs(1)
definition.setMaxNumOutputs(2)
definition.setParmTemplateGroup(build_parameter_interface())
definition.addSection("PythonModule", hou.readFile(MODULE_SOURCE))
definition.addSection("EditableNodes", "cpu_volume_cache viewport_preview_cache")
definition.addSection(
    "Help",
    """= MC Texture to Volume CPU =

An in-memory, File Cache-style builder that stacks animated 2D COP/SOP slices
into one dense Float32 volume in CPU RAM.

Connect a COP Network directly to input 1. Its displayed COP node is used as
the source. Enable Use External COP only when an explicit node path is needed.
A File Cache or another SOP that outputs a dense 2D Volume can also be wired to
input 1.

Build Volume advances the timeline and updates a low-resolution viewport
volume while the full-resolution result grows in memory. Cancel preserves the
previous full cache and leaves the partial preview visible.

Stack Direction defaults to Y Up. Substeps samples fractional frames between
each Start/End/Inc frame interval.

@outputs

output1:
    Viewport Preview - progressive, low-resolution, and visualized.
output2:
    Full CPU Volume - untouched full-resolution dense volume.
""",
)
patch_connector_labels(definition)
definition.save(definition.libraryFilePath())
node.matchCurrentDefinition()

node.setParms(
    {
        "use_external_cop": 0,
        "external_cop": old_values["external_cop"],
        "output_index": 0,
        "trange": 1,
        "substeps": 1,
        "initialize_sim": 1,
        "stack_axis": 0,
        "image_size": old_values["image_size"],
        "volume_name": old_values["volume_name"],
        "channel": old_values["channel"],
        "flip_y": old_values["flip_y"],
        "preview_resolution": old_values["preview_resolution"],
        "preview_update_interval": 4,
        "preview_density": old_values["preview_density"],
        "memory_limit_gib": old_values["memory_limit_gib"],
        "status": "Ready. Existing cache preserved; rebuild once for the new Y Up direction.",
    }
)
for parm_name, value in zip(("f1", "f2", "f3"), old_values["frame_range"]):
    parm = node.parm(parm_name)
    parm.deleteAllKeyframes()
    parm.set(value)
node.node("cpu_volume_cache").parm("stash").set(full_geometry)
node.node("viewport_preview_cache").parm("stash").set(preview_geometry)

copnet = hou.node("/obj/geo1/copnet1")
if copnet is not None:
    node.setInput(0, copnet)
node.setSelected(True, clear_all_selected=True)

print(
    {
        "node": node.path(),
        "input": node.input(0).path() if node.input(0) else None,
        "max_inputs": definition.maxNumInputs(),
        "max_outputs": definition.maxNumOutputs(),
        "sync": node.matchesCurrentDefinition(),
        "full_cache_prims": node.node("cpu_volume_cache").geometry().intrinsicValue(
            "primitivecount"
        ),
        "preview_cache_prims": node.node(
            "viewport_preview_cache"
        ).geometry().intrinsicValue("primitivecount"),
    }
)
