import csv
import os
from collections import defaultdict

BASE_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "01_참가자_배포용", "04_원본데이터")
)


def read_pipe_csv(rel_path):
    full_path = os.path.join(BASE_DATA_DIR, rel_path)
    with open(full_path, mode="r", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="|"))


def read_md_text(rel_path):
    full_path = os.path.join(BASE_DATA_DIR, rel_path)
    with open(full_path, mode="r", encoding="utf-8") as f:
        return f.read()


class DataRoomRepository:
    """원본 데이터룸(04_원본데이터)을 수정 없이 로드하고 계보(Lineage)를 추적하는 저장소."""

    def __init__(self):
        self.as_of_date = "2026-07-01"
        self.reload()

    def reload(self):
        self.lots = read_pipe_csv(r"01_corevia\procurement\material_lot_master_cv.csv")
        self.batches = read_pipe_csv(r"01_corevia\production\prod_batch_log_cv.csv")
        self.claims = read_pipe_csv(r"01_corevia\quality\qc_claims_cv.csv")
        self.sbl = read_pipe_csv(r"01_corevia\quality\shipment_batch_link_cv.csv")
        self.sh = read_pipe_csv(r"01_corevia\sales\sales_shipments_cv.csv")
        self.so = read_pipe_csv(r"01_corevia\sales\sales_orders_cv.csv")
        self.customers = read_pipe_csv(r"01_corevia\master\m_customer_cv.csv")
        self.products = read_pipe_csv(r"01_corevia\master\m_product_cv.csv")
        self.materials = read_pipe_csv(r"01_corevia\master\m_material_cv.csv")
        self.capacity = read_pipe_csv(r"01_corevia\production\strat_capacity_cv.csv")

        self.masil_skus = read_pipe_csv(r"02_masil\master\m_sku_ms.csv")
        self.masil_inventory = read_pipe_csv(r"02_masil\inventory\sku_inventory_ms.csv")
        self.masil_pos = read_pipe_csv(r"02_masil\inventory\sc_purchase_orders_ms.csv")
        self.masil_weekly_sales = read_pipe_csv(r"02_masil\inventory\sku_weekly_sales_ms.csv")

        self.quality_policy_md = read_md_text(r"01_corevia\quality\quality_policy_cv.md")
        self.approval_policy_md = read_md_text(r"00_common\approval_authority_policy.md")
        self.ext_news_md = read_md_text(r"05_external\news\ext_news_quality_incident.md")
        self.sales_notes_md = read_md_text(r"01_corevia\sales\sales_meeting_notes_cv.md")

        # 인덱싱
        self.customer_map = {c["customer_id"]: c for c in self.customers}
        self.product_map = {p["product_id"]: p for p in self.products}
        self.batch_map = {b["batch_id"]: b for b in self.batches}
        self.lot_map = {l["lot_id"]: l for l in self.lots}

        # 고객별 PL-02 평균 출하 단가 산출 (크레딧/재무 영향 계산용)
        cust_rev = defaultdict(int)
        cust_qty = defaultdict(int)
        for r in self.sh:
            if r["product_id"] == "PL-02" and r["ship_date"] >= "2026-01-01":
                cid = r["customer_id"]
                cust_rev[cid] += int(r["revenue_krw"])
                cust_qty[cid] += int(r["shipped_qty"])
        self.pl02_unit_price_by_cust = {}
        for cid, q in cust_qty.items():
            self.pl02_unit_price_by_cust[cid] = round(cust_rev[cid] / q) if q > 0 else 9000

    def get_lineage_summary(self):
        return [
            {
                "file": "01_corevia/quality/qc_claims_cv.csv",
                "type": "원본 기록 (거래/품질 증거)",
                "rows": len(self.claims),
                "key_cols": "claim_id, batch_id, lot_id, customer_id, defect_confirmed, qty_affected, status",
                "usage": "배치별 확정 불량 수량 집계 및 미확정(False) 조사 대상 분리"
            },
            {
                "file": "01_corevia/production/prod_batch_log_cv.csv",
                "type": "원본 기록 (생산 증거)",
                "rows": len(self.batches),
                "key_cols": "batch_id, product_id, production_date, produced_qty, input_lot_ids, qc_result",
                "usage": "회수 판단 단위(배치) 생산량 모수 산정 및 원료 로트(LOT-B-2602-P) 투입 추적"
            },
            {
                "file": "01_corevia/quality/shipment_batch_link_cv.csv",
                "type": "원본 기록 (품질 출하 연결)",
                "rows": len(self.sbl),
                "key_cols": "shipment_id(SBL-*), batch_id, customer_id, order_date, ship_date, shipped_qty",
                "usage": "회수 대상 배치의 고객별 출하 수량 특정 및 미매핑 생산 차액(11,825 EA) 탐지"
            },
            {
                "file": "01_corevia/sales/sales_shipments_cv.csv & sales_orders_cv.csv",
                "type": "원본 기록 (매출 출하 / 수주)",
                "rows": f"SH: {len(self.sh):,} / SO: {len(self.so):,}",
                "key_cols": "shipment_id(SH-*), order_id(SO-*), customer_id, ship_date, shipped_qty, revenue_krw",
                "usage": "SBL 누락 고객(C-105) 역추적 대조 및 피해 고객(C-101, C-104) 수주 급감(-53%) 추세 검증"
            },
            {
                "file": "01_corevia/production/strat_capacity_cv.csv",
                "type": "원본 기록 (생산능력 제약)",
                "rows": len(self.capacity),
                "key_cols": "plant_id(F1/F2), line_id(L-01~13), product_id, capacity_qty, utilization_pct",
                "usage": "더마 전용 라인(F1 L-02, 가동률 97%, 월 여유 4,873 EA) 병목 확인 및 타 라인 전환 시뮬레이션"
            },
            {
                "file": "02_masil/inventory/sku_inventory_ms.csv & sc_purchase_orders_ms.csv",
                "type": "원본 기록 (계열사 유통 재고/발주)",
                "rows": f"INV: {len(self.masil_inventory)} / PO: {len(self.masil_pos)}",
                "key_cols": "sku_id(SKU-1001~1004), on_hand_qty, stock_cover_weeks, po_id(SPO-0001~0004)",
                "usage": "Corevia PL-02에 100% 의존하는 Masil 더마 SKU 결품 위험(커버 2.21~2.92주) 동시 방어"
            },
            {
                "file": "01_corevia/quality/quality_policy_cv.md & 00_common/approval_authority_policy.md",
                "type": "원본 정책 (업무 규칙/권한 경계)",
                "rows": "정책 문서 2종",
                "key_cols": "defect_confirmed=True & 불량률≥10% 회수, 품질위원회/영업임원/SCM 권한",
                "usage": "과잉 대응 차단 규칙 및 사람 승인(HITL) 게이트웨이 경계 정의"
            }
        ]
