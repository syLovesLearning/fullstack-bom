"""BOM 演示种子数据：示例机柜多级 BOM（物料清单与父子关系定义）。"""

from typing import Any

SEED_ITEMS: list[dict[str, Any]] = [
    {"sku_code": "PROD-GGD-01", "name": "GGD标准低压配电柜", "category": "PRODUCT", "sub_type": "STANDARD", "unit": "台", "base_price": 0.0},
    {"sku_code": "SEMI-FRAME-01", "name": "柜体钣金骨架(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0},
    {"sku_code": "SEMI-DRAWER-01", "name": "标准抽屉单元(半成品)", "category": "SEMI_FINISHED", "sub_type": "STANDARD", "unit": "套", "base_price": 0.0},
    {"sku_code": "MAT-STEEL-2MM", "name": "2.0mm冷轧钢板(整块200kg)", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "kg", "base_price": 5.8},
    {"sku_code": "MAT-COPPER-BAR", "name": "TMY主母线铜排", "category": "BASE_MATERIAL", "sub_type": "NON_FIXED", "unit": "kg", "base_price": 86.0},
    {"sku_code": "OUT-BREAKER-250", "name": "塑壳断路器3P-250A(外购)", "category": "OUTSOURCED", "sub_type": "FIXED", "unit": "台", "base_price": 680.0},
    {"sku_code": "LAB-INT-ASSY", "name": "内部装配与二次接线(人工-内)", "category": "LABOR", "sub_type": "INTERNAL", "unit": "工时", "base_price": 65.0},
    {"sku_code": "LAB-EXT-PAINT", "name": "外协静电喷塑(人工-外/特殊工艺)", "category": "LABOR", "sub_type": "EXTERNAL", "unit": "㎡", "base_price": 35.0},
    {"sku_code": "MAC-LASER-CUT", "name": "光纤激光切割台班(机械)", "category": "MACHINE", "sub_type": "SPECIAL_PROCESS", "unit": "台班", "base_price": 180.0},
]

# (父SKU, 子SKU, 计量模式, 基础用量, 3D公式, 附加成本公式, 余料策略, 整包量, 余料阈值, 损耗率, 浮动系数, BOM分组, 成本分组)
DEMO_RELATIONS: list[tuple[str, str, str, float, str, str, str, float, float, float, float, str, str]] = [
    ("PROD-GGD-01", "SEMI-FRAME-01", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
    ("PROD-GGD-01", "SEMI-DRAWER-01", "FIXED", 2.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "半成品"),
    ("PROD-GGD-01", "MAT-COPPER-BAR", "FORMULA_3D", 14.5, "(dist3d(0, H*0.8, 0, W*0.9, H*0.2, D*0.8) / 1000.0) * 6.8", "iif(W >= 1000, 120, 0)", "CONTINUOUS", 1.0, 0.0, 0.05, 1.0, "材料", "基材"),
    ("PROD-GGD-01", "OUT-BREAKER-250", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "材料", "基材"),
    ("PROD-GGD-01", "LAB-INT-ASSY", "FIXED", 4.5, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
    ("PROD-GGD-01", "MAC-LASER-CUT", "FIXED", 1.0, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "机械", "人工费"),
    ("SEMI-FRAME-01", "MAT-STEEL-2MM", "FORMULA_3D", 180.0, "(2*(H*W + H*D + W*D) / 1000000.0) * T * 7.85", "", "THRESHOLD_SCRAP", 200.0, 50.0, 0.0, 1.0, "材料", "基材"),
    ("SEMI-FRAME-01", "LAB-EXT-PAINT", "FORMULA_3D", 9.6, "(2*(H*W + H*D) / 1000000.0) * 1.4", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
    ("SEMI-DRAWER-01", "MAT-STEEL-2MM", "FIXED", 13.5, "", "", "CONTINUOUS", 1.0, 0.0, 0.08, 1.0, "材料", "基材"),
    ("SEMI-DRAWER-01", "LAB-INT-ASSY", "FIXED", 1.2, "", "", "CONTINUOUS", 1.0, 0.0, 0.0, 1.0, "人工", "人工费"),
]
