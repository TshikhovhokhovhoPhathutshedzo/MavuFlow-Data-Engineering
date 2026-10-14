import ast
import json
import operator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.core.config import settings

MAX_CODE_LENGTH = 12_000
MAX_SYNTAX_NODES = 3_000

_SAFE_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "round": round,
    "str": str,
    "sum": sum,
}

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left.isin(right) if isinstance(left, (pd.Series, pd.Index)) else left in right,
    ast.NotIn: lambda left, right: ~(left.isin(right)) if isinstance(left, (pd.Series, pd.Index)) else left not in right,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.invert,
}

_PANDAS_API = SimpleNamespace(
    NA=pd.NA,
    cut=pd.cut,
    isna=pd.isna,
    notna=pd.notna,
    to_datetime=pd.to_datetime,
    to_numeric=pd.to_numeric,
)

_NUMPY_API = SimpleNamespace(
    abs=np.abs,
    ceil=np.ceil,
    floor=np.floor,
    inf=np.inf,
    isfinite=np.isfinite,
    isnan=np.isnan,
    log=np.log,
    maximum=np.maximum,
    minimum=np.minimum,
    nan=np.nan,
    round=np.round,
    select=np.select,
    sqrt=np.sqrt,
    where=np.where,
)

_SAFE_ATTRIBUTES = {
    "NA", "abs", "agg", "aggregate", "astype", "between", "ceil", "clip", "columns", "copy", "count",
    "cut",
    "drop", "drop_duplicates", "dropna", "duplicated", "dt", "fillna", "groupby",
    "floor", "head", "iloc", "index", "inf", "isfinite", "isin", "isna", "isnan", "items", "iterrows", "loc", "log", "lower",
    "map", "mask", "max", "mean", "median", "min", "month", "nunique", "notna",
    "maximum", "minimum", "nan", "quantile", "rename", "replace", "reset_index", "round", "select", "shape", "size", "sort_index",
    "sort_values", "std", "str", "strip", "sum", "tail", "title", "upper", "value_counts",
    "sqrt", "to_datetime", "to_numeric", "var", "where", "year", "day", "contains", "startswith", "endswith",
}

_SAFE_NODE_TYPES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.Pass,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set,
    ast.BinOp, ast.UnaryOp, ast.Compare, ast.Subscript, ast.Slice,
    ast.Call, ast.Attribute, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.BitAnd, ast.BitOr, ast.BitXor,
    ast.UAdd, ast.USub, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)


class _CodeValidator(ast.NodeVisitor):
    def __init__(self, tree: ast.Module) -> None:
        self.assignable_names = {"df"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            else:
                continue
            for target in targets:
                self._validate_target(target)

    def _validate_target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            if target.id in {"pd", "np"} or target.id.startswith("_"):
                raise ValueError(f"Cannot assign to reserved name '{target.id}'")
            self.assignable_names.add(target.id)
            return
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "df":
            return
        raise ValueError("Assignments are limited to variables and DataFrame columns")

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _SAFE_NODE_TYPES):
            raise ValueError(f"Unsupported Python syntax: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        available = {"df", "pd", "np", *_SAFE_BUILTINS, *self.assignable_names}
        if node.id.startswith("_") or node.id not in available:
            raise ValueError(f"Name '{node.id}' is not available in the code environment")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_") or node.attr not in _SAFE_ATTRIBUTES:
            raise ValueError(f"Attribute '{node.attr}' is not available in the code environment")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in _SAFE_BUILTINS:
                raise ValueError(f"Function '{node.func.id}' is not available in the code environment")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr not in _SAFE_ATTRIBUTES:
                raise ValueError(f"Function '{node.func.attr}' is not available in the code environment")
        else:
            raise ValueError("Only approved pandas, NumPy, and basic functions can be called")
        if any(keyword.arg is None for keyword in node.keywords):
            raise ValueError("Keyword unpacking is not supported")
        self.generic_visit(node)


class CodeExecutionService:
    def __init__(self, root_path: str | None = None) -> None:
        self.root_path = Path(root_path or settings.storage_root).resolve()

    def execute(self, storage_key: str, code: str, *, save: bool = False) -> dict[str, Any]:
        if len(code) > MAX_CODE_LENGTH:
            raise ValueError(f"Code exceeds the {MAX_CODE_LENGTH:,}-character limit")
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ValueError(f"Syntax error on line {exc.lineno}: {exc.msg}") from exc
        if sum(1 for _ in ast.walk(tree)) > MAX_SYNTAX_NODES:
            raise ValueError("Code contains too many syntax nodes")

        _CodeValidator(tree).visit(tree)
        dataframe = self._read_dataframe(storage_key)
        namespace: dict[str, Any] = {"df": dataframe.copy(), "pd": _PANDAS_API, "np": _NUMPY_API, **_SAFE_BUILTINS}
        try:
            for statement in tree.body:
                if isinstance(statement, ast.Pass):
                    continue
                if isinstance(statement, ast.Expr):
                    self._evaluate(statement.value, namespace)
                    continue
                if isinstance(statement, ast.Assign):
                    value = self._evaluate(statement.value, namespace)
                    for target in statement.targets:
                        self._assign(target, value, namespace)
                    continue
                if isinstance(statement, ast.AugAssign):
                    current = self._evaluate(statement.target, namespace)
                    operation = _SAFE_OPERATORS.get(type(statement.op))
                    if operation is None:
                        raise ValueError("Unsupported arithmetic operator")
                    self._assign(statement.target, operation(current, self._evaluate(statement.value, namespace)), namespace)
        except Exception as exc:
            raise ValueError(f"Code execution failed: {exc}") from exc
        result = namespace.get("df")
        if not isinstance(result, pd.DataFrame):
            raise ValueError("Your code must leave a pandas DataFrame named 'df'")

        response: dict[str, Any] = {
            "status": "saved" if save else "preview",
            "saved": save,
            "row_count": int(len(result)),
            "column_count": int(len(result.columns)),
            "columns": [str(column) for column in result.columns],
            "preview": json.loads(result.head(20).to_json(orient="records", date_format="iso")),
        }
        if save:
            source_path = (self.root_path / storage_key).resolve()
            version_dir = source_path.parent.parent / "versions"
            version_dir.mkdir(parents=True, exist_ok=True)
            output_path = version_dir / f"manual_code_{uuid4().hex}.csv"
            result.to_csv(output_path, index=False)
            response["output_path"] = output_path.relative_to(self.root_path).as_posix()
        return response

    def _assign(self, target: ast.expr, value: Any, namespace: dict[str, Any]) -> None:
        if isinstance(target, ast.Name):
            namespace[target.id] = value
            return
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "df":
            key = self._evaluate(target.slice, namespace)
            namespace["df"][key] = value
            return
        raise ValueError("Assignments are limited to variables and DataFrame columns")

    def _evaluate(self, node: ast.expr, namespace: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in namespace:
                raise ValueError(f"Name '{node.id}' has not been assigned")
            return namespace[node.id]
        if isinstance(node, ast.List):
            return [self._evaluate(item, namespace) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._evaluate(item, namespace) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self._evaluate(item, namespace) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {self._evaluate(key, namespace): self._evaluate(value, namespace) for key, value in zip(node.keys, node.values)}
        if isinstance(node, ast.Slice):
            return slice(
                self._evaluate(node.lower, namespace) if node.lower else None,
                self._evaluate(node.upper, namespace) if node.upper else None,
                self._evaluate(node.step, namespace) if node.step else None,
            )
        if isinstance(node, ast.Subscript):
            return self._evaluate(node.value, namespace)[self._evaluate(node.slice, namespace)]
        if isinstance(node, ast.Attribute):
            return getattr(self._evaluate(node.value, namespace), node.attr)
        if isinstance(node, ast.BinOp):
            operation = _SAFE_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported arithmetic operator")
            return operation(self._evaluate(node.left, namespace), self._evaluate(node.right, namespace))
        if isinstance(node, ast.UnaryOp):
            operation = _SAFE_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported unary operator")
            return operation(self._evaluate(node.operand, namespace))
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ValueError("Chained comparisons are not supported; compare one pair at a time")
            operation = _SAFE_OPERATORS.get(type(node.ops[0]))
            if operation is None:
                raise ValueError("Unsupported comparison operator")
            return operation(self._evaluate(node.left, namespace), self._evaluate(node.comparators[0], namespace))
        if isinstance(node, ast.Call):
            function = self._evaluate(node.func, namespace)
            arguments = [self._evaluate(argument, namespace) for argument in node.args]
            keywords = {keyword.arg: self._evaluate(keyword.value, namespace) for keyword in node.keywords}
            return function(*arguments, **keywords)
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    def _read_dataframe(self, storage_key: str) -> pd.DataFrame:
        resolved_path = (self.root_path / storage_key).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {storage_key}")
        suffix = resolved_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(resolved_path)
        if suffix == ".xlsx":
            return pd.read_excel(resolved_path)
        raise ValueError(f"Unsupported dataset file type: {suffix}")


code_execution_service = CodeExecutionService()