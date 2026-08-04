"""PythonModule for boning::mc_texture_to_volume_cpu::1.0.

The asset streams animated Copernicus layers into one dense CPU volume.  It
intentionally keeps only one image slice alive while building so the peak
working set is the final volume plus the Stash copy and one source frame.
"""

import time

import hou
import numpy as np


def _set_status(node, message):
    parm = node.parm("status")
    if parm is not None:
        parm.set(str(message))


def _source_node(node):
    path = node.evalParm("cop_source").strip()
    if not path:
        raise hou.NodeError("Set COP Source before building.")

    source = hou.node(path)
    if source is None:
        source = node.node(path)
    if source is None:
        raise hou.NodeError("COP Source does not exist: {}".format(path))
    if not isinstance(source, hou.CopNode):
        raise hou.NodeError("COP Source must point to a Copernicus node.")
    return source


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


def _float_slice(layer, channel_mode, flip_y):
    width, height = (int(v) for v in layer.bufferResolution())
    channels = int(layer.channelCount())
    dtype, scale = _storage_layout(layer)
    raw = layer.allBufferElements()
    image = np.frombuffer(raw, dtype=dtype).reshape(height, width, channels)

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
                "Requested channel {} but source has only {} channel(s).".format(
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


def inspect_source(kwargs):
    node = kwargs["node"]
    try:
        source = _source_node(node)
        frame = int(node.evalParm("start_frame"))
        output_index = int(node.evalParm("output_index"))
        layer = source.layerAtFrame(frame, output_index)
        width, height = (int(v) for v in layer.bufferResolution())
        message = (
            "{}x{}x{} | {} channel(s) | {} | {}"
        ).format(
            width,
            height,
            len(range(
                int(node.evalParm("start_frame")),
                int(node.evalParm("end_frame")) + 1,
                int(node.evalParm("frame_step")),
            )),
            layer.channelCount(),
            layer.storageType(),
            "GPU source" if layer.onGPU() else "CPU source",
        )
        layer.close()
        raw_gib = width * height * len(range(
            int(node.evalParm("start_frame")),
            int(node.evalParm("end_frame")) + 1,
            int(node.evalParm("frame_step")),
        )) * 4.0 / (1024.0 ** 3)
        _set_status(node, "{} | dense Float32 {:.2f} GiB".format(message, raw_gib))
    except Exception as exc:
        _set_status(node, "Inspect failed: {}".format(exc))
        raise


def _active_builds():
    name = "_mc_texture_to_volume_cpu_builds"
    builds = getattr(hou.session, name, None)
    if builds is None:
        builds = {}
        setattr(hou.session, name, builds)
    return builds


def _restore_display(state, keep_sop_display=False):
    cop_parent = hou.node(state["cop_parent_path"])
    if cop_parent is not None:
        old_cop_display = set(state["old_cop_display"])
        for child in cop_parent.children():
            child.setDisplayFlag(child.path() in old_cop_display)

    if not keep_sop_display:
        sop_parent = hou.node(state["sop_parent_path"])
        if sop_parent is not None:
            old_sop_display = set(state["old_sop_display"])
            for child in sop_parent.children():
                child.setDisplayFlag(child.path() in old_sop_display)

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


def _cancel_state(state, message, keep_sop_display=False):
    node = hou.node(state["node_path"])
    _remove_callback(state)
    _restore_display(state, keep_sop_display=keep_sop_display)
    if node is not None:
        _set_status(node, message)


def build(kwargs):
    node = kwargs["node"]
    _set_status(node, "Preparing live CPU build...")
    key = str(node.sessionId())
    previous = _active_builds().get(key)
    if previous is not None:
        _cancel_state(previous, "Previous build cancelled.")

    try:
        source = _source_node(node)
        output_index = int(node.evalParm("output_index"))
        start = int(node.evalParm("start_frame"))
        end = int(node.evalParm("end_frame"))
        step = int(node.evalParm("frame_step"))
        if step < 1:
            raise hou.NodeError("Frame Step must be at least 1.")
        if end < start:
            raise hou.NodeError("End Frame must be greater than or equal to Start Frame.")
        frames = list(range(start, end + 1, step))
        zres = len(frames)

        probe = source.layerAtFrame(start, output_index)
        width, height = (int(v) for v in probe.bufferResolution())
        probe.close()
        raw_bytes = width * height * zres * 4
        raw_gib = raw_bytes / (1024.0 ** 3)
        limit_gib = float(node.evalParm("memory_limit_gib"))
        if raw_gib > limit_gib:
            raise hou.NodeError(
                "Dense volume needs {:.2f} GiB before Stash/viewport overhead; "
                "Memory Limit is {:.2f} GiB.".format(raw_gib, limit_gib)
            )

        xy_size = float(node.evalParm("xy_size"))
        if xy_size <= 0.0:
            raise hou.NodeError("XY Size must be greater than zero.")
        voxel_size = xy_size / float(width)
        z_size = voxel_size * zres
        bbox = hou.BoundingBox(
            -0.5 * xy_size,
            -0.5 * xy_size * float(height) / float(width),
            -0.5 * z_size,
            0.5 * xy_size,
            0.5 * xy_size * float(height) / float(width),
            0.5 * z_size,
        )

        geometry = hou.Geometry()
        volume = geometry.createVolume(width, height, zres, bbox)
        name_attrib = geometry.addAttrib(hou.attribType.Prim, "name", "")
        volume.setAttribValue(name_attrib, node.evalParm("volume_name"))
        geometry.addAttrib(hou.attribType.Global, "mc_source_cop", "")
        geometry.addAttrib(hou.attribType.Global, "mc_frame_start", 0)
        geometry.addAttrib(hou.attribType.Global, "mc_frame_end", 0)
        geometry.addAttrib(hou.attribType.Global, "mc_frame_step", 1)
        geometry.addAttrib(hou.attribType.Global, "mc_voxel_size", 0.0)
        geometry.setGlobalAttribValue("mc_source_cop", source.path())
        geometry.setGlobalAttribValue("mc_frame_start", start)
        geometry.setGlobalAttribValue("mc_frame_end", end)
        geometry.setGlobalAttribValue("mc_frame_step", step)
        geometry.setGlobalAttribValue("mc_voxel_size", voxel_size)

        cop_parent = source.parent()
        sop_parent = node.parent()
        state = {
            "key": key,
            "node_path": node.path(),
            "source_path": source.path(),
            "cop_parent_path": cop_parent.path(),
            "sop_parent_path": sop_parent.path(),
            "old_cop_display": [n.path() for n in cop_parent.children() if n.isDisplayFlagSet()],
            "old_sop_display": [n.path() for n in sop_parent.children() if n.isDisplayFlagSet()],
            "old_frame": hou.frame(),
            "frames": frames,
            "index": 0,
            "phase": "set_frame",
            "geometry": geometry,
            "volume": volume,
            "width": width,
            "height": height,
            "raw_gib": raw_gib,
            "output_index": output_index,
            "channel_mode": int(node.evalParm("channel")),
            "flip_y": bool(node.evalParm("flip_y")),
            "show_when_finished": bool(node.evalParm("show_when_finished")),
            "started": time.perf_counter(),
            "value_min": float("inf"),
            "value_max": float("-inf"),
            "callback": None,
        }

        source.setDisplayFlag(True)
        node.setDisplayFlag(True)
        if node.evalParm("reset_source"):
            reset = source.parm("resimulate")
            if reset is not None and reset.parmTemplate().type() == hou.parmTemplateType.Button:
                reset.pressButton()
        hou.setFrame(start - 1)

        def tick():
            active_node = hou.node(state["node_path"])
            active_source = hou.node(state["source_path"])
            if active_node is None or active_source is None:
                _cancel_state(state, "Build stopped because a required node was removed.")
                return
            try:
                zindex = state["index"]
                frame = state["frames"][zindex]
                if state["phase"] == "set_frame":
                    hou.setFrame(frame)
                    state["phase"] = "capture"
                    _set_status(
                        active_node,
                        "Simulating frame {} ({}/{})...".format(
                            frame, zindex + 1, len(state["frames"])
                        ),
                    )
                    return

                layer = active_source.layer(state["output_index"])
                try:
                    values, frame_width, frame_height = _float_slice(
                        layer, state["channel_mode"], state["flip_y"]
                    )
                    if frame_width != state["width"] or frame_height != state["height"]:
                        raise hou.NodeError(
                            "COP resolution changed at frame {}: {}x{}, expected {}x{}.".format(
                                frame,
                                frame_width,
                                frame_height,
                                state["width"],
                                state["height"],
                            )
                        )
                    state["volume"].setVoxelSliceFromString(
                        values.tobytes(order="C"), "xy", zindex
                    )
                    state["value_min"] = min(state["value_min"], float(values.min()))
                    state["value_max"] = max(state["value_max"], float(values.max()))
                finally:
                    layer.close()

                state["index"] += 1
                if state["index"] < len(state["frames"]):
                    state["phase"] = "set_frame"
                    _set_status(
                        active_node,
                        "Captured {}/{} slices to CPU RAM".format(
                            state["index"], len(state["frames"])
                        ),
                    )
                    return

                elapsed = time.perf_counter() - state["started"]
                state["geometry"].addAttrib(hou.attribType.Global, "mc_build_seconds", 0.0)
                state["geometry"].addAttrib(hou.attribType.Global, "mc_value_min", 0.0)
                state["geometry"].addAttrib(hou.attribType.Global, "mc_value_max", 0.0)
                state["geometry"].setGlobalAttribValue("mc_build_seconds", elapsed)
                state["geometry"].setGlobalAttribValue("mc_value_min", state["value_min"])
                state["geometry"].setGlobalAttribValue("mc_value_max", state["value_max"])
                cache = active_node.node("cpu_volume_cache")
                if cache is None:
                    raise hou.NodeError("Internal CPU Volume Cache node is missing.")
                cache.parm("stash").set(state["geometry"])
                cache.cook(force=True)
                _remove_callback(state)
                _restore_display(state, keep_sop_display=state["show_when_finished"])
                _set_status(
                    active_node,
                    "Built {}x{}x{} Float32 ({:.2f} GiB) in {:.2f}s | values {:.5g}..{:.5g}".format(
                        state["width"],
                        state["height"],
                        len(state["frames"]),
                        state["raw_gib"],
                        elapsed,
                        state["value_min"],
                        state["value_max"],
                    ),
                )
            except Exception as exc:
                _cancel_state(state, "Build failed: {}".format(exc))
                raise

        state["callback"] = tick
        _active_builds()[key] = state
        hou.ui.addEventLoopCallback(tick)
        _set_status(node, "Build queued; advancing simulation from frame {}.".format(start))
    except Exception as exc:
        _set_status(node, "Build failed: {}".format(exc))
        raise


def cancel(kwargs):
    node = kwargs["node"]
    state = _active_builds().get(str(node.sessionId()))
    if state is None:
        _set_status(node, "No active build to cancel.")
        return
    _cancel_state(state, "Build cancelled; previous CPU cache was preserved.")


def clear(kwargs):
    node = kwargs["node"]
    state = _active_builds().get(str(node.sessionId()))
    if state is not None:
        _cancel_state(state, "Build cancelled.")
    cache = node.node("cpu_volume_cache")
    if cache is None:
        raise hou.NodeError("Internal CPU Volume Cache node is missing.")
    cache.parm("stash").set(hou.Geometry())
    cache.cook(force=True)
    _set_status(node, "CPU volume cache cleared.")
