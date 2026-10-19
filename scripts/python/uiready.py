"""Enable media paste after Houdini's UI is ready (H21 / H22)."""
try:
    from motioncops.clipboard import install
    install()
except Exception as exc:
    print("[MotionCOPs] Could not enable clipboard import: " + str(exc))
