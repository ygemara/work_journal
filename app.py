import streamlit as st
import pandas as pd
from datetime import datetime, date
from data_manager import SheetsManager

st.set_page_config(page_title="Manager Dashboard", page_icon="📋", layout="wide")

# ── password protection ───────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("## 🔒 Manager Dashboard")
    st.markdown("Please log in to continue.")
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

st.markdown("""
<style>
    [data-testid="metric-container"] {
        background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.25rem;
    }
    .stTabs [data-baseweb="tab"] { border-radius:8px 8px 0 0; padding:8px 20px; font-weight:500; }
    .section-header {
        font-size:1.1rem; font-weight:700;
        border-left:4px solid #6366f1; padding-left:10px; margin:0.5rem 0 1rem;
    }
    #MainMenu, footer { visibility:hidden; }
    .block-container { padding-top:1.5rem; }
</style>
""", unsafe_allow_html=True)


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
    """Call a write fn. On success clear cache and rerun. On error show message."""
    try:
        fn(*args, **kwargs)
        get_data.clear()
        if success_msg:
            st.toast(success_msg)
        st.rerun()
    except Exception as e:
        st.error(f"❌ {e}")


def v():
    return 0


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
        bust()
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
            i_owner    = st.selectbox("Owner", ["(Unassigned)"] + st.session_state.direct_reports, key="i_owner")
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
            f_status   = fc1.multiselect("Status",   ["Open", "In Progress", "Resolved"], default=["Open", "In Progress"])
            f_priority = fc2.multiselect("Priority", ["High", "Medium", "Low"],           default=["High", "Medium", "Low"])
            view = df.copy()
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map({"High":0,"Medium":1,"Low":2}).fillna(9)).sort_values("_s").drop(columns=["_s"])

            # Summary table
            display_cols = [c for c in ["Title","Priority","Owner","Due","Status"] if c in view.columns]
            st.dataframe(view[display_cols], use_container_width=True, hide_index=True)

            st.markdown("**Update status:**")
            for idx, row in view.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(f"**{row.get('Title','')}**")
                    c1.caption(f"👤 {row.get('Owner','')}  ·  📅 {row.get('Due','')}  ·  {row.get('Description','')[:60]}")
                    choices = ["Open", "In Progress", "Resolved"]
                    cur = row.get("Status", "Open")
                    ns = c2.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"is_{idx}", label_visibility="collapsed")
                    if c3.button("💾", key=f"iu_{idx}", use_container_width=True):
                        save(dm().update_cell, "Issues", idx, "Status", ns, success_msg="Updated!")
                    if c4.button("🗑", key=f"id_{idx}", use_container_width=True):
                        save(dm().delete_row, "Issues", idx, success_msg="Deleted!")


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
                a_added_by = st.radio("Added by", ["Me", selected], horizontal=True, key="a_by")
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
            person_df = df[df["Person"] == selected] if not df.empty and "Person" in df.columns else pd.DataFrame()
            show_done = st.toggle("Show discussed", False, key="ag_show_done")

            if person_df.empty:
                st.info(f"No topics for {selected} yet.")
            else:
                pending = person_df[person_df["Discussed"] == "No"]  if "Discussed" in person_df.columns else person_df
                done    = person_df[person_df["Discussed"] == "Yes"] if "Discussed" in person_df.columns else pd.DataFrame()
                st.markdown(f"**{len(pending)} to discuss · {len(done)} done**")

                # Table view of pending
                if not pending.empty:
                    dcols = [c for c in ["Topic","Category","AddedBy","Created"] if c in pending.columns]
                    st.dataframe(pending[dcols], use_container_width=True, hide_index=True)

                for idx, row in pending.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4, 1, 1])
                        c1.markdown(f"**{row.get('Topic','')}**")
                        c1.caption(f"📁 {row.get('Category','')}  ·  {row.get('AddedBy','')}  ·  {row.get('Created','')}")
                        if c2.button("✓ Done", key=f"ag_{idx}", use_container_width=True):
                            save(dm().update_cell, "Agenda", idx, "Discussed", "Yes", success_msg="Marked done!")
                        if c3.button("🗑", key=f"agd_{idx}", use_container_width=True):
                            save(dm().delete_row, "Agenda", idx, success_msg="Deleted!")

                if show_done and not done.empty:
                    st.markdown("---")
                    st.markdown("**Previously discussed:**")
                    dcols2 = [c for c in ["Topic","Category","Created"] if c in done.columns]
                    st.dataframe(done[dcols2], use_container_width=True, hide_index=True)


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
            ac_owner = st.selectbox("Owner", ["Me"] + st.session_state.direct_reports, key="ac_owner")
            ac_due   = st.date_input("Due date", key="ac_due")
            ac_src   = st.selectbox("From", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
            ac_notes = st.text_area("Notes / context", key="ac_notes", height=80,
                                    placeholder="What exactly needs to be done? Any context?")
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
            f_owner = st.selectbox("Filter by", ["Everyone", "Me"] + st.session_state.direct_reports, key="ac_filt")
            today_str = str(date.today())
            view = df.copy()
            if "Status" in view.columns:
                view = view[view["Status"] != "Done"]
            if f_owner != "Everyone" and "Owner" in view.columns:
                view = view[view["Owner"] == f_owner]

            if view.empty:
                st.success("🎉 All clear!")
            else:
                # Mark overdue
                if "Due" in view.columns and "Status" in view.columns:
                    view = view.copy()
                    view["Overdue"] = view.apply(lambda r: "🚨" if r.get("Due","") < today_str and r.get("Status") == "Pending" else "", axis=1)

                dcols = [c for c in ["Overdue","Task","Owner","Due","Status","Source"] if c in view.columns]
                st.dataframe(view[dcols], use_container_width=True, hide_index=True)

                for idx, row in view.iterrows():
                    overdue = row.get("Due","") < today_str and row.get("Status") == "Pending"
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                        c1.markdown(f"{'🚨 ' if overdue else ''}**{row.get('Task','')}**")
                        c1.caption(f"👤 {row.get('Owner','')}  ·  📅 {row.get('Due','')}")
                        if row.get("Notes"): c1.markdown(f"<small style='color:#64748b'>{row['Notes']}</small>", unsafe_allow_html=True)
                        choices = ["Pending","In Progress","Done"]
                        cur = row.get("Status","Pending")
                        ns = c2.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"acs_{idx}", label_visibility="collapsed")
                        if c3.button("💾", key=f"acsv_{idx}", use_container_width=True):
                            save(dm().update_cell, "ActionItems", idx, "Status", ns, success_msg="Updated!")
                        if c4.button("🗑", key=f"acd_{idx}", use_container_width=True):
                            save(dm().delete_row, "ActionItems", idx, success_msg="Deleted!")

            done_df = df[df["Status"] == "Done"] if "Status" in df.columns else pd.DataFrame()
            if not done_df.empty:
                with st.expander(f"✅ {len(done_df)} completed"):
                    dcols3 = [c for c in ["Task","Owner","Due"] if c in done_df.columns]
                    st.dataframe(done_df[dcols3], use_container_width=True, hide_index=True)
                    for idx, row in done_df.iterrows():
                        if st.button(f"🗑 {row.get('Task','')}", key=f"acdd_{idx}"):
                            save(dm().delete_row, "ActionItems", idx, success_msg="Deleted!")


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
            ev_with  = st.multiselect("With", st.session_state.direct_reports, key="ev_with")
            ev_notes = st.text_area("Notes", key="ev_notes", height=60)
            if st.button("Add Event", type="primary", use_container_width=True):
                if not ev_title.strip():
                    st.warning("Event needs a name.")
                else:
                    save(dm().append_row, "Calendar", {
                        "Title": ev_title.strip(), "Date": str(ev_date),
                        "Time": str(ev_time)[:5] if ev_time else "",
                        "Type": ev_type, "With": ", ".join(ev_with),
                        "Notes": ev_notes.strip(),
                    }, success_msg="Event added!")

    with col_v:
        df = get_data("Calendar")
        today_str = str(date.today())
        if df.empty:
            st.info("No events yet.")
        else:
            if "Date" in df.columns:
                upcoming = df[df["Date"] >= today_str].sort_values("Date")
                past     = df[df["Date"] < today_str].sort_values("Date", ascending=False)
            else:
                upcoming, past = df, pd.DataFrame()

            st.markdown(f"**{len(upcoming)} upcoming**")
            if not upcoming.empty:
                dcols = [c for c in ["Date","Time","Title","Type","With"] if c in upcoming.columns]
                st.dataframe(upcoming[dcols], use_container_width=True, hide_index=True)

            for idx, row in upcoming.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1, 1])
                    c1.markdown(f"**{row.get('Title','')}**")
                    meta = [f"📅 {row.get('Date','')}"]
                    if row.get("Time"): meta.append(f"🕐 {row['Time']}")
                    if row.get("With"): meta.append(f"👥 {row['With']}")
                    c1.caption("  ·  ".join(meta))
                    if row.get("Date","") == today_str: c2.markdown("🟡 Today")
                    if c3.button("🗑", key=f"evd_{idx}", use_container_width=True):
                        save(dm().delete_row, "Calendar", idx, success_msg="Deleted!")

            if not past.empty:
                with st.expander(f"🗓 {len(past)} past events"):
                    dcols2 = [c for c in ["Date","Title","Type"] if c in past.columns]
                    st.dataframe(past[dcols2], use_container_width=True, hide_index=True)


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
            em_from     = st.text_input("From", key="em_from", placeholder="sender@company.com")
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
            view = df.copy()
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map({"Urgent":0,"High":1,"Medium":2,"Low":3}).fillna(9)).sort_values("_s").drop(columns=["_s"])

            # Summary table
            dcols = [c for c in ["Subject","From","Received","Priority","Status"] if c in view.columns]
            st.dataframe(view[dcols], use_container_width=True, hide_index=True)

            for idx, row in view.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(f"**{row.get('Subject','')}**")
                    c1.caption(f"From: {row.get('From','')}  ·  {row.get('Received','')}  ·  {row.get('Priority','')}")
                    if row.get("Action"): c1.markdown(f"**Action:** {row['Action']}")
                    choices = ["Pending","In Progress","Done"]
                    cur = row.get("Status","Pending")
                    ns = c2.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"ems_{idx}", label_visibility="collapsed")
                    if c3.button("💾", key=f"emv_{idx}", use_container_width=True):
                        save(dm().update_cell, "Emails", idx, "Status", ns, success_msg="Updated!")
                    if c4.button("🗑", key=f"emd_{idx}", use_container_width=True):
                        save(dm().delete_row, "Emails", idx, success_msg="Deleted!")


# ═══════════════════════════════════════════════════════════════════════════════
# MEETINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_meetings:
    st.markdown('<div class="section-header">Meeting Summaries</div>', unsafe_allow_html=True)
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Log a meeting**")
            mt_title     = st.text_input("Meeting title", key="mt_title", placeholder="e.g. Weekly team sync")
            mt_date      = st.date_input("Date", key="mt_date")
            mt_type      = st.selectbox("Type", ["1:1","Team Meeting","Stakeholder","Interview","Planning","Retrospective","Other"], key="mt_type")
            mt_attendees = st.multiselect("Attendees", st.session_state.direct_reports, key="mt_att")
            mt_other_att = st.text_input("Other attendees (comma-separated)", key="mt_other_att", placeholder="e.g. John Smith, Sarah Lee")
            mt_summary   = st.text_area("Summary", key="mt_summary", height=100,
                                        placeholder="What was discussed? Key points?")
            mt_decisions = st.text_area("Decisions / outcomes", key="mt_decisions", height=80,
                                        placeholder="What was decided? What will happen next?")
            if st.button("Save Meeting", type="primary", use_container_width=True):
                if not mt_title.strip():
                    st.warning("Title required.")
                else:
                    all_att = mt_attendees + [a.strip() for a in mt_other_att.split(",") if a.strip()]
                    save(dm().append_row, "Meetings", {
                        "Title": mt_title.strip(),
                        "Date": str(mt_date),
                        "Attendees": ", ".join(all_att),
                        "Type": mt_type,
                        "Summary": mt_summary.strip(),
                        "Decisions": mt_decisions.strip(),
                        "Created": str(date.today()),
                    }, success_msg="Meeting saved!")

    with col_v:
        df = get_data("Meetings")
        if df.empty:
            st.info("No meetings logged yet.")
        else:
            # Search + filter
            sc1, sc2 = st.columns([2, 1])
            search  = sc1.text_input("🔍 Search", key="mt_search")
            all_types = ["All"] + sorted(df["Type"].dropna().unique().tolist()) if "Type" in df.columns else ["All"]
            f_type  = sc2.selectbox("Type", all_types, key="mt_type_filter")

            view = df.copy()
            if "Date" in view.columns:
                view = view.sort_values("Date", ascending=False)
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_type != "All" and "Type" in view.columns:
                view = view[view["Type"] == f_type]

            # Summary table
            dcols = [c for c in ["Date","Title","Type","Attendees"] if c in view.columns]
            st.dataframe(view[dcols], use_container_width=True, hide_index=True)

            for idx, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Date','')}  ·  {row.get('Type','')}"):
                    if row.get("Attendees"):
                        st.caption(f"👥 {row['Attendees']}")
                    if row.get("Summary"):
                        st.markdown("**Summary:**")
                        st.markdown(row["Summary"])
                    if row.get("Decisions"):
                        st.markdown("**Decisions / outcomes:**")
                        st.success(row["Decisions"])
                    if st.button("🗑 Delete", key=f"mtd_{idx}"):
                        save(dm().delete_row, "Meetings", idx, success_msg="Deleted!")


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scripts:
    st.markdown('<div class="section-header">Script Review</div>', unsafe_allow_html=True)
    st.caption("Paste scripts here and annotate them with notes, issues, and questions for review.")
    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**➕ Add a script**")
            sc_title  = st.text_input("Title", key="sc_title", placeholder="e.g. User onboarding flow")
            sc_lang   = st.selectbox("Language", ["SQL","Python","Shell / Bash","JavaScript","Other"], key="sc_lang")
            sc_status = st.selectbox("Status", ["Under Review","Has Issues","Approved","Needs Rewrite"], key="sc_status")
            sc_script = st.text_area("Script", key="sc_script", height=180,
                                     placeholder="Paste the script here...")
            sc_notes  = st.text_area("General notes", key="sc_notes", height=80,
                                     placeholder="Overview, context, what this script does...")
            sc_issues = st.text_area("Issues", key="sc_issues", height=80,
                                     placeholder="What's wrong or unclear?")
            sc_qs     = st.text_area("Questions", key="sc_qs", height=80,
                                     placeholder="Things you need to find out or clarify...")
            if st.button("Save Script", type="primary", use_container_width=True):
                if not sc_title.strip():
                    st.warning("Title required.")
                else:
                    save(dm().append_row, "Scripts", {
                        "Title":     sc_title.strip(),
                        "Language":  sc_lang,
                        "Script":    sc_script.strip(),
                        "Notes":     sc_notes.strip(),
                        "Issues":    sc_issues.strip(),
                        "Questions": sc_qs.strip(),
                        "Status":    sc_status,
                        "Created":   datetime.now().strftime("%Y-%m-%d %H:%M"),
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

            view = df.copy().iloc[::-1]
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_status != "All" and "Status" in view.columns:
                view = view[view["Status"] == f_status]

            dcols = [c for c in ["Title","Language","Status","Created"] if c in view.columns]
            st.dataframe(view[dcols], use_container_width=True, hide_index=True)

            status_icon = {"Under Review": "🔍", "Has Issues": "🚨", "Approved": "✅", "Needs Rewrite": "🔄"}

            for idx, row in view.iterrows():
                icon = status_icon.get(row.get("Status",""), "📄")
                with st.expander(f"{icon} **{row.get('Title','')}**  ·  `{row.get('Language','')}`  ·  {row.get('Status','')}"):

                    if row.get("Notes"):
                        st.markdown("**Overview / Notes:**")
                        st.markdown(row["Notes"])

                    if row.get("Script"):
                        lang_map = {"SQL":"sql","Python":"python","Shell / Bash":"bash","JavaScript":"javascript"}
                        lang = lang_map.get(row.get("Language",""), "text")
                        st.markdown("**Script:**")
                        st.code(row["Script"], language=lang)

                    if row.get("Issues"):
                        st.markdown("**⚠️ Issues:**")
                        st.error(row["Issues"])

                    if row.get("Questions"):
                        st.markdown("**❓ Questions:**")
                        st.warning(row["Questions"])

                    # Inline edit status
                    ec1, ec2, ec3 = st.columns([2, 1, 1])
                    choices = ["Under Review","Has Issues","Approved","Needs Rewrite"]
                    cur = row.get("Status","Under Review")
                    ns = ec1.selectbox("Update status", choices,
                                       index=choices.index(cur) if cur in choices else 0,
                                       key=f"sc_st_{idx}")
                    if ec2.button("💾 Save", key=f"sc_sv_{idx}", use_container_width=True):
                        save(dm().update_cell, "Scripts", idx, "Status", ns, success_msg="Updated!")
                    if ec3.button("🗑 Delete", key=f"sc_dl_{idx}", use_container_width=True):
                        save(dm().delete_row, "Scripts", idx, success_msg="Deleted!")


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
                        "Tags": r_tags.strip(),
                        "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
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
            view = df.copy().iloc[::-1]
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_cat != "All" and "Category" in view.columns:
                view = view[view["Category"] == f_cat]

            # Index table
            dcols = [c for c in ["Title","Category","Tags","Created"] if c in view.columns]
            st.dataframe(view[dcols], use_container_width=True, hide_index=True)

            for idx, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  `{row.get('Category','')}`"):
                    content = row.get("Content","")
                    if content:
                        cat  = row.get("Category","")
                        lang = "sql" if "SQL" in cat else "python" if "Python" in cat else "bash" if "Shell" in cat else "text"
                        st.code(content, language=lang)
                    if row.get("Explanation"):
                        st.info(row["Explanation"])
                    if st.button("🗑 Delete", key=f"rdel_{idx}"):
                        save(dm().delete_row, "Reference", idx, success_msg="Deleted!")


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
            n_tags  = st.multiselect("Tags", ["Strategy","HR","Technical","Process","Personal","Meeting","Other"], key="n_tags")
            n_link  = st.selectbox("Link to person (optional)", ["—"] + st.session_state.direct_reports, key="n_link")
            n_body  = st.text_area("Note", key="n_body", height=140)
            if st.button("Save Note", type="primary", use_container_width=True):
                if not n_title.strip() or not n_body.strip():
                    st.warning("Title and note required.")
                else:
                    save(dm().append_row, "Notes", {
                        "Title": n_title.strip(), "Tags": ", ".join(n_tags),
                        "LinkedTo": n_link if n_link != "—" else "",
                        "Body": n_body.strip(),
                        "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }, success_msg="Saved!")

    with col_v:
        df = get_data("Notes")
        if df.empty:
            st.info("No notes yet.")
        else:
            search = st.text_input("🔍 Search", key="n_search")
            view = df.copy().iloc[::-1]
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

            # Index table
            dcols = [c for c in ["Title","Tags","LinkedTo","Created"] if c in view.columns]
            st.dataframe(view[dcols], use_container_width=True, hide_index=True)

            for idx, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  {row.get('Created','')}"):
                    if row.get("Tags"):    st.caption(f"🏷 {row['Tags']}")
                    if row.get("LinkedTo"): st.caption(f"👤 {row['LinkedTo']}")
                    st.markdown(row.get("Body",""))
                    if st.button("🗑 Delete", key=f"nd_{idx}"):
                        save(dm().delete_row, "Notes", idx, success_msg="Deleted!")
