"""Generate local desktop connection files. Does not modify AI model/account settings."""
from pathlib import Path
import argparse
import json
import os
import sys
ROOT=Path(__file__).resolve().parent
def generate(destination=None):
    output=Path(destination or ROOT/'clients')
    output.mkdir(parents=True,exist_ok=True)
    server={'command':sys.executable,'args':['-B',str(ROOT/'mcp_server.py')]}
    generic={'mcpServers':{'plantcad':server}}
    workbuddy={'mcpServers':{'plantcad':{'type':'stdio',**server,'timeout':60000}}}
    for name,value in [('mcp.json',generic),('workbuddy.mcp.json',workbuddy)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # YAML uses JSON double-quoted scalars so Windows backslashes stay literal.
    dump=lambda value:json.dumps(value,ensure_ascii=False)
    yaml="- id: mcp-plantcad\n  name: '@deepseek-ai/dsh-mcp-client'\n  config:\n    serverName: plantcad\n    transport: stdio\n    command: "+dump(sys.executable)+"\n    args: "+dump(server['args'])+"\n    toolCallTimeoutMs: 60000\n"
    (output/'deepseek-harness.plugins.yaml').write_text(yaml,encoding='utf-8')
    toml='[mcp_servers.plantcad]\ncommand = '+dump(sys.executable)+'\nargs = '+dump(server['args'])+'\nstartup_timeout_sec = 20\ntool_timeout_sec = 60\n'
    (output/'codex.config.toml').write_text(toml,encoding='utf-8')
    print('Generated local connection files:',output)
    return toml
def register_codex(fragment):
    import datetime,tomllib
    profile=Path(os.environ.get('USERPROFILE',str(Path.home())))
    config=Path(os.environ.get('CODEX_HOME',str(profile/'.codex')))/'config.toml'
    text=config.read_text(encoding='utf-8') if config.exists() else ''
    original=tomllib.loads(text)
    desired=tomllib.loads(fragment)['mcp_servers']['plantcad']
    existing=original.get('mcp_servers',{}).get('plantcad')
    if existing==desired: print('Codex CountingTrees（数树） already registered.');return
    if existing is not None: raise SystemExit('Existing plantcad entry differs; review it before replacing.')
    combined=text.rstrip()+'\n\n'+fragment
    parsed=tomllib.loads(combined)
    parsed['mcp_servers'].pop('plantcad')
    if not parsed['mcp_servers'] and 'mcp_servers' not in original:parsed.pop('mcp_servers')
    if parsed!=original: raise SystemExit('Refusing unrelated configuration changes.')
    config.parent.mkdir(parents=True,exist_ok=True)
    if config.exists():
        backup=config.with_name(config.name+'.plantcad-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.backup')
        backup.write_bytes(config.read_bytes())
    temporary=config.with_name(config.name+'.plantcad.tmp')
    temporary.write_text(combined,encoding='utf-8')
    os.replace(temporary,config)
    print('Codex CountingTrees（数树） registered. Reload MCP or open a new desktop task to load it.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--register-codex',action='store_true')
    args=parser.parse_args();fragment=generate()
    if args.register_codex:register_codex(fragment)
