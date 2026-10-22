"""Validate platform exports and the narrowly scoped legacy HACS compatibility."""
import gzip
import importlib.util
import json
import pathlib
import struct
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("home_share_brand_test")
package.__path__ = [str(ROOT / "custom_components/home_share")]
sys.modules[package.__name__] = package
from home_share_brand_test.hacs_branding import configure


class AssetTests(unittest.TestCase):
    def test_all_platform_pngs_are_present_and_have_expected_sizes(self):
        for dark in ['', 'dark_']:
            for double, factor in [('', 1), ('@2x', 2)]:
                for image, size in [('icon', (256, 256)), ('logo', (640, 160))]:
                    path = ROOT / f'custom_components/home_share/brand/{dark}{image}{double}.png'
                    raw = path.read_bytes()
                    self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
                    self.assertEqual(struct.unpack('>II', raw[16:24]), tuple(x*factor for x in size))
                    self.assertEqual(raw[25], 6, 'RGBA transparency is required')

    def test_panel_uses_canonical_source_artwork(self):
        self.assertEqual((ROOT/'custom_components/home_share/brand/icon.svg').read_bytes(),
                         (ROOT/'custom_components/home_share/frontend/home-share-mark.svg').read_bytes())


class HacsCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.hacs = self.root/'custom_components/hacs'
        self.frontend = self.hacs/'hacs_frontend/frontend_latest'
        self.frontend.mkdir(parents=True)
        (self.hacs/'manifest.json').write_text(json.dumps({'version':'2.0.5'}))
        (self.hacs/'hacs_frontend/version.py').write_text('VERSION="20250128065759"')
        self.original = 'const a=e=>`https://brands.home-assistant.io/${e.brand?"brands/":""}${e.useFallback?"_/":""}${e.domain}/${e.darkOptimized?"dark_":""}${e.type}.png`;'
        self.assets = [self.frontend/f'{i}.abcdef.js' for i in range(7)]
        for path in self.assets:
            path.write_text(self.original)
            path.with_suffix('.js.gz').write_bytes(gzip.compress(self.original.encode(),mtime=0))

    def tearDown(self):
        self.temp.cleanup()

    def test_patch_is_scoped_idempotent_and_gzip_matches(self):
        self.assertEqual(configure(self.root,True)['files'],14)
        for path in self.assets:
            value=path.read_text()
            self.assertIn('e.domain==="home_share"?',value)
            self.assertIn('https://brands.home-assistant.io/',value)
            self.assertEqual(gzip.decompress(path.with_suffix('.js.gz').read_bytes()),value.encode())
        self.assertEqual(configure(self.root,True)['status'],'unchanged')

    def test_disable_restores_originals_exactly(self):
        configure(self.root,True)
        self.assertEqual(configure(self.root,False)['restored'],14)
        for path in self.assets:
            self.assertEqual(path.read_text(),self.original)
            self.assertEqual(path.with_suffix('.js.gz').read_bytes(),gzip.compress(self.original.encode(),mtime=0))

    def test_external_modification_is_not_overwritten_on_restore(self):
        configure(self.root,True)
        self.assets[0].write_text('external update')
        self.assertEqual(configure(self.root,False)['skipped'],1)
        self.assertEqual(self.assets[0].read_text(),'external update')

    def test_other_hacs_versions_are_not_modified(self):
        (self.hacs/'manifest.json').write_text(json.dumps({'version':'2.0.6'}))
        self.assertEqual(configure(self.root,True)['status'],'unsupported_version')
        self.assertEqual(self.assets[0].read_text(),self.original)

    def test_unknown_distribution_fails_before_any_write(self):
        self.assets[0].write_text('different build')
        with self.assertRaisesRegex(ValueError,'Unrecognized'):
            configure(self.root,True)
        self.assertEqual(self.assets[1].read_text(),self.original)

    def test_corrupt_gzip_fails_before_any_write(self):
        self.assets[0].with_suffix('.js.gz').write_bytes(gzip.compress(b'different'))
        with self.assertRaisesRegex(ValueError,'differs'):
            configure(self.root,True)
        self.assertEqual(self.assets[1].read_text(),self.original)


if __name__=='__main__':
    unittest.main()
