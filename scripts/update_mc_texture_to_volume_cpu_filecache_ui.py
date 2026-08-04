"""Upgrade the live CPU texture-to-volume HDA to timeline recording UX."""

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
    "trange": int(parm_value("trange", 1)),
    "frame_range": (
        float(parm_value("f1", 1.0)),
        float(parm_value("f2", 240.0)),
        float(parm_value("f3", 1.0)),
    ),
    "substeps": int(parm_value("substeps", 1)),
    "initialize_sim": int(parm_value("initialize_sim", 1)),
    "stack_axis": int(parm_value("stack_axis", 0)),
    "volume_name": str(parm_value("volume_name", "density")),
    "channel": int(parm_value("channel", 0)),
    "flip_y": int(parm_value("flip_y", 0)),
    "preview_resolution": int(parm_value("preview_resolution", 256)),
    "preview_density": float(parm_value("preview_density", 1.0)),
    "memory_limit_gib": float(parm_value("memory_limit_gib", 32.0)),
}

full_cache = node.node("cpu_volume_cache")
preview_cache = node.node("viewport_preview_cache")
full_geometry = full_cache.geometry().freeze()
preview_geometry = preview_cache.geometry().freeze()

definition.updateFromNode(node)
definition.setMinNumInputs(0)
definition.setMaxNumInputs(1)
definition.setMaxNumOutputs(2)
definition.setParmTemplateGroup(build_parameter_interface())
definition.addSection("PythonModule", hou.readFile(MODULE_SOURCE))
definition.addSection("EditableNodes", "cpu_volume_cache viewport_preview_cache")
definition.addSection(
    "OnCreated",
    'exec(kwargs["type"].definition().sections()["PythonModule"].contents());install_live(kwargs)',
)
definition.addSection(
    "OnLoaded",
    'exec(kwargs["type"].definition().sections()["PythonModule"].contents());install_live(kwargs)',
)
definition.addSection(
    "Help",
    """= MC Texture to Volume CPU =

An in-memory timeline recorder that stacks animated 2D COP/SOP slices into one
dense Float32 volume in CPU RAM.

Connect a COP Network directly to input 1, enable Record While Playing, and
press Play. The source resolution determines the image-plane voxel resolution;
the frame range and Substeps determine the stack resolution. Playback is
temporarily switched to play every frame so no samples are skipped.

Resulting Volume reports exact X/Y/Z voxel resolution, normalized world size,
and raw memory before recording. Pausing preserves progress and pressing Play
continues it. Returning to the range start begins a fresh recording.

@outputs

output1:
    Viewport Preview - progressive, low-resolution, and visualized.
output2:
    Full CPU Volume - completed full-resolution dense volume.
""",
)
patch_connector_labels(definition)
definition.save(definition.libraryFilePath())
node.matchCurrentDefinition()

node.setParms(
    {
        "record_timeline": 1,
        "use_external_cop": old_values["use_external_cop"],
        "external_cop": old_values["external_cop"],
        "output_index": old_values["output_index"],
        "trange": old_values["trange"],
        "substeps": old_values["substeps"],
        "initialize_sim": old_values["initialize_sim"],
        "stack_axis": old_values["stack_axis"],
        "volume_name": old_values["volume_name"],
        "channel": old_values["channel"],
        "flip_y": old_values["flip_y"],
        "preview_resolution": old_values["preview_resolution"],
        "preview_update_interval": 1,
        "preview_density": old_values["preview_density"],
        "memory_limit_gib": old_values["memory_limit_gib"],
        "status": "Ready. Press Play to record into CPU memory.",
    }
)
for parm_name, value in zip(("f1", "f2", "f3"), old_values["frame_range"]):
    parm = node.parm(parm_name)
    parm.deleteAllKeyframes()
    parm.set(value)

node.node("cpu_volume_cache").parm("stash").set(full_geometry)
node.node("viewport_preview_cache").parm("stash").set(preview_geometry)

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
node.setSelected(True, clear_all_selected=True)

print(
    {
        "node": node.path(),
        "input": node.input(0).path() if node.input(0) else None,
        "record_timeline": node.evalParm("record_timeline"),
        "voxel_resolution": node.evalParm("voxel_resolution"),
        "world_size": node.evalParm("world_size"),
        "raw_memory": node.evalParm("raw_memory"),
        "peak_memory": node.evalParm("peak_memory"),
        "sync": node.matchesCurrentDefinition(),
        "full_cache_prims": node.node("cpu_volume_cache").geometry().intrinsicValue(
            "primitivecount"
        ),
        "preview_cache_prims": node.node(
            "viewport_preview_cache"
        ).geometry().intrinsicValue("primitivecount"),
    }
)
