"""Verify actual AutoLISP rules in AutoCAD 2014 Core Console; this is not GUI/Tianzheng acceptance."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'developer/tests'))
from lisp_harness import parse

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--drawing',type=Path,required=True,help='Existing DWG copied to an isolated test folder; original is not modified.')
    ap.add_argument('--cad-dir',type=Path,default=Path(os.environ.get('PLANTCAD_CAD_DIR',r'D:\Program Files (x86)\CAD2014\AutoCAD 2014')))
    args=ap.parse_args()
    engine=args.cad_dir/'accoreconsole.exe'
    if not engine.is_file() or not args.drawing.is_file():raise RuntimeError('Core Console and a test DWG are required.')
    output=ROOT/'bridge/host-output'/('native-rules-'+uuid.uuid4().hex[:8]);output.mkdir(parents=True)
    source_hash=hashlib.sha256(args.drawing.read_bytes()).hexdigest()
    shutil.copy2(args.drawing,output/'input.dwg')
    hashes={}
    for name in ['plantcad-core.lsp','plantcad-workflow.lsp']:
        source=ROOT/'developer/src'/name
        hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
        (output/name).write_bytes(source.read_text(encoding='utf-8').replace('\n','\r\n').encode('gbk'))
    box="'((0.0 0.0) (10.0 0.0) (10.0 10.0) (0.0 10.0))"
    concave="'((0.0 0.0) (8.0 0.0) (8.0 3.0) (3.0 3.0) (3.0 8.0) (0.0 8.0))"
    cases=[
        ('open_path','(pl:line-stations 10.0 2.0 nil)',[0.,2.,4.,6.,8.,10.]),
        ('closed_path','(pl:line-stations 10.0 2.0 T)',[0.,2.,4.,6.,8.]),
        ('valid_boundary','(pl:simple-polygon '+box+')',True),
        ('self_intersection',"(pl:simple-polygon '((0.0 0.0) (10.0 10.0) (0.0 10.0) (10.0 0.0)))",None),
        ('concave_inside',"(list (pl:inside-polygon '(1.0 7.0) "+concave+") (pl:inside-polygon '(7.0 7.0) "+concave+'))',[True,None]),
        ('grid_count','(length (pl:polygon-grid '+box+' 2.0))',25),
        ('survey_area',"(pl:polygon-area '((1000000000.0 1000000000.0) (1000000010.0 1000000000.0) (1000000010.0 1000000010.0) (1000000000.0 1000000010.0)))",100.),
        ('separate_units',"""(progn
          (setq pc:p (pl:put 'name "银杏" (pl:empty-plant "P001")))
          (setq pc:a (pl:put 'quantity_unit "平方米" pc:p))
          (setq pc:rows (pl:add-quantity pc:a 12.5 (pl:add-quantity pc:p 1 nil)))
          (setq pc:rows (pl:add-quantity pc:a 3.25 pc:rows))
          (list (caddr (car pc:rows)) (caddr (cadr pc:rows))))""",[1,15.75])
    ]
    cases.extend([
        ('centimetre_roundtrip',"""(progn
          (setq pc:p (pl:put 'crown (pl:dimension-input 'crown "300" 0) (pl:empty-plant "PC")))
          (list (pl:get 'crown pc:p) (pl:dimension-cm 'crown pc:p) (pl:block-scale pc:p 1000.0)))""",[3.,300.,3000.]),
        ('optional_shrub_diameter',"""(progn
          (setq pc:p (pl:put 'kind 1 (pl:empty-plant "PC")))
          (and (= (pl:dbh-text pc:p 0 nil) "") (= (pl:dimension-input 'dbh "——" 1) 0.0)))""",True),
        ('selected_filter_retention',"""(progn
          (setq pc:a '((id . "A") (name . "A") (category . 0)) pc:b '((id . "B") (name . "B") (category . 1)))
          (setq pc:rows (pl:species-merge-selection (list pc:a) (list pc:b) '(0)))
          (list (pl:get 'id (car pc:rows)) (pl:get 'id (cadr pc:rows))))""",['A','B']),
        ('explicit_species_tags',"""(equal (pl:species-tags '((category . 0) (tags . "彩叶|开花"))) '("常绿" "彩叶" "开花"))""",True),
    ])
    report={'passed':False,'scope':'AutoCAD 2014 Core Console: native AutoLISP rules only; no modeless UI, mouse or Tianzheng launcher acceptance',
            'source_sha256':hashes,'checks':[]}
    path=ROOT/'developer/native-rule-verification.json'
    def quote(p):return '"'+str(p).replace('\\','/')+'"'
    si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    try:
        for name,expr,expected in cases:
            target=output/(name+'.txt')
            body="(setq pc:r (vl-catch-all-apply 'eval (list '"+expr+")))\n"
            body+='(setq pc:f (open '+quote(target)+' "w"))\n'
            body+='(prin1 (if (vl-catch-all-error-p pc:r) (vl-catch-all-error-message pc:r) pc:r) pc:f)\n(close pc:f)\n(princ)\n'
            lsp=output/(name+'.lsp');lsp.write_bytes(body.replace('\n','\r\n').encode('gbk'))
            scr=output/(name+'.scr')
            scr.write_bytes(('\r\n'.join(['(load '+quote(output/'plantcad-core.lsp')+')',
              '(load '+quote(output/'plantcad-workflow.lsp')+')','(load '+quote(lsp)+')','_.QUIT'])+'\r\n').encode('gbk'))
            run=subprocess.run([str(engine),'/i',str(output/'input.dwg'),'/s',str(scr)],cwd=output,
                               startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            actual=parse(target.read_text(encoding='gbk'))[0] if target.exists() else 'missing output'
            if run.returncode!=0 or actual!=expected:raise AssertionError((name,run.returncode,actual,expected))
            report['checks'].append(name)
            print('PASS native '+name,flush=True)
        assert hashlib.sha256(args.drawing.read_bytes()).hexdigest()==source_hash
        report['original_drawing_unchanged']=True;report['passed']=True
    finally:path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Native AutoLISP rule checks passed; GUI acceptance remains separate.')
if __name__=='__main__':main()
