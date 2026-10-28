"""Build the portfolio candidate for multimodal advertising quality review."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import build_agent_v1 as base


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "workflow" / "candidate" / "AIGC-Multimodal-QA-v1.yml"
BASE_URL = "http://host.docker.internal:8000"


def _by_id(nodes: list[dict], node_id: str) -> dict:
    return next(item for item in nodes if item["id"] == node_id)


def _start_variables() -> list[dict]:
    return [
        {"default": "video", "hide": False, "hint": "选择内容类型", "label": "内容类型", "options": ["video", "image", "script"], "placeholder": "", "required": True, "type": "select", "variable": "asset_type"},
        {"allowed_file_extensions": [".MP4", ".MOV", ".WEBM"], "allowed_file_types": ["video"], "allowed_file_upload_methods": ["local_file"], "default": "", "hide": False, "hint": "video 时上传", "label": "广告视频", "options": [], "placeholder": "", "required": False, "type": "file", "variable": "video"},
        {"allowed_file_extensions": [".JPG", ".JPEG", ".PNG", ".WEBP"], "allowed_file_types": ["image"], "allowed_file_upload_methods": ["local_file"], "default": "", "hide": False, "hint": "image 时上传", "label": "广告图片", "options": [], "placeholder": "", "required": False, "type": "file", "variable": "image"},
        {"default": "", "hide": False, "hint": "script 时填写", "label": "广告脚本", "max_length": 20000, "options": [], "placeholder": "粘贴脚本", "required": False, "type": "paragraph", "variable": "script"},
        {"default": "", "hide": False, "hint": "最低业务上下文", "label": "产品信息", "max_length": 10000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "product_context"},
        {"default": "", "hide": False, "hint": "可选", "label": "目标受众", "max_length": 2000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "target_audience"},
        {"default": "", "hide": False, "hint": "可选", "label": "转化目标", "max_length": 2000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "conversion_goal"},
        {"default": "", "hide": False, "hint": "可选", "label": "补充要求", "max_length": 5000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "additional_requirements"},
    ]


def build_dsl() -> dict:
    dsl = deepcopy(base.dsl)
    graph = dsl["workflow"]["graph"]
    nodes, edges = graph["nodes"], graph["edges"]
    start = _by_id(nodes, "1900000000001")
    start["data"]["variables"], start["height"] = _start_variables(), 420

    routes = [
        base.node("2900000000001", "内容类型是视频？", "if-else", 330, 1080, base.if_data(["1900000000001", "asset_type"], "video")),
        base.node("2900000000002", "内容类型是图片？", "if-else", 630, 1080, base.if_data(["1900000000001", "asset_type"], "image")),
        base.node("2900000000003", "内容类型是脚本？", "if-else", 930, 1080, base.if_data(["1900000000001", "asset_type"], "script")),
    ]
    pending = []
    for node_id, title, y, variable in [
        ("2900000000004", "图片分支待实现", 1020, "pending_image"),
        ("2900000000005", "脚本分支待实现", 1160, "pending_script"),
        ("2900000000006", "不支持的内容类型", 1300, "invalid_asset_type"),
    ]:
        pending.append(base.node(node_id, title, "end", 1230, y, {"outputs": [{"value_selector": ["1900000000001", "asset_type"], "value_type": "string", "variable": variable}]}))
    nodes.extend(routes + pending)
    edges[:] = [item for item in edges if not (item["source"] == "1900000000001" and item["target"] == "1900000000002")]
    edges.extend([
        base.edge("1900000000001", "2900000000001", "start", "if-else"),
        base.edge("2900000000001", "1900000000002", "if-else", "http-request", "true"),
        base.edge("2900000000001", "2900000000002", "if-else", "if-else", "false"),
        base.edge("2900000000002", "2900000000004", "if-else", "end", "true"),
        base.edge("2900000000002", "2900000000003", "if-else", "if-else", "false"),
        base.edge("2900000000003", "2900000000005", "if-else", "end", "true"),
        base.edge("2900000000003", "2900000000006", "if-else", "end", "false"),
    ])

    nodes[:] = [item for item in nodes if item["id"] not in {"1900000000051", "1900000000052"}]
    edges[:] = [item for item in edges if item["source"] not in {"1900000000051", "1900000000052"} and item["target"] not in {"1900000000051", "1900000000052"}]
    convert_code = '''import json
DIMENSIONS=[("hook","开场钩子"),("product_display","商品展示"),("selling_point","核心卖点"),("audience","目标人群"),("structure","脚本结构"),("cta","行动引导")]
def main(state_json, product_context, target_audience, conversion_goal):
    state=json.loads(state_json); missing=[]
    if not str(product_context or "").strip(): missing.append("product_context")
    if not str(target_audience or "").strip(): missing.append("target_audience")
    if not str(conversion_goal or "").strip(): missing.append("conversion_goal")
    known_missing=set(state.get("missing_dimensions", [])); dimensions=[]
    for key,label in DIMENSIONS:
        partial=key in known_missing
        dimensions.append({"dimension":key,"label":label,"score":5,"max_score":10,"status":"partial" if partial else "evaluated","reason":"Agent证据不足" if partial else "已完成基础证据检查"})
    evidence=[*state.get("visual_evidence", []),*state.get("script_evidence", [])]
    summary="；".join(str(x.get("summary", "")) for x in evidence if isinstance(x,dict) and x.get("summary")) or "已完成广告视频基础质量评估。"
    payload={"asset_type":"video","profile":"ad_video_v1","summary":summary,"dimensions":dimensions,"evidence":[],"issues":[],"strengths":[],"suggestions":[],"missing_information":missing,"confidence":0.7 if state.get("visual_evidence") else 0.4,"human_review_required":bool(state.get("needs_human_review")),"human_review_reason":"Agent要求人工复核" if state.get("needs_human_review") else None,"run_summary":{"steps":int(state.get("current_step",0)),"completed_actions":state.get("completed_actions",[]),"supplementary_frames_used":bool(state.get("supplementary_rounds",0)),"retry_count":int(state.get("retry_count",0)),"stop_reason":state.get("final_status","unknown")},"technical_details":{"state_json":state}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":state}
'''
    converter = base.node("2900000000100", "转换视频评估结果", "code", 5520, 360, base.code_data(convert_code, [base.var([base.LOOP_ID, "state_json"], "state_json"), base.var(["1900000000001", "product_context"], "product_context"), base.var(["1900000000001", "target_audience"], "target_audience"), base.var(["1900000000001", "conversion_goal"], "conversion_goal")], {"evaluation_json": "string", "technical_details": "object"}))
    render_body = {"type": "json", "data": [{"id": "evaluation-json", "key": "", "type": "text", "value": "{{#2900000000100.evaluation_json#}}"}]}
    renderer = base.node("2900000000101", "渲染人类可读报告", "http-request", 5820, 360, base.http_data("post", f"{BASE_URL}/api/v1/evaluations/render", render_body))
    parse_code = '''import json
def main(body, status_code, fallback_details):
    try:
        data=json.loads(body) if isinstance(body,str) else body; result=data.get("result",{})
        return {"report_markdown":str(data.get("report_markdown","")),"evaluation_result":result,"final_status":str(result.get("status","human_review_required")),"technical_details":data.get("technical_details",fallback_details)}
    except Exception as exc:
        return {"report_markdown":"# AIGC 内容质量评估报告\\n\\n报告渲染失败，需要人工复核。","evaluation_result":{},"final_status":"human_review_required","technical_details":{"error":str(exc),"fallback":fallback_details}}
'''
    parser = base.node("2900000000102", "解析报告响应", "code", 6120, 360, base.code_data(parse_code, [base.var(["2900000000101", "body"], "body"), base.var(["2900000000101", "status_code"], "status_code", "number"), base.var(["2900000000100", "technical_details"], "fallback_details", "object")], {"report_markdown": "string", "evaluation_result": "object", "final_status": "string", "technical_details": "object"}))
    final = base.node("2900000000103", "输出多模态报告", "end", 6420, 360, {"outputs": [
        {"value_selector": ["2900000000102", "report_markdown"], "value_type": "string", "variable": "report_markdown"},
        {"value_selector": ["2900000000102", "evaluation_result"], "value_type": "object", "variable": "evaluation_result"},
        {"value_selector": ["2900000000102", "final_status"], "value_type": "string", "variable": "final_status"},
        {"value_selector": ["2900000000102", "technical_details"], "value_type": "object", "variable": "technical_details"},
    ]}, height=192)
    nodes.extend([converter, renderer, parser, final])
    edges.extend([
        base.edge("1900000000050", "2900000000100", "http-request", "code"),
        base.edge("1900000000050", "2900000000100", "http-request", "code", "fail-branch"),
        base.edge("2900000000100", "2900000000101", "code", "http-request"),
        base.edge("2900000000101", "2900000000102", "http-request", "code"),
        base.edge("2900000000102", "2900000000103", "code", "end"),
    ])
    dsl["app"].update({"name": "AIGC Multimodal Quality V1 - CANDIDATE", "description": "Portfolio candidate for advertising video, image and script quality evaluation"})
    return dsl


def main() -> None:
    OUTPUT.write_text(json.dumps(build_dsl(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
