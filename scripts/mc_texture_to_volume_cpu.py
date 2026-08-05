"""PythonModule for boning::mc_texture_to_volume_cpu::1.0.

The HDA behaves like an in-memory File Cache: it samples a frame range from a
connected COP Network (or an optional external COP/SOP path), streams slices
into one full-resolution CPU volume, and updates a smaller viewport volume as
the stack grows.
"""

import math
import time

import hou
import numpy as np


def _set_status(node, message):
    parm = node.parm("status")
    if parm is not None:
        parm.set(str(message))


def _active_builds():
    name = "_mc_texture_to_volume_cpu_builds"
    builds = getattr(hou.session, name, None)
    if builds is None:
        builds = {}
        setattr(hou.session, name, builds)
    return builds


def _resolve_path(node, path):
    result = hou.node(path)
    if result is None:
        result = node.node(path)
    return result


def _as_source(candidate, output_index, label):
    if isinstance(candidate, hou.CopNode):
        return {
            "kind": "cop",
            "node": candidate,
            "output_index": output_index,
            "label": label,
        }
    if isinstance(candidate, hou.SopNode):
        if candidate.type().name() == "copnet":
            displayed = candidate.displayNode()
            if isinstance(displayed, hou.CopNode):
                return {
                    "kind": "cop",
                    "node": displayed,
                    "output_index": output_index,
                    "label": "{} -> {}".format(label, displayed.name()),
                }
        return {
            "kind": "sop",
            "node": candidate,
            "output_index": output_index,
            "label": label,
        }
    raise hou.NodeError("Source must be a COP node or a SOP that outputs a 2D volume.")


def _source(node):
    output_index = int(node.evalParm("output_index"))
    if node.evalParm("use_external_cop"):
        path = node.evalParm("external_cop").strip()
        if not path:
            raise hou.NodeError("Set External COP, or turn off Use External COP.")
        candidate = _resolve_path(node, path)
        if candidate is None:
            raise hou.NodeError("External COP does not exist: {}".format(path))
        return _as_source(candidate, output_index, "External: {}".format(candidate.path()))

    connections = node.inputConnections()
    if not connections:
        raise hou.NodeError(
            "Connect a COP Network or cached 2D volume to input 1, "
            "or enable Use External COP."
        )
    connection = connections[0]
    candidate = connection.inputNode()
    return _as_source(
        candidate,
        int(connection.outputIndex()),
        "Input: {}".format(candidate.path()),
    )


def _storage_layout(layer):
    storage = layer.storageType()
    if storage == hou.imageLayerStorageType.Float32:
        return np.float32, 1.0
    if storage == hou.imageLayerStorageType.Float16:
        return np.float16, 1.0
    if storage == hou.imageLayerStorageType.Fixed8:
        return np.uint8, 1.0 / 255.0
    if storage == hou.imageLayerStorageType.Fixed16:
        return np.uint16, 1.0 / 65535.0
    if storage == hou.imageLayerStorageType.Int8:
        return np.int8, 1.0
    if storage == hou.imageLayerStorageType.Int16:
        return np.int16, 1.0
    if storage == hou.imageLayerStorageType.Int32:
        return np.int32, 1.0
    raise hou.NodeError("Unsupported COP storage type: {}".format(storage))


def _layer_values(layer, channel_mode, flip_y):
    width, height = (int(v) for v in layer.bufferResolution())
    channels = int(layer.channelCount())
    dtype, scale = _storage_layout(layer)
    image = np.frombuffer(layer.allBufferElements(), dtype=dtype).reshape(
        height, width, channels
    )

    if channel_mode == 5:
        if channels < 3:
            selected = image[:, :, 0]
        else:
            selected = (
                image[:, :, 0].astype(np.float32) * 0.2126
                + image[:, :, 1].astype(np.float32) * 0.7152
                + image[:, :, 2].astype(np.float32) * 0.0722
            )
            scale = 1.0
    else:
        requested = 0 if channel_mode == 0 else channel_mode - 1
        if requested >= channels:
            raise hou.NodeError(
                "Requested channel {} but source has {} channel(s).".format(
                    requested, channels
                )
            )
        selected = image[:, :, requested]

    if selected.dtype != np.float32:
        selected = selected.astype(np.float32)
    elif not selected.flags.c_contiguous:
        selected = np.ascontiguousarray(selected)
    if scale != 1.0:
        selected *= scale
    if flip_y:
        selected = np.ascontiguousarray(selected[::-1, :])
    return selected, width, height


def _first_dense_volume(geometry):
    for prim in geometry.iterPrims():
        if isinstance(prim, hou.Volume):
            return prim
    raise hou.NodeError(
        "The connected SOP does not contain a dense 2D Volume. "
        "A File Cache after a COP Network is supported; convert VDBs to Volume first."
    )


def _geometry_values(geometry, flip_y):
    volume = _first_dense_volume(geometry)
    xres, yres, zres = (int(v) for v in volume.resolution())
    if zres == 1:
        width, height = xres, yres
        raw = volume.voxelSliceAsString("xy", 0)
    elif yres == 1:
        width, height = xres, zres
        raw = volume.voxelSliceAsString("xz", 0)
    else:
        raise hou.NodeError(
            "Connected SOP volume must be 2D (one resolution axis must equal 1)."
        )
    selected = np.frombuffer(raw, dtype=np.float32).reshape(height, width)
    if flip_y:
        selected = np.ascontiguousarray(selected[::-1, :])
    elif not selected.flags.c_contiguous:
        selected = np.ascontiguousarray(selected)
    return selected, width, height


def _probe(source, frame, channel_mode, flip_y):
    node = source["node"]
    output_index = source["output_index"]
    if source["kind"] == "cop":
        layer = node.layerAtFrame(frame, output_index)
        try:
            width, height = (int(v) for v in layer.bufferResolution())
            detail = "{} channel(s), {}".format(
                layer.channelCount(), layer.storageType()
            )
        finally:
            layer.close()
        return width, height, detail

    geometry = node.geometryAtFrame(frame, output_index)
    volume = _first_dense_volume(geometry)
    xres, yres, zres = (int(v) for v in volume.resolution())
    if zres == 1:
        width, height = xres, yres
    elif yres == 1:
        width, height = xres, zres
    else:
        raise hou.NodeError("Connected SOP volume is not a 2D slice.")
    return width, height, "dense SOP volume"


def _capture(source, channel_mode, flip_y):
    node = source["node"]
    output_index = source["output_index"]
    if source["kind"] == "cop":
        layer = node.layer(output_index)
        try:
            return _layer_values(layer, channel_mode, flip_y)
        finally:
            layer.close()
    return _geometry_values(node.geometry(output_index), flip_y)


def _sample_frames(node):
    if int(node.evalParm("trange")) == 0:
        return [float(hou.frame())]

    start, end, increment = (float(v) for v in node.evalParmTuple("f"))
    if end < start:
        raise hou.NodeError("End frame must be greater than or equal to Start.")
    if increment <= 0.0:
        raise hou.NodeError("Frame increment must be greater than zero.")
    substeps = max(1, int(node.evalParm("substeps")))
    sample_step = increment / float(substeps)
    count = int(math.floor((end - start) / sample_step + 1e-7)) + 1
    frames = [start + i * sample_step for i in range(count)]
    if frames[-1] < end - 1e-7:
        frames.append(end)
    return frames


def _frame_text(frame):
    if abs(frame - round(frame)) < 1e-7:
        return str(int(round(frame)))
    return "{:.4f}".format(frame).rstrip("0").rstrip(".")


def _layout(width, height, count, stack_axis):
    # Normalize the source width to one Houdini unit.  Every source pixel and
    # every timeline sample therefore has the same cubic voxel size.
    normalized_width = 1.0
    voxel_size = normalized_width / float(width)
    image_height = voxel_size * height
    stack_size = voxel_size * count
    if stack_axis == 0:
        dims = (width, count, height)
        plane = "xz"
        bbox = hou.BoundingBox(
            -0.5 * normalized_width,
            -0.5 * stack_size,
            -0.5 * image_height,
            0.5 * normalized_width,
            0.5 * stack_size,
            0.5 * image_height,
        )
    else:
        dims = (width, height, count)
        plane = "xy"
        bbox = hou.BoundingBox(
            -0.5 * normalized_width,
            -0.5 * image_height,
            -0.5 * stack_size,
            0.5 * normalized_width,
            0.5 * image_height,
            0.5 * stack_size,
        )
    return dims, plane, bbox, voxel_size


def _volume_summary(dims, width, raw_gib):
    world = tuple(float(value) / float(width) for value in dims)
    return (
        "{} x {} x {} voxels  |  World {:.3f} x {:.3f} x {:.3f}  |  "
        "{:.2f} GiB raw".format(
            dims[0], dims[1], dims[2], world[0], world[1], world[2], raw_gib
        )
    )


def _new_volume_geometry(dims, bbox, volume_name):
    geometry = hou.Geometry()
    volume = geometry.createVolume(dims[0], dims[1], dims[2], bbox)
    name_attrib = geometry.addAttrib(hou.attribType.Prim, "name", "")
    volume.setAttribValue(name_attrib, volume_name)
    return geometry, volume


def _preview_layout(full_dims, bbox, stack_axis, max_resolution):
    scale = min(1.0, float(max_resolution) / float(max(full_dims)))
    dims = tuple(max(1, int(round(v * scale))) for v in full_dims)
    if stack_axis == 0:
        plane = "xz"
        image_width, image_height, stack_count = dims[0], dims[2], dims[1]
    else:
        plane = "xy"
        image_width, image_height, stack_count = dims[0], dims[1], dims[2]
    return dims, plane, bbox, image_width, image_height, stack_count


def _restore_state(state, restore_sop_display):
    cop_parent_path = state.get("cop_parent_path")
    if cop_parent_path:
        cop_parent = hou.node(cop_parent_path)
        if cop_parent is not None:
            old = set(state["old_cop_display"])
            for child in cop_parent.children():
                child.setDisplayFlag(child.path() in old)

    if restore_sop_display:
        sop_parent = hou.node(state["sop_parent_path"])
        if sop_parent is not None:
            old = set(state["old_sop_display"])
            for child in sop_parent.children():
                child.setDisplayFlag(child.path() in old)
    hou.setFrame(state["old_frame"])


def _remove_callback(state):
    callback = state.get("callback")
    if callback is not None:
        try:
            hou.ui.removeEventLoopCallback(callback)
        except hou.OperationFailed:
            pass
        state["callback"] = None
    _active_builds().pop(state["key"], None)


def _cancel_state(state, message, restore_sop_display=False):
    node = hou.node(state["node_path"])
    _remove_callback(state)
    _restore_state(state, restore_sop_display=restore_sop_display)
    if node is not None:
        _set_status(node, message)


def _live_recordings():
    name = "_mc_texture_to_volume_cpu_live_recordings"
    recordings = getattr(hou.session, name, None)
    if recordings is None:
        recordings = {}
        setattr(hou.session, name, recordings)
    return recordings


def _live_listeners():
    name = "_mc_texture_to_volume_cpu_live_listeners"
    listeners = getattr(hou.session, name, None)
    if listeners is None:
        listeners = {}
        setattr(hou.session, name, listeners)
    return listeners


def _configuration(node):
    source = _source(node)
    frames = _sample_frames(node)
    channel_mode = int(node.evalParm("channel"))
    flip_y = bool(node.evalParm("flip_y"))
    width, height, detail = _probe(
        source, frames[0], channel_mode, flip_y
    )
    count = len(frames)
    raw_gib = width * height * count * 4.0 / (1024.0 ** 3)
    limit_gib = float(node.evalParm("memory_limit_gib"))
    if raw_gib > limit_gib:
        raise hou.NodeError(
            "Volume needs {:.2f} GiB before preview/cache overhead; "
            "Memory Limit is {:.2f} GiB.".format(raw_gib, limit_gib)
        )
    stack_axis = int(node.evalParm("stack_axis"))
    dims, plane, bbox, voxel_size = _layout(
        width, height, count, stack_axis
    )
    config_id = repr(
        (
            source["kind"],
            source["node"].path(),
            source["output_index"],
            tuple(round(value, 7) for value in frames),
            width,
            height,
            stack_axis,
            channel_mode,
            flip_y,
            node.evalParm("volume_name"),
            int(node.evalParm("preview_resolution")),
        )
    )
    return {
        "source": source,
        "frames": frames,
        "channel_mode": channel_mode,
        "flip_y": flip_y,
        "width": width,
        "height": height,
        "detail": detail,
        "count": count,
        "raw_gib": raw_gib,
        "stack_axis": stack_axis,
        "dims": dims,
        "plane": plane,
        "bbox": bbox,
        "voxel_size": voxel_size,
        "config_id": config_id,
        "voxel_text": "{} x {} x {}".format(dims[0], dims[1], dims[2]),
        "world_text": "{:.3f} x {:.3f} x {:.3f}".format(
            dims[0] / float(width),
            dims[1] / float(width),
            dims[2] / float(width),
        ),
        "memory_text": "{:.2f} GiB".format(raw_gib),
        "peak_memory_text": "about {:.2f} GiB".format(raw_gib * 2.0),
        "summary": _volume_summary(dims, width, raw_gib),
    }


def refresh_info(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    info_parms = {
        "voxel_resolution": node.parm("voxel_resolution"),
        "world_size": node.parm("world_size"),
        "raw_memory": node.parm("raw_memory"),
        "peak_memory": node.parm("peak_memory"),
    }
    try:
        config = _configuration(node)
        for parm_name, config_name in (
            ("voxel_resolution", "voxel_text"),
            ("world_size", "world_text"),
            ("raw_memory", "memory_text"),
            ("peak_memory", "peak_memory_text"),
        ):
            parm = info_parms[parm_name]
            if parm is not None:
                parm.set(config[config_name])
        key = str(node.sessionId())
        if key not in _live_recordings() and not hou.playbar.isPlaying():
            _set_status(
                node,
                "Ready. Press Play to record {} samples into CPU memory.".format(
                    config["count"]
                ),
            )
    except Exception as exc:
        for parm in info_parms.values():
            if parm is not None:
                parm.set("Unavailable")
        if not hou.playbar.isPlaying():
            _set_status(node, "Source unavailable: {}".format(exc))


def settings_changed(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    if hou.playbar.isPlaying():
        hou.playbar.stop()
        _set_status(node, "Playback stopped because recording settings changed.")
    refresh_info({"node": node})
    _set_idle_frame_increment(node)
    _arm_current_frame(node)


def viewport_settings_changed(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    use_proxy = bool(node.evalParm("use_viewport_proxy"))
    live_updates = bool(node.evalParm("live_viewport_updates"))
    node.setOutputForViewFlag(1 if use_proxy else 0)
    state = _live_recordings().get(str(node.sessionId()))
    if state is not None:
        state["use_proxy"] = use_proxy
        state["live_viewport"] = live_updates
        state["preview_interval"] = max(
            1, int(node.evalParm("preview_update_interval"))
        )
        if live_updates:
            if use_proxy:
                _refresh_live_preview(node, state)
            node.setDisplayFlag(True)
        elif not live_updates and node.isDisplayFlagSet():
            node.setDisplayFlag(False)


def _prepare_live_recording(node, config):
    full_geo, full_volume = _new_volume_geometry(
        config["dims"], config["bbox"], node.evalParm("volume_name")
    )
    preview_max = max(16, int(node.evalParm("preview_resolution")))
    (
        preview_dims,
        preview_plane,
        preview_bbox,
        preview_width,
        preview_height,
        preview_stack_count,
    ) = _preview_layout(
        config["dims"], config["bbox"], config["stack_axis"], preview_max
    )
    preview_geo, preview_volume = _new_volume_geometry(
        preview_dims, preview_bbox, node.evalParm("volume_name")
    )

    for name, default in (
        ("mc_source", ""),
        ("mc_stack_axis", ""),
        ("mc_config_id", ""),
        ("mc_captured_indices", ""),
    ):
        full_geo.addAttrib(hou.attribType.Global, name, default)
    for name, default in (
        ("mc_sample_count", 0),
        ("mc_substeps", 1),
        ("mc_captured_count", 0),
        ("mc_recording_complete", 0),
    ):
        full_geo.addAttrib(hou.attribType.Global, name, default)
    for name in (
        "mc_voxel_size",
        "mc_record_seconds",
        "mc_value_min",
        "mc_value_max",
    ):
        full_geo.addAttrib(hou.attribType.Global, name, 0.0)
    full_geo.setGlobalAttribValue("mc_source", config["source"]["label"])
    full_geo.setGlobalAttribValue(
        "mc_stack_axis", "Y" if config["stack_axis"] == 0 else "Z"
    )
    full_geo.setGlobalAttribValue("mc_config_id", config["config_id"])
    full_geo.setGlobalAttribValue("mc_sample_count", config["count"])
    full_geo.setGlobalAttribValue("mc_substeps", int(node.evalParm("substeps")))
    full_geo.setGlobalAttribValue("mc_voxel_size", config["voxel_size"])

    state = dict(config)
    state.update(
        {
            "key": str(node.sessionId()),
            "node_path": node.path(),
            "full_geo": full_geo,
            "full_volume": full_volume,
            "preview_geo": preview_geo,
            "preview_volume": preview_volume,
            "preview_plane": preview_plane,
            "preview_stack_count": preview_stack_count,
            "preview_x": np.linspace(0, config["width"] - 1, preview_width).astype(
                np.int64
            ),
            "preview_y": np.linspace(0, config["height"] - 1, preview_height).astype(
                np.int64
            ),
            "captured": set(),
            "last_preview_index": -1,
            "last_frame": None,
            "preview_interval": max(
                1, int(node.evalParm("preview_update_interval"))
            ),
            "live_viewport": bool(node.evalParm("live_viewport_updates")),
            "use_proxy": bool(node.evalParm("use_viewport_proxy")),
            "started": time.perf_counter(),
            "value_min": float("inf"),
            "value_max": float("-inf"),
        }
    )
    _live_recordings()[state["key"]] = state
    preview_cache = node.node("viewport_preview_cache")
    if preview_cache is None:
        raise hou.NodeError("Internal Viewport Preview Cache node is missing.")
    if state["live_viewport"]:
        if state["use_proxy"]:
            preview_cache.parm("stash").set(preview_geo)
            preview_cache.cook(force=True)
        node.setOutputForViewFlag(1 if state["use_proxy"] else 0)
        node.setDisplayFlag(True)
    else:
        node.setOutputForViewFlag(1 if state["use_proxy"] else 0)
        if not state["live_viewport"] and node.isDisplayFlagSet():
            node.setDisplayFlag(False)
    return state


def _frame_index(state, frame):
    frames = state["frames"]
    if len(frames) == 1:
        return 0 if abs(frame - frames[0]) < 1e-5 else None
    step = frames[1] - frames[0]
    if step <= 0.0:
        return None
    index = int(round((frame - frames[0]) / step))
    candidates = (index, len(frames) - 1)
    tolerance = max(1e-5, abs(step) * 1e-4)
    for candidate in candidates:
        if 0 <= candidate < len(frames):
            if abs(frame - frames[candidate]) <= tolerance:
                return candidate
    return None


def _refresh_live_preview(node, state):
    preview_cache = node.node("viewport_preview_cache")
    if preview_cache is not None:
        preview_cache.parm("stash").set(state["preview_geo"])
        preview_cache.cook(force=True)
        hou.ui.triggerUpdate()


def _commit_live_recording(node, state):
    elapsed = time.perf_counter() - state["started"]
    captured = sorted(state["captured"])
    state["full_geo"].setGlobalAttribValue(
        "mc_captured_indices", ",".join(str(index) for index in captured)
    )
    state["full_geo"].setGlobalAttribValue("mc_captured_count", len(captured))
    state["full_geo"].setGlobalAttribValue("mc_recording_complete", 1)
    state["full_geo"].setGlobalAttribValue("mc_record_seconds", elapsed)
    state["full_geo"].setGlobalAttribValue("mc_value_min", state["value_min"])
    state["full_geo"].setGlobalAttribValue("mc_value_max", state["value_max"])
    full_cache = node.node("cpu_volume_cache")
    if full_cache is None:
        raise hou.NodeError("Internal CPU Volume Cache node is missing.")
    full_cache.parm("stash").set(state["full_geo"])
    full_cache.cook(force=True)
    _refresh_live_preview(node, state)
    node.setOutputForViewFlag(1 if node.evalParm("use_viewport_proxy") else 0)
    listener = _live_listeners().get(state["key"])
    if listener is not None:
        listener["completed_config_id"] = state["config_id"]
        listener["completed_frame"] = state["last_frame"]
    _live_recordings().pop(state["key"], None)
    _set_status(
        node,
        "Recorded {} | {:.2f}s | values {:.5g}..{:.5g}".format(
            state["summary"], elapsed, state["value_min"], state["value_max"]
        ),
    )


def _write_live_values(node, state, frame, index, values, width, height):
    if width != state["width"] or height != state["height"]:
        raise hou.NodeError(
            "Source resolution changed at frame {}: {}x{}, expected {}x{}.".format(
                _frame_text(frame), width, height, state["width"], state["height"]
            )
        )
    state["full_volume"].setVoxelSliceFromString(
        values.tobytes(order="C"), state["plane"], index
    )
    state["value_min"] = min(state["value_min"], float(values.min()))
    state["value_max"] = max(state["value_max"], float(values.max()))
    if state["count"] == 1:
        preview_index = 0
    else:
        preview_index = int(
            round(
                index
                * float(state["preview_stack_count"] - 1)
                / float(state["count"] - 1)
            )
        )
    preview_values = np.ascontiguousarray(
        values[np.ix_(state["preview_y"], state["preview_x"])]
    )
    state["preview_volume"].setVoxelSliceFromString(
        preview_values.tobytes(order="C"), state["preview_plane"], preview_index
    )
    state["last_preview_index"] = preview_index
    state["captured"].add(index)
    state["last_frame"] = frame
    captured_count = len(state["captured"])
    if (
        state["live_viewport"]
        and state["use_proxy"]
        and (
        captured_count == 1
        or captured_count == state["count"]
        or captured_count % state["preview_interval"] == 0
        )
    ):
        _refresh_live_preview(node, state)
    if captured_count == state["count"]:
        _commit_live_recording(node, state)
    else:
        _set_status(
            node,
            "Recording {}/{} | frame {} | {}".format(
                captured_count,
                state["count"],
                _frame_text(frame),
                state["summary"],
            ),
        )


def _capture_live_frame(node, state, frame):
    index = _frame_index(state, frame)
    if index is None or index in state["captured"]:
        state["last_frame"] = frame
        return
    source = _source(node)
    values, width, height = _capture(
        source, state["channel_mode"], state["flip_y"]
    )
    _write_live_values(node, state, frame, index, values, width, height)


def _arm_current_frame(node, frame=None):
    if not node.evalParm("record_timeline") or hou.playbar.isPlaying():
        return
    if frame is None:
        frame = float(hou.frame())
    try:
        config = _configuration(node)
        index = _frame_index(config, frame)
        if index is None:
            return
        entry = _live_listeners().get(str(node.sessionId()))
        if entry is None:
            return
        if (
            index == 0
            and node.evalParm("initialize_sim")
            and entry.get("armed_reset_config_id") != config["config_id"]
        ):
            reset = config["source"]["node"].parm("resimulate")
            if reset is not None and reset.parmTemplate().type() == hou.parmTemplateType.Button:
                reset.pressButton()
            entry["armed_reset_config_id"] = config["config_id"]
        values, width, height = _capture(
            config["source"], config["channel_mode"], config["flip_y"]
        )
        entry["armed"] = {
            "config_id": config["config_id"],
            "frame": frame,
            "index": index,
            "values": values,
            "width": width,
            "height": height,
        }
    except Exception:
        pass


def _save_playback_settings(node):
    entry = _live_listeners().get(str(node.sessionId()))
    if entry is None or entry.get("playback_settings") is not None:
        return
    entry["playback_settings"] = {
        "realtime": hou.playbar.isRealTime(),
        "skipping": hou.playbar.isRealTimeSkipping(),
    }
    hou.playbar.setRealTime(False)
    hou.playbar.setRealTimeSkipping(False)


def _restore_playback_settings(node):
    entry = _live_listeners().get(str(node.sessionId()))
    settings = entry.get("playback_settings") if entry else None
    if settings is None:
        return
    hou.playbar.setRealTime(settings["realtime"])
    hou.playbar.setRealTimeSkipping(settings["skipping"])
    entry["playback_settings"] = None


def _set_idle_frame_increment(node):
    entry = _live_listeners().get(str(node.sessionId()))
    if entry is None:
        return
    if node.evalParm("record_timeline"):
        frames = _sample_frames(node)
        increment = frames[1] - frames[0] if len(frames) > 1 else 1.0
        if abs(increment - round(increment)) > 1e-7:
            hou.playbar.setUseIntegerFrames(False)
        else:
            hou.playbar.setUseIntegerFrames(entry["original_integer_frames"])
        hou.playbar.setFrameIncrement(increment)
    else:
        original = entry.get("original_frame_increment")
        if original is not None:
            hou.playbar.setFrameIncrement(original)
        hou.playbar.setUseIntegerFrames(entry["original_integer_frames"])


def _timeline_started(node, frame):
    if not node.evalParm("record_timeline"):
        return
    _save_playback_settings(node)
    config = _configuration(node)
    key = str(node.sessionId())
    listener = _live_listeners().get(key)
    completed_same = (
        listener is not None
        and listener.get("completed_config_id") == config["config_id"]
    )
    completed_frame = listener.get("completed_frame") if listener else None
    if (
        completed_same
        and completed_frame is not None
        and frame >= completed_frame - 1e-5
    ):
        return
    if _frame_index(config, frame) is None:
        return
    state = _live_recordings().get(key)
    wrapped = (
        state is not None
        and state["last_frame"] is not None
        and frame < state["last_frame"] - 1e-5
    )
    if state is None or state["config_id"] != config["config_id"] or wrapped:
        if listener is not None:
            listener["completed_config_id"] = None
            listener["completed_frame"] = None
        state = _prepare_live_recording(node, config)
        armed = listener.get("armed") if listener else None
        if (
            armed is not None
            and armed["config_id"] == config["config_id"]
            and armed["index"] not in state["captured"]
        ):
            _write_live_values(
                node,
                state,
                armed["frame"],
                armed["index"],
                armed["values"],
                armed["width"],
                armed["height"],
            )
        elif node.evalParm("initialize_sim"):
            reset = config["source"]["node"].parm("resimulate")
            if reset is not None and reset.parmTemplate().type() == hou.parmTemplateType.Button:
                reset.pressButton()
    if key in _live_recordings():
        _capture_live_frame(node, state, frame)


def _timeline_frame_changed(node, frame):
    if not node.evalParm("record_timeline"):
        return
    key = str(node.sessionId())
    state = _live_recordings().get(key)
    config = _configuration(node) if state is None else None
    if state is None:
        listener = _live_listeners().get(key)
        if _frame_index(config, frame) is None:
            return
        completed_same = (
            listener is not None
            and listener.get("completed_config_id") == config["config_id"]
        )
        completed_frame = listener.get("completed_frame") if listener else None
        if (
            completed_same
            and completed_frame is not None
            and frame >= completed_frame - 1e-5
        ):
            return
        if listener is not None:
            listener["completed_config_id"] = None
            listener["completed_frame"] = None
        state = _prepare_live_recording(node, config)
    elif state["last_frame"] is not None and frame < state["last_frame"] - 1e-5:
        state = _prepare_live_recording(node, _configuration(node))
    _capture_live_frame(node, state, frame)


def _timeline_stopped(node, frame):
    state = _live_recordings().get(str(node.sessionId()))
    if state is not None:
        _capture_live_frame(node, state, frame)
    _restore_playback_settings(node)
    state = _live_recordings().get(str(node.sessionId()))
    if state is not None:
        if state["live_viewport"] and state["use_proxy"]:
            _refresh_live_preview(node, state)
        _set_status(
            node,
            "Paused at {}/{} slices. Press Play to continue | {}".format(
                len(state["captured"]), state["count"], state["summary"]
            ),
        )


def install_live(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    key = str(node.sessionId())
    listeners = _live_listeners()
    old = listeners.pop(key, None)
    if old is not None:
        try:
            hou.playbar.removeEventCallback(old["playbar_callback"])
        except hou.OperationFailed:
            pass
        old_node = hou.node(old["node_path"])
        if old_node is not None:
            try:
                old_node.removeEventCallback(
                    old["node_events"], old["node_callback"]
                )
            except hou.OperationFailed:
                pass

    node_path = node.path()
    node.setOutputForViewFlag(1 if node.evalParm("use_viewport_proxy") else 0)
    node_events = (
        hou.nodeEventType.InputRewired,
        hou.nodeEventType.BeingDeleted,
    )

    def playbar_callback(event_type, frame):
        active_node = hou.node(node_path)
        if active_node is None:
            return
        try:
            if event_type == hou.playbarEvent.Started:
                _live_listeners()[key]["recording_active"] = True
                _timeline_started(active_node, float(hou.frame()))
            elif event_type == hou.playbarEvent.FrameChanged:
                entry = _live_listeners().get(key)
                if entry is not None and entry.get("recording_active"):
                    _timeline_frame_changed(active_node, float(hou.frame()))
                else:
                    _arm_current_frame(active_node, float(hou.frame()))
            elif event_type == hou.playbarEvent.Stopped:
                _timeline_stopped(active_node, float(hou.frame()))
                entry = _live_listeners().get(key)
                if entry is not None:
                    entry["recording_active"] = False
            elif event_type in (
                hou.playbarEvent.GlobalFrameRangeChanged,
                hou.playbarEvent.PlaybackFrameRangeChanged,
            ):
                refresh_info({"node": active_node})
        except Exception as exc:
            _restore_playback_settings(active_node)
            _set_status(active_node, "Timeline recording failed: {}".format(exc))
            if hou.playbar.isPlaying():
                hou.playbar.stop()

    def node_callback(changed_node, event_type, **event_kwargs):
        if event_type == hou.nodeEventType.BeingDeleted:
            entry = _live_listeners().pop(key, None)
            if entry is not None:
                original = entry.get("original_frame_increment")
                if original is not None:
                    hou.playbar.setFrameIncrement(original)
                hou.playbar.setUseIntegerFrames(entry["original_integer_frames"])
                try:
                    hou.playbar.removeEventCallback(entry["playbar_callback"])
                except hou.OperationFailed:
                    pass
            _live_recordings().pop(key, None)
        elif event_type == hou.nodeEventType.InputRewired:
            refresh_info({"node": changed_node})

    node.addEventCallback(node_events, node_callback)
    hou.playbar.addEventCallback(playbar_callback)
    listeners[key] = {
        "node_path": node_path,
        "playbar_callback": playbar_callback,
        "node_callback": node_callback,
        "node_events": node_events,
        "playback_settings": None,
        "original_frame_increment": hou.playbar.frameIncrement(),
        "original_integer_frames": hou.playbar.usesIntegerFrames(),
        "completed_config_id": None,
        "completed_frame": None,
        "armed": None,
        "armed_reset_config_id": None,
        "recording_active": False,
    }
    refresh_info({"node": node})
    _set_idle_frame_increment(node)
    _arm_current_frame(node)


def inspect_source(kwargs):
    node = kwargs["node"]
    try:
        source = _source(node)
        frames = _sample_frames(node)
        width, height, detail = _probe(
            source,
            frames[0],
            int(node.evalParm("channel")),
            bool(node.evalParm("flip_y")),
        )
        raw_gib = width * height * len(frames) * 4.0 / (1024.0 ** 3)
        axis = "Y Up" if int(node.evalParm("stack_axis")) == 0 else "Z Forward"
        _set_status(
            node,
            "{} | {}x{} x {} samples | {} | {:.2f} GiB | {}".format(
                source["label"], width, height, len(frames), detail, raw_gib, axis
            ),
        )
    except Exception as exc:
        _set_status(node, "Inspect failed: {}".format(exc))
        raise


def build(kwargs):
    node = kwargs["node"]
    key = str(node.sessionId())
    previous = _active_builds().get(key)
    if previous is not None:
        _cancel_state(previous, "Previous build cancelled.")

    _set_status(node, "Preparing volume build...")
    try:
        source = _source(node)
        frames = _sample_frames(node)
        channel_mode = int(node.evalParm("channel"))
        flip_y = bool(node.evalParm("flip_y"))
        width, height, detail = _probe(
            source, frames[0], channel_mode, flip_y
        )
        count = len(frames)
        raw_gib = width * height * count * 4.0 / (1024.0 ** 3)
        limit_gib = float(node.evalParm("memory_limit_gib"))
        if raw_gib > limit_gib:
            raise hou.NodeError(
                "Volume needs {:.2f} GiB before preview/Stash overhead; "
                "Memory Limit is {:.2f} GiB.".format(raw_gib, limit_gib)
            )

        stack_axis = int(node.evalParm("stack_axis"))
        full_dims, full_plane, bbox, voxel_size = _layout(
            width, height, count, stack_axis
        )
        full_geo, full_volume = _new_volume_geometry(
            full_dims, bbox, node.evalParm("volume_name")
        )

        preview_max = max(16, int(node.evalParm("preview_resolution")))
        (
            preview_dims,
            preview_plane,
            preview_bbox,
            preview_width,
            preview_height,
            preview_stack_count,
        ) = _preview_layout(full_dims, bbox, stack_axis, preview_max)
        preview_geo, preview_volume = _new_volume_geometry(
            preview_dims, preview_bbox, node.evalParm("volume_name")
        )
        preview_x = np.linspace(0, width - 1, preview_width).astype(np.int64)
        preview_y = np.linspace(0, height - 1, preview_height).astype(np.int64)

        for name, default in (
            ("mc_source", ""),
            ("mc_stack_axis", ""),
        ):
            full_geo.addAttrib(hou.attribType.Global, name, default)
        for name, default in (
            ("mc_sample_count", 0),
            ("mc_substeps", 1),
        ):
            full_geo.addAttrib(hou.attribType.Global, name, default)
        full_geo.addAttrib(hou.attribType.Global, "mc_voxel_size", 0.0)
        full_geo.setGlobalAttribValue("mc_source", source["label"])
        full_geo.setGlobalAttribValue(
            "mc_stack_axis", "Y" if stack_axis == 0 else "Z"
        )
        full_geo.setGlobalAttribValue("mc_sample_count", count)
        full_geo.setGlobalAttribValue("mc_substeps", int(node.evalParm("substeps")))
        full_geo.setGlobalAttribValue("mc_voxel_size", voxel_size)

        sop_parent = node.parent()
        state = {
            "key": key,
            "node_path": node.path(),
            "source": source,
            "sop_parent_path": sop_parent.path(),
            "old_sop_display": [
                child.path() for child in sop_parent.children() if child.isDisplayFlagSet()
            ],
            "old_frame": hou.frame(),
            "frames": frames,
            "index": 0,
            "phase": "set_frame",
            "full_geo": full_geo,
            "full_volume": full_volume,
            "full_plane": full_plane,
            "preview_geo": preview_geo,
            "preview_volume": preview_volume,
            "preview_plane": preview_plane,
            "preview_stack_count": preview_stack_count,
            "preview_x": preview_x,
            "preview_y": preview_y,
            "last_preview_index": -1,
            "preview_interval": max(1, int(node.evalParm("preview_update_interval"))),
            "width": width,
            "height": height,
            "raw_gib": raw_gib,
            "channel_mode": channel_mode,
            "flip_y": flip_y,
            "started": time.perf_counter(),
            "value_min": float("inf"),
            "value_max": float("-inf"),
            "callback": None,
            "cop_parent_path": None,
            "old_cop_display": [],
        }

        if source["kind"] == "cop":
            cop_parent = source["node"].parent()
            state["cop_parent_path"] = cop_parent.path()
            state["old_cop_display"] = [
                child.path() for child in cop_parent.children() if child.isDisplayFlagSet()
            ]
            source["node"].setDisplayFlag(True)

        node.setOutputForViewFlag(1)
        node.setDisplayFlag(True)
        preview_cache = node.node("viewport_preview_cache")
        if preview_cache is None:
            raise hou.NodeError("Internal Viewport Preview Cache node is missing.")
        preview_cache.parm("stash").set(preview_geo)
        preview_cache.cook(force=True)

        if node.evalParm("initialize_sim"):
            reset = source["node"].parm("resimulate")
            if reset is not None and reset.parmTemplate().type() == hou.parmTemplateType.Button:
                reset.pressButton()
        hou.setFrame(frames[0] - 1.0)

        def tick():
            active_node = hou.node(state["node_path"])
            source_node = hou.node(state["source"]["node"].path())
            if active_node is None or source_node is None:
                _cancel_state(
                    state,
                    "Build stopped because a required node was removed.",
                    restore_sop_display=True,
                )
                return
            state["source"]["node"] = source_node
            try:
                index = state["index"]
                frame = state["frames"][index]
                if state["phase"] == "set_frame":
                    hou.setFrame(frame)
                    state["phase"] = "capture"
                    _set_status(
                        active_node,
                        "Building frame {} | {}/{}".format(
                            _frame_text(frame), index + 1, len(state["frames"])
                        ),
                    )
                    return

                values, frame_width, frame_height = _capture(
                    state["source"], state["channel_mode"], state["flip_y"]
                )
                if frame_width != state["width"] or frame_height != state["height"]:
                    raise hou.NodeError(
                        "Source resolution changed at frame {}: {}x{}, expected {}x{}.".format(
                            _frame_text(frame),
                            frame_width,
                            frame_height,
                            state["width"],
                            state["height"],
                        )
                    )
                state["full_volume"].setVoxelSliceFromString(
                    values.tobytes(order="C"), state["full_plane"], index
                )
                state["value_min"] = min(state["value_min"], float(values.min()))
                state["value_max"] = max(state["value_max"], float(values.max()))

                if len(state["frames"]) == 1:
                    preview_index = 0
                else:
                    preview_index = int(
                        round(
                            index
                            * float(state["preview_stack_count"] - 1)
                            / float(len(state["frames"]) - 1)
                        )
                    )
                if preview_index != state["last_preview_index"]:
                    preview_values = np.ascontiguousarray(
                        values[np.ix_(state["preview_y"], state["preview_x"])]
                    )
                    state["preview_volume"].setVoxelSliceFromString(
                        preview_values.tobytes(order="C"),
                        state["preview_plane"],
                        preview_index,
                    )
                    state["last_preview_index"] = preview_index

                state["index"] += 1
                finished = state["index"] >= len(state["frames"])
                refresh = (
                    finished
                    or state["index"] == 1
                    or state["index"] % state["preview_interval"] == 0
                )
                if refresh:
                    preview_cache = active_node.node("viewport_preview_cache")
                    preview_cache.parm("stash").set(state["preview_geo"])
                    preview_cache.cook(force=True)
                    hou.ui.triggerUpdate()

                if not finished:
                    state["phase"] = "set_frame"
                    _set_status(
                        active_node,
                        "Built {}/{} slices | next frame {}".format(
                            state["index"],
                            len(state["frames"]),
                            _frame_text(state["frames"][state["index"]]),
                        ),
                    )
                    return

                elapsed = time.perf_counter() - state["started"]
                for name, default in (
                    ("mc_build_seconds", 0.0),
                    ("mc_value_min", 0.0),
                    ("mc_value_max", 0.0),
                ):
                    state["full_geo"].addAttrib(hou.attribType.Global, name, default)
                state["full_geo"].setGlobalAttribValue("mc_build_seconds", elapsed)
                state["full_geo"].setGlobalAttribValue("mc_value_min", state["value_min"])
                state["full_geo"].setGlobalAttribValue("mc_value_max", state["value_max"])
                full_cache = active_node.node("cpu_volume_cache")
                full_cache.parm("stash").set(state["full_geo"])
                full_cache.cook(force=True)
                active_node.setOutputForViewFlag(0)

                _remove_callback(state)
                _restore_state(state, restore_sop_display=False)
                axis = "Y Up" if int(active_node.evalParm("stack_axis")) == 0 else "Z Forward"
                _set_status(
                    active_node,
                    "Built {}x{}x{} | {:.2f} GiB | {:.2f}s | {} | values {:.5g}..{:.5g}".format(
                        state["full_volume"].resolution()[0],
                        state["full_volume"].resolution()[1],
                        state["full_volume"].resolution()[2],
                        state["raw_gib"],
                        elapsed,
                        axis,
                        state["value_min"],
                        state["value_max"],
                    ),
                )
            except Exception as exc:
                _cancel_state(
                    state,
                    "Build failed: {}".format(exc),
                    restore_sop_display=True,
                )
                raise

        state["callback"] = tick
        _active_builds()[key] = state
        hou.ui.addEventLoopCallback(tick)
        _set_status(
            node,
            "Build started | {} samples | {} | progressive preview every {} slices".format(
                len(frames),
                "Y Up" if stack_axis == 0 else "Z Forward",
                state["preview_interval"],
            ),
        )
    except Exception as exc:
        _set_status(node, "Build failed: {}".format(exc))
        raise


def cancel(kwargs):
    node = kwargs["node"]
    state = _active_builds().get(str(node.sessionId()))
    if state is None:
        _set_status(node, "No active build to cancel.")
        return
    _cancel_state(
        state,
        "Build cancelled at {}/{} slices; partial preview preserved.".format(
            state["index"], len(state["frames"])
        ),
        restore_sop_display=False,
    )


def clear(kwargs):
    node = kwargs["node"]
    _live_recordings().pop(str(node.sessionId()), None)
    listener = _live_listeners().get(str(node.sessionId()))
    if listener is not None:
        listener["completed_config_id"] = None
        listener["completed_frame"] = None
    state = _active_builds().get(str(node.sessionId()))
    if state is not None:
        _cancel_state(state, "Build cancelled.", restore_sop_display=False)
    for child_name in ("cpu_volume_cache", "viewport_preview_cache"):
        cache = node.node(child_name)
        if cache is not None:
            cache.parm("stash").set(hou.Geometry())
            cache.cook(force=True)
    node.setOutputForViewFlag(1 if node.evalParm("use_viewport_proxy") else 0)
    _set_status(node, "Memory cleared. Press Play to begin a new recording.")
