# Paste images and videos into COPs

Copy one or more image/video files in Explorer or Finder, move the mouse over a
Copernicus network editor, and press **Ctrl+V** (Cmd+V on macOS). MotionCOPs creates
one native **File COP per file**, reads its AOVs, and places the selected nodes in
a grid at the cursor. **Ctrl+Z** undoes the entire paste. Numbered images remain
separate stills; they are not silently combined into a sequence.

- Supports native file selections and quoted absolute paths (Windows **Copy as
  path**), including spaces, Unicode and file URLs.
- Skips duplicate paths within a paste, missing files, directories and unsupported
  extensions. Reports skipped/failed files in the status bar and Python Shell.
- Preserves native node Copy/Cut/Paste. After copying nodes, the native node
  clipboard takes priority until you copy something new to the system clipboard.
- Works in Copernicus networks, including COP Network SOPs and subnets. Other
  network types and text fields keep their normal paste behavior.
- Uses Houdini's own image/video reader; available formats/codecs depend on your
  Houdini installation. No extra runtime dependency or background conversion.

The feature starts automatically after installing the package and restarting
Houdini (21 / 22). To disable it, set `MOTIONCOPS_CLIPBOARD=0` before launch.
It uses the [network editor hook](https://www.sidefx.com/docs/houdini/hom/network.html)
and chains any existing `nodegraphhooks` implementation instead of replacing its
file. To run checks from the repository root:

```sh
python -m unittest discover -s tests -v
```

For the GUI integration check, run the following in Houdini's Python Shell. It
creates tiny test images, a short MP4 (requires FFmpeg with lavfi/libx264), and a
test COP network under the current `$HIP` project; it restores the system
clipboard afterward. Test media stay in `$HIP/motioncops_clipboard_validation/`.

```python
import runpy, hou
runpy.run_path(hou.getenv("MotionCOPs") + "/tests/validate_clipboard_houdini.py")["main"]()
```

[Back to MotionCOPs](../README.md)
