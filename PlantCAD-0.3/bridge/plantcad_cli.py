"""Structured CLI for clients that can launch tools. Uses exactly the MCP tool schemas."""
import argparse
import json
from pathlib import Path
import sys
from mcp_server import MCPServer,QueueBridge
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['status','get_plants','catalogue','preview_adjust','apply_adjust','plot_settings'])
    parser.add_argument('--args-file',type=Path,help='UTF-8 JSON arguments, never executable code')
    args=parser.parse_args()
    arguments=json.loads(args.args_file.read_text(encoding='utf-8-sig')) if args.args_file else {}
    response=MCPServer(QueueBridge(Path(__file__).resolve().parent/'runtime')).handle(
        {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'plantcad_'+args.action,'arguments':arguments}})
    result=response.get('result',response)
    print(json.dumps(result.get('structuredContent',result),ensure_ascii=False,indent=2))
    return 1 if 'error' in response or result.get('isError') else 0
if __name__=='__main__':sys.exit(main())
