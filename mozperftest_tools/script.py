from mozperftest_tools.side_by_side import SideBySide
from mozperftest_tools.profile_enhancer import ProfileEnhancer
pe = ProfileEnhancer(".")
pe.run(
	"/home/sparky/Downloads/profile_cnn/cnn-cold/tmp.json",
	"/home/sparky/Downloads/profile_cnn/cnn-cold/tmp-regressed.json"
)
