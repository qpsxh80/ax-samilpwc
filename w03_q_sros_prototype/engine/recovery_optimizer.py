import math
from collections import defaultdict
from datetime import datetime, timedelta


def add_business_days(start_str, biz_days):
    dt = datetime.strptime(start_str, "%Y-%m-%d")
    added = 0
    while added < biz_days:
        dt += timedelta(days=1)
        if dt.weekday() < 5:
            added += 1
    return dt.strftime("%Y-%m-%d")


class SupplyRecoveryOptimizer:
    """
    다중 부서 제약(생산 F1 라인 가동률 · 영업 B2B 수주이탈 방어 · 유통 Masil 안전재고 방어)을 반영한
    AI 자율 공급 복구 스케줄러 및 대안 비교 엔진.
    """

    def __init__(self, repo):
        self.repo = repo

    def auto_solve_optimal_params(self, triage_result, runtime_state):
        """
        조건이 변경되었을 때 AI가 자동으로 최적의 라인 전환량(L-01, L-03)과
        Masil 보호/순연 전략을 역산하는 자율 해법 탐색기(Autonomous Constraint Solver).
        """
        params = runtime_state.get("sim_params", {})
        c101_force_100 = runtime_state.get("c101_force_100_physical", False)
        include_c105 = params.get("include_c105_reserve", True)
        base_phys_ratio = float(params.get("physical_replace_ratio", 0.60))
        l01_max_limit = int(runtime_state.get("l01_max_limit_qty", 16812))
        l03_max_limit = int(runtime_state.get("l03_max_limit_qty", 24420))
        masil_surge_pct = float(runtime_state.get("masil_demand_surge_pct", 0.0))

        # 1. 현재 유효 회수 대상에 따른 총 현물 필요량 및 핵심 고객(C-101, 102, 104) 긴급 현물 필요량 계산
        total_phys_needed = 0
        urgent_tier1_phys_needed = 0

        for c in triage_result["customer_tiers"]:
            cid = c["customer_id"]
            if cid == "C-105" and not include_c105 and c["tier"] == "TIER_2_MAPPING_GAP":
                target_q = 0
            else:
                target_q = c["effective_recall_qty"]

            if cid == "C-101" and c101_force_100:
                p_ratio = 1.0
            elif cid in ("C-101", "C-102"):
                p_ratio = max(base_phys_ratio, 0.65)
            elif cid == "C-104":
                p_ratio = base_phys_ratio
            else:
                p_ratio = min(base_phys_ratio, 0.50) if base_phys_ratio < 0.99 else 1.0

            phys_q = int(round(target_q * p_ratio))
            total_phys_needed += phys_q
            if cid in ("C-101", "C-102", "C-104"):
                urgent_tier1_phys_needed += phys_q

        # 2. 목표 납기 제약:
        #    - 핵심 고객(Tier 1: C-101, 102, 104) 완료가 10영업일(준비 2일 + 생산 8일) 이내에 끝나려면
        #      일일 생산속도 >= urgent_tier1_phys_needed / 8.0 -> 월(20영업일) 필요능력 = urgent_tier1_phys_needed * 2.5
        #    - 또한 전체 현물 복구 물량(total_phys_needed)도 가급적 16영업일(준비 2일 + 생산 14일) 내 소화 목표
        req_monthly_for_tier1 = int(math.ceil(urgent_tier1_phys_needed / 8.0 * 20.0))
        req_monthly_for_total = int(math.ceil(total_phys_needed / 14.0 * 20.0))
        # Masil 수요 급증 시 안전재고 보충을 위해 추가 버퍼 확보
        masil_buffer_needed = int(round(4000 * (masil_surge_pct / 25.0))) if masil_surge_pct > 0 else 0

        target_monthly_cap = max(req_monthly_for_tier1, req_monthly_for_total) + masil_buffer_needed
        l02_free = 4873
        needed_extra = max(0, target_monthly_cap - l02_free)

        # 1000 단위 반올림 배정 (L-01 우선 투입 -> 한도 도달 시 L-03 자동 투입)
        raw_l01 = min(l01_max_limit, int(math.ceil(needed_extra / 500.0) * 500))
        rem_after_l01 = max(0, needed_extra - raw_l01)
        raw_l03 = min(l03_max_limit, int(math.ceil(rem_after_l01 / 500.0) * 500))

        return {
            "auto_l01_support_qty": raw_l01,
            "auto_l03_support_qty": raw_l03,
            "total_phys_needed": total_phys_needed,
            "urgent_tier1_phys_needed": urgent_tier1_phys_needed,
            "target_monthly_cap": target_monthly_cap,
        }

    def simulate_recovery_plans(self, triage_result, runtime_state):
        repo = self.repo
        params = runtime_state.get("sim_params", {})

        selected_plan = params.get("selected_plan", "PLAN_C")
        c101_force_100_physical = runtime_state.get("c101_force_100_physical", False)
        include_c105_reserve = params.get("include_c105_reserve", True)
        l01_support_qty = int(params.get("l01_support_qty", 12000))
        l03_support_qty = int(params.get("l03_support_qty", 0))
        default_physical_ratio = float(params.get("physical_replace_ratio", 0.60))
        l01_max_limit = int(runtime_state.get("l01_max_limit_qty", 16812))
        masil_surge_pct = float(runtime_state.get("masil_demand_surge_pct", 0.0))

        # L-01 설비 한도 제약 적용
        effective_l01_qty = min(l01_support_qty, l01_max_limit)

        # 1. Corevia 생산 라인 기초 능력 로드
        lines = []
        l02_monthly_free = 4873
        for r in repo.capacity:
            cap_yr = int(r["capacity_qty"])
            util = float(r["utilization_pct"])
            free_yr = int(round(cap_yr * (100.0 - util) / 100.0))
            free_mo = free_yr // 12
            if r["line_id"] == "L-02":
                l02_monthly_free = free_mo
            lines.append({
                "plant_id": r["plant_id"],
                "line_id": r["line_id"],
                "product_id": r["product_id"],
                "annual_capacity_qty": cap_yr,
                "baseline_utilization_pct": util,
                "annual_free_qty": free_yr,
                "monthly_free_qty": free_mo,
            })

        # 2. Masil 더마 SKU(PL-02) 기초 재고 및 발주 현황 로드 (수요 변동률 반영)
        inv_map = {r["sku_id"]: r for r in repo.masil_inventory}
        wsales_by_sku = defaultdict(list)
        for r in repo.masil_weekly_sales:
            wsales_by_sku[r["sku_id"]].append((r["week"], int(r["sold_qty"])))

        demand_mult = 1.0 + (masil_surge_pct / 100.0)
        masil_derma_skus = []
        for s in repo.masil_skus:
            if s["product_id"] == "PL-02":
                sid = s["sku_id"]
                inv = inv_map.get(sid, {})
                on_hand = int(inv.get("on_hand_qty", 0))
                in_trans = int(inv.get("in_transit_qty", 0))
                ws = sorted(wsales_by_sku[sid], key=lambda x: x[0])
                last4 = [x[1] for x in ws[-4:]]
                avg_wk_demand = (sum(last4) / 4.0 if last4 else 1.0) * demand_mult
                cover_wks = round(on_hand / avg_wk_demand, 2)
                po_list = [p for p in repo.masil_pos if p["sku_id"] == sid]
                po = po_list[0] if po_list else {}
                masil_derma_skus.append({
                    "sku_id": sid,
                    "sku_name": s["sku_name"],
                    "on_hand_qty": on_hand,
                    "in_transit_qty": in_trans,
                    "weekly_demand_avg": round(avg_wk_demand, 1),
                    "baseline_cover_weeks": cover_wks,
                    "safety_stock_min_weeks": int(s["safety_stock_weeks_min"]),
                    "moq": int(s["moq"]),
                    "po_id": po.get("po_id", "NONE"),
                    "po_order_date": po.get("order_date", ""),
                    "po_qty": int(po.get("order_qty", 0)),
                    "po_amount_krw": int(po.get("amount_krw", 0)),
                    "po_payment_due_date": po.get("payment_due_date", ""),
                })

        customer_tiers = triage_result["customer_tiers"]

        def build_plan_detail(plan_code):
            cust_schedules = []
            total_physical_qty = 0
            total_credit_qty = 0
            total_credit_krw = 0

            if plan_code == "PLAN_A":
                avail_monthly_cap = l02_monthly_free
                used_l01_qty = 0
                used_l03_qty = 0
            elif plan_code == "PLAN_B":
                masil_diverted_qty = 31649
                avail_monthly_cap = l02_monthly_free + masil_diverted_qty
                used_l01_qty = 0
                used_l03_qty = 0
            else:
                used_l01_qty = effective_l01_qty
                used_l03_qty = l03_support_qty
                avail_monthly_cap = l02_monthly_free + used_l01_qty + used_l03_qty

            priority_order = {"C-101": 1, "C-102": 2, "C-104": 3, "C-105": 4, "C-103": 5, "C-108": 6}
            sorted_custs = sorted(customer_tiers, key=lambda x: priority_order.get(x["customer_id"], 99))

            cumulative_physical = 0
            for c in sorted_custs:
                cid = c["customer_id"]
                unit_p = c["avg_unit_price_krw"]

                if plan_code in ("PLAN_A", "PLAN_B"):
                    target_qty = c["effective_recall_qty"]
                    phys_ratio = 1.0
                else:
                    if cid == "C-105" and not include_c105_reserve and c["tier"] == "TIER_2_MAPPING_GAP":
                        target_qty = 0
                    else:
                        target_qty = c["effective_recall_qty"]

                    if cid == "C-101" and c101_force_100_physical:
                        phys_ratio = 1.0
                    elif cid in ("C-101", "C-102"):
                        phys_ratio = max(default_physical_ratio, 0.65)
                    elif cid == "C-104":
                        phys_ratio = default_physical_ratio
                    else:
                        phys_ratio = min(default_physical_ratio, 0.50) if default_physical_ratio < 0.99 else 1.0

                phys_qty = int(round(target_qty * phys_ratio))
                cred_qty = target_qty - phys_qty
                cred_krw = cred_qty * unit_p

                cumulative_physical += phys_qty
                total_physical_qty += phys_qty
                total_credit_qty += cred_qty
                total_credit_krw += cred_krw

                daily_rate = max(avail_monthly_cap / 20.0, 1.0)
                if phys_qty == 0:
                    lead_biz_days = 0
                    promised_date = "해당없음(교체불필요/보류)"
                else:
                    prep_days = 2 if (used_l01_qty > 0 or used_l03_qty > 0) else 1
                    lead_biz_days = prep_days + max(1, int(round(cumulative_physical / daily_rate)))
                    promised_date = add_business_days(repo.as_of_date, lead_biz_days)

                if target_qty == 0:
                    churn_status = "정상(회수/교체 제외)"
                elif lead_biz_days <= 12:
                    churn_status = "방어성공(2주내 초도납품)"
                elif lead_biz_days <= 22:
                    churn_status = "주의(납기지연 협의필요)"
                else:
                    churn_status = "위험(2nd Vendor 이탈임박)"

                cust_schedules.append({
                    "customer_id": cid,
                    "customer_name": c["customer_name"],
                    "revenue_share_pct": c["revenue_share_pct"],
                    "so_trend_3m_pct": c["so_trend_3m_pct"],
                    "tier_label": c["tier_label"],
                    "target_recall_qty": target_qty,
                    "physical_replace_qty": phys_qty,
                    "credit_note_qty": cred_qty,
                    "credit_amount_krw": cred_krw,
                    "lead_biz_days": lead_biz_days,
                    "promised_ship_date": promised_date,
                    "churn_status": churn_status,
                })

            # PLAN_C에서 월 가용 능력을 초과하는 현물 수요가 발생하면,
            # Masil SKU-1003(배리어 로션)의 현재 커버가 3.8주 이상일 때만 분할 순연 허용
            shortfall_qty = max(0, total_physical_qty - avail_monthly_cap)
            sku1003_deferred_qty = 0
            sku1003_info = [m for m in masil_derma_skus if m["sku_id"] == "SKU-1003"]
            sku1003_cov = sku1003_info[0]["baseline_cover_weeks"] if sku1003_info else 0

            if plan_code == "PLAN_C" and shortfall_qty > 0 and sku1003_cov >= 3.8:
                sku1003_deferred_qty = min(shortfall_qty, 8000)
                avail_monthly_cap += sku1003_deferred_qty
                daily_rate = max(avail_monthly_cap / 20.0, 1.0)
                cum_p = 0
                for cs in cust_schedules:
                    if cs["physical_replace_qty"] > 0:
                        cum_p += cs["physical_replace_qty"]
                        cs["lead_biz_days"] = 2 + max(1, int(round(cum_p / daily_rate)))
                        cs["promised_ship_date"] = add_business_days(repo.as_of_date, cs["lead_biz_days"])
                        cs["churn_status"] = (
                            "방어성공(2주내 초도납품)" if cs["lead_biz_days"] <= 12 else "주의(납기지연 협의필요)"
                        )

            masil_impact = []
            stockout_sku_cnt = 0
            for msku in masil_derma_skus:
                sid = msku["sku_id"]
                base_cov = msku["baseline_cover_weeks"]
                wk_dem = msku["weekly_demand_avg"]

                if plan_code == "PLAN_A":
                    po_action = "납기 무기한 지연 (L-02 병목)"
                    proj_cov = round(max(0.0, (msku["on_hand_qty"] - wk_dem * 2) / wk_dem), 2)
                elif plan_code == "PLAN_B":
                    adj_in_transit = max(0, msku["in_transit_qty"] - 8000)
                    po_action = "SPO 입고 4주 순연 (B2B 차출)"
                    proj_cov = round(max(0.0, (msku["on_hand_qty"] + adj_in_transit * 0.2 - wk_dem * 2) / wk_dem), 2)
                else:
                    if sid == "SKU-1003" and sku1003_deferred_qty > 0:
                        po_action = f"SPO-0003 중 {sku1003_deferred_qty:,} EA만 2주 분할순연 (안전재고 유지)"
                        proj_cov = round(base_cov - (sku1003_deferred_qty / wk_dem) * 0.3, 2)
                    else:
                        # L-01/L-03 지원이 충분하면 정상 입고 보호, 부족하면 지연 영향 반영
                        unresolved_gap = max(0, total_physical_qty - avail_monthly_cap)
                        delay_penalty = (unresolved_gap / 20000.0) if unresolved_gap > 0 else 0.0
                        if delay_penalty > 0.3:
                            po_action = f"생산여력 부족({unresolved_gap:,} EA)으로 입고 일부 지연 위험"
                        else:
                            po_action = "긴급 방어 배정 (정상 입고 유지)"
                        proj_cov = round(max(0.5, base_cov + 1.1 - delay_penalty), 2)

                if proj_cov < 2.0:
                    stock_status = "품절위험(Stock-out 임박)"
                    stockout_sku_cnt += 1
                elif proj_cov < 3.5:
                    stock_status = "결품주의(안전재고 미달)"
                else:
                    stock_status = "안전재고 방어(정상)"

                masil_impact.append({
                    "sku_id": sid,
                    "sku_name": msku["sku_name"],
                    "po_id": msku["po_id"],
                    "weekly_demand_avg": wk_dem,
                    "baseline_cover_weeks": base_cov,
                    "projected_cover_weeks_2w": proj_cov,
                    "po_schedule_action": po_action,
                    "stock_status": stock_status,
                })

            line_impacts = []
            for ln in lines:
                lid = ln["line_id"]
                base_u = ln["baseline_utilization_pct"]
                ann_cap = ln["annual_capacity_qty"]
                free_m = ln["monthly_free_qty"]
                if lid == "L-01":
                    free_m = min(free_m, l01_max_limit)

                if lid == "L-02":
                    added_mo = l02_monthly_free
                elif lid == "L-01":
                    added_mo = used_l01_qty if plan_code == "PLAN_C" else 0
                elif lid == "L-03":
                    added_mo = used_l03_qty if plan_code == "PLAN_C" else 0
                else:
                    added_mo = 0

                new_u = min(100.0, round(base_u + (added_mo * 12 / ann_cap * 100.0), 1))
                line_impacts.append({
                    "plant_id": ln["plant_id"],
                    "line_id": lid,
                    "product_id": ln["product_id"],
                    "baseline_utilization_pct": base_u,
                    "monthly_free_qty": free_m,
                    "allocated_recovery_monthly_qty": added_mo,
                    "simulated_utilization_pct": new_u,
                })

            max_biz_days = max((cs["lead_biz_days"] for cs in cust_schedules), default=0)
            full_batch_months_if_overreact = round(299653 / l02_monthly_free, 1)

            return {
                "plan_code": plan_code,
                "total_target_recall_qty": total_physical_qty + total_credit_qty,
                "total_physical_replace_qty": total_physical_qty,
                "total_credit_note_qty": total_credit_qty,
                "total_credit_amount_krw": total_credit_krw,
                "available_monthly_recovery_cap_qty": avail_monthly_cap,
                "used_l01_support_qty": used_l01_qty,
                "used_l03_support_qty": used_l03_qty,
                "sku1003_deferred_qty": sku1003_deferred_qty,
                "max_recovery_lead_biz_days": max_biz_days,
                "full_sbl_overreaction_months": full_batch_months_if_overreact,
                "masil_stockout_sku_cnt": stockout_sku_cnt,
                "customer_schedules": cust_schedules,
                "masil_sku_impacts": masil_impact,
                "line_utilization_impacts": line_impacts,
            }

        plan_a = build_plan_detail("PLAN_A")
        plan_b = build_plan_detail("PLAN_B")
        plan_c = build_plan_detail("PLAN_C")

        plans_map = {"PLAN_A": plan_a, "PLAN_B": plan_b, "PLAN_C": plan_c}
        active_plan = plans_map.get(selected_plan, plan_c)

        # AI 추천 대안 자동 판정 (조건이 바뀌었을 때 왜 이 대안이 최적인지 동적 평가)
        c101_c = [c for c in plan_c["customer_schedules"] if c["customer_id"] == "C-101"]
        c101_lead = c101_c[0]["lead_biz_days"] if c101_c else 0
        if plan_c["masil_stockout_sku_cnt"] == 0 and c101_lead <= 12:
            ai_recommendation = "PLAN_C (최적 균형 달성: C-101 2주 내 납기 + Masil 전 SKU 품절 방어)"
        elif plan_c["masil_stockout_sku_cnt"] > 0:
            ai_recommendation = "PLAN_C + L-03 추가전환 권고 (Masil 수요급증/설비제약으로 인한 결품 위험 감지)"
        else:
            ai_recommendation = "PLAN_C + L-01/L-03 증량 권고 (B2B 초도 납기 12영업일 초과 위험 감지)"

        return {
            "selected_plan_code": selected_plan,
            "ai_recommendation": ai_recommendation,
            "active_plan": active_plan,
            "comparison": {
                "PLAN_A": plan_a,
                "PLAN_B": plan_b,
                "PLAN_C": plan_c,
            },
        }
