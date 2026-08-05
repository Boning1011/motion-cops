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


def viewport_callback(parm):
    parm.setScriptCallback(
        'exec(kwargs["node"].type().definition().sections()["PythonModule"].contents());viewport_settings_changed(kwargs)'
    )
    parm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    return parm


def heading(name, text):
    parm = hou.LabelParmTemplate(name, name, column_labels=(text,))
    parm.setTags({"sidefx::look": "block"})
    return parm


def build_parameter_interface():
    main = hou.FolderParmTemplate(
        "main", "Texture to Volume", folder_type=hou.folderType.Simple
    )
    main.addParmTemplate(heading("source_heading", "SOURCE"))
    record_timeline = hou.ToggleParmTemplate(
        "record_timeline", "Record While Playing", default_value=True
    )
    record_timeline.setHelp(
        "When enabled, pressing Play records each timeline sample into CPU memory."
    )
    main.addParmTemplate(settings_callback(record_timeline))
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

    main.addParmTemplate(hou.SeparatorParmTemplate("source_sep"))
    main.addParmTemplate(callback_button("clear", "Clear Memory", "clear"))

    main.addParmTemplate(hou.SeparatorParmTemplate("frame_sep"))
    main.addParmTemplate(heading("frame_heading", "FRAME RANGE"))
    main.addParmTemplate(
        settings_callback(hou.MenuParmTemplate(
            "trange",
            "Valid Frame Range",
            ("off", "normal"),
            ("Current Frame Only", "Frame Range"),
            default_value=1,
        ))
    )
    frame_range = hou.FloatParmTemplate(
        "f",
        "Start/End/Inc",
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
    frame_range.setConditional(hou.parmCondType.DisableWhen, "{ trange == off }")
    main.addParmTemplate(settings_callback(frame_range))
    main.addParmTemplate(
        settings_callback(hou.IntParmTemplate(
            "substeps", "Substeps", 1, default_value=(1,), min=1, max=64
        ))
    )
    main.addParmTemplate(
        settings_callback(hou.ToggleParmTemplate(
            "initialize_sim", "Initialize Simulation OPs", default_value=True
        ))
    )

    main.addParmTemplate(hou.SeparatorParmTemplate("volume_sep"))
    main.addParmTemplate(heading("volume_heading", "VOLUME"))
    main.addParmTemplate(
        settings_callback(hou.MenuParmTemplate(
            "stack_axis",
            "Stack Direction",
            ("y", "z"),
            ("Y Up", "Z Forward"),
            default_value=0,
        ))
    )
    for parm_name, label, default in (
        ("voxel_resolution", "Voxel Resolution", "Unavailable"),
        ("world_size", "World Size", "Unavailable"),
        ("raw_memory", "Raw CPU Memory", "Unavailable"),
        ("peak_memory", "Temporary Peak", "Unavailable"),
    ):
        result_info = hou.StringParmTemplate(
            parm_name, label, 1, default_value=(default,)
        )
        result_info.setConditional(
            hou.parmCondType.DisableWhen,
            "{ use_external_cop == 0 } { use_external_cop == 1 }",
        )
        main.addParmTemplate(result_info)
    main.addParmTemplate(
        settings_callback(hou.StringParmTemplate(
            "volume_name", "Volume Name", 1, default_value=("density",)
        ))
    )
    main.addParmTemplate(
        settings_callback(hou.MenuParmTemplate(
            "channel",
            "Source Channel",
            ("first", "r", "g", "b", "a", "luma"),
            ("First", "Red", "Green", "Blue", "Alpha", "Luminance"),
            default_value=0,
        ))
    )
    main.addParmTemplate(settings_callback(hou.ToggleParmTemplate(
        "flip_y", "Flip Source Y", default_value=False
    )))

    main.addParmTemplate(hou.SeparatorParmTemplate("viewport_sep"))
    main.addParmTemplate(heading("viewport_heading", "VIEWPORT"))
    live_updates = hou.ToggleParmTemplate(
        "live_viewport_updates", "Show Live Viewport", default_value=True
    )
    live_updates.setHelp(
        "Disable this to hide the HDA and stop viewport texture uploads while recording. CPU recording continues normally."
    )
    main.addParmTemplate(viewport_callback(live_updates))
    use_proxy = hou.ToggleParmTemplate(
        "use_viewport_proxy", "Use Low Resolution Proxy", default_value=True
    )
    use_proxy.setHelp(
        "Display the internal proxy in the viewport. The HDA's single output always remains full resolution."
    )
    main.addParmTemplate(viewport_callback(use_proxy))
    main.addParmTemplate(
        settings_callback(hou.IntParmTemplate(
            "preview_resolution",
            "Preview Max Resolution",
            1,
            default_value=(256,),
            min=16,
            max=1024,
        ))
    )
    update_interval = hou.IntParmTemplate(
            "preview_update_interval",
            "Update Every N Slices",
            1,
            default_value=(8,),
            min=1,
            max=128,
    )
    update_interval.setHelp(
        "Higher values reduce viewport texture uploads. They do not change recorded volume resolution."
    )
    main.addParmTemplate(viewport_callback(update_interval))
    main.addParmTemplate(
        hou.FloatParmTemplate(
            "preview_density",
            "Density Scale",
            1,
            default_value=(1.0,),
            min=0.0,
            max=100.0,
        )
    )
    main.addParmTemplate(
        settings_callback(hou.FloatParmTemplate(
            "memory_limit_gib",
            "Memory Limit (GiB)",
            1,
            default_value=(32.0,),
            min=0.1,
            max=128.0,
        ))
    )
    status = hou.StringParmTemplate(
        "status",
        "Status",
        1,
        default_value=("Connect a source, then press Play to record.",),
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
    added_outputs = False
    for line in dialog.splitlines():
        stripped = line.strip()
        if stripped.startswith("inputlabel"):
            if "\t1\t" in line or stripped.startswith("inputlabel 1 "):
                lines.append('    inputlabel\t1\t"COP Network / Cached Slice"')
            continue
        if stripped.startswith("outputlabel"):
            continue
        lines.append(line)
        if stripped.startswith("inputlabel") and not added_outputs:
            added_outputs = True
    insert_at = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("group")),
        len(lines),
    )
    lines[insert_at:insert_at] = [
        '    outputlabel\t1\t"Full CPU Volume"',
        "",
    ]
    definition.sections()["DialogScript"].setContents("\n".join(lines) + "\n")


parent = hou.node("/obj/geo1")
if parent is None:
    raise hou.NodeError("Missing /obj/geo1")
if hou.node(INSTANCE_PATH) is not None:
    raise hou.NodeError("{} already exists".format(INSTANCE_PATH))
if os.path.exists(LIBRARY):
    raise hou.NodeError("Asset library already exists: {}".format(LIBRARY))

subnet = parent.createNode("subnet", "mc_texture_to_volume_cpu1")
subnet.setPosition(hou.Vector2(-4.0, -4.0))
full_cache = subnet.createNode("stash", "cpu_volume_cache")
full_cache.setComment("Full-resolution dense volume stored in CPU RAM")
preview_cache = subnet.createNode("stash", "viewport_preview_cache")
preview_cache.setComment("Progressive low-resolution viewport volume")
preview_filter = subnet.createNode("volumeresample", "viewport_preview_filter")
preview_filter.setInput(0, preview_cache)
preview_filter.setParms({"fixedresample": 0, "scale": 1.0})
visualize = subnet.createNode("volumevisualization", "viewport_density_visualization")
visualize.setInput(0, preview_filter)
preview_output = subnet.createNode("output", "VIEWPORT_PREVIEW")
preview_output.parm("outputidx").set(1)
preview_output.setInput(0, visualize)
full_output = subnet.createNode("output", "FULL_CPU_VOLUME")
full_output.parm("outputidx").set(0)
full_output.setInput(0, full_cache)

full_cache.setPosition(hou.Vector2(1.5, 2.0))
full_output.setPosition(hou.Vector2(1.5, -2.5))
preview_cache.setPosition(hou.Vector2(-1.5, 2.0))
preview_filter.setPosition(hou.Vector2(-1.5, 0.5))
visualize.setPosition(hou.Vector2(-1.5, -1.0))
preview_output.setPosition(hou.Vector2(-1.5, -2.5))

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
definition.setMaxNumOutputs(1)
definition.setParmTemplateGroup(build_parameter_interface())
definition.addSection("PythonModule", hou.readFile(MODULE_SOURCE))
definition.addSection("EditableNodes", "cpu_volume_cache viewport_preview_cache")
definition.addSection(
    "Help",
    """= MC Texture to Volume CPU =

An in-memory timeline recorder that stacks animated 2D COP/SOP slices into one
dense Float32 volume in CPU RAM.

Connect a COP Network directly to input 1. Its displayed COP node is used as
the source. Enable Use External COP only when an explicit node path is needed.
A File Cache or another SOP that outputs a dense 2D Volume can also be wired to
input 1.

Enable Record While Playing and press Play. The asset allocates the complete
dense volume from the source resolution and frame range, then writes each
timeline sample into its corresponding slice. Playback is temporarily switched
to play-every-frame mode so no samples are skipped. Pausing preserves progress;
press Play again to continue.

The HDA exposes one production output: the full-resolution CPU volume. Use Low
Resolution Proxy affects only the node's viewport display. Show Live Viewport
can be disabled entirely, and Update Every N Slices controls texture upload
frequency while it is enabled.

The source width is normalized to one world unit. Source aspect ratio controls
the other image dimension, and frame count controls the stack dimension. The
Resulting Volume field reports exact voxel resolution, world size, and raw RAM
before recording starts.

@outputs

output1:
    Full CPU Volume - completed full-resolution dense volume for downstream use.
""",
)

visualize = asset.node("viewport_density_visualization")
visualize.parm("densityfield").setExpression('chs("../volume_name")', hou.exprLanguage.Hscript)
visualize.parm("densityscale").setExpression('ch("../preview_density")', hou.exprLanguage.Hscript)
definition.updateFromNode(asset)
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
        "editable_nodes": definition.sections()["EditableNodes"].contents(),
    }
)
