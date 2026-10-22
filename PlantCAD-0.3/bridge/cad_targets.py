"""Autodesk documented managed-API compatibility groups, Windows x64 only."""
from pathlib import Path

COMPATIBILITY_URL='https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-Customization/files/GUID-A6C680F2-DE2E-418A-A182-E4884073338A.htm'
TARGETS=(
    dict(key='2014',years=[2014],series_min='R19.1',series_max='R19.1',sdk=None,framework='4.0',module='bridge/PlantCADBridge.dll'),
    dict(key='2015-2016',years=[2015,2016],series_min='R20.0',series_max='R20.1',sdk='20.0.0',framework='4.5',module='bridge/2015-2016/PlantCADBridge.dll'),
    dict(key='2017',years=[2017],series_min='R21.0',series_max='R21.0',sdk='21.0.0',framework='4.6',module='bridge/2017/PlantCADBridge.dll'),
    dict(key='2018',years=[2018],series_min='R22.0',series_max='R22.0',sdk='22.0.0',framework='4.6',module='bridge/2018/PlantCADBridge.dll'),
    dict(key='2019-2020',years=[2019,2020],series_min='R23.0',series_max='R23.1',sdk='23.0.0',framework='4.7',module='bridge/2019-2020/PlantCADBridge.dll'),
    dict(key='2021-2024',years=[2021,2022,2023,2024],series_min='R24.0',series_max='R24.3',sdk='24.0.0',framework='4.8',module='bridge/2021-2024/PlantCADBridge.dll'),
)

def target_for_series(series):
    version=tuple(int(part) for part in str(series).strip().lstrip('Rr').split('.')[:2])
    for target in TARGETS:
        low=tuple(map(int,target['series_min'][1:].split('.')))
        high=tuple(map(int,target['series_max'][1:].split('.')))
        if low<=version<=high:return target
    return None

def compiled_targets(root):
    root=Path(root)
    return [t for t in TARGETS if (root/t['module']).is_file()]
