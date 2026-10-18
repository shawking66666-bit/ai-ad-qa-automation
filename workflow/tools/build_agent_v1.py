"""Build the reviewable Dify Agent V1 DSL without reading Dify credentials."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "workflow" / "candidate" / "AI-Ad-QA-agent-v1.yml"
BASE_URL = "http://host.docker.internal:8000"
LOOP_ID = "1900000000010"
MODEL = {
    "provider": "langgenius/deepseek/deepseek",
    "name": "deepseek-flash",
    "mode": "chat",
    "completion_params": {"temperature": 0.1},
}


def node(node_id, title, node_type, x, y, data=None, parent=None, width=242, height=90):
    payload = {"title": title, "type": node_type, "selected": False}
    payload.update(data or {})
    item = {
        "data": payload,
        "height": height,
        "id": str(node_id),
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x + (900 if parent else 0), "y": y + (240 if parent else 0)},
        "sourcePosition": "right",
        "targetPosition": "left",
        "type": "custom",
        "width": width,
        "zIndex": 1002 if parent else 0,
    }
    if parent:
        item["parentId"] = parent
        payload.update({"isInLoop": True, "loop_id": parent, "isInIteration": False})
    return item


def edge(source, target, source_type, target_type, handle="source", in_loop=False):
    return {
        "data": {
            "isInIteration": False,
            "isInLoop": in_loop,
            **({"loop_id": LOOP_ID} if in_loop else {}),
            "sourceType": source_type,
            "targetType": target_type,
        },
        "id": f"{source}-{handle}-{target}-target",
        "source": str(source),
        "sourceHandle": handle,
        "target": str(target),
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 1002 if in_loop else 0,
    }


def http_data(method, url, body=None, title="HTTP"):
    return {
        "authorization": {"config": None, "type": "no-auth"},
        "body": body or {"data": [], "type": "none"},
        "headers": "Content-Type: application/json" if body and body.get("type") == "json" else "",
        "method": method,
        "params": "",
        "retry_config": {"max_retries": 1, "retry_enabled": True, "retry_interval": 1000},
        "ssl_verify": True,
        "timeout": {"connect": 10, "read": 120, "write": 120, "max_connect_timeout": 0, "max_read_timeout": 0, "max_write_timeout": 0},
        "url": url,
        "variables": [],
    }


def llm_data(system, user, schema, vision_selector=None):
    return {
        "context": {"enabled": False, "variable_selector": []},
        "model": MODEL,
        "prompt_template": [
            {"id": str(uuid4()), "role": "system", "text": system},
            {"id": str(uuid4()), "role": "user", "text": user},
        ],
        "structured_output": {"schema": schema},
        "structured_output_enabled": True,
        "vision": {
            "enabled": vision_selector is not None,
            **({"configs": {"detail": "high", "variable_selector": vision_selector}} if vision_selector else {}),
        },
    }


def code_data(code, variables, outputs):
    return {
        "code": code,
        "code_language": "python3",
        "variables": variables,
        "outputs": {name: {"children": None, "type": kind} for name, kind in outputs.items()},
    }


def var(selector, name, value_type="string"):
    return {"value_selector": selector, "value_type": value_type, "variable": name}


def if_data(selector, expected, var_type="string", operator="is"):
    return {
        "cases": [{
            "case_id": "true",
            "id": "true",
            "logical_operator": "and",
            "conditions": [{
                "comparison_operator": operator,
                "id": str(uuid4()),
                "value": expected,
                "varType": var_type,
                "variable_selector": selector,
            }],
        }]
    }


STATE_FIELDS = [
    "video_id", "duration_seconds", "current_step", "completed_actions",
    "used_timestamps", "visual_evidence", "script_evidence", "missing_dimensions",
    "errors", "retry_count", "supplementary_rounds", "needs_human_review", "final_status",
]
ACTIONS = [
    "analyze_frames", "extract_additional_frames", "check_ad_script",
    "generate_optimization_plan", "stop",
]

decision_schema = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "reason": {"type": "string"},
        "arguments": {"type": "object", "additionalProperties": True},
        "should_stop": {"type": "boolean"},
    },
    "required": ["action", "reason", "arguments", "should_stop"],
}
evidence_schema = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "missing_dimensions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["summary", "evidence", "missing_dimensions", "confidence"],
}
plan_schema = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "priority": {"type": "string"},
        "changes": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["priority", "changes", "rationale"],
}

nodes = []
edges = []

nodes.append(node("1900000000001", "用户输入", "start", 40, 360, {
    "variables": [
        {"allowed_file_extensions": [".MP4", ".MOV", ".WEBM"], "allowed_file_types": ["video"], "allowed_file_upload_methods": ["local_file"], "default": "", "hide": False, "hint": "", "label": "广告视频", "options": [], "placeholder": "", "required": True, "type": "file", "variable": "video"},
        {"default": "auto", "hide": False, "hint": "", "label": "素材类型", "max_length": 32, "options": [], "placeholder": "auto/hook/intro/show/full_ad", "required": True, "type": "text-input", "variable": "material_type"},
        {"default": "", "hide": False, "hint": "", "label": "广告文案", "max_length": 10000, "options": [], "placeholder": "可留空", "required": False, "type": "paragraph", "variable": "ad_script"},
        {"default": "", "hide": False, "hint": "", "label": "产品信息", "max_length": 10000, "options": [], "placeholder": "产品、受众和目标", "required": False, "type": "paragraph", "variable": "product_context"},
    ]
}, height=220))
nodes.append(node("1900000000002", "创建 Agent 视频任务", "http-request", 340, 360, http_data(
    "post", f"{BASE_URL}/api/v1/agent-videos",
    {"type": "form-data", "data": [{"id": "video-url", "key": "video_url", "type": "text", "value": "{{#1900000000001.video.url#}}"}]},
)))
parse_code = '''import json
def main(body, status_code):
    try:
        data = json.loads(body) if isinstance(body, str) else body
        frames = data.get("frames", []) if 200 <= int(status_code) < 300 else []
        urls = [str(x.get("url", "")) for x in frames if x.get("url")]
        state = {"video_id": str(data.get("video_id", "")), "duration_seconds": float(data.get("duration_seconds", 0)), "current_step": 0, "completed_actions": [], "used_timestamps": [float(x.get("timestamp_seconds", 0)) for x in frames], "visual_evidence": [], "script_evidence": [], "missing_dimensions": [], "errors": [], "retry_count": 0, "supplementary_rounds": 0, "needs_human_review": False, "final_status": "running"}
        return {"success": bool(urls and state["video_id"]), "error": "" if urls else str(data.get("detail", "未返回关键帧")), "video_id": state["video_id"], "frame_urls": urls, "state_json": json.dumps(state, ensure_ascii=False)}
    except Exception as exc:
        return {"success": False, "error": f"解析失败：{exc}", "video_id": "", "frame_urls": [], "state_json": "{}"}
'''
nodes.append(node("1900000000003", "解析并初始化状态", "code", 640, 360, code_data(
    parse_code,
    [var(["1900000000002", "body"], "body"), var(["1900000000002", "status_code"], "status_code", "number")],
    {"success": "boolean", "error": "string", "video_id": "string", "frame_urls": "array[string]", "state_json": "string"},
)))
nodes.append(node("1900000000004", "创建成功？", "if-else", 940, 360, if_data(["1900000000003", "success"], True, "boolean")))
nodes.append(node("1900000000005", "失败说明", "template-transform", 1240, 590, {
    "template": "Agent 视频任务创建失败：{{ error }}", "variables": [var(["1900000000003", "error"], "error")]
}))
nodes.append(node("1900000000006", "失败输出", "end", 1540, 590, {
    "outputs": [{"value_selector": ["1900000000005", "output"], "value_type": "string", "variable": "result"}]
}))
nodes.append(node("1900000000007", "下载初始关键帧", "iteration", 1240, 260, {
    "error_handle_mode": "terminated", "flatten_output": True, "is_parallel": True,
    "iterator_input_type": "array[string]", "iterator_selector": ["1900000000003", "frame_urls"],
    "output_selector": ["1900000000009", "files"], "output_type": "array[file]", "parallel_nums": 3,
    "start_node_id": "1900000000008", "width": 520, "height": 210,
}, width=520, height=210))
start_iteration = node("1900000000008", "", "iteration-start", 24, 68, {"desc": "", "isInIteration": True}, parent=None, width=44, height=48)
start_iteration.update({"parentId": "1900000000007", "type": "custom-iteration-start", "draggable": False, "selectable": False, "zIndex": 1001})
nodes.append(start_iteration)
download = http_data("get", "{{#1900000000007.item#}}")
download.update({"isInIteration": True, "isInLoop": False, "iteration_id": "1900000000007"})
download_node = node("1900000000009", "下载单张关键帧", "http-request", 128, 68, download, width=242, height=125)
download_node.update({"parentId": "1900000000007", "zIndex": 1001})
nodes.append(download_node)

loop_data = {
    "break_conditions": [{"comparison_operator": "is not", "id": str(uuid4()), "value": "running", "varType": "string", "variable_selector": [LOOP_ID, "final_status"]}],
    "error_handle_mode": "terminated", "logical_operator": "and", "loop_count": 5,
    "loop_variables": [
        {"id": str(uuid4()), "label": "state_json", "value": ["1900000000003", "state_json"], "value_type": "variable", "var_type": "string"},
        {"id": str(uuid4()), "label": "final_status", "value": "running", "value_type": "constant", "var_type": "string"},
    ],
    "start_node_id": f"{LOOP_ID}start", "width": 3300, "height": 850,
}
nodes.append(node(LOOP_ID, "受控 Agent 循环", "loop", 1840, 150, loop_data, width=3300, height=850))
loop_start = node(f"{LOOP_ID}start", "", "loop-start", 24, 70, {"desc": "", "isInLoop": True}, width=44, height=48)
loop_start.update({"parentId": LOOP_ID, "type": "custom-loop-start", "draggable": False, "selectable": False, "zIndex": 1002})
nodes.append(loop_start)

decision_prompt = f'''你是广告分析流程的控制器。只选择下一步动作，不直接写最终报告。
允许动作：{", ".join(ACTIONS)}。
硬规则：最多一次补帧；视觉分析最多两次；文案检查和优化方案最多一次；final_status 非 running 时必须 stop；未知或不安全情况 stop 并 should_stop=true。'''
nodes.append(node("1900000000011", "Agent 决策", "llm", 120, 70, llm_data(
    decision_prompt,
    "当前状态：{{#1900000000010.state_json#}}\n广告文案：{{#1900000000001.ad_script#}}\n产品信息：{{#1900000000001.product_context#}}",
    decision_schema,
), parent=LOOP_ID))
guard_code = '''import json
ALLOWED={"analyze_frames","extract_additional_frames","check_ad_script","generate_optimization_plan","stop"}
def main(state_json, decision):
    state=json.loads(state_json); action=str((decision or {}).get("action", "stop"))
    completed=state.get("completed_actions", [])
    invalid=(action not in ALLOWED or state.get("final_status") != "running" or (action=="extract_additional_frames" and state.get("supplementary_rounds",0)>=1) or (action=="analyze_frames" and completed.count("analyze_frames")>=2) or (action=="check_ad_script" and "check_ad_script" in completed) or (action=="generate_optimization_plan" and "generate_optimization_plan" in completed))
    if invalid: action="stop"; state["needs_human_review"]=True; state["errors"].append("决策被确定性守卫拒绝")
    state["current_step"]=int(state.get("current_step",0))+1
    return {"action": action, "state_json": json.dumps(state,ensure_ascii=False), "timestamps_json": json.dumps((decision or {}).get("arguments",{}).get("timestamps",[]),ensure_ascii=False)}
'''
nodes.append(node("1900000000012", "校验决策与守卫", "code", 430, 70, code_data(
    guard_code,
    [var([LOOP_ID, "state_json"], "state_json"), var(["1900000000011", "structured_output"], "decision", "object")],
    {"action": "string", "state_json": "string", "timestamps_json": "string"},
), parent=LOOP_ID))

route_ids = {
    "analyze_frames": "1900000000013",
    "check_ad_script": "1900000000014",
    "extract_additional_frames": "1900000000015",
    "generate_optimization_plan": "1900000000016",
}
for index, (action, route_id) in enumerate(route_ids.items()):
    nodes.append(node(route_id, f"动作？{action}", "if-else", 730 + index * 300, 70 + index * 135, if_data(["1900000000012", "action"], action), parent=LOOP_ID))

nodes.append(node("1900000000020", "分析关键帧", "llm", 1050, 20, llm_data(
    "只根据输入关键帧提取广告视觉证据；不猜测音频、转场或未出现内容。",
    "素材类型：{{#1900000000001.material_type#}}\n当前状态：{{#1900000000012.state_json#}}",
    evidence_schema, ["1900000000007", "output"],
), parent=LOOP_ID))
nodes.append(node("1900000000021", "检查广告文案", "llm", 1350, 160, llm_data(
    "检查广告文案是否清晰、可信、与产品信息一致；不得编造事实。",
    "广告文案：{{#1900000000001.ad_script#}}\n产品信息：{{#1900000000001.product_context#}}",
    evidence_schema,
), parent=LOOP_ID))
supplement_body = {"type": "json", "data": [{"id": "supplement-json", "key": "", "type": "text", "value": "{\"timestamps\": {{#1900000000012.timestamps_json#}}}"}]}
nodes.append(node("1900000000022", "提取补充关键帧", "http-request", 1650, 300, http_data(
    "post", f"{BASE_URL}/api/v1/agent-videos/{{{{#1900000000003.video_id#}}}}/frames", supplement_body,
), parent=LOOP_ID))
nodes.append(node("1900000000023", "生成优化方案", "llm", 1950, 430, llm_data(
    "根据已有状态生成可执行的广告素材优化方案；证据不足时明确标注，不得杜撰。",
    "当前状态：{{#1900000000012.state_json#}}\n产品信息：{{#1900000000001.product_context#}}",
    plan_schema,
), parent=LOOP_ID))

update_code = '''import json
def main(state_json, action, result):
    state=json.loads(state_json); completed=state.setdefault("completed_actions", [])
    if action not in completed or action=="analyze_frames": completed.append(action)
    if action=="analyze_frames": state["visual_evidence"].append(result)
    elif action=="check_ad_script": state["script_evidence"].append(result)
    elif action=="extract_additional_frames": state["supplementary_rounds"]=1
    elif action=="generate_optimization_plan": state["optimization_plan"]=result
    if action=="stop" or ("analyze_frames" in completed and "generate_optimization_plan" in completed):
        state["final_status"]="human_review_required" if state.get("needs_human_review") else ("partial" if state.get("errors") else "completed")
    return {"state_json":json.dumps(state,ensure_ascii=False),"final_status":state.get("final_status","running")}
'''
action_results = {
    "1900000000020": ("analyze_frames", ["1900000000020", "structured_output"]),
    "1900000000021": ("check_ad_script", ["1900000000021", "structured_output"]),
    "1900000000022": ("extract_additional_frames", ["1900000000022", "body"]),
    "1900000000023": ("generate_optimization_plan", ["1900000000023", "structured_output"]),
}
for idx, (source_id, (action, result_selector)) in enumerate(action_results.items(), start=30):
    update_id, assign_id = f"19000000000{idx}", f"19000000000{idx+10}"
    nodes.append(node(update_id, f"合并 {action} 结果", "code", 2300, 20 + (idx-30)*160, code_data(
        update_code,
        [var(["1900000000012", "state_json"], "state_json"), {"variable": "action", "value_selector": ["1900000000012", "action"], "value_type": "string"}, var(result_selector, "result", "object" if "structured_output" in result_selector else "string")],
        {"state_json": "string", "final_status": "string"},
    ), parent=LOOP_ID))
    nodes.append(node(assign_id, f"写回 {action} 状态", "assigner", 2600, 20 + (idx-30)*160, {
        "version": "2",
        "items": [
            {"input_type": "variable", "operation": "over-write", "value": [update_id, "state_json"], "variable_selector": [LOOP_ID, "state_json"], "write_mode": "over-write"},
            {"input_type": "variable", "operation": "over-write", "value": [update_id, "final_status"], "variable_selector": [LOOP_ID, "final_status"], "write_mode": "over-write"},
        ]
    }, parent=LOOP_ID))
    edges.append(edge(source_id, update_id, nodes[[n["id"] for n in nodes].index(source_id)]["data"]["type"], "code", in_loop=True))
    edges.append(edge(update_id, assign_id, "code", "assigner", in_loop=True))

nodes.append(node("1900000000024", "停止并确定状态", "code", 2250, 700, code_data(
    update_code,
    [var(["1900000000012", "state_json"], "state_json"), {"variable": "action", "value_selector": ["1900000000012", "action"], "value_type": "string"}, {"variable": "result", "value_selector": ["1900000000011", "structured_output"], "value_type": "object"}],
    {"state_json": "string", "final_status": "string"},
), parent=LOOP_ID))
nodes.append(node("1900000000044", "写回停止状态", "assigner", 2600, 700, {
    "version": "2",
    "items": [
        {"input_type": "variable", "operation": "over-write", "value": ["1900000000024", "state_json"], "variable_selector": [LOOP_ID, "state_json"], "write_mode": "over-write"},
        {"input_type": "variable", "operation": "over-write", "value": ["1900000000024", "final_status"], "variable_selector": [LOOP_ID, "final_status"], "write_mode": "over-write"},
    ]
}, parent=LOOP_ID))

nodes.append(node("1900000000050", "清理 Agent 视频任务", "http-request", 5220, 360, {
    **http_data("delete", f"{BASE_URL}/api/v1/agent-videos/{{{{#1900000000003.video_id#}}}}"),
    "error_strategy": "fail-branch",
}))
nodes.append(node("1900000000051", "生成最终报告", "template-transform", 5520, 360, {
    "template": "# AI 广告素材 Agent 报告\n\n状态：{{ final_status }}\n\n> 技术链路已验证，真实广告质量待人工复核。\n\n## Agent 状态与证据\n\n```json\n{{ state_json }}\n```",
    "variables": [var([LOOP_ID, "final_status"], "final_status"), var([LOOP_ID, "state_json"], "state_json")],
}))
nodes.append(node("1900000000052", "输出报告", "end", 5820, 360, {
    "outputs": [
        {"value_selector": ["1900000000051", "output"], "value_type": "string", "variable": "report"},
        {"value_selector": [LOOP_ID, "final_status"], "value_type": "string", "variable": "final_status"},
    ]
}))

edges.extend([
    edge("1900000000001", "1900000000002", "start", "http-request"),
    edge("1900000000002", "1900000000003", "http-request", "code"),
    edge("1900000000003", "1900000000004", "code", "if-else"),
    edge("1900000000004", "1900000000007", "if-else", "iteration", "true"),
    edge("1900000000004", "1900000000005", "if-else", "template-transform", "false"),
    edge("1900000000005", "1900000000006", "template-transform", "end"),
    edge("1900000000008", "1900000000009", "iteration-start", "http-request"),
    edge("1900000000007", LOOP_ID, "iteration", "loop"),
    edge(f"{LOOP_ID}start", "1900000000011", "loop-start", "llm", in_loop=True),
    edge("1900000000011", "1900000000012", "llm", "code", in_loop=True),
    edge("1900000000012", "1900000000013", "code", "if-else", in_loop=True),
    edge("1900000000013", "1900000000020", "if-else", "llm", "true", True),
    edge("1900000000013", "1900000000014", "if-else", "if-else", "false", True),
    edge("1900000000014", "1900000000021", "if-else", "llm", "true", True),
    edge("1900000000014", "1900000000015", "if-else", "if-else", "false", True),
    edge("1900000000015", "1900000000022", "if-else", "http-request", "true", True),
    edge("1900000000015", "1900000000016", "if-else", "if-else", "false", True),
    edge("1900000000016", "1900000000023", "if-else", "llm", "true", True),
    edge("1900000000016", "1900000000024", "if-else", "code", "false", True),
    edge("1900000000024", "1900000000044", "code", "assigner", in_loop=True),
    edge(LOOP_ID, "1900000000050", "loop", "http-request"),
    edge("1900000000050", "1900000000051", "http-request", "template-transform"),
    edge("1900000000050", "1900000000051", "http-request", "template-transform", "fail-branch"),
    edge("1900000000051", "1900000000052", "template-transform", "end"),
])

dsl = {
    "app": {"description": "Dify 1.15 controlled advertising-analysis Agent V1 candidate", "icon": "🤖", "icon_background": "#E4FBCC", "icon_type": "emoji", "mode": "workflow", "name": "AI-Ad-QA Agent V1 - CANDIDATE", "use_icon_as_answer_icon": False},
    "dependencies": [{"current_identifier": None, "type": "marketplace", "value": {"marketplace_plugin_unique_identifier": "langgenius/deepseek:0.0.24@9e12eef09973667f0eaf4f082af883167e1de88740b22e71e71488d020c3778a", "version": None}}],
    "kind": "app", "version": "0.6.0",
    "workflow": {
        "conversation_variables": [], "environment_variables": [],
        "features": {"file_upload": {"enabled": False}, "opening_statement": "", "retriever_resource": {"enabled": True}, "sensitive_word_avoidance": {"enabled": False}, "speech_to_text": {"enabled": False}, "suggested_questions": [], "suggested_questions_after_answer": {"enabled": False}, "text_to_speech": {"enabled": False, "language": "", "voice": ""}},
        "graph": {"edges": edges, "nodes": nodes, "viewport": {"x": -120, "y": 20, "zoom": 0.55}},
        "rag_pipeline_variables": [],
    },
}


if __name__ == "__main__":
    # JSON is valid YAML 1.2 and keeps this generator standard-library only.
    OUTPUT.write_text(json.dumps(dsl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)
