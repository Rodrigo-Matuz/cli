# caelestia-cli

The main control script for the Caelestia dotfiles.

<details><summary id="dependencies">External dependencies</summary>

- [`libnotify`](https://gitlab.gnome.org/GNOME/libnotify) - sending notifications
- [`swappy`](https://github.com/jtheoof/swappy) - screenshot editor
- [`grim`](https://gitlab.freedesktop.org/emersion/grim) - taking screenshots
- [`dart-sass`](https://github.com/sass/dart-sass) - discord theming
- [`wl-clipboard`](https://github.com/bugaevc/wl-clipboard) - copying to clipboard
- [`slurp`](https://github.com/emersion/slurp) - selecting an area
- [`gpu-screen-recorder`](https://git.dec05eba.com/gpu-screen-recorder/about) - screen recording
- `glib2` - closing notifications
- [`cliphist`](https://github.com/sentriz/cliphist) - clipboard history
- [`fuzzel`](https://codeberg.org/dnkl/fuzzel) - clipboard history/emoji picker

</details>

## Installation

### Arch linux

The CLI is available from the AUR as `caelestia-cli`. You can install it with an AUR helper
like [`yay`](https://github.com/Jguer/yay) or manually downloading the PKGBUILD and running `makepkg -si`.

A package following the latest commit also exists as `caelestia-cli-git`. This is bleeding edge
and likely to be unstable/have bugs. Regular users are recommended to use the stable package
(`caelestia-cli`).

### Nix

You can run the CLI directly via `nix run`:

```sh
nix run github:caelestia-dots/cli
```

Or add it to your system configuration:

```nix
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    caelestia-cli = {
      url = "github:caelestia-dots/cli";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
}
```

The package is available as `caelestia-cli.packages.<system>.default`, which can be added to your
`environment.systemPackages`, `users.users.<username>.packages`, `home.packages` if using home-manager,
or a devshell. The CLI can then be used via the `caelestia` command.

> [!TIP]
> The default package does not have the shell enabled by default, which is required for full functionality.
> To enable the shell, use the `with-shell` package. This is the recommended installation method, as
> the CLI exposes the shell via the `shell` subcommand, meaning there is no need for the shell package
> to be exposed.

For home-manager, you can also use the Caelestia's home manager module (explained in
[configuring](https://github.com/caelestia-dots/shell?tab=readme-ov-file#home-manager-module)) that
installs and configures the shell and the CLI.

### Manual installation

Install all [dependencies](#dependencies), then install
[`python-build`](https://github.com/pypa/build),
[`python-installer`](https://github.com/pypa/installer),
[`python-hatch`](https://github.com/pypa/hatch) and
[`python-hatch-vcs`](https://github.com/ofek/hatch-vcs).

e.g. via an AUR helper (yay)

```sh
yay -S libnotify swappy grim dart-sass wl-clipboard slurp gpu-screen-recorder glib2 cliphist fuzzel python-build python-installer python-hatch python-hatch-vcs
```

Now, clone the repo, `cd` into it, build the wheel via `python -m build --wheel`
and install it via `python -m installer dist/*.whl`. Then, to install the `fish`
completions, copy the `completions/caelestia.fish` file to
`/usr/share/fish/vendor_completions.d/caelestia.fish`.

```sh
git clone https://github.com/caelestia-dots/cli.git
cd cli
python -m build --wheel
sudo python -m installer dist/*.whl
sudo cp completions/caelestia.fish /usr/share/fish/vendor_completions.d/caelestia.fish
```

### Additional steps

#### Auto folder colour theming

For automatic Papirus folder icon colour syncing, you must have [`papirus-folders`](https://github.com/PapirusDevelopmentTeam/papirus-folders)
installed, and `papirus-folders` must to be able to run with `sudo` without a password prompt.

You can allow this by creating a sudoers file:

```sh
echo "$USER ALL=(ALL) NOPASSWD: $(which papirus-folders)" | sudo tee /etc/sudoers.d/papirus-folders
sudo chmod 440 /etc/sudoers.d/papirus-folders
```

#### Chromium-based browser theming

For live Chromium-based browser theming, the CLI must be allowed to create certain directories in `/etc`
and write to them via `sudo` without a password prompt.

You can allow this by creating a sudoers file:

```fish
# Fish shell
for dir in /etc/chromium/policies/managed /etc/brave/policies/managed /etc/opt/chrome/policies/managed
    echo "$USER ALL=(ALL) NOPASSWD: $(which mkdir) -p $dir" | sudo tee -a /etc/sudoers.d/caelestia-chromium
    echo "$USER ALL=(ALL) NOPASSWD: $(which tee) $dir/caelestia.json" | sudo tee -a /etc/sudoers.d/caelestia-chromium
end
sudo chmod 440 /etc/sudoers.d/caelestia-chromium
```

```sh
# Bash/other shells
for dir in /etc/chromium/policies/managed /etc/brave/policies/managed /etc/opt/chrome/policies/managed; do
    echo "$USER ALL=(ALL) NOPASSWD: $(which mkdir) -p $dir" | sudo tee -a /etc/sudoers.d/caelestia-chromium
    echo "$USER ALL=(ALL) NOPASSWD: $(which tee) $dir/caelestia.json" | sudo tee -a /etc/sudoers.d/caelestia-chromium
done
sudo chmod 440 /etc/sudoers.d/caelestia-chromium
```

## Usage

All subcommands/options can be explored via the help flag.

```
$ caelestia -h
usage: caelestia [-h] [-v] COMMAND ...

Main control script for the Caelestia dotfiles

options:
  -h, --help     show this help message and exit
  -v, --version  print the current version

subcommands:
  valid subcommands

  COMMAND        the subcommand to run
    shell        start or message the shell
    toggle       toggle a special workspace
    scheme       manage the colour scheme
    screenshot   take a screenshot
    record       start a screen recording
    clipboard    open clipboard history
    emoji        emoji/glyph utilities
    wallpaper    manage the wallpaper
    resizer      window resizer daemon
    install      install the Caelestia dotfiles
    update       update the Caelestia dotfiles
```

### User templates

Custom user templates can be defined in `~/.config/caelestia/templates/`.

#### Template syntax

`{{ <color>.<format> }}`

- `<color>` is a theme color role derived from the Material You color system (e.g. `primary`, `secondary`, `background`)
- `<format>` is the output format: `hex`, `rgb`, `hsl`, or a single channel (`red`, `green`, `blue`, `hue`, `saturation`, `lightness`)

#### Examples

- `{{ primary.hex }}` outputs `3f4ba2`
- `{{ primary.rgb }}` outputs `rgb(193, 132, 207)`
- `{{ primary.red }}` outputs `193`
- `{{ primary.hsl }}` outputs `hsl(268,41%,66%)`
- `{{ primary.hue }}` outputs `268`

Output files are written to `~/.local/state/caelestia/theme/`. You can symlink them to your desired locations.

### Fixed Matuz palette

This fork defaults to `matuz/default/dark` on a new install. Existing installations retain their
selected scheme in `~/.local/state/caelestia/scheme.json`; select the new palette once with:

```sh
caelestia scheme set --name matuz --flavour default --mode dark
```

Its accents are red `FC1A70`, purple `702EF3`, blue `1E65FF`, orange `FF4D00`, yellow `FFFF87`,
and green `A4E400`, over neutral dark surfaces. Changing the wallpaper updates the wallpaper and
thumbnail but **does not change, regenerate, or reapply the current colour scheme** (including when
`dynamic` is selected). Change the scheme explicitly with `caelestia scheme set`; the wallpaper
post-hook still runs. When a static scheme is selected, `caelestia wallpaper --print` reports that
scheme's colours rather than a wallpaper-derived preview.

## Record through a running OBS Studio

The Caelestia utilities drawer uses OBS's built-in WebSocket v5 server to control the
**existing** OBS session. In OBS, enable **Tools → WebSocket Server Settings → Enable
WebSocket server** (default local port `4455`); keep password authentication enabled.
The CLI reads the port/password from your own `~/.config/obs-studio/plugin_config/obs-websocket/config.json`
without printing the password. `OBS_WEBSOCKET_PORT` and `OBS_WEBSOCKET_PASSWORD` override
that file if needed. The server must be enabled in OBS; Caelestia will not start or kill OBS
or silently launch another recorder when the server is unreachable.

```sh
caelestia record --obs --status    # JSON: active/paused state and elapsed seconds
caelestia record --obs --start     # start unless already recording
caelestia record --obs --pause     # pause/resume a running recording
caelestia record --obs --stop      # stop and show the OBS output path
```

OBS controls the capture sources, audio, format and output location in its own scene/profile.
The `--region`, `--sound` and `record.extraArgs` settings belong to the original
`gpu-screen-recorder` backend; do not combine those flags with `--obs`. Running
`caelestia record` **without** `--obs` preserves that legacy behavior.

## Configuring

All configuration options are in `~/.config/caelestia/cli.json`.

<details><summary>Example configuration</summary>

```json
{
    "record": {
        "extraArgs": []
    },
    "wallpaper": {
        "postHook": "echo $WALLPAPER_PATH $SCHEME_NAME $SCHEME_FLAVOUR $SCHEME_MODE $SCHEME_VARIANT $SCHEME_COLOURS"
    },
    "theme": {
        "enableTerm": true,
        "enableHypr": true,
        "enableDiscord": true,
        "enableSpicetify": true,
        "enablePandora": true,
        "enableFuzzel": true,
        "enableBtop": true,
        "enableNvtop": true,
        "enableHtop": true,
        "enableGtk": true,
        "enableQt": true,
        "enableWarp": true,
        "enableChromium": true,
        "enableZed": true,
        "enableCava": true,
        "iconTheme": "Papirus-Dark",
        "iconThemeLight": "Papirus-Light",
        "iconThemeDark": "Papirus-Dark",
        "postHook": "echo $SCHEME_NAME $SCHEME_FLAVOUR $SCHEME_MODE $SCHEME_VARIANT $SCHEME_COLOURS"
    },
    "toggles": {
        "communication": {
            "discord": {
                "enable": true,
                "match": [{ "class": "discord" }],
                "command": ["discord"],
                "move": true
            },
            "whatsapp": {
                "enable": true,
                "match": [{ "class": "whatsapp" }],
                "move": true
            }
        },
        "music": {
            "spotify": {
                "enable": true,
                "match": [{ "class": "Spotify" }, { "initialTitle": "Spotify" }, { "initialTitle": "Spotify Free" }],
                "command": ["spicetify", "watch", "-s"],
                "move": true
            },
            "feishin": {
                "enable": true,
                "match": [{ "class": "feishin" }],
                "move": true
            }
        },
        "sysmon": {
            "btop": {
                "enable": true,
                "match": [{ "class": "btop", "title": "btop", "workspace": { "name": "special:sysmon" } }],
                "command": ["foot", "-a", "btop", "-T", "btop", "fish", "-C", "exec btop"]
            }
        },
        "todo": {
            "todoist": {
                "enable": true,
                "match": [{ "class": "Todoist" }],
                "command": ["todoist"],
                "move": true
            }
        }
    },
    "dots": {
        "url": "https://github.com/caelestia-dots/caelestia.git",
        "branch": "main"
    }
}
```

</details>
