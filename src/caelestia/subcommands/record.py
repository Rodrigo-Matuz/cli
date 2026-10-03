import json
import logging
import os
import re
import shutil
import subprocess
import time
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from caelestia.utils import hypr
from caelestia.utils.notify import close_notification, notify
from caelestia.utils.paths import get_config, recording_notif_path, recording_path, recordings_dir

RECORDER = "gpu-screen-recorder"

# Handles the "Recording stopped" notification actions in a tiny detached shell
# process, so `caelestia record` can exit as soon as the recording is saved.
_STOPPED_NOTIF_HANDLER = r"""
path=$1
uri=$2
directory=$3

action=$(notify-send -a caelestia-cli \
    --action=watch=Watch \
    --action=open=Open \
    --action=delete=Delete \
    "Recording stopped" \
    "Recording saved in $path") || exit 0

case "$action" in
    watch)
        exec xdg-open "$path"
        ;;
    open)
        if ! dbus-send --session \
            --dest=org.freedesktop.FileManager1 \
            --type=method_call \
            /org/freedesktop/FileManager1 \
            org.freedesktop.FileManager1.ShowItems \
            "array:string:$uri" \
            "string:"; then
            exec xdg-open "$directory"
        fi
        ;;
    delete)
        rm -f -- "$path"
        ;;
esac
"""


class Command:
    args: Namespace

    def __init__(self, args: Namespace) -> None:
        self.args = args

    def run(self) -> None:
        if self.args.obs and (self.args.region or self.args.sound):
            raise SystemExit("OBS uses its configured scene/audio; --region and --sound are only supported by gpu-screen-recorder")
        if not self.args.obs and (self.args.start or self.args.stop or self.args.status):
            raise SystemExit("--start, --stop and --status require --obs")
        if self.args.obs:
            try:
                self.run_obs()
            except Exception:
                # Never echo OBS exception text: some clients include connection
                # details or the supplied password in their exceptions.
                message = "OBS WebSocket unavailable or request failed; enable it in OBS > Tools > WebSocket Server Settings and check the password"
                if self.args.status:
                    print(json.dumps({"available": False, "running": False, "paused": False, "elapsed": 0, "error": message}))
                raise SystemExit(message) from None
            return
        if self.args.pause:
            subprocess.run(["pkill", "-USR2", "-f", RECORDER], stdout=subprocess.DEVNULL)
        elif self.proc_running():
            self.stop()
        else:
            self.start()

    @staticmethod
    def obs_connection() -> tuple[int, str]:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        settings = config_home / "obs-studio/plugin_config/obs-websocket/config.json"
        try:
            config = json.loads(settings.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            config = {}
        port = int(os.environ.get("OBS_WEBSOCKET_PORT") or config.get("server_port", 4455))
        password = os.environ.get("OBS_WEBSOCKET_PASSWORD") or config.get("server_password", "")
        return port, password

    def run_obs(self) -> None:
        import obsws_python as obs

        # obsws-python logs its connection arguments, including the plaintext
        # password, at INFO. Keep its logger silent for the lifetime of this CLI.
        logging.getLogger("obsws_python.baseclient").setLevel(logging.CRITICAL + 1)
        port, password = self.obs_connection()
        client = obs.ReqClient(host="127.0.0.1", port=port, password=password, timeout=3)
        try:
            status = client.get_record_status()
            if self.args.start:
                if not status.output_active:
                    client.start_record()
            elif self.args.stop:
                if status.output_active:
                    self.stop_obs(client)
            elif self.args.status:
                print(json.dumps({"available": True, "running": status.output_active, "paused": status.output_paused,
                                  "elapsed": status.output_duration / 1000}))
            elif self.args.pause:
                if status.output_active:
                    client.toggle_record_pause()
            elif status.output_active:
                self.stop_obs(client)
            else:
                client.start_record()
        finally:
            try:
                client.disconnect()
            except Exception:
                # A failed cleanup cannot undo a completed OBS recording action.
                pass

    def stop_obs(self, client) -> None:
        output_path = Path(client.stop_record().output_path)
        print(output_path)
        try:
            self.notify_stopped(output_path)
        except OSError:
            # OBS already saved the file; a missing notification/clipboard tool
            # must not report the recording operation as failed.
            pass

    def proc_running(self) -> bool:
        return subprocess.run(["pidof", RECORDER], stdout=subprocess.DEVNULL).returncode == 0

    def intersects(self, a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]

    def start(self) -> None:
        args = ["-w"]

        monitors = hypr.message("monitors")
        if self.args.region:
            if self.args.region == "slurp":
                region = subprocess.check_output(
                    ["slurp", "-f", "%wx%h+%x+%y"],
                    text=True,
                    stdin=subprocess.DEVNULL,
                )
            else:
                region = self.args.region.strip()
            args += ["region", "-region", region]

            m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", region)
            if not m:
                raise ValueError(f"Invalid region: {region}")

            w, h, x, y = map(int, m.groups())
            r = x, y, w, h
            max_rr = 0
            for monitor in monitors:
                if self.intersects((monitor["x"], monitor["y"], monitor["width"], monitor["height"]), r):
                    rr = round(monitor["refreshRate"])
                    max_rr = max(max_rr, rr)
            args += ["-f", str(max_rr)]
        else:
            focused_monitor = next(monitor for monitor in monitors if monitor["focused"])
            if focused_monitor:
                args += [
                    focused_monitor["name"],
                    "-f",
                    str(round(focused_monitor["refreshRate"])),
                ]

        if self.args.sound:
            args += ["-a", "default_output"]

        config = get_config()
        try:
            if "record" in config and "extraArgs" in config["record"]:
                args += config["record"]["extraArgs"]
        except TypeError as e:
            raise ValueError(f"Config option 'record.extraArgs' should be an array: {e}")

        recording_path.parent.mkdir(parents=True, exist_ok=True)
        # The recorder outlives this command, so it must not inherit our stdio
        proc = subprocess.Popen(
            [RECORDER, *args, "-o", str(recording_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        notif = notify("-p", "Recording started", "Recording...")
        recording_notif_path.write_text(notif)

        try:
            if proc.wait(1) != 0:
                close_notification(notif)
                notify(
                    "Recording failed",
                    "An error occurred attempting to start recorder. "
                    f"Command `{' '.join(proc.args)}` failed with exit code {proc.returncode}",
                )
        except subprocess.TimeoutExpired:
            pass

    def stop(self) -> None:
        # Start killing recording process
        subprocess.run(["pkill", "-f", RECORDER], stdout=subprocess.DEVNULL)

        # Wait for recording to finish to avoid corrupted video file
        while self.proc_running():
            time.sleep(0.1)

        # Move to recordings folder
        new_path = recordings_dir / f"recording_{datetime.now().strftime('%Y%m%d_%H-%M-%S')}.mp4"
        recordings_dir.mkdir(exist_ok=True, parents=True)
        shutil.move(recording_path, new_path)
        self.notify_stopped(new_path, legacy=True)

    def notify_stopped(self, new_path: Path, *, legacy: bool = False) -> None:
        # Close the notification only for the legacy recorder, which created it.
        if legacy:
            try:
                close_notification(recording_notif_path.read_text())
            except IOError:
                pass

        if self.args.clipboard:
            file_uri = Path(new_path).resolve().as_uri() + "\n"
            subprocess.run(["wl-copy", "--type", "text/uri-list"], input=file_uri.encode())

        recording = new_path.resolve()

        # The action notification's lifetime is the user's interaction with it,
        # not this command's, so hand it off to a detached lightweight handler
        subprocess.Popen(
            [
                "sh",
                "-c",
                _STOPPED_NOTIF_HANDLER,
                "sh",
                str(recording),
                recording.as_uri(),
                str(recording.parent),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd="/",
        )
