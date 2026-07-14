import streamlit as st
import pandas as pd
from datetime import datetime, date
from data_manager import SheetsManager

st.set_page_config(page_title="Task Dashboard", page_icon="📋", layout="wide")

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
    st.markdown("## 🔒 Task Dashboard")
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

if "direct_reports" not in st.session_state:
    try:
        st.session_state.direct_reports = _sm.get_direct_reports()
    except Exception:
        st.session_state.direct_reports = []


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
    """File uploader (multi) + button that uploads to Drive and appends links into session_state[target_key]."""
    folder_id = st.secrets.get("drive_folder_id", "")
    uploaded_files = st.file_uploader("Or upload files", accept_multiple_files=True, key=uploader_key, label_visibility="collapsed")
    if uploaded_files and st.button("📤 Upload files", key=f"{uploader_key}_btn"):
        if not folder_id:
            st.error("drive_folder_id not configured in secrets.")
        else:
            new_lines = []
            for f in uploaded_files:
                try:
                    link = dm().upload_file_to_drive(f.read(), f.name, f.type, folder_id)
                    new_lines.append(f"{f.name}: {link}")
                except Exception as e:
                    st.error(f"❌ Failed to upload {f.name}: {e}")
            if new_lines:
                current = st.session_state.get(target_key, "")
                st.session_state[target_key] = (current + "\n" + "\n".join(new_lines)).strip()
                st.toast(f"Uploaded {len(new_lines)} file(s)!")
                st.rerun()


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Manager Dashboard")
    st.success("☁️ Google Sheets connected")
    st.markdown("---")
    st.markdown("### 👥 Your Team")

    new_name = st.text_input("Add person", placeholder="Jane Smith", label_visibility="collapsed")
    if st.button("➕ Add", use_container_width=True) and new_name.strip():
        save(dm().add_direct_report, new_name.strip(), sheet=None, success_msg=None)
        st.session_state.direct_reports = dm().get_direct_reports()
        st.rerun()

    reports = st.session_state.direct_reports
    if reports:
        for r in reports:
            st.markdown(f"• {r}")
        remove = st.selectbox("Remove", ["—"] + reports, label_visibility="collapsed")
        if st.button("🗑 Remove", use_container_width=True) and remove != "—":
            save(dm().remove_direct_report, remove, sheet=None, success_msg=None)
            st.session_state.direct_reports = dm().get_direct_reports()
            st.rerun()
    else:
        st.caption("No team members yet.")

    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("_data_"):
                del st.session_state[k]
        st.session_state.direct_reports = dm().get_direct_reports()
        st.rerun()
    st.caption(f"Refreshed: {datetime.now().strftime('%H:%M')}")


# ── header ────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Manager Dashboard")
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
    "🔍 Investigations",
    "🔬 Scripts",
    "📋 Procedures",
    "📝 Notes",
])
tab_todo, tab_issues, tab_actions, tab_meetings, tab_invest, tab_scripts, tab_procedures, tab_notes = tabs


# ═══════════════════════════════════════════════════════════════════════════════
# TODO
# ═══════════════════════════════════════════════════════════════════════════════
with tab_todo:
    st.markdown('<div class="section-header">TODO</div>', unsafe_allow_html=True)

    # Quick-add input
    col_in, col_btn = st.columns([5, 1])
    new_task = col_in.text_input("Add a task", key="todo_input", placeholder="What needs doing?", label_visibility="collapsed")
    if col_btn.button("➕ Add", use_container_width=True) and new_task.strip():
        save(dm().append_row, "TODO", {
            "Task": new_task.strip(), "Done": "No", "Created": str(date.today()),
        }, sheet="TODO", success_msg=None)

    st.markdown("---")

    df = get_data("TODO")
    if df.empty:
        st.info("Nothing here yet — type above to add your first task.")
    else:
        pending = df[df["Done"] == "No"].reset_index(drop=False) if "Done" in df.columns else df.reset_index(drop=False)
        if "Created" in pending.columns: pending = pending.sort_values("Created", ascending=False)
        done_df = df[df["Done"] == "Yes"].reset_index(drop=False) if "Done" in df.columns else pd.DataFrame()

        if pending.empty:
            st.success("🎉 All done!")
        else:
            for _, row in pending.iterrows():
                orig_idx = int(row["index"])
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                    c1.markdown(f"{row.get('Task','')} <small style='color:#94a3b8'>&nbsp;{row.get('Created','')}</small>", unsafe_allow_html=True)
                    if c2.button("✓", key=f"td_done_{orig_idx}", use_container_width=True, help="Mark done"):
                        dm().update_cell("TODO", orig_idx, "Done", "Yes")
                        invalidate("TODO")
                        st.rerun()
                    if c3.button("✏️", key=f"td_edit_{orig_idx}", use_container_width=True, help="Edit"):
                        st.session_state[f"editing_todo_{orig_idx}"] = True
                    if c4.button("🗑", key=f"td_del_{orig_idx}", use_container_width=True, help="Delete"):
                        dm().delete_row("TODO", orig_idx)
                        invalidate("TODO")
                        st.rerun()
                    if st.session_state.get(f"editing_todo_{orig_idx}"):
                        new_val = st.text_input("Edit task", value=row.get("Task",""), key=f"td_val_{orig_idx}")
                        s1, s2 = st.columns(2)
                        if s1.button("💾 Save", key=f"td_sv_{orig_idx}", use_container_width=True):
                            dm().update_cell("TODO", orig_idx, "Task", new_val.strip())
                            st.session_state[f"editing_todo_{orig_idx}"] = False
                            invalidate("TODO")
                            st.rerun()
                        if s2.button("Cancel", key=f"td_cancel_{orig_idx}", use_container_width=True):
                            st.session_state[f"editing_todo_{orig_idx}"] = False
                            st.rerun()

        if not done_df.empty:
            with st.expander(f"✅ {len(done_df)} completed"):
                for _, row in done_df.iterrows():
                    orig_idx = int(row["index"])
                    c1, c2 = st.columns([7, 1])
                    c1.markdown(f"~~{row.get('Task','')}~~")
                    if c2.button("🗑", key=f"td_ddel_{orig_idx}", use_container_width=True):
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
                    ib1, ib2 = st.columns(2)
                    cur_status = row.get("Status","Open")
                    if cur_status != "Resolved":
                        if ib1.button("✅ Mark Resolved", key=f"is_res_{orig_idx}", use_container_width=True):
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
        f_owner = st.selectbox("Filter by owner", ["Everyone"] + ["Me"] + st.session_state.direct_reports, key="ac_filt")
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
# INVESTIGATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_invest:
    st.markdown('<div class="section-header">Investigations</div>', unsafe_allow_html=True)
    st.caption("For bigger, multi-session investigations. Attach files by pasting links (Google Drive, Imgur, etc.) — one per line, optionally labeled.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Start a new investigation**")
        r1c1, r1c2 = st.columns([2, 1])
        inv_title  = r1c1.text_input("Title", key="inv_title", placeholder="e.g. Duplicate properties in StorTrack ETL")
        inv_status = r1c2.selectbox("Status", ["Open","Ongoing","Resolved"], key="inv_status")
        inv_tags   = st.text_input("Tags (optional)", key="inv_tags", placeholder="e.g. ETL, duplicates, StorTrack")
        inv_summary = st.text_area("Summary", key="inv_summary", height=300,
                                   placeholder="What's the investigation about? What have you found so far? Paste chat summaries, findings, conclusions here.")
        files_upload_widget("inv_files_upl", "inv_files")
        inv_files = st.text_area("Files / links (one per line, optional)", key="inv_files", height=100,
                                 placeholder="Screenshot of issue: https://imgur.com/...\nFull data export: https://drive.google.com/...")
        if st.button("Save Investigation", type="primary", use_container_width=True):
            if not inv_title.strip():
                st.warning("Title required.")
            else:
                save(dm().append_row, "Investigations", {
                    "Title": inv_title.strip(), "Status": inv_status,
                    "Summary": inv_summary.strip(), "Files": inv_files.strip(),
                    "Tags": inv_tags.strip(), "Created": str(date.today()),
                }, sheet="Investigations", success_msg="Investigation saved!")

    st.markdown("---")

    df = get_data("Investigations")
    if df.empty:
        st.info("No investigations logged yet.\n\nUse this for things like:\n- A multi-day debugging effort\n- A data discrepancy you're tracking down\n- Anything where you need to keep notes across multiple sessions")
    else:
        sc1, sc2 = st.columns([2, 1])
        search   = sc1.text_input("🔍 Search", key="inv_search")
        all_st   = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
        f_status = sc2.selectbox("Status", all_st, key="inv_status_filter")

        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        if f_status != "All" and "Status" in view.columns: view = view[view["Status"] == f_status]

        status_icon = {"Open":"🔴","Ongoing":"🟡","Resolved":"✅"}

        edit_df = add_delete_col(view[[c for c in ["index","Title","Status","Tags","Created"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=["Open","Ongoing","Resolved"]),
        }, use_container_width=True, hide_index=True, key="inv_editor")

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save status", key="inv_save", use_container_width=True):
            for _, row in edited.iterrows():
                orig_idx = int(row["index"])
                if row.get("Status") != df.loc[orig_idx].get("Status"):
                    dm().update_cell("Investigations", orig_idx, "Status", row["Status"])
            invalidate("Investigations")
            st.toast("Saved!")
            st.rerun()
        if bc2.button("🗑 Delete selected", key="inv_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Investigations", int(idx))
                invalidate("Investigations")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            icon = status_icon.get(row.get("Status",""), "📄")
            with st.expander(f"{icon} **{row.get('Title','')}**  ·  {row.get('Status','')}  ·  {row.get('Created','')}"):
                if row.get("Tags"):
                    st.markdown(" ".join([f"`{t.strip()}`" for t in row["Tags"].split(",") if t.strip()]))
                if row.get("Summary"):
                    st.markdown(row["Summary"])

                if row.get("Files"):
                    st.markdown("**📎 Files / links:**")
                    for line in row["Files"].split("\n"):
                        line = line.strip()
                        if not line: continue
                        if ":" in line and ("http" in line.split(":",1)[1]):
                            label, url = line.split(":", 1)
                            url = url.strip()
                            st.markdown(f"- [{label.strip()}]({url})")
                            if is_image_url(url) or "imgur" in url or "drive.google" in url:
                                st.image(resolve_image_url(url))
                        elif line.startswith("http"):
                            st.markdown(f"- [{line}]({line})")
                            if is_image_url(line) or "imgur" in line or "drive.google" in line:
                                st.image(resolve_image_url(line))
                        else:
                            st.markdown(f"- {line}")

                st.markdown("---")
                st.markdown("### ✏️ Edit")
                e_title   = st.text_input("Title", value=row.get("Title",""), key=f"inv_et_{orig_idx}")
                e_tags    = st.text_input("Tags",  value=row.get("Tags",""),  key=f"inv_etg_{orig_idx}")
                e_summary = st.text_area("Summary", value=row.get("Summary",""), key=f"inv_es_{orig_idx}", height=300)
                files_upload_widget(f"inv_ef_upl_{orig_idx}", f"inv_ef_{orig_idx}")
                e_files   = st.text_area("Files / links", value=row.get("Files",""), key=f"inv_ef_{orig_idx}", height=100)

                ib1, ib2 = st.columns(2)
                if ib1.button("💾 Save changes", key=f"inv_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Title",e_title),("Tags",e_tags),("Summary",e_summary),("Files",e_files)]:
                        if val != row.get(col,""):
                            dm().update_cell("Investigations", orig_idx, col, val)
                    invalidate("Investigations")
                    st.toast("Saved!")
                    st.rerun()
                if ib2.button("🗑 Delete", key=f"inv_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Investigations", orig_idx)
                    invalidate("Investigations")
                    st.toast("Deleted!")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPTS — pipeline / schedule tracker
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scripts:
    st.markdown('<div class="section-header">Script & Pipeline Tracker</div>', unsafe_allow_html=True)
    st.caption("Track scheduled scripts — what they run, what notebooks they call, what tables they write to, and how often.")

    form_col, _ = st.columns([5, 2])
    with form_col, st.container(border=True):
        st.markdown("**➕ Add a script / pipeline**")
        r1c1, r1c2, r1c3 = st.columns(3)
        sc_name    = r1c1.text_input("Script name", key="sc_name", placeholder="e.g. Daily Sales Refresh")
        sc_sched   = r1c2.selectbox("Schedule", ["Daily","Weekly","Monthly","Ad hoc","Continuous","Other"], key="sc_sched")
        sc_owner   = r1c3.text_input("Owner", key="sc_owner", placeholder="e.g. Data team")
        r2c1, r2c2 = st.columns(2)
        sc_status  = r2c1.selectbox("Status", ["Active","Paused","Broken","Under Review","Deprecated"], key="sc_status")
        sc_lastrun = r2c2.text_input("Last run", key="sc_lastrun", placeholder="e.g. 2026-04-27 06:00")
        sc_desc    = st.text_area("What does it do?", key="sc_desc", height=120,
                                  placeholder="Brief description of purpose and logic")
        nb1, nb2 = st.columns(2)
        sc_nbs     = nb1.text_area("Notebooks / child scripts", key="sc_nbs", height=120,
                                  placeholder="List the notebooks or scripts it calls, one per line")
        sc_tables  = nb2.text_area("Output tables / destinations", key="sc_tables", height=120,
                                  placeholder="List tables or systems it writes to, one per line")
        sc_notes   = st.text_area("Notes / known issues", key="sc_notes", height=120,
                                  placeholder="Quirks, known issues, dependencies...")
        sc_lang    = st.selectbox("Code language", ["SQL","Python","Shell / Bash","DAX","Other"], key="sc_lang_sel")
        sc_code    = st.text_area("Code (optional)", key="sc_code", height=250,
                                  placeholder="Paste the main script or key code blocks here...")
        if st.button("Save Script", type="primary", use_container_width=True):
            if not sc_name.strip():
                st.warning("Name required.")
            else:
                save(dm().append_row, "Scripts", {
                    "Name": sc_name.strip(), "Schedule": sc_sched,
                    "Description": sc_desc.strip(), "Notebooks": sc_nbs.strip(),
                    "OutputTables": sc_tables.strip(), "Owner": sc_owner.strip(),
                    "Status": sc_status, "LastRun": sc_lastrun.strip(),
                    "Notes": sc_notes.strip(),
                    "Code": sc_code.strip(),
                    "Language": sc_lang,
                    "Created": str(date.today()),
                }, sheet="Scripts", success_msg="Script saved!")

    st.markdown("---")

    df = get_data("Scripts")
    if df.empty:
        st.info("No scripts logged yet.")
    else:
        sc1, sc2 = st.columns([2, 1])
        search   = sc1.text_input("🔍 Search", key="sc_search")
        all_st   = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
        f_status = sc2.selectbox("Status", all_st, key="sc_status_filter")

        view = df.copy().reset_index(drop=False)
        if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
        if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
        if f_status != "All" and "Status" in view.columns: view = view[view["Status"] == f_status]

        status_icon = {"Active":"🟢","Paused":"🟡","Broken":"🔴","Under Review":"🔍","Deprecated":"⚫"}

        edit_df = add_delete_col(view[[c for c in ["index","Name","Schedule","Owner","Status","LastRun"] if c in view.columns]])
        edited = st.data_editor(edit_df, column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "index":  st.column_config.Column("Row", disabled=True, width="small"),
            "Status": st.column_config.SelectboxColumn("Status", options=["Active","Paused","Broken","Under Review","Deprecated"]),
        }, use_container_width=True, hide_index=True, key="scripts_editor")

        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save status", key="sc_save", use_container_width=True):
            for _, row in edited.iterrows():
                orig_idx = int(row["index"])
                if row.get("Status") != df.loc[orig_idx].get("Status"):
                    dm().update_cell("Scripts", orig_idx, "Status", row["Status"])
            invalidate("Scripts")
            st.toast("Saved!")
            st.rerun()
        if bc2.button("🗑 Delete selected", key="sc_del", use_container_width=True):
            to_del = edited[edited["Delete"] == True]["index"].tolist()
            if not to_del:
                st.info("Tick rows first.")
            else:
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Scripts", int(idx))
                invalidate("Scripts")
                st.rerun()

        st.markdown("---")
        for _, row in view.iterrows():
            orig_idx = int(row["index"])
            icon = status_icon.get(row.get("Status",""), "📄")
            with st.expander(f"{icon} **{row.get('Name','')}**  ·  {row.get('Schedule','')}  ·  {row.get('Status','')}"):

                d1, d2 = st.columns(2)
                d1.markdown(f"**Owner:** {row.get('Owner','—')}")
                d1.markdown(f"**Last run:** {row.get('LastRun','—')}")
                d2.markdown(f"**Schedule:** {row.get('Schedule','—')}")

                if row.get("Description"):
                    st.markdown("**What it does:**")
                    st.markdown(row["Description"])

                nb1, nb2 = st.columns(2)
                if row.get("Notebooks"):
                    nb1.markdown("**📓 Notebooks / child scripts:**")
                    nb1.text(row["Notebooks"])
                if row.get("OutputTables"):
                    nb2.markdown("**📊 Output tables / destinations:**")
                    nb2.text(row["OutputTables"])

                if row.get("Notes"):
                    st.markdown("**⚠️ Notes / known issues:**")
                    st.warning(row["Notes"])

                if row.get("Code"):
                    st.markdown("**💻 Code:**")
                    code_text = row["Code"]
                    lang_map = {"SQL":"sql","Python":"python","Shell / Bash":"bash","DAX":"text","Other":"text"}
                    lang = lang_map.get(row.get("Language",""), "sql" if "select " in code_text.lower() else "python" if "import " in code_text else "text")
                    st.code(code_text, language=lang)

                st.markdown("---")
                st.markdown("### ✏️ Edit this script")
                e_name    = st.text_input("Name",       value=row.get("Name",""),        key=f"sc_en_{orig_idx}")
                e_sched   = st.selectbox("Schedule",    ["Daily","Weekly","Monthly","Ad hoc","Continuous","Other"],
                                         index=["Daily","Weekly","Monthly","Ad hoc","Continuous","Other"].index(row.get("Schedule","Ad hoc")) if row.get("Schedule") in ["Daily","Weekly","Monthly","Ad hoc","Continuous","Other"] else 0,
                                         key=f"sc_esc_{orig_idx}")
                e_owner   = st.text_input("Owner",      value=row.get("Owner",""),       key=f"sc_eo_{orig_idx}")
                e_lastrun = st.text_input("Last run",   value=row.get("LastRun",""),     key=f"sc_elr_{orig_idx}")
                e_desc    = st.text_area("Description", value=row.get("Description",""), key=f"sc_ed_{orig_idx}", height=120)
                e_nbs     = st.text_area("Notebooks",   value=row.get("Notebooks",""),   key=f"sc_enb_{orig_idx}", height=120)
                e_tables  = st.text_area("Output tables", value=row.get("OutputTables",""), key=f"sc_et_{orig_idx}", height=120)
                e_notes   = st.text_area("Notes",       value=row.get("Notes",""),       key=f"sc_eno_{orig_idx}", height=120)
                e_lang_opts = ["SQL","Python","Shell / Bash","DAX","Other"]
                e_lang    = st.selectbox("Language", e_lang_opts,
                                        index=e_lang_opts.index(row.get("Language","SQL")) if row.get("Language") in e_lang_opts else 0,
                                        key=f"sc_elang_{orig_idx}")
                e_code    = st.text_area("Code",        value=row.get("Code",""),        key=f"sc_eco_{orig_idx}", height=250)

                scb1, scb2 = st.columns(2)
                if scb1.button("💾 Save changes", key=f"sc_sv_{orig_idx}", use_container_width=True):
                    for col, val in [("Name",e_name),("Schedule",e_sched),("Owner",e_owner),
                                     ("LastRun",e_lastrun),("Description",e_desc),
                                     ("Notebooks",e_nbs),("OutputTables",e_tables),("Notes",e_notes),
                                     ("Language",e_lang),("Code",e_code)]:
                        if val != row.get(col,""):
                            dm().update_cell("Scripts", orig_idx, col, val)
                    invalidate("Scripts")
                    st.toast("Saved!")
                    st.rerun()
                if scb2.button("🗑 Delete", key=f"sc_del_{orig_idx}", use_container_width=True):
                    dm().delete_row("Scripts", orig_idx)
                    invalidate("Scripts")
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
