"""GUI integration check. Run main() inside Houdini; uses $HIP test media.

Creates an isolated COP network, tiny PNGs and a short MP4 below $HIP.
Exercises the installed network hook with real Qt clipboard MIME data. Restores
the user's clipboard at the end. The test network remains available to inspect.
"""
import os
from pathlib import Path
import subprocess
import shutil
from types import SimpleNamespace


def main():
    import hou
    from hutil.Qt import QtCore, QtGui, QtWidgets
    import nodegraphhooks
    from motioncops import clipboard

    assert getattr(nodegraphhooks.createEventHandler, "_motioncops_clipboard", False)
    installed_hook = nodegraphhooks.createEventHandler
    clipboard.install()
    assert nodegraphhooks.createEventHandler is installed_hook, "Hook installed twice"
    directory = Path(hou.getenv("HIP")) / "motioncops_clipboard_validation"
    directory.mkdir(exist_ok=True)
    paths = []
    for n in range(10):
        path = directory / ("image %02d.png" % n)
        image = QtGui.QImage(64, 64, QtGui.QImage.Format_RGBA8888)
        image.fill(QtGui.QColor.fromHsv(n * 30, 180, 220))
        assert image.save(str(path))
        paths.append(str(path))
    for name in ("\u56fe\u7247 \u6d4b\u8bd5.png", "literal $F `test`.png"):
        path = directory / name
        assert image.save(str(path))
        paths.append(str(path))
    video = directory / "test clip.mp4"
    subprocess.run([
        shutil.which("ffmpeg") or str(Path(hou.getenv("HFS")) / "bin" / "hffmpeg.exe"),
        "-y", "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=24",
        "-t", "0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True, creationflags=(
        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
    paths.append(str(video))
    parent = hou.node("/obj").createNode("copnet", "motioncops_clipboard_tests")
    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    original_pwd = editor.pwd()
    editor.setPwd(parent)
    event = SimpleNamespace(editor=editor, eventtype="keyhit", key="Ctrl+V",
                            mousepos=editor.screenBounds().center())
    qt_clipboard = QtWidgets.QApplication.clipboard()
    original = qt_clipboard.mimeData()
    saved = QtCore.QMimeData()
    for fmt in original.formats():
        saved.setData(fmt, original.data(fmt))
    results = []

    def paste(filepaths):
        before = set(parent.children())
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(p) for p in filepaths])
        qt_clipboard.setMimeData(mime)
        assert nodegraphhooks.createEventHandler(event, []) == (None, True)
        return [node for node in parent.children() if node not in before]

    try:
        for size in (1, 5, 10):
            nodes = paste(paths[:size])
            assert len(nodes) == size, (size, len(nodes))
            for node, path in zip(nodes, paths[:size]):
                assert node.parm("filename").evalAsString() == path.replace("\\", "/")
                layer = node.layer(0)
                assert tuple(layer.bufferResolution()) == (64, 64)
                assert not node.errors(), node.errors()
            results.append("{} PNGs: created and cooked".format(size))
        nodes = paste(paths[10:])
        assert len(nodes) == 3
        for node, path in zip(nodes, paths[10:]):
            assert node.parm("filename").evalAsString() == path.replace("\\", "/")
            assert tuple(node.layer(0).bufferResolution()) == (64, 64)
            assert not node.errors(), node.errors()
        video_node = nodes[-1]
        first = bytes(video_node.layerAtFrame(1, 0).allBufferElements())
        last = bytes(video_node.layerAtFrame(10, 0).allBufferElements())
        assert first != last, "Video did not advance"
        results.append("Unicode / literal dollar and backtick / MP4 playback: passed")
        nodes = paste([paths[0], paths[0], str(directory / "missing.png"), str(directory)])
        assert len(nodes) == 1
        results.append("Duplicates / missing files / directories: passed")
        corrupt = directory / "corrupt.png"
        corrupt.write_bytes(b"not a PNG")
        nodes = paste([str(corrupt), paths[0]])
        assert len(nodes) == 1, "Bad file prevented the valid file importing"
        results.append("Corrupt file cleanup / partial batch success: passed")
        text = QtCore.QMimeData()
        text.setText('\n'.join('"' + p + '"' for p in paths[:2]))
        assert clipboard.paths_from_mime(text) == paths[:2]
        text.setText(QtCore.QUrl.fromLocalFile(paths[10]).toString())
        assert clipboard.paths_from_mime(text) == [paths[10].replace("\\", "/")]
        text.setText("https://example.com/test.png\nprint('do not execute')")
        assert clipboard.paths_from_mime(text) == []
        results.append("Quoted paths / URI / remote and code rejection: passed")
        event.key = "h.copy"
        assert clipboard.handle_paste(event) is False
        parent.copyItemsToClipboard([nodes[0]])
        event.key = "Ctrl+V"
        assert clipboard.handle_paste(event) is False, "Native node paste intercepted"
        qt_clipboard.setText("ordinary text")
        assert clipboard.handle_paste(event) is False
        event.editor.setPwd(hou.node("/obj"))
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile(paths[0])])
        qt_clipboard.setMimeData(mime)
        assert clipboard.handle_paste(event) is False, "Non-COP context intercepted"
        editor.setPwd(parent)
        results.append("Native nodes / ordinary text / non-COP context: passed")
    finally:
        qt_clipboard.setMimeData(saved)
        editor.setPwd(original_pwd)
    return {"network": parent.path(), "media_directory": str(directory), "checks": results}
