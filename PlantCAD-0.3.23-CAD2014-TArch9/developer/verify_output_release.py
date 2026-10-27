"""Run current planting output and pre-existing kernel regression checks on a fixture copy."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'bridge/host-output/area-native-224da63d/input.dwg'
def run(script,*args):
    print('CHECK',script,flush=True)
    subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'developer'/script),*map(str,args)],check=True)
if __name__=='__main__':
    run('build.py')
    for name in ['verify_native_rules.py','verify_placement_interop.py','verify_area_native.py','verify_workflow_native.py','verify_area_selection_native.py','verify_normalization_native.py']:
        run(name,'--drawing',FIXTURE)
    run('verify_output_native.py')
    run('verify_schedule_split.py')
    run('verify_label_feedback.py')
    run('verify_manual_area.py')
    run('diagnose_performance.py','--drawing',ROOT.parent/'20261016压力测试01/Drawing2.dwg')
    run('verify_release.py')
