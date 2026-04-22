"""LUT COP — pythonsnippet body. Applies a .cube LUT to the input layer.

Supports:
    * 3D LUTs (LUT_3D_SIZE, trilinear interp).
    * 1D LUTs (LUT_1D_SIZE, linear interp, per-channel).
    * Combined shaper + 3D LUTs (1D applied first, then 3D).
    * DOMAIN_MIN / DOMAIN_MAX and LUT_{1D,3D}_INPUT_RANGE.

Outputs:
    graded         (RGBA) — LUT-applied result.
    original_rgba  (RGBA) — input promoted to RGBA, no LUT applied.
                            Used by a downstream blend node so the user-facing
                            intensity slider doesn't re-trigger the (expensive)
                            LUT lookup on every drag.

Bindings:
    lut_path  (String)  — path to .cube file
    input_log (Integer) — 0=feed data straight to LUT (input is already in LUT's
                          expected encoding); 1=encode linear input as Cineon log
                          before lookup (use this when the LUT was authored for
                          Cineon-log input but your image is linear).
"""
import os
import numpy as np
import hou

_LUT_CACHE = {}


def _parse_cube(path):
    size_3d = None
    size_1d = None
    dmin_3d = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    dmax_3d = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    dmin_1d = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    dmax_1d = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    samples = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            head = line.split()
            tok = head[0].upper()
            if tok == "TITLE":
                continue
            if tok == "LUT_3D_SIZE":
                size_3d = int(head[1])
                continue
            if tok == "LUT_1D_SIZE":
                size_1d = int(head[1])
                continue
            if tok == "DOMAIN_MIN":
                v = np.array([float(x) for x in head[1:4]], dtype=np.float32)
                dmin_3d = v
                dmin_1d = v
                continue
            if tok == "DOMAIN_MAX":
                v = np.array([float(x) for x in head[1:4]], dtype=np.float32)
                dmax_3d = v
                dmax_1d = v
                continue
            if tok == "LUT_3D_INPUT_RANGE":
                dmin_3d = np.array([float(head[1])] * 3, dtype=np.float32)
                dmax_3d = np.array([float(head[2])] * 3, dtype=np.float32)
                continue
            if tok == "LUT_1D_INPUT_RANGE":
                dmin_1d = np.array([float(head[1])] * 3, dtype=np.float32)
                dmax_1d = np.array([float(head[2])] * 3, dtype=np.float32)
                continue
            try:
                samples.append([float(x) for x in head[:3]])
            except ValueError:
                continue

    if size_1d is None and size_3d is None:
        raise RuntimeError("Neither LUT_1D_SIZE nor LUT_3D_SIZE found in " + path)

    one_d = None
    three_d = None
    cursor = 0
    if size_1d is not None:
        if len(samples) - cursor < size_1d:
            raise RuntimeError(
                f"1D LUT data short: have {len(samples) - cursor} rows, need {size_1d}"
            )
        one_d = np.asarray(samples[cursor:cursor + size_1d], dtype=np.float32)
        cursor += size_1d
    if size_3d is not None:
        expected = size_3d ** 3
        if len(samples) - cursor < expected:
            raise RuntimeError(
                f"3D LUT data short: have {len(samples) - cursor} rows, need {expected}"
            )
        three_d = (
            np.asarray(samples[cursor:cursor + expected], dtype=np.float32)
            .reshape(size_3d, size_3d, size_3d, 3)
        )

    return {
        "one_d": one_d,
        "three_d": three_d,
        "size_3d": size_3d,
        "dmin_3d": dmin_3d,
        "dmax_3d": dmax_3d,
        "dmin_1d": dmin_1d,
        "dmax_1d": dmax_1d,
        "mtime": os.path.getmtime(path),
    }


def _get_lut(path):
    if not path or not os.path.isfile(path):
        raise RuntimeError("LUT file not found: " + repr(path))
    cached = _LUT_CACHE.get(path)
    mtime = os.path.getmtime(path)
    if cached is None or cached["mtime"] != mtime:
        cached = _parse_cube(path)
        _LUT_CACHE[path] = cached
    return cached


def _apply_1d(rgb, table, dmin, dmax):
    """rgb: (..., 3); table: (N, 3) — separate curve per channel."""
    n = table.shape[0]
    span = np.maximum(dmax - dmin, 1e-8)
    t = np.clip((rgb - dmin) / span, 0.0, 1.0) * (n - 1)
    i0 = np.floor(t).astype(np.int32)
    i1 = np.minimum(i0 + 1, n - 1)
    f = (t - i0).astype(np.float32)
    out = np.empty_like(rgb)
    for c in range(3):
        v0 = table[i0[..., c], c]
        v1 = table[i1[..., c], c]
        out[..., c] = v0 * (1 - f[..., c]) + v1 * f[..., c]
    return out


def _apply_3d(rgb, lut, dmin, dmax):
    """Trilinear interp on a (size, size, size, 3) LUT indexed [b, g, r]."""
    size = lut.shape[0]
    span = np.maximum(dmax - dmin, 1e-8)
    n = np.clip((rgb - dmin) / span, 0.0, 1.0) * (size - 1)
    i0 = np.floor(n).astype(np.int32)
    i1 = np.minimum(i0 + 1, size - 1)
    f = (n - i0).astype(np.float32)
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    r1, g1, b1 = i1[..., 0], i1[..., 1], i1[..., 2]
    fr = f[..., 0:1]
    fg = f[..., 1:2]
    fb = f[..., 2:3]
    c000 = lut[b0, g0, r0]
    c100 = lut[b0, g0, r1]
    c010 = lut[b0, g1, r0]
    c110 = lut[b0, g1, r1]
    c001 = lut[b1, g0, r0]
    c101 = lut[b1, g0, r1]
    c011 = lut[b1, g1, r0]
    c111 = lut[b1, g1, r1]
    c00 = c000 * (1 - fr) + c100 * fr
    c01 = c001 * (1 - fr) + c101 * fr
    c10 = c010 * (1 - fr) + c110 * fr
    c11 = c011 * (1 - fr) + c111 * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    return c0 * (1 - fb) + c1 * fb


def _linear_to_cineon(x):
    x = np.maximum(x, 0.0)
    cin = (np.log10(x * (1.0 - 0.0108) + 0.0108) * 0.6 / 0.002) + 685.0
    return np.clip(cin / 1023.0, 0.0, 1.0)


# -- entry --
src = kwargs["src"]
lut_path = kwargs.get("lut_path", "")
input_log = int(kwargs.get("input_log", 0))

w, h = src.bufferResolution()
in_ch = src.channelCount()
buf = src.allBufferElements()
storage = src.storageType()

# Decode storage type to a numpy dtype + a normalisation factor.
storage_name = str(storage)
if "Float16" in storage_name:
    in_dtype = np.float16
    norm_in = 1.0
elif "UNorm16" in storage_name:
    in_dtype = np.uint16
    norm_in = 1.0 / 65535.0
elif "UNorm8" in storage_name:
    in_dtype = np.uint8
    norm_in = 1.0 / 255.0
else:  # Float32 / anything unrecognised
    in_dtype = np.float32
    norm_in = 1.0

img = np.frombuffer(buf, dtype=in_dtype).reshape(h, w, in_ch).astype(np.float32)
if norm_in != 1.0:
    img = img * norm_in

# Promote whatever we got to a 3-channel RGB working buffer so the LUT can
# always be applied. Mono is replicated, UV is padded with zero blue,
# everything else takes the first three channels.
if in_ch == 1:
    rgb = np.repeat(img, 3, axis=2)
elif in_ch == 2:
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[..., 0:2] = img
else:
    rgb = img[..., :3].copy()

rgb_in = _linear_to_cineon(rgb) if input_log else rgb

lut = _get_lut(lut_path)
graded = rgb_in
if lut["one_d"] is not None:
    graded = _apply_1d(graded, lut["one_d"], lut["dmin_1d"], lut["dmax_1d"])
if lut["three_d"] is not None:
    graded = _apply_3d(graded, lut["three_d"], lut["dmin_3d"], lut["dmax_3d"])

# Always produce RGBA on both outputs so a downstream blend can mix them
# cleanly regardless of input layer type.
graded_rgba = np.empty((h, w, 4), dtype=np.float32)
graded_rgba[..., :3] = graded
graded_rgba[..., 3] = img[..., 3] if in_ch >= 4 else 1.0

original_rgba = np.empty((h, w, 4), dtype=np.float32)
original_rgba[..., :3] = rgb
original_rgba[..., 3] = img[..., 3] if in_ch >= 4 else 1.0


def _encode(arr):
    if in_dtype == np.uint8:
        return np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8).tobytes()
    if in_dtype == np.uint16:
        return np.clip(arr * 65535.0 + 0.5, 0, 65535).astype(np.uint16).tobytes()
    if in_dtype == np.float16:
        return arr.astype(np.float16).tobytes()
    return arr.astype(np.float32).tobytes()


def _make_layer(arr):
    layer = hou.ImageLayer()
    layer.setDataWindow(0, 0, w, h)
    layer.setDisplayWindow(0, 0, w, h)
    layer.setChannelCount(4)
    layer.setStorageType(storage)
    layer.setTypeInfo(src.typeInfo())
    layer.setAllBufferElements(_encode(arr))
    return layer


return {
    "graded": _make_layer(graded_rgba),
    "original_rgba": _make_layer(original_rgba),
}
