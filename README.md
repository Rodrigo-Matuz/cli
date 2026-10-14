# Caelestia CLI — Matuz personal fork

This repository is Rodrigo Matuz's personal fork of the [Caelestia CLI](https://github.com/caelestia-dots/cli), the command-line control layer for the Caelestia desktop.

It is not a general-purpose distribution. The fork follows one workstation's setup, keeps personal defaults, and may diverge from upstream without compatibility guarantees, public support, issue triage, or a release schedule.

## Relationship with the shell fork

The CLI and the companion [Caelestia Shell fork](https://github.com/Rodrigo-Matuz/shell) are developed and packaged together:

- The CLI owns commands for wallpapers, color schemes, screenshots, recording, shell IPC, installation, and updates.
- The shell owns the Quickshell UI, dashboard, lock screen, notifications, media views, and services.
- The shell's Home Manager package uses the matching CLI through its `with-cli` package output.
- The shell's optional `CaelestiaVoice` integration adds a Vesktop/Vencord voice-call view to the dashboard; the CLI does not install Vesktop or the voice plugin.

Use the [shell README](https://github.com/Rodrigo-Matuz/shell/blob/main/README.md) for shell installation and the opt-in Vesktop module. Use this README for CLI commands and CLI-specific configuration.

## What this fork adds

The original CLI functionality is retained, with these personal additions and changes:

- A fixed `matuz/default/dark` palette:
  - red `#FC1A70`
  - purple `#702EF3`
  - blue `#1E65FF`
  - orange `#FF4D00`
  - yellow `#FFFF87`
  - green `#A4E400`
- Wallpaper changes no longer regenerate or reapply the active color scheme automatically.
- Nix packaging is paired with the Matuz shell fork.
- An authenticated OBS WebSocket v5 backend for an already-running OBS Studio instance.
- OBS status, start, stop, pause/resume, returned-output-path reporting, bounded connection handling, credential-safe logging, and Fish completions.
- MP4, MKV, and WebM wallpaper selection with on-demand JPEG thumbnails and video-aware random selection.

## Install with Nix

The flake exports these packages:

- `packages.default` / `packages.caelestia-cli`: the CLI without the shell bundled as a runtime dependency.
- `packages.with-shell`: the CLI paired with the matching Caelestia Shell package.

Run the CLI directly without installing it:

```sh
nix run github:Rodrigo-Matuz/cli -- --help
```

To add it to a Home Manager profile, expose the input in the consumer flake and add the package for the current system:

```nix
inputs.caelestia-cli = {
  url = "github:Rodrigo-Matuz/cli";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

```nix
home.packages = [
  inputs.caelestia-cli.packages.${pkgs.system}.default
];
```

When the shell is installed through `inputs.caelestia-shell.homeManagerModules.default`, use that module's package instead of adding another standalone CLI package. Its default shell package is the paired `with-cli` build. Adding the standalone package as well is unnecessary and can create duplicate files in a Home Manager profile.

Validate a consumer configuration before switching it:

```sh
nix flake check --no-write-lock-file
nix build .#default --no-link --no-write-lock-file
```

## Command reference

The executable is `caelestia`. Use `caelestia COMMAND --help` for the options available in the installed revision.

### Shell control

```sh
caelestia shell                 # start the shell
caelestia shell --daemon        # start it detached
caelestia shell --restart       # restart running instances
caelestia shell --kill          # stop running instances
caelestia shell --log           # print the shell log
caelestia shell --show          # print shell IPC commands
```

Pass an IPC command after `caelestia shell` to send it to the running shell. Use `caelestia shell --show` to list the commands supported by the installed shell revision.

### Color schemes

```sh
caelestia scheme list
caelestia scheme list --names
caelestia scheme get --name
caelestia scheme set --name matuz --flavour default --mode dark
caelestia scheme set --random
```

The `matuz/default/dark` scheme is part of this fork. Wallpaper selection can calculate preview colors, but it does not change the active scheme automatically.

### Wallpapers

```sh
caelestia wallpaper                  # print the selected wallpaper
caelestia wallpaper --file /path/to/image.png
caelestia wallpaper --file /path/to/video.mp4
caelestia set wallpaper /path/to/video.mkv
caelestia wallpaper --random
caelestia wallpaper --thumbnail /path/to/video.webm
caelestia wallpaper --thumbnail-info /path/to/video.webm
caelestia wallpaper --print /path/to/video.mp4
```

`--thumbnail` prints an absolute path to a cached JPEG for an image or video without selecting it. `--thumbnail-info` prints the source and cached thumbnail as JSON. The selected source remains the original file in `~/.local/state/caelestia/wallpaper/`; the thumbnail is only a preview artifact.

Random selection includes valid videos from `~/Pictures/Live-Wallpapers` alongside `~/Pictures/Wallpapers`. Set `CAELESTIA_LIVE_WALLPAPERS_DIR` to override the video directory, or pass an explicit directory with `wallpaper --random DIR`. Video dimensions are filtered against the monitor size unless `--no-filter` is used. The Nix package supplies ffmpeg; non-Nix installations need both `ffmpeg` and `ffprobe` on `PATH`.

The live-wallpaper concept is credited to [SunnydeuS/Caelestia-Live-Wallpapers-Integration](https://github.com/SunnydeuS/Caelestia-Live-Wallpapers-Integration). This fork's CLI implementation is original and does not copy code from that repository.

### Screenshots and recording

```sh
caelestia screenshot
caelestia screenshot --region
caelestia screenshot --region --freeze

caelestia record                  # toggle the legacy gpu-screen-recorder
caelestia record --region
caelestia record --sound
caelestia record --pause
```

The normal recorder uses `gpu-screen-recorder` and stores finished recordings in the configured recordings directory. The CLI does not launch the shell or OBS automatically for the legacy path.

### OBS recording

The explicit OBS backend controls an existing authenticated OBS Studio session. It does not launch or terminate OBS:

```sh
caelestia record --obs --status
caelestia record --obs --start
caelestia record --obs --pause
caelestia record --obs --stop
```

Enable the OBS WebSocket server in **OBS → Tools → WebSocket Server Settings**. The CLI reads the localhost port and password from OBS's configuration file, or from these environment variables when set:

```sh
export OBS_WEBSOCKET_PORT=4455
export OBS_WEBSOCKET_PASSWORD='your-password'
```

The `--obs` backend uses OBS's configured scene and audio sources. Do not combine it with `--region` or `--sound`; those options belong to `gpu-screen-recorder`. The CLI suppresses the OBS client logger so the password is not written to normal command output.

### Other commands

```sh
caelestia clipboard
caelestia clipboard --delete
caelestia emoji --picker
caelestia emoji --fetch
caelestia resizer --daemon
caelestia toggle <workspace>
caelestia install
caelestia update
```

The installer and updater operate on the broader Caelestia dotfiles setup and may prompt for components or an AUR helper. Read their `--help` output before using them on a machine that is not the target workstation.

## Notes and Vesktop

Notes are a shell feature, not a CLI feature. The shell fork vendors the Notes dashboard plugin and stores its data locally; no CLI command or CLI dependency is needed. See the [shell README's Notes section](https://github.com/Rodrigo-Matuz/shell/blob/main/README.md#notes-setup).

Similarly, the shell's `CaelestiaVoice` plugin is packaged through the shell flake's opt-in `homeManagerModules.vesktop-voice` output. The CLI does not install Vesktop, write Vencord settings, or provide the voice socket. Enable that module only from the [shell README's Vesktop instructions](https://github.com/Rodrigo-Matuz/shell/blob/main/README.md#caelestiavoice-for-vesktop).

## Development and verification

The Python package is under `src/caelestia/`. Focused tests cover the fixed palette, wallpapers, and OBS backend:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
nix flake check --no-write-lock-file
nix build .#default --no-link --no-write-lock-file
```

## Original project

For authoritative upstream installation instructions, dependencies, general CLI usage, support, and upstream history, see:

https://github.com/caelestia-dots/cli
