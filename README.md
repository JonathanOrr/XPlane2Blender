[![Tests](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml/badge.svg?branch=develop)](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

> **X-Plane 12 Aircraft Tools is an unofficial fork of [XPlane2Blender](https://github.com/X-Plane/XPlane2Blender)**,
> not affiliated with or supported by Laminar Research. Please report problems with it
> [here](https://github.com/JonathanOrr/XPlane2Blender/issues), not to Laminar Research.

# X-Plane 12 Aircraft Tools
A Blender add-on (Blender 3.6 and up, 5.2 LTS recommended) for making X-Plane 12 aircraft and cockpits: import an
aircraft or an OBJ, change it or add to it, and export X-Plane 12 OBJs.

How it differs from XPlane2Blender:
- X-Plane 12 aircraft only. There is no X-Plane version setting and nothing for scenery or for X-Plane 9 and 10. Files
  made with XPlane2Blender open and are converted once; every aircraft setting of XPlane2Blender is kept, under the same
  stored names, and has a place in the panels.
- Plain-words panels that follow the selection: an **X-Plane** panel in the Properties editor's Object, Bone,
  Material, Collection and Scene tabs, each showing only what applies to what is selected.
- Work in progress always exports: settings that are not filled in yet are left out, never an error.
- An importer for whole aircraft (.acf) and OBJ files, so an aircraft can come in, be changed and go out again.

## Documentation
The [User Guide](docs/README.md) explains the add-on with pictures of its panels:
[Getting Started](docs/getting-started.md), [Cockpit Controls](docs/cockpit-controls.md), [Lights](docs/lights.md),
[Materials And Screens](docs/materials-and-screens.md), [Files And Export](docs/files-and-export.md),
[Importing](docs/importing.md), [Working Faster](docs/working-faster.md), and the
[Settings Reference](docs/reference.md) with every setting, button and menu. The guide is checked by the test suite,
so it describes the add-on as it is.

## Installation
Download the add-on .zip from the [releases](https://github.com/JonathanOrr/XPlane2Blender/releases) (do not unzip
it), install it in Blender's Preferences > Add-ons, enable X-Plane 12 Aircraft Tools and restart Blender. It replaces
XPlane2Blender, so do not enable both. Step by step: [Getting Started](docs/getting-started.md#install).

Always keep backups of your .blend files: a file opened and saved with this add-on has been converted to X-Plane 12.

## Relationship To XPlane2Blender
This fork started from XPlane2Blender 4.5 (the tag `upstream-base`) and has since been rewritten for X-Plane 12
aircraft only: the exporter no longer has code for older X-Plane versions or scenery, and the settings, panels and
updater are reorganized into small modules. Fixes no longer move between the two projects by cherry-picking; a fix
that matters to both is ported by hand. The settings keep XPlane2Blender's stored names, so a file can still be opened
with XPlane2Blender, which sees its aircraft settings as they are.

## Documentation Sources
- [XPlane2Blender Manual](https://xp2b-docs.gitbook.io/xplane2blender-docs)
- [The PZL-M-18, an open source aircraft](https://github.com/todirbg/PZL-M-18)
- [The BD-5J Microjet, an open source jet](https://forums.x-plane.org/index.php?/files/file/27269-bd-5j-microjet)
- [Dan Klaue's "Using Blender With PlaneMaker" Playlist](https://www.youtube.com/playlist?list=PLDB0F4B925CF9169C). While older it still explains many of the principles of XPlane2Blender
- [X-Plane Scenery File Formats](http://developer.x-plane.com/docs/specs/)
- [X-Plane.org's 3d Modeling board](https://forums.x-plane.org/index.php?/forums/forum/45-3d-modeling/)
- [X-Plane Scenery Developer Blog/Knowledge Base](http://developer.x-plane.com/)
- [X-Plane Modeling Tutorials](http://developer.x-plane.com/docs/modeling/)

## Test Suite
The average user does not need the test suite. Before releasing a build to the public we test the code many many many times! This is only useful for developers and power users who make changes to the source code. The tests folder must also be in the same folder as the addon folder (see manual installation).

If you have Python 3 installed (it only launches Blender; the tests themselves run on Blender's bundled Python) and the full source code downloaded, you can run the test suite. It will attempt to export sample .blend files that utilize various features of the exporter and print the results (see the contents of the ``test`` folder). All passing means XPlane2Blender is safe to use. In the XPlane2Blender folder, open up a command line and run

``python tests.py --print-fails``

This runs the test files in parallel (``-j N`` sets how many at once, default is your CPU count) and stops at the first failing file, or use ``--continue`` to run everything. Only detailed logs will be printed for failed tests, and the exit code is non-zero if anything failed. See ``--help`` to show all flags and what they do.

If Blender isn't in your path, point the test runner at it with ``--blender /path/to/blender``.

## Code Style
New and changed code is formatted with [black](https://github.com/psf/black) and [isort](https://pycqa.github.io/isort/), applied only to the lines you touch so that old code isn't reformatted wholesale. To set it up:

```
pip install -r requirements.txt
pre-commit install
```

[ruff](https://docs.astral.sh/ruff/) also runs to catch real bugs like undefined names. The settings are in ``pyproject.toml``.
