"""Version routing must never load one API group's DLL into a different host."""
from pathlib import Path
import sys,unittest,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from bridge.cad_targets import TARGETS,target_for_series
import install_panel

class MultiVersionRouting(unittest.TestCase):
    def test_each_requested_year_is_covered_once(self):
        years=[year for target in TARGETS for year in target['years']]
        self.assertEqual(sorted(years),list(range(2014,2025)))
        self.assertEqual(len(years),len(set(years)))

    def test_api_boundaries_select_the_matching_group(self):
        expected={'19.1':'2014','20.0':'2015-2016','20.1':'2015-2016','21.0':'2017','22.0':'2018',
            '23.0':'2019-2020','23.1':'2019-2020','24.0':'2021-2024','24.1':'2021-2024','24.2':'2021-2024','24.3':'2021-2024'}
        for series,key in expected.items():
            with self.subTest(series=series):self.assertEqual(target_for_series('R'+series)['key'],key)

    def test_unrequested_generations_do_not_match(self):
        for series in ['R18.2','R19.0','R19.2','R24.4','R25.0','R25.1','R26.0']:
            self.assertIsNone(target_for_series(series),series)

    def test_package_components_have_nonoverlapping_version_ranges(self):
        package=ET.fromstring(install_panel.bundle_xml())
        components=package.findall('Components');self.assertEqual(len(components),6)
        for target in TARGETS:
            for year in target['years']:
                series={2014:'R19.1',2015:'R20.0',2016:'R20.1',2017:'R21.0',2018:'R22.0',2019:'R23.0',2020:'R23.1',2021:'R24.0',2022:'R24.1',2023:'R24.2',2024:'R24.3'}[year]
                value=tuple(map(int,series[1:].split('.')));matching=[]
                for component in components:
                    req=component.find('RuntimeRequirements')
                    low=tuple(map(int,req.get('SeriesMin')[1:].split('.')));high=tuple(map(int,req.get('SeriesMax')[1:].split('.')))
                    if low<=value<=high:matching.append(component.find('ComponentEntry').get('ModuleName'))
                self.assertEqual(matching,['./Contents/'+target['module']])

    def test_every_component_is_windows_64_bit(self):
        for component in ET.fromstring(install_panel.bundle_xml()).findall('Components'):
            self.assertEqual(component.find('RuntimeRequirements').get('OS'),'Win64')

    def test_legacy_and_new_launch_commands_are_in_every_component(self):
        for component in ET.fromstring(install_panel.bundle_xml()).findall('Components'):
            names={c.get('Global') for c in component.findall('.//Command')}
            self.assertTrue({'COUNTINGTREES','数树','PLANTCAD','PLANTCADPLACE'}<=names)

    def test_installer_contains_only_paired_runtime_files_and_all_six_modules(self):
        modules={target['module'] for target in TARGETS}
        self.assertTrue(modules<=set(install_panel.FILES));self.assertEqual(len(install_panel.FILES),14)
        self.assertEqual(len(install_panel.FILES),len(set(install_panel.FILES)))
        for name in install_panel.FILES:
            path=Path(name);self.assertFalse(path.is_absolute());self.assertNotIn('..',path.parts)
            self.assertNotIn('sdk-cache',path.parts)

    def test_upgrade_preserves_existing_bundle_identity(self):
        package=ET.fromstring(install_panel.bundle_xml())
        self.assertEqual(package.get('ProductCode'),'{D75A82EC-CE0F-4E2D-AFC4-28FCD8D02618}')
        self.assertEqual(package.get('UpgradeCode'),'{C2916E13-F217-47DD-981D-52C14ED13391}')
        self.assertEqual(package.get('Name'),'CountingTrees')

if __name__=='__main__':unittest.main()
