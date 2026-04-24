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


@st.cache_data(ttl=120, show_spinner=False)
def get_data(sheet: str) -> pd.DataFrame:
    return get_manager().get_data(sheet)


def save(fn, *args, success_msg="Saved!", **kwargs):
    try:
        fn(*args, **kwargs)
        get_data.clear()
        if success_msg:
            st.toast(success_msg)
        st.rerun()
    except Exception as e:
        st.error(f"❌ {e}")


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Manager Dashboard")
    st.success("☁️ Google Sheets connected")
    st.markdown("---")
    st.markdown("### 👥 Your Team")

    new_name = st.text_input("Add person", placeholder="Jane Smith", label_visibility="collapsed")
    if st.button("➕ Add", use_container_width=True) and new_name.strip():
        save(dm().add_direct_report, new_name.strip(), success_msg=None)

    reports = st.session_state.direct_reports
    if reports:
        for r in reports:
            st.markdown(f"• {r}")
        remove = st.selectbox("Remove", ["—"] + reports, label_visibility="collapsed")
        if st.button("🗑 Remove", use_container_width=True) and remove != "—":
            save(dm().remove_direct_report, remove, success_msg=None)
    else:
        st.caption("No team members yet.")

    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        get_data.clear()
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
    _e = get_data("Emails")
    open_issues     = int((_i["Status"] == "Open").sum())           if not _i.empty and "Status" in _i.columns else 0
    high_pri        = int(((_i["Status"] == "Open") & (_i["Priority"] == "High")).sum()) if not _i.empty else 0
    pending_actions = int((_a["Status"] == "Pending").sum())        if not _a.empty and "Status" in _a.columns else 0
    urgent_emails   = int(((_e["Status"] == "Pending") & (_e["Priority"] == "Urgent")).sum()) if not _e.empty else 0
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔴 Open Issues",    open_issues)
    k2.metric("⚡ High Priority",   high_pri)
    k3.metric("✅ Pending Actions", pending_actions)
    k4.metric("📧 Urgent Emails",   urgent_emails)
except Exception as e:
    st.warning(f"Could not load summary: {e}")

st.markdown("---")

tabs = st.tabs(["🔴 Issues", "💬 1:1 Agenda", "✅ Action Items", "📅 Calendar", "📧 Emails", "🗒 Meetings", "🔬 Scripts", "📚 Reference", "📝 Notes"])
tab_issues, tab_agenda, tab_actions, tab_calendar, tab_emails, tab_meetings, tab_scripts, tab_ref, tab_notes = tabs


# ── helpers ───────────────────────────────────────────────────────────────────
def delete_selected(sheet: str, df: pd.DataFrame, edited: pd.DataFrame):
    """Delete rows where the Delete checkbox is ticked."""
    to_delete = edited[edited["Delete"] == True].index.tolist()
    if not to_delete:
        st.info("Tick the Delete box on a row then click Delete Selected.")
        return
    for idx in sorted(to_delete, reverse=True):
        dm().delete_row(sheet, idx)
    get_data.clear()
    st.toast(f"Deleted {len(to_delete)} row(s).")
    st.rerun()


def add_delete_col(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "Delete", False)
    return df


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
                        "Priority": i_priority, "Owner": i_owner,
                        "Due": str(i_due) if i_due else "", "Status": "Open",
                        "Created": str(date.today()),
                    }, success_msg="Issue logged!")

    with col_list:
        df = get_data("Issues")
        if df.empty:
            st.info("No issues yet.")
        else:
            fc1, fc2 = st.columns(2)
            f_status   = fc1.multiselect("Status",   ["Open","In Progress","Resolved"], default=["Open","In Progress"])
            f_priority = fc2.multiselect("Priority", ["High","Medium","Low"],           default=["High","Medium","Low"])
            view = df.copy().reset_index(drop=False)  # keep original index
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map({"High":0,"Medium":1,"Low":2}).fillna(9)).sort_values("_s").drop(columns=["_s"])

            edit_df = add_delete_col(view[[c for c in ["index","Title","Priority","Owner","Created","Status","Description"] if c in view.columns]])
            edited = st.data_editor(
                edit_df,
                column_config={
                    "Delete":   st.column_config.CheckboxColumn("🗑", width="small"),
                    "index":    st.column_config.Column("Row", disabled=True, width="small"),
                    "Status":   st.column_config.SelectboxColumn("Status", options=["Open","In Progress","Resolved"]),
                    "Priority": st.column_config.SelectboxColumn("Priority", options=["High","Medium","Low"]),
                },
                use_container_width=True, hide_index=True, key="issues_editor"
            )

            bc1, bc2 = st.columns(2)
            if bc1.button("💾 Save changes", key="issues_save", use_container_width=True):
                for _, row in edited.iterrows():
                    orig_idx = int(row["index"])
                    orig_row = df.loc[orig_idx]
                    if row.get("Status") != orig_row.get("Status"):
                        dm().update_cell("Issues", orig_idx, "Status", row["Status"])
                    if row.get("Priority") != orig_row.get("Priority"):
                        dm().update_cell("Issues", orig_idx, "Priority", row["Priority"])
                get_data.clear()
                st.toast("Saved!")
                st.rerun()
            if bc2.button("🗑 Delete selected", key="issues_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                if not to_del:
                    st.info("Tick Delete on a row first.")
                else:
                    for idx in sorted(to_del, reverse=True):
                        dm().delete_row("Issues", int(idx))
                    get_data.clear()
                    st.toast(f"Deleted {len(to_del)} row(s).")
                    st.rerun()


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
                            "Category": a_type, "AddedBy": a_added_by,
                            "Discussed": "No", "Created": str(date.today()),
                        }, success_msg="Added!")

        with col_view:
            df = get_data("Agenda")
            person_df = df[df["Person"] == selected].reset_index(drop=False) if not df.empty and "Person" in df.columns else pd.DataFrame()
            show_done = st.toggle("Show discussed", False, key="ag_show_done")

            pending = person_df[person_df["Discussed"] == "No"]  if not person_df.empty and "Discussed" in person_df.columns else person_df
            done    = person_df[person_df["Discussed"] == "Yes"] if not person_df.empty and "Discussed" in person_df.columns else pd.DataFrame()

            if person_df.empty:
                st.info(f"No topics for {selected} yet.")
            else:
                st.markdown(f"**{len(pending)} to discuss · {len(done)} done**")
                if not pending.empty:
                    edit_df = add_delete_col(pending[[c for c in ["index","Topic","Category","AddedBy","Created"] if c in pending.columns]])
                    edited = st.data_editor(
                        edit_df,
                        column_config={
                            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                            "index":  st.column_config.Column("Row", disabled=True, width="small"),
                        },
                        use_container_width=True, hide_index=True, key="agenda_editor"
                    )
                    bc1, bc2, bc3 = st.columns(3)
                    if bc1.button("✓ Mark Done", key="ag_done", use_container_width=True):
                        checked = edited[edited["Delete"] == True]["index"].tolist()
                        if not checked:
                            st.info("Tick rows to mark as done.")
                        else:
                            for idx in checked:
                                dm().update_cell("Agenda", int(idx), "Discussed", "Yes")
                            get_data.clear()
                            st.toast("Marked done!")
                            st.rerun()
                    if bc2.button("🗑 Delete", key="ag_del", use_container_width=True):
                        to_del = edited[edited["Delete"] == True]["index"].tolist()
                        if not to_del:
                            st.info("Tick rows first.")
                        else:
                            for idx in sorted(to_del, reverse=True):
                                dm().delete_row("Agenda", int(idx))
                            get_data.clear()
                            st.rerun()

                if show_done and not done.empty:
                    st.markdown("---")
                    st.markdown("**Previously discussed:**")
                    st.dataframe(done[[c for c in ["Topic","Category","Created"] if c in done.columns]], use_container_width=True, hide_index=True)


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
            ac_owner = st.text_input("Owner", key="ac_owner", placeholder="e.g. Me, Jane Smith")
            ac_due   = st.date_input("Due date", key="ac_due")
            ac_src   = st.selectbox("From", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
            ac_notes = st.text_area("Notes / context", key="ac_notes", height=80,
                                    placeholder="What exactly needs to be done?")
            if st.button("Add Action", type="primary", use_container_width=True):
                if not ac_task.strip():
                    st.warning("Task required.")
                else:
                    save(dm().append_row, "ActionItems", {
                        "Task": ac_task.strip(), "Owner": ac_owner,
                        "Due": str(ac_due), "Source": ac_src,
                        "Status": "Pending", "Notes": ac_notes.strip(),
                        "Created": str(date.today()),
                    }, success_msg="Added!")

    with col_v:
        df = get_data("ActionItems")
        if df.empty:
            st.info("No action items yet.")
        else:
            f_owner = st.selectbox("Filter by", ["Everyone","Me"] + st.session_state.direct_reports, key="ac_filt")
            today_str = str(date.today())
            view = df.copy().reset_index(drop=False)
            if "Status" in view.columns:
                view = view[view["Status"] != "Done"]
            if f_owner != "Everyone" and "Owner" in view.columns:
                view = view[view["Owner"] == f_owner]

            if view.empty:
                st.success("🎉 All clear!")
            else:
                if "Due" in view.columns:
                    view = view.copy()
                    view["⚠️"] = view.apply(lambda r: "🚨" if str(r.get("Due","")) < today_str and r.get("Status") == "Pending" else "", axis=1)
                edit_cols = [c for c in ["Delete","⚠️","index","Task","Owner","Due","Status","Notes","Source"] if c in ["Delete","⚠️","index"] or c in view.columns]
                edit_df = add_delete_col(view[[c for c in ["index","⚠️","Task","Owner","Created","Due","Status","Notes"] if c in view.columns or c in ["index","⚠️"]]])
                edited = st.data_editor(
                    edit_df,
                    column_config={
                        "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                        "index":  st.column_config.Column("Row", disabled=True, width="small"),
                        "⚠️":    st.column_config.Column("⚠️", disabled=True, width="small"),
                        "Status": st.column_config.SelectboxColumn("Status", options=["Pending","In Progress","Done"]),
                    },
                    use_container_width=True, hide_index=True, key="actions_editor"
                )
                bc1, bc2 = st.columns(2)
                if bc1.button("💾 Save changes", key="ac_save", use_container_width=True):
                    for _, row in edited.iterrows():
                        orig_idx = int(row["index"])
                        if row.get("Status") != df.loc[orig_idx].get("Status"):
                            dm().update_cell("ActionItems", orig_idx, "Status", row["Status"])
                    get_data.clear()
                    st.toast("Saved!")
                    st.rerun()
                if bc2.button("🗑 Delete selected", key="ac_del", use_container_width=True):
                    to_del = edited[edited["Delete"] == True]["index"].tolist()
                    if not to_del:
                        st.info("Tick rows first.")
                    else:
                        for idx in sorted(to_del, reverse=True):
                            dm().delete_row("ActionItems", int(idx))
                        get_data.clear()
                        st.rerun()

            done_df = df[df["Status"] == "Done"].reset_index(drop=False) if "Status" in df.columns else pd.DataFrame()
            if not done_df.empty:
                with st.expander(f"✅ {len(done_df)} completed"):
                    st.dataframe(done_df[[c for c in ["Task","Owner","Due"] if c in done_df.columns]], use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_calendar:
    st.markdown('<div class="section-header">Calendar & Upcoming Events</div>', unsafe_allow_html=True)
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Add event**")
            ev_title = st.text_input("Event name", key="ev_title")
            ev_date  = st.date_input("Date", key="ev_date")
            ev_time  = st.time_input("Time (optional)", value=None, key="ev_time", step=900)
            ev_type  = st.selectbox("Type", ["1:1","Team Meeting","Deadline","Performance Review","Planning","Other"], key="ev_type")
            ev_with  = st.text_input("With (optional)", key="ev_with", placeholder="e.g. John, Sarah")
            ev_notes = st.text_area("Notes", key="ev_notes", height=60)
            if st.button("Add Event", type="primary", use_container_width=True):
                if not ev_title.strip():
                    st.warning("Event needs a name.")
                else:
                    save(dm().append_row, "Calendar", {
                        "Title": ev_title.strip(), "Date": str(ev_date),
                        "Time": str(ev_time)[:5] if ev_time else "",
                        "Type": ev_type, "With": ev_with.strip(),
                        "Notes": ev_notes.strip(),
                    }, success_msg="Event added!")

    with col_v:
        df = get_data("Calendar")
        today_str = str(date.today())
        if df.empty:
            st.info("No events yet.")
        else:
            view = df.copy().reset_index(drop=False)
            if "Date" in view.columns:
                upcoming = view[view["Date"] >= today_str].sort_values("Date")
                past     = view[view["Date"] < today_str].sort_values("Date", ascending=False)
            else:
                upcoming, past = view, pd.DataFrame()

            if not upcoming.empty:
                st.markdown(f"**{len(upcoming)} upcoming**")
                edit_df = add_delete_col(upcoming[[c for c in ["index","Date","Time","Title","Type","With","Notes"] if c in upcoming.columns]])
                edited = st.data_editor(edit_df, column_config={
                    "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                    "index":  st.column_config.Column("Row", disabled=True, width="small"),
                }, use_container_width=True, hide_index=True, key="cal_editor")
                if st.button("🗑 Delete selected", key="cal_del", use_container_width=True):
                    to_del = edited[edited["Delete"] == True]["index"].tolist()
                    for idx in sorted(to_del, reverse=True):
                        dm().delete_row("Calendar", int(idx))
                    get_data.clear()
                    st.rerun()

            if not past.empty:
                with st.expander(f"🗓 {len(past)} past events"):
                    st.dataframe(past[[c for c in ["Date","Title","Type"] if c in past.columns]], use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EMAILS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_emails:
    st.markdown('<div class="section-header">Important Emails</div>', unsafe_allow_html=True)
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**📧 Log an email**")
            em_subject  = st.text_input("Subject", key="em_subject")
            em_from     = st.text_input("From", key="em_from")
            em_received = st.date_input("Received", key="em_received")
            em_priority = st.selectbox("Priority", ["Urgent","High","Medium","Low"], key="em_priority")
            em_action   = st.text_area("Action needed", key="em_action", height=80)
            em_notes    = st.text_area("Notes / summary", key="em_notes", height=80)
            if st.button("Save Email", type="primary", use_container_width=True):
                if not em_subject.strip():
                    st.warning("Subject required.")
                else:
                    save(dm().append_row, "Emails", {
                        "Subject": em_subject.strip(), "From": em_from.strip(),
                        "Received": str(em_received), "Priority": em_priority,
                        "Action": em_action.strip(), "Status": "Pending",
                        "Notes": em_notes.strip(), "Created": str(date.today()),
                    }, success_msg="Saved!")

    with col_v:
        df = get_data("Emails")
        if df.empty:
            st.info("No emails logged yet.")
        else:
            fc1, fc2 = st.columns(2)
            f_status   = fc1.multiselect("Status",   ["Pending","In Progress","Done"], default=["Pending","In Progress"], key="em_fs")
            f_priority = fc2.multiselect("Priority", ["Urgent","High","Medium","Low"], default=["Urgent","High","Medium","Low"], key="em_fp")
            view = df.copy().reset_index(drop=False)
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map({"Urgent":0,"High":1,"Medium":2,"Low":3}).fillna(9)).sort_values("_s").drop(columns=["_s"])

            edit_df = add_delete_col(view[[c for c in ["index","Subject","From","Received","Priority","Status","Action"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete":   st.column_config.CheckboxColumn("🗑", width="small"),
                "index":    st.column_config.Column("Row", disabled=True, width="small"),
                "Status":   st.column_config.SelectboxColumn("Status",   options=["Pending","In Progress","Done"]),
                "Priority": st.column_config.SelectboxColumn("Priority", options=["Urgent","High","Medium","Low"]),
            }, use_container_width=True, hide_index=True, key="emails_editor")

            bc1, bc2 = st.columns(2)
            if bc1.button("💾 Save changes", key="em_save", use_container_width=True):
                for _, row in edited.iterrows():
                    orig_idx = int(row["index"])
                    if row.get("Status") != df.loc[orig_idx].get("Status"):
                        dm().update_cell("Emails", orig_idx, "Status", row["Status"])
                    if row.get("Priority") != df.loc[orig_idx].get("Priority"):
                        dm().update_cell("Emails", orig_idx, "Priority", row["Priority"])
                get_data.clear()
                st.toast("Saved!")
                st.rerun()
            if bc2.button("🗑 Delete selected", key="em_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Emails", int(idx))
                get_data.clear()
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
            mt_type      = st.selectbox("Type", ["1:1","Team Meeting","Stakeholder","Interview","Planning","Retrospective","Other"], key="mt_type")
            mt_attendees_text = st.text_input("Attendees", key="mt_att", placeholder="e.g. Jane, John, Sarah")

            mt_summary   = st.text_area("Summary", key="mt_summary", height=100)
            mt_decisions = st.text_area("Decisions / outcomes", key="mt_decisions", height=80)
            if st.button("Save Meeting", type="primary", use_container_width=True):
                if not mt_title.strip():
                    st.warning("Title required.")
                else:
                    all_att = mt_attendees_text
                    save(dm().append_row, "Meetings", {
                        "Title": mt_title.strip(), "Date": str(mt_date),
                        "Attendees": all_att.strip(), "Type": mt_type,
                        "Summary": mt_summary.strip(), "Decisions": mt_decisions.strip(),
                        "Created": str(date.today()),
                    }, success_msg="Meeting saved!")

    with col_v:
        df = get_data("Meetings")
        if df.empty:
            st.info("No meetings logged yet.")
        else:
            sc1, sc2 = st.columns([2, 1])
            search  = sc1.text_input("🔍 Search", key="mt_search")
            all_types = ["All"] + sorted(df["Type"].dropna().unique().tolist()) if "Type" in df.columns else ["All"]
            f_type  = sc2.selectbox("Type", all_types, key="mt_type_filter")

            view = df.copy().reset_index(drop=False)
            if "Date" in view.columns: view = view.sort_values("Date", ascending=False)
            if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_type != "All" and "Type" in view.columns: view = view[view["Type"] == f_type]

            # Index table with delete
            edit_df = add_delete_col(view[[c for c in ["index","Date","Title","Type","Attendees"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
            }, use_container_width=True, hide_index=True, key="meetings_editor")
            if st.button("🗑 Delete selected", key="mt_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Meetings", int(idx))
                get_data.clear()
                st.rerun()

            st.markdown("---")
            for _, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Date','')}"):
                    if row.get("Attendees"): st.caption(f"👥 {row['Attendees']}")
                    if row.get("Summary"):
                        st.markdown("**Summary:**")
                        st.markdown(row["Summary"])
                    if row.get("Decisions"):
                        st.markdown("**Decisions:**")
                        st.success(row["Decisions"])


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scripts:
    st.markdown('<div class="section-header">Script Review</div>', unsafe_allow_html=True)
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Add a script**")
            sc_title  = st.text_input("Title", key="sc_title")
            sc_lang   = st.selectbox("Language", ["SQL","Python","Shell / Bash","JavaScript","Other"], key="sc_lang")
            sc_status = st.selectbox("Status", ["Under Review","Has Issues","Approved","Needs Rewrite"], key="sc_status")
            sc_script = st.text_area("Script", key="sc_script", height=180)
            sc_notes  = st.text_area("General notes", key="sc_notes", height=80)
            sc_issues = st.text_area("Issues", key="sc_issues", height=80)
            sc_qs     = st.text_area("Questions", key="sc_qs", height=80)
            if st.button("Save Script", type="primary", use_container_width=True):
                if not sc_title.strip():
                    st.warning("Title required.")
                else:
                    save(dm().append_row, "Scripts", {
                        "Title": sc_title.strip(), "Language": sc_lang,
                        "Script": sc_script.strip(), "Notes": sc_notes.strip(),
                        "Issues": sc_issues.strip(), "Questions": sc_qs.strip(),
                        "Status": sc_status, "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }, success_msg="Script saved!")

    with col_v:
        df = get_data("Scripts")
        if df.empty:
            st.info("No scripts yet.")
        else:
            sc1, sc2 = st.columns([2, 1])
            search   = sc1.text_input("🔍 Search", key="sc_search")
            all_st   = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
            f_status = sc2.selectbox("Status", all_st, key="sc_status_filter")

            view = df.copy().reset_index(drop=False).iloc[::-1]
            if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_status != "All" and "Status" in view.columns: view = view[view["Status"] == f_status]

            edit_df = add_delete_col(view[[c for c in ["index","Title","Language","Status"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
                "Status": st.column_config.SelectboxColumn("Status", options=["Under Review","Has Issues","Approved","Needs Rewrite"]),
            }, use_container_width=True, hide_index=True, key="scripts_editor")

            bc1, bc2 = st.columns(2)
            if bc1.button("💾 Save status", key="sc_save", use_container_width=True):
                for _, row in edited.iterrows():
                    orig_idx = int(row["index"])
                    if row.get("Status") != df.loc[orig_idx].get("Status"):
                        dm().update_cell("Scripts", orig_idx, "Status", row["Status"])
                get_data.clear()
                st.toast("Saved!")
                st.rerun()
            if bc2.button("🗑 Delete selected", key="sc_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Scripts", int(idx))
                get_data.clear()
                st.rerun()

            st.markdown("---")
            status_icon = {"Under Review":"🔍","Has Issues":"🚨","Approved":"✅","Needs Rewrite":"🔄"}
            for _, row in view.iterrows():
                icon = status_icon.get(row.get("Status",""), "📄")
                with st.expander(f"{icon} **{row.get('Title','')}**  ·  `{row.get('Language','')}`"):
                    if row.get("Notes"):
                        st.markdown("**Notes:**")
                        st.markdown(row["Notes"])
                    if row.get("Script"):
                        lang_map = {"SQL":"sql","Python":"python","Shell / Bash":"bash","JavaScript":"javascript"}
                        st.code(row["Script"], language=lang_map.get(row.get("Language",""), "text"))
                    if row.get("Issues"):
                        st.error(f"**Issues:** {row['Issues']}")
                    if row.get("Questions"):
                        st.warning(f"**Questions:** {row['Questions']}")


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown('<div class="section-header">Reference Library</div>', unsafe_allow_html=True)
    col_add, col_view = st.columns([1, 2], gap="large")

    with col_add:
        with st.container(border=True):
            st.markdown("**➕ Add entry**")
            r_title = st.text_input("Title", key="r_title")
            r_cat   = st.selectbox("Category", ["SQL / Query","Python","Shell / Bash","Process / Checklist","Table / Data","Template","Formula","Other"], key="r_cat")
            r_tags  = st.text_input("Tags (comma-separated)", key="r_tags")
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
                    }, success_msg="Saved!")

    with col_view:
        df = get_data("Reference")
        if df.empty:
            st.info("Nothing saved yet.")
        else:
            sc1, sc2 = st.columns([2, 1])
            search  = sc1.text_input("🔍 Search", key="r_search")
            all_cats = ["All"] + sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else ["All"]
            f_cat   = sc2.selectbox("Category", all_cats, key="r_cat_filter")
            view = df.copy().reset_index(drop=False).iloc[::-1]
            if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_cat != "All" and "Category" in view.columns: view = view[view["Category"] == f_cat]

            edit_df = add_delete_col(view[[c for c in ["index","Title","Category","Tags"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
            }, use_container_width=True, hide_index=True, key="ref_editor")
            if st.button("🗑 Delete selected", key="ref_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Reference", int(idx))
                get_data.clear()
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
# NOTES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_notes:
    st.markdown('<div class="section-header">Notes</div>', unsafe_allow_html=True)
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ New note**")
            n_title = st.text_input("Title", key="n_title")
            n_tags  = st.text_input("Tags (optional)", key="n_tags", placeholder="e.g. strategy, HR")
            n_link  = st.text_input("Link to person (optional)", key="n_link", placeholder="e.g. Jane Smith")
            n_body  = st.text_area("Note", key="n_body", height=140)
            if st.button("Save Note", type="primary", use_container_width=True):
                if not n_title.strip() or not n_body.strip():
                    st.warning("Title and note required.")
                else:
                    save(dm().append_row, "Notes", {
                        "Title": n_title.strip(), "Tags": n_tags.strip(),
                        "LinkedTo": n_link.strip(),
                        "Body": n_body.strip(),
                        "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }, success_msg="Saved!")

    with col_v:
        df = get_data("Notes")
        if df.empty:
            st.info("No notes yet.")
        else:
            search = st.text_input("🔍 Search", key="n_search")
            view = df.copy().reset_index(drop=False).iloc[::-1]
            if search: view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

            edit_df = add_delete_col(view[[c for c in ["index","Title","Tags","LinkedTo","Created"] if c in view.columns]])
            edited = st.data_editor(edit_df, column_config={
                "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
                "index":  st.column_config.Column("Row", disabled=True, width="small"),
            }, use_container_width=True, hide_index=True, key="notes_editor")
            if st.button("🗑 Delete selected", key="notes_del", use_container_width=True):
                to_del = edited[edited["Delete"] == True]["index"].tolist()
                for idx in sorted(to_del, reverse=True):
                    dm().delete_row("Notes", int(idx))
                get_data.clear()
                st.rerun()

            st.markdown("---")
            for _, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Created','')}"):
                    if row.get("Tags"):    st.caption(f"🏷 {row['Tags']}")
                    if row.get("LinkedTo"): st.caption(f"👤 {row['LinkedTo']}")
                    st.markdown(row.get("Body",""))
