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
    issues=[{"priority":"P1","dimension":"overall","problem":text,"impact":"可能降低广告信息传达效果","evidence_refs":[],"suggestion":"根据问题调整画面后复核"} for text in analysis.get("issues",[])]
    suggestions=[{"priority":"P1" if i<2 else "P2","action":text,"expected_effect":"提升广告信息传达质量","evidence_refs":[]} for i,text in enumerate(analysis.get("suggestions",[]))]
    confidence=float(analysis.get("confidence",0)); incomplete=any(x["status"]=="partial" for x in dims)
    payload={"asset_type":"image","profile":"ad_image_v1","summary":analysis.get("summary","") or "图片评估需要人工复核。","dimensions":dims,"evidence":evidence,"issues":issues,"strengths":analysis.get("strengths",[]),"suggestions":suggestions,"missing_information":missing,"confidence":confidence,"human_review_required":incomplete or confidence<0.6,"human_review_reason":"评分维度缺失或模型置信度偏低" if incomplete or confidence<0.6 else None,"run_summary":{"steps":1,"completed_actions":["single_vision_review"],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"single_pass_completed"},"technical_details":{"vision_call":"single_pass"}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":{"vision_call":"single_pass","raw_analysis":analysis}}
'''
    image_normalizer = base.node("2900000000201", "规范化图片评估", "code", 1530, 920, base.code_data(image_normalize_code, [
        base.var(["2900000000200", "structured_output"], "analysis", "object"), base.var(["1900000000001", "product_context"], "product_context"), base.var(["1900000000001", "target_audience"], "target_audience"), base.var(["1900000000001", "conversion_goal"], "conversion_goal")
    ], {"evaluation_json":"string","technical_details":"object"}), height=120)
    image_body = {"type":"json","data":[{"id":"image-evaluation-json","key":"","type":"text","value":"{{#2900000000201.evaluation_json#}}"}]}
    image_renderer = base.node("2900000000202", "渲染图片报告", "http-request", 1830, 920, base.http_data("post", f"{BASE_URL}/api/v1/evaluations/render", image_body))
    image_parse_code = '''import json
def main(body, status_code, fallback_details):
    try:
        if int(status_code)!=200: raise ValueError(f"renderer status={status_code}")
        data=json.loads(body) if isinstance(body,str) else body; result=data.get("result",{})
        if not data.get("report_markdown") or not result: raise ValueError("empty renderer response")
        return {"report_markdown":data["report_markdown"],"evaluation_result":result,"final_status":str(result.get("status","human_review_required")),"technical_details":data.get("technical_details",fallback_details)}
    except Exception as exc:
        return {"report_markdown":"# AIGC 图片质量评估报告\n\n报告渲染失败，需要人工复核。","evaluation_result":{},"final_status":"human_review_required","technical_details":{"error":str(exc),"fallback":fallback_details}}
'''
    image_parser = base.node("2900000000203", "解析图片报告", "code", 2130, 920, base.code_data(image_parse_code, [base.var(["2900000000202","body"],"body"),base.var(["2900000000202","status_code"],"status_code","number"),base.var(["2900000000201","technical_details"],"fallback_details","object")], {"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"}), height=120)
    image_end = base.node("2900000000204", "输出图片报告", "end", 2430, 920, {"outputs":[
        {"value_selector":["2900000000203","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000203","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000203","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000203","technical_details"],"value_type":"object","variable":"technical_details"},
    ]}, height=192)
    nodes[:] = [item for item in nodes if item["id"] != "2900000000004"]
    edges[:] = [item for item in edges if item["target"] != "2900000000004"]
    nodes.extend([image_llm,image_normalizer,image_renderer,image_parser,image_end])
    edges.extend([base.edge("2900000000002","2900000000200","if-else","llm","true"),base.edge("2900000000200","2900000000201","llm","code"),base.edge("2900000000201","2900000000202","code","http-request"),base.edge("2900000000202","2900000000203","http-request","code"),base.edge("2900000000202","2900000000203","http-request","code","fail-branch"),base.edge("2900000000203","2900000000204","code","end")])

    script_dimensions = ["hook", "pain_point", "selling_point", "audience", "structure", "cta", "claim_risk"]
    script_schema = {
        "type":"object","additionalProperties":False,"properties":{
            "summary":{"type":"string"},
            "dimensions":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"dimension":{"type":"string","enum":script_dimensions},"score":{"type":"number","minimum":0,"maximum":10},"reason":{"type":"string"}},"required":["dimension","score","reason"]}},
            "evidence":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"location":{"type":"string","description":"段落编号或场景编号"},"dimension":{"type":"string","enum":script_dimensions},"finding":{"type":"string"}},"required":["location","dimension","finding"]}},
            "issues":{"type":"array","items":{"type":"string"}},"strengths":{"type":"array","items":{"type":"string"}},"suggestions":{"type":"array","items":{"type":"string"}},"confidence":{"type":"number","minimum":0,"maximum":1},
        },"required":["summary","dimensions","evidence","issues","strengths","suggestions","confidence"],
    }
    script_validator = base.node("2900000000300","脚本非空？","if-else",1230,1160,base.if_data(["1900000000001","script"],"","string","not empty"))
    empty_script = base.node("2900000000301","拒绝空脚本","end",1530,1280,{"outputs":[
        {"value_selector":["1900000000001","script"],"value_type":"string","variable":"invalid_script"},
    ]})
    script_llm = base.node("2900000000302","评估广告脚本","llm",1530,1100,base.llm_data(
        "你是广告脚本质量审核员。只根据原文和提供的业务上下文判断，不得补写原文没有的事实。逐项评估 hook、pain_point、selling_point、audience、structure、cta、claim_risk。每条证据必须使用段落编号或场景编号作为 location，便于人工回看。",
        "profile: ad_script_v1\n脚本原文：{{#1900000000001.script#}}\n产品信息：{{#1900000000001.product_context#}}\n目标受众：{{#1900000000001.target_audience#}}\n转化目标：{{#1900000000001.conversion_goal#}}\n补充要求：{{#1900000000001.additional_requirements#}}",
        script_schema,
    ),height=120)
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
    issues=[{"priority":"P1","dimension":"overall","problem":text,"impact":"可能降低脚本表达或转化效果","evidence_refs":[],"suggestion":"根据问题改写对应段落后复核"} for text in analysis.get("issues",[])]
    suggestions=[{"priority":"P1" if i<2 else "P2","action":text,"expected_effect":"提升脚本表达与转化清晰度","evidence_refs":[]} for i,text in enumerate(analysis.get("suggestions",[]))]
    confidence=float(analysis.get("confidence",0)); incomplete=any(x["status"]=="partial" for x in dims)
    payload={"asset_type":"script","profile":"ad_script_v1","summary":analysis.get("summary","") or "脚本评估需要人工复核。","dimensions":dims,"evidence":evidence,"issues":issues,"strengths":analysis.get("strengths",[]),"suggestions":suggestions,"missing_information":missing,"confidence":confidence,"human_review_required":incomplete or confidence<0.6,"human_review_reason":"评分维度缺失或模型置信度偏低" if incomplete or confidence<0.6 else None,"run_summary":{"steps":1,"completed_actions":["single_script_review"],"supplementary_frames_used":False,"retry_count":0,"stop_reason":"single_pass_completed"},"technical_details":{"text_call":"single_pass"}}
    return {"evaluation_json":json.dumps(payload,ensure_ascii=False),"technical_details":{"text_call":"single_pass","raw_analysis":analysis}}
'''
    script_normalizer=base.node("2900000000303","规范化脚本评估","code",1830,1100,base.code_data(script_normalize_code,[base.var(["2900000000302","structured_output"],"analysis","object"),base.var(["1900000000001","product_context"],"product_context"),base.var(["1900000000001","target_audience"],"target_audience"),base.var(["1900000000001","conversion_goal"],"conversion_goal")],{"evaluation_json":"string","technical_details":"object"}),height=120)
    script_body={"type":"json","data":[{"id":"script-evaluation-json","key":"","type":"text","value":"{{#2900000000303.evaluation_json#}}"}]}
    script_renderer=base.node("2900000000304","渲染脚本报告","http-request",2130,1100,base.http_data("post",f"{BASE_URL}/api/v1/evaluations/render",script_body))
    script_parse_code='''import json
def main(body, status_code, fallback_details):
    try:
        if int(status_code)!=200: raise ValueError(f"renderer status={status_code}")
        data=json.loads(body) if isinstance(body,str) else body; result=data.get("result",{})
        if not data.get("report_markdown") or not result: raise ValueError("empty renderer response")
        return {"report_markdown":data["report_markdown"],"evaluation_result":result,"final_status":str(result.get("status","human_review_required")),"technical_details":data.get("technical_details",fallback_details)}
    except Exception as exc:
        return {"report_markdown":"# AIGC 脚本质量评估报告\n\n报告渲染失败，需要人工复核。","evaluation_result":{},"final_status":"human_review_required","technical_details":{"error":str(exc),"fallback":fallback_details}}
'''
    script_parser=base.node("2900000000305","解析脚本报告","code",2430,1100,base.code_data(script_parse_code,[base.var(["2900000000304","body"],"body"),base.var(["2900000000304","status_code"],"status_code","number"),base.var(["2900000000303","technical_details"],"fallback_details","object")],{"report_markdown":"string","evaluation_result":"object","final_status":"string","technical_details":"object"}),height=120)
    script_end=base.node("2900000000306","输出脚本报告","end",2730,1100,{"outputs":[{"value_selector":["2900000000305","report_markdown"],"value_type":"string","variable":"report_markdown"},{"value_selector":["2900000000305","evaluation_result"],"value_type":"object","variable":"evaluation_result"},{"value_selector":["2900000000305","final_status"],"value_type":"string","variable":"final_status"},{"value_selector":["2900000000305","technical_details"],"value_type":"object","variable":"technical_details"}]},height=192)
    nodes[:]=[item for item in nodes if item["id"]!="2900000000005"]
    edges[:]=[item for item in edges if item["target"]!="2900000000005"]
    nodes.extend([script_validator,empty_script,script_llm,script_normalizer,script_renderer,script_parser,script_end])
    edges.extend([base.edge("2900000000003","2900000000300","if-else","if-else","true"),base.edge("2900000000300","2900000000302","if-else","llm","true"),base.edge("2900000000300","2900000000301","if-else","end","false"),base.edge("2900000000302","2900000000303","llm","code"),base.edge("2900000000303","2900000000304","code","http-request"),base.edge("2900000000304","2900000000305","http-request","code"),base.edge("2900000000304","2900000000305","http-request","code","fail-branch"),base.edge("2900000000305","2900000000306","code","end")])
    dsl["app"].update({"name": "AIGC Multimodal Quality V1 - CANDIDATE", "description": "Portfolio candidate for advertising video, image and script quality evaluation"})
    return dsl


def main() -> None:
    OUTPUT.write_text(json.dumps(build_dsl(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
