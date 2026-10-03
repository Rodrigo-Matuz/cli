"""OBS controls use the running OBS WebSocket instance, not gpu-screen-recorder."""

import json
import logging
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from caelestia.parser import parse_args
from caelestia.subcommands.record import Command


def args(**overrides):
    values = dict(obs=True, status=False, start=False, stop=False, pause=False,
                  region=None, sound=False, clipboard=False)
    values.update(overrides)
    return Namespace(**values)


class ObsRecordingTest(unittest.TestCase):
    def test_obs_starts_idle_existing_instance(self):
        client = MagicMock()
        client.get_record_status.return_value = SimpleNamespace(
            output_active=False, output_paused=False, output_duration=0
        )
        with patch.dict(os.environ, {"OBS_WEBSOCKET_PASSWORD": "test-password"}), \
             patch("obsws_python.ReqClient", return_value=client) as connect, \
             patch.object(Command, "proc_running", side_effect=AssertionError("legacy recorder queried")):
            Command(args(start=True)).run()
        connect.assert_called_once_with(host="127.0.0.1", port=4455, password="test-password", timeout=3)
        client.start_record.assert_called_once_with()
        client.disconnect.assert_called_once_with()
    def test_obs_stop_keeps_obs_output_path_and_notifies(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "OBS capture.mkv"
            path.write_bytes(b"recorded")
            client = MagicMock()
            client.get_record_status.return_value = SimpleNamespace(
                output_active=True, output_paused=False, output_duration=3400
            )
            client.stop_record.return_value = SimpleNamespace(output_path=str(path))
            with patch.dict(os.environ, {"OBS_WEBSOCKET_PASSWORD": "test-password"}), \
                 patch("obsws_python.ReqClient", return_value=client), \
                 patch("caelestia.subcommands.record.shutil.move") as move, \
                 patch("caelestia.subcommands.record.subprocess.Popen") as notified, \
                 redirect_stdout(StringIO()):
                Command(args(stop=True)).run()
            client.stop_record.assert_called_once_with()
            move.assert_not_called()
            self.assertTrue(path.exists())
            self.assertIn(str(path), notified.call_args.args[0])
    def test_obs_stop_reports_saved_path_even_if_notification_fails(self):
        client = MagicMock()
        client.get_record_status.return_value = SimpleNamespace(
            output_active=True, output_paused=False, output_duration=2500
        )
        client.stop_record.return_value = SimpleNamespace(output_path="/home/matuz/Videos/OBS capture.mov")
        output = StringIO()
        with patch("obsws_python.ReqClient", return_value=client), \
             patch.object(Command, "notify_stopped", side_effect=OSError("notify unavailable")), \
             redirect_stdout(output):
            Command(args(stop=True)).run()
        self.assertEqual("/home/matuz/Videos/OBS capture.mov", output.getvalue().strip())
        client.stop_record.assert_called_once_with()

    def test_successful_obs_stop_is_not_reported_failed_when_disconnect_raises(self):
        client = MagicMock()
        client.get_record_status.return_value = SimpleNamespace(
            output_active=True, output_paused=False, output_duration=2500
        )
        client.stop_record.return_value = SimpleNamespace(output_path="/home/matuz/Videos/Capture.mov")
        client.disconnect.side_effect = ConnectionError("socket already closed")
        output = StringIO()
        with patch("obsws_python.ReqClient", return_value=client), \
             patch.object(Command, "notify_stopped"), redirect_stdout(output):
            Command(args(stop=True)).run()
        self.assertEqual("/home/matuz/Videos/Capture.mov", output.getvalue().strip())
        client.disconnect.assert_called_once_with()

    def test_obs_status_reports_actual_recording_state_and_duration(self):
        client = MagicMock()
        client.get_record_status.return_value = SimpleNamespace(
            output_active=True, output_paused=True, output_duration=12500
        )
        output = StringIO()
        with patch("obsws_python.ReqClient", return_value=client), redirect_stdout(output):
            Command(args(status=True)).run()
        self.assertEqual({"available": True, "running": True, "paused": True, "elapsed": 12.5}, json.loads(output.getvalue()))
        client.start_record.assert_not_called()
        client.stop_record.assert_not_called()
    def test_obs_reads_password_from_own_config_without_exposing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "obs-studio/plugin_config/obs-websocket/config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"server_port": 4455, "auth_required": true, "server_password": "from-obs"}')
            client = MagicMock()
            client.get_record_status.return_value = SimpleNamespace(
                output_active=False, output_paused=False, output_duration=0
            )
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp, "OBS_WEBSOCKET_PASSWORD": ""}), \
                 patch("obsws_python.ReqClient", return_value=client) as connect, \
                 redirect_stdout(StringIO()):
                Command(args(status=True)).run()
            connect.assert_called_once_with(host="127.0.0.1", port=4455, password="from-obs", timeout=3)
    def test_obs_server_unavailable_reports_json_without_legacy_fallback(self):
        output = StringIO()
        with patch("obsws_python.ReqClient", side_effect=ConnectionRefusedError("secret-value")), \
             patch.object(Command, "proc_running", side_effect=AssertionError("legacy recorder queried")), \
             redirect_stdout(output):
            with self.assertRaises(SystemExit) as error:
                Command(args(status=True)).run()
        self.assertNotIn("secret-value", str(error.exception) + output.getvalue())
        self.assertIn("WebSocket", __import__("json").loads(output.getvalue())["error"])
    def test_record_parser_selects_obs_status_and_explicit_actions(self):
        for flag in ("--status", "--start", "--stop", "--pause"):
            with self.subTest(flag=flag), patch.object(sys, "argv", ["caelestia", "record", "--obs", flag]):
                _, parsed = parse_args()
                self.assertTrue(parsed.obs)
                self.assertTrue(getattr(parsed, flag[2:]))

    def test_obs_rejects_region_and_sound_instead_of_ignoring_them(self):
        with patch("obsws_python.ReqClient") as connect, \
             patch.object(Command, "notify_stopped", side_effect=AssertionError("unexpected recording action")):
            for invalid in (args(region="slurp"), args(sound=True)):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(SystemExit) as error:
                        Command(invalid).run()
                    self.assertIn("OBS", str(error.exception))
            connect.assert_not_called()
    def test_obs_client_logs_never_reveal_connection_password(self):
        sink = StringIO()
        logger = logging.getLogger("obsws_python.baseclient")
        handler = logging.StreamHandler(sink)
        original_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            def fail_with_logging(**kwargs):
                logging.getLogger("obsws_python.baseclient.ReqClient").info(
                    "Connecting with password '%s'", kwargs["password"]
                )
                raise ConnectionRefusedError("unavailable")

            with patch.dict(os.environ, {"OBS_WEBSOCKET_PASSWORD": "sensitive-test-value"}), \
                 patch("obsws_python.ReqClient", side_effect=fail_with_logging), \
                 redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit):
                    Command(args(status=True)).run()
            self.assertNotIn("sensitive-test-value", sink.getvalue())
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)


if __name__ == "__main__":
    unittest.main()
