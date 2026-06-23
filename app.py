import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import calendar
import os
import json

# --- 기본 설정 ---
CRED_FILENAME = "service.json"
FIREBASE_DB_URL = 'https://ydcpmanager-default-rtdb.firebaseio.com/'

st.set_page_config(
    page_title="율동공원 모바일", 
    page_icon="⛺", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 🔐 로그인 시스템
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def check_password():
    if "PASSWORD" in st.secrets:
        system_pass = st.secrets["PASSWORD"]
    else:
        system_pass = "0616"
    
    if st.session_state.password_input == system_pass:
        st.session_state.logged_in = True
    else:
        st.error("비밀번호가 틀렸습니다.")

if not st.session_state.logged_in:
    st.markdown("## 🔒 관리자 로그인")
    st.text_input("비밀번호를 입력하세요", type="password", key="password_input", on_change=check_password)
    if st.button("로그인"):
        check_password()
    st.stop()

# ==========================================
# 🎨 UI 스타일 (모바일 최적화)
# ==========================================
st.markdown("""
<style>
    .stApp { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; }
    
    /* 캘린더 스타일 */
    .cal-container { display: flex; flex-direction: column; border: 1px solid #ddd; background-color: #fff; }
    .cal-header-row { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #f1f3f5; border-bottom: 1px solid #ddd; }
    .cal-header-item { text-align: center; font-weight: bold; padding: 5px 0; font-size: 0.9rem; color: #333; }
    .cal-header-item:nth-child(6) { color: #1c7ed6; }
    .cal-header-item:nth-child(7) { color: #e03131; }
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #e9ecef; gap: 1px; }
    .cal-cell { background-color: #ffffff; min-height: 80px; padding: 2px; display: flex; flex-direction: column; }
    .cal-cell.empty { background-color: #f8f9fa; }
    .date-num { font-size: 0.8rem; font-weight: bold; margin-bottom: 2px; padding-left: 2px; color: #333; }
    .cal-cell:nth-child(7n-1) .date-num { color: #1c7ed6; }
    .cal-cell:nth-child(7n) .date-num { color: #e03131; }

    /* 근무자 뱃지 */
    .work-box { font-size: 0.7rem; padding: 2px 4px; margin-bottom: 2px; border-radius: 4px; line-height: 1.2; color: #333; font-weight: 500; word-break: keep-all; }
    .wb-a { background-color: #e7f5ff; border: 1px solid #d0ebff; color: #1864ab; }
    .wb-b { background-color: #fff4e6; border: 1px solid #ffe8cc; color: #d9480f; }
    .wb-rest { background-color: #ffe3e3; color: #c92a2a; text-align: center; }
    .badge { font-size: 0.7rem; padding: 2px 4px; border-radius: 3px; margin-top: 1px; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
    .bg-night { background-color: #1E3A8A; } .bg-leave { background-color: #10B981; } .bg-ot { background-color: #0EA5E9; } .bg-gray { background-color: #868e96; }
    
    /* 모바일 반응형 */
    @media (max-width: 600px) { 
        .cal-header-item { font-size: 0.75rem; padding: 3px 0; } 
        .cal-cell { min-height: 65px; padding: 1px; } 
        .date-num { font-size: 0.7rem; } 
        .work-box, .badge { font-size: 0.6rem; padding: 1px 2px; } 
    }
    
    /* 현황판 스타일 */
    .stat-card { padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 5px; }
    .stat-blue { background-color: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; }
    .stat-green { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
</style>
""", unsafe_allow_html=True)

# --- Firebase 초기화 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(CURRENT_DIR, CRED_FILENAME)

@st.cache_resource
def init_firebase():
    if firebase_admin._apps: return True
    if "firebase_key" in st.secrets:
        try:
            val = st.secrets["firebase_key"]
            if isinstance(val, str): cred_info = json.loads(val)
            else: cred_info = dict(val)
            if "private_key" in cred_info: cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
            return True
        except Exception as e: st.error(f"Cloud 인증 오류: {e}"); return False
    if os.path.exists(CRED_PATH):
        try:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
            return True
        except Exception as e: st.error(f"로컬 인증 오류: {e}"); return False
    st.warning("⚠️ 인증 파일을 찾을 수 없습니다.")
    return False

if not init_firebase(): st.stop()

# --- DB 헬퍼 ---
def get_data(path): return db.reference(f'yuldong_data/{path}').get()
def set_data(path, data): db.reference(f'yuldong_data/{path}').set(data)
def normalize_data(data):
    if isinstance(data, list): return {str(i): v for i, v in enumerate(data) if v is not None}
    return data if data else {}

# --- 달력 그리기 ---
def draw_calendar(year, month, sch_data, my_filter=None):
    records = normalize_data(sch_data.get("records", {}))
    teams = normalize_data(sch_data.get("teams", {}))
    month_rules = normalize_data(sch_data.get("month_rules", {}))

    t1_list = teams.get("1", [])
    t2_list = teams.get("2", [])
    if isinstance(t1_list, str): t1_list = [t1_list]
    if isinstance(t2_list, str): t2_list = [t2_list]

    month_key = f"{year}-{month:02d}"
    has_rule = month_key in month_rules
    rules = month_rules.get(month_key, {})
    start_team = rules.get("start_team", "1")
    time_type = rules.get("time_type", "split")
    rotation_type = rules.get("rotation_type", "fixed")
    base_off1 = rules.get("t1_off", [4, 5])
    base_off2 = rules.get("t2_off", [6, 0])

    html = '<div class="cal-container"><div class="cal-header-row">'
    days = ['월', '화', '수', '목', '금', '토', '일']
    for d in days: html += f'<div class="cal-header-item">{d}</div>'
    html += '</div><div class="cal-grid">'

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    for r_idx, week in enumerate(month_days):
        # PC 버전과 동일한 rotation_type 처리
        if rotation_type == "two_weeks":
            rot_state = (r_idx // 2) % 2
        elif rotation_type == "biweekly":
            rot_state = r_idx % 2
        else:
            rot_state = 0

        if rot_state == 1:
            curr_off1, curr_off2 = base_off2, base_off1
        else:
            curr_off1, curr_off2 = base_off1, base_off2

        if rotation_type == "two_weeks":
            is_primary_order = (rot_state == 0)
        else:
            is_primary_order = (r_idx % 2 == 0)
        is_t1_first = (start_team == "1") if is_primary_order else (start_team == "2")

        for c_idx, day in enumerate(week):
            if day == 0:
                html += '<div class="cal-cell empty"></div>'
                continue

            curr_date = datetime(year, month, day)
            prev_str = (curr_date - timedelta(days=1)).strftime("%Y-%m-%d")
            d_str = f"{year}-{month:02d}-{day:02d}"

            # 어제 당직자 → 오늘 휴무 (모바일에서 추가한 당직휴무 미등록 케이스 대비)
            off_names = set()
            if prev_str in records:
                prev_recs = records[prev_str]
                if isinstance(prev_recs, dict): prev_recs = list(prev_recs.values())
                elif isinstance(prev_recs, list): prev_recs = [x for x in prev_recs if x]
                for r in prev_recs:
                    if isinstance(r, dict) and r.get('type') == '당직':
                        off_names.add(r.get('name'))

            # 당일 수동 override (PC에서 설정한 휴무/특별근무 반영)
            day_recs = records.get(d_str, {})
            if isinstance(day_recs, dict): day_recs = list(day_recs.values())
            elif isinstance(day_recs, list): day_recs = [x for x in day_recs if x]

            special_names = set()
            for r in day_recs:
                if not isinstance(r, dict): continue
                if r.get('type') in ['휴무', '당직휴무', '팀휴무']:
                    off_names.add(r.get('name'))
                elif r.get('type') == '특별근무':
                    special_names.add(r.get('name'))

            # 규칙 + 수동 override 적용 (PC 버전과 동일 로직)
            is_t1_rule_work = has_rule and (c_idx not in curr_off1)
            is_t2_rule_work = has_rule and (c_idx not in curr_off2)
            final_t1 = [m for m in t1_list if (is_t1_rule_work and m not in off_names) or m in special_names]
            final_t2 = [m for m in t2_list if (is_t2_rule_work and m not in off_names) or m in special_names]

            top_team, bot_team = (final_t1, final_t2) if is_t1_first else (final_t2, final_t1)

            # time_type 반영
            if time_type == "unified":
                t_top = t_bot = "[09-18]"
            else:
                t_top, t_bot = "[08-17]", "[11-20]"

            work_html = ""
            if has_rule:
                if not top_team and not bot_team:
                    work_html += '<div class="work-box wb-rest">휴무</div>'
                elif top_team and bot_team:
                    work_html += f'<div class="work-box wb-a">A {t_top} {", ".join(top_team)}</div>'
                    work_html += f'<div class="work-box wb-b">B {t_bot} {", ".join(bot_team)}</div>'
                elif top_team:
                    work_html += f'<div class="work-box wb-a">통합 {", ".join(top_team)}</div>'
                else:
                    work_html += f'<div class="work-box wb-b">통합 {", ".join(bot_team)}</div>'

            # 개인 기록 (당직, 연차, 시간외)
            indiv_html = ""
            for evt in day_recs:
                if not isinstance(evt, dict): continue
                if my_filter and my_filter != "전체 보기" and evt.get('name') != my_filter: continue
                e_type, e_name = evt.get('type', ''), evt.get('name', '')
                if e_type == "당직": cls, txt = "bg-night", f"🌙{e_name}"
                elif e_type == "연차": cls, txt = "bg-leave", f"🌴{e_name}"
                elif e_type == "시간외": cls, txt = "bg-ot", f"⏰{e_name}"
                else: continue
                indiv_html += f'<div class="badge {cls}">{txt}</div>'

            html += f'<div class="cal-cell"><div class="date-num">{day}</div>{work_html}{indiv_html}</div>'

    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)

# --- 메인 탭 구성 ---
st.title("🏕️ 율동공원 관리 시스템")
if st.sidebar.button("로그아웃"):
    st.session_state.logged_in = False
    st.rerun()

# 탭 5개로 확장
tab_cal, tab_my, tab_stay, tab_mon, tab_lost = st.tabs(["📅 근무", "✍️ 수정", "⛺ 연박", "📊 현황", "🧢 분실"])

# 1. 근무표 탭
with tab_cal:
    if 'curr_date' not in st.session_state: st.session_state.curr_date = datetime.now()
    def change_month(amount):
        st.session_state.curr_date += timedelta(days=32 * amount)
        st.session_state.curr_date = st.session_state.curr_date.replace(day=1)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: st.button("◀", on_click=change_month, args=(-1,), use_container_width=True)
    with c2: 
        cur = st.session_state.curr_date
        st.markdown(f"<h4 style='text-align:center; margin:0'>{cur.year}년 {cur.month}월</h4>", unsafe_allow_html=True)
    with c3: st.button("▶", on_click=change_month, args=(1,), use_container_width=True)
    
    sch_data = get_data("schedule") or {}
    teams = normalize_data(sch_data.get("teams", {}))
    t1 = teams.get("1", [])
    t2 = teams.get("2", [])
    if isinstance(t1, str): t1 = [t1]
    if isinstance(t2, str): t2 = [t2]
    members = ["전체 보기"] + t1 + t2
    
    my_filter = st.selectbox("직원별 보기", members, label_visibility="collapsed")
    draw_calendar(cur.year, cur.month, sch_data, my_filter)

# 2. 내 수정 탭
with tab_my:
    st.subheader("근무 기록 수정")
    sel_name = st.selectbox("이름", [m for m in members if m != "전체 보기"])

    if sel_name:
        # =============================================
        # 시간외 일괄 등록 · 수정
        # =============================================
        st.markdown("#### ⏰ 시간외 일괄 등록 · 수정")

        col_y, col_m = st.columns(2)
        bulk_year = int(col_y.number_input("년", value=datetime.now().year, min_value=2020, max_value=2030, step=1, key="bulk_year"))
        bulk_month = int(col_m.number_input("월", value=datetime.now().month, min_value=1, max_value=12, step=1, key="bulk_month"))

        _, days_in_month = calendar.monthrange(bulk_year, bulk_month)
        date_options = [f"{bulk_year}-{bulk_month:02d}-{d:02d}" for d in range(1, days_in_month + 1)]
        day_names = ['월', '화', '수', '목', '금', '토', '일']

        def fmt_date(x):
            dt = datetime.strptime(x, "%Y-%m-%d")
            return f"{dt.day}일 ({day_names[dt.weekday()]})"

        selected_dates = st.multiselect(
            f"{bulk_month}월 날짜 선택 (복수 선택 가능)",
            date_options,
            format_func=fmt_date
        )

        col_h, col_btn = st.columns([1, 2])
        default_hours = col_h.number_input("시간(H)", min_value=1, max_value=24, value=4, step=1, key="bulk_hours")
        with col_btn:
            st.write(""); st.write("")
            if st.button("선택 날짜 일괄 등록", type="primary", use_container_width=True):
                if not selected_dates:
                    st.warning("날짜를 선택해주세요.")
                else:
                    fresh_sch = get_data("schedule") or {}
                    if "records" not in fresh_sch: fresh_sch["records"] = {}
                    recs = normalize_data(fresh_sch["records"])
                    for d_key in selected_dates:
                        day_list = recs.get(d_key, [])
                        if isinstance(day_list, dict): day_list = list(day_list.values())
                        elif isinstance(day_list, list): day_list = [x for x in day_list if x]
                        day_list.append({"name": sel_name, "type": "시간외", "val": str(default_hours)})
                        recs[d_key] = day_list
                    fresh_sch["records"] = recs
                    set_data("schedule", fresh_sch)
                    st.success(f"{len(selected_dates)}일 등록 완료 ({default_hours}H)")
                    st.rerun()

        st.divider()

        # --- 해당 월 시간외 빠른 수정 ---
        st.markdown(f"**{bulk_month}월 {sel_name} 시간외 기록**")

        sch_ot = get_data("schedule") or {}
        recs_ot = normalize_data(sch_ot.get("records", {}))
        month_prefix = f"{bulk_year}-{bulk_month:02d}"

        ot_list = []
        for d_key in sorted(recs_ot.keys()):
            if not d_key.startswith(month_prefix): continue
            evts = recs_ot[d_key]
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name and e.get('type') == '시간외':
                    ot_list.append({"date": d_key, "val": str(e.get('val', '0'))})

        if not ot_list:
            st.info(f"{bulk_month}월 시간외 기록이 없습니다.")
        else:
            new_vals = {}
            for i, ot in enumerate(ot_list):
                col_d, col_h2, col_del = st.columns([3, 2, 1])
                col_d.markdown(f"**{fmt_date(ot['date'])}**")
                try: cur_h = float(ot['val'])
                except: cur_h = 0.0
                new_vals[i] = col_h2.number_input(
                    "H", value=cur_h, min_value=0.0, max_value=24.0, step=1.0,
                    key=f"ot_h_{bulk_year}_{bulk_month}_{i}", label_visibility="collapsed"
                )
                if col_del.button("삭제", key=f"ot_del_{bulk_year}_{bulk_month}_{i}"):
                    fresh_sch2 = get_data("schedule") or {}
                    fresh_recs2 = normalize_data(fresh_sch2.get("records", {}))
                    day_evts = fresh_recs2.get(ot['date'], [])
                    if isinstance(day_evts, dict): day_evts = list(day_evts.values())
                    elif isinstance(day_evts, list): day_evts = [x for x in day_evts if x]
                    new_evts = []
                    deleted = False
                    for ev in day_evts:
                        if (not deleted and isinstance(ev, dict) and
                                ev.get('name') == sel_name and ev.get('type') == '시간외' and
                                str(ev.get('val')) == ot['val']):
                            deleted = True
                            continue
                        new_evts.append(ev)
                    fresh_recs2[ot['date']] = new_evts
                    fresh_sch2["records"] = fresh_recs2
                    set_data("schedule", fresh_sch2)
                    st.rerun()

            if st.button("시간 일괄 저장", type="primary", use_container_width=True):
                fresh_sch3 = get_data("schedule") or {}
                fresh_recs3 = normalize_data(fresh_sch3.get("records", {}))
                for i, ot in enumerate(ot_list):
                    new_v = new_vals[i]
                    new_val_str = str(int(new_v) if new_v == int(new_v) else new_v)
                    day_evts = fresh_recs3.get(ot['date'], [])
                    if isinstance(day_evts, dict): day_evts = list(day_evts.values())
                    elif isinstance(day_evts, list): day_evts = [x for x in day_evts if x]
                    updated = False
                    for ev in day_evts:
                        if (not updated and isinstance(ev, dict) and
                                ev.get('name') == sel_name and ev.get('type') == '시간외' and
                                str(ev.get('val')) == ot['val']):
                            ev['val'] = new_val_str
                            updated = True
                    fresh_recs3[ot['date']] = day_evts
                fresh_sch3["records"] = fresh_recs3
                set_data("schedule", fresh_sch3)
                st.success("저장 완료")
                st.rerun()

        st.divider()

        # =============================================
        # 개별 기록 추가 (당직 · 연차 등)
        # =============================================
        with st.expander("➕ 개별 기록 추가 (당직 · 연차 등)"):
            with st.form("new_schedule"):
                c_d, c_t = st.columns(2)
                in_date = c_d.date_input("날짜")
                in_type = c_t.selectbox("구분", ["시간외", "당직", "연차"])
                in_val = st.text_input("내용", placeholder="시간(4, 8) 또는 메모")

                if st.form_submit_button("기록 저장", type="primary", use_container_width=True):
                    d_key = in_date.strftime("%Y-%m-%d")
                    fresh_sch = get_data("schedule") or {}
                    if "records" not in fresh_sch: fresh_sch["records"] = {}
                    records = normalize_data(fresh_sch["records"])

                    day_list = records.get(d_key, [])
                    if isinstance(day_list, dict): day_list = list(day_list.values())
                    elif isinstance(day_list, list): day_list = [x for x in day_list if x]

                    save_val = in_val
                    if in_type == "당직" and not in_val: save_val = "22:00~"

                    day_list.append({"name": sel_name, "type": in_type, "val": save_val})
                    records[d_key] = day_list
                    fresh_sch["records"] = records
                    set_data("schedule", fresh_sch)
                    st.success("저장됨")
                    st.rerun()

        st.divider()
        st.write("🗑️ **최근 기록 삭제**")

        sch_data = get_data("schedule") or {}
        records = normalize_data(sch_data.get("records", {}))

        my_logs = []
        for d_key, evts in records.items():
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name:
                    temp_e = e.copy()
                    temp_e['date'] = d_key
                    my_logs.append(temp_e)

        my_logs.sort(key=lambda x: x['date'], reverse=True)

        if not my_logs:
            st.info("기록이 없습니다.")

        for i, log in enumerate(my_logs[:10]):
            with st.container(border=True):
                col_info, col_btn = st.columns([4, 1])
                type_icon = {"시간외": "⏰", "당직": "🌙", "연차": "🌴"}.get(log['type'], "📝")
                disp_text = f"{type_icon} {log['type']} | {log['val']}"
                with col_info:
                    st.write(f"**{log['date']}**")
                    st.caption(disp_text)
                with col_btn:
                    unique_key = f"del_{log['date']}_{log['type']}_{log['val']}_{i}"
                    if st.button("삭제", key=unique_key, use_container_width=True):
                        fresh_sch = get_data("schedule") or {}
                        fresh_recs = normalize_data(fresh_sch.get("records", {}))
                        target_day_list = fresh_recs.get(log['date'], [])
                        if isinstance(target_day_list, dict): target_day_list = list(target_day_list.values())
                        elif isinstance(target_day_list, list): target_day_list = [x for x in target_day_list if x]
                        new_day_list = []
                        deleted = False
                        for item in target_day_list:
                            if (not deleted and
                                    item.get('name') == sel_name and
                                    item.get('type') == log['type'] and
                                    str(item.get('val')) == str(log['val'])):
                                deleted = True
                                continue
                            new_day_list.append(item)
                        fresh_recs[log['date']] = new_day_list
                        fresh_sch["records"] = fresh_recs
                        set_data("schedule", fresh_sch)
                        st.success("삭제되었습니다.")
                        st.rerun()

# 3. [신규] 연박자 보기 탭
with tab_stay:
    st.subheader("⛺ 연박 및 이동 현황")
    stay_data = get_data("stay_result")
    
    if stay_data:
        updated = stay_data.get("updated_at", "-")
        st.info(f"🕒 업데이트: {updated}")
        
        items = stay_data.get("list", [])
        if not items:
            st.success("연박/이동 내역이 없습니다.")
        else:
            for item in items:
                # "방이동" 키워드가 있으면 경고색, 연박이면 파란색
                if "방이동" in item or "➡" in item:
                    st.warning(item)
                else:
                    st.info(item)
            
            st.caption("※ 데이터는 PC 프로그램에서 분석 후 자동 반영됩니다.")
    else:
        st.warning("데이터가 없습니다. PC 프로그램에서 분석을 실행해주세요.")

# 4. [신규] 입실 현황 탭
with tab_mon:
    st.subheader("📊 예약 및 입실 현황")
    mon_data = get_data("monitor_result")
    
    if mon_data:
        updated = mon_data.get("updated_at", "-")
        st.caption(f"🕒 기준: {updated}")
        
        summ = mon_data.get("summary", {})
        col1, col2, col3 = st.columns(3)
        col1.metric("총 예약", f"{summ.get('total',0)}건")
        col2.metric("입실(파랑)", f"{summ.get('checkin',0)}건")
        col3.metric("대기(초록)", f"{summ.get('nocheck',0)}건")
        
        st.divider()
        
        zones = mon_data.get("zones", {})
        # A~F 구역별 표시
        for z_name in ["A", "B", "C", "D", "E", "F", "기타"]:
            if z_name not in zones: continue
            
            z_data = zones[z_name]
            blues = z_data.get("blue", [])
            greens = z_data.get("green", [])
            
            if not blues and not greens: continue
            
            with st.expander(f"📍 {z_name} 구역 ({len(blues)+len(greens)}건)", expanded=True):
                # 입실 완료 (파랑)
                if blues:
                    for b in blues:
                        st.markdown(f"<div class='stat-card stat-blue'>{b}</div>", unsafe_allow_html=True)
                # 미입실 (초록)
                if greens:
                    for g in greens:
                        st.markdown(f"<div class='stat-card stat-green'>{g}</div>", unsafe_allow_html=True)
    else:
        st.warning("데이터가 없습니다. PC 프로그램에서 분석을 실행해주세요.")

# 5. 분실물 탭
with tab_lost:
    st.subheader("🧢 분실물 센터")
    raw_lost = get_data("lost_found")
    lost_items = []
    if isinstance(raw_lost, dict): lost_items = list(raw_lost.values())
    elif isinstance(raw_lost, list): lost_items = [x for x in raw_lost if x]
    
    # 등록 UI
    with st.expander("➕ 분실물 등록", expanded=False):
        c1, c2 = st.columns(2)
        l_loc = c1.text_input("장소")
        l_nm = c2.text_input("물건명")
        if st.button("등록", use_container_width=True):
            if l_loc and l_nm:
                new_l = {"date": datetime.now().strftime("%Y-%m-%d"), "item": l_nm, "location": l_loc, "status": "보관중", "return_date": "-"}
                lost_items.append(new_l)
                set_data("lost_found", lost_items)
                st.rerun()

    # 리스트 표시
    cnt = len([x for x in lost_items if x.get('status')=='보관중'])
    st.markdown(f"**보관중: {cnt}개**")
    
    for i, item in reversed(list(enumerate(lost_items))):
        is_kept = (item.get('status') == "보관중")
        with st.container(border=True):
            c_txt, c_btn = st.columns([3, 1])
            with c_txt:
                icon = "🟢" if is_kept else "⚪"
                st.write(f"{icon} **{item.get('item')}**")
                st.caption(f"{item.get('location')} | {item.get('date')}")
            with c_btn:
                if is_kept:
                    if st.button("수령", key=f"rec_{i}"):
                        lost_items[i]['status'] = "수령완료"
                        lost_items[i]['return_date'] = datetime.now().strftime("%Y-%m-%d")
                        set_data("lost_found", lost_items)
                        st.rerun()
                else:
                    if st.button("삭제", key=f"del_{i}"):
                        del lost_items[i]
                        set_data("lost_found", lost_items)
                        st.rerun()