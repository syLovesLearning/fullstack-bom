"""BOM 公式求值器与余料阈值核算的离线单元测试（纯函数，不依赖数据库）。"""

import math

from src.services.bom_formula import calc_remnant_qty, dist3d, eval_formula_with_error, safe_eval_formula


class TestSafeEvalFormula:
    def test_empty_expr_returns_fallback(self) -> None:
        assert safe_eval_formula("", {"H": 1.0}) == 0.0
        assert safe_eval_formula("   ", {"H": 1.0}) == 0.0
        assert safe_eval_formula("", {}, fallback=-1.0) == -1.0

    def test_arithmetic_precedence(self) -> None:
        assert safe_eval_formula("1 + 2 * 3", {}) == 7.0
        assert safe_eval_formula("(1 + 2) * 3", {}) == 9.0
        assert safe_eval_formula("-3 + 5", {}) == 2.0
        assert safe_eval_formula("10 % 3", {}) == 1.0

    def test_variables_from_env(self) -> None:
        assert safe_eval_formula("H * W / 1000000.0", {"H": 2000.0, "W": 1000.0}) == 2.0

    def test_unknown_variable_returns_fallback(self) -> None:
        assert safe_eval_formula("XYZ + 1", {"H": 1.0}) == 0.0
        assert safe_eval_formula("XYZ + 1", {}, fallback=-99.0) == -99.0

    def test_iif_conditional(self) -> None:
        assert safe_eval_formula("iif(W >= 1000, 120, 0)", {"W": 1200.0}) == 120.0
        assert safe_eval_formula("iif(W >= 1000, 120, 0)", {"W": 800.0}) == 0.0
        assert safe_eval_formula("iif(H > 0 and W > 0, 1, 2)", {"H": 2.0, "W": 3.0}) == 1.0

    def test_dist3d_and_math_funcs(self) -> None:
        assert dist3d(0, 0, 0, 3, 4, 0) == 5.0
        # dist3d(0, 80, 0, 100, 20, 0) = sqrt(100^2 + (-60)^2) = sqrt(13600)
        assert math.isclose(
            safe_eval_formula("dist3d(0, H*0.8, 0, W, H*0.2, D)", {"H": 100.0, "W": 100.0, "D": 0.0}),
            math.sqrt(13600.0),
        )
        assert safe_eval_formula("ceil(1.2)", {}) == 2.0
        assert safe_eval_formula("floor(1.8)", {}) == 1.0
        assert safe_eval_formula("min(3, 5)", {}) == 3.0
        assert safe_eval_formula("max(3, 5)", {}) == 5.0
        assert safe_eval_formula("abs(-2.5)", {}) == 2.5

    def test_illegal_syntax_returns_fallback(self) -> None:
        # 幂运算符未在白名单中
        assert safe_eval_formula("H ** 2", {"H": 3.0}) == 0.0
        # 危险调用必须被拒绝（不抛异常、不执行）
        assert safe_eval_formula("__import__('os').getcwd()", {}) == 0.0
        # 函数名不在白名单
        assert safe_eval_formula("eval('1+1')", {}) == 0.0
        # 语法错误
        assert safe_eval_formula("1 +", {}) == 0.0

    def test_result_is_float(self) -> None:
        res = safe_eval_formula("2 * 3", {})
        assert isinstance(res, float)
        assert math.isfinite(res)


class TestEvalFormulaWithError:
    def test_valid_expr_returns_value_and_empty_error(self) -> None:
        value, err = eval_formula_with_error("(2*(H*W+H*D+W*D)/1000000.0)*T*7.85", {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0})
        assert err == ""
        # 2*(1760000+1320000+480000)/1e6 × 2 × 7.85 = 111.784
        assert math.isclose(value, 111.784, rel_tol=1e-6)  # type: ignore[arg-type]

    def test_invalid_expr_returns_error_message(self) -> None:
        value, err = eval_formula_with_error("H ** 2", {"H": 3.0})
        assert value is None
        assert "无法求值" in err

    def test_empty_expr_returns_error(self) -> None:
        value, err = eval_formula_with_error("  ", {})
        assert value is None
        assert err == "公式为空"


class TestCalcRemnantQty:
    def test_continuous_policy_keeps_raw_qty(self) -> None:
        bill, scrap, note = calc_remnant_qty(13.5, 200.0, "CONTINUOUS", 50.0)
        assert (bill, scrap, note) == (13.5, 0.0, "")

    def test_non_positive_qty_passthrough(self) -> None:
        assert calc_remnant_qty(0.0, 200.0, "WHOLE_PACK", 50.0) == (0.0, 0.0, "")

    def test_zero_pack_size_passthrough(self) -> None:
        assert calc_remnant_qty(180.0, 0.0, "WHOLE_PACK", 50.0) == (180.0, 0.0, "")

    def test_whole_pack_rounds_up_and_reports_scrap(self) -> None:
        bill, scrap, note = calc_remnant_qty(180.0, 200.0, "WHOLE_PACK", 50.0)
        assert bill == 200.0
        assert scrap == 20.0
        assert "整料计价" in note and "20" in note

    def test_whole_pack_exact_no_scrap(self) -> None:
        bill, scrap, note = calc_remnant_qty(400.0, 200.0, "WHOLE_PACK", 50.0)
        assert (bill, scrap, note) == (400.0, 0.0, "")

    def test_threshold_scrap_when_below_min(self) -> None:
        bill, scrap, note = calc_remnant_qty(180.0, 200.0, "THRESHOLD_SCRAP", 50.0)
        assert bill == 200.0
        assert scrap == 20.0
        assert "整块报废" in note

    def test_threshold_keep_when_above_min(self) -> None:
        bill, scrap, note = calc_remnant_qty(180.0, 200.0, "THRESHOLD_SCRAP", 10.0)
        assert bill == 180.0
        assert scrap == 0.0
        assert "留库" in note
