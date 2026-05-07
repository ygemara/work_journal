import streamlit as st
import pandas as pd
from datetime import datetime, date
from data_manager import SheetsManager

st.set_page_config(page_title="Manager Dashboard", page_icon="📋", layout="wide")

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
    st.markdown("## 🔒 Manager Dashboard")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            if username == "admin" and password == "admin":
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


def sorted_by_created(df: pd.DataFrame) -> pd.DataFrame:
    if "Created" in df.columns:
        return df.sort_values("Created", ascending=False)
    return df


def resolve_image_url(url: str) -> str:
    """Convert share URLs to direct image URLs."""
    import re
    url = url.strip()
    # Google Drive
    m = re.search(r"/file/d/([^/]+)", url)
    if m:
        return f"https://drive.google.com/uc?id={m.group(1)}"
    # Imgur page link -> direct image
    m = re.match(r"https?://imgur\.com/([a-zA-Z0-9]+)$", url)
    if m:
        return f"https://i.imgur.com/{m.group(1)}.png"
    return url


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
    "🔴 Issues",
    "✅ Action Items",
    "🗒 Meetings",
    "🔬 Scripts",
    "📋 Procedures",
    "📚 Reference",
    "💬 1:1 Agenda",
    "📝 Notes",
])
tab_issues, tab_actions, tab_meetings, tab_scripts, tab_procedures, tab_ref, tab_agenda, tab_notes = tabs


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_issues:
    st.markdown('<div class="section-header">Outstanding Issues</div>', unsafe_allow_html=True)
    col_form, col_list = st.columns([1, 2], gap="large")

    with col_form:
        with st.container(border=True):
            st.markdown("**➕ Log a new issue**")
            i_title    = st.text_input("Title", key="i_title")
            i_desc     = st.text_area("Detail (optional)", key="i_desc", height=80)
            i_priority = st.selectbox("Priority", ["High", "Medium", "Low"], key="i_priority")
            i_owner    = st.text_input("Owner", key="i_owner", placeholder="e.g. Jane Smith")
            i_due      = st.date_input("Due (optional)", value=None, key="i_due")
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

    with col_list:
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

            # Detail expanders for description
            has_desc = view[view["Description"].str.strip() != ""] if "Description" in view.columns else pd.DataFrame()
            if not has_desc.empty:
                st.markdown("---")
                for _, row in has_desc.iterrows():
                    orig_idx = int(row["index"])
                    with st.expander(f"{row.get('Title','')}  ·  {row.get('Created','')}"):
                        st.markdown(row.get("Description",""))
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
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ New action item**")
            ac_task  = st.text_input("Task", key="ac_task")
            ac_owner = st.text_input("Owner", key="ac_owner", placeholder="e.g. Me, Jane")
            ac_due   = st.date_input("Due date", key="ac_due")
            ac_src   = st.selectbox("From", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
            ac_notes = st.text_area("Notes / context", key="ac_notes", height=80,
                                    placeholder="What exactly needs to be done?")
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

    with col_v:
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

            # Notes/image expanders
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
                        e_notes = st.text_area("Notes",       value=row.get("Notes",""),   key=f"ac_en_{orig_idx}", height=80)
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
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Log a meeting**")
            mt_title     = st.text_input("Meeting title", key="mt_title")
            mt_date      = st.date_input("Date", key="mt_date")
            mt_attendees = st.text_input("Attendees", key="mt_att", placeholder="e.g. Jane, John, Sarah")
            mt_notes     = st.text_area("Notes / summary", key="mt_notes", height=120,
                                        placeholder="What was discussed?")
            mt_questions = st.text_area("Outstanding questions", key="mt_questions", height=80,
                                        placeholder="What's still unresolved?")
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

    with col_v:
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
                    e_notes = st.text_area("Notes / summary",      value=row.get("Notes",""),     key=f"mt_en_{orig_idx}", height=120)
                    e_qs    = st.text_area("Outstanding questions", value=row.get("Questions",""), key=f"mt_eq_{orig_idx}", height=80)
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
# SCRIPTS — pipeline / schedule tracker
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scripts:
    st.markdown('<div class="section-header">Script & Pipeline Tracker</div>', unsafe_allow_html=True)
    st.caption("Track scheduled scripts — what they run, what notebooks they call, what tables they write to, and how often.")

    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Add a script / pipeline**")
            sc_name    = st.text_input("Script name", key="sc_name", placeholder="e.g. Daily Sales Refresh")
            sc_sched   = st.selectbox("Schedule", ["Daily","Weekly","Monthly","Ad hoc","Continuous","Other"], key="sc_sched")
            sc_owner   = st.text_input("Owner", key="sc_owner", placeholder="e.g. Data team")
            sc_status  = st.selectbox("Status", ["Active","Paused","Broken","Under Review","Deprecated"], key="sc_status")
            sc_desc    = st.text_area("What does it do?", key="sc_desc", height=80,
                                      placeholder="Brief description of purpose and logic")
            sc_nbs     = st.text_area("Notebooks / child scripts", key="sc_nbs", height=80,
                                      placeholder="List the notebooks or scripts it calls, one per line")
            sc_tables  = st.text_area("Output tables / destinations", key="sc_tables", height=80,
                                      placeholder="List tables or systems it writes to, one per line")
            sc_lastrun = st.text_input("Last run", key="sc_lastrun", placeholder="e.g. 2026-04-27 06:00")
            sc_notes   = st.text_area("Notes / known issues", key="sc_notes", height=80,
                                      placeholder="Quirks, known issues, dependencies...")
            sc_lang    = st.selectbox("Code language", ["SQL","Python","Shell / Bash","DAX","Other"], key="sc_lang_sel")
            sc_code    = st.text_area("Code (optional)", key="sc_code", height=160,
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

    with col_v:
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

            # Status indicator colours
            status_icon = {"Active":"🟢","Paused":"🟡","Broken":"🔴","Under Review":"🔍","Deprecated":"⚫"}

            # Summary table
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

                    # Two-column layout inside expander
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
                    e_desc    = st.text_area("Description", value=row.get("Description",""), key=f"sc_ed_{orig_idx}", height=80)
                    e_nbs     = st.text_area("Notebooks",   value=row.get("Notebooks",""),   key=f"sc_enb_{orig_idx}", height=80)
                    e_tables  = st.text_area("Output tables", value=row.get("OutputTables",""), key=f"sc_et_{orig_idx}", height=80)
                    e_notes   = st.text_area("Notes",       value=row.get("Notes",""),       key=f"sc_eno_{orig_idx}", height=80)
                    e_lang_opts = ["SQL","Python","Shell / Bash","DAX","Other"]
                    e_lang    = st.selectbox("Language", e_lang_opts,
                                            index=e_lang_opts.index(row.get("Language","SQL")) if row.get("Language") in e_lang_opts else 0,
                                            key=f"sc_elang_{orig_idx}")
                    e_code    = st.text_area("Code",        value=row.get("Code",""),        key=f"sc_eco_{orig_idx}", height=200)

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

    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Add a procedure**")
            pr_title = st.text_input("Title", key="pr_title", placeholder="e.g. How to debug Power BI refresh")
            pr_cat   = st.selectbox("Category", [
                "Debugging", "Deployment", "Onboarding", "Reporting",
                "Data Pipeline", "HR Process", "Admin", "Other"
            ], key="pr_cat")
            pr_tags  = st.text_input("Tags", key="pr_tags", placeholder="e.g. Power BI, data, reporting")
            pr_steps = st.text_area("Steps / content", key="pr_steps", height=200,
                                    placeholder="Write the steps here. Use numbered lists, bullet points, etc.")
            pr_notes = st.text_area("Notes / context", key="pr_notes", height=80,
                                    placeholder="When to use this, prerequisites, gotchas...")
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

    with col_v:
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

            # Index table
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
                    e_title = st.text_input("Title",    value=row.get("Title",""),    key=f"pr_et_{orig_idx}")
                    e_steps = st.text_area("Steps",     value=row.get("Steps",""),    key=f"pr_es_{orig_idx}", height=200)
                    e_notes = st.text_area("Notes",     value=row.get("Notes",""),    key=f"pr_en_{orig_idx}", height=80)
                    e_tags  = st.text_input("Tags",     value=row.get("Tags",""),     key=f"pr_etg_{orig_idx}")

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
# REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown('<div class="section-header">Reference Library</div>', unsafe_allow_html=True)
    st.caption("Store SQL queries, code snippets, templates — with your own explanation.")

    col_add, col_view = st.columns([1, 2], gap="large")

    with col_add:
        with st.container(border=True):
            st.markdown("**➕ Add entry**")
            r_title = st.text_input("Title", key="r_title")
            r_cat   = st.selectbox("Category", ["SQL / Query","Python","Shell / Bash","DAX / Power BI","Process / Checklist","Template","Formula","Other"], key="r_cat")
            r_tags  = st.text_input("Tags", key="r_tags")
            r_body  = st.text_area("Content", key="r_body", height=160)
            r_notes = st.text_area("Your notes / explanation", key="r_notes", height=100)
            if st.button("Save", type="primary", use_container_width=True):
                if not r_title.strip() or not r_body.strip():
                    st.warning("Title and content required.")
                else:
                    save(dm().append_row, "Reference", {
                        "Title": r_title.strip(), "Category": r_cat,
                        "Content": r_body.strip(), "Explanation": r_notes.strip(),
                        "Tags": r_tags.strip(), "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }, sheet="Reference", success_msg="Saved!")

    with col_view:
        df = get_data("Reference")
        if df.empty:
            st.info("Nothing saved yet.")
        else:
            sc1, sc2 = st.columns([2, 1])
            search  = sc1.text_input("🔍 Search", key="r_search")
            all_cats = ["All"] + sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else ["All"]
            f_cat   = sc2.selectbox("Category", all_cats, key="r_cat_filter")
            view = df.copy().reset_index(drop=False)
            if "Created" in view.columns: view = view.sort_values("Created", ascending=False)
            if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_cat != "All" and "Category" in view.columns: view = view[view["Category"] == f_cat]

            edit_df = add_delete_col(view[[c for c in ["index","Title","Category","Tags"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
            }, use_container_width=True, hide_index=True, key="ref_editor")

            if st.button("🗑 Delete selected", key="ref_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                if not to_del:
                    st.info("Tick rows first.")
                else:
                    for idx in sorted(to_del, reverse=True):
                        dm().delete_row("Reference", int(idx))
                    invalidate("Reference")
                    st.rerun()

            st.markdown("---")
            for _, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  `{row.get('Category','')}`"):
                    if row.get("Content"):
                        cat  = row.get("Category","")
                        lang = "sql" if "SQL" in cat else "python" if "Python" in cat else "bash" if "Shell" in cat else "text"
                        st.code(row["Content"], language=lang)
                    if row.get("Explanation"):
                        st.info(row["Explanation"])


# ═══════════════════════════════════════════════════════════════════════════════
# 1:1 AGENDA
# ═══════════════════════════════════════════════════════════════════════════════
with tab_agenda:
    st.markdown('<div class="section-header">1:1 Agenda Builder</div>', unsafe_allow_html=True)
    if not st.session_state.direct_reports:
        st.info("👈 Add team members in the sidebar first.")
    else:
        selected = st.selectbox("Who are you meeting with?", st.session_state.direct_reports, key="ag_person")
        col_add, col_view = st.columns([1, 2], gap="large")

        with col_add:
            with st.container(border=True):
                st.markdown(f"**➕ Add topic for {selected}**")
                a_topic    = st.text_area("Topic", key="a_topic", height=80)
                a_type     = st.selectbox("Category", ["Update","Feedback","Blocker","Development","Recognition","Other"], key="a_type")
                a_added_by = st.text_input("Added by", key="a_by", value="Me")
                if st.button("Add to Agenda", type="primary", use_container_width=True):
                    if not a_topic.strip():
                        st.warning("Topic required.")
                    else:
                        save(dm().append_row, "Agenda", {
                            "Person": selected, "Topic": a_topic.strip(),
                            "Category": a_type, "AddedBy": a_added_by.strip(),
                            "Discussed": "No", "Created": str(date.today()),
                        }, sheet="Agenda", success_msg="Added!")

        with col_view:
            df = get_data("Agenda")
            person_df = df[df["Person"] == selected].reset_index(drop=False) if not df.empty and "Person" in df.columns else pd.DataFrame()
            show_done = st.toggle("Show discussed", False, key="ag_show_done")

            pending_raw = person_df[person_df["Discussed"] == "No"]  if not person_df.empty and "Discussed" in person_df.columns else person_df
            pending = pending_raw.sort_values("Created", ascending=False) if "Created" in pending_raw.columns else pending_raw
            done    = person_df[person_df["Discussed"] == "Yes"] if not person_df.empty and "Discussed" in person_df.columns else pd.DataFrame()

            if person_df.empty:
                st.info(f"No topics for {selected} yet.")
            else:
                st.markdown(f"**{len(pending)} to discuss · {len(done)} done**")
                if not pending.empty:
                    edit_df = add_delete_col(pending[[c for c in ["index","Topic","Category","AddedBy","Created"] if c in pending.columns]])
                    edited = st.data_editor(edit_df, column_config={
                        "Delete": st.column_config.CheckboxColumn("🗑 / ✓", width="small"),
                        "index":  st.column_config.Column("Row", disabled=True, width="small"),
                    }, use_container_width=True, hide_index=True, key="agenda_editor")

                    bc1, bc2 = st.columns(2)
                    if bc1.button("✓ Mark Done", key="ag_done", use_container_width=True):
                        checked = edited[edited["Delete"] == True]["index"].tolist()
                        if not checked:
                            st.info("Tick rows to mark as done.")
                        else:
                            for idx in checked:
                                dm().update_cell("Agenda", int(idx), "Discussed", "Yes")
                            invalidate("Agenda")
                            st.toast("Marked done!")
                            st.rerun()
                    if bc2.button("🗑 Delete", key="ag_del", use_container_width=True):
                        to_del = edited[edited["Delete"] == True]["index"].tolist()
                        if not to_del:
                            st.info("Tick rows first.")
                        else:
                            for idx in sorted(to_del, reverse=True):
                                dm().delete_row("Agenda", int(idx))
                            invalidate("Agenda")
                            st.rerun()

                if show_done and not done.empty:
                    st.markdown("---")
                    st.markdown("**Previously discussed:**")
                    st.dataframe(done[[c for c in ["Topic","Category","Created"] if c in done.columns]], use_container_width=True, hide_index=True)


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
