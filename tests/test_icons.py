import unittest

from maderpacker.icons import recolor_svg, scheme_color

COOLICON = ('<svg width="24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M1 2" stroke="currentColor" stroke-width="2"/></svg>')
PLAIN = ('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
         '<title>GitHub</title><path d="M12 .297"/></svg>')


class TestRecolor(unittest.TestCase):
    def test_replaces_currentcolor(self):
        out = recolor_svg(COOLICON, "#FFFFFF")
        self.assertIn('stroke="#FFFFFF"', out)
        self.assertNotIn("currentColor", out)

    def test_keeps_explicit_root_fill(self):
        out = recolor_svg(COOLICON, "#FFFFFF")
        self.assertIn('fill="none"', out)

    def test_adds_root_fill_when_missing(self):
        out = recolor_svg(PLAIN, "#1E1E1E")
        self.assertIn('<svg fill="#1E1E1E"', out)
        self.assertIn("<title>GitHub</title>", out)

    def test_scheme_color(self):
        self.assertEqual(scheme_color(True), "#FFFFFF")
        self.assertEqual(scheme_color(False), "#1E1E1E")


if __name__ == "__main__":
    unittest.main()
