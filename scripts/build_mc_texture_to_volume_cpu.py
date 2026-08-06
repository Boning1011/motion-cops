"""Build boning::mc_texture_to_volume_cpu::1.0 from scratch."""

import os

import hou


ASSET_NAME = "boning::mc_texture_to_volume_cpu::1.0"
ASSET_LABEL = "MC Texture to Volume CPU"
LIBRARY = "C:/Users/boning/Documents/GitHub/motion-cops/otls/sop_boning.mc_texture_to_volume_cpu.1.0.hdalc"
MODULE_SOURCE = "C:/Users/boning/Documents/GitHub/motion-cops/scripts/mc_texture_to_volume_cpu.py"
INSTANCE_PATH = "/obj/geo1/mc_texture_to_volume_cpu1"


def callback_button(name, label, function_name):
    parm = hou.ButtonParmTemplate(name, label)
    parm.setScriptCallback(
        'exec(kwargs["node"].type().definition().sections()["PythonModule"].contents());{}(kwargs)'.format(
            function_name
        )
    )
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def settings_callback(parm):
    parm.setScriptCallback(
        'exec(kwargs["node"].type().definition().sections()["PythonModule"].contents());settings_changed(kwargs)'
    )
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def heading(name, text):
    parm = hou.LabelParmTemplate(name, name, column_labels=(text,))
    parm.setTags({"sidefx::look": "block"})
    return parm


def result_string(name, label):
    parm = hou.StringParmTemplate(name, label, 1, default_value=("Unavailable",))
    parm.setConditional(
        hou.parmCondType.DisableWhen,
        "{ use_external_cop == 0 } { use_external_cop == 1 }",
    )
    return parm


def build_parameter_interface():
    main = hou.FolderParmTemplate(
        "main", "Texture to Volume", folder_type=hou.folderType.Simple
    )

    main.addParmTemplate(heading("source_heading", "SOURCE"))
    use_external = hou.ToggleParmTemplate(
        "use_external_cop", "Use External COP", default_value=False
    )
    main.addParmTemplate(settings_callback(use_external))
    external = hou.StringParmTemplate(
        "external_cop",
        "External COP / SOP",
        1,
        default_value=("",),
        string_type=hou.stringParmType.NodeReference,
    )
    external.setConditional(hou.parmCondType.HideWhen, "{ use_external_cop == 0 }")
    main.addParmTemplate(settings_callback(external))
    output_index = hou.IntParmTemplate(
        "output_index", "Output Index", 1, default_value=(0,), min=0, max=16
    )
    output_index.setConditional(
        hou.parmCondType.HideWhen, "{ use_external_cop == 0 }"
    )
    main.addParmTemplate(settings_callback(output_index))
    main.addParmTemplate(
        settings_callback(
            hou.MenuParmTemplate(
                "channel",
                "Source Channel",
                ("first", "r", "g", "b", "a", "luma"),
                ("First", "Red", "Green", "Blue", "Alpha", "Luminance"),
                default_value=0,
            )
        )
    )
    main.addParmTemplate(
        settings_callback(
            hou.ToggleParmTemplate("flip_y", "Flip Source Y", default_value=False)
        )
    )

    main.addParmTemplate(hou.SeparatorParmTemplate("simulation_sep"))
    main.addParmTemplate(heading("simulation_heading", "SIMULATION"))
    resolution = hou.IntParmTemplate(
        "resolution",
        "Resolution",
        1,
        default_value=(256,),
        min=16,
        max=4096,
    )
    resolution.setHelp(
        "This is the actual output width, not a display proxy. Use a lower value while working, then set it to the source width, reset, and replay for the final cache."
    )
    main.addParmTemplate(settings_callback(resolution))
    frame_range = hou.FloatParmTemplate(
        "f",
        "Frame Range",
        3,
        default_value=(1.0, 240.0, 1.0),
        default_expression=("$FSTART", "$FEND", ""),
        default_expression_language=(
            hou.scriptLanguage.Hscript,
            hou.scriptLanguage.Hscript,
            hou.scriptLanguage.Hscript,
        ),
        naming_scheme=hou.parmNamingScheme.Base1,
    )
    main.addParmTemplate(settings_callback(frame_range))
    main.addParmTemplate(
        settings_callback(
            hou.IntParmTemplate(
                "substeps", "Substeps", 1, default_value=(1,), min=1, max=64
            )
        )
    )
    main.addParmTemplate(
        settings_callback(
            hou.MenuParmTemplate(
                "stack_axis",
                "Stack Direction",
                ("y", "z"),
                ("Y Up", "Z Forward"),
                default_value=0,
            )
        )
    )
    main.addParmTemplate(callback_button("reset", "Reset Simulation", "reset"))

    main.addParmTemplate(hou.SeparatorParmTemplate("output_sep"))
    main.addParmTemplate(heading("output_heading", "OUTPUT"))
    main.addParmTemplate(
        settings_callback(
            hou.StringParmTemplate(
                "volume_name", "Volume Name", 1, default_value=("density",)
            )
        )
    )
    main.addParmTemplate(result_string("source_resolution", "Source Resolution"))
    main.addParmTemplate(result_string("output_resolution", "Final Resolution"))
    status = hou.StringParmTemplate(
        "status",
        "Status",
        1,
        default_value=("Connect a source, then press Play from the range start.",),
    )
    status.setConditional(
        hou.parmCondType.DisableWhen,
        "{ use_external_cop == 0 } { use_external_cop == 1 }",
    )
    main.addParmTemplate(status)

    group = hou.ParmTemplateGroup()
    group.append(main)
    return group


def patch_connector_labels(definition):
    dialog = definition.sections()["DialogScript"].contents()
    lines = []
    for line in dialog.splitlines():
        stripped = line.strip()
        if stripped.startswith("inputlabel") or stripped.startswith("outputlabel"):
            continue
        lines.append(line)
    insert_at = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("group")),
        len(lines),
    )
    lines[insert_at:insert_at] = [
        '    inputlabel\t1\t"COP Network / Cached Slice"',
        '    outputlabel\t1\t"Growing Sparse VDB"',
        "",
    ]
    definition.sections()["DialogScript"].setContents("\n".join(lines) + "\n")


def configure_sparse_nodes(asset):
    accumulated = asset.createNode("stash", "cpu_volume_cache")
    accumulated.setComment("Growing sparse VDB simulation state")
    current_slice = asset.createNode("stash", "viewport_preview_cache")
    current_slice.setComment("Current low-cost 2D source slice")
    convert = asset.createNode("convertvdb", "slice_to_vdb")
    convert.setInput(0, current_slice)
    convert.setParms({"conversion": 1, "vdbclass": 2, "prune": 1})
    combine = asset.createNode("vdbcombine", "vdb_accumulate")
    combine.setInput(0, accumulated)
    combine.setInput(1, convert)
    combine.setParms(
        {
            "collation": "pairs",
            "operation": "add",
            "deactivate": 1,
            "prune": 1,
        }
    )
    output = asset.createNode("output", "VDB_OUTPUT")
    output.parm("outputidx").set(0)
    output.setInput(0, accumulated)
    accumulated.setPosition(hou.Vector2(-2.0, 1.5))
    current_slice.setPosition(hou.Vector2(2.0, 1.5))
    convert.setPosition(hou.Vector2(2.0, 0.0))
    combine.setPosition(hou.Vector2(0.0, -1.5))
    output.setPosition(hou.Vector2(-2.0, -1.5))
    return accumulated, current_slice


parent = hou.node("/obj/geo1")
if parent is None:
    raise hou.NodeError("Missing /obj/geo1")
if hou.node(INSTANCE_PATH) is not None:
    raise hou.NodeError("{} already exists".format(INSTANCE_PATH))
if os.path.exists(LIBRARY):
    raise hou.NodeError("Asset library already exists: {}".format(LIBRARY))

subnet = parent.createNode("subnet", "mc_texture_to_volume_cpu1")
subnet.setPosition(hou.Vector2(-4.0, -4.0))
configure_sparse_nodes(subnet)
asset = subnet.createDigitalAsset(
    name=ASSET_NAME,
    hda_file_name=LIBRARY,
    description=ASSET_LABEL,
    min_num_inputs=0,
    max_num_inputs=1,
    compress_contents=True,
    ignore_external_references=True,
)
definition = asset.type().definition()
definition.setMinNumInputs(0)
definition.setMaxNumInputs(1)
definition.setMaxNumOutputs(1)
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

A timeline-driven sparse VDB stack, designed to feel like a simple Pyro
simulation. Connect a COP Network or cached 2D Volume, move to the range start,
and press Play. The output grows by one sparse VDB slice per timeline sample.

Resolution is the real output resolution. Use 128 or 256 while working. For a
final cache, set Resolution to the source width, press Reset Simulation, replay,
and connect a normal File Cache downstream. There is no separate proxy or hidden
full-resolution mode.

Only the elapsed stack region exists. Early frames therefore have a small active
bounding box, and empty background voxels remain sparse.

@outputs

output1:
    Growing Sparse VDB - current simulation state for viewport and caching.
""",
)
patch_connector_labels(definition)
definition.save(LIBRARY)
asset.matchCurrentDefinition()
asset.setColor(hou.Color(0.22, 0.48, 0.72))
asset.setUserData("nodeshape", "tabbed_left")
asset.setSelected(True, clear_all_selected=True)
module_scope = {}
exec(
    compile(
        definition.sections()["PythonModule"].contents(),
        "MCTextureToVolumePythonModule",
        "exec",
    ),
    module_scope,
)
module_scope["install_live"]({"node": asset})

print(
    {
        "asset": asset.path(),
        "library": definition.libraryFilePath(),
        "inputs": definition.maxNumInputs(),
        "outputs": definition.maxNumOutputs(),
    }
)
