from collections import defaultdict


class OntologyRulesEngine:
    """
    W03 온톨로지 및 동적 재판단 규칙 엔진
    - Rule 0 (과잉대응 차단): 루머/미확정 클레임 분리 및 동일 원료 로트(LOT-B-2602-P) 내 정상 배치 제외
    - Rule 1~3 (필수 전문성 확장): 배치 불량률 10% 기준 동적 재판정(판정 정정·신규 클레임 유입 반영)
      + SBL↔SH↔QC 4자 대사 기반 3-Tier 고객/출하 분류
    """

    def __init__(self, repo):
        self.repo = repo

    def evaluate_triage_and_traceability(self, runtime_state):
        repo = self.repo
        extra_claims = runtime_state.get("injected_claims", [])
        claim_adjustments = runtime_state.get("batch_claim_adjustments", {})
        c105_mapping_verified = runtime_state.get("c105_mapping_verified", False)
        c103_audit_qty = int(runtime_state.get("c103_unsold_audit_qty", 0))
        c108_audit_qty = int(runtime_state.get("c108_unsold_audit_qty", 0))
        lot_reinspection_status = runtime_state.get("lot_reinspection_status", "보류(선투입위험)")

        all_claims = list(repo.claims) + list(extra_claims)

        # 1. SBL 배치별 집계
        sbl_by_batch = defaultdict(list)
        for s in repo.sbl:
            sbl_by_batch[s["batch_id"]].append(s)

        # 2. 클레임 배치별 집계
        claims_by_batch = defaultdict(list)
        for c in all_claims:
            claims_by_batch[c["batch_id"]].append(c)

        # 3. 배치별 불량률 동적 계산 (판정 정정 delta 반영)
        batch_evaluations = {}
        reclassified_batches = []

        for b in repo.batches:
            b_id = b["batch_id"]
            prod_qty = int(b["produced_qty"])
            b_sbls = sbl_by_batch.get(b_id, [])
            sbl_qty = sum(int(x["shipped_qty"]) for x in b_sbls)
            b_claims = claims_by_batch.get(b_id, [])

            conf_c = [c for c in b_claims if str(c["defect_confirmed"]) == "True"]
            unconf_c = [c for c in b_claims if str(c["defect_confirmed"]) != "True"]
            base_conf_qty = sum(int(c["qty_affected"]) for c in conf_c)
            unconf_qty = sum(int(c["qty_affected"]) for c in unconf_c)

            # 조건 변경: 배치별 확정 클레임 정정/추가 수량(delta) 반영
            adj_delta = int(claim_adjustments.get(b_id, 0))
            conf_qty = max(0, base_conf_qty + adj_delta)
            if adj_delta < 0:
                # 오판 정정으로 확정에서 제외된 수량은 소명종결/미확정으로 이동
                unconf_qty += abs(adj_delta)

            base_rate_prod = (base_conf_qty / prod_qty * 100.0) if prod_qty > 0 else 0.0
            rate_vs_prod = (conf_qty / prod_qty * 100.0) if prod_qty > 0 else 0.0
            rate_vs_ship = (conf_qty / sbl_qty * 100.0) if sbl_qty > 0 else 0.0

            was_recall_target = (base_conf_qty > 0) and (base_rate_prod >= 10.0)
            is_recall_target = (conf_qty > 0) and (rate_vs_prod >= 10.0 or rate_vs_ship >= 10.0)

            if was_recall_target != is_recall_target:
                reclassified_batches.append({
                    "batch_id": b_id,
                    "before_target": was_recall_target,
                    "after_target": is_recall_target,
                    "before_rate_pct": round(base_rate_prod, 2),
                    "after_rate_pct": round(rate_vs_prod, 2),
                    "delta_qty": adj_delta,
                })

            if is_recall_target:
                saved_st = runtime_state.get("batch_statuses", {}).get(b_id)
                if saved_st and ("회수" in saved_st or "의결" in saved_st):
                    op_status = saved_st
                else:
                    op_status = f"회수대상 판정(불량률 {rate_vs_prod:.2f}% ≥ 10%)"
            elif was_recall_target and not is_recall_target:
                op_status = f"회수해제·판정정정(불량률 {rate_vs_prod:.2f}% < 10%)"
            elif "LOT-B-2602-P" in b["input_lot_ids"]:
                op_status = "정상출하(동일로트_합격_회수제외)"
            elif conf_qty > 0:
                op_status = "정상출하(경미확정_<10%_종결)"
            elif unconf_qty > 0:
                op_status = "조사·소명대상(미확정클레임)"
            else:
                op_status = "정상"

            batch_evaluations[b_id] = {
                "batch_id": b_id,
                "product_id": b["product_id"],
                "production_line": b["production_line"],
                "production_date": b["production_date"],
                "produced_qty": prod_qty,
                "sbl_shipped_qty": sbl_qty,
                "unmapped_prod_diff_qty": prod_qty - sbl_qty,
                "input_lot_ids": b["input_lot_ids"],
                "qc_result": b["qc_result"],
                "confirmed_claim_cnt": len(conf_c) + (1 if adj_delta > 0 else 0),
                "unconfirmed_claim_cnt": len(unconf_c),
                "base_confirmed_defect_qty": base_conf_qty,
                "claim_adjustment_delta_qty": adj_delta,
                "confirmed_defect_qty": conf_qty,
                "unconfirmed_claim_qty": unconf_qty,
                "defect_rate_prod_pct": round(rate_vs_prod, 2),
                "defect_rate_ship_pct": round(rate_vs_ship, 2),
                "was_recall_target": was_recall_target,
                "is_recall_target": is_recall_target,
                "operational_status": op_status,
            }

        confirmed_recall_claims = []
        confirmed_minor_claims = []
        unconfirmed_claims = []
        for c in all_claims:
            b_eval = batch_evaluations.get(c["batch_id"], {})
            if str(c["defect_confirmed"]) == "True":
                if b_eval.get("is_recall_target"):
                    confirmed_recall_claims.append(c)
                else:
                    confirmed_minor_claims.append(c)
            else:
                unconfirmed_claims.append(c)

        # 4. LOT-B-2602-P 4개 배치 비교
        lot_b2602p_batches = [
            batch_evaluations[b["batch_id"]]
            for b in repo.batches
            if "LOT-B-2602-P" in b["input_lot_ids"]
        ]
        lot_b2602p_batches.sort(key=lambda x: x["batch_id"])

        recall_batches = [b for b in batch_evaluations.values() if b["is_recall_target"]]
        recall_batches.sort(key=lambda x: x["batch_id"])

        excluded_same_lot_batches = [
            b for b in lot_b2602p_batches if not b["is_recall_target"]
        ]
        saved_overreaction_prod_qty = sum(b["produced_qty"] for b in excluded_same_lot_batches)
        saved_overreaction_ship_qty = sum(b["sbl_shipped_qty"] for b in excluded_same_lot_batches)

        # 5. 회수 대상 배치들의 고객별 SBL 출하 vs 확정 클레임 vs SH 매출출하 3-Tier 분류
        recall_batch_ids = {b["batch_id"] for b in recall_batches}

        cust_matrix = defaultdict(lambda: {
            "sbl_by_batch": defaultdict(int),
            "sbl_records": [],
            "claims_by_batch": defaultdict(int),
            "claim_cnt": 0,
            "claim_records": [],
        })

        # LOT-B-2602-P 관련 주요 고객들을 기본 추적 풀에 유지하되, 실제 유효 회수량은 is_recall_target 배치만 산입!
        for b in lot_b2602p_batches:
            b_id = b["batch_id"]
            is_target = b["is_recall_target"]
            base_b_conf = b["base_confirmed_defect_qty"]
            adj_b_conf = b["confirmed_defect_qty"]
            scale_factor = (adj_b_conf / base_b_conf) if base_b_conf > 0 else 1.0

            for s in sbl_by_batch.get(b_id, []):
                cid = s["customer_id"]
                if is_target:
                    cust_matrix[cid]["sbl_by_batch"][b_id] += int(s["shipped_qty"])
                    cust_matrix[cid]["sbl_records"].append(s)

            for c in claims_by_batch.get(b_id, []):
                if str(c["defect_confirmed"]) == "True":
                    cid = c["customer_id"]
                    if is_target:
                        scaled_q = int(round(int(c["qty_affected"]) * scale_factor))
                        cust_matrix[cid]["claims_by_batch"][b_id] += scaled_q
                        cust_matrix[cid]["claim_cnt"] += 1
                        cust_matrix[cid]["claim_records"].append(c)

            # 만약 기존에 클레임이 0건이던 정상 배치(예: B-02-2602-03)에 신규 확정 클레임(adj_delta > 0)이 주입되어 회수대상이 된 경우
            if is_target and base_b_conf == 0 and adj_b_conf > 0:
                b_sbls = sbl_by_batch.get(b_id, [])
                tot_b_sbl = sum(int(x["shipped_qty"]) for x in b_sbls) or 1
                for s in b_sbls:
                    cid = s["customer_id"]
                    alloc_c = int(round(adj_b_conf * (int(s["shipped_qty"]) / tot_b_sbl)))
                    cust_matrix[cid]["claims_by_batch"][b_id] += alloc_c
                    cust_matrix[cid]["claim_cnt"] += 1

        so_pl02_by_cust_month = defaultdict(lambda: defaultdict(int))
        for r in repo.so:
            if r["product_id"] == "PL-02" and r["order_date"] >= "2026-01-01":
                so_pl02_by_cust_month[r["customer_id"]][r["order_date"][:7]] += int(r["order_qty"])

        sh_pl02_feb_mar = defaultdict(list)
        for r in repo.sh:
            if r["product_id"] == "PL-02" and r["ship_date"][:7] in ("2026-02", "2026-03"):
                sh_pl02_feb_mar[r["customer_id"]].append(r)

        customer_tiers = []
        for cid in sorted(cust_matrix.keys()):
            c_info = repo.customer_map.get(cid, {})
            m = cust_matrix[cid]
            tot_sbl = sum(m["sbl_by_batch"].values())
            tot_claim = sum(m["claims_by_batch"].values())
            unit_price = repo.pl02_unit_price_by_cust.get(cid, 9000)

            so_mar = so_pl02_by_cust_month[cid].get("2026-03", 0)
            so_jun = so_pl02_by_cust_month[cid].get("2026-06", 0)
            so_trend_pct = round((so_jun - so_mar) / so_mar * 100.0, 1) if so_mar > 0 else 0.0

            if tot_sbl > 0 and tot_claim > 0:
                tier = "TIER_1_CONFIRMED"
                tier_label = "Tier 1: 출하·클레임 교차확정 (즉시 복구)"
                mapping_status = "SBL 출하 & QC 클레임 정합 완료"
                effective_recall_qty = tot_claim
            elif tot_sbl == 0 and tot_claim > 0:
                if c105_mapping_verified:
                    tier = "TIER_1_VERIFIED_FROM_GAP"
                    tier_label = "Tier 1 (매핑복구완료): 물류원장 대조 확정"
                    mapping_status = "미매핑 생산차액(11,825 EA) & SH 원장 대조로 SBL 누락 복구됨"
                    effective_recall_qty = tot_claim
                else:
                    tier = "TIER_2_MAPPING_GAP"
                    tier_label = "Tier 2: 데이터 공백 (SBL 누락 · 가배정 보류)"
                    mapping_status = f"QC 확정클레임({tot_claim:,} EA) 존재하나 SBL 출하 0건 → 미매핑 차액 역추적 중"
                    effective_recall_qty = tot_claim
            else:
                audit_qty = c103_audit_qty if cid == "C-103" else (c108_audit_qty if cid == "C-108" else 0)
                if audit_qty > 0:
                    tier = "TIER_3_AUDIT_CONFIRMED"
                    tier_label = f"Tier 3 (실사회신반영): 창고 미판매분 {audit_qty:,} EA 교체"
                    mapping_status = f"클레임 0건이나 고객 창고 실사로 미판매 재고 {audit_qty:,} EA 확인됨"
                    effective_recall_qty = audit_qty
                else:
                    tier = "TIER_3_PREVENTIVE_AUDIT"
                    tier_label = "Tier 3: 예방적 재고 실사 대상 (클레임 0건)"
                    mapping_status = f"문제 배치 SBL 출하({tot_sbl:,} EA) 존재하나 클레임 0건 → 고객 창고 잔여재고 실사 요청"
                    effective_recall_qty = 0

            customer_tiers.append({
                "customer_id": cid,
                "customer_name": c_info.get("customer_name", cid),
                "channel_type": c_info.get("channel_type", ""),
                "revenue_share_pct": float(c_info.get("revenue_share_pct", 0)),
                "cost_linked_clause": c_info.get("cost_linked_clause") == "True",
                "payment_terms_days": int(c_info.get("payment_terms_days", 45)),
                "avg_unit_price_krw": unit_price,
                "b2602_01_sbl_qty": m["sbl_by_batch"].get("B-02-2602-01", 0),
                "b2602_01_claim_qty": m["claims_by_batch"].get("B-02-2602-01", 0),
                "b2603_01_sbl_qty": m["sbl_by_batch"].get("B-02-2603-01", 0),
                "b2603_01_claim_qty": m["claims_by_batch"].get("B-02-2603-01", 0),
                "total_sbl_qty": tot_sbl,
                "total_confirmed_claim_qty": tot_claim,
                "claim_cnt": m["claim_cnt"],
                "customer_defect_rate_pct": round(tot_claim / tot_sbl * 100.0, 2) if tot_sbl > 0 else None,
                "so_2026_03_qty": so_mar,
                "so_2026_06_qty": so_jun,
                "so_trend_3m_pct": so_trend_pct,
                "tier": tier,
                "tier_label": tier_label,
                "mapping_status": mapping_status,
                "effective_recall_qty": effective_recall_qty,
                "sh_feb_mar_candidates": sh_pl02_feb_mar.get(cid, [])[:8],
            })

        c105_sh_feb = [r for r in sh_pl02_feb_mar.get("C-105", []) if r["ship_date"].startswith("2026-02")]
        c105_sh_mar = [r for r in sh_pl02_feb_mar.get("C-105", []) if r["ship_date"].startswith("2026-03")]
        c105_gap_analysis = {
            "customer_id": "C-105",
            "customer_name": "더뷰티클럽",
            "confirmed_claims_b2602_01": 5320,
            "confirmed_claims_b2603_01": 6445,
            "total_confirmed_claims_qty": 11765,
            "sbl_recorded_qty": 0,
            "unmapped_batch_diff_b2602_01": 150745 - 145860,
            "unmapped_batch_diff_b2603_01": 160733 - 153793,
            "total_unmapped_batch_diff_qty": (150745 - 145860) + (160733 - 153793),
            "diff_vs_claim_residual_EA": 11825 - 11765,
            "sh_feb_2026_total_qty": sum(int(x["shipped_qty"]) for x in c105_sh_feb),
            "sh_mar_2026_total_qty": sum(int(x["shipped_qty"]) for x in c105_sh_mar),
            "sh_candidate_records": (c105_sh_feb + c105_sh_mar)[:10],
            "verification_status": "VERIFIED" if c105_mapping_verified else "HOLD_PENDING_CONFIRMATION",
        }

        total_confirmed_recall_qty = sum(b["confirmed_defect_qty"] for b in recall_batches)

        return {
            "as_of_date": repo.as_of_date,
            "reclassified_batches": reclassified_batches,
            "lot_inspection_alert": {
                "lot_id": "LOT-B-2602-P",
                "material_id": "M-B (더마 활성원료)",
                "supplier_id": "V-205 (단독 공급처)",
                "receipt_date": "2026-02-06",
                "inspection_date": "2026-02-09",
                "inspection_result": lot_reinspection_status,
                "received_qty_kg": 807.9,
                "pre_receipt_issue": "B-02-2602-01 배치가 원료 입고일(02-06)·검사일(02-09) 이전인 2026-02-05에 선투입됨",
            },
            "triage_funnel": {
                "total_claims_cnt": len(all_claims),
                "total_claims_qty": sum(int(c["qty_affected"]) for c in all_claims),
                "confirmed_recall_claims_cnt": len(confirmed_recall_claims),
                "confirmed_recall_claims_qty": total_confirmed_recall_qty,
                "confirmed_minor_claims_cnt": len(confirmed_minor_claims),
                "confirmed_minor_claims_qty": sum(int(c["qty_affected"]) for c in confirmed_minor_claims),
                "unconfirmed_claims_cnt": len(unconfirmed_claims),
                "unconfirmed_claims_qty": sum(int(c["qty_affected"]) for c in unconfirmed_claims),
                "lot_b2602p_total_prod_qty": sum(b["produced_qty"] for b in lot_b2602p_batches),
                "recall_target_prod_qty": sum(b["produced_qty"] for b in recall_batches),
                "saved_overreaction_prod_qty": saved_overreaction_prod_qty,
                "saved_overreaction_ship_qty": saved_overreaction_ship_qty,
                "saved_overreaction_value_krw": saved_overreaction_ship_qty * 9000,
            },
            "lot_b2602p_batches": lot_b2602p_batches,
            "recall_batches": recall_batches,
            "customer_tiers": customer_tiers,
            "c105_gap_analysis": c105_gap_analysis,
        }
