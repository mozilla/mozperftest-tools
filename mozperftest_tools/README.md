# mozperftest_tools

This repository is a collection of various tools that are useful for the things we do in Performance and Performance Testing. You can find the most interesting ones documented below.

## Setup

`pip install mozperftest-tools`

## Browsertime Side-by-Side Video Comparisons

The `side_by_side.py` tool can be used to generate a side-by-side comparion of two browsertime videos. This can be useful for determining if a regression/improvement is legitimate or not. It uses the similarity metric which is calculated using video histograms. See below for more information.

```
from mozperftest_tools.side_by_side import SideBySide

s = SideBySide("welcome-linux/")
s.run(
    test_name="browsertime-first-install-firefox-welcome-fis-e10s",
    platform="test-linux1804-64-shippable-qr/opt-browsertime-first-install-firefox-welcome-fis-e10s",
    base_branch="autoland",
    base_revision="a9fcab1e5680054879d4d9547b0a36f6e15b1216",
    new_branch="autoland",
    new_revision="962cc435d9fbdd0b69e678bdc62a041f7164c7f4"
)
```

