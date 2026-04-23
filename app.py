import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
from data_manager import LocalManager, SheetsManager, GSPREAD_AVAILABLE

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Manager Dashboard",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #1e293b; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: #94a3b8 !important; font-size:0.8rem !important; }
    [data-testid="metric-container"] {
        background: #f8fafc; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 1rem 1.25rem;
    }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 8px 20px; font-weight: 500; }
    .section-header {
        font-size: 1.1rem; font-weight: 700; color: #1e293b;
        border-left: 4px solid #6366f1; padding-left: 10px; margin: 0.5rem 0 1rem;
    }
    .badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600; }
    .badge-high   { background:#fee2e2; color:#b91c1c; }
    .badge-medium { background:#fef3c7; color:#b45309; }
    .badge-low    { background:#dcfce7; color:#15803d; }
    .mode-pill {
        display:inline-block; padding:3px 12px; border-radius:999px;
        font-size:0.75rem; font-weight:600; margin-bottom:0.5rem;
    }
    .mode-local  { background:#dbeafe; color:#1d4ed8; }
    .mode-sheets { background:#dcfce7; color:#15803d; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Auto-connect from secrets (Streamlit Cloud or local secrets.toml) ─────────
def try_connect_from_secrets() -> SheetsManager | None:
    """Returns a connected SheetsManager if secrets are configured, else None."""
    try:
        sid = st.secrets.get("spreadsheet_id", "")
        creds = dict(st.secrets.get("gcp_service_account", {}))
        if not sid or not creds or sid == "PASTE_YOUR_SPREADSHEET_ID_HERE":
            return None
        sm = SheetsManager(creds, sid)
        sm.ensure_worksheets()
        return sm
    except Exception:
        return None


# ── Session state ─────────────────────────────────────────────────────────────
if "dm" not in st.session_state:
    auto = try_connect_from_secrets()
    if auto:
        st.session_state.dm   = auto
        st.session_state.mode = "sheets"
    else:
        st.session_state.dm   = LocalManager()
        st.session_state.mode = "local"
    st.session_state.direct_reports = st.session_state.dm.get_direct_reports()


def dm():
    return st.session_state.dm


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Manager Dashboard")

    mode = st.session_state.get("mode", "local")
    if mode == "local":
        st.markdown('<span class="mode-pill mode-local">💾 Local mode</span>', unsafe_allow_html=True)
        st.caption("Data saved in **data.json** next to the app.")
    else:
        st.markdown('<span class="mode-pill mode-sheets">☁️ Google Sheets</span>', unsafe_allow_html=True)
        st.caption("Data synced to your spreadsheet.")

    st.markdown("---")

    # ── Team ──────────────────────────────────────────────────────────────────
    st.markdown("### 👥 Your Team")
    new_name = st.text_input("Add a direct report", placeholder="e.g. Jane Smith", label_visibility="collapsed")
    if st.button("➕ Add person", use_container_width=True) and new_name.strip():
        dm().add_direct_report(new_name.strip())
        st.session_state.direct_reports = dm().get_direct_reports()
        st.rerun()

    reports = st.session_state.direct_reports
    if reports:
        for r in reports:
            st.markdown(f"&nbsp;&nbsp;• {r}")
    else:
        st.caption("No team members yet — add one above.")

    st.markdown("---")

    # ── Manual Google Sheets connection (fallback if secrets not configured) ──
    if mode == "local":
        with st.expander("☁️ Connect Google Sheets"):
            st.caption("Connect a Google Sheet to sync your data to the cloud.")
            spreadsheet_id = st.text_input("Spreadsheet ID", placeholder="1BxiMVs0XRA5...")
            creds_file = st.file_uploader("Service account JSON", type="json")
            if not GSPREAD_AVAILABLE:
                st.warning("Run `pip install gspread google-auth` first.")
            elif st.button("Connect", type="primary", use_container_width=True):
                if not spreadsheet_id or not creds_file:
                    st.error("Need both the Spreadsheet ID and the JSON file.")
                else:
                    try:
                        creds_data = json.loads(creds_file.read())
                        sheets_dm = SheetsManager(creds_data, spreadsheet_id)
                        sheets_dm.ensure_worksheets()
                        st.session_state.dm   = sheets_dm
                        st.session_state.mode = "sheets"
                        st.session_state.direct_reports = sheets_dm.get_direct_reports()
                        st.success("Connected ✓")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    st.markdown("---")
    if st.button("🔄 Refresh", use_container_width=True):
        st.session_state.direct_reports = dm().get_direct_reports()
        st.rerun()
    st.caption(f"Refreshed: {datetime.now().strftime('%H:%M')}")


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Manager Dashboard")
st.caption(f"{date.today().strftime('%A, %B %d, %Y')}")

try:
    issues_df  = dm().get_data("Issues")
    actions_df = dm().get_data("ActionItems")
    agenda_df  = dm().get_data("Agenda")

    open_issues     = len(issues_df[issues_df["Status"] == "Open"])    if not issues_df.empty and "Status" in issues_df.columns else 0
    high_priority   = len(issues_df[(issues_df["Status"] == "Open") & (issues_df["Priority"] == "High")]) if not issues_df.empty and "Priority" in issues_df.columns else 0
    pending_actions = len(actions_df[actions_df["Status"] == "Pending"]) if not actions_df.empty and "Status" in actions_df.columns else 0
    agenda_count    = len(agenda_df[agenda_df["Discussed"] == "No"]) if not agenda_df.empty and "Discussed" in agenda_df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Open Issues",    open_issues)
    c2.metric("⚡ High Priority",   high_priority)
    c3.metric("✅ Pending Actions", pending_actions)
    c4.metric("💬 Agenda Items",    agenda_count)
except Exception as e:
    st.warning(f"Could not load summary: {e}")

st.markdown("---")

tabs = st.tabs(["🔴 Issues", "💬 1:1 Agenda", "✅ Action Items", "📅 Calendar", "📚 Reference", "📝 Notes"])
tab_issues, tab_agenda, tab_actions, tab_calendar, tab_ref, tab_notes = tabs


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_issues:
    st.markdown('<div class="section-header">Outstanding Issues</div>', unsafe_allow_html=True)
    st.caption("Track problems, blockers, or anything that needs resolution.")
    col_form, col_list = st.columns([1, 2], gap="large")
    with col_form:
        with st.container(border=True):
            st.markdown("**➕ Log a new issue**")
            i_title    = st.text_input("Title", key="i_title", placeholder="Short description")
            i_desc     = st.text_area("More detail (optional)", key="i_desc", height=80)
            i_priority = st.selectbox("Priority", ["High", "Medium", "Low"], key="i_priority")
            i_owner    = st.selectbox("Who owns it?", ["(Unassigned)"] + st.session_state.direct_reports, key="i_owner")
            i_due      = st.date_input("Due date (optional)", value=None, key="i_due")
            if st.button("Add Issue", type="primary", use_container_width=True):
                if not i_title.strip():
                    st.warning("Please add a title.")
                else:
                    dm().append_row("Issues", {
                        "Title": i_title.strip(), "Description": i_desc.strip(),
                        "Priority": i_priority, "Owner": i_owner,
                        "Due": str(i_due) if i_due else "", "Status": "Open",
                        "Created": str(date.today()),
                    })
                    st.success("Issue logged!")
                    st.rerun()
    with col_list:
        df = dm().get_data("Issues")
        if df.empty:
            st.info("No issues yet. Add one on the left to get started.")
        else:
            fc1, fc2 = st.columns(2)
            f_status   = fc1.multiselect("Status",   ["Open","In Progress","Resolved"], default=["Open","In Progress"])
            f_priority = fc2.multiselect("Priority", ["High","Medium","Low"],           default=["High","Medium","Low"])
            view = df.copy()
            if "Status"   in view.columns and f_status:   view = view[view["Status"].isin(f_status)]
            if "Priority" in view.columns and f_priority: view = view[view["Priority"].isin(f_priority)]
            porder = {"High": 0, "Medium": 1, "Low": 2}
            if "Priority" in view.columns:
                view = view.assign(_s=view["Priority"].map(porder).fillna(9)).sort_values("_s").drop(columns=["_s"])
            for idx, row in view.iterrows():
                bcls = f"badge-{row.get('Priority','medium').lower()}"
                with st.container(border=True):
                    h1, h2 = st.columns([3, 1])
                    h1.markdown(f"**{row.get('Title','')}**")
                    h2.markdown(f'<span class="badge {bcls}">{row.get("Priority","")}</span>', unsafe_allow_html=True)
                    meta = []
                    if row.get("Owner"): meta.append(f"👤 {row['Owner']}")
                    if row.get("Due"):   meta.append(f"📅 {row['Due']}")
                    st.caption("  ·  ".join(meta) if meta else "")
                    if row.get("Description"):
                        st.markdown(f"<small style='color:#64748b'>{row['Description']}</small>", unsafe_allow_html=True)
                    s1, s2 = st.columns(2)
                    choices = ["Open","In Progress","Resolved"]
                    cur = row.get("Status","Open")
                    new_status = s1.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"is_{idx}", label_visibility="collapsed")
                    if s2.button("Update", key=f"iu_{idx}", use_container_width=True):
                        dm().update_cell("Issues", idx, "Status", new_status)
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 1:1 AGENDA
# ═══════════════════════════════════════════════════════════════════════════════
with tab_agenda:
    st.markdown('<div class="section-header">1:1 Agenda Builder</div>', unsafe_allow_html=True)
    st.caption("Build a running list of topics for each person. Mark them done after your meeting.")
    if not st.session_state.direct_reports:
        st.info("👈 Add team members in the sidebar first.")
    else:
        selected = st.selectbox("Who are you meeting with?", st.session_state.direct_reports, key="ag_person")
        col_add, col_view = st.columns([1, 2], gap="large")
        with col_add:
            with st.container(border=True):
                st.markdown(f"**➕ Add topic for {selected}**")
                a_topic    = st.text_area("What do you want to discuss?", key="a_topic", height=80)
                a_type     = st.selectbox("Category", ["Update","Feedback","Blocker","Development","Recognition","Other"], key="a_type")
                a_added_by = st.radio("Added by", ["Me", selected], horizontal=True, key="a_by")
                if st.button("Add to Agenda", type="primary", use_container_width=True):
                    if not a_topic.strip():
                        st.warning("Please add a topic.")
                    else:
                        dm().append_row("Agenda", {
                            "Person": selected, "Topic": a_topic.strip(),
                            "Category": a_type, "AddedBy": a_added_by,
                            "Discussed": "No", "Created": str(date.today()),
                        })
                        st.success("Added!")
                        st.rerun()
        with col_view:
            df = dm().get_data("Agenda")
            person_df = df[df["Person"] == selected] if not df.empty and "Person" in df.columns else pd.DataFrame()
            show_done = st.toggle("Show completed topics", False, key="ag_show_done")
            if person_df.empty:
                st.info(f"No topics for {selected} yet.")
            else:
                pending = person_df[person_df["Discussed"] == "No"]  if "Discussed" in person_df.columns else person_df
                done    = person_df[person_df["Discussed"] == "Yes"] if "Discussed" in person_df.columns else pd.DataFrame()
                st.markdown(f"**{len(pending)} to discuss · {len(done)} done**")
                for idx, row in pending.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.markdown(f"**{row.get('Topic','')}**")
                        c1.caption(f"📁 {row.get('Category','')}  ·  Added by {row.get('AddedBy','')}  ·  {row.get('Created','')}")
                        if c2.button("✓ Done", key=f"ag_{idx}", use_container_width=True):
                            dm().update_cell("Agenda", idx, "Discussed", "Yes")
                            st.rerun()
                if show_done and not done.empty:
                    st.markdown("---")
                    st.markdown("**Previously discussed:**")
                    for _, row in done.iterrows():
                        st.markdown(f"~~{row.get('Topic','')}~~ · <small style='color:#94a3b8'>{row.get('Created','')}</small>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION ITEMS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_actions:
    st.markdown('<div class="section-header">Action Items & Follow-ups</div>', unsafe_allow_html=True)
    st.caption("Track commitments from meetings. Overdue items are flagged automatically.")
    col_f, col_v = st.columns([1, 2], gap="large")
    with col_f:
        with st.container(border=True):
            st.markdown("**➕ New action item**")
            ac_task  = st.text_input("What needs to be done?", key="ac_task")
            ac_owner = st.selectbox("Who's doing it?", ["Me"] + st.session_state.direct_reports, key="ac_owner")
            ac_due   = st.date_input("Due date", key="ac_due")
            ac_src   = st.selectbox("From which meeting?", ["1:1","Team Meeting","Issue","Email","Other"], key="ac_src")
            if st.button("Add Action", type="primary", use_container_width=True):
                if not ac_task.strip():
                    st.warning("Please describe the task.")
                else:
                    dm().append_row("ActionItems", {
                        "Task": ac_task.strip(), "Owner": ac_owner,
                        "Due": str(ac_due), "Source": ac_src,
                        "Status": "Pending", "Created": str(date.today()),
                    })
                    st.success("Added!")
                    st.rerun()
    with col_v:
        df = dm().get_data("ActionItems")
        if df.empty:
            st.info("No action items yet.")
        else:
            f_owner = st.selectbox("Show actions for", ["Everyone","Me"] + st.session_state.direct_reports, key="ac_filt")
            open_df = df[df["Status"] != "Done"].copy() if "Status" in df.columns else df.copy()
            if f_owner != "Everyone" and "Owner" in open_df.columns:
                open_df = open_df[open_df["Owner"] == f_owner]
            today_str = str(date.today())
            if open_df.empty:
                st.success("🎉 All clear! No pending actions.")
            else:
                for idx, row in open_df.iterrows():
                    overdue = row.get("Due","") and row.get("Due","") < today_str and row.get("Status") == "Pending"
                    with st.container(border=True):
                        r1, r2 = st.columns([4,1])
                        r1.markdown(f"{'🚨 ' if overdue else ''}**{row.get('Task','')}**")
                        r1.caption(f"👤 {row.get('Owner','')}  ·  📅 {row.get('Due','')}  ·  📁 {row.get('Source','')}" + (" — **OVERDUE**" if overdue else ""))
                        choices = ["Pending","In Progress","Done"]
                        cur = row.get("Status","Pending")
                        ns = r2.selectbox("", choices, index=choices.index(cur) if cur in choices else 0, key=f"acs_{idx}", label_visibility="collapsed")
                        if r2.button("Save", key=f"acsv_{idx}", use_container_width=True):
                            dm().update_cell("ActionItems", idx, "Status", ns)
                            st.rerun()
            done_df = df[df["Status"] == "Done"] if "Status" in df.columns else pd.DataFrame()
            if not done_df.empty:
                with st.expander(f"✅ {len(done_df)} completed"):
                    for _, row in done_df.iterrows():
                        st.markdown(f"~~{row.get('Task','')}~~ · {row.get('Owner','')} · {row.get('Due','')}")


# ═══════════════════════════════════════════════════════════════════════════════
# CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_calendar:
    st.markdown('<div class="section-header">Calendar & Upcoming Events</div>', unsafe_allow_html=True)
    st.caption("A lightweight tracker for meetings, reviews, and deadlines.")
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
                    dm().append_row("Calendar", {
                        "Title": ev_title.strip(), "Date": str(ev_date),
                        "Time": str(ev_time)[:5] if ev_time else "",
                        "Type": ev_type, "With": ", ".join(ev_with),
                        "Notes": ev_notes.strip(),
                    })
                    st.success("Event added!")
                    st.rerun()
    with col_v:
        df = dm().get_data("Calendar")
        today_str = str(date.today())
        icons = {"1:1":"👤","Team Meeting":"👥","Deadline":"⏰","Performance Review":"📊","Planning":"🗓","Other":"📌"}
        if df.empty:
            st.info("No events yet.")
        else:
            upcoming = df[df["Date"] >= today_str].sort_values("Date") if "Date" in df.columns else df
            past     = df[df["Date"] < today_str].sort_values("Date",ascending=False) if "Date" in df.columns else pd.DataFrame()
            st.markdown(f"**{len(upcoming)} upcoming**")
            for _, row in upcoming.iterrows():
                icon = icons.get(row.get("Type",""), "📌")
                is_today = row.get("Date","") == today_str
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    c1.markdown(f"{icon} **{row.get('Title','')}**")
                    if is_today: c2.markdown("🟡 **Today**")
                    meta = [f"📅 {row.get('Date','')}"]
                    if row.get("Time"): meta.append(f"🕐 {row['Time']}")
                    if row.get("With"): meta.append(f"👥 {row['With']}")
                    c1.caption("  ·  ".join(meta))
                    if row.get("Notes"): st.caption(row["Notes"])
            if not past.empty:
                with st.expander(f"🗓 {len(past)} past events"):
                    for _, row in past.iterrows():
                        st.caption(f"{row.get('Date','')} — {row.get('Title','')}")


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown('<div class="section-header">Reference Library</div>', unsafe_allow_html=True)
    st.caption("Your personal knowledge base. Store SQL queries, scripts, checklists, templates — with your own explanation of each.")
    col_add, col_view = st.columns([1, 2], gap="large")
    with col_add:
        with st.container(border=True):
            st.markdown("**➕ Add a reference entry**")
            r_title = st.text_input("Title", key="r_title", placeholder="e.g. Weekly report SQL")
            r_cat   = st.selectbox("Category", ["SQL / Query","Python","Shell / Bash","Process / Checklist","Table / Data","Template","Formula","Other"], key="r_cat")
            r_tags  = st.text_input("Tags (comma-separated)", key="r_tags", placeholder="e.g. reporting, HR, weekly")
            r_body  = st.text_area("Content", key="r_body", height=180, placeholder="Paste your script, table, checklist, or template here...")
            r_notes = st.text_area("Your notes / explanation", key="r_notes", height=100, placeholder="What does this do?\nWhen should you use it?\nAny gotchas?")
            if st.button("Save to Reference", type="primary", use_container_width=True):
                if not r_title.strip() or not r_body.strip():
                    st.warning("Title and content are both required.")
                else:
                    dm().append_row("Reference", {
                        "Title": r_title.strip(), "Category": r_cat,
                        "Content": r_body.strip(), "Explanation": r_notes.strip(),
                        "Tags": r_tags.strip(),
                        "Created": str(datetime.now().strftime("%Y-%m-%d %H:%M")),
                    })
                    st.success("Saved!")
                    st.rerun()
    with col_view:
        df = dm().get_data("Reference")
        if df.empty:
            st.info("Nothing saved yet.\n\nIdeas:\n- A SQL query you run every week\n- A Python snippet for data cleaning\n- An onboarding checklist\n- A performance review template")
        else:
            sc1, sc2 = st.columns([2,1])
            search = sc1.text_input("🔍 Search", key="r_search", placeholder="Filter by keyword...")
            all_cats = ["All"] + sorted(df["Category"].dropna().unique().tolist()) if "Category" in df.columns else ["All"]
            f_cat = sc2.selectbox("Category", all_cats, key="r_cat_filter")
            view = df.copy().iloc[::-1]
            if search:
                mask = view.apply(lambda row: search.lower() in str(row).lower(), axis=1)
                view = view[mask]
            if f_cat != "All" and "Category" in view.columns:
                view = view[view["Category"] == f_cat]
            if view.empty:
                st.info("No entries match your filter.")
            else:
                st.markdown(f"**{len(view)} entries**")
                for idx, row in view.iterrows():
                    with st.expander(f"**{row.get('Title','')}**  ·  `{row.get('Category','')}`  ·  {row.get('Created','')}"):
                        tags = row.get("Tags","")
                        if tags:
                            st.markdown(" ".join([f"`{t.strip()}`" for t in tags.split(",") if t.strip()]))
                        content = row.get("Content","")
                        if content:
                            cat  = row.get("Category","")
                            lang = "sql" if "SQL" in cat else "python" if "Python" in cat else "bash" if "Shell" in cat else "text"
                            st.markdown("**Content:**")
                            st.code(content, language=lang)
                        expl = row.get("Explanation","")
                        if expl:
                            st.markdown("**Notes / Explanation:**")
                            st.info(expl)
                        if st.button("🗑 Delete this entry", key=f"rdel_{idx}"):
                            dm().delete_row("Reference", idx)
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_notes:
    st.markdown('<div class="section-header">Notes</div>', unsafe_allow_html=True)
    st.caption("General-purpose scratch pad. Searchable, taggable, linkable to team members.")
    col_f, col_v = st.columns([1, 2], gap="large")
    with col_f:
        with st.container(border=True):
            st.markdown("**➕ New note**")
            n_title = st.text_input("Title", key="n_title")
            n_tags  = st.multiselect("Tags", ["Strategy","HR","Technical","Process","Personal","Meeting","Other"], key="n_tags")
            n_link  = st.selectbox("Link to team member (optional)", ["—"] + st.session_state.direct_reports, key="n_link")
            n_body  = st.text_area("Note", key="n_body", height=140)
            if st.button("Save Note", type="primary", use_container_width=True):
                if not n_title.strip() or not n_body.strip():
                    st.warning("Title and note are both required.")
                else:
                    dm().append_row("Notes", {
                        "Title": n_title.strip(), "Tags": ", ".join(n_tags),
                        "LinkedTo": n_link if n_link != "—" else "",
                        "Body": n_body.strip(),
                        "Created": str(datetime.now().strftime("%Y-%m-%d %H:%M")),
                    })
                    st.success("Saved!")
                    st.rerun()
    with col_v:
        df = dm().get_data("Notes")
        if df.empty:
            st.info("No notes yet.")
        else:
            search = st.text_input("🔍 Search notes", key="n_search", placeholder="Type to filter...")
            view = df.copy().iloc[::-1]
            if search:
                mask = view.apply(lambda row: search.lower() in str(row).lower(), axis=1)
                view = view[mask]
            for _, row in view.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row.get('Title','')}**")
                    meta = [row.get("Created","")]
                    if row.get("Tags"):    meta.append(f"🏷 {row['Tags']}")
                    if row.get("LinkedTo"): meta.append(f"👤 {row['LinkedTo']}")
                    st.caption("  ·  ".join(meta))
                    st.markdown(row.get("Body",""))
