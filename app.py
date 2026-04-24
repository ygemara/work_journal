import streamlit as st
import pandas as pd
from datetime import datetime, date
from data_manager import LocalManager, SheetsManager, GSPREAD_AVAILABLE

st.set_page_config(page_title="Manager Dashboard", page_icon="📋", layout="wide")

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
    .badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600; }
    .badge-high   { background:#fee2e2; color:#991b1b; }
    .badge-medium { background:#fef9c3; color:#854d0e; }
    .badge-low    { background:#dcfce7; color:#166534; }
    .badge-urgent { background:#fce7f3; color:#9d174d; }
    #MainMenu, footer { visibility:hidden; }
    .block-container { padding-top:1.5rem; }
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def safe_write(fn, *args, **kwargs):
    """Call a write function, show a visible error if it fails."""
    try:
        fn(*args, **kwargs)
        return True
    except Exception as e:
        st.error(f"❌ Write failed: {e}")
        return False


# ── auto-connect from secrets ─────────────────────────────────────────────────

if "dm" not in st.session_state:
    try:
        sid   = st.secrets.get("spreadsheet_id", "")
        creds = dict(st.secrets.get("gcp_service_account", {}))
        if not sid or sid == "PASTE_YOUR_SPREADSHEET_ID_HERE" or not creds:
            st.error("❌ Secrets not configured. Add spreadsheet_id and gcp_service_account to Streamlit secrets.")
            st.stop()
        sm = SheetsManager(creds, sid)
        sm.ensure_worksheets()
        st.session_state.dm   = sm
        st.session_state.mode = "sheets"
    except Exception as e:
        st.error(f"❌ Could not connect to Google Sheets: {e}")
        st.stop()
    st.session_state.direct_reports = st.session_state.dm.get_direct_reports()


def dm() -> SheetsManager:
    return st.session_state.dm


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📋 Manager Dashboard")
    st.success("☁️ Connected to Google Sheets")
    st.markdown("---")

    st.markdown("### 👥 Your Team")
    new_name = st.text_input("Add person", placeholder="Jane Smith", label_visibility="collapsed")
    if st.button("➕ Add", use_container_width=True) and new_name.strip():
        if safe_write(dm().add_direct_report, new_name.strip()):
            st.session_state.direct_reports = dm().get_direct_reports()
            st.rerun()

    reports = st.session_state.direct_reports
    if reports:
        for r in reports:
            st.markdown(f"• {r}")
        st.markdown("**Remove:**")
        remove = st.selectbox("Remove", ["—"] + reports, label_visibility="collapsed")
        if st.button("🗑 Remove", use_container_width=True) and remove != "—":
            if safe_write(dm().remove_direct_report, remove):
                st.session_state.direct_reports = dm().get_direct_reports()
                st.rerun()
    else:
        st.caption("No team members yet.")

    st.markdown("---")
    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state.direct_reports = dm().get_direct_reports()
        st.rerun()
    st.caption(f"Refreshed: {datetime.now().strftime('%H:%M')}")


# ── header + KPIs ─────────────────────────────────────────────────────────────

st.markdown("# 📋 Manager Dashboard")
col_title, col_status = st.columns([4, 1])
col_title.caption(date.today().strftime("%A, %B %d, %Y"))
col_status.success("☁️ Sheets connected")

try:
    issues_df  = dm().get_data("Issues")
    actions_df = dm().get_data("ActionItems")
    agenda_df  = dm().get_data("Agenda")
    emails_df  = dm().get_data("Emails")

    open_issues     = len(issues_df[issues_df["Status"] == "Open"])    if not issues_df.empty and "Status" in issues_df.columns else 0
    high_pri        = len(issues_df[(issues_df["Status"] == "Open") & (issues_df["Priority"] == "High")]) if not issues_df.empty and "Priority" in issues_df.columns else 0
    pending_actions = len(actions_df[actions_df["Status"] == "Pending"]) if not actions_df.empty and "Status" in actions_df.columns else 0
    urgent_emails   = len(emails_df[(emails_df["Status"] == "Pending") & (emails_df["Priority"] == "Urgent")]) if not emails_df.empty and "Status" in emails_df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Open Issues",    open_issues)
    c2.metric("⚡ High Priority",   high_pri)
    c3.metric("✅ Pending Actions", pending_actions)
    c4.metric("📧 Urgent Emails",   urgent_emails)
except Exception as e:
    st.warning(f"Could not load summary: {e}")

st.markdown("---")

tabs = st.tabs(["🔴 Issues", "💬 1:1 Agenda", "✅ Action Items", "📅 Calendar", "📧 Emails", "📚 Reference", "📝 Notes"])
tab_issues, tab_agenda, tab_actions, tab_calendar, tab_emails, tab_ref, tab_notes = tabs


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
                elif safe_write(dm().append_row, "Issues", {
                    "Title": i_title.strip(), "Description": i_desc.strip(),
                    "Priority": i_priority, "Owner": i_owner,
                    "Due": str(i_due) if i_due else "", "Status": "Open",
                    "Created": str(date.today()),
                }):
                    st.success("Logged!")
                    st.rerun()

    with col_list:
        df = dm().get_data("Issues")
        if df.empty:
            st.info("No issues yet.")
        else:
            fc1, fc2 = st.columns(2)
            f_status   = fc1.multiselect("Status",   ["Open","In Progress","Resolved"], default=["Open","In Progress"])
            f_priority = fc2.multiselect("Priority", ["High","Medium","Low"],           default=["High","Medium","Low"])
            view = df.copy()
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            porder = {"High":0,"Medium":1,"Low":2}
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map(porder).fillna(9)).sort_values("_s").drop(columns=["_s"])

            for idx, row in view.iterrows():
                bcls = f"badge-{row.get('Priority','medium').lower()}"
                with st.container(border=True):
                    h1, h2 = st.columns([3,1])
                    h1.markdown(f"**{row.get('Title','')}**")
                    h2.markdown(f'<span class="badge {bcls}">{row.get("Priority","")}</span>', unsafe_allow_html=True)
                    meta = []
                    if row.get("Owner"): meta.append(f"👤 {row['Owner']}")
                    if row.get("Due"):   meta.append(f"📅 {row['Due']}")
                    if meta: st.caption("  ·  ".join(meta))
                    if row.get("Description"):
                        st.markdown(f"<small style='color:#64748b'>{row['Description']}</small>", unsafe_allow_html=True)
                    s1, s2, s3 = st.columns([2,1,1])
                    choices = ["Open","In Progress","Resolved"]
                    cur = row.get("Status","Open")
                    ns = s1.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"is_{idx}", label_visibility="collapsed")
                    if s2.button("Update", key=f"iu_{idx}", use_container_width=True):
                        if safe_write(dm().update_cell, "Issues", idx, "Status", ns):
                            st.rerun()
                    if s3.button("🗑", key=f"id_{idx}", use_container_width=True):
                        if safe_write(dm().delete_row, "Issues", idx):
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
                a_added_by = st.radio("Added by", ["Me", selected], horizontal=True, key="a_by")
                if st.button("Add to Agenda", type="primary", use_container_width=True):
                    if not a_topic.strip():
                        st.warning("Topic required.")
                    elif safe_write(dm().append_row, "Agenda", {
                        "Person": selected, "Topic": a_topic.strip(),
                        "Category": a_type, "AddedBy": a_added_by,
                        "Discussed": "No", "Created": str(date.today()),
                    }):
                        st.success("Added!")
                        st.rerun()

        with col_view:
            df = dm().get_data("Agenda")
            person_df = df[df["Person"] == selected] if not df.empty and "Person" in df.columns else pd.DataFrame()
            show_done = st.toggle("Show discussed", False, key="ag_show_done")

            if person_df.empty:
                st.info(f"No topics for {selected} yet.")
            else:
                pending = person_df[person_df["Discussed"] == "No"]  if "Discussed" in person_df.columns else person_df
                done    = person_df[person_df["Discussed"] == "Yes"] if "Discussed" in person_df.columns else pd.DataFrame()
                st.markdown(f"**{len(pending)} to discuss · {len(done)} done**")

                for idx, row in pending.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4,1,1])
                        c1.markdown(f"**{row.get('Topic','')}**")
                        c1.caption(f"📁 {row.get('Category','')}  ·  {row.get('AddedBy','')}  ·  {row.get('Created','')}")
                        if c2.button("✓", key=f"ag_{idx}", use_container_width=True):
                            if safe_write(dm().update_cell, "Agenda", idx, "Discussed", "Yes"):
                                st.rerun()
                        if c3.button("🗑", key=f"agd_{idx}", use_container_width=True):
                            if safe_write(dm().delete_row, "Agenda", idx):
                                st.rerun()

                if show_done and not done.empty:
                    st.markdown("---")
                    for idx, row in done.iterrows():
                        c1, c2 = st.columns([5,1])
                        c1.markdown(f"~~{row.get('Topic','')}~~ · <small style='color:#94a3b8'>{row.get('Created','')}</small>", unsafe_allow_html=True)
                        if c2.button("🗑", key=f"agdd_{idx}", use_container_width=True):
                            if safe_write(dm().delete_row, "Agenda", idx):
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
            ac_owner = st.selectbox("Owner", ["Me"] + st.session_state.direct_reports, key="ac_owner")
            ac_due   = st.date_input("Due date", key="ac_due")
            ac_src   = st.selectbox("From", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
            if st.button("Add Action", type="primary", use_container_width=True):
                if not ac_task.strip():
                    st.warning("Task required.")
                elif safe_write(dm().append_row, "ActionItems", {
                    "Task": ac_task.strip(), "Owner": ac_owner,
                    "Due": str(ac_due), "Source": ac_src,
                    "Status": "Pending", "Created": str(date.today()),
                }):
                    st.success("Added!")
                    st.rerun()

    with col_v:
        df = dm().get_data("ActionItems")
        if df.empty:
            st.info("No action items yet.")
        else:
            f_owner = st.selectbox("Filter by", ["Everyone","Me"] + st.session_state.direct_reports, key="ac_filt")
            open_df = df[df["Status"] != "Done"].copy() if "Status" in df.columns else df.copy()
            if f_owner != "Everyone" and "Owner" in open_df.columns:
                open_df = open_df[open_df["Owner"] == f_owner]

            today_str = str(date.today())
            if open_df.empty:
                st.success("🎉 All clear!")
            else:
                for idx, row in open_df.iterrows():
                    overdue = row.get("Due","") and row.get("Due","") < today_str and row.get("Status") == "Pending"
                    with st.container(border=True):
                        r1, r2, r3 = st.columns([4,1,1])
                        r1.markdown(f"{'🚨 ' if overdue else ''}**{row.get('Task','')}**")
                        r1.caption(f"👤 {row.get('Owner','')}  ·  📅 {row.get('Due','')}  ·  {row.get('Source','')}" + (" **OVERDUE**" if overdue else ""))
                        choices = ["Pending","In Progress","Done"]
                        cur = row.get("Status","Pending")
                        ns = r2.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"acs_{idx}", label_visibility="collapsed")
                        if r2.button("💾", key=f"acsv_{idx}", use_container_width=True):
                            if safe_write(dm().update_cell, "ActionItems", idx, "Status", ns):
                                st.rerun()
                        if r3.button("🗑", key=f"acd_{idx}", use_container_width=True):
                            if safe_write(dm().delete_row, "ActionItems", idx):
                                st.rerun()

            done_df = df[df["Status"] == "Done"] if "Status" in df.columns else pd.DataFrame()
            if not done_df.empty:
                with st.expander(f"✅ {len(done_df)} completed"):
                    for idx, row in done_df.iterrows():
                        c1, c2 = st.columns([5,1])
                        c1.markdown(f"~~{row.get('Task','')}~~ · {row.get('Owner','')} · {row.get('Due','')}")
                        if c2.button("🗑", key=f"acdd_{idx}", use_container_width=True):
                            if safe_write(dm().delete_row, "ActionItems", idx):
                                st.rerun()


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
                elif safe_write(dm().append_row, "Calendar", {
                    "Title": ev_title.strip(), "Date": str(ev_date),
                    "Time": str(ev_time)[:5] if ev_time else "",
                    "Type": ev_type, "With": ", ".join(ev_with),
                    "Notes": ev_notes.strip(),
                }):
                    st.success("Added!")
                    st.rerun()

    with col_v:
        df = dm().get_data("Calendar")
        today_str = str(date.today())
        icons = {"1:1":"👤","Team Meeting":"👥","Deadline":"⏰","Performance Review":"📊","Planning":"🗓","Other":"📌"}
        if df.empty:
            st.info("No events yet.")
        else:
            upcoming = df[df["Date"] >= today_str].sort_values("Date") if "Date" in df.columns else df
            past     = df[df["Date"] < today_str].sort_values("Date", ascending=False) if "Date" in df.columns else pd.DataFrame()

            st.markdown(f"**{len(upcoming)} upcoming**")
            for idx, row in upcoming.iterrows():
                icon = icons.get(row.get("Type",""), "📌")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4,1,1])
                    c1.markdown(f"{icon} **{row.get('Title','')}**")
                    if row.get("Date","") == today_str: c2.markdown("🟡 Today")
                    meta = [f"📅 {row.get('Date','')}"]
                    if row.get("Time"): meta.append(f"🕐 {row['Time']}")
                    if row.get("With"): meta.append(f"👥 {row['With']}")
                    c1.caption("  ·  ".join(meta))
                    if row.get("Notes"): c1.caption(row["Notes"])
                    if c3.button("🗑", key=f"evd_{idx}", use_container_width=True):
                        if safe_write(dm().delete_row, "Calendar", idx):
                            st.rerun()

            if not past.empty:
                with st.expander(f"🗓 {len(past)} past events"):
                    for idx, row in past.iterrows():
                        c1, c2 = st.columns([5,1])
                        c1.caption(f"{row.get('Date','')} — {row.get('Title','')}")
                        if c2.button("🗑", key=f"evpd_{idx}", use_container_width=True):
                            if safe_write(dm().delete_row, "Calendar", idx):
                                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# EMAILS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_emails:
    st.markdown('<div class="section-header">Important Emails</div>', unsafe_allow_html=True)
    st.caption("Flag emails that need follow-up or action. Paste the key details here so nothing slips through.")

    col_f, col_v = st.columns([1, 2], gap="large")

    with col_f:
        with st.container(border=True):
            st.markdown("**📧 Log an email**")
            em_subject  = st.text_input("Subject", key="em_subject")
            em_from     = st.text_input("From", key="em_from", placeholder="sender@company.com")
            em_received = st.date_input("Received", key="em_received")
            em_priority = st.selectbox("Priority", ["Urgent","High","Medium","Low"], key="em_priority")
            em_action   = st.text_area("Action needed", key="em_action", height=80,
                                       placeholder="What do you need to do about this?")
            em_notes    = st.text_area("Notes / summary", key="em_notes", height=80,
                                       placeholder="Key points from the email...")
            if st.button("Save Email", type="primary", use_container_width=True):
                if not em_subject.strip():
                    st.warning("Subject required.")
                elif safe_write(dm().append_row, "Emails", {
                    "Subject": em_subject.strip(), "From": em_from.strip(),
                    "Received": str(em_received), "Priority": em_priority,
                    "Action": em_action.strip(), "Status": "Pending",
                    "Notes": em_notes.strip(), "Created": str(date.today()),
                }):
                    st.success("Saved!")
                    st.rerun()

    with col_v:
        df = dm().get_data("Emails")
        if df.empty:
            st.info("No emails logged yet.")
        else:
            fc1, fc2 = st.columns(2)
            f_status   = fc1.multiselect("Status",   ["Pending","In Progress","Done"], default=["Pending","In Progress"], key="em_fs")
            f_priority = fc2.multiselect("Priority", ["Urgent","High","Medium","Low"], default=["Urgent","High","Medium","Low"], key="em_fp")
            view = df.copy()
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            porder = {"Urgent":0,"High":1,"Medium":2,"Low":3}
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map(porder).fillna(9)).sort_values("_s").drop(columns=["_s"])

            for idx, row in view.iterrows():
                pri = row.get("Priority","")
                bcls = "badge-urgent" if pri == "Urgent" else f"badge-{pri.lower()}"
                with st.container(border=True):
                    h1, h2 = st.columns([4,1])
                    h1.markdown(f"**{row.get('Subject','')}**")
                    h2.markdown(f'<span class="badge {bcls}">{pri}</span>', unsafe_allow_html=True)
                    h1.caption(f"From: {row.get('From','')}  ·  📅 {row.get('Received','')}")

                    if row.get("Action"):
                        st.markdown(f"**Action:** {row['Action']}")
                    if row.get("Notes"):
                        st.markdown(f"<small style='color:#64748b'>{row['Notes']}</small>", unsafe_allow_html=True)

                    s1, s2, s3 = st.columns([2,1,1])
                    choices = ["Pending","In Progress","Done"]
                    cur = row.get("Status","Pending")
                    ns = s1.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"ems_{idx}", label_visibility="collapsed")
                    if s2.button("💾", key=f"emv_{idx}", use_container_width=True):
                        if safe_write(dm().update_cell, "Emails", idx, "Status", ns):
                            st.rerun()
                    if s3.button("🗑", key=f"emd_{idx}", use_container_width=True):
                        if safe_write(dm().delete_row, "Emails", idx):
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown('<div class="section-header">Reference Library</div>', unsafe_allow_html=True)
    st.caption("Store SQL queries, scripts, checklists, templates — with your own explanation of each.")

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
                elif safe_write(dm().append_row, "Reference", {
                    "Title": r_title.strip(), "Category": r_cat,
                    "Content": r_body.strip(), "Explanation": r_notes.strip(),
                    "Tags": r_tags.strip(),
                    "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }):
                    st.success("Saved!")
                    st.rerun()

    with col_view:
        df = dm().get_data("Reference")
        if df.empty:
            st.info("Nothing saved yet.")
        else:
            sc1, sc2 = st.columns([2,1])
            search = sc1.text_input("🔍 Search", key="r_search")
            all_cats = ["All"] + sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else ["All"]
            f_cat = sc2.selectbox("Category", all_cats, key="r_cat_filter")
            view = df.copy().iloc[::-1]
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]
            if f_cat != "All" and "Category" in view.columns:
                view = view[view["Category"] == f_cat]

            for idx, row in view.iterrows():
                with st.expander(f"**{row.get('Title','')}**  ·  `{row.get('Category','')}`"):
                    tags = row.get("Tags","")
                    if tags:
                        st.markdown(" ".join([f"`{t.strip()}`" for t in tags.split(",") if t.strip()]))
                    content = row.get("Content","")
                    if content:
                        cat  = row.get("Category","")
                        lang = "sql" if "SQL" in cat else "python" if "Python" in cat else "bash" if "Shell" in cat else "text"
                        st.code(content, language=lang)
                    expl = row.get("Explanation","")
                    if expl:
                        st.info(expl)
                    if st.button("🗑 Delete", key=f"rdel_{idx}"):
                        if safe_write(dm().delete_row, "Reference", idx):
                            st.rerun()


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
                elif safe_write(dm().append_row, "Notes", {
                    "Title": n_title.strip(), "Tags": ", ".join(n_tags),
                    "LinkedTo": n_link if n_link != "—" else "",
                    "Body": n_body.strip(),
                    "Created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }):
                    st.success("Saved!")
                    st.rerun()

    with col_v:
        df = dm().get_data("Notes")
        if df.empty:
            st.info("No notes yet.")
        else:
            search = st.text_input("🔍 Search", key="n_search")
            view = df.copy().iloc[::-1]
            if search:
                view = view[view.apply(lambda r: search.lower() in str(r).lower(), axis=1)]

            for idx, row in view.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5,1])
                    c1.markdown(f"**{row.get('Title','')}**")
                    meta = [row.get("Created","")]
                    if row.get("Tags"):    meta.append(f"🏷 {row['Tags']}")
                    if row.get("LinkedTo"): meta.append(f"👤 {row['LinkedTo']}")
                    c1.caption("  ·  ".join(meta))
                    c1.markdown(row.get("Body",""))
                    if c2.button("🗑", key=f"nd_{idx}", use_container_width=True):
                        if safe_write(dm().delete_row, "Notes", idx):
                            st.rerun()
