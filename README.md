# Caelestia CLI — Matuz personal fork

This repository is a personal fork of the original Caelestia CLI project.

It is not a public project. It exists for Rodrigo Matuz's personal setup and for a small number of friends. No public support, compatibility guarantee, issue triage, release schedule, or general-purpose documentation is provided here.

For normal Caelestia CLI installation, configuration, dependency, usage, or troubleshooting questions, refer to the original project and its documentation. This fork may diverge from upstream at any time.

## Fork changes

The original CLI functionality is retained, with these personal additions and changes:

- Added the fixed `matuz/default/dark` palette with these accents:
  - red `#FC1A70`
  - purple `#702EF3`
  - blue `#1E65FF`
  - orange `#FF4D00`
  - yellow `#FFFF87`
  - green `#A4E400`
- Decoupled wallpaper changes from automatic regeneration or reapplication of the active color scheme.
- Paired the CLI's Nix integration with the personal shell fork.
- Added an explicit authenticated OBS WebSocket v5 recording backend for an already-running OBS Studio instance.
- Added OBS status, start, stop, and pause/resume commands, returned-output-path reporting, bounded connection handling, credential-safe logging, and Fish completions.
- Kept `gpu-screen-recorder` as the default legacy recorder. OBS is used only with the explicit `--obs` option.
- Added regression tests and documentation for the OBS backend and its shell integration.

## OBS commands

The OBS backend controls an existing authenticated OBS session. It does not launch or terminate OBS and does not store credentials in this repository.

```sh
caelestia record --obs --status
caelestia record --obs --start
caelestia record --obs --pause
caelestia record --obs --stop
```

The normal `caelestia record` command continues to use the legacy `gpu-screen-recorder` backend.

## Original project

For authoritative installation instructions, configuration reference, dependencies, general CLI usage, support, and upstream history, use the original project:

https://github.com/caelestia-dots/cli
