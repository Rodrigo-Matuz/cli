"""Live wallpaper contract tests using real short ffmpeg videos and JPEG outputs."""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from caelestia.parser import parse_args
from caelestia.utils import wallpaper


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
class LiveWallpaperTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state/wallpaper"
        self.cache = self.root / "cache/wallpapers"
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for name, value in (
            ("wallpaper_path_path", self.state / "path.txt"),
            ("wallpaper_link_path", self.state / "current"),
            ("wallpaper_thumbnail_path", self.state / "thumbnail.jpg"),
            ("wallpapers_cache_dir", self.cache),
        ):
            stack.enter_context(patch.object(wallpaper, name, value))
        stack.enter_context(patch.object(wallpaper, "get_config", return_value={}))
        stack.enter_context(patch.object(wallpaper, "get_scheme", return_value=Namespace(name="matuz", flavour="default", mode="dark", variant="tonalspot", colours={"primary": "FFFFFF"})))

    def video(self, name="scene.MP4", size="320x240"):
        path = self.root / name
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=red:s={size}:r=2", "-t", "1", "-c:v", "libvpx" if path.suffix.lower() == ".webm" else "mpeg4", "-y", str(path)], check=True, capture_output=True)
        return path

    def test_video_selection_retains_original_and_links_real_jpeg(self):
        video = self.video()
        wallpaper.set_wallpaper(video, False)
        self.assertEqual((self.state / "path.txt").read_text(), str(video))
        self.assertEqual(os.readlink(self.state / "current"), str(video))
        self.assertTrue((self.state / "thumbnail.jpg").is_symlink())
        with Image.open(self.state / "thumbnail.jpg") as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (128, 96))
        self.assertTrue((self.state / "thumbnail.jpg").resolve().is_relative_to(self.cache))

    def test_replacing_selected_thumbnail_never_unlinks_the_previous_one(self):
        first = self.video("first.mp4")
        second = self.video("second.webm")
        wallpaper.set_wallpaper(first, False)
        original_replace = os.replace
        replaced = []
        def inspect_replace(src, dst):
            if Path(dst) == self.state / "thumbnail.jpg":
                self.assertTrue((self.state / "thumbnail.jpg").is_symlink())
                self.assertEqual(os.readlink(self.state / "thumbnail.jpg"), str(self.cache / wallpaper.cache_for_wall(first).name / "thumbnail.jpg"))
                replaced.append(dst)
            return original_replace(src, dst)
        with patch.object(wallpaper.os, "replace", side_effect=inspect_replace):
            wallpaper.set_wallpaper(second, False)
        self.assertEqual(replaced, [self.state / "thumbnail.jpg"])

    def test_invalid_or_missing_video_does_not_change_selection(self):
        original = self.video()
        wallpaper.set_wallpaper(original, False)
        before = ((self.state / "path.txt").read_bytes(),
                  os.readlink(self.state / "current"),
                  os.readlink(self.state / "thumbnail.jpg"))
        broken = self.root / "broken.mkv"
        broken.write_bytes(b"not a video")
        for invalid in (broken, self.root / "missing.webm"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                wallpaper.set_wallpaper(invalid, False)
            after = ((self.state / "path.txt").read_bytes(),
                     os.readlink(self.state / "current"),
                     os.readlink(self.state / "thumbnail.jpg"))
            self.assertEqual(after, before)

    def test_all_video_extensions_are_accepted_case_insensitively(self):
        for name in ("clip.MP4", "clip.MkV", "clip.WEBM"):
            with self.subTest(name=name):
                video = self.video(name)
                wallpaper.set_wallpaper(video, False)
                self.assertEqual((self.state / "path.txt").read_text(), str(video))

    def test_file_option_still_selects_wallpaper(self):
        video = self.video()
        with patch.object(sys, "argv", ["caelestia", "wallpaper", "-f", str(video)]):
            _, args = parse_args()
        args.cls(args).run()
        self.assertEqual((self.state / "path.txt").read_text(), str(video))

    def test_threshold_option_is_numeric_for_video_filtering(self):
        with patch.object(sys, "argv", ["caelestia", "wallpaper", "-r", str(self.root), "-t", "0.5"]):
            _, args = parse_args()
        self.assertEqual(args.threshold, 0.5)

    def test_random_discovery_filters_video_by_dimensions_and_skips_broken_video(self):
        large = self.video("large.MKV")
        small = self.video("small.webm", "64x64")
        corrupt = self.root / "broken.mp4"
        corrupt.write_bytes(b"not video")
        args = Namespace(random=str(self.root), no_filter=False, threshold=0.8)
        with patch.object(wallpaper, "message", return_value=[{"width": 320, "height": 240}]):
            self.assertEqual(wallpaper.get_wallpapers(args), [large])
            args.no_filter = True
            self.assertEqual(set(wallpaper.get_wallpapers(args)), {large, small})

    def test_random_filters_each_video_with_one_probe(self):
        video = self.video()
        args = Namespace(random=self.root, no_filter=False, threshold=0.8)
        with patch.object(wallpaper, "video_size", wraps=wallpaper.video_size) as probe, \
             patch.object(wallpaper, "message", return_value=[{"width": 320, "height": 240}]):
            self.assertEqual(wallpaper.get_wallpapers(args), [video])
            self.assertEqual(probe.call_count, 1)

    def test_default_random_discovery_includes_separate_live_directory(self):
        image_dir = self.root / "Wallpapers"
        live_dir = self.root / "Live-Wallpapers"
        image_dir.mkdir()
        live_dir.mkdir()
        image = image_dir / "still.png"
        Image.new("RGB", (320, 240), "blue").save(image)
        video = self.video("Live-Wallpapers/live.webm")
        args = Namespace(random=image_dir, no_filter=True, threshold=0.8)
        with patch.object(wallpaper, "wallpapers_dir", image_dir, create=True), \
             patch.object(wallpaper, "live_wallpapers_dir", live_dir, create=True):
            self.assertEqual(set(wallpaper.get_wallpapers(args)), {image, video})
            image.unlink()
            image_dir.rmdir()
            self.assertEqual(wallpaper.get_wallpapers(args), [video])

    def test_dynamic_preview_uses_video_frame_without_hashing_video(self):
        video = self.video()
        dynamic = Namespace(name="dynamic", flavour="default", mode="dark", variant="tonalspot", colours={})
        seen = []
        def colours(path, scheme):
            with Image.open(path) as frame:
                seen.append((frame.format, frame.size))
            return {"primary": "FF0000"}
        with patch.object(wallpaper, "get_scheme", return_value=dynamic), \
             patch.object(wallpaper, "compute_hash", side_effect=AssertionError("video must not be read for hashing")), \
             patch.object(wallpaper, "get_colours_for_image", side_effect=colours):
            preview = wallpaper.get_colours_for_wall(video, True)
        self.assertEqual(preview["colours"], {"primary": "FF0000"})
        self.assertEqual(seen, [("JPEG", (128, 96))])

    def test_smart_dynamic_preview_reads_frame_not_original_video(self):
        video = self.video()
        dynamic = Namespace(name="dynamic", flavour="default", mode="dark", variant="tonalspot", colours={})
        with patch.object(wallpaper, "get_scheme", return_value=dynamic), \
             patch.object(wallpaper, "get_colours_for_image", return_value={"primary": "FF0000"}), \
             warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Image.Image.getdata is deprecated", DeprecationWarning)
            preview = wallpaper.get_colours_for_wall(video, False)
        self.assertEqual(preview["name"], "dynamic")
        self.assertEqual(preview["colours"], {"primary": "FF0000"})

    def test_set_wallpaper_alias_selects_original_video(self):
        video = self.video("wall.webm")
        with patch.object(sys, "argv", ["caelestia", "set", "wallpaper", str(video)]):
            _, args = parse_args()
        args.cls(args).run()
        self.assertEqual((self.state / "path.txt").read_text(), str(video))
        self.assertEqual(os.readlink(self.state / "current"), str(video))

    def test_thumbnail_info_echoes_requested_source_for_async_gallery(self):
        from caelestia.subcommands.wallpaper import Command
        video = self.video()
        with patch.object(sys, "argv", ["caelestia", "wallpaper", "--thumbnail-info", str(video)]):
            _, args = parse_args()
        output = io.StringIO()
        with redirect_stdout(output):
            Command(args).run()
        import json
        info = json.loads(output.getvalue())
        self.assertEqual(info["source"], str(video))
        with Image.open(info["thumbnail"]) as result:
            self.assertEqual(result.format, "JPEG")

    def test_thumbnail_command_prints_on_demand_jpeg_without_selecting_wallpaper(self):
        from caelestia.subcommands.wallpaper import Command
        video = self.video()
        image = self.root / "picture.png"
        Image.new("RGB", (256, 128), "blue").save(image)
        for source in (video, image):
            with self.subTest(source=source), patch.object(sys, "argv", ["caelestia", "wallpaper", "--thumbnail", str(source)]):
                _, args = parse_args()
                output = io.StringIO()
                with redirect_stdout(output):
                    Command(args).run()
                thumb = Path(output.getvalue().strip())
                self.assertTrue(thumb.is_relative_to(self.cache))
                with Image.open(thumb) as result:
                    self.assertEqual(result.format, "JPEG")
        self.assertFalse((self.state / "path.txt").exists())


if __name__ == "__main__":
    unittest.main()
