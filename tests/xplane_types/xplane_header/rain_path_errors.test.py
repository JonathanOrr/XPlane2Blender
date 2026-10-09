from io_xplane2blender.tests import *
from io_xplane2blender.xplane_types.xplane_attribute import XPlaneAttribute
from io_xplane2blender.xplane_types.xplane_attributes import XPlaneAttributes
from io_xplane2blender.xplane_types.xplane_header_rain import NAMES, collect


class _Settings:
    """Rain settings with one wiper and one thermal source turned on"""

    def __init__(self, wiper_texture: str, thermal_texture: str) -> None:
        self.rain_scale = 1.0
        self.wiper_texture, self.thermal_texture = wiper_texture, thermal_texture
        self.wiper_1 = type("W", (), {"dataref": "sim/w", "start": 0.0, "end": 1.0, "nominal_width": 0.1})()
        self.thermal_source_1 = type("T", (), {"defrost_time": "1", "dataref_on_off": "sim/t"})()
        for kind in ("wiper", "thermal_source"):
            for i in range(1, 5):
                setattr(self, f"{kind}_{i}_enabled", i == 1)


def _relative(path: str) -> str:
    if " " in path:
        raise ValueError  # as XPlaneHeader.get_path_relative_to_dir does, after logging its error
    return path


class TestRainPathErrors(XPlaneTestCase):
    """A rain texture whose path can't be written is an error of its own, not the end of the export"""

    def _collect(self, wiper: str, thermal: str) -> XPlaneAttributes:
        attributes = XPlaneAttributes()
        for name in NAMES:
            attributes.add(XPlaneAttribute(name, None))
        collect(attributes, _Settings(wiper, thermal), "file", _relative)
        return attributes

    def test_a_bad_wiper_path_keeps_the_thermal_lines(self) -> None:
        attributes = self._collect("my wipers/w.png", "t.png")
        self.assertIsNone(attributes["WIPER_texture"].getValue())
        self.assertEqual("t.png", attributes["THERMAL_texture"].getValue())

    def test_a_bad_thermal_path_keeps_the_wiper_lines(self) -> None:
        attributes = self._collect("w.png", "my heat/t.png")
        self.assertIsNone(attributes["THERMAL_texture"].getValue())
        self.assertEqual("w.png", attributes["WIPER_texture"].getValue())


runTestCases([TestRainPathErrors])
