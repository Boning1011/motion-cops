"""Sparse VDB timeline recorder for boning::mc_texture_to_volume_cpu::1.0."""

import math
import time

import hou
import numpy as np


def _set_status(node, message):
    parm = node.parm("status")
    if parm is not None:
        parm.set(str(message))


def _recordings():
    name = "_mc_texture_to_volume_cpu_live_recordings"
    value = getattr(hou.session, name, None)
    if value is None:
        value = {}
        setattr(hou.session, name, value)
    return value


def _listeners():
    name = "_mc_texture_to_volume_cpu_live_listeners"
    value = getattr(hou.session, name, None)
    if value is None:
        value = {}
        setattr(hou.session, name, value)
    return value


def _resolve_path(node, path):
    result = hou.node(path)
    return result if result is not None else node.node(path)


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
    raise hou.NodeError("Source must be a COP node or a SOP with a 2D Volume.")


def _source(node):
    output_index = int(node.evalParm("output_index"))
    if node.evalParm("use_external_cop"):
        path = node.evalParm("external_cop").strip()
        if not path:
            raise hou.NodeError("Set External COP, or turn off Use External COP.")
        candidate = _resolve_path(node, path)
        if candidate is None:
            raise hou.NodeError("External COP does not exist: {}".format(path))
        return _as_source(candidate, output_index, candidate.path())
    connections = node.inputConnections()
    if not connections:
        raise hou.NodeError(
            "Connect a COP Network or cached 2D Volume to input 1."
        )
    connection = connections[0]
    candidate = connection.inputNode()
    return _as_source(
        candidate,
        int(connection.outputIndex()),
        candidate.path(),
    )


def _storage_layout(layer):
    storage = layer.storageType()
    layouts = {
        hou.imageLayerStorageType.Float32: (np.float32, 1.0),
        hou.imageLayerStorageType.Float16: (np.float16, 1.0),
        hou.imageLayerStorageType.Fixed8: (np.uint8, 1.0 / 255.0),
        hou.imageLayerStorageType.Fixed16: (np.uint16, 1.0 / 65535.0),
        hou.imageLayerStorageType.Int8: (np.int8, 1.0),
        hou.imageLayerStorageType.Int16: (np.int16, 1.0),
        hou.imageLayerStorageType.Int32: (np.int32, 1.0),
    }
    if storage not in layouts:
        raise hou.NodeError("Unsupported COP storage type: {}".format(storage))
    return layouts[storage]


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
    raise hou.NodeError("Connected SOP must contain a dense 2D Volume.")


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
        raise hou.NodeError("Connected SOP Volume must be two dimensional.")
    selected = np.frombuffer(raw, dtype=np.float32).reshape(height, width)
    if flip_y:
        selected = np.ascontiguousarray(selected[::-1, :])
    elif not selected.flags.c_contiguous:
        selected = np.ascontiguousarray(selected)
    return selected, width, height


def _probe(source, frame):
    source_node = source["node"]
    output_index = source["output_index"]
    if source["kind"] == "cop":
        layer = source_node.layerAtFrame(frame, output_index)
        try:
            return tuple(int(v) for v in layer.bufferResolution())
        finally:
            layer.close()
    volume = _first_dense_volume(source_node.geometryAtFrame(frame, output_index))
    xres, yres, zres = (int(v) for v in volume.resolution())
    if zres == 1:
        return xres, yres
    if yres == 1:
        return xres, zres
    raise hou.NodeError("Connected SOP Volume must be two dimensional.")


def _capture(source, channel_mode, flip_y):
    source_node = source["node"]
    output_index = source["output_index"]
    if source["kind"] == "cop":
        layer = source_node.layer(output_index)
        try:
            return _layer_values(layer, channel_mode, flip_y)
        finally:
            layer.close()
    return _geometry_values(source_node.geometry(output_index), flip_y)


def _capture_at_frame(source, frame, channel_mode, flip_y):
    source_node = source["node"]
    output_index = source["output_index"]
    if source["kind"] == "cop":
        layer = source_node.layerAtFrame(frame, output_index)
        try:
            return _layer_values(layer, channel_mode, flip_y)
        finally:
            layer.close()
    return _geometry_values(
        source_node.geometryAtFrame(frame, output_index), flip_y
    )


def _sample_frames(node):
    start, end, increment = (float(v) for v in node.evalParmTuple("f"))
    if end < start:
        raise hou.NodeError("End frame must be greater than or equal to Start.")
    if increment <= 0.0:
        raise hou.NodeError("Frame increment must be greater than zero.")
    substeps = max(1, int(node.evalParm("substeps")))
    step = increment / float(substeps)
    count = int(math.floor((end - start) / step + 1e-7)) + 1
    frames = [start + index * step for index in range(count)]
    if frames[-1] < end - 1e-7:
        frames.append(end)
    return frames


def _frame_index(state, frame):
    frames = state["frames"]
    if len(frames) == 1:
        return 0 if abs(frame - frames[0]) < 1e-5 else None
    step = frames[1] - frames[0]
    index = int(round((frame - frames[0]) / step))
    tolerance = max(1e-5, abs(step) * 1e-4)
    if 0 <= index < len(frames) and abs(frame - frames[index]) <= tolerance:
        return index
    return None


def _target_index(state, frame):
    frames = state["frames"]
    if frame < frames[0] - 1e-5:
        return None
    if frame >= frames[-1] - 1e-5:
        return len(frames) - 1
    if len(frames) == 1:
        return 0
    step = frames[1] - frames[0]
    return max(
        0,
        min(
            len(frames) - 1,
            int(math.floor((frame - frames[0]) / step + 1e-7)),
        ),
    )


def _frame_text(frame):
    if abs(frame - round(frame)) < 1e-7:
        return str(int(round(frame)))
    return "{:.4f}".format(frame).rstrip("0").rstrip(".")


def _configuration(node):
    source = _source(node)
    frames = _sample_frames(node)
    source_width, source_height = _probe(source, frames[0])
    requested = max(16, int(node.evalParm("resolution")))
    width = min(source_width, requested)
    height = max(1, int(round(source_height * width / float(source_width))))
    count = len(frames)
    axis = int(node.evalParm("stack_axis"))
    dims = (width, count, height) if axis == 0 else (width, height, count)
    voxel_size = 1.0 / float(width)
    config_id = repr(
        (
            source["kind"],
            source["node"].path(),
            source["output_index"],
            tuple(round(value, 7) for value in frames),
            source_width,
            source_height,
            width,
            height,
            axis,
            int(node.evalParm("channel")),
            bool(node.evalParm("flip_y")),
            node.evalParm("volume_name"),
        )
    )
    return {
        "source": source,
        "frames": frames,
        "source_width": source_width,
        "source_height": source_height,
        "width": width,
        "height": height,
        "count": count,
        "axis": axis,
        "dims": dims,
        "voxel_size": voxel_size,
        "channel": int(node.evalParm("channel")),
        "flip_y": bool(node.evalParm("flip_y")),
        "volume_name": node.evalParm("volume_name"),
        "config_id": config_id,
    }


def refresh_info(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    try:
        config = _configuration(node)
        node.parm("source_resolution").set(
            "{} x {}".format(config["source_width"], config["source_height"])
        )
        node.parm("output_resolution").set(
            "{} x {} x {}".format(*config["dims"])
        )
        if str(node.sessionId()) not in _recordings() and not hou.playbar.isPlaying():
            _set_status(
                node,
                "Ready. Resolution {} is the real VDB output. Press Play from frame {}.".format(
                    config["width"], _frame_text(config["frames"][0])
                ),
            )
    except Exception as exc:
        for name in ("source_resolution", "output_resolution"):
            parm = node.parm(name)
            if parm is not None:
                parm.set("Unavailable")
        if not hou.playbar.isPlaying():
            _set_status(node, "Source unavailable: {}".format(exc))


def _clear_caches(node):
    for name in ("cpu_volume_cache", "viewport_preview_cache"):
        cache = node.node(name)
        if cache is not None:
            cache.parm("stash").set(hou.Geometry())
            cache.cook(force=True)


def _cancel_seek(entry):
    callback = entry.get("seek_callback") if entry else None
    if callback is not None:
        try:
            hou.ui.removeEventLoopCallback(callback)
        except hou.OperationFailed:
            pass
        entry["seek_callback"] = None
    if entry is not None:
        entry["seek_target_index"] = None


def _restore_playback_settings(node):
    entry = _listeners().get(str(node.sessionId()))
    settings = entry.get("playback_settings") if entry else None
    if settings is None:
        return
    hou.playbar.setRealTime(settings["realtime"])
    hou.playbar.setRealTimeSkipping(settings["skipping"])
    entry["playback_settings"] = None


def reset(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    if hou.playbar.isPlaying():
        hou.playbar.stop()
    _restore_playback_settings(node)
    _recordings().pop(str(node.sessionId()), None)
    entry = _listeners().get(str(node.sessionId()))
    if entry is not None:
        _cancel_seek(entry)
        entry["completed_config_id"] = None
        entry["completed_frame"] = None
        entry["armed"] = None
    _clear_caches(node)
    try:
        source = _source(node)
        resimulate = source["node"].parm("resimulate")
        if resimulate is not None and resimulate.parmTemplate().type() == hou.parmTemplateType.Button:
            resimulate.pressButton()
    except Exception:
        pass
    try:
        if entry is not None:
            entry["suppress_frame_trigger"] = True
        hou.setFrame(_sample_frames(node)[0])
    except Exception:
        pass
    finally:
        if entry is not None:
            entry["suppress_frame_trigger"] = False
    node.setOutputForViewFlag(0)
    refresh_info({"node": node})
    _arm_current_frame(node)


def settings_changed(kwargs):
    reset(kwargs)
    _set_idle_frame_increment(kwargs.get("node"))


def display_settings_changed(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    visualize = node.node("viewport_density_visualization")
    if visualize is not None:
        visualize.cook(force=True)


def _prepare_recording(node, config):
    _clear_caches(node)
    state = dict(config)
    state.update(
        {
            "key": str(node.sessionId()),
            "node_path": node.path(),
            "captured": set(),
            "last_frame": None,
            "started": time.perf_counter(),
            "value_min": float("inf"),
            "value_max": float("-inf"),
        }
    )
    _recordings()[state["key"]] = state
    return state


def _downsample(values, width, height):
    source_height, source_width = values.shape
    if source_width == width and source_height == height:
        return values
    x_indices = np.linspace(0, source_width - 1, width).astype(np.int64)
    y_indices = np.linspace(0, source_height - 1, height).astype(np.int64)
    return np.ascontiguousarray(values[np.ix_(y_indices, x_indices)])


def _slice_geometry(state, index, values):
    width = state["width"]
    height = state["height"]
    voxel = state["voxel_size"]
    image_height = height * voxel
    if state["axis"] == 0:
        dims = (width, 1, height)
        plane = "xz"
        bbox = hou.BoundingBox(
            -0.5,
            index * voxel,
            -0.5 * image_height,
            0.5,
            (index + 1) * voxel,
            0.5 * image_height,
        )
    else:
        dims = (width, height, 1)
        plane = "xy"
        bbox = hou.BoundingBox(
            -0.5,
            -0.5 * image_height,
            index * voxel,
            0.5,
            0.5 * image_height,
            (index + 1) * voxel,
        )
    geometry = hou.Geometry()
    volume = geometry.createVolume(dims[0], dims[1], dims[2], bbox)
    name_attrib = geometry.addAttrib(hou.attribType.Prim, "name", "")
    volume.setAttribValue(name_attrib, state["volume_name"])
    volume.setVoxelSliceFromString(values.tobytes(order="C"), plane, 0)
    return geometry


def _set_detail(geometry, name, default, value):
    if geometry.findGlobalAttrib(name) is None:
        geometry.addAttrib(hou.attribType.Global, name, default)
    geometry.setGlobalAttribValue(name, value)


def _tag_output(source_geometry, state, complete):
    geometry = hou.Geometry(source_geometry)
    captured = sorted(state["captured"])
    current_layers = max(captured) + 1 if captured else 0
    if state["axis"] == 0:
        current_dims = (state["width"], current_layers, state["height"])
    else:
        current_dims = (state["width"], state["height"], current_layers)
    _set_detail(geometry, "mc_source", "", state["source"]["label"])
    _set_detail(
        geometry,
        "mc_stack_axis",
        "",
        "Y" if state["axis"] == 0 else "Z",
    )
    _set_detail(geometry, "mc_config_id", "", state["config_id"])
    _set_detail(
        geometry,
        "mc_captured_indices",
        "",
        ",".join(str(value) for value in captured),
    )
    _set_detail(geometry, "mc_sample_count", 0, state["count"])
    _set_detail(geometry, "mc_captured_count", 0, len(captured))
    _set_detail(geometry, "mc_recording_complete", 0, int(bool(complete)))
    _set_detail(geometry, "mc_voxel_size", 0.0, state["voxel_size"])
    _set_detail(
        geometry,
        "mc_record_seconds",
        0.0,
        time.perf_counter() - state["started"],
    )
    _set_detail(geometry, "mc_value_min", 0.0, state["value_min"])
    _set_detail(geometry, "mc_value_max", 0.0, state["value_max"])
    _set_detail(
        geometry,
        "mc_current_resolution",
        "",
        "{} x {} x {}".format(*current_dims),
    )
    return geometry, current_dims


def _append_slice(node, state, frame, index, values, width, height):
    if width != state["source_width"] or height != state["source_height"]:
        raise hou.NodeError(
            "Source resolution changed at frame {}: {}x{}, expected {}x{}.".format(
                _frame_text(frame),
                width,
                height,
                state["source_width"],
                state["source_height"],
            )
        )
    values = _downsample(values, state["width"], state["height"])
    state["value_min"] = min(state["value_min"], float(values.min()))
    state["value_max"] = max(state["value_max"], float(values.max()))
    first_slice = not state["captured"]
    state["captured"].add(index)
    state["last_frame"] = frame

    slice_cache = node.node("viewport_preview_cache")
    convert = node.node("slice_to_vdb")
    combine = node.node("vdb_accumulate")
    output_cache = node.node("cpu_volume_cache")
    if any(
        value is None for value in (slice_cache, convert, combine, output_cache)
    ):
        raise hou.NodeError("Sparse VDB internal nodes are missing.")
    slice_cache.parm("stash").set(_slice_geometry(state, index, values))
    slice_cache.cook(force=True)
    convert.cook(force=True)
    if first_slice:
        result = convert.geometry()
    else:
        combine.cook(force=True)
        result = combine.geometry()
    complete = len(state["captured"]) == state["count"]
    tagged, current_dims = _tag_output(result, state, complete)
    output_cache.parm("stash").set(tagged)
    output_cache.cook(force=True)
    node.setOutputForViewFlag(0)

    active_voxels = 0
    output_geometry = output_cache.geometry()
    if output_geometry.intrinsicValue("primitivecount"):
        active_voxels = int(output_geometry.prim(0).activeVoxelCount())
    if complete:
        entry = _listeners().get(state["key"])
        if entry is not None:
            entry["completed_config_id"] = state["config_id"]
            entry["completed_frame"] = state["last_frame"]
        _recordings().pop(state["key"], None)
        _set_status(
            node,
            "Complete | {} x {} x {} | {:,} active VDB voxels".format(
                current_dims[0], current_dims[1], current_dims[2], active_voxels
            ),
        )
    else:
        _set_status(
            node,
            "Growing {}/{} | {} x {} x {} | {:,} active VDB voxels".format(
                len(state["captured"]),
                state["count"],
                current_dims[0],
                current_dims[1],
                current_dims[2],
                active_voxels,
            ),
        )


def _capture_frame(node, state, frame):
    index = _frame_index(state, frame)
    if index is None or index in state["captured"]:
        state["last_frame"] = frame
        return
    values, width, height = _capture_at_frame(
        _source(node), frame, state["channel"], state["flip_y"]
    )
    _append_slice(node, state, frame, index, values, width, height)


def _capture_index(node, state, index):
    if index in state["captured"]:
        return
    frame = state["frames"][index]
    values, width, height = _capture_at_frame(
        _source(node), frame, state["channel"], state["flip_y"]
    )
    _append_slice(node, state, frame, index, values, width, height)


def _cook_through(node, state, target_index):
    for index in range(target_index + 1):
        if state["key"] not in _recordings():
            break
        if index not in state["captured"]:
            _capture_index(node, state, index)


def _request_cook_to_frame(node, frame):
    key = str(node.sessionId())
    entry = _listeners().get(key)
    if entry is None or entry.get("seek_cooking"):
        return
    config = _configuration(node)
    target_index = _target_index(config, frame)
    if target_index is None:
        _recordings().pop(key, None)
        _clear_caches(node)
        _set_status(
            node,
            "Before simulation start frame {}.".format(
                _frame_text(config["frames"][0])
            ),
        )
        return

    state = _recordings().get(key)
    current_max = max(state["captured"]) if state and state["captured"] else -1
    completed_at_end = (
        state is None
        and entry.get("completed_config_id") == config["config_id"]
        and target_index == config["count"] - 1
    )
    if completed_at_end:
        return
    if (
        state is None
        or state["config_id"] != config["config_id"]
        or current_max > target_index
    ):
        state = _prepare_recording(node, config)
        entry["completed_config_id"] = None
        entry["completed_frame"] = None

    missing = [
        index
        for index in range(target_index + 1)
        if index not in state["captured"]
    ]
    if not missing:
        _set_status(
            node,
            "Cooked to frame {} | {}/{} slices".format(
                _frame_text(config["frames"][target_index]),
                len(state["captured"]),
                state["count"],
            ),
        )
        return

    target_text = _frame_text(config["frames"][target_index])
    entry["seek_cooking"] = True
    try:
        with hou.InterruptableOperation(
            "Cooking frames {} to {}".format(
                _frame_text(config["frames"][missing[0]]), target_text
            ),
            "MC Texture to Volume",
            open_interrupt_dialog=False,
        ) as operation:
            total = float(len(missing))
            for progress_index, index in enumerate(missing):
                current_text = _frame_text(config["frames"][index])
                fraction = progress_index / total
                operation.updateLongProgress(
                    fraction,
                    "Cooking frame {} / {}".format(current_text, target_text),
                )
                operation.updateProgress(fraction)
                _capture_index(node, state, index)
                if key not in _recordings():
                    break
            operation.updateProgress(1.0)
    except hou.OperationInterrupted:
        current_state = _recordings().get(key)
        captured_count = len(current_state["captured"]) if current_state else 0
        _set_status(
            node,
            "Cook interrupted at {}/{} slices.".format(
                captured_count, config["count"]
            ),
        )
    finally:
        entry["seek_cooking"] = False

    current_state = _recordings().get(key)
    if current_state is not None and all(
        index in current_state["captured"] for index in range(target_index + 1)
    ):
        _set_status(
            node,
            "Cooked to frame {} | {}/{} slices".format(
                target_text,
                len(current_state["captured"]),
                current_state["count"],
            ),
        )


def _arm_current_frame(node, frame=None):
    if node is None or hou.playbar.isPlaying():
        return
    if frame is None:
        frame = float(hou.frame())
    try:
        config = _configuration(node)
        index = _frame_index(config, frame)
        entry = _listeners().get(str(node.sessionId()))
        if index is None or entry is None:
            return
        values, width, height = _capture(
            config["source"], config["channel"], config["flip_y"]
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
    entry = _listeners().get(str(node.sessionId()))
    if entry is None or entry.get("playback_settings") is not None:
        return
    entry["playback_settings"] = {
        "realtime": hou.playbar.isRealTime(),
        "skipping": hou.playbar.isRealTimeSkipping(),
    }
    hou.playbar.setRealTime(False)
    hou.playbar.setRealTimeSkipping(False)


def _set_idle_frame_increment(node):
    if node is None:
        return
    entry = _listeners().get(str(node.sessionId()))
    if entry is None:
        return
    frames = _sample_frames(node)
    increment = frames[1] - frames[0] if len(frames) > 1 else 1.0
    hou.playbar.setUseIntegerFrames(
        False
        if abs(increment - round(increment)) > 1e-7
        else entry["original_integer_frames"]
    )
    hou.playbar.setFrameIncrement(increment)


def _timeline_started(node, frame):
    _save_playback_settings(node)
    config = _configuration(node)
    index = _frame_index(config, frame)
    if index is None:
        return
    key = str(node.sessionId())
    entry = _listeners().get(key)
    if (
        entry is not None
        and entry.get("completed_config_id") == config["config_id"]
        and entry.get("completed_frame") is not None
        and frame >= entry["completed_frame"] - 1e-5
    ):
        return
    state = _recordings().get(key)
    wrapped = (
        state is not None
        and state["last_frame"] is not None
        and frame < state["last_frame"] - 1e-5
    )
    if state is None or state["config_id"] != config["config_id"] or wrapped:
        state = _prepare_recording(node, config)
        if entry is not None:
            entry["completed_config_id"] = None
            entry["completed_frame"] = None
        armed = entry.get("armed") if entry else None
        if (
            armed is not None
            and armed["config_id"] == config["config_id"]
            and armed["index"] in (index, max(0, index - 1))
        ):
            _append_slice(
                node,
                state,
                armed["frame"],
                armed["index"],
                armed["values"],
                armed["width"],
                armed["height"],
            )
    if key in _recordings():
        _capture_frame(node, state, frame)


def _timeline_frame_changed(node, frame):
    key = str(node.sessionId())
    state = _recordings().get(key)
    if state is None:
        config = _configuration(node)
        if _frame_index(config, frame) is None:
            return
        state = _prepare_recording(node, config)
    elif state["last_frame"] is not None and frame < state["last_frame"] - 1e-5:
        state = _prepare_recording(node, _configuration(node))
    _capture_frame(node, state, frame)


def _timeline_stopped(node, frame):
    state = _recordings().get(str(node.sessionId()))
    if state is not None:
        _capture_frame(node, state, frame)
    _restore_playback_settings(node)
    state = _recordings().get(str(node.sessionId()))
    if state is not None:
        _set_status(
            node,
            "Paused at {}/{} slices. Press Play to continue.".format(
                len(state["captured"]), state["count"]
            ),
        )


def install_live(kwargs):
    node = kwargs.get("node")
    if node is None:
        return
    key = str(node.sessionId())
    listeners = _listeners()
    old = listeners.pop(key, None)
    if old is not None:
        try:
            hou.playbar.removeEventCallback(old["playbar_callback"])
        except hou.OperationFailed:
            pass
        old_node = hou.node(old["node_path"])
        if old_node is not None:
            try:
                old_node.removeEventCallback(old["node_events"], old["node_callback"])
            except hou.OperationFailed:
                pass
    _recordings().pop(key, None)
    node_path = node.path()
    node_events = (hou.nodeEventType.InputRewired, hou.nodeEventType.BeingDeleted)

    def playbar_callback(event_type, frame):
        active_node = hou.node(node_path)
        if active_node is None:
            return
        try:
            if event_type == hou.playbarEvent.Started:
                _listeners()[key]["recording_active"] = True
                _timeline_started(active_node, float(hou.frame()))
            elif event_type == hou.playbarEvent.FrameChanged:
                entry = _listeners().get(key)
                if entry is not None and entry.get("suppress_frame_trigger"):
                    return
                if entry is not None and entry.get("recording_active"):
                    _timeline_frame_changed(active_node, float(hou.frame()))
                else:
                    _request_cook_to_frame(active_node, float(hou.frame()))
            elif event_type == hou.playbarEvent.Stopped:
                _timeline_stopped(active_node, float(hou.frame()))
                entry = _listeners().get(key)
                if entry is not None:
                    entry["recording_active"] = False
            elif event_type in (
                hou.playbarEvent.GlobalFrameRangeChanged,
                hou.playbarEvent.PlaybackFrameRangeChanged,
            ):
                refresh_info({"node": active_node})
        except Exception as exc:
            _restore_playback_settings(active_node)
            _set_status(active_node, "Sparse VDB recording failed: {}".format(exc))
            if hou.playbar.isPlaying():
                hou.playbar.stop()

    def node_callback(changed_node, event_type, **event_kwargs):
        if event_type == hou.nodeEventType.BeingDeleted:
            entry = _listeners().pop(key, None)
            if entry is not None:
                hou.playbar.setFrameIncrement(entry["original_frame_increment"])
                hou.playbar.setUseIntegerFrames(entry["original_integer_frames"])
                try:
                    hou.playbar.removeEventCallback(entry["playbar_callback"])
                except hou.OperationFailed:
                    pass
            _recordings().pop(key, None)
        elif event_type == hou.nodeEventType.InputRewired:
            reset({"node": changed_node})

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
        "recording_active": False,
        "seek_cooking": False,
        "suppress_frame_trigger": False,
    }
    node.setOutputForViewFlag(0)
    refresh_info({"node": node})
    _set_idle_frame_increment(node)
    _arm_current_frame(node)


def clear(kwargs):
    reset(kwargs)
