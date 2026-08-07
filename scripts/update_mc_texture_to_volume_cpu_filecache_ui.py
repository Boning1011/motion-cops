"""Upgrade the CPU texture stack HDA to one growing sparse VDB output."""

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


def parm_value(name, default):
    parm = node.parm(name)
    return parm.eval() if parm is not None else default


old_values = {
    "use_external_cop": int(parm_value("use_external_cop", 0)),
    "external_cop": str(parm_value("external_cop", "")),
    "output_index": int(parm_value("output_index", 0)),
    "frame_range": (
        float(parm_value("f1", 1.0)),
        float(parm_value("f2", 240.0)),
        float(parm_value("f3", 1.0)),
    ),
    "substeps": int(parm_value("substeps", 1)),
    "stack_axis": int(parm_value("stack_axis", 0)),
    "volume_name": str(parm_value("volume_name", "density")),
    "channel": int(parm_value("channel", 0)),
    "flip_y": int(parm_value("flip_y", 0)),
    "resolution": int(
        parm_value("resolution", parm_value("preview_resolution", 256))
    ),
    "display_density": float(parm_value("display_density", 1000.0)),
}
display_flag = node.isDisplayFlagSet()

if hou.playbar.isPlaying():
    hou.playbar.stop()

full_cache = node.node("cpu_volume_cache")
slice_cache = node.node("viewport_preview_cache")
if full_cache is None or slice_cache is None:
    raise hou.NodeError("Required internal Stash nodes are missing.")
full_cache.parm("stash").set(hou.Geometry())
slice_cache.parm("stash").set(hou.Geometry())

node.allowEditingOfContents()
convert = node.node("slice_to_vdb")
if convert is None:
    convert = node.createNode("convertvdb", "slice_to_vdb")
convert.setInput(0, slice_cache)
convert.setParms({"conversion": 1, "vdbclass": 2, "prune": 1})

combine = node.node("vdb_accumulate")
if combine is None:
    combine = node.createNode("vdbcombine", "vdb_accumulate")
combine.setInput(0, full_cache)
combine.setInput(1, convert)
combine.setParms(
    {
        "collation": "pairs",
        "operation": "add",
        "deactivate": 1,
        "prune": 1,
    }
)

full_output = node.node("FULL_CPU_VOLUME")
if full_output is None:
    full_output = node.createNode("output", "FULL_CPU_VOLUME")
full_output.parm("outputidx").set(0)
visualize = node.node("viewport_density_visualization")
if visualize is None:
    visualize = node.createNode(
        "volumevisualization", "viewport_density_visualization"
    )
visualize.setInput(0, full_cache)
visualize.parm("densityfield").setExpression(
    'chs("../volume_name")', hou.exprLanguage.Hscript
)
visualize.parm("densityscale").setExpression(
    'ch("../display_density")', hou.exprLanguage.Hscript
)
full_output.setInput(0, visualize)

old_preview_output = node.node("VIEWPORT_PREVIEW")
if old_preview_output is not None:
    old_preview_output.setInput(0, None)
    old_preview_output.setDisplayFlag(False)
    old_preview_output.setRenderFlag(False)

full_cache.setComment("Growing sparse VDB simulation state")
slice_cache.setComment("Current low-cost 2D source slice")
full_cache.setPosition(hou.Vector2(-2.0, 1.5))
slice_cache.setPosition(hou.Vector2(2.0, 1.5))
convert.setPosition(hou.Vector2(2.0, 0.0))
combine.setPosition(hou.Vector2(0.0, -1.5))
visualize.setPosition(hou.Vector2(-2.0, -0.25))
full_output.setPosition(hou.Vector2(-2.0, -2.0))

definition.updateFromNode(node)
definition.setMinNumInputs(0)
definition.setMaxNumInputs(1)
definition.setMaxNumOutputs(1)
definition.setParmTemplateGroup(build_parameter_interface())
definition.addSection("PythonModule", hou.readFile(MODULE_SOURCE))
definition.addSection("EditableNodes", "cpu_volume_cache viewport_preview_cache")
definition.addSection(
    "OnCreated",
    'exec(kwargs["type"].definition().sections()["PythonModule"].contents());bootstrap_live(kwargs)',
)
definition.addSection(
    "OnLoaded",
    'exec(kwargs["type"].definition().sections()["PythonModule"].contents());bootstrap_live(kwargs)',
)
definition.addSection(
    "Help",
    """= MC Texture to Volume CPU =

A timeline-driven sparse VDB stack, designed to feel like a simple Pyro
simulation. Connect a COP Network or cached 2D Volume, move to the range start,
and press Play. The output grows by one sparse VDB slice per timeline sample.

Resolution is the real output resolution. Use 128 or 256 while working. For a
final cache, set Resolution to the source width, press Reset Simulation, replay,
and connect a normal File Cache downstream. There is no separate proxy or hidden
full-resolution mode.

Only the elapsed stack region exists. Early frames therefore have a small active
bounding box, and empty background voxels remain sparse.

Display Density defaults to 1000 for a solid viewport preview and affects only
visualization metadata. Jumping directly to a timeline frame cooks from the
range start to that frame with native Houdini progress and Escape interruption.

@outputs

output1:
    Growing Sparse VDB - current simulation state for viewport and caching.
""",
)
patch_connector_labels(definition)
definition.save(definition.libraryFilePath())
node.matchCurrentDefinition()

node.setParms(
    {
        "use_external_cop": old_values["use_external_cop"],
        "external_cop": old_values["external_cop"],
        "output_index": old_values["output_index"],
        "substeps": old_values["substeps"],
        "stack_axis": old_values["stack_axis"],
        "volume_name": old_values["volume_name"],
        "channel": old_values["channel"],
        "flip_y": old_values["flip_y"],
        "resolution": old_values["resolution"],
        "display_density": old_values["display_density"],
    }
)
for parm_name, value in zip(("f1", "f2", "f3"), old_values["frame_range"]):
    parm = node.parm(parm_name)
    parm.deleteAllKeyframes()
    parm.set(value)

node.node("cpu_volume_cache").parm("stash").set(hou.Geometry())
node.node("viewport_preview_cache").parm("stash").set(hou.Geometry())
node.setOutputForViewFlag(0)
node.setDisplayFlag(display_flag)

module_scope = {}
exec(
    compile(
        definition.sections()["PythonModule"].contents(),
        "MCTextureToVolumePythonModule",
        "exec",
    ),
    module_scope,
)
module_scope["install_live"]({"node": node})
module_scope["reset"]({"node": node})
node.setSelected(True, clear_all_selected=True)

print(
    {
        "node": node.path(),
        "input": node.input(0).path() if node.input(0) else None,
        "resolution": node.evalParm("resolution"),
        "source_resolution": node.evalParm("source_resolution"),
        "output_resolution": node.evalParm("output_resolution"),
        "outputs": definition.maxNumOutputs(),
        "sync": node.matchesCurrentDefinition(),
    }
)
