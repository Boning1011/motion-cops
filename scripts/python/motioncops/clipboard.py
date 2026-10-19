"""Import copied local media into Copernicus, on Houdini's UI thread.

Only handles file URLs / absolute file paths. All other clipboard contents
(especially Houdini nodes) continue through the existing network editor hook.
No polling, global Qt event filter, external dependency, or media conversion.
"""

import math
import os
import re
from pathlib import Path


MEDIA_EXTENSIONS = frozenset((
    ".bmp", ".cin", ".dds", ".dpx", ".exr", ".gif", ".hdr", ".jpeg",
    ".jpg", ".pic", ".picnc", ".png", ".psd", ".rat", ".rgb", ".rgba",
    ".sgi", ".tga", ".tif", ".tiff", ".webp", ".yuv",
    ".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm",
))

# Houdini keeps its node clipboard separately from the OS clipboard. Remember
# a native Copy/Cut until the OS clipboard changes, so old Explorer file URLs
# cannot hijack a subsequent native node paste.
_prefer_nodes = False


def _clipboard_changed():
    global _prefer_nodes
    _prefer_nodes = False


def paths_from_mime(mime):
    """Prefer Explorer/Finder file URLs; also accept Copy as path / URI lists.

    Never interpret plain text as Python, shell commands, or remote downloads.
    QUrl handles percent encoding, Unicode and UNC shares for native file lists.
    """
    if mime is None:
        return []
    if mime.hasUrls():
        return [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
    if not mime.hasText():
        return []
    from hutil.Qt import QtCore

    paths = []
    for line in mime.text().splitlines():
        path = line.strip().strip('"')
        if path.lower().startswith("file:"):
            url = QtCore.QUrl(path)
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
        if os.path.isabs(path):
            paths.append(path)
    return paths


def classify_paths(paths):
    """Return (valid media, skipped paths, recognized file payload).

    Deduplicate each paste, preserving clipboard order. Numbered stills stay
    separate files: copying ten images always imports ten nodes, not a sequence.
    """
    valid, skipped, seen = [], [], set()
    for path in paths:
        path = os.path.normpath(path)
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        if (Path(path).suffix.lower() in MEDIA_EXTENSIONS
                and os.path.isfile(path)):
            valid.append(path.replace("\\", "/"))
        else:
            skipped.append(path)
    return valid, skipped, bool(seen)


def node_name(path):
    # Houdini node names are ASCII; the filename parameter keeps Unicode intact.
    name = re.sub(r"[^A-Za-z0-9_]+", "_", Path(path).stem).strip("_")
    return "read_" + (name or "media")


def import_files(editor, paths, position):
    """Create a readable grid of File COPs as a single undoable operation.

    Failures affect only newly created nodes. Existing nodes, connections,
    display flags and timeline settings are left alone.
    """
    import hou

    parent = editor.pwd()
    if parent is None or parent.childTypeCategory() != hou.copNodeTypeCategory():
        raise ValueError("Open a Copernicus network to paste media.")
    if not parent.isEditable():
        raise ValueError("This Copernicus network is locked.")
    created, failed = [], []
    columns = min(5, max(1, math.ceil(math.sqrt(len(paths)))))
    with hou.undos.group("MotionCOPs: Paste media"):
        for path in paths:
            node = None
            try:
                node = parent.createNode("file", node_name(path))
                # Set the explicit file source rather than inheriting user presets.
                node.parm("source").set("file")
                parm = node.parm("filename")
                if "$" in path or "`" in path:
                    # Literal filenames must not become HScript expressions.
                    parm.setExpression(repr(path), hou.exprLanguage.Python)
                else:
                    parm.set(path)
                # parm.set() doesn't run the file browser callback. Discover
                # real layers (including multi-AOV EXRs), otherwise a new File
                # COP has zero outputs despite a perfectly valid filename.
                node.parm("aovs").set(0)
                node.parm("addaovs").pressButton()
                if node.evalParm("aovs") == 0:
                    raise ValueError("The file has no readable image layers.")
                index = len(created)
                node.setPosition(hou.Vector2(
                    position[0] + (index % columns) * 3.0,
                    position[1] - (index // columns) * 2.0))
                created.append(node)
            except Exception as exc:
                if node is not None:
                    # This node belongs to this failed import only.
                    node.destroy()
                failed.append((path, str(exc)))
        if created:
            created[0].setSelected(True, clear_all_selected=True)
            for node in created[1:]:
                node.setSelected(True)
            created[-1].setCurrent(True)
    return created, failed


def handle_paste(uievent):
    """Return True only after recognizing a file paste inside Copernicus."""
    import hou
    global _prefer_nodes

    if os.environ.get("MOTIONCOPS_CLIPBOARD", "1") == "0":
        return False
    if getattr(uievent, "eventtype", "") not in (
            "keyhit", "menukeyhit", "parentkeyhit"):
        return False
    editor = uievent.editor
    if editor.type() != hou.paneTabType.NetworkEditor:
        return False
    # H22 may deliver either the resolved hotkey symbol or the physical key.
    # isKeyMatch(raw_key, symbol) alone is context dependent in the new keymap.
    rawkey = getattr(uievent, "rawkey", "") or uievent.key
    if (rawkey.lower() in ("ctrl+c", "ctrl+x", "cmd+c", "cmd+x")
            or uievent.key in ("h.copy", "h.cut")):
        _prefer_nodes = True
        return False
    if not (rawkey.lower() in ("ctrl+v", "cmd+v")
            or hou.ui.isKeyMatch(uievent.key, "h.paste")):
        return False
    if _prefer_nodes:
        return False
    parent = editor.pwd()
    if parent is None or parent.childTypeCategory() != hou.copNodeTypeCategory():
        return False
    from hutil.Qt import QtWidgets

    mime = QtWidgets.QApplication.clipboard().mimeData()
    valid, skipped, recognized = classify_paths(paths_from_mime(mime))
    if not recognized:
        return False
    # Once files are recognized, don't fall through to Houdini's node paste on
    # failure: it would generate a second, unrelated clipboard error dialog.
    try:
        mousepos = (uievent.mousepos if uievent.eventtype == "keyhit"
                    else editor.screenBounds().center())
        created, failed = import_files(editor, valid, editor.posFromScreen(mousepos))
        count = len(created)
        message = "MotionCOPs: Imported {} file{}".format(count, "" if count == 1 else "s")
        if skipped or failed:
            message += "; {} skipped, {} failed (see Python Shell)".format(
                len(skipped), len(failed))
            for path in skipped:
                print("[MotionCOPs] Skipped missing/unsupported file: " + path)
            for path, error in failed:
                print("[MotionCOPs] Could not import {}: {}".format(path, error))
        hou.ui.setStatusMessage(message, severity=(
            hou.severityType.Warning if skipped or failed else hou.severityType.Message))
    except Exception as exc:
        hou.ui.setStatusMessage("MotionCOPs: " + str(exc), hou.severityType.Warning)
        print("[MotionCOPs] Paste failed: " + str(exc))
    return True


def install():
    """Chain the existing hook in memory; never shadow another nodegraphhooks.py.

    Idempotent across repeated startup calls / scene changes. Call on UI thread.
    """
    import hou
    if not hou.isUIAvailable():
        return
    import nodegraphhooks
    from hutil.Qt import QtWidgets

    previous = nodegraphhooks.createEventHandler
    if getattr(previous, "_motioncops_clipboard", False):
        return

    QtWidgets.QApplication.clipboard().dataChanged.connect(_clipboard_changed)

    def create_event_handler(uievent, pending_actions):
        try:
            if handle_paste(uievent):
                return None, True
        except Exception as exc:
            # An unexpected preflight error must not disable normal editing.
            print("[MotionCOPs] Clipboard hook: " + str(exc))
        return previous(uievent, pending_actions)

    create_event_handler._motioncops_clipboard = True
    nodegraphhooks.createEventHandler = create_event_handler
