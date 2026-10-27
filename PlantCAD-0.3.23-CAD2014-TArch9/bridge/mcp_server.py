"""Local stdio MCP adapter for PlantCAD. No model API or external dependencies."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

VERSION = "0.3"
ACTIONS = {"get_plants", "catalogue", "preview_adjust", "apply_adjust", "plot_settings"}
TARGET_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "scope": {"type": "string", "enum": ["selection", "model", "handles"]},
        "handles": {"type": "array", "items": {"type": "string", "pattern": "^[0-9A-Fa-f]+$"}, "maxItems": 500},
        "name": {"type": "string"}, "spec_no": {"type": "string"},
    },
}
CHANGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "maxLength": 40},
        "species_id": {"type": "string"},
        "new_species_category": {"type": "integer", "minimum": 0, "maximum": 12},
        "dbh": {"type": "number", "minimum": 0, "description": "胸径，厘米"},
        "caliper": {"type": "number", "minimum": 0, "description": "地径，厘米"},
        "height": {"type": "number", "minimum": 0, "description": "苗高，米"},
        "crown": {"type": "number", "exclusiveMinimum": 0, "description": "实际冠幅，米"},
        "factor": {"type": "number", "exclusiveMinimum": 0},
        "style": {"type": "string", "enum": ["circle", "simple"]},
        "diameter_mode": {"type": "string", "enum": ["dbh", "caliper"]},
        "dx_m": {"type": "number"}, "dy_m": {"type": "number"},
    },
    "minProperties": 1,
}

def tool(name, description, properties, required=(), read_only=True):
    return {
        "name": name, "description": description,
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": properties, "required": list(required)},
        "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                        "idempotentHint": read_only, "openWorldHint": False},
    }

TOOLS = [
    tool("plantcad_status", "读取CAD桥接连接状态、当前绑定图纸和接通方法。", {}),
    tool("plantcad_get_plants", "读取插件植物的句柄、品种、规格和位置。必须先获取对象再预览微调。",
         {"target": TARGET_SCHEMA, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
    tool("plantcad_catalogue", "查找当前图纸品种库，返回品种ID与分类，供替换植物时明确关联。",
         {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}),
    tool("plantcad_preview_adjust", "预览微调，不改图纸。返回plan_id、对象数量和改前/改后数据。单位：径值cm，高度/冠幅/位移m。新名称须匹配品种库或明确提供new_species_category。",
         {"target": TARGET_SCHEMA, "changes": CHANGE_SCHEMA}, ("target", "changes")),
    tool("plantcad_apply_adjust", "执行已预览的微调并刷新关联文字与受管理表格。只在用户已明确授权该调整时使用；图纸或对象变化则拒绝旧计划。遇到超时或部分错误先读图核对，禁止盲目重试。",
         {"plan_id": {"type": "string"}}, ("plan_id",), False),
    tool("plantcad_plot_settings", "设置图纸出图比例/纸面字高，刷新内部文字；保持实际冠幅。",
         {"scale": {"type": "number", "exclusiveMinimum": 0},
          "paper_height": {"type": "number", "exclusiveMinimum": 0}}, (), False),
]

def validate(schema, value, path="arguments"):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict): raise ValueError(f"{path}必须是对象")
        properties = schema.get("properties", {})
        unknown = set(value) - set(properties)
        if unknown and schema.get("additionalProperties") is False:
            raise ValueError(f"{path}含不支持字段：{', '.join(sorted(unknown))}")
        for required in schema.get("required", []):
            if required not in value: raise ValueError(f"{path}缺少{required}")
        if len(value) < schema.get("minProperties", 0): raise ValueError("至少提供一个修改字段")
        for key, item in value.items():
            if key in properties: validate(properties[key], item, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list): raise ValueError(f"{path}必须是数组")
        if len(value) > schema.get("maxItems", 1000): raise ValueError("目标过多，请分批操作")
        for item in value: validate(schema["items"], item, path)
    elif kind in ("number", "integer"):
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"{path}必须是有限数字")
        if kind == "integer" and not isinstance(value, int): raise ValueError(f"{path}必须是整数")
        if "minimum" in schema and value < schema["minimum"]: raise ValueError(f"{path}过小")
        if "maximum" in schema and value > schema["maximum"]: raise ValueError(f"{path}过大")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]: raise ValueError(f"{path}必须大于0")
    elif kind == "string":
        if not isinstance(value, str): raise ValueError(f"{path}必须是文字")
        if any(ord(c) < 32 for c in value): raise ValueError("字段不能包含控制字符")
        if len(value) > schema.get("maxLength", 200): raise ValueError(f"{path}过长")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value): raise ValueError(f"{path}格式无效")
        try: value.encode("gbk")
        except UnicodeEncodeError: raise ValueError("旧版CAD暂不支持此字符，请使用GBK兼容文字") from None
    if "enum" in schema and value not in schema["enum"]: raise ValueError(f"{path}取值不支持")

def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)

class QueueBridge:
    def __init__(self, root, timeout=35.0):
        self.root = Path(root).resolve()
        self.timeout = timeout

    def status(self):
        try:
            state = json.loads((self.root / "session.json").read_text(encoding="utf-8-sig"))
            age = time.time() - float(state["heartbeat"])
            state["connected"] = bool(state.get("connected")) and 0 <= age < 30
            state["heartbeat_age_sec"] = max(0, round(age, 1))
            return state
        except (OSError, ValueError, KeyError, TypeError):
            return {"connected": False, "message": "CAD未连接。在AutoCAD2014中打开或切到要使用的已有底图，NETLOAD加载桥接DLL后运行PLANTCADCONNECT绑定当前图纸；无需新建空白图。"}

    def call(self, action, arguments):
        if action not in ACTIONS: raise ValueError("不支持此操作")
        state = self.status()
        if not state.get("connected"): raise RuntimeError(state.get("message", "CAD连接失效或正在忙碌，请先核对CAD状态"))
        if not state.get("active_document", True): raise RuntimeError("当前CAD活动图纸与绑定图纸不同；切回绑定图纸或重新PLANTCADCONNECT")
        request_id = uuid.uuid4().hex
        args = dict(arguments)
        if action == "preview_adjust": args["plan_id"] = uuid.uuid4().hex
        request = {"protocol": 1, "id": request_id, "session_id": state["session_id"],
                   "action": action, "arguments": args, "expires": time.time() + self.timeout}
        pending = self.root / "requests" / (request_id + ".json")
        result_path = self.root / "responses" / (request_id + ".json")
        atomic_json(pending, request)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8-sig"))
                if result.get("id") != request_id or result.get("session_id") != request["session_id"]:
                    raise RuntimeError("响应图纸会话不匹配")
                return result["result"]
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(0.08)
        # Queued requests must never execute later, after the client reported a timeout.
        try: pending.unlink()
        except FileNotFoundError: pass
        raise TimeoutError("CAD响应超时。若已开始执行，结果可能尚未返回；请先读取图纸核对，勿重复提交调整。")

class MCPServer:
    def __init__(self, bridge):
        self.bridge = bridge

    def handle(self, message):
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None: return None
        result = None
        try:
            if method == "initialize":
                requested = message.get("params", {}).get("protocolVersion")
                result = {
                    "protocolVersion": requested if requested in ("2024-11-05", "2025-03-26", "2025-06-18") else "2025-06-18",
                    "capabilities": {"tools": {}}, "serverInfo": {"name": "CountingTrees", "title": "数树", "version": VERSION},
                    "instructions": "用CountingTrees（数树）工具定位真实对象，先读图和预览，再按用户授权执行。只控制PLANTCADCONNECT绑定的图纸。工具不执行任意CAD脚本，不调用模型API，不自动保存图纸。超时或部分失败先读图核对，禁止盲目重试。灌木区域修补尚未实现，不能声称已完成。",
                }
            elif method == "ping": result = {}
            elif method == "tools/list": result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params", {})
                name = params.get("name")
                definition = next((t for t in TOOLS if t["name"] == name), None)
                if not definition: raise ValueError("未知工具")
                arguments = params.get("arguments", {})
                validate(definition["inputSchema"], arguments)
                try:
                    if name == "plantcad_status": output = self.bridge.status()
                    else:
                        action = name.removeprefix("plantcad_")
                        if action == "get_plants":
                            arguments.setdefault("target", {"scope": "selection"})
                            arguments.setdefault("limit", 200)
                        elif action == "catalogue": arguments.setdefault("limit", 100)
                        if action == "plot_settings" and not arguments: raise ValueError("请提供比例或纸面字高")
                        if action == "apply_adjust" and not re.fullmatch(r"[0-9a-f]{32}", arguments["plan_id"]):
                            raise ValueError("计划编号无效")
                        target = arguments.get("target")
                        if target and target.get("scope") == "handles" and not target.get("handles"):
                            raise ValueError("请提供明确的植物句柄")
                        output = self.bridge.call(action, arguments)
                except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
                    output = {"ok": False, "error": str(exc)}
                result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                          "structuredContent": output, "isError": output.get("ok") is False}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except (ValueError, TypeError, KeyError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-root", default=str(Path(__file__).resolve().parent / "runtime"))
    args = parser.parse_args()
    if hasattr(sys.stdin, "reconfigure"): sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    server = MCPServer(QueueBridge(args.queue_root))
    for line in sys.stdin:
        try:
            response = server.handle(json.loads(line))
        except (json.JSONDecodeError, AttributeError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)

if __name__ == "__main__": main()
