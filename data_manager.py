"""
data_manager.py — Unified data layer.

Two modes:
  LOCAL  — reads/writes a local JSON file (data.json). Works immediately, no setup.
  SHEETS — reads/writes Google Sheets. Optional; for cloud persistence & sharing.
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import Any

LOCAL_FILE = "data.json"

SCHEMAS: dict[str, list[str]] = {
    "Issues":      ["Title", "Description", "Priority", "Owner", "Due", "Status", "Created"],
    "Agenda":      ["Person", "Topic", "Category", "AddedBy", "Discussed", "Created"],
    "ActionItems": ["Task", "Owner", "Due", "Source", "Status", "Created"],
    "Calendar":    ["Title", "Date", "Time", "Type", "With", "Notes"],
    "Reference":   ["Title", "Category", "Content", "Explanation", "Tags", "Created"],
    "Notes":       ["Title", "Tags", "LinkedTo", "Body", "Created"],
    "Config":      ["Key", "Value"],
}


# ── Local JSON backend ────────────────────────────────────────────────────────

def _load_local() -> dict:
    if os.path.exists(LOCAL_FILE):
        with open(LOCAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {k: {"columns": v, "rows": []} for k, v in SCHEMAS.items()}


def _save_local(data: dict):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class LocalManager:
    """Stores everything in a local data.json file."""

    def get_data(self, sheet: str) -> pd.DataFrame:
        data = _load_local()
        sheet_data = data.get(sheet, {"columns": SCHEMAS.get(sheet, []), "rows": []})
        rows = sheet_data.get("rows", [])
        cols = sheet_data.get("columns", SCHEMAS.get(sheet, []))
        return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)

    def append_row(self, sheet: str, row_dict: dict):
        data = _load_local()
        if sheet not in data:
            data[sheet] = {"columns": SCHEMAS.get(sheet, list(row_dict.keys())), "rows": []}
        cols = data[sheet]["columns"]
        row = [row_dict.get(c, "") for c in cols]
        data[sheet]["rows"].append(row)
        _save_local(data)

    def update_cell(self, sheet: str, df_index: int, column: str, value: Any):
        data = _load_local()
        if sheet not in data:
            return
        cols = data[sheet]["columns"]
        try:
            col_idx = cols.index(column)
        except ValueError:
            return
        if df_index < len(data[sheet]["rows"]):
            data[sheet]["rows"][df_index][col_idx] = value
        _save_local(data)

    def delete_row(self, sheet: str, df_index: int):
        data = _load_local()
        if sheet in data and df_index < len(data[sheet]["rows"]):
            data[sheet]["rows"].pop(df_index)
        _save_local(data)

    def get_direct_reports(self) -> list[str]:
        df = self.get_data("Config")
        if df.empty or "Key" not in df.columns:
            return []
        row = df[df["Key"] == "DirectReports"]
        if row.empty:
            return []
        val = row.iloc[0].get("Value", "")
        return [x.strip() for x in str(val).split(",") if x.strip()]

    def add_direct_report(self, name: str):
        data = _load_local()
        cfg = data.get("Config", {"columns": ["Key", "Value"], "rows": []})
        for row in cfg["rows"]:
            if row[0] == "DirectReports":
                current = [x.strip() for x in str(row[1]).split(",") if x.strip()]
                if name not in current:
                    current.append(name)
                    row[1] = ", ".join(current)
                _save_local(data)
                return
        cfg["rows"].append(["DirectReports", name])
        data["Config"] = cfg
        _save_local(data)


# ── Google Sheets backend ─────────────────────────────────────────────────────

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsManager:
    """Stores everything in a Google Sheets spreadsheet."""

    def __init__(self, creds_dict: dict, spreadsheet_id: str):
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread is not installed. Run: pip install gspread google-auth")
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self._gc = gspread.authorize(creds)
        self._sh = self._gc.open_by_key(spreadsheet_id)

    def ensure_worksheets(self):
        existing = {ws.title for ws in self._sh.worksheets()}
        for name, cols in SCHEMAS.items():
            if name not in existing:
                ws = self._sh.add_worksheet(title=name, rows=1000, cols=max(len(cols), 10))
                ws.append_row(cols)

    def _ws(self, name: str):
        return self._sh.worksheet(name)

    def get_data(self, sheet: str) -> pd.DataFrame:
        ws = self._ws(sheet)
        records = ws.get_all_records(default_blank="")
        return pd.DataFrame(records) if records else pd.DataFrame(columns=SCHEMAS.get(sheet, []))

    def append_row(self, sheet: str, row_dict: dict):
        ws = self._ws(sheet)
        cols = SCHEMAS.get(sheet, list(row_dict.keys()))
        row = [row_dict.get(c, "") for c in cols]
        ws.append_row(row, value_input_option="USER_ENTERED")

    def update_cell(self, sheet: str, df_index: int, column: str, value: Any):
        ws = self._ws(sheet)
        cols = SCHEMAS.get(sheet, [])
        try:
            col_idx = cols.index(column) + 1
        except ValueError:
            header = ws.row_values(1)
            col_idx = header.index(column) + 1
        ws.update_cell(df_index + 2, col_idx, value)

    def delete_row(self, sheet: str, df_index: int):
        ws = self._ws(sheet)
        ws.delete_rows(df_index + 2)

    def get_direct_reports(self) -> list[str]:
        ws = self._ws("Config")
        records = ws.get_all_records(default_blank="")
        for r in records:
            if r.get("Key") == "DirectReports":
                val = r.get("Value", "")
                return [x.strip() for x in str(val).split(",") if x.strip()]
        return []

    def add_direct_report(self, name: str):
        ws = self._ws("Config")
        records = ws.get_all_records(default_blank="")
        for i, r in enumerate(records):
            if r.get("Key") == "DirectReports":
                current = [x.strip() for x in str(r.get("Value","")).split(",") if x.strip()]
                if name not in current:
                    current.append(name)
                    ws.update_cell(i + 2, 2, ", ".join(current))
                return
        ws.append_row(["DirectReports", name])
