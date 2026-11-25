import streamlit as st
import pandas as pd
from datetime import datetime, date
from data_manager import SheetsManager

st.set_page_config(page_title="Dashboard", page_icon="📋", layout="wide")

st.markdown("""
<style>
    [data-testid="metric-container"] {
        background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem;
    }
    .stTabs [data-baseweb="tab"] { border-radius:8px 8px 0 0; padding:8px 20px; font-weight:500; }
    .section-header {
        font-size:1.1rem; font-weight:700;
        border-left:4px solid #6366f1; padding-left:10px; margin:0.5rem 0 0.75rem;
    }
    #MainMenu, footer { visibility:hidden; }
    .block-container { padding-top:1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── password ──────────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("## 🔒 Dashboard")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            if username == "admin" and password == "admin218":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect username or password.")
    st.stop()


# ── connection ────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Connecting to Google Sheets...")
def get_manager():
    sid   = st.secrets["sheet_id"]
    creds = dict(st.secrets["gcp_service_account"])
    sm    = SheetsManager(creds, sid)
    sm.ensure_worksheets()
    return sm

try:
    _sm = get_manager()
except Exception as e:
    st.error(f"❌ Could not connect to Google Sheets: {e}")
    st.stop()


def dm() -> SheetsManager:
    return get_manager()


def get_data(sheet: str) -> pd.DataFrame:
    key = f"_data_{sheet}"
    if key not in st.session_state:
        st.session_state[key] = get_manager().get_data(sheet)
    return st.session_state[key]


def invalidate(sheet: str):
    key = f"_data_{sheet}"
    if key in st.session_state:
        del st.session_state[key]


def save(fn, *args, sheet: str = None, success_msg="Saved!", **kwargs):
    try:
        fn(*args, **kwargs)
        if sheet:
            invalidate(sheet)
        if success_msg:
            st.toast(success_msg)
        st.rerun()
    except Exception as e:
        st.error(f"❌ {e}")


def add_delete_col(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "Delete", False)
    return df


def resolve_image_url(url: str) -> str:
    """Convert share URLs to direct image URLs."""
    import re
    url = url.strip()
    m = re.search(r"/file/d/([^/]+)", url)
    if m:
        return f"https://drive.google.com/uc?id={m.group(1)}"
    m = re.match(r"https?://imgur\.com/([a-zA-Z0-9]+)$", url)
    if m:
        return f"https://i.imgur.com/{m.group(1)}.png"
    return url


def is_image_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


def image_upload_widget(uploader_key: str, target_key: str):
    """File uploader + button that uploads to Drive and stores the link in session_state[target_key]."""
    folder_id = st.secrets.get("drive_folder_id", "")
    uploaded = st.file_uploader("Or upload an image", type=["png","jpg","jpeg","gif","webp"], key=uploader_key, label_visibility="collapsed")
    if uploaded is not None and st.button("📤 Upload image", key=f"{uploader_key}_btn"):
        if not folder_id:
            st.error("drive_folder_id not configured in secrets.")
        else:
            try:
                link = dm().upload_file_to_drive(uploaded.read(), uploaded.name, uploaded.type, folder_id)
                st.session_state[target_key] = link
                st.toast("Uploaded!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Upload failed: {e}")


def files_upload_widget(uploader_key: str, target_key: str):
    """File uploader (multi) + label + button that uploads to Drive and appends links."""
    folder_id = st.secrets.get("drive_folder_id", "")
    uploaded_files = st.file_uploader("Upload files", accept_multiple_files=True, key=uploader_key, label_visibility="collapsed")
    if uploaded_files:
        label = st.text_input("Label for this file (optional)", key=f"{uploader_key}_label",
                              placeholder="e.g. Temp Daily Performance Dashboard")
        if st.button("📤 Upload", key=f"{uploader_key}_btn"):
            if not folder_id:
                st.error("drive_folder_id not configured in secrets.")
            else:
                new_lines = []
                for f in uploaded_files:
                    try:
                        link = dm().upload_file_to_drive(f.read(), f.name, f.type, folder_id)
                        clean_name = label.strip() if label.strip() else f.name.replace("_", " ").split("(")[0].strip()
                        display_label = f"{clean_name} (Google Drive: andover_files)"
                        new_lines.append(f"{display_label}: {link}")
                    except Exception as e:
                        st.error(f"❌ Failed to upload {f.name}: {e}")
                if new_lines:
                    current = st.session_state.get(target_key, "")
                    st.session_state[target_key] = (current + "\n" + "\n".join(new_lines)).strip()
                    st.toast(f"Uploaded {len(new_lines)} file(s)!")
                    st.rerun()


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Dashboard")
    st.success("☁️ Google Sheets connected")
    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("_data_"):
                del st.session_state[k]
        st.rerun()
    st.caption(f"Refreshed: {datetime.now().strftime('%H:%M')}")


# ── header ────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Dashboard")
c0, c_status = st.columns([4, 1])
c0.caption(date.today().strftime("%A, %B %d, %Y"))
c_status.success("☁️ Connected")

try:
    _i = get_data("Issues")
    _a = get_data("ActionItems")
    open_issues     = int((_i["Status"] == "Open").sum())           if not _i.empty and "Status" in _i.columns else 0
    high_pri        = int(((_i["Status"] == "Open") & (_i["Priority"] == "High")).sum()) if not _i.empty else 0
    pending_actions = int((_a["Status"] == "Pending").sum())        if not _a.empty and "Status" in _a.columns else 0
    k1, k2, k3 = st.columns(3)
    k1.metric("🔴 Open Issues",    open_issues)
    k2.metric("⚡ High Priority",   high_pri)
    k3.metric("✅ Pending Actions", pending_actions)
except Exception as e:
    st.warning(f"Could not load summary: {e}")

st.markdown("---")

tabs = st.tabs([
    "☑️ TODO",
    "🔴 Issues",
    "✅ Action Items",
    "🗒 Meetings",
    "🏗️ Projects",
    "🔍 Data Pulls",
    "🗄️ Data Issues",
    "📋 Procedures",
    "✔️ Resolutions",
    "📝 Notes",
])
tab_todo, tab_issues, tab_actions, tab_meetings, tab_projects, tab_datapulls, tab_dataissues, tab_procedures, tab_resolutions, tab_notes = tabs


# ═══════════════════════════════════════════════════════════════════════════════
# TODO
# ═══════════════════════════════════════════════════════════════════════════════
with tab_todo:
    st.markdown('<div class="section-header">TODO</div>', unsafe_allow_html=True)

    # ── Add form ──────────────────────────────────────────────────────────────
    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Add a task**")
        new_task = st.text_input("Task", key="todo_input", placeholder="What needs doing?", label_visibility="collapsed")
        td_due_col, td_empty = st.columns([2, 3])
        new_due = td_due_col.date_input("Due date (optional)", value=None, key="todo_due")
        new_comments = st.text_area("How we solved it (optional)", key="todo_comments", height=68,
                                    placeholder="Any extra context, links, or notes...")
        if st.button("➕ Add", type="primary", use_container_width=True) and new_task.strip():
            save(dm().append_row, "TODO", {
                "Task": new_task.strip(), "Done": "No", "Created": str(date.today()),
                "DueDate": str(new_due) if new_due else "",
                "HowWeSolvedIt": new_comments.strip(),
            }, sheet="TODO", success_msg=None)

    st.markdown("---")

    try:
        from streamlit_sortables import sort_items
        _sortables_ok = True
    except ImportError:
        _sortables_ok = False

    df = get_data("TODO")
    if df.empty:
        st.info("Nothing here yet — add your first task above.")
    else:
        pending = df[df["Done"] == "No"].reset_index(drop=False) if "Done" in df.columns else df.reset_index(drop=False)
        done_df = df[df["Done"] == "Yes"].reset_index(drop=False) if "Done" in df.columns else pd.DataFrame()
        if not done_df.empty and "Created" in done_df.columns:
            done_df = done_df.sort_values("Created", ascending=False)

        # ── Auto-assign Order values if missing ───────────────────────────────
        _order_col_missing = "Order" not in pending.columns
        if not _order_col_missing and (pending["Order"].isna().all() or (pending["Order"].astype(str).str.strip() == "").all()):
            try:
                for i, (_, row) in enumerate(pending.iterrows()):
                    dm().update_cell("TODO", int(row["index"]), "Order", i)
                invalidate("TODO")
                df = get_data("TODO")
                pending = df[df["Done"] == "No"].reset_index(drop=False)
            except Exception:
                _order_col_missing = True  # column not in sheet yet, skip ordering
        if _order_col_missing:
            st.info("💡 Add an **Order** column header to the end of your TODO sheet in Google Sheets to enable drag-and-drop ordering, then refresh.")
            _sortables_ok = False  # fall back to plain view

        # Sort by Order, falling back to Created
        try:
            pending["_order"] = pd.to_numeric(pending["Order"], errors="coerce").fillna(999)
            pending = pending.sort_values("_order").drop(columns=["_order"])
        except Exception:
            if "Created" in pending.columns:
                pending = pending.sort_values("Created", ascending=False)

        if pending.empty:
            st.success("🎉 All done!")
        elif _sortables_ok:
            # ── Drag-and-drop card view ───────────────────────────────────────
            today_str = str(date.today())

            def _card_label(row):
                due = row.get("DueDate", "")
                due_part = f"  📅 {due}" if due else ""
                overdue = due and due < today_str
                prefix = "🔴 " if overdue else ""
                return f"{prefix}{row.get('Task','')}{due_part}"

            card_labels = [_card_label(r) for _, r in pending.iterrows()]
            # Map label → orig_idx (labels must be unique for sortables)
            label_to_idx = {}
            for i, (_, row) in enumerate(pending.iterrows()):
                lbl = card_labels[i]
                # Deduplicate if identical task names exist
                base = lbl
                counter = 1
                while lbl in label_to_idx:
                    lbl = f"{base} ({counter})"
                    counter += 1
                card_labels[i] = lbl
                label_to_idx[lbl] = int(row["index"])

            st.caption("☰ Drag cards to reorder — click **Save order** to persist")
            sorted_labels = sort_items(card_labels, direction="vertical", key="todo_sort")

            if st.button("💾 Save order", key="todo_save_order", type="primary"):
                for new_pos, lbl in enumerate(sorted_labels):
                    orig_idx = label_to_idx.get(lbl)
                    if orig_idx is not None:
                        dm().update_cell("TODO", orig_idx, "Order", new_pos)
                invalidate("TODO")
                st.toast("Order saved!")
                st.rerun()

            st.markdown("---")
            # Reorder pending to match sorted_labels for displaying detail cards
            lbl_order = {lbl: i for i, lbl in enumerate(sorted_labels)}
            pending_rows = list(pending.iterrows())
            pending_rows.sort(key=lambda x: lbl_order.get(
                next((l for l, idx in label_to_idx.items() if idx == int(x[1]["index"])), ""), 999
            ))

            for _, row in pending_rows:
                orig_idx = int(row["index"])
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([5, 1, 1, 1, 1])
                    due_str = row.get("DueDate", "")
                    due_label = ""
                    if due_str:
                        due_label = f" &nbsp;<small style='color:{'#ef4444' if due_str < today_str else '#94a3b8'}'>📅 {due_str}</small>"
                    c1.markdown(
                        f"**{row.get('Task','')}**{due_label} "
                        f"<small style='color:#cbd5e1'>&nbsp;{row.get('Created','')}</small>",
                        unsafe_allow_html=True
                    )
                    if row.get("HowWeSolvedIt","").strip():
                        c1.caption(row["HowWeSolvedIt"])

                    if c2.button("✓", key=f"td_done_{orig_idx}", use_container_width=True, help="Mark done"):
                        dm().update_cell("TODO", orig_idx, "Done", "Yes")
                        invalidate("TODO")
                        st.rerun()
                    if c3.button("✏️", key=f"td_edit_{orig_idx}", use_container_width=True, help="Edit"):
                        st.session_state[f"editing_todo_{orig_idx}"] = not st.session_state.get(f"editing_todo_{orig_idx}", False)
                        st.rerun()
                    if c4.button("📋", key=f"td_promo_{orig_idx}", use_container_width=True, help="Promote to Resolution"):
                        st.session_state[f"promote_todo_{orig_idx}"] = True
                        st.rerun()
                    if c5.button("🗑", key=f"td_del_{orig_idx}", use_container_width=True, help="Delete"):
                        dm().delete_row("TODO", orig_idx)
                        invalidate("TODO")
                        st.rerun()

                    if st.session_state.get(f"editing_todo_{orig_idx}"):
                        e_task = st.text_input("Task", value=row.get("Task",""), key=f"td_val_{orig_idx}")
                        e_due_default = None
                        try:
                            import datetime as _dt
                            if row.get("DueDate",""):
                                e_due_default = _dt.date.fromisoformat(str(row["DueDate"]))
                        except Exception:
                            pass
                        e_due = st.date_input("Due date", value=e_due_default, key=f"td_edue_{orig_idx}")
                        e_comments = st.text_area("How we solved it", value=row.get("HowWeSolvedIt",""), key=f"td_ecmt_{orig_idx}", height=68)
                        s1, s2 = st.columns(2)
                        if s1.button("💾 Save", key=f"td_sv_{orig_idx}", use_container_width=True):
                            if e_task.strip() != row.get("Task",""):
                                dm().update_cell("TODO", orig_idx, "Task", e_task.strip())
                            new_due_str = str(e_due) if e_due else ""
                            if new_due_str != str(row.get("DueDate","")):
                                dm().update_cell("TODO", orig_idx, "DueDate", new_due_str)
                            if e_comments.strip() != str(row.get("HowWeSolvedIt","")):
                                dm().update_cell("TODO", orig_idx, "HowWeSolvedIt", e_comments.strip())
                            st.session_state[f"editing_todo_{orig_idx}"] = False
                            invalidate("TODO")
                            st.rerun()
                        if s2.button("Cancel", key=f"td_cancel_{orig_idx}", use_container_width=True):
                            st.session_state[f"editing_todo_{orig_idx}"] = False
                            st.rerun()

                    if st.session_state.get(f"promote_todo_{orig_idx}"):
                        st.markdown("**📋 Promote to Resolution**")
                        pr_title  = st.text_input("Resolution title", value=row.get("Task",""), key=f"pr_t_{orig_idx}")
                        pr_prob   = st.text_area("Problem description", value=row.get("HowWeSolvedIt",""), key=f"pr_p_{orig_idx}", height=80, placeholder="What was the problem?")
                        pr_steps  = st.text_area("What was tried", key=f"pr_s_{orig_idx}", height=80, placeholder="Steps taken / things attempted...")
                        pr_sol    = st.text_area("What fixed it", key=f"pr_sol_{orig_idx}", height=80, placeholder="The resolution or answer")
                        pr_tags   = st.text_input("Tags", key=f"pr_tags_{orig_idx}", placeholder="e.g. data, pipeline")
                        pr_mark_done = st.checkbox("Also mark this TODO as done", value=True, key=f"pr_done_{orig_idx}")
                        pb1, pb2 = st.columns(2)
                        if pb1.button("✅ Create Resolution", key=f"pr_go_{orig_idx}", use_container_width=True, type="primary"):
                            dm().append_row("Resolutions", {
                                "Title": pr_title.strip(), "Problem": pr_prob.strip(),
                                "Steps": pr_steps.strip(), "Solution": pr_sol.strip(),
                                "Tags": pr_tags.strip(), "Created": str(date.today()),
                            })
                            invalidate("Resolutions")
                            if pr_mark_done:
                                dm().update_cell("TODO", orig_idx, "Done", "Yes")
                                invalidate("TODO")
                            st.session_state[f"promote_todo_{orig_idx}"] = False
                            st.toast("Resolution created!")
                            st.rerun()
                        if pb2.button("Cancel", key=f"pr_cancel_{orig_idx}", use_container_width=True):
                            st.session_state[f"promote_todo_{orig_idx}"] = False
                            st.rerun()
        else:
            # ── Fallback: original card view without drag (sortables not installed) ──
            today_str = str(date.today())
            for _, row in pending.iterrows():
                orig_idx = int(row["index"])
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([5, 1, 1, 1, 1])
                    due_str = row.get("DueDate", "")
                    due_label = ""
                    if due_str:
                        due_label = f" &nbsp;<small style='color:{'#ef4444' if due_str < today_str else '#94a3b8'}'>📅 {due_str}</small>"
                    c1.markdown(
                        f"**{row.get('Task','')}**{due_label} "
                        f"<small style='color:#cbd5e1'>&nbsp;{row.get('Created','')}</small>",
                        unsafe_allow_html=True
                    )
                    if row.get("HowWeSolvedIt","").strip():
                        c1.caption(row["HowWeSolvedIt"])
                    if c2.button("✓", key=f"td_done_{orig_idx}", use_container_width=True, help="Mark done"):
                        dm().update_cell("TODO", orig_idx, "Done", "Yes")
                        invalidate("TODO")
                        st.rerun()
                    if c3.button("✏️", key=f"td_edit_{orig_idx}", use_container_width=True, help="Edit"):
                        st.session_state[f"editing_todo_{orig_idx}"] = not st.session_state.get(f"editing_todo_{orig_idx}", False)
                        st.rerun()
                    if c4.button("📋", key=f"td_promo_{orig_idx}", use_container_width=True, help="Promote to Resolution"):
                        st.session_state[f"promote_todo_{orig_idx}"] = True
                        st.rerun()
                    if c5.button("🗑", key=f"td_del_{orig_idx}", use_container_width=True, help="Delete"):
                        dm().delete_row("TODO", orig_idx)
                        invalidate("TODO")
                        st.rerun()

        # Completed items — with Revive button
        if not done_df.empty:
            with st.expander(f"✅ {len(done_df)} completed"):
                for _, row in done_df.iterrows():
                    orig_idx = int(row["index"])
                    c1, c2, c3 = st.columns([6, 1, 1])
                    c1.markdown(f"~~{row.get('Task','')}~~  <small style='color:#94a3b8'>{row.get('Created','')}</small>", unsafe_allow_html=True)
                    if row.get("HowWeSolvedIt","").strip():
                        c1.caption(row["HowWeSolvedIt"])
                    if c2.button("↩", key=f"td_revive_{orig_idx}", use_container_width=True, help="Move back to active"):
                        dm().update_cell("TODO", orig_idx, "Done", "No")
                        invalidate("TODO")
                        st.rerun()
                    if c3.button("🗑", key=f"td_ddel_{orig_idx}", use_container_width=True):
                        dm().delete_row("TODO", orig_idx)
                        invalidate("TODO")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_issues:
    st.markdown('<div class="section-header">Outstanding Issues</div>', unsafe_allow_html=True)

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Log a new issue**")
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        i_title    = r1c1.text_input("Title", key="i_title")
        i_priority = r1c2.selectbox("Priority", ["High", "Medium", "Low"], key="i_priority")
        i_owner    = r1c3.text_input("Owner", key="i_owner", placeholder="e.g. Jane Smith")
        i_due      = r1c4.date_input("Due (optional)", value=None, key="i_due")
        i_desc     = st.text_area("Detail", key="i_desc", height=200, placeholder="Describe the issue in full...")
        if st.button("Add Issue", type="primary", use_container_width=True):
            if not i_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Issues", {
                    "Title": i_title.strip(), "Description": i_desc.strip(),
                    "Priority": i_priority, "Owner": i_owner.strip(),
                    "Due": str(i_due) if i_due else "", "Status": "Open",
                    "Created": str(date.today()),
                }, sheet="Issues", success_msg="Issue logged!")

    st.markdown("---")

    df = get_data("Issues")
    if df.empty:
        st.info("No issues yet.")
    else:
        fc1, fc2 = st.columns(2)
        f_status   = fc1.multiselect("Status",   ["Open","In Progress","Resolved"], default=["Open","In Progress"])
        f_priority = fc2.multiselect("Priority", ["High","Medium","Low"],           default=["High","Medium","Low"])
        view = df.copy().reset_index(drop=False)
        if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
        if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
        if "Priority" in view.columns:
            view = view.assign(_s=view["Priority"].map({"High":0,"Medium":1,"Low":2}).fillna(9))
            view = view.sort_values(["_s","Created"], ascending=[True,False]).drop(columns=["_s"])

        edit_df = add_delete_col(view[[c for c in ["index","Title","Priority","Owner","Created","Status"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete":   st.column_config.CheckboxColumn("🗑", width="small"),
            "index":    st.column_config.Column("Row", disabled=True, width="small"),
            "Status":   st.column_config.SelectboxColumn("Status",   options=["Open","In Progress","Resolved"]),
            "Priority": st.column_config.SelectboxColumn("Priority", options=["High","Medium","Low"]),
        }, use_container_width=True, hide_index=True, key="issues_editor")

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save changes", key="issues_save", use_container_width=True):
            for _, row in edited.iterrows():
                orig_idx = int(row["index"])
                if row.get("Status") != df.loc[orig_idx].get("Status"):
                    dm().update_cell("Issues", orig_idx, "Status", row["Status"])
                if row.get("Priority") != df.loc[orig_idx].get("Priority"):
                    dm().update_cell("Issues", orig_idx, "Priority", row["Priority"])
            invalidate("Issues")
            st.toast("Saved!")
            st.rerun()
        if bc2.button("🗑 Delete selected", key="issues_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Issues", int(idx))
                invalidate("Issues")
                st.toast(f"Deleted {len(to_del)} row(s).")
                st.rerun()

        has_desc = view[view["Description"].str.strip() != ""] if "Description" in view.columns else pd.DataFrame()
        if not has_desc.empty:
            st.markdown("---")
            for _, row in has_desc.iterrows():
                orig_idx = int(row["index"])
                with st.expander(f"{row.get('Title','')}  ·  {row.get('Created','')}"):
                    e_title = st.text_input("Title", value=row.get("Title",""), key=f"is_et_{orig_idx}")
                    e_desc  = st.text_area("Detail", value=row.get("Description",""), key=f"is_ed_{orig_idx}", height=200)
                    if st.button("💾 Save", key=f"is_sv_{orig_idx}", use_container_width=True):
                        for col, val in [("Title",e_title),("Description",e_desc)]:
                            if val != row.get(col,""):
                                dm().update_cell("Issues", orig_idx, col, val)
                        invalidate("Issues")
                        st.toast("Saved!")
                        st.rerun()
                    st.markdown("---")
                    ib1, ib2, ib3, ib4 = st.columns(4)
                    cur_status = row.get("Status","Open")
                    if cur_status != "Resolved":
                        if ib1.button("✅ Resolved", key=f"is_res_{orig_idx}", use_container_width=True):
                            dm().update_cell("Issues", orig_idx, "Status", "Resolved")
                            invalidate("Issues")
                            st.toast("Marked as resolved!")
                            st.rerun()
                    else:
                        if ib1.button("↩️ Reopen", key=f"is_reopen_{orig_idx}", use_container_width=True):
                            dm().update_cell("Issues", orig_idx, "Status", "Open")
                            invalidate("Issues")
                            st.toast("Reopened!")
                            st.rerun()
                    if ib2.button("🔄 In Progress", key=f"is_prog_{orig_idx}", use_container_width=True):
                        dm().update_cell("Issues", orig_idx, "Status", "In Progress")
                        invalidate("Issues")
                        st.toast("Marked in progress!")
                        st.rerun()
                    if ib3.button("📋 → Resolution", key=f"is_tores_{orig_idx}", use_container_width=True):
                        save(dm().append_row, "Resolutions", {
                            "Title": row.get("Title",""),
                            "Problem": row.get("Description",""),
                            "Steps": "", "Solution": "",
                            "Files": "", "Tags": "",
                            "Created": str(date.today()),
                        }, sheet="Resolutions", success_msg="Moved to Resolutions!")
                        dm().delete_row("Issues", orig_idx)
                        invalidate("Issues")
                        invalidate("Resolutions")
                        st.rerun()
                    if ib4.button("🗑 Delete", key=f"is_del_{orig_idx}", use_container_width=True):
                        dm().delete_row("Issues", orig_idx)
                        invalidate("Issues")
                        st.toast("Deleted!")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION ITEMS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_actions:
    st.markdown('<div class="section-header">Action Items & Follow-ups</div>', unsafe_allow_html=True)

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ New action item**")
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        ac_task  = r1c1.text_input("Task", key="ac_task")
        ac_owner = r1c2.text_input("Owner", key="ac_owner", placeholder="e.g. Me, Jane")
        ac_due   = r1c3.date_input("Due date", key="ac_due")
        ac_src   = r1c4.selectbox("From", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
        ac_notes = st.text_area("Notes / context", key="ac_notes", height=200,
                                placeholder="What exactly needs to be done?")
        image_upload_widget("ac_img_upl", "ac_img")
        ac_img = st.text_input("Image URL (optional)", key="ac_img",
                               placeholder="Paste Imgur or Google Drive link")
        if st.button("Add Action", type="primary", use_container_width=True):
            if not ac_task.strip():
                st.warning("Task required.")
            else:
                save(dm().append_row, "ActionItems", {
                    "Task": ac_task.strip(), "Owner": ac_owner.strip(),
                    "Due": str(ac_due), "Source": ac_src,
                    "Status": "Pending", "Notes": ac_notes.strip(),
                    "Created": str(date.today()), "ImageURL": ac_img.strip(),
                }, sheet="ActionItems", success_msg="Added!")

    st.markdown("---")

    df = get_data("ActionItems")
    if df.empty:
        st.info("No action items yet.")
    else:
        f_owner = st.selectbox("Filter by owner", ["Everyone"], key="ac_filt")
        today_str = str(date.today())
        view = df.copy().reset_index(drop=False)
        if "Status" in view.columns:
            view = view[view["Status"] != "Done"]
        if f_owner != "Everyone" and "Owner" in view.columns:
            view = view[view["Owner"] == f_owner]
        if "Created" in view.columns:
            view = view.sort_values("Created", ascending=False)
        if "Due" in view.columns:
            view["⚠️"] = view.apply(lambda r: "🚨" if str(r.get("Due","")) < today_str and r.get("Status") == "Pending" else "", axis=1)

        if view.empty:
            st.success("🎉 All clear!")
        else:
            edit_df = add_delete_col(view[[c for c in ["index","⚠️","Task","Owner","Created","Due","Status"] if c in view.columns or c == "⚠️"]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
                "⚠️":    st.column_config.Column("⚠️", disabled=True, width="small"),
                "Status": st.column_config.SelectboxColumn("Status", options=["Pending","In Progress","Done"]),
            }, use_container_width=True, hide_index=True, key="actions_editor")

            bc1, bc2 = st.columns(2)
            if bc1.button("💾 Save changes", key="ac_save", use_container_width=True):
                for _, row in edited.iterrows():
                    orig_idx = int(row["index"])
                    if row.get("Status") != df.loc[orig_idx].get("Status"):
                        dm().update_cell("ActionItems", orig_idx, "Status", row["Status"])
                invalidate("ActionItems")
                st.toast("Saved!")
                st.rerun()
            if bc2.button("🗑 Delete selected", key="ac_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                if not to_del:
                    st.info("Tick rows first.")
                else:
                    for idx in sorted(to_del, reverse=True):
                        dm().delete_row("ActionItems", int(idx))
                    invalidate("ActionItems")
                    st.rerun()

        done_df = df[df["Status"] == "Done"].reset_index(drop=False) if "Status" in df.columns else pd.DataFrame()
        if not done_df.empty:
            with st.expander(f"✅ {len(done_df)} completed"):
                st.dataframe(done_df[[c for c in ["Task","Owner","Due"] if c in done_df.columns]], use_container_width=True, hide_index=True)

        has_notes = view[(view["Notes"].str.strip() != "") | (view["ImageURL"].str.strip() != "")] if "Notes" in view.columns and "ImageURL" in view.columns else (view[view["Notes"].str.strip() != ""] if "Notes" in view.columns else pd.DataFrame())
        if not has_notes.empty:
            st.markdown("---")
            for _, row in has_notes.iterrows():
                with st.expander(f"{row.get('Task','')}  ·  {row.get('Created','')}"):
                    if row.get("Notes"): st.markdown(row["Notes"])
                    if row.get("ImageURL"):
                        st.image(resolve_image_url(row["ImageURL"]))
                    st.markdown("---")
                    orig_idx = int(row["index"])
                    e_task  = st.text_input("Task",       value=row.get("Task",""),    key=f"ac_et_{orig_idx}")
                    e_owner = st.text_input("Owner",      value=row.get("Owner",""),   key=f"ac_eo_{orig_idx}")
                    e_notes = st.text_area("Notes",       value=row.get("Notes",""),   key=f"ac_en_{orig_idx}", height=200)
                    image_upload_widget(f"ac_ei_upl_{orig_idx}", f"ac_ei_{orig_idx}")
                    e_img   = st.text_input("Image URL",  value=row.get("ImageURL",""),key=f"ac_ei_{orig_idx}", placeholder="Paste Imgur or Google Drive link")
                    sb1, sb2 = st.columns(2)
                    if sb1.button("💾 Save changes", key=f"ac_sv_{orig_idx}", use_container_width=True):
                        for col, val in [("Task",e_task),("Owner",e_owner),("Notes",e_notes),("ImageURL",e_img)]:
                            if val != row.get(col,""):
                                dm().update_cell("ActionItems", orig_idx, col, val)
                        invalidate("ActionItems")
                        st.toast("Saved!")
                        st.rerun()
                    cur_status = row.get("Status","Pending")
                    if cur_status != "Done":
                        if sb2.button("✅ Mark Done", key=f"ac_done_{orig_idx}", use_container_width=True):
                            dm().update_cell("ActionItems", orig_idx, "Status", "Done")
                            invalidate("ActionItems")
                            st.toast("Marked as done!")
                            st.rerun()
                    else:
                        if sb2.button("↩️ Reopen", key=f"ac_reopen_{orig_idx}", use_container_width=True):
                            dm().update_cell("ActionItems", orig_idx, "Status", "Pending")
                            invalidate("ActionItems")
                            st.toast("Reopened!")
                            st.rerun()
                    st.markdown("---")
                    ac1, ac2, ac3 = st.columns(3)
                    if ac1.button("☑️ → TODO", key=f"ac_totodo_{orig_idx}", use_container_width=True):
                        save(dm().append_row, "TODO", {
                            "Task": row.get("Task",""),
                            "Done": "No",
                            "Created": str(date.today()),
                            "DueDate": row.get("Due",""),
                            "HowWeSolvedIt": "",
                        }, sheet="TODO", success_msg="Moved to TODO!")
                        dm().delete_row("ActionItems", orig_idx)
                        invalidate("ActionItems")
                        invalidate("TODO")
                        st.rerun()
                    if ac2.button("📋 → Resolution", key=f"ac_tores_{orig_idx}", use_container_width=True):
                        save(dm().append_row, "Resolutions", {
                            "Title": row.get("Task",""),
                            "Problem": row.get("Notes",""),
                            "Steps": "", "Solution": "",
                            "Files": "", "Tags": "",
                            "Created": str(date.today()),
                        }, sheet="Resolutions", success_msg="Moved to Resolutions!")
                        dm().delete_row("ActionItems", orig_idx)
                        invalidate("ActionItems")
                        invalidate("Resolutions")
                        st.rerun()
                    if ac3.button("🗑 Delete", key=f"ac_del_{orig_idx}", use_container_width=True):
                        dm().delete_row("ActionItems", orig_idx)
                        invalidate("ActionItems")
                        st.toast("Deleted!")
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MEETINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_meetings:
    st.markdown('<div class="section-header">Meeting Summaries</div>', unsafe_allow_html=True)

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Log a meeting**")
        r1c1, r1c2, r1c3 = st.columns(3)
        mt_title     = r1c1.text_input("Meeting title", key="mt_title")
        mt_date      = r1c2.date_input("Date", key="mt_date")
        mt_attendees = r1c3.text_input("Attendees", key="mt_att", placeholder="e.g. Jane, John, Sarah")
        mt_notes     = st.text_area("Notes / summary", key="mt_notes", height=250,
                                    placeholder="What was discussed?")
        mt_questions = st.text_area("Outstanding questions", key="mt_questions", height=150,
                                    placeholder="What's still unresolved?")
        image_upload_widget("mt_img_upl", "mt_img")
        mt_img = st.text_input("Image URL (optional)", key="mt_img",
                              placeholder="Paste Imgur or Google Drive link")
        if st.button("Save Meeting", type="primary", use_container_width=True):
            if not mt_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Meetings", {
                    "Title": mt_title.strip(), "Date": str(mt_date),
                    "Attendees": mt_attendees.strip(),
                    "Notes": mt_notes.strip(), "Questions": mt_questions.strip(),
                    "Created": str(date.today()), "ImageURL": mt_img.strip(),
                }, sheet="Meetings", success_msg="Meeting saved!")

    st.markdown("---")

    df = get_data("Meetings")
    if df.empty:
        st.info("No meetings logged yet.")
    else:
        search = st.text_input("🔍 Search", key="mt_search")
        view = df.copy().reset_index(drop=False)
        if "Date" in view.columns:
            view = view.sort_values("Date", ascending=False)
        if search:
            view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

        edit_df = add_delete_col(view[[c for c in ["index","Date","Title","Attendees"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
        }, use_container_width=True, hide_index=True, key="meetings_editor")

        if st.button("🗑 Delete selected", key="mt_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Meetings", int(idx))
                invalidate("Meetings")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Date','')}  ·  {row.get('Attendees','')}"):
                e_title = st.text_input("Title",     value=row.get("Title",""),     key=f"mt_et_{orig_idx}")
                e_date  = st.text_input("Date",      value=row.get("Date",""),      key=f"mt_ed_{orig_idx}")
                e_att   = st.text_input("Attendees", value=row.get("Attendees",""), key=f"mt_ea_{orig_idx}")
                e_notes = st.text_area("Notes / summary",      value=row.get("Notes",""),     key=f"mt_en_{orig_idx}", height=250)
                e_qs    = st.text_area("Outstanding questions", value=row.get("Questions",""), key=f"mt_eq_{orig_idx}", height=150)
                image_upload_widget(f"mt_ei_upl_{orig_idx}", f"mt_ei_{orig_idx}")
                e_img = st.text_input("Image URL", value=row.get("ImageURL",""), key=f"mt_ei_{orig_idx}", placeholder="Paste Imgur or Google Drive link")
                if row.get("ImageURL"):
                    st.image(resolve_image_url(row["ImageURL"]), use_container_width=True)
                mb1, mb2 = st.columns(2)
                if mb1.button("💾 Save", key=f"mt_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Date",e_date),("Attendees",e_att),("Notes",e_notes),("Questions",e_qs),("ImageURL",e_img)]:
                        if val != row.get(col,""):
                            dm().update_cell("Meetings", orig_idx, col, val)
                    invalidate("Meetings")
                    st.toast("Saved!")
                    st.rerun()
                if mb2.button("🗑 Delete", key=f"mt_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Meetings", orig_idx)
                    invalidate("Meetings")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_projects:
    st.markdown('<div class="section-header">Projects</div>', unsafe_allow_html=True)
    st.caption("Document significant work — models, pipelines, dashboards, analyses. A living record that grows over time.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Add a project**")
        r1c1, r1c2 = st.columns(2)
        proj_title  = r1c1.text_input("Title", key="proj_title", placeholder="e.g. Deal Prioritization ML Model")
        proj_status = r1c2.selectbox("Status", ["In Progress","Complete","On Hold","Planned"], key="proj_status")
        proj_tags   = st.text_input("Tags", key="proj_tags", placeholder="e.g. ML, Databricks, Monday.com")
        proj_desc   = st.text_area("What is it / why?", key="proj_desc", height=120,
                                   placeholder="What are you building and what problem does it solve?")
        proj_approach = st.text_area("Approach / methodology", key="proj_approach", height=150,
                                     placeholder="How are you going about it? What tools, models, data sources?")
        proj_results  = st.text_area("Results / findings", key="proj_results", height=150,
                                     placeholder="What did you find or build? Performance metrics, outputs, conclusions...")
        proj_next     = st.text_area("Next steps / comments", key="proj_next", height=100,
                                     placeholder="What still needs to be done? Open questions, future improvements...")
        files_upload_widget("proj_files_upl", "proj_files")
        proj_files = st.text_area("Files / links (one per line)", key="proj_files", height=80,
                                  placeholder="Notebook: https://...\nResults chart: https://...")
        if st.button("Save Project", type="primary", use_container_width=True):
            if not proj_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Projects", {
                    "Title": proj_title.strip(), "Status": proj_status,
                    "Description": proj_desc.strip(), "Approach": proj_approach.strip(),
                    "Results": proj_results.strip(), "NextSteps": proj_next.strip(),
                    "Files": proj_files.strip(), "Tags": proj_tags.strip(),
                    "Created": str(date.today()),
                }, sheet="Projects", success_msg="Project saved!")

    st.markdown("---")

    df = get_data("Projects")
    if df.empty:
        st.info("No projects yet. Add your first one above.")
    else:
        sc1, sc2 = st.columns([2, 1])
        search   = sc1.text_input("🔍 Search", key="proj_search")
        all_st   = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
        f_status = sc2.selectbox("Status", all_st, key="proj_status_filter")

        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        if f_status != "All" and "Status" in view.columns: view = view[view["Status"] == f_status]

        status_icon = {"In Progress":"🟡","Complete":"✅","On Hold":"⏸️","Planned":"📌"}

        edit_df = add_delete_col(view[[c for c in ["index","Title","Status","Tags","Created"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=["In Progress","Complete","On Hold","Planned"]),
        }, use_container_width=True, hide_index=True, key="proj_editor")

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save status", key="proj_save", use_container_width=True):
            for _, row in edited.iterrows():
                orig_idx = int(row["index"])
                if row.get("Status") != df.loc[orig_idx].get("Status"):
                    dm().update_cell("Projects", orig_idx, "Status", row["Status"])
            invalidate("Projects")
            st.toast("Saved!")
            st.rerun()
        if bc2.button("🗑 Delete selected", key="proj_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Projects", int(idx))
                invalidate("Projects")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            icon = status_icon.get(row.get("Status",""), "📄")
            with st.expander(f"{icon} **{row.get('Title','')}**  ·  {row.get('Status','')}  ·  {row.get('Created','')}"):
                if row.get("Tags"):
                    st.markdown(" ".join([f"`{t.strip()}`" for t in row["Tags"].split(",") if t.strip()]))

                if row.get("Description"):
                    st.markdown("**What is it / why:**")
                    st.markdown(row["Description"])
                if row.get("Approach"):
                    st.markdown("**Approach / methodology:**")
                    st.markdown(row["Approach"])
                if row.get("Results"):
                    st.markdown("**Results / findings:**")
                    st.success(row["Results"])
                if row.get("NextSteps"):
                    st.markdown("**Next steps / comments:**")
                    st.info(row["NextSteps"])

                if row.get("Files"):
                    st.markdown("**📎 Files / links:**")
                    for line in row["Files"].split("\n"):
                        line = line.strip()
                        if not line: continue
                        if ":" in line and "http" in line.split(":",1)[1]:
                            label, url = line.split(":", 1)
                            url = url.strip()
                            st.markdown(f"- [{label.strip()}]({url})")
                            if is_image_url(url) or "imgur" in url or "drive.google" in url:
                                st.image(resolve_image_url(url))
                        elif line.startswith("http"):
                            st.markdown(f"- [{line}]({line})")
                        else:
                            st.markdown(f"- {line}")

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_title    = st.text_input("Title",     value=row.get("Title",""),       key=f"proj_et_{orig_idx}")
                e_tags     = st.text_input("Tags",      value=row.get("Tags",""),        key=f"proj_etg_{orig_idx}")
                e_desc     = st.text_area("What is it / why",     value=row.get("Description",""), key=f"proj_ed_{orig_idx}", height=120)
                e_approach = st.text_area("Approach",             value=row.get("Approach",""),    key=f"proj_ea_{orig_idx}", height=150)
                e_results  = st.text_area("Results / findings",   value=row.get("Results",""),     key=f"proj_er_{orig_idx}", height=150)
                e_next     = st.text_area("Next steps / comments",value=row.get("NextSteps",""),   key=f"proj_en_{orig_idx}", height=100)
                files_upload_widget(f"proj_ef_upl_{orig_idx}", f"proj_ef_{orig_idx}")
                e_files    = st.text_area("Files / links",        value=row.get("Files",""),       key=f"proj_ef_{orig_idx}", height=80)

                pb1, pb2 = st.columns(2)
                if pb1.button("💾 Save", key=f"proj_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Tags",e_tags),("Description",e_desc),
                                     ("Approach",e_approach),("Results",e_results),
                                     ("NextSteps",e_next),("Files",e_files)]:
                        if val != row.get(col,""):
                            dm().update_cell("Projects", orig_idx, col, val)
                    invalidate("Projects")
                    st.toast("Saved!")
                    st.rerun()
                if pb2.button("🗑 Delete", key=f"proj_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Projects", orig_idx)
                    invalidate("Projects")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA PULLS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_datapulls:
    st.markdown('<div class="section-header">Data Pulls</div>', unsafe_allow_html=True)
    st.caption("Log ad-hoc data pulls — the question asked, sources used, logic, gotchas, result, and the SQL to reproduce it.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Log a data pull**")
        dp_title     = st.text_input("Title", key="dp_title", placeholder="e.g. Trash expense by asset, Aug 2024–Jul 2026")
        dp_requester = st.text_input("Requester", key="dp_requester", placeholder="Who asked for this?")
        dp_question  = st.text_area("Question / request", key="dp_question", height=80,
                                    placeholder="What exactly was being asked?")
        dp_sources   = st.text_area("Sources / tables used", key="dp_sources", height=80,
                                    placeholder="e.g. storedge_prod.datamodels.monthlyfinancials_detail; dim.assets")
        dp_logic     = st.text_area("Logic", key="dp_logic", height=120,
                                    placeholder="How was the data assembled? Filters, joins, aggregations...")
        dp_gotchas   = st.text_area("Gotchas / caveats", key="dp_gotchas", height=80,
                                    placeholder="Edge cases, exclusions, known issues encountered...")
        dp_result    = st.text_area("Result / answer", key="dp_result", height=80,
                                    placeholder="e.g. $836K vs $610K (-27%); comparable 151 assets...")
        dp_output    = st.text_input("Output file", key="dp_output", placeholder="e.g. Trash_Expense_by_Asset.xlsx")
        dp_sql       = st.text_area("SQL / code", key="dp_sql", height=250,
                                    placeholder="Paste the query or script used to produce the result...")
        dp_followups = st.text_area("Follow-ups", key="dp_followups", height=68,
                                    placeholder="Open questions or next steps from this pull...")
        dp_tags      = st.text_input("Tags", key="dp_tags", placeholder="e.g. GL, trash, CREST, Heitman")
        if st.button("Save Data Pull", type="primary", use_container_width=True):
            if not dp_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "DataPulls", {
                    "Title": dp_title.strip(), "Requester": dp_requester.strip(),
                    "Question": dp_question.strip(), "Sources": dp_sources.strip(),
                    "Logic": dp_logic.strip(), "Gotchas": dp_gotchas.strip(),
                    "Result": dp_result.strip(), "Output": dp_output.strip(),
                    "SQL": dp_sql.strip(), "FollowUps": dp_followups.strip(),
                    "Tags": dp_tags.strip(), "Created": str(date.today()),
                }, sheet="DataPulls", success_msg="Saved!")

    st.markdown("---")

    df = get_data("DataPulls")
    if df.empty:
        st.info("No data pulls logged yet.")
    else:
        search = st.text_input("🔍 Search", key="dp_search")
        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

        edit_df = add_delete_col(view[[c for c in ["index","Title","Requester","Tags","Created"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
        }, use_container_width=True, hide_index=True, key="dp_editor")

        if st.button("🗑 Delete selected", key="dp_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("DataPulls", int(idx))
                invalidate("DataPulls")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Created','')}  ·  {row.get('Requester','')}"):
                if row.get("Tags"): st.caption(f"🏷 {row['Tags']}")

                if row.get("Question"):
                    st.markdown("**Question**")
                    st.markdown(row["Question"])

                c1, c2 = st.columns(2)
                if row.get("Sources"):
                    c1.markdown("**Sources**")
                    c1.markdown(row["Sources"])
                if row.get("Result"):
                    c2.markdown("**Result**")
                    c2.info(row["Result"])

                if row.get("Logic"):
                    st.markdown("**Logic**")
                    st.markdown(row["Logic"])

                if row.get("Gotchas"):
                    st.markdown("**⚠️ Gotchas**")
                    st.warning(row["Gotchas"])

                if row.get("Output"):
                    st.markdown(f"**Output file:** `{row['Output']}`")

                if row.get("FollowUps"):
                    st.markdown("**Follow-ups**")
                    st.markdown(row["FollowUps"])

                if row.get("SQL"):
                    st.markdown("**SQL / code**")
                    sql_text = row["SQL"]
                    lang = "python" if "import " in sql_text else "sql"
                    st.code(sql_text, language=lang)

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_title     = st.text_input("Title",      value=row.get("Title",""),     key=f"dp_et_{orig_idx}")
                e_requester = st.text_input("Requester",  value=row.get("Requester",""), key=f"dp_er_{orig_idx}")
                e_question  = st.text_area("Question",    value=row.get("Question",""),  key=f"dp_eq_{orig_idx}", height=80)
                e_sources   = st.text_area("Sources",     value=row.get("Sources",""),   key=f"dp_es_{orig_idx}", height=80)
                e_logic     = st.text_area("Logic",       value=row.get("Logic",""),     key=f"dp_el_{orig_idx}", height=120)
                e_gotchas   = st.text_area("Gotchas",     value=row.get("Gotchas",""),   key=f"dp_eg_{orig_idx}", height=80)
                e_result    = st.text_area("Result",      value=row.get("Result",""),    key=f"dp_eres_{orig_idx}", height=80)
                e_output    = st.text_input("Output file",value=row.get("Output",""),    key=f"dp_eo_{orig_idx}")
                e_sql       = st.text_area("SQL / code",  value=row.get("SQL",""),       key=f"dp_esql_{orig_idx}", height=250)
                e_followups = st.text_area("Follow-ups",  value=row.get("FollowUps",""), key=f"dp_efu_{orig_idx}", height=68)
                e_tags      = st.text_input("Tags",       value=row.get("Tags",""),      key=f"dp_etg_{orig_idx}")

                dpb1, dpb2 = st.columns(2)
                if dpb1.button("💾 Save changes", key=f"dp_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Requester",e_requester),("Question",e_question),
                                     ("Sources",e_sources),("Logic",e_logic),("Gotchas",e_gotchas),
                                     ("Result",e_result),("Output",e_output),("SQL",e_sql),
                                     ("FollowUps",e_followups),("Tags",e_tags)]:
                        if val != row.get(col,""):
                            dm().update_cell("DataPulls", orig_idx, col, val)
                    invalidate("DataPulls")
                    st.toast("Saved!")
                    st.rerun()
                if dpb2.button("🗑 Delete", key=f"dp_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("DataPulls", orig_idx)
                    invalidate("DataPulls")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PROCEDURES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_procedures:
    st.markdown('<div class="section-header">Procedures & Processes</div>', unsafe_allow_html=True)
    st.caption("Document how things work — debugging steps, deployment processes, runbooks, how-tos.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Add a procedure**")
        r1c1, r1c2 = st.columns(2)
        pr_title = r1c1.text_input("Title", key="pr_title", placeholder="e.g. How to debug Power BI refresh")
        pr_cat   = r1c2.selectbox("Category", [
            "Debugging", "Deployment", "Onboarding", "Reporting",
            "Data Pipeline", "HR Process", "Admin", "Other"
        ], key="pr_cat")
        pr_tags  = st.text_input("Tags", key="pr_tags", placeholder="e.g. Power BI, data, reporting")
        pr_steps = st.text_area("Steps / content", key="pr_steps", height=300,
                                placeholder="Write the steps here. Use numbered lists, bullet points, etc.")
        pr_notes = st.text_area("Notes / context", key="pr_notes", height=120,
                                placeholder="When to use this, prerequisites, gotchas...")
        image_upload_widget("pr_img_upl", "pr_img")
        pr_img = st.text_input("Image URL (optional)", key="pr_img",
                              placeholder="Paste Imgur or Google Drive link")
        if st.button("Save Procedure", type="primary", use_container_width=True):
            if not pr_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Procedures", {
                    "Title": pr_title.strip(), "Category": pr_cat,
                    "Steps": pr_steps.strip(), "Notes": pr_notes.strip(),
                    "Tags": pr_tags.strip(),
                    "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "ImageURL": pr_img.strip(),
                }, sheet="Procedures", success_msg="Saved!")

    st.markdown("---")

    df = get_data("Procedures")
    if df.empty:
        st.info("No procedures yet.\n\nIdeas to add:\n- How to debug a Power BI refresh failure\n- Deployment checklist\n- New hire onboarding steps\n- How to run a monthly report")
    else:
        sc1, sc2 = st.columns([2, 1])
        search   = sc1.text_input("🔍 Search", key="pr_search")
        all_cats = ["All"] + sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else ["All"]
        f_cat    = sc2.selectbox("Category", all_cats, key="pr_cat_filter")

        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        if f_cat != "All" and "Category" in view.columns: view = view[view["Category"] == f_cat]

        edit_df = add_delete_col(view[[c for c in ["index","Title","Category","Tags"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
        }, use_container_width=True, hide_index=True, key="proc_editor")

        if st.button("🗑 Delete selected", key="pr_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Procedures", int(idx))
                invalidate("Procedures")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Category','')}"):
                if row.get("Tags"): st.caption(f"🏷 {row['Tags']}")
                if row.get("Notes"):
                    st.info(row["Notes"])

                if row.get("Steps"):
                    st.markdown(row["Steps"])
                if row.get("ImageURL"):
                    st.image(resolve_image_url(row["ImageURL"]), use_container_width=True)

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_title = st.text_input("Title",    value=row.get("Title",""),    key=f"pr_et_{orig_idx}")
                e_steps = st.text_area("Steps",     value=row.get("Steps",""),    key=f"pr_es_{orig_idx}", height=300)
                e_notes = st.text_area("Notes",     value=row.get("Notes",""),    key=f"pr_en_{orig_idx}", height=120)
                e_tags  = st.text_input("Tags",     value=row.get("Tags",""),     key=f"pr_etg_{orig_idx}")
                image_upload_widget(f"pr_ei_upl_{orig_idx}", f"pr_ei_{orig_idx}")
                e_img = st.text_input("Image URL", value=row.get("ImageURL",""), key=f"pr_ei_{orig_idx}")

                pb1, pb2 = st.columns(2)
                if pb1.button("💾 Save changes", key=f"pr_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Steps",e_steps),("Notes",e_notes),("Tags",e_tags),("ImageURL",e_img)]:
                        if val != row.get(col,""):
                            dm().update_cell("Procedures", orig_idx, col, val)
                    invalidate("Procedures")
                    st.toast("Saved!")
                    st.rerun()
                if pb2.button("🗑 Delete", key=f"pr_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Procedures", orig_idx)
                    invalidate("Procedures")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLUTIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_resolutions:
    st.markdown('<div class="section-header">Resolutions</div>', unsafe_allow_html=True)
    st.caption("Document how specific issues were solved — what the problem was, what you tried, and what actually fixed it.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Log a resolution**")
        r1c1, r1c2 = st.columns(2)
        res_title = r1c1.text_input("Title", key="res_title", placeholder="e.g. Duplicate properties in daily rent roll")
        res_tags  = r1c2.text_input("Tags", key="res_tags", placeholder="e.g. ETL, duplicates, Databricks")
        res_problem = st.text_area("What was the problem?", key="res_problem", height=120,
                                   placeholder="Describe the issue — what was wrong, what symptoms you saw...")
        res_steps = st.text_area("What did you try?", key="res_steps", height=120,
                                 placeholder="Steps taken, things that didn't work, dead ends...")
        res_solution = st.text_area("What fixed it?", key="res_solution", height=150,
                                    placeholder="The actual solution — be specific so you can repeat it later...")
        files_upload_widget("res_files_upl", "res_files")
        res_files = st.text_area("Files / links (one per line)", key="res_files", height=80,
                                 placeholder="Screenshot: https://...\nScript: https://...")
        if st.button("Save Resolution", type="primary", use_container_width=True):
            if not res_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Resolutions", {
                    "Title": res_title.strip(),
                    "Problem": res_problem.strip(),
                    "Steps": res_steps.strip(),
                    "Solution": res_solution.strip(),
                    "Files": res_files.strip(),
                    "Tags": res_tags.strip(),
                    "Created": str(date.today()),
                }, sheet="Resolutions", success_msg="Resolution saved!")

    st.markdown("---")

    df = get_data("Resolutions")
    if df.empty:
        st.info("No resolutions yet. When you solve a tricky issue, log it here so you don't have to figure it out again.")
    else:
        sc1, sc2 = st.columns([3, 1])
        search = sc1.text_input("🔍 Search", key="res_search")
        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

        edit_df = add_delete_col(view[[c for c in ["index","Title","Tags","Created"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
        }, use_container_width=True, hide_index=True, key="res_editor")

        if st.button("🗑 Delete selected", key="res_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Resolutions", int(idx))
                invalidate("Resolutions")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Created','')}"):
                if row.get("Tags"):
                    st.markdown(" ".join([f"`{t.strip()}`" for t in row["Tags"].split(",") if t.strip()]))

                if row.get("Problem"):
                    st.markdown("**🔴 Problem:**")
                    st.markdown(row["Problem"])

                if row.get("Steps"):
                    st.markdown("**🔄 What was tried:**")
                    st.markdown(row["Steps"])

                if row.get("Solution"):
                    st.markdown("**✅ What fixed it:**")
                    st.success(row["Solution"])

                if row.get("Files"):
                    st.markdown("**📎 Files / links:**")
                    for line in row["Files"].split("\n"):
                        line = line.strip()
                        if not line: continue
                        if ":" in line and "http" in line.split(":",1)[1]:
                            label, url = line.split(":", 1)
                            url = url.strip()
                            st.markdown(f"- [{label.strip()}]({url})")
                            if is_image_url(url) or "imgur" in url or "drive.google" in url:
                                st.image(resolve_image_url(url))
                        elif line.startswith("http"):
                            st.markdown(f"- [{line}]({line})")
                        else:
                            st.markdown(f"- {line}")

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_title    = st.text_input("Title",            value=row.get("Title",""),    key=f"res_et_{orig_idx}")
                e_tags     = st.text_input("Tags",             value=row.get("Tags",""),     key=f"res_etg_{orig_idx}")
                e_problem  = st.text_area("Problem",           value=row.get("Problem",""),  key=f"res_ep_{orig_idx}", height=120)
                e_steps    = st.text_area("What was tried",    value=row.get("Steps",""),    key=f"res_es_{orig_idx}", height=120)
                e_solution = st.text_area("What fixed it",     value=row.get("Solution",""), key=f"res_esol_{orig_idx}", height=150)
                files_upload_widget(f"res_ef_upl_{orig_idx}", f"res_ef_{orig_idx}")
                e_files    = st.text_area("Files / links",     value=row.get("Files",""),    key=f"res_ef_{orig_idx}", height=80)

                rb1, rb2 = st.columns(2)
                if rb1.button("💾 Save", key=f"res_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Tags",e_tags),("Problem",e_problem),
                                     ("Steps",e_steps),("Solution",e_solution),("Files",e_files)]:
                        if val != row.get(col,""):
                            dm().update_cell("Resolutions", orig_idx, col, val)
                    invalidate("Resolutions")
                    st.toast("Saved!")
                    st.rerun()
                if rb2.button("🗑 Delete", key=f"res_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Resolutions", orig_idx)
                    invalidate("Resolutions")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA ISSUES — metric / definition tracker
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dataissues:
    st.markdown('<div class="section-header">Data Issues</div>', unsafe_allow_html=True)
    st.caption("Track metrics or fields that are defined differently across sources, or have known quirks that affect reporting.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Log a data issue**")
        di_metric  = st.text_input("Metric / field", key="di_metric", placeholder="e.g. Occupied Units, Rent Roll, Effective Rent")
        di_sources = st.text_input("Sources / tables", key="di_sources", placeholder="e.g. StorEdge vs CREST pre-recap; dim.assets vs monthlyfinancials_detail")
        di_issue   = st.text_area("Issue / discrepancy", key="di_issue", height=100,
                                  placeholder="What's different or confusing about how this metric is defined or calculated?")
        di_impact  = st.text_area("Impact", key="di_impact", height=80,
                                  placeholder="How does this affect reports, comparisons, or decisions?")
        di_resolution = st.text_area("Resolution / how to handle", key="di_resolution", height=80,
                                     placeholder="Which definition to use and when, or how to reconcile...")
        di_status  = st.selectbox("Status", ["Open", "Resolved", "Known quirk"], key="di_status")
        di_tags    = st.text_input("Tags", key="di_tags", placeholder="e.g. GL, occupancy, CREST, rent roll")
        if st.button("Save Data Issue", type="primary", use_container_width=True):
            if not di_metric.strip():
                st.warning("Metric / field name required.")
            else:
                save(dm().append_row, "DataIssues", {
                    "Metric": di_metric.strip(), "Sources": di_sources.strip(),
                    "Issue": di_issue.strip(), "Impact": di_impact.strip(),
                    "Resolution": di_resolution.strip(), "Status": di_status,
                    "Tags": di_tags.strip(), "Created": str(date.today()),
                }, sheet="DataIssues", success_msg="Saved!")

    st.markdown("---")

    df = get_data("DataIssues")
    if df.empty:
        st.info("No data issues logged yet.")
    else:
        di_c1, di_c2 = st.columns([3, 1])
        di_search  = di_c1.text_input("🔍 Search", key="di_search")
        all_st     = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
        di_f_status = di_c2.selectbox("Status", all_st, key="di_status_filter")

        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns:
            view = view.sort_values("Created", ascending=False)
        if di_search:
            view = view[view.apply(lambda r: di_search.lower() in str(r).lower(), axis=1)]
        if di_f_status != "All" and "Status" in view.columns:
            view = view[view["Status"] == di_f_status]

        status_icon = {"Open": "🔴", "Resolved": "✅", "Known quirk": "🟡"}

        edit_df = add_delete_col(view[[c for c in ["index", "Metric", "Sources", "Status", "Created"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=["Open", "Resolved", "Known quirk"]),
        }, use_container_width=True, hide_index=True, key="di_editor")

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save status", key="di_save", use_container_width=True):
            for _, row in edited.iterrows():
                orig_idx = int(row["index"])
                if row.get("Status") != df.loc[orig_idx].get("Status"):
                    dm().update_cell("DataIssues", orig_idx, "Status", row["Status"])
            invalidate("DataIssues")
            st.toast("Saved!")
            st.rerun()
        if bc2.button("🗑 Delete selected", key="di_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("DataIssues", int(idx))
                invalidate("DataIssues")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            icon = status_icon.get(row.get("Status", ""), "📄")
            with st.expander(f"{icon} **{row.get('Metric', '')}**  ·  {row.get('Status', '')}  ·  {row.get('Created', '')}"):
                if row.get("Tags"):
                    st.caption(f"🏷 {row['Tags']}")
                if row.get("Sources"):
                    st.markdown(f"**Sources:** {row['Sources']}")

                if row.get("Issue"):
                    st.markdown("**Issue / discrepancy**")
                    st.markdown(row["Issue"])

                if row.get("Impact"):
                    st.markdown("**Impact**")
                    st.warning(row["Impact"])

                if row.get("Resolution"):
                    st.markdown("**Resolution / how to handle**")
                    st.success(row["Resolution"])

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_metric     = st.text_input("Metric / field",           value=row.get("Metric", ""),     key=f"di_em_{orig_idx}")
                e_sources    = st.text_input("Sources / tables",          value=row.get("Sources", ""),    key=f"di_es_{orig_idx}")
                e_issue      = st.text_area("Issue / discrepancy",        value=row.get("Issue", ""),      key=f"di_ei_{orig_idx}", height=100)
                e_impact     = st.text_area("Impact",                     value=row.get("Impact", ""),     key=f"di_eimp_{orig_idx}", height=80)
                e_resolution = st.text_area("Resolution / how to handle", value=row.get("Resolution", ""), key=f"di_er_{orig_idx}", height=80)
                st_opts      = ["Open", "Resolved", "Known quirk"]
                e_status     = st.selectbox("Status", st_opts,
                                            index=st_opts.index(row.get("Status", "Open")) if row.get("Status") in st_opts else 0,
                                            key=f"di_est_{orig_idx}")
                e_tags       = st.text_input("Tags", value=row.get("Tags", ""), key=f"di_etg_{orig_idx}")

                dib1, dib2 = st.columns(2)
                if dib1.button("💾 Save changes", key=f"di_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Metric", e_metric), ("Sources", e_sources), ("Issue", e_issue),
                                     ("Impact", e_impact), ("Resolution", e_resolution),
                                     ("Status", e_status), ("Tags", e_tags)]:
                        if val != row.get(col, ""):
                            dm().update_cell("DataIssues", orig_idx, col, val)
                    invalidate("DataIssues")
                    st.toast("Saved!")
                    st.rerun()
                if dib2.button("🗑 Delete", key=f"di_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("DataIssues", orig_idx)
                    invalidate("DataIssues")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# NOTES — scratchpad
# ═══════════════════════════════════════════════════════════════════════════════
with tab_notes:
    st.markdown('<div class="section-header">Notes</div>', unsafe_allow_html=True)
    st.caption("Free-form scratchpad. Saved to your Google Sheet.")

    if "scratchpad_loaded" not in st.session_state:
        try:
            st.session_state.scratchpad = dm().get_scratchpad()
        except Exception:
            st.session_state.scratchpad = ""
        st.session_state.scratchpad_loaded = True

    text = st.text_area(
        "Scratchpad", value=st.session_state.scratchpad,
        height=600, label_visibility="collapsed",
        placeholder="Start typing your notes here...",
        key="scratchpad_input",
    )
    c1, _ = st.columns([1, 4])
    if c1.button("💾 Save", type="primary", use_container_width=True):
        try:
            dm().set_scratchpad(text)
            st.session_state.scratchpad = text
            st.toast("Saved!")
        except Exception as e:
            st.error(f"❌ {e}")
