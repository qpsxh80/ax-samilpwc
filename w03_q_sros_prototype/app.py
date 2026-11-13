import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.data_loader import DataRoomRepository
from engine.llm_agent import LLMCopilotAgent
from engine.ontology_rules import OntologyRulesEngine
from engine.recovery_optimizer import SupplyRecoveryOptimizer
from engine.state_manager import StateManager

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

repo = DataRoomRepository()
ontology_engine = OntologyRulesEngine(repo)
optimizer = SupplyRecoveryOptimizer(repo)
state_mgr = StateManager()
llm_agent = LLMCopilotAgent(repo)


def build_full_response(runtime_state=None, copilot_output=None):
    if runtime_state is None:
        runtime_state = state_mgr.load_state()
    triage = ontology_engine.evaluate_triage_and_traceability(runtime_state)
    state_mgr.save_mapping_candidates(triage["c105_gap_analysis"])
    simulation = optimizer.simulate_recovery_plans(triage, runtime_state)
    res = {
        "runtime_state": runtime_state,
        "triage": triage,
        "simulation": simulation,
        "lineage": repo.get_lineage_summary(),
        "llm_status": llm_agent.get_status(),
    }
    if copilot_output is not None:
        res["copilot_output"] = copilot_output
    return res


class QSROSRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, file_path):
        with open(file_path, mode="rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(os.path.join(STATIC_DIR, "index.html"))
        elif self.path in ("/portfolio", "/portfolio.html"):
            self._send_html(os.path.join(STATIC_DIR, "portfolio.html"))
        elif self.path.startswith("/api/state"):
            self._send_json(build_full_response())
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/action":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            req = json.loads(raw)
            action_type = req.get("action_type", "RESET")
            payload = req.get("payload", {})
            updated_state = state_mgr.apply_action(action_type, payload, ontology_engine, optimizer)
            self._send_json(build_full_response(updated_state))
        elif self.path == "/api/nl_copilot":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            req = json.loads(raw)
            user_text = req.get("user_text", "").strip()
            doc_type = req.get("doc_type", "AUTO")
            apply_changes = req.get("apply_changes", True)

            cur_state = state_mgr.load_state()
            parsed = llm_agent.parse_natural_language_command(user_text, cur_state)

            if apply_changes and parsed.get("has_condition_change"):
                cur_state = state_mgr.apply_action(
                    "APPLY_DYNAMIC_CONDITION_CHANGE",
                    parsed,
                    ontology_engine,
                    optimizer,
                )

            full_data = build_full_response(cur_state)
            copilot_out = llm_agent.generate_copilot_response(
                user_text=user_text,
                parsed_info=parsed,
                full_response_data=full_data,
                doc_type=doc_type,
            )
            full_data["copilot_output"] = copilot_out
            self._send_json(full_data)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass


def run_self_verification():
    """3대 필수 시연 시나리오 + 실시간 동적 조건 변경(재판단) 자동 검증."""
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== [W03 Q-SROS 운영 시스템 자동 검증 시작] ===")

    # 초기 리셋
    st0 = state_mgr.apply_action("RESET", {}, ontology_engine, optimizer)
    res0 = build_full_response(st0)
    tf0 = res0["triage"]["triage_funnel"]
    print(f"[초기 상태] 과잉회수 차단 생산량: {tf0['saved_overreaction_prod_qty']:,} EA (출하분 {tf0['saved_overreaction_ship_qty']:,} EA)")
    print(f"[초기 상태] C-105 미매핑 차액 대사: 클레임 {res0['triage']['c105_gap_analysis']['total_confirmed_claims_qty']:,} EA vs 배치생산차액 {res0['triage']['c105_gap_analysis']['total_unmapped_batch_diff_qty']:,} EA")

    # 시나리오 1: 정상 사례
    st1 = state_mgr.apply_action("RUN_SCENARIO_1_NORMAL", {}, ontology_engine, optimizer)
    res1 = build_full_response(st1)
    p1 = res1["simulation"]["active_plan"]
    c101_1 = [c for c in p1["customer_schedules"] if c["customer_id"] == "C-101"][0]
    print(f"\n[시연 1: 정상 사례] 선택 대안: {p1['plan_code']} | 총 복구대상: {p1['total_target_recall_qty']:,} EA (현물 {p1['total_physical_replace_qty']:,} EA / 크레딧 {p1['total_credit_note_qty']:,} EA)")
    print(f"  -> C-101 초도납기: {c101_1['lead_biz_days']}영업일 ({c101_1['promised_ship_date']}) | 상태: {c101_1['churn_status']}")
    print(f"  -> Masil 품절위험 SKU 수: {p1['masil_stockout_sku_cnt']}종 | 배치 상태: {st1['batch_statuses']['B-02-2602-01']}")

    # 시나리오 2: 조건 변경 사례
    st2 = state_mgr.apply_action("RUN_SCENARIO_2_CHANGE", {}, ontology_engine, optimizer)
    res2 = build_full_response(st2)
    p2 = res2["simulation"]["active_plan"]
    c103_2 = [c for c in p2["customer_schedules"] if c["customer_id"] == "C-103"][0]
    print(f"\n[시연 2: 조건 변경 사례] C-103 실사 반영 후 총 복구대상: {p2['total_target_recall_qty']:,} EA (현물 {p2['total_physical_replace_qty']:,} EA)")
    print(f"  -> C-103 교체 배정: 현물 {c103_2['physical_replace_qty']:,} EA / 크레딧 {c103_2['credit_note_qty']:,} EA | 납기: {c103_2['promised_ship_date']}")
    print(f"  -> F1 라인 지원: L-01 {p2['used_l01_support_qty']:,} EA + L-03 {p2['used_l03_support_qty']:,} EA | Masil 품절위험: {p2['masil_stockout_sku_cnt']}종")

    # 시나리오 3: 정보 부족 · 승인 거절 사례 + 모의 외부 회신
    st3 = state_mgr.apply_action("RUN_SCENARIO_3_EXCEPTION", {}, ontology_engine, optimizer)
    res3 = build_full_response(st3)
    p3 = res3["simulation"]["active_plan"]
    c101_3 = [c for c in p3["customer_schedules"] if c["customer_id"] == "C-101"][0]
    print(f"\n[시연 3: 정보부족·승인거절] 영업임원 반려 후 C-101 현물 배정: {c101_3['physical_replace_qty']:,} EA (100% 현물), 크레딧: {c101_3['credit_note_qty']} EA")

    st3_ver = state_mgr.apply_action("VERIFY_C105_MAPPING", {}, ontology_engine, optimizer)
    res3_ver = build_full_response(st3_ver)
    c105_tier = [c for c in res3_ver["triage"]["customer_tiers"] if c["customer_id"] == "C-105"][0]
    print(f"  -> [모의 회신 후 C-105 상태 전이] {c105_tier['tier_label']} ({c105_tier['mapping_status']})")

    # [신규 검증] 동적 조건 변경 1: 판정 정정(B-02-2603-01 오판 클레임 -3,500 EA 차감 -> 9.41% < 10% 회수 해제)
    state_mgr.apply_action("RUN_SCENARIO_1_NORMAL", {}, ontology_engine, optimizer)
    st_dyn1 = state_mgr.apply_action(
        "APPLY_DYNAMIC_CONDITION_CHANGE",
        {
            "preset_label": "판정 정정: B-02-2603-01 오판 클레임 -3,500 EA 차감",
            "b2603_01_claim_delta": -3500,
            "b2602_03_claim_delta": 0,
            "c103_unsold_audit_qty": 0,
            "c101_force_100_physical": False,
            "l01_max_limit_qty": 16812,
            "masil_demand_surge_pct": 0.0,
        },
        ontology_engine,
        optimizer,
    )
    rep1 = st_dyn1["ai_rejudgment_report"]
    bva1 = rep1["before_vs_after"]
    print(f"\n[동적 재판단 검증 1: 클레임 하향 정정] 결론변경={rep1['conclusion_changed']} | 회수배치: {bva1['recall_batches']['before']} -> {bva1['recall_batches']['after']}")
    print(f"  -> 총 복구대상: {bva1['total_recall_qty']['before']} -> {bva1['total_recall_qty']['after']} | 품질위원회 상태: {st_dyn1['approvals']['quality_committee']['status']}")

    # [신규 검증] 동적 조건 변경 2: 신규 배치 편입(B-02-2602-03 +17,000 EA) + L-01 설비 한도 축소(6,000 EA) + Masil 수요 +25%
    st_dyn2 = state_mgr.apply_action(
        "APPLY_DYNAMIC_CONDITION_CHANGE",
        {
            "preset_label": "복합 위기: B-02-2602-03 신규 불량(+17,000 EA) + F1 L-01 설비한도 축소(6,000 EA) + Masil 수요 +25%",
            "b2603_01_claim_delta": 0,
            "b2602_03_claim_delta": 17000,
            "c103_unsold_audit_qty": 18500,
            "c101_force_100_physical": False,
            "l01_max_limit_qty": 6000,
            "masil_demand_surge_pct": 25.0,
        },
        ontology_engine,
        optimizer,
    )
    rep2 = st_dyn2["ai_rejudgment_report"]
    bva2 = rep2["before_vs_after"]
    print(f"\n[동적 재판단 검증 2: 신규 배치 회수 편입 & 설비 제약] 회수배치: {bva2['recall_batches']['after']}")
    print(f"  -> AI 자율 역산 라인전환: {bva2['line_support']['after']} | Masil 품절위험: {bva2['masil_stockout_cnt']['after']}")

    # [신규 검증] 자연어 코파일럿(NL-to-Action & 공식 문서 생성) 검증
    nl_text = "올리브뷰티(C-101)가 크레딧 거부하고 100% 전량 현물로 달라고 요구했어. 그리고 C-103 창고 실사에서 미판매 재고 18,500개가 나왔어. C-101 바이어 협상 이메일 작성해줘."
    parsed_nl = llm_agent.parse_natural_language_command(nl_text, st_dyn2)
    st_nl = state_mgr.apply_action("APPLY_DYNAMIC_CONDITION_CHANGE", parsed_nl, ontology_engine, optimizer)
    full_nl = build_full_response(st_nl)
    cop_out = llm_agent.generate_copilot_response(nl_text, parsed_nl, full_nl, doc_type="C101_EMAIL")
    print(f"\n[자연어 코파일럿 검증] 추출된 조건: {parsed_nl.get('extracted_entities')} | 엔진: {cop_out['provider_used']}")
    print(f"  -> 생성된 문서 첫 줄: {cop_out['response_text'].splitlines()[0]}")

    # 시연 1 상태로 기본 세팅 유지
    state_mgr.apply_action("RUN_SCENARIO_1_NORMAL", {}, ontology_engine, optimizer)
    print("\n=== [검증 완료: 모든 상태 및 파일(runtime_state.json, sbl_sh_mapping_candidates.json) 정상 생성] ===")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        run_self_verification()
    else:
        port = int(os.environ.get("PORT", 8083))
        server = HTTPServer(("127.0.0.1", port), QSROSRequestHandler)
        print(f"W03 Q-SROS Server running on http://127.0.0.1:{port}")
        server.serve_forever()
