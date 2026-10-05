import hashlib
import json
import os
import random
import subprocess
import tempfile
from argparse import Namespace
from pathlib import Path
from typing import cast

from materialyoucolor.hct import Hct
from materialyoucolor.utils.color_utils import argb_from_rgb
from PIL import Image

from caelestia.utils.colourfulness import get_variant
from caelestia.utils.hypr import message
from caelestia.utils.material import get_colours_for_image
from caelestia.utils.paths import (
    compute_hash,
    get_config,
    live_wallpapers_dir,
    wallpaper_link_path,
    wallpaper_path_path,
    wallpaper_thumbnail_path,
    wallpapers_cache_dir,
    wallpapers_dir,
)
from caelestia.utils.scheme import Scheme, get_scheme



def is_valid_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".gif"]


def is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {
        ".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".ts", ".mts", ".m2ts", ".ogv"
    }


def video_size(wall: Path) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height", "-of", "json", str(wall)],
            capture_output=True, timeout=15, check=False,
        )
        if result.returncode:
            return None
        stream = json.loads(result.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        return (width, height) if width > 0 and height > 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError, TypeError):
        return None


def cache_for_wall(wall: Path) -> Path:
    if is_video(wall):
        stat = wall.stat()
        identity = f"{wall.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode()
        return wallpapers_cache_dir / hashlib.sha256(identity).hexdigest()
    return wallpapers_cache_dir / compute_hash(wall)


def video_thumbnail(wall: Path, cache: Path) -> Path:
    thumb = cache / "thumbnail.jpg"
    if thumb.exists():
        return thumb

    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".jpg", dir=cache, delete=False) as output:
        temporary = Path(output.name)
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(wall),
             "-frames:v", "1", "-vf", "scale=128:128:force_original_aspect_ratio=decrease",
             "-q:v", "2", "-y", str(temporary)],
            capture_output=True, timeout=30, check=False,
        )
        if result.returncode or not temporary.stat().st_size:
            raise ValueError(f'"{wall}" is not a decodable video: {result.stderr.decode(errors="replace").strip()}')
        os.replace(temporary, thumb)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise ValueError(f'Cannot generate a thumbnail for "{wall}": {error}') from error
    finally:
        temporary.unlink(missing_ok=True)
    return thumb


def check_wall(wall: Path, filter_size: tuple[int, int], threshold: float, video_dimensions: tuple[int, int] | None = None) -> bool:
    if is_video(wall):
        size = video_dimensions if video_dimensions is not None else video_size(wall)
        if size is None:
            return False
        width, height = size
    else:
        with Image.open(wall) as img:
            width, height = img.size
    return width >= filter_size[0] * threshold and height >= filter_size[1] * threshold


def get_wallpaper() -> str | None:
    try:
        return wallpaper_path_path.read_text()
    except IOError:
        return None


def get_wallpapers(args: Namespace) -> list[Path]:
    directory = Path(args.random)

    directories = [directory]
    if directory == wallpapers_dir and live_wallpapers_dir != directory:
        directories.append(live_wallpapers_dir)
    dimensions: dict[Path, tuple[int, int]] = {}
    walls = []
    for folder in directories:
        if not folder.is_dir():
            continue
        for f in folder.rglob("*"):
            if is_valid_image(f):
                walls.append(f)
            elif is_video(f) and (size := video_size(f)) is not None:
                dimensions[f] = size
                walls.append(f)

    if args.no_filter:
        return walls

    monitors = cast(list[dict[str, int]], message("monitors"))
    filter_size = min(m["width"] for m in monitors), min(m["height"] for m in monitors)

    return [f for f in walls if check_wall(f, filter_size, args.threshold, dimensions.get(f))]


def get_thumb(wall: Path, cache: Path) -> Path:
    if is_video(wall):
        return video_thumbnail(wall, cache)
    thumb = cache / "thumbnail.jpg"

    if not thumb.exists():
        with Image.open(wall) as img:
            img = img.convert("RGB")
            img.thumbnail((128, 128), Image.Resampling.NEAREST)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            img.save(thumb, "JPEG")

    return thumb


def thumbnail_for_wall(wall: Path | str) -> Path:
    wall = Path(wall).resolve()
    if not (is_valid_image(wall) or is_video(wall)):
        raise ValueError(f'"{wall}" is not a valid image or video')
    return get_thumb(wall, cache_for_wall(wall))


def get_smart_opts(wall: Path, cache: Path) -> dict:
    opts_cache = cache / "smart.json"

    try:
        return json.loads(opts_cache.read_text())
    except (IOError, json.JSONDecodeError):
        pass

    opts = {}

    with Image.open(get_thumb(wall, cache)) as img:
        opts["variant"] = get_variant(img)
        img.thumbnail((1, 1), Image.Resampling.LANCZOS)

        # Cast the pixel to a tuple of 3 integers to safely unpack it
        pixel = cast(tuple[int, int, int], img.getpixel((0, 0)))
        hct = Hct.from_int(argb_from_rgb(*pixel))

        opts["mode"] = "light" if hct.tone > 60 else "dark"

    opts_cache.parent.mkdir(parents=True, exist_ok=True)
    with opts_cache.open("w") as f:
        json.dump(opts, f)

    return opts


def get_colours_for_wall(wall: Path | str, no_smart: bool) -> dict:
    wall = Path(wall)
    scheme = get_scheme()
    if scheme.name != "dynamic":
        return {
            "name": scheme.name,
            "flavour": scheme.flavour,
            "mode": scheme.mode,
            "variant": scheme.variant,
            "colours": scheme.colours,
        }

    cache = cache_for_wall(wall)

    if wall.suffix.lower() == ".gif":
        wall = convert_gif(wall)
    elif is_video(wall):
        wall = get_thumb(wall, cache)

    name = "dynamic"

    if not no_smart:
        smart_opts = get_smart_opts(wall, cache)
        scheme = Scheme(
            {
                "name": name,
                "flavour": scheme.flavour,
                "mode": smart_opts["mode"],
                "variant": smart_opts["variant"],
                "colours": scheme.colours,
            }
        )

    return {
        "name": name,
        "flavour": scheme.flavour,
        "mode": scheme.mode,
        "variant": scheme.variant,
        "colours": get_colours_for_image(get_thumb(wall, cache), scheme),
    }


def convert_gif(wall: Path) -> Path:
    cache = wallpapers_cache_dir / compute_hash(wall)
    output_path = cache / "first_frame.png"

    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(wall) as img:
            try:
                img.seek(0)
            except EOFError:
                pass

            img = img.convert("RGB")
            img.save(output_path, "PNG")

    return output_path


def replace_link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=link.parent, delete=False) as temporary:
        tmp = Path(temporary.name)
    tmp.unlink()
    try:
        tmp.symlink_to(target)
        os.replace(tmp, link)
    finally:
        tmp.unlink(missing_ok=True)


def set_wallpaper(wall: Path, no_smart: bool) -> None:
    # Make path absolute
    wall = Path(wall).resolve()

    if not (is_valid_image(wall) or is_video(wall)):
        raise ValueError(f'"{wall}" is not a valid image or video')

    # Use gif's 1st frame for thumb only
    wall_cache = convert_gif(wall) if wall.suffix.lower() == ".gif" else wall

    # Decode before changing the selected wallpaper. Failed inputs leave
    # path.txt and the two current symlinks untouched.
    cache = cache_for_wall(wall if is_video(wall) else wall_cache)
    thumb = get_thumb(wall_cache, cache)

    # Update links without ever exposing a missing thumbnail to the shell.
    replace_link(wallpaper_link_path, wall)
    replace_link(wallpaper_thumbnail_path, thumb)
    wallpaper_path_path.parent.mkdir(parents=True, exist_ok=True)
    wallpaper_path_path.write_text(str(wall))

    scheme = get_scheme()

    # Wallpaper selection only updates wallpaper state. Theme changes must be
    # explicit (`caelestia scheme set`), even when the dynamic scheme is active.

    # Run custom post-hook if configured
    cfg = get_config().get("wallpaper", {})
    if post_hook := cfg.get("postHook"):
        subprocess.run(
            post_hook,
            shell=True,
            env={
                **os.environ,
                "WALLPAPER_PATH": str(wall),
                "SCHEME_NAME": scheme.name,
                "SCHEME_FLAVOUR": scheme.flavour,
                "SCHEME_MODE": scheme.mode,
                "SCHEME_VARIANT": scheme.variant,
                "SCHEME_COLOURS": json.dumps(scheme.colours),
                "THUMBNAIL_PATH": str(thumb),
            },
            stderr=subprocess.DEVNULL,
        )


def set_random(args: Namespace) -> None:
    wallpapers = get_wallpapers(args)

    if not wallpapers:
        raise ValueError("No valid wallpapers found")

    try:
        last_wall = wallpaper_path_path.read_text()
        wallpapers.remove(Path(last_wall))

        if not wallpapers:
            raise ValueError("Only valid wallpaper is current")
    except (FileNotFoundError, ValueError):
        pass

    set_wallpaper(random.choice(wallpapers), args.no_smart)
