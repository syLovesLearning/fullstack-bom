"""两个直观真实的演示 BOM：1) 定制金属工业工作台 (PROD-DESK-01)  2) 四层重型仓储货架 (PROD-RACK-01)。"""

from typing import Any

SEED_ITEMS: list[dict[str, Any]] = [
    # --- 成品 ---
    {"sku_code": "PROD-DESK-01", "name": "定制金属工业工作台", "category": "PRODUCT", "sub_type": "STANDARD", "unit": "张", "base_price": 0.0},
    {"sku_code": "PROD-RACK-01", "name": "四层重型仓储货架", "category": "PRODUCT", "sub_type": "STANDARD", "unit": "组", "base_price": 0.0},
    # --- 半成品 ---
    {"sku_code": "SEMI-DESK-FRAME", "name": "焊接钢制桌架(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0},
    {"sku_code": "SEMI-RACK-UPRIGHT", "name": "货架立柱片组件(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "片", "base_price": 0.0},
    {"sku_code": "SEMI-RACK-LAYER", "name": "货架单层横梁层板(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "层", "base_price": 0.0},
    # --- 基材 (固定 / 非固定) ---
    {"sku_code": "MAT-WOOD-25", "name": "25mm实木橡木桌面(整板3.0㎡)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "㎡", "base_price": 260.0},
    {"sku_code": "MAT-TUBE-40", "name": "40×40镀锌方管(整根6m)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "m", "base_price": 28.0},
    {"sku_code": "MAT-BEAM-MID", "name": "桌面防塌腰加强横梁", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "根", "base_price": 45.0},
    {"sku_code": "MAT-C-STEEL", "name": "80×60C型钢立柱(整根6m)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "m", "base_price": 42.0},
    {"sku_code": "MAT-BEAM-ORANGE", "name": "重型抱焊橙色横梁", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "m", "base_price": 36.0},
    {"sku_code": "MAT-DECK-STEEL", "name": "镀锌钢制层板(整张2.4㎡)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "㎡", "base_price": 115.0},
    # --- 外购五金 ---
    {"sku_code": "OUT-FOOT-PAD", "name": "重型防滑调节脚垫+角码包", "category": "OUTSOURCED", "sub_type": "FIXED", "unit": "套", "base_price": 38.0},
    {"sku_code": "OUT-ANCHOR-BOLT", "name": "膨胀地脚螺栓+安全插销套组", "category": "OUTSOURCED", "sub_type": "FIXED", "unit": "套", "base_price": 32.0},
    # --- 人工 (内 / 外) & 机械 ---
    {"sku_code": "LAB-WELD-INT", "name": "车间下料与氩弧焊接(人工-内)", "category": "LABOR", "sub_type": "INTERNAL", "unit": "工时", "base_price": 65.0},
    {"sku_code": "LAB-SPRAY-EXT", "name": "外协静电喷塑烤漆(人工-外)", "category": "LABOR", "sub_type": "EXTERNAL", "unit": "㎡", "base_price": 35.0},
    {"sku_code": "MAC-CNC-EDGE", "name": "数控开孔与封边台班(机械)", "category": "MACHINE", "sub_type": "SPECIAL_PROCESS", "unit": "台班", "base_price": 90.0},
]

DEMO_RELATIONS: list[tuple[Any, ...]] = [
    # 1. 定制金属工业工作台 (H=桌高750, W=桌长1600, D=桌深800, T=板厚25)
    ("PROD-DESK-01", "SEMI-DESK-FRAME", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
    ("PROD-DESK-01", "MAT-WOOD-25", "FORMULA_3D", 1.28, "(W * D) / 1000000.0", "iif(W >= 1800, 80, 0)", "THRESHOLD_SCRAP", 3.0, 0.6, 0.0, 1.0, "材料", "基材"),
    ("PROD-DESK-01", "OUT-FOOT-PAD", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
    ("PROD-DESK-01", "MAC-CNC-EDGE", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "机械", "人工费"),
    ("SEMI-DESK-FRAME", "MAT-TUBE-40", "FORMULA_3D", 6.2, "(4 * H + 2 * W + 2 * D) / 1000.0", "", "WHOLE_PACK", 6.0, 0.0, 0.05, 1.0, "材料", "基材"),
    ("SEMI-DESK-FRAME", "MAT-BEAM-MID", "FORMULA_3D", 1.0, "iif(W >= 1500, 2, 1)", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
    ("SEMI-DESK-FRAME", "LAB-WELD-INT", "FORMULA_3D", 1.5, "iif(W >= 1500, 2.2, 1.5)", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
    ("SEMI-DESK-FRAME", "LAB-SPRAY-EXT", "FORMULA_3D", 1.4, "(4 * H + 2 * W) * 0.16 / 1000.0", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),

    # 2. 四层重型仓储货架 (H=架高2000, W=跨宽1800, D=架深600)
    ("PROD-RACK-01", "SEMI-RACK-UPRIGHT", "FIXED", 2.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
    ("PROD-RACK-01", "SEMI-RACK-LAYER", "FIXED", 4.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
    ("PROD-RACK-01", "OUT-ANCHOR-BOLT", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
    ("PROD-RACK-01", "LAB-WELD-INT", "FIXED", 2.5, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
    ("SEMI-RACK-UPRIGHT", "MAT-C-STEEL", "FORMULA_3D", 4.0, "(2 * H) / 1000.0", "", "THRESHOLD_SCRAP", 6.0, 1.0, 0.03, 1.0, "材料", "基材"),
    ("SEMI-RACK-UPRIGHT", "LAB-SPRAY-EXT", "FORMULA_3D", 1.2, "(2 * H * 0.28) / 1000.0", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
    ("SEMI-RACK-LAYER", "MAT-BEAM-ORANGE", "FORMULA_3D", 3.6, "(2 * W) / 1000.0", "iif(W >= 2000, 60, 0)", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
    ("SEMI-RACK-LAYER", "MAT-DECK-STEEL", "FORMULA_3D", 1.08, "(W * D) / 1000000.0", "", "THRESHOLD_SCRAP", 2.4, 0.4, 0.0, 1.0, "材料", "基材"),
]
