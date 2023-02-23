# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from mozperftest_tools.side_by_side import SideBySide
from mozperftest_tools.profile_enhancer import ProfileEnhancer
pe = ProfileEnhancer(".")
pe.run(
	"/home/sparky/Downloads/profile_cnn/cnn-cold/tmp.json",
	"/home/sparky/Downloads/profile_cnn/cnn-cold/tmp-regressed.json"
)
