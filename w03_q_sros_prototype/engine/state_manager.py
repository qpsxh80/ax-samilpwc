import copy
import json
import os
from datetime import datetime

WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data_workspace")
)
STATE_FILE = os.path.join(WORKSPACE_DIR, "runtime_state.json")
MAPPING_FILE = os.path.join(WORKSPACE_DIR, "sbl_sh_mapping_candidates.json")


def get_initial_state():
    return {
        "scenario_mode": "INITIAL_AS_OF",
        "scenario_title": "기준일(2026-07-01) 초기 상태 — 클레임 165건 및 미확정 언론 보도 접수 대기",
        "as_of_date": "2026-07-01",
        "c105_mapping_verified": False,
        "c103_unsold_audit_qty": 0,
        "c108_unsold_audit_qty": 0,
        "c101_force_100_physical": False,
        "l01_max_limit_qty": 16812,
        "l03_max_limit_qty": 24420,
        "masil_demand_surge_pct": 0.0,
        "batch_claim_adjustments": {
            "B-02-2602-01": 0,
            "B-02-2603-01": 0,
            "B-02-2602-02": 0,
            "B-02-2602-03": 0,
        },
        "lot_reinspection_status": "보류(선투입위험)",
        "injected_claims": [],
        "batch_statuses": {
            "B-02-2602-01": "회수검토(불량률 11.87% ≥ 10%)",
            "B-02-2603-01": "회수검토(불량률 11.59% ≥ 10%)",
            "B-02-2602-02": "정상출하(동일로트_합격_회수제외)",
            "B-02-2602-03": "정상출하(동일로트_합격_회수제외)",
        },
        "approvals": {
            "quality_committee": {
                "authority": "품질위원회",
                "scope": "B-02-2602-01, B-02-2603-01 배치 회수 실행 의결 (과잉회수 316,277 EA 제외)",
                "status": "상신대기",
                "updated_at": "2026-07-01 09:00",
                "comment": "불량률 10% 이상 확정 배치 2건에 대한 회수 의결 필요 (원인규명과 별도 트랙)",
            },
            "sales_executive": {
                "authority": "영업 임원",
                "scope": "C-101(매출 30%)·C-102·C-104 복구 일정 및 현물+크레딧 혼합 보상안 승인",
                "status": "상신대기",
                "updated_at": "2026-07-01 09:00",
                "comment": "C-101 3~6월 수주 -53.0% 급감 대응을 위한 2주 내 초도 물량 납품 확약 필요",
            },
            "scm_production": {
                "authority": "생산·SCM",
                "scope": "F1 공장 L-02 여유분(4,873 EA) + L-01 일시 전환(12,000 EA) 및 Masil 안전재고 방어 배정",
                "status": "상신대기",
                "updated_at": "2026-07-01 09:00",
                "comment": "Masil 더마 SKU-1004(2.21주)·1001(2.92주) 결품 방어를 위한 동시 스케줄링 승인 필요",
            },
        },
        "sim_params": {
            "selected_plan": "PLAN_C",
            "physical_replace_ratio": 0.60,
            "l01_support_qty": 12000,
            "l03_support_qty": 0,
            "include_c105_reserve": True,
        },
        "ai_rejudgment_report": {
            "timestamp": "2026-07-01 09:00:00",
            "trigger_summary": "초기 데이터룸(2026-07-01 As-Of) 스캔 및 기본 제약 조건 로드",
            "conclusion_status": "초기 기준 판정 완료 (2개 배치 표적 회수 + Plan C 혼합 복구 권고)",
            "conclusion_changed": False,
            "before_vs_after": {
                "recall_batches": {"before": "미분류(4개 후보)", "after": "B-02-2602-01, B-02-2603-01 (2개 배치)"},
                "total_recall_qty": {"before": "627,755 EA (로트 일괄 시)", "after": "36,522 EA (확정 불량 기준)"},
                "physical_replace_qty": {"before": "36,522 EA", "after": "21,534 EA (현물+크레딧 최적혼합)"},
                "line_support": {"before": "L-02 단독(4,873 EA/월)", "after": "L-02(4,873) + L-01(12,000) = 16,873 EA/월"},
                "c101_lead_days": {"before": "42영업일 (이탈위험)", "after": "8영업일 (2주 내 방어성공)"},
                "masil_stockout_cnt": {"before": "3종 품절위험", "after": "0종 (전 SKU 안전재고 방어)"},
            },
            "reasoning_trace": [
                "1. [과잉대응 차단] LOT-B-2602-P 투입 4개 배치 중 B-02-2602-02/03(316,277 EA)은 배치 QC 합격 및 확정클레임 0건(0.00%)이므로 회수에서 제외.",
                "2. [데이터 공백 탐지] C-105 확정클레임(11,765 EA)은 SBL 출하가 0건이나, 두 배치의 미매핑 생산차액(11,825 EA)과 99.5% 일치하므로 가배정(Hold) 후 물류 대조 티켓 발행.",
                "3. [다부서 제약 해법] F1 L-02 월 여유(4,873 EA)만으로는 C-101 2주 내 납기 불가 → L-01 여유분 12,000 EA 일시 전환 및 현물+크레딧 혼합(Plan C) 도출."
            ],
            "affected_departments": [
                "품질위원회: 2개 배치(B-02-2602-01, 2603-01) 표적 회수 의결 상신",
                "영업 임원: C-101·102·104 혼합 보상안 및 2주 내 납기 확약 상신",
                "생산·SCM: F1 L-01 12,000 EA 전환 및 Masil 긴급 PO 보호 스케줄 상신"
            ]
        },
        "tasks": [
            {
                "task_id": "TASK-QC-001",
                "dept": "품질보증팀",
                "target_obj": "LOT-B-2602-P / 101건 미확정 클레임",
                "title": "예비검사 보류 원료(LOT-B-2602-P) 원인 규명 및 미확정 클레임(101건) 소명 조사",
                "status": "진행중(회수와 분리)",
                "priority": "HIGH",
                "created_at": "2026-07-01 09:00",
            },
            {
                "task_id": "TASK-MAP-C105",
                "dept": "품질·물류합동",
                "target_obj": "C-105 (더뷰티클럽) / B-02-2602-01, 2603-01",
                "title": "C-105 확정 클레임(11,765 EA)의 SBL 출하 누락분(생산차액 11,825 EA) 및 SH 매출원장 대조 요청",
                "status": "회신대기(가배정 Hold)",
                "priority": "CRITICAL",
                "created_at": "2026-07-01 09:05",
            },
            {
                "task_id": "TASK-AUD-C103",
                "dept": "영업지원팀",
                "target_obj": "C-103(83,402 EA), C-108(34,929 EA)",
                "title": "회수 배치 출하 고객 중 클레임 0건 거래처(C-103, C-108) 창고 미판매 잔여재고 실사 요청",
                "status": "실사요청발송",
                "priority": "MEDIUM",
                "created_at": "2026-07-01 09:10",
            },
        ],
        "audit_logs": [
            {
                "timestamp": "2026-07-01 09:00:00",
                "actor": "SYSTEM (AI Engine)",
                "event": "기준일(2026-07-01) 데이터룸 로드 및 초기 트리아지 완료",
                "state_diff": "B-02-2602-01(11.87%), B-02-2603-01(11.59%) 회수검토 지정 / B-02-2602-02·03(316,277 EA) 과잉회수 차단",
            }
        ],
    }


class StateManager:
    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        if not os.path.exists(STATE_FILE):
            self.save_state(get_initial_state())

    def load_state(self):
        if not os.path.exists(STATE_FILE):
            state = get_initial_state()
            self.save_state(state)
            return state
        with open(STATE_FILE, mode="r", encoding="utf-8") as f:
            st = json.load(f)
        # 하위 호환성 보장 (새로 추가된 필드가 없을 경우 기본값 채움)
        init_st = get_initial_state()
        for k, v in init_st.items():
            if k not in st:
                st[k] = v
        return st

    def save_state(self, state):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        with open(STATE_FILE, mode="w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def save_mapping_candidates(self, c105_gap_analysis):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        with open(MAPPING_FILE, mode="w", encoding="utf-8") as f:
            json.dump(c105_gap_analysis, f, ensure_ascii=False, indent=2)

    def now_str(self):
        return datetime.now().strftime("2026-07-01 %H:%M:%S")

    def reset_state(self):
        st = get_initial_state()
        self.save_state(st)
        return st

    def _capture_metrics_snapshot(self, state, ontology_engine, optimizer):
        tri = ontology_engine.evaluate_triage_and_traceability(state)
        sim = optimizer.simulate_recovery_plans(tri, state)
        ap = sim["active_plan"]
        c101 = [c for c in ap["customer_schedules"] if c["customer_id"] == "C-101"]
        c101_days = c101[0]["lead_biz_days"] if c101 else 0
        recall_b_ids = [b["batch_id"] for b in tri["recall_batches"]]
        return {
            "recall_batches_str": ", ".join(recall_b_ids) if recall_b_ids else "없음(전부 해제)",
            "recall_batch_cnt": len(recall_b_ids),
            "total_recall_qty": ap["total_target_recall_qty"],
            "physical_replace_qty": ap["total_physical_replace_qty"],
            "l01_qty": ap["used_l01_support_qty"],
            "l03_qty": ap["used_l03_support_qty"],
            "c101_lead_days": c101_days,
            "masil_stockout_cnt": ap["masil_stockout_sku_cnt"],
            "reclassified_batches": tri.get("reclassified_batches", []),
        }

    def apply_action(self, action_type, payload=None, ontology_engine=None, optimizer=None):
        payload = payload or {}
        st = self.load_state()
        ts = self.now_str()

        if action_type == "RESET":
            return self.reset_state()

        # 변경 전 스냅샷 캡처 (동적 재판단 비교용)
        before_snap = None
        if ontology_engine and optimizer:
            before_snap = self._capture_metrics_snapshot(copy.deepcopy(st), ontology_engine, optimizer)

        trigger_desc = ""

        if action_type == "UPDATE_SIM_PARAMS":
            sp = st["sim_params"]
            if "selected_plan" in payload:
                sp["selected_plan"] = payload["selected_plan"]
            if "physical_replace_ratio" in payload:
                sp["physical_replace_ratio"] = float(payload["physical_replace_ratio"])
            if "l01_support_qty" in payload:
                sp["l01_support_qty"] = int(payload["l01_support_qty"])
            if "l03_support_qty" in payload:
                sp["l03_support_qty"] = int(payload["l03_support_qty"])
            if "include_c105_reserve" in payload:
                sp["include_c105_reserve"] = bool(payload["include_c105_reserve"])
            trigger_desc = f"담당자 시뮬레이션 파라미터 수동 조정 ({sp['selected_plan']}, 현물비율 {int(sp['physical_replace_ratio']*100)}%)"

        elif action_type == "APPLY_DYNAMIC_CONDITION_CHANGE":
            # 사용자가 임의의 조건 변경(판정 정정, 창고 실사 수량, 설비 한도, Masil 수요 급증, C-101 100% 현물 요구 등)을 입력했을 때
            # AI가 자동으로 온톨로지 재판정 -> 최적 라인 배정 역산 -> 기존 부서 승인 무효화/재검증 -> 작업 티켓 갱신 수행!
            if "b2603_01_claim_delta" in payload:
                st["batch_claim_adjustments"]["B-02-2603-01"] = int(payload["b2603_01_claim_delta"])
            if "b2602_03_claim_delta" in payload:
                st["batch_claim_adjustments"]["B-02-2602-03"] = int(payload["b2602_03_claim_delta"])
            if "c103_unsold_audit_qty" in payload:
                st["c103_unsold_audit_qty"] = int(payload["c103_unsold_audit_qty"])
            if "c101_force_100_physical" in payload:
                st["c101_force_100_physical"] = bool(payload["c101_force_100_physical"])
            if "l01_max_limit_qty" in payload:
                st["l01_max_limit_qty"] = int(payload["l01_max_limit_qty"])
            if "masil_demand_surge_pct" in payload:
                st["masil_demand_surge_pct"] = float(payload["masil_demand_surge_pct"])
            if "c105_mapping_verified" in payload:
                st["c105_mapping_verified"] = bool(payload["c105_mapping_verified"])

            auto_solve = payload.get("auto_solve", True)
            if auto_solve and ontology_engine and optimizer:
                tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                solved = optimizer.auto_solve_optimal_params(tri_new, st)
                st["sim_params"]["selected_plan"] = "PLAN_C"
                st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]

            st["scenario_mode"] = "DYNAMIC_REJUDGMENT"
            trigger_desc = payload.get(
                "preset_label",
                f"동적 조건 변경 입력 (B-2603-01 정정:{st['batch_claim_adjustments']['B-02-2603-01']:+,} EA, "
                f"B-2602-03 추가:{st['batch_claim_adjustments']['B-02-2602-03']:+,} EA, "
                f"C-103 실사:{st['c103_unsold_audit_qty']:,} EA, L-01한도:{st['l01_max_limit_qty']:,} EA, "
                f"Masil수요:{st['masil_demand_surge_pct']:+.0f}%)"
            )
            st["scenario_title"] = f"[AI 실시간 재판단 완료] {trigger_desc}"

        elif action_type == "RUN_SCENARIO_1_NORMAL":
            st = get_initial_state()
            st["scenario_mode"] = "SCENARIO_1_NORMAL"
            st["scenario_title"] = "[시연 1: 정상 사례] 정밀 회수 판정(2개 배치) + 다부서 혼합 복구안(Plan C) 의결 및 일정 갱신 완료"
            if ontology_engine and optimizer:
                tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                solved = optimizer.auto_solve_optimal_params(tri_new, st)
                st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]

            st["batch_statuses"]["B-02-2602-01"] = "회수실행중(품질위 의결완료)"
            st["batch_statuses"]["B-02-2603-01"] = "회수실행중(품질위 의결완료)"
            st["approvals"]["quality_committee"]["status"] = "승인완료"
            st["approvals"]["quality_committee"]["updated_at"] = ts
            st["approvals"]["quality_committee"]["comment"] = "B-02-2602-01(11.87%), B-02-2603-01(11.59%) 2개 배치 표적 회수 의결. 정상 배치 2건(316,277 EA) 및 루머 전면회수 배제 확정."

            st["approvals"]["sales_executive"]["status"] = "승인완료"
            st["approvals"]["sales_executive"]["updated_at"] = ts
            st["approvals"]["sales_executive"]["comment"] = "C-101·C-102(65% 현물+35% 크레딧), C-104(60% 현물+40% 크레딧) 10영업일 내 초도 공급 일정 승인."

            st["approvals"]["scm_production"]["status"] = "승인완료"
            st["approvals"]["scm_production"]["updated_at"] = ts
            st["approvals"]["scm_production"]["comment"] = f"F1 L-02 여유(4,873 EA) + L-01 일시 전환({st['sim_params']['l01_support_qty']:,} EA) 배정 완료. Masil 더마 긴급 PO 정상 입고 보호 확정."

            st["tasks"].insert(0, {
                "task_id": "TASK-REC-101",
                "dept": "생산·물류·영업",
                "target_obj": "C-101, C-102, C-104 (확정 24,757 EA + C-105 가배정 11,765 EA)",
                "title": "[실행지시] Plan C 기반 B2B 회수 교체품 출하(21,534 EA) 및 매출채권 크레딧 정산(14,988 EA) 집행",
                "status": "실행확정(생산배정완료)",
                "priority": "CRITICAL",
                "created_at": ts,
            })
            st["tasks"].insert(1, {
                "task_id": "TASK-SCM-MS01",
                "dept": "Masil SCM · Corevia 생산관리",
                "target_obj": "SPO-0001, SPO-0002, SPO-0004 (더마 세럼·크림·앰플)",
                "title": "[일정확정] Masil 결품위험 SKU(재고커버 2.21~2.92주) 보호를 위한 L-02 정규 생산슬롯 우선 고정",
                "status": "보호배정완료",
                "priority": "HIGH",
                "created_at": ts,
            })
            trigger_desc = "[시연 1: 정상 사례] 클레임 165건 스캔 + 루머 차단 + Plan C 다부서 승인"

        elif action_type == "RUN_SCENARIO_2_CHANGE":
            st["scenario_mode"] = "SCENARIO_2_CHANGE"
            st["scenario_title"] = "[시연 2: 조건 변경 사례] C-103 창고 미판매 재고(18,500 EA) 실사 회신 유입 → AI 자율 재계획(L-01 한도 채움 + L-03 추가 전환)"
            st["c103_unsold_audit_qty"] = 18500
            st["lot_reinspection_status"] = "불량확정(V-205 정제공정 온도이탈 확인)"
            st["sim_params"]["selected_plan"] = "PLAN_C"

            if ontology_engine and optimizer:
                tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                solved = optimizer.auto_solve_optimal_params(tri_new, st)
                st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]
            else:
                st["sim_params"]["l01_support_qty"] = 16812
                st["sim_params"]["l03_support_qty"] = 6000

            st["approvals"]["scm_production"]["status"] = "재검토필요(조건변경)"
            st["approvals"]["scm_production"]["updated_at"] = ts
            st["approvals"]["scm_production"]["comment"] = (
                f"C-103 실사 물량(+18,500 EA) 추가로 AI가 L-01({st['sim_params']['l01_support_qty']:,} EA) + "
                f"L-03({st['sim_params']['l03_support_qty']:,} EA) 자동 확대 배정 산출 → SCM 재승인 요청."
            )

            for t in st["tasks"]:
                if t["task_id"] == "TASK-AUD-C103":
                    t["status"] = "실사완료(미판매 18,500 EA 확인)"
                    t["title"] = "[실사회신] C-103 창고 내 B-02-2602-01/2603-01 미판매 재고 18,500 EA 봉인 및 교체 편입 완료"

            st["tasks"].insert(0, {
                "task_id": "TASK-CHG-201",
                "dept": "생산관리팀 · Masil SCM",
                "target_obj": "F1 L-01/L-03 라인 & Masil SPO-0003(SKU-1003)",
                "title": (
                    f"[AI 자동재조정] C-103 교체분(+9,250 EA 현물) 흡수를 위해 L-01({st['sim_params']['l01_support_qty']:,} EA) + "
                    f"L-03({st['sim_params']['l03_support_qty']:,} EA) 자동 전환 배정 및 핵심 고객 2주 내 납기 유지"
                ),
                "status": "재검증완료(일정갱신)",
                "priority": "HIGH",
                "created_at": ts,
            })
            trigger_desc = "[시연 2: 조건 변경] C-103 창고 실사 미판매 재고(18,500 EA) 발견 회신 및 원료 불량 확정"

        elif action_type == "RUN_SCENARIO_3_EXCEPTION":
            st["scenario_mode"] = "SCENARIO_3_EXCEPTION"
            st["scenario_title"] = "[시연 3: 정보 부족·승인 거절] C-105 출하식별자(SBL) 누락 보류 + 영업임원 'C-101 크레딧 반려(100% 현물 요구)'에 따른 AI 대안 재상신"
            st["c105_mapping_verified"] = False
            st["c101_force_100_physical"] = True
            st["sim_params"]["selected_plan"] = "PLAN_C"

            if ontology_engine and optimizer:
                tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                solved = optimizer.auto_solve_optimal_params(tri_new, st)
                st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]
            else:
                st["sim_params"]["l01_support_qty"] = 14500

            st["approvals"]["sales_executive"]["status"] = "반려(조건부재상신요구)"
            st["approvals"]["sales_executive"]["updated_at"] = ts
            st["approvals"]["sales_executive"]["comment"] = "[반려 사유] 1위 고객 C-101(수주 -53% 급감)은 크레딧 정산 수용 불가. C-101 클레임 7,214 EA 전량(100%) 현물 즉시 교체로 계획 수정 요망."

            st["approvals"]["scm_production"]["status"] = "재검토필요(물량변경)"
            st["approvals"]["scm_production"]["updated_at"] = ts
            st["approvals"]["scm_production"]["comment"] = (
                f"C-101 100% 현물 전환(+2,525 EA 현물 증가)에 따라 AI가 F1 L-01 전환 물량을 "
                f"{st['sim_params']['l01_support_qty']:,} EA로 자동 상향 조정."
            )

            st["tasks"].insert(0, {
                "task_id": "TASK-REJ-301",
                "dept": "영업1팀 · 생산계획팀",
                "target_obj": "C-101 복구 계획 (Plan C-Rev)",
                "title": f"[반려 후속조치] 영업임원 반려 반영: C-101 현물 교체비율 65% → 100%(7,214 EA 전량 현물) 상향 및 L-01 {st['sim_params']['l01_support_qty']:,} EA 배정 재상신",
                "status": "재상신완료",
                "priority": "CRITICAL",
                "created_at": ts,
            })
            trigger_desc = "[시연 3: 정보부족·승인거절] 영업임원 'C-101 크레딧 반려(100% 현물 요구)' 및 C-105 SBL 매핑 미확인 보류"

        elif action_type == "VERIFY_C105_MAPPING":
            st["c105_mapping_verified"] = True
            st["sim_params"]["include_c105_reserve"] = True
            if ontology_engine and optimizer:
                tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                solved = optimizer.auto_solve_optimal_params(tri_new, st)
                st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]

            for t in st["tasks"]:
                if t["task_id"] == "TASK-MAP-C105":
                    t["status"] = "매핑확정완료(SH 원장 대조)"
                    t["title"] = "[회신완료] C-105 2~3월 SH 매출출하 원장 및 배치 미매핑 차액(11,825 EA) 대조 결과 SBL 누락 확인 → 정식 회수·복구 편입"
            trigger_desc = "물류팀 모의 회신 유입: C-105(더뷰티클럽) SBL↔SH 출하 매핑 검증 완료"

        elif action_type == "APPROVE_GATEWAY":
            gate = payload.get("gate", "quality_committee")
            decision = payload.get("decision", "승인완료")
            comment = payload.get("comment", "")
            if gate in st["approvals"]:
                st["approvals"][gate]["status"] = decision
                st["approvals"][gate]["updated_at"] = ts
                if comment:
                    st["approvals"][gate]["comment"] = comment

                if gate == "quality_committee" and decision == "승인완료":
                    st["batch_statuses"]["B-02-2602-01"] = "회수실행중(품질위 의결완료)"
                    st["batch_statuses"]["B-02-2603-01"] = "회수실행중(품질위 의결완료)"
                elif gate == "quality_committee" and ("보류" in decision or "반려" in decision):
                    st["batch_statuses"]["B-02-2602-01"] = "의결보류(추가소명대기)"
                    st["batch_statuses"]["B-02-2603-01"] = "의결보류(추가소명대기)"

                # 만약 영업임원이 게이트웨이에서 반려를 누르면 AI가 자동으로 C-101 100% 현물 전환 대안을 재계산!
                if gate == "sales_executive" and "반려" in decision:
                    st["c101_force_100_physical"] = True
                    if ontology_engine and optimizer:
                        tri_new = ontology_engine.evaluate_triage_and_traceability(st)
                        solved = optimizer.auto_solve_optimal_params(tri_new, st)
                        st["sim_params"]["l01_support_qty"] = solved["auto_l01_support_qty"]
                        st["sim_params"]["l03_support_qty"] = solved["auto_l03_support_qty"]
                    st["approvals"]["scm_production"]["status"] = "재검토필요(영업반려연동)"

                trigger_desc = f"HITL 권한 게이트웨이 의사결정 입력 ({st['approvals'][gate]['authority']}: {decision})"

        # 변경 후 스냅샷 계산 및 AI 재판단 리포트(Before vs After Diff & 부서 기록 재확인) 자동 생성
        if ontology_engine and optimizer and before_snap:
            after_snap = self._capture_metrics_snapshot(st, ontology_engine, optimizer)
            self._update_rejudgment_report_and_governance(st, before_snap, after_snap, trigger_desc, ts, action_type)
        else:
            st["audit_logs"].insert(0, {
                "timestamp": ts,
                "actor": "SYSTEM (AI Engine)",
                "event": trigger_desc or action_type,
                "state_diff": "상태 갱신 완료",
            })

        self.save_state(st)
        return st

    def _update_rejudgment_report_and_governance(self, st, before_snap, after_snap, trigger_desc, ts, action_type):
        batch_changed = before_snap["recall_batches_str"] != after_snap["recall_batches_str"]
        qty_changed = before_snap["total_recall_qty"] != after_snap["total_recall_qty"]
        phys_changed = before_snap["physical_replace_qty"] != after_snap["physical_replace_qty"]
        line_changed = (before_snap["l01_qty"] != after_snap["l01_qty"]) or (before_snap["l03_qty"] != after_snap["l03_qty"])

        conclusion_changed = batch_changed or qty_changed or phys_changed or line_changed

        affected_depts = []
        reasoning = []

        # 1. 배치 회수 판정이 정정/변경된 경우 (W03.html 핵심 질문: "품질 판정이 정정됐을 때 어떤 부서의 기존 기록을 다시 확인해야 하는가?")
        if batch_changed:
            for rb in after_snap["reclassified_batches"]:
                if rb["before_target"] and not rb["after_target"]:
                    reasoning.append(
                        f"[품질 판정 정정 → 회수 해제] {rb['batch_id']} 배치의 확정 불량률이 {rb['before_rate_pct']}% → "
                        f"{rb['after_rate_pct']}% (< 10%)로 하락하여 회수 대상에서 즉시 해제하고 원인조사 트랙으로 전환했습니다."
                    )
                    st["batch_statuses"][rb["batch_id"]] = f"회수해제·판정정정(불량률 {rb['after_rate_pct']}% < 10%)"
                elif not rb["before_target"] and rb["after_target"]:
                    reasoning.append(
                        f"[신규 불량 배치 편입] {rb['batch_id']} 배치의 확정 불량률이 {rb['before_rate_pct']}% → "
                        f"{rb['after_rate_pct']}% (≥ 10%)로 상승하여 회수 대상에 긴급 편입했습니다."
                    )
                    st["batch_statuses"][rb["batch_id"]] = f" 긴급회수편입(불량률 {rb['after_rate_pct']}% ≥ 10%)"

            # 배치 범위가 바뀌었으므로 기존 3개 부서 승인 및 기록을 모두 재확인 상태로 전환!
            if action_type == "APPLY_DYNAMIC_CONDITION_CHANGE":
                for gk in ("quality_committee", "sales_executive", "scm_production"):
                    st["approvals"][gk]["status"] = "재검토필요(배치판정정정)"
                    st["approvals"][gk]["updated_at"] = ts
            affected_depts.extend([
                "품질위원회: 회수 대상 배치 범위 변경에 따른 기존 회수 의결안 정정 재심의 필요",
                "영업부서(B2B 고객대응): 해당 배치 출하 고객(C-101~C-105) 대상 기존 회수 통보 및 크레딧 정산 원장 취소/수정",
                "생산·SCM 및 재무회계: 재생산 배정 슬롯(F1 L-01/L-03) 회수 및 매출차감(충당부채) 기표 기록 재확인"
            ])
            st["tasks"].insert(0, {
                "task_id": f"TASK-REV-{len(st['tasks'])+101}",
                "dept": "품질위·영업·생산·재무 합동",
                "target_obj": f"회수 배치 변경 ({before_snap['recall_batches_str']} → {after_snap['recall_batches_str']})",
                "title": f"[판정정정 후속조치] 배치 회수 판정 변경에 따른 기존 고객 회수안내·생산슬롯·크레딧 원장 일괄 정정",
                "status": "긴급재확인중",
                "priority": "CRITICAL",
                "created_at": ts,
            })
        else:
            reasoning.append(
                f"[배치 회수 범위 재검증] 회수 대상 배치({after_snap['recall_batches_str']})는 10% 기준 재검증 결과 기존 판정이 그대로 유지됩니다."
            )

        # 2. 물량 또는 설비/수요 제약 변경에 따른 AI 라인 배정 재산출
        if qty_changed or phys_changed or line_changed:
            reasoning.append(
                f"[공급 복구 물량 재산출] 총 복구 대상 수량 {before_snap['total_recall_qty']:,} EA → {after_snap['total_recall_qty']:,} EA "
                f"(현물 필요량 {before_snap['physical_replace_qty']:,} EA → {after_snap['physical_replace_qty']:,} EA)."
            )
            reasoning.append(
                f"[다부서 제약 자율 해법] F1 L-02 여유분(4,873 EA) 외에 L-01 전환을 {before_snap['l01_qty']:,} → {after_snap['l01_qty']:,} EA, "
                f"L-03 전환을 {before_snap['l03_qty']:,} → {after_snap['l03_qty']:,} EA로 자동 재조정하여 "
                f"C-101 납기({after_snap['c101_lead_days']}영업일) 및 Masil 품절 위험({after_snap['masil_stockout_cnt']}종)을 방어했습니다."
            )
            if action_type == "APPLY_DYNAMIC_CONDITION_CHANGE" and not batch_changed:
                st["approvals"]["scm_production"]["status"] = "재검토필요(일정·물량변경)"
                st["approvals"]["scm_production"]["updated_at"] = ts
                affected_depts.append("생산·SCM: 라인 전환 물량(L-01/L-03) 및 Masil 발주 보호 스케줄 변경에 따른 생산계획 재승인 필요")
                if phys_changed:
                    st["approvals"]["sales_executive"]["status"] = "재검토필요(보상물량변경)"
                    st["approvals"]["sales_executive"]["updated_at"] = ts
                    affected_depts.append("영업 임원: 고객별 현물 재공급 및 크레딧 정산 수량 변경에 따른 고객 확약서 재확인 필요")
        else:
            reasoning.append(
                f"[공급 복구 결론 유지] 조건 변경에도 불구하고 현재 가용 생산능력(L-02 4,873 + L-01 {after_snap['l01_qty']:,} EA) 안에서 "
                f"C-101 초도 납기({after_snap['c101_lead_days']}영업일 ≤ 12영업일)와 Masil 안전재고 방어(품절 0종)가 모두 충족되므로 기존 복구 계획을 유지합니다."
            )
            if not affected_depts:
                affected_depts.append("전 부서: 기존 승인 범위 및 안전 마진 내에서 흡수 가능하므로 계획 유지 (재검증 로그만 기록)")

        c101_ok = after_snap["c101_lead_days"] <= 12
        masil_ok = after_snap["masil_stockout_cnt"] == 0
        if batch_changed:
            status_headline = f"결론 변경됨 — 회수 대상 배치 범위 정정 ({before_snap['recall_batches_str']} → {after_snap['recall_batches_str']}) 및 전 부서 기록 재조정"
        elif conclusion_changed and c101_ok and masil_ok:
            status_headline = "세부 배정 자동 재조정 완료 (핵심 결론 유지: C-101 2주 내 납기 & Masil 품절 0종 방어 성공)"
        elif conclusion_changed:
            status_headline = "결론 변경됨 — 설비/수요 극한 제약으로 인해 추가 라인 전환 및 상위 임원 에스컬레이션 필요"
        else:
            status_headline = "결론 유지됨 — 조건 재검증 결과 기존 Plan C 배정 안에서 모든 부서 제약 충족 확인"

        st["ai_rejudgment_report"] = {
            "timestamp": ts,
            "trigger_summary": trigger_desc,
            "conclusion_status": status_headline,
            "conclusion_changed": conclusion_changed,
            "before_vs_after": {
                "recall_batches": {
                    "before": before_snap["recall_batches_str"],
                    "after": after_snap["recall_batches_str"],
                },
                "total_recall_qty": {
                    "before": f"{before_snap['total_recall_qty']:,} EA",
                    "after": f"{after_snap['total_recall_qty']:,} EA",
                },
                "physical_replace_qty": {
                    "before": f"{before_snap['physical_replace_qty']:,} EA",
                    "after": f"{after_snap['physical_replace_qty']:,} EA",
                },
                "line_support": {
                    "before": f"L-01: {before_snap['l01_qty']:,} / L-03: {before_snap['l03_qty']:,} EA",
                    "after": f"L-01: {after_snap['l01_qty']:,} / L-03: {after_snap['l03_qty']:,} EA",
                },
                "c101_lead_days": {
                    "before": f"{before_snap['c101_lead_days']} 영업일",
                    "after": f"{after_snap['c101_lead_days']} 영업일",
                },
                "masil_stockout_cnt": {
                    "before": f"{before_snap['masil_stockout_cnt']}종",
                    "after": f"{after_snap['masil_stockout_cnt']}종",
                },
            },
            "reasoning_trace": reasoning,
            "affected_departments": affected_depts,
        }

        st["audit_logs"].insert(0, {
            "timestamp": ts,
            "actor": "AI Re-Judgment Engine",
            "event": trigger_desc,
            "state_diff": (
                f"배치:[{before_snap['recall_batches_str']}→{after_snap['recall_batches_str']}], "
                f"복구량:[{before_snap['total_recall_qty']:,}→{after_snap['total_recall_qty']:,} EA], "
                f"라인지원:[L01 {after_snap['l01_qty']:,}/L03 {after_snap['l03_qty']:,} EA], "
                f"C-101납기:[{after_snap['c101_lead_days']}일]"
            ),
        })
