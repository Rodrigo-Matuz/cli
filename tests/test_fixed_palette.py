"""Regression tests for the fixed palette and wallpaper/theme separation."""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

src = Path(__file__).resolve().parents[1] / "src"
# Avoid CLI entrypoint imports while testing isolated utility modules.
caelestia = types.ModuleType("caelestia")
caelestia.__path__ = [str(src / "caelestia")]
utils = types.ModuleType("caelestia.utils")
utils.__path__ = [str(src / "caelestia/utils")]
sys.modules["caelestia"] = caelestia
sys.modules["caelestia.utils"] = utils

from caelestia.utils import paths, scheme as scheme_module


class FixedPaletteTest(unittest.TestCase):
    def test_standalone_cli_with_shell_uses_shell_fork(self):
        flake = (Path(__file__).resolve().parents[1] / "flake.nix").read_text()
        self.assertIn('url = "github:Rodrigo-Matuz/shell";', flake)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        state = Path(self.temp.name)
        self.patcher = patch.object(scheme_module, "scheme_path", state / "scheme.json")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.original_scheme = scheme_module.scheme
        scheme_module.scheme = None
        self.addCleanup(setattr, scheme_module, "scheme", self.original_scheme)

    def test_matuz_has_all_existing_roles_and_six_accents(self):
        source = paths.scheme_data_dir / "caelestia/default/dark.txt"
        target = paths.scheme_data_dir / "matuz/default/dark.txt"
        colours = scheme_module.read_colours_from_file(target)
        self.assertEqual(set(colours), set(scheme_module.read_colours_from_file(source)))
        for key, value in {
            "red": "FC1A70", "mauve": "702EF3", "blue": "1E65FF",
            "peach": "FF4D00", "yellow": "FFFF87", "green": "A4E400",
            "background": "050505", "surfaceContainerHighest": "202020",
        }.items():
            self.assertEqual(colours[key].upper(), value)
        for key in ("background", "surface", "surfaceDim", "surfaceBright", "surfaceContainerLowest", "surfaceContainerLow", "surfaceContainer", "surfaceContainerHigh", "surfaceContainerHighest", "surfaceVariant", "base", "mantle", "crust"):
            value = colours[key]
            self.assertEqual(len(value), 6)
            self.assertEqual(value[0:2], value[2:4])
            self.assertEqual(value[2:4], value[4:6])
            self.assertTrue(5 <= int(value[0:2], 16) <= 32, key)
        self.assertTrue(all(len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v) for v in colours.values()))

    def test_new_install_defaults_to_fixed_dark_scheme(self):
        current = scheme_module.Scheme(None)
        self.assertEqual((current.name, current.flavour, current.mode), ("matuz", "default", "dark"))
        self.assertEqual(current.colours["primary"], "1E65FF")

    def test_wallpaper_switch_does_not_reapply_or_change_selected_scheme(self):
        # Stub optional imaging dependencies; test actual wallpaper state transitions
        # without touching the live desktop or invoking external theme generators.
        import importlib
        with patch.dict(sys.modules, {
            "materialyoucolor": types.ModuleType("materialyoucolor"),
            "materialyoucolor.hct": types.SimpleNamespace(Hct=object),
            "materialyoucolor.utils": types.ModuleType("materialyoucolor.utils"),
            "materialyoucolor.utils.color_utils": types.SimpleNamespace(argb_from_rgb=lambda *x: 0),
            "PIL": types.ModuleType("PIL"),
            "PIL.Image": types.SimpleNamespace(open=lambda *a: None),
            "caelestia.utils.colourfulness": types.SimpleNamespace(get_variant=lambda *x: None),
            "caelestia.utils.hypr": types.SimpleNamespace(message=lambda *x: []),
            "caelestia.utils.material": types.SimpleNamespace(get_colours_for_image=lambda *x: {}),
            "caelestia.utils.theme": types.SimpleNamespace(apply_colours=lambda *x: None),
        }):
            sys.modules.pop("caelestia.utils.wallpaper", None)
            wallpaper = importlib.import_module("caelestia.utils.wallpaper")
            self.addCleanup(sys.modules.pop, "caelestia.utils.wallpaper", None)
            wall = Path(self.temp.name) / "wall.png"
            wall.write_bytes(b"a")
            state = Path(self.temp.name)
            current = scheme_module.Scheme(None)
            current.save()
            before = scheme_module.scheme_path.read_bytes()
            with patch.object(wallpaper, "wallpaper_path_path", state / "wallpaper/path.txt"), \
                 patch.object(wallpaper, "wallpaper_link_path", state / "wallpaper/current"), \
                 patch.object(wallpaper, "wallpaper_thumbnail_path", state / "wallpaper/thumbnail.jpg"), \
                 patch.object(wallpaper, "get_scheme", return_value=current), \
                 patch.object(wallpaper, "get_thumb", return_value=wall), \
                 patch.object(wallpaper, "get_config", return_value={}), \
                 patch.object(wallpaper, "get_smart_opts", side_effect=AssertionError("wallpaper must not pick a theme")), \
                 patch.object(current, "update_colours") as update:
                wallpaper.set_wallpaper(wall, False)
                self.assertEqual((state / "wallpaper/path.txt").read_text(), str(wall))
                self.assertEqual(scheme_module.scheme_path.read_bytes(), before)
                update.assert_not_called()

    def test_dynamic_selection_is_not_recomputed_by_wallpaper_switch(self):
        import importlib
        with patch.dict(sys.modules, {
            "materialyoucolor": types.ModuleType("materialyoucolor"),
            "materialyoucolor.hct": types.SimpleNamespace(Hct=object),
            "materialyoucolor.utils": types.ModuleType("materialyoucolor.utils"),
            "materialyoucolor.utils.color_utils": types.SimpleNamespace(argb_from_rgb=lambda *x: 0),
            "PIL": types.ModuleType("PIL"),
            "PIL.Image": types.SimpleNamespace(open=lambda *a: None),
            "caelestia.utils.colourfulness": types.SimpleNamespace(get_variant=lambda *x: None),
            "caelestia.utils.hypr": types.SimpleNamespace(message=lambda *x: []),
            "caelestia.utils.material": types.SimpleNamespace(get_colours_for_image=lambda *x: {}),
        }):
            sys.modules.pop("caelestia.utils.wallpaper", None)
            wallpaper = importlib.import_module("caelestia.utils.wallpaper")
            self.addCleanup(sys.modules.pop, "caelestia.utils.wallpaper", None)
            wall = Path(self.temp.name) / "wall.png"
            wall.write_bytes(b"a")
            state = Path(self.temp.name)
            current = scheme_module.Scheme({"name": "dynamic", "flavour": "default", "mode": "dark", "variant": "tonalspot", "colours": {"primary": "1E65FF"}})
            current.save()
            before = scheme_module.scheme_path.read_bytes()
            with patch.object(wallpaper, "wallpaper_path_path", state / "wallpaper/path.txt"), \
                 patch.object(wallpaper, "wallpaper_link_path", state / "wallpaper/current"), \
                 patch.object(wallpaper, "wallpaper_thumbnail_path", state / "wallpaper/thumbnail.jpg"), \
                 patch.object(wallpaper, "get_scheme", return_value=current), \
                 patch.object(wallpaper, "get_thumb", return_value=wall), \
                 patch.object(wallpaper, "get_config", return_value={}), \
                 patch.object(wallpaper, "get_smart_opts", side_effect=AssertionError("smart recolor not allowed")), \
                 patch.object(current, "update_colours", side_effect=AssertionError("theme update not allowed")):
                wallpaper.set_wallpaper(wall, False)
            self.assertEqual(scheme_module.scheme_path.read_bytes(), before)

    def test_static_scheme_preview_uses_current_colors(self):
        import importlib
        with patch.dict(sys.modules, {
            "materialyoucolor": types.ModuleType("materialyoucolor"),
            "materialyoucolor.hct": types.SimpleNamespace(Hct=object),
            "materialyoucolor.utils": types.ModuleType("materialyoucolor.utils"),
            "materialyoucolor.utils.color_utils": types.SimpleNamespace(argb_from_rgb=lambda *x: 0),
            "PIL": types.ModuleType("PIL"),
            "PIL.Image": types.SimpleNamespace(open=lambda *a: None),
            "caelestia.utils.colourfulness": types.SimpleNamespace(get_variant=lambda *x: None),
            "caelestia.utils.hypr": types.SimpleNamespace(message=lambda *x: []),
            "caelestia.utils.material": types.SimpleNamespace(get_colours_for_image=lambda *x: {}),
        }):
            sys.modules.pop("caelestia.utils.wallpaper", None)
            wallpaper = importlib.import_module("caelestia.utils.wallpaper")
            self.addCleanup(sys.modules.pop, "caelestia.utils.wallpaper", None)
            current = scheme_module.Scheme(None)
            current.name = "matuz"
            wall = Path(self.temp.name) / "wall.png"
            wall.write_bytes(b"a")
            with patch.object(wallpaper, "get_scheme", return_value=current), \
                 patch.object(wallpaper, "get_smart_opts", side_effect=AssertionError("static preview must not inspect wallpaper")), \
                 patch.object(wallpaper, "get_colours_for_image", side_effect=AssertionError("static preview must not recolor")):
                preview = wallpaper.get_colours_for_wall(wall, False)
            self.assertEqual(preview["name"], "matuz")
            self.assertEqual(preview["colours"], current.colours)


if __name__ == "__main__":
    unittest.main()
