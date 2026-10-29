"""Build the portfolio candidate for multimodal advertising quality review."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5

import build_agent_v1 as base


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "workflow" / "candidate" / "AIGC-Multimodal-QA-v1.yml"
BASE_URL = "http://host.docker.internal:8000"
UUID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")


def _by_id(nodes: list[dict], node_id: str) -> dict:
    return next(item for item in nodes if item["id"] == node_id)


def _start_variables() -> list[dict]:
    return [
        {"default": "video", "hide": False, "hint": "选择内容类型", "label": "内容类型", "options": ["video", "image", "script"], "placeholder": "", "required": True, "type": "select", "variable": "asset_type"},
        {"allowed_file_extensions": [".MP4", ".MOV"], "allowed_file_types": ["video"], "allowed_file_upload_methods": ["local_file"], "default": "", "hide": False, "hint": "video 时上传", "label": "广告视频", "options": [], "placeholder": "", "required": False, "type": "file", "variable": "video"},
        {"allowed_file_extensions": [".JPG", ".JPEG", ".PNG", ".WEBP"], "allowed_file_types": ["image"], "allowed_file_upload_methods": ["local_file"], "default": "", "hide": False, "hint": "image 时上传", "label": "广告图片", "options": [], "placeholder": "", "required": False, "type": "file", "variable": "image"},
        {"default": "", "hide": False, "hint": "script 时填写", "label": "广告脚本", "max_length": 20000, "options": [], "placeholder": "粘贴脚本", "required": False, "type": "paragraph", "variable": "script"},
        {"default": "", "hide": False, "hint": "最低业务上下文", "label": "产品信息", "max_length": 10000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "product_context"},
        {"default": "", "hide": False, "hint": "可选", "label": "目标受众", "max_length": 2000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "target_audience"},
        {"default": "", "hide": False, "hint": "可选", "label": "转化目标", "max_length": 2000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "conversion_goal"},
        {"default": "", "hide": False, "hint": "可选", "label": "补充要求", "max_length": 5000, "options": [], "placeholder": "", "required": False, "type": "paragraph", "variable": "additional_requirements"},
    ]


def _stabilize_uuid_values(value, path: str = "root"):
    if isinstance(value, dict):
        return {key: _stabilize_uuid_values(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_stabilize_uuid_values(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, str) and UUID_PATTERN.fullmatch(value):
        return str(uuid5(NAMESPACE_URL, f"ai-ad-qa-multimodal-v1:{path}"))
    return value


def _migrate_inherited_start_references(value):
    if isinstance(value, dict):
        return {key: _migrate_inherited_start_references(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_migrate_inherited_start_references(item) for item in value]
    if isinstance(value, str):
        return value.replace("1900000000001.ad_script#}}", "1900000000001.script#}}").replace(
            "1900000000001.material_type#}}", "1900000000001.asset_type#}}"
        )
    return value


def _report_parser_code(asset_type: str, profile: str, heading: str) -> str:
    return f'''import json
def main(body, status_code, fallback_details):
    try:
        if int(status_code)!=200: raise ValueError(f"renderer status={{status_code}}")
        data=json.loads(body) if isinstance(body,str) else body; result=data.get("result",{{}})
        if not data.get("report_markdown") or not result: raise ValueError("empty renderer response")
        return {{"report_markdown":data["report_markdown"],"evaluation_result":result,"final_status":str(result.get("status","human_review_required")),"technical_details":data.get("technical_details",fallback_details)}}
    except Exception as exc:
        result={{"asset_type":"{asset_type}","profile":"{profile}","status":"human_review_required","overall_score":0,"summary":"报告渲染失败，需要人工复核。","dimensions":[],"evidence":[],"issues":[],"strengths":[],"suggestions":[],"missing_information":["rendered_report"],"confidence":0.0,"human_review_required":True,"human_review_reason":"报告渲染失败","run_summary":{{"steps":0,"completed_actions":[],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"renderer_failed"}}}}
        return {{"report_markdown":"# {heading}\\n\\n报告渲染失败，需要人工复核。","evaluation_result":result,"final_status":"human_review_required","technical_details":{{"error":str(exc),"fallback":fallback_details}}}}
'''


def _model_fallback_code(asset_type: str, profile: str, heading: str) -> str:
    return f'''def main():
    result={{"asset_type":"{asset_type}","profile":"{profile}","status":"human_review_required","overall_score":0,"summary":"模型分析或结构化处理失败，需要人工复核。","dimensions":[],"evidence":[],"issues":[],"strengths":[],"suggestions":[],"missing_information":["model_evaluation"],"confidence":0.0,"human_review_required":True,"human_review_reason":"模型分析或结构化处理失败","run_summary":{{"steps":0,"completed_actions":[],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"model_or_normalizer_failed"}}}}
    return {{"report_markdown":"# {heading}\\n\\n模型分析或结构化处理失败，需要人工复核。","evaluation_result":result,"final_status":"human_review_required","technical_details":{{"failure_stage":"model_or_normalizer"}}}}
'''


def _converge_report_ends(nodes: list[dict], edges: list[dict]) -> None:
    """Give Dify one public report End while preserving exclusive branch results."""
    report_end_ids = [
        "2900000000103",  # video
        "2900000000204",  # image
        "2900000000206",  # image model fallback
        "2900000000306",  # script
        "2900000000308",  # script model fallback
    ]
    fields = ["report_markdown", "evaluation_result", "final_status", "technical_details"]
    kinds = {"report_markdown": "string", "evaluation_result": "object", "final_status": "string", "technical_details": "object"}
    pack_code = '''def main(report_markdown, evaluation_result, final_status, technical_details):
    return {"report_bundle": {"report_markdown": report_markdown, "evaluation_result": evaluation_result, "final_status": final_status, "technical_details": technical_details}}
'''
    packers = []
    for index, end_id in enumerate(report_end_ids, 1):
        old_end = _by_id(nodes, end_id)
        old_outputs = {item["variable"]: item for item in old_end["data"]["outputs"]}
        if set(old_outputs) != set(fields):
            raise ValueError(f"Unexpected report outputs on {end_id}")
        incoming = [item for item in edges if item["target"] == end_id]
        if len(incoming) != 1:
            raise ValueError(f"Expected one incoming report edge on {end_id}")
        source_edge = incoming[0]
        packer_id = f"390000000000{index}"
        packers.append(packer_id)
        packer = base.node(
            packer_id,
            f"打包报告分支 {index}",
            "code",
            old_end["position"]["x"],
            old_end["position"]["y"],
            base.code_data(
                pack_code,
                [base.var(old_outputs[name]["value_selector"], name, kinds[name]) for name in fields],
                {"report_bundle": "object"},
            ),
            height=120,
        )
        nodes.append(packer)
        edges.remove(source_edge)
        edges.append(base.edge(source_edge["source"], packer_id, source_edge["data"]["sourceType"], "code", source_edge["sourceHandle"]))

    nodes[:] = [item for item in nodes if item["id"] not in report_end_ids]
    aggregator_id = "3900000000010"
    unpack_id = "3900000000011"
    nodes.append(base.node(
        aggregator_id, "汇聚报告分支", "variable-aggregator", 6750, 700,
        {"output_type": "object", "variables": [[item, "report_bundle"] for item in packers]},
        height=160,
    ))
    unpack_code = '''def main(report_bundle):
    required = ("report_markdown", "evaluation_result", "final_status", "technical_details")
    if not isinstance(report_bundle, dict) or any(key not in report_bundle for key in required):
        raise ValueError("Incomplete report bundle")
    return {key: report_bundle[key] for key in required}
'''
    nodes.append(base.node(
        unpack_id, "拆分统一报告", "code", 7050, 700,
        base.code_data(unpack_code, [base.var([aggregator_id, "output"], "report_bundle", "object")], kinds),
        height=120,
    ))
    nodes.append(base.node(
        report_end_ids[0], "输出多模态报告", "end", 7350, 700,
        {"outputs": [
            {"value_selector": [unpack_id, name], "value_type": kinds[name], "variable": name}
            for name in fields
        ]},
        height=192,
    ))
    edges.extend(base.edge(item, aggregator_id, "code", "variable-aggregator") for item in packers)
    edges.append(base.edge(aggregator_id, unpack_id, "variable-aggregator", "code"))
    edges.append(base.edge(unpack_id, report_end_ids[0], "code", "end"))


def build_dsl() -> dict:
    dsl = _migrate_inherited_start_references(deepcopy(base.dsl))
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
    analyses=[*(state.get("visual_evidence") or []),*(state.get("script_evidence") or [])]
    known_missing=set(state.get("missing_dimensions", []))
    for analysis in analyses:
        if isinstance(analysis,dict): known_missing.update(analysis.get("missing_dimensions",[]) or [])
    dimensions=[]
    for key,label in DIMENSIONS:
        reason="Agent 当前只返回证据，未提供该维度的结构化评分"
        if key in known_missing: reason="Agent 明确报告该维度证据不足"
        dimensions.append({"dimension":key,"label":label,"score":0,"max_score":10,"status":"partial","reason":reason})
    evidence=[]
    for group_index,analysis in enumerate(analyses):
        if not isinstance(analysis,dict): continue
        source_type="video_frame" if group_index < len(state.get("visual_evidence") or []) else "text_span"
        for finding in analysis.get("evidence",[]) or []:
            if not str(finding).strip(): continue
            evidence.append({"id":f"video-{len(evidence)+1}","source_type":source_type,"location":f"Agent分析{group_index+1}","dimension":"overall","finding":str(finding),"confidence":float(analysis.get("confidence",0))})
    evidence_ids=[item["id"] for item in evidence]
    issues=[]
    changes=(state.get("optimization_plan") or {}).get("changes",[]) if isinstance(state.get("optimization_plan"),dict) else []
    suggestions=[{"priority":"P1" if i<2 else "P2","action":str(change),"expected_effect":"提升广告内容表达质量","evidence_refs":evidence_ids} for i,change in enumerate(changes) if str(change).strip()]
    summary="；".join(str(x.get("summary", "")) for x in analyses if isinstance(x,dict) and x.get("summary")) or "视频 Agent 未返回足够的结构化评估证据。"
    confidence=min([float(x.get("confidence",0)) for x in analyses if isinstance(x,dict)] or [0.0])
    review=True
    payload={"asset_type":"video","profile":"ad_video_v1","summary":summary,"dimensions":dimensions,"evidence":evidence,"issues":issues,"strengths":[],"suggestions":suggestions,"missing_information":missing+sorted(known_missing),"confidence":confidence,"human_review_required":review,"human_review_reason":"当前视频 Agent 未输出可验证的逐维度数值评分，需人工复核","run_summary":{"steps":int(state.get("current_step",0)),"completed_actions":state.get("completed_actions",[]),"supplementary_frames_used":bool(state.get("supplementary_rounds",0)),"retry_count":int(state.get("retry_count",0)),"stop_reason":state.get("final_status","unknown")},"technical_details":{"state_json":state}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":state}
'''
    converter = base.node("2900000000100", "转换视频评估结果", "code", 5520, 360, base.code_data(convert_code, [base.var([base.LOOP_ID, "state_json"], "state_json"), base.var(["1900000000001", "product_context"], "product_context"), base.var(["1900000000001", "target_audience"], "target_audience"), base.var(["1900000000001", "conversion_goal"], "conversion_goal")], {"evaluation_json": "string", "technical_details": "object"}))
    render_body = {"type": "json", "data": [{"id": "evaluation-json", "key": "", "type": "text", "value": "{{#2900000000100.evaluation_json#}}"}]}
    renderer = base.node("2900000000101", "渲染人类可读报告", "http-request", 5820, 360, base.http_data("post", f"{BASE_URL}/api/v1/evaluations/render", render_body))
    parse_code = _report_parser_code("video", "ad_video_v1", "AIGC 视频质量评估报告")
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

    # Image uses one bounded vision call: evidence and scores are produced together,
    # then normalized through the same renderer contract as the video branch.
    image_dimensions = ["subject", "composition", "readability", "selling_point", "audience", "cta", "risk"]
    image_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "dimensions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
                "dimension": {"type": "string", "enum": image_dimensions}, "score": {"type": "number", "minimum": 0, "maximum": 10}, "reason": {"type": "string"},
            }, "required": ["dimension", "score", "reason"]}},
            "evidence": {"type": "array", "items": {"type":"object","additionalProperties":False,"properties":{"dimension":{"type":"string","enum":image_dimensions},"finding":{"type":"string"}},"required":["dimension","finding"]}},
            "issues": {"type": "array", "items": {"type": "string"}},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "suggestions": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["summary", "dimensions", "evidence", "issues", "strengths", "suggestions", "confidence"],
    }
    image_llm = base.node("2900000000200", "评估广告图片", "llm", 1230, 920, base.llm_data(
        "你是广告图片质量审核员。只根据实际图片和用户提供的上下文判断，不得猜测不可见信息。逐项评估 subject、composition、readability、selling_point、audience、cta、risk；证据必须是人能在图中复核的具体描述。",
        "profile: ad_image_v1\n产品信息：{{#1900000000001.product_context#}}\n目标受众：{{#1900000000001.target_audience#}}\n转化目标：{{#1900000000001.conversion_goal#}}\n补充要求：{{#1900000000001.additional_requirements#}}",
        image_schema, ["1900000000001", "image"],
    ), height=120)
    image_llm["data"]["error_strategy"] = "fail-branch"
    image_normalize_code = '''import json
LABELS={"subject":"主体呈现","composition":"画面构图","readability":"文字可读性","selling_point":"卖点表达","audience":"受众匹配","cta":"行动引导","risk":"内容风险"}
def main(analysis, product_context, target_audience, conversion_goal):
    missing=[]
    for key,value in (("product_context",product_context),("target_audience",target_audience),("conversion_goal",conversion_goal)):
        if not str(value or "").strip(): missing.append(key)
    dims=[]
    seen=set()
    for item in analysis.get("dimensions",[]):
        key=item.get("dimension")
        if key in LABELS and key not in seen:
            seen.add(key); dims.append({"dimension":key,"label":LABELS[key],"score":item.get("score",0),"max_score":10,"status":"evaluated","reason":item.get("reason","")})
    for key,label in LABELS.items():
        if key not in seen: dims.append({"dimension":key,"label":label,"score":0,"max_score":10,"status":"partial","reason":"模型未返回该维度，需人工复核"})
    evidence=[{"id":f"img-{i+1}","source_type":"image","location":"image:1","dimension":item.get("dimension","overall"),"finding":item.get("finding",""),"confidence":analysis.get("confidence",0)} for i,item in enumerate(analysis.get("evidence",[])) if item.get("finding")]
    evidence_ids=[item["id"] for item in evidence]
    unsupported_findings=not evidence_ids and bool((analysis.get("issues") or [])+(analysis.get("suggestions") or []))
    if unsupported_findings: missing.append("issue_evidence")
    issues=[{"priority":"P1","dimension":"overall","problem":text,"impact":"可能降低广告信息传达效果","evidence_refs":evidence_ids,"suggestion":"根据问题调整画面后复核"} for text in analysis.get("issues",[]) if evidence_ids]
    suggestions=[{"priority":"P1" if i<2 else "P2","action":text,"expected_effect":"提升广告信息传达质量","evidence_refs":evidence_ids} for i,text in enumerate(analysis.get("suggestions",[])) if evidence_ids]
    confidence=float(analysis.get("confidence",0)); incomplete=any(x["status"]=="partial" for x in dims)
    review=incomplete or confidence<0.6 or unsupported_findings
    reason="模型返回的问题或建议缺少可引用证据" if unsupported_findings else ("评分维度缺失或模型置信度偏低" if review else None)
    summary=(analysis.get("summary","") or "图片评估需要人工复核。")+("；模型返回的问题缺少证据，已转人工复核。" if unsupported_findings else "")
    payload={"asset_type":"image","profile":"ad_image_v1","summary":summary,"dimensions":dims,"evidence":evidence,"issues":issues,"strengths":analysis.get("strengths",[]),"suggestions":suggestions,"missing_information":missing,"confidence":confidence,"human_review_required":review,"human_review_reason":reason,"run_summary":{"steps":1,"completed_actions":["single_vision_review"],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"single_pass_completed"},"technical_details":{"vision_call":"single_pass"}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":{"vision_call":"single_pass","raw_analysis":analysis}}
'''
    image_normalizer = base.node("2900000000201", "规范化图片评估", "code", 1530, 920, base.code_data(image_normalize_code, [
        base.var(["2900000000200", "structured_output"], "analysis", "object"), base.var(["1900000000001", "product_context"], "product_context"), base.var(["1900000000001", "target_audience"], "target_audience"), base.var(["1900000000001", "conversion_goal"], "conversion_goal")
    ], {"evaluation_json":"string","technical_details":"object"}), height=120)
    image_normalizer["data"]["error_strategy"] = "fail-branch"
    image_body = {"type":"json","data":[{"id":"image-evaluation-json","key":"","type":"text","value":"{{#2900000000201.evaluation_json#}}"}]}
    image_renderer = base.node("2900000000202", "渲染图片报告", "http-request", 1830, 920, base.http_data("post", f"{BASE_URL}/api/v1/evaluations/render", image_body))
    image_parse_code = _report_parser_code("image", "ad_image_v1", "AIGC 图片质量评估报告")
    image_parser = base.node("2900000000203", "解析图片报告", "code", 2130, 920, base.code_data(image_parse_code, [base.var(["2900000000202","body"],"body"),base.var(["2900000000202","status_code"],"status_code","number"),base.var(["2900000000201","technical_details"],"fallback_details","object")], {"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"}), height=120)
    image_end = base.node("2900000000204", "输出图片报告", "end", 2430, 920, {"outputs":[
        {"value_selector":["2900000000203","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000203","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000203","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000203","technical_details"],"value_type":"object","variable":"technical_details"},
    ]}, height=192)
    image_fallback = base.node("2900000000205", "图片分析失败转人工复核", "code", 1830, 1040, base.code_data(
        _model_fallback_code("image", "ad_image_v1", "AIGC 图片质量评估报告"), [],
        {"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"},
    ), height=120)
    image_fallback_end = base.node("2900000000206", "输出图片人工复核结果", "end", 2130, 1040, {"outputs":[
        {"value_selector":["2900000000205","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000205","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000205","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000205","technical_details"],"value_type":"object","variable":"technical_details"},
    ]}, height=192)
    nodes[:] = [item for item in nodes if item["id"] != "2900000000004"]
    edges[:] = [item for item in edges if item["target"] != "2900000000004"]
    nodes.extend([image_llm,image_normalizer,image_renderer,image_parser,image_end,image_fallback,image_fallback_end])
    edges.extend([base.edge("2900000000002","2900000000200","if-else","llm","true"),base.edge("2900000000200","2900000000201","llm","code"),base.edge("2900000000200","2900000000205","llm","code","fail-branch"),base.edge("2900000000201","2900000000202","code","http-request"),base.edge("2900000000201","2900000000205","code","code","fail-branch"),base.edge("2900000000202","2900000000203","http-request","code"),base.edge("2900000000202","2900000000203","http-request","code","fail-branch"),base.edge("2900000000203","2900000000204","code","end"),base.edge("2900000000205","2900000000206","code","end")])

    script_dimensions = ["hook", "pain_point", "selling_point", "audience", "structure", "cta", "claim_risk"]
    script_schema = {
        "type":"object","additionalProperties":False,"properties":{
            "summary":{"type":"string"},
            "dimensions":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"dimension":{"type":"string","enum":script_dimensions},"score":{"type":"number","minimum":0,"maximum":10},"reason":{"type":"string"}},"required":["dimension","score","reason"]}},
            "evidence":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"location":{"type":"string","description":"段落编号或场景编号"},"dimension":{"type":"string","enum":script_dimensions},"finding":{"type":"string"}},"required":["location","dimension","finding"]}},
            "issues":{"type":"array","items":{"type":"string"}},"strengths":{"type":"array","items":{"type":"string"}},"suggestions":{"type":"array","items":{"type":"string"}},"confidence":{"type":"number","minimum":0,"maximum":1},
        },"required":["summary","dimensions","evidence","issues","strengths","suggestions","confidence"],
    }
    script_precheck_code='''def main(script):
    normalized=str(script or "").strip()
    return {"has_script":bool(normalized),"normalized_script":normalized}
'''
    script_precheck=base.node("2900000000299","脚本输入预检","code",1230,1160,base.code_data(script_precheck_code,[base.var(["1900000000001","script"],"script")],{"has_script":"boolean","normalized_script":"string"}))
    script_validator = base.node("2900000000300","脚本非空？","if-else",1530,1160,base.if_data(["2900000000299","has_script"],True,"boolean","is"))
    empty_script = base.node("2900000000301","拒绝空脚本","end",1530,1280,{"outputs":[
        {"value_selector":["2900000000299","normalized_script"],"value_type":"string","variable":"invalid_script"},
    ]})
    script_llm = base.node("2900000000302","评估广告脚本","llm",1530,1100,base.llm_data(
        "你是广告脚本质量审核员。只根据原文和提供的业务上下文判断，不得补写原文没有的事实。逐项评估 hook、pain_point、selling_point、audience、structure、cta、claim_risk。每条证据必须使用段落编号或场景编号作为 location，便于人工回看。",
        "profile: ad_script_v1\n脚本原文：{{#2900000000299.normalized_script#}}\n产品信息：{{#1900000000001.product_context#}}\n目标受众：{{#1900000000001.target_audience#}}\n转化目标：{{#1900000000001.conversion_goal#}}\n补充要求：{{#1900000000001.additional_requirements#}}",
        script_schema,
    ),height=120)
    script_llm["data"]["error_strategy"] = "fail-branch"
    script_normalize_code='''import json
LABELS={"hook":"开场钩子","pain_point":"痛点表达","selling_point":"卖点表达","audience":"受众匹配","structure":"脚本结构","cta":"行动引导","claim_risk":"宣称风险"}
def main(analysis, product_context, target_audience, conversion_goal):
    missing=[]
    for key,value in (("product_context",product_context),("target_audience",target_audience),("conversion_goal",conversion_goal)):
        if not str(value or "").strip(): missing.append(key)
    dims=[]; seen=set()
    for item in analysis.get("dimensions",[]):
        key=item.get("dimension")
        if key in LABELS and key not in seen:
            seen.add(key); dims.append({"dimension":key,"label":LABELS[key],"score":item.get("score",0),"max_score":10,"status":"evaluated","reason":item.get("reason","")})
    for key,label in LABELS.items():
        if key not in seen: dims.append({"dimension":key,"label":label,"score":0,"max_score":10,"status":"partial","reason":"模型未返回该维度，需人工复核"})
    evidence=[]
    for i,item in enumerate(analysis.get("evidence",[])):
        if item.get("finding"): evidence.append({"id":f"script-{i+1}","source_type":"text_span","location":str(item.get("location","未定位")),"dimension":str(item.get("dimension","overall")),"finding":str(item.get("finding","")),"confidence":analysis.get("confidence",0)})
    evidence_ids=[item["id"] for item in evidence]
    unsupported_findings=not evidence_ids and bool((analysis.get("issues") or [])+(analysis.get("suggestions") or []))
    if unsupported_findings: missing.append("issue_evidence")
    issues=[{"priority":"P1","dimension":"overall","problem":text,"impact":"可能降低脚本表达或转化效果","evidence_refs":evidence_ids,"suggestion":"根据问题改写对应段落后复核"} for text in analysis.get("issues",[]) if evidence_ids]
    suggestions=[{"priority":"P1" if i<2 else "P2","action":text,"expected_effect":"提升脚本表达与转化清晰度","evidence_refs":evidence_ids} for i,text in enumerate(analysis.get("suggestions",[])) if evidence_ids]
    confidence=float(analysis.get("confidence",0)); incomplete=any(x["status"]=="partial" for x in dims)
    review=incomplete or confidence<0.6 or unsupported_findings
    reason="模型返回的问题或建议缺少可引用证据" if unsupported_findings else ("评分维度缺失或模型置信度偏低" if review else None)
    summary=(analysis.get("summary","") or "脚本评估需要人工复核。")+("；模型返回的问题缺少证据，已转人工复核。" if unsupported_findings else "")
    payload={"asset_type":"script","profile":"ad_script_v1","summary":summary,"dimensions":dims,"evidence":evidence,"issues":issues,"strengths":analysis.get("strengths",[]),"suggestions":suggestions,"missing_information":missing,"confidence":confidence,"human_review_required":review,"human_review_reason":reason,"run_summary":{"steps":1,"completed_actions":["single_script_review"],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"single_pass_completed"},"technical_details":{"text_call":"single_pass"}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":{"text_call":"single_pass","raw_analysis":analysis}}
'''
    script_normalizer=base.node("2900000000303","规范化脚本评估","code",1830,1100,base.code_data(script_normalize_code,[base.var(["2900000000302","structured_output"],"analysis","object"),base.var(["1900000000001","product_context"],"product_context"),base.var(["1900000000001","target_audience"],"target_audience"),base.var(["1900000000001","conversion_goal"],"conversion_goal")],{"evaluation_json":"string","technical_details":"object"}),height=120)
    script_normalizer["data"]["error_strategy"] = "fail-branch"
    script_body={"type":"json","data":[{"id":"script-evaluation-json","key":"","type":"text","value":"{{#2900000000303.evaluation_json#}}"}]}
    script_renderer=base.node("2900000000304","渲染脚本报告","http-request",2130,1100,base.http_data("post",f"{BASE_URL}/api/v1/evaluations/render",script_body))
    script_parse_code=_report_parser_code("script", "ad_script_v1", "AIGC 脚本质量评估报告")
    script_parser=base.node("2900000000305","解析脚本报告","code",2430,1100,base.code_data(script_parse_code,[base.var(["2900000000304","body"],"body"),base.var(["2900000000304","status_code"],"status_code","number"),base.var(["2900000000303","technical_details"],"fallback_details","object")],{"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"}),height=120)
    script_end=base.node("2900000000306","输出脚本报告","end",2730,1100,{"outputs":[{"value_selector":["2900000000305","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000305","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000305","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000305","technical_details"],"value_type":"object","variable":"technical_details"}]},height=192)
    script_fallback=base.node("2900000000307","脚本分析失败转人工复核","code",2130,1240,base.code_data(_model_fallback_code("script","ad_script_v1","AIGC 脚本质量评估报告"),[],{"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"}),height=120)
    script_fallback_end=base.node("2900000000308","输出脚本人工复核结果","end",2430,1240,{"outputs":[{"value_selector":["2900000000307","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000307","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000307","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000307","technical_details"],"value_type":"object","variable":"technical_details"}]},height=192)
    nodes[:]=[item for item in nodes if item["id"]!="2900000000005"]
    edges[:]=[item for item in edges if item["target"]!="2900000000005"]
    nodes.extend([script_precheck,script_validator,empty_script,script_llm,script_normalizer,script_renderer,script_parser,script_end,script_fallback,script_fallback_end])
    edges.extend([base.edge("2900000000003","2900000000299","if-else","code","true"),base.edge("2900000000299","2900000000300","code","if-else"),base.edge("2900000000300","2900000000302","if-else","llm","true"),base.edge("2900000000300","2900000000301","if-else","end","false"),base.edge("2900000000302","2900000000303","llm","code"),base.edge("2900000000302","2900000000307","llm","code","fail-branch"),base.edge("2900000000303","2900000000304","code","http-request"),base.edge("2900000000303","2900000000307","code","code","fail-branch"),base.edge("2900000000304","2900000000305","http-request","code"),base.edge("2900000000304","2900000000305","http-request","code","fail-branch"),base.edge("2900000000305","2900000000306","code","end"),base.edge("2900000000307","2900000000308","code","end")])
    dsl["app"].update({"name": "AIGC Multimodal Quality V1 - CANDIDATE", "description": "Portfolio candidate for advertising video, image and script quality evaluation"})
    _converge_report_ends(nodes, edges)
    return _stabilize_uuid_values(dsl)


def main() -> None:
    OUTPUT.write_text(json.dumps(build_dsl(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
