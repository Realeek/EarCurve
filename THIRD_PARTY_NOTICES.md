# Third-party notices

EarCurve is MIT-licensed (see [LICENSE](LICENSE)). The distributed Windows
builds also contain third-party components with their own licenses. This file
is informational; the full license texts are in [`licenses/`](licenses/).

## Components

| Component | Version | License | License text |
| --- | --- | --- | --- |
| Python | 3.12.15 | PSF-2.0 | `licenses/PSF-2.0.txt` |
| PySide6-Essentials / shiboken6 / Qt | 6.12.0 | LGPL-3.0 (or GPL-3.0/commercial) | `licenses/LGPL-3.0.txt`, `licenses/GPL-3.0.txt`, `licenses/Qt-PySide6-notice.txt` |
| numpy | 2.5.4 | BSD-3-Clause | `licenses/numpy-BSD-3-Clause.txt` |
| sounddevice | 0.5.6 | MIT | `licenses/sounddevice-MIT.txt` |
| PortAudio (bundled by sounddevice) | bundled DLLs | MIT-style | `licenses/PortAudio-MIT.txt` |
| soundfile | 0.14.0 | BSD-3-Clause | `licenses/soundfile-BSD-3-Clause.txt` |
| libsndfile (bundled by soundfile) | 1.2.2 | LGPL-2.1 | `licenses/libsndfile-LGPL-2.1.txt` |
| PyInstaller | 6.22.3 | GPL-2.0 with bootloader exception | `licenses/PyInstaller-GPL-2.0-with-exception.txt` |
| OpenSSL (bundled by Python/Qt) | 3.x | Apache-2.0 | `licenses/Apache-2.0.txt` |
| Microsoft Universal C Runtime | Windows system runtime | Microsoft redistributable terms | System component |

## LGPL / relinking information

Qt/PySide6 and libsndfile are LGPL-licensed. They are dynamically loaded in
the onedir build, where the shared libraries remain separate files under
`_internal/PySide6/` and `_internal/_soundfile_data/`. You can replace those
files with a compatible build of the same libraries.

The onefile build is a convenience distribution that extracts the same files
at runtime. For strict LGPL relinking, use the onedir build, or rebuild from
the public source and build scripts in this repository. The corresponding
source of the LGPL-covered components is available from:

- Qt: https://code.qt.io/cgit/qt/
- PySide6: https://code.qt.io/cgit/pyside/pyside-setup.git/
- libsndfile: https://github.com/libsndfile/libsndfile

For three years after distribution, the EarCurve maintainer will provide the
corresponding source for the LGPL-covered components used in a release on
request via GitHub Issues. This is a written offer under the LGPL.

Qt third-party notices are maintained by the Qt project at
https://code.qt.io/cgit/qt/qtbase.git/tree/LICENSES and should be consulted
together with the Qt license.

## Bundled music

The eight excerpts under `assets/tracks/` are CC0 1.0; see
[assets/tracks/CREDITS.md](assets/tracks/CREDITS.md) and
[assets/tracks/CC0-1.0.txt](assets/tracks/CC0-1.0.txt).

## Trademarks

DARKRIM, Darkrim Shadow, 寸渊影弑, DTS, Dolby, Windows, and other names are
trademarks or registered trademarks of their respective owners. EarCurve is
an unofficial third-party tool and is not affiliated with or endorsed by
those owners. Model names are used only to describe compatibility.

## No legal advice

This notice is provided for transparency and is not legal advice. If you
redistribute a modified build, review the applicable licenses with qualified
counsel and preserve the notices and license texts.
