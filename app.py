import streamlit as st
import firebase_admin
from firebase_admin import credentials, db, storage
from datetime import datetime, timedelta
import calendar
import os
import json
import re
from PIL import Image
import io
import uuid
import requests
import zipfile

# --- 기본 설정 ---
CRED_FILENAME = "service.json" 
FIREBASE_DB_URL = 'https://ydcpmanager-default-rtdb.firebaseio.com/'
# [수정] 스토리지 버킷 주소 (gs:// 제외)
STORAGE_BUCKET_URL = 'ydcpmanager.firebasestorage.app'

st.set_page_config(
    page_title="율동공원 모바일", 
    page_icon="⛺", 
    layout="wide",
    initial_sidebar_state="expanded" 
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
# 🎨 UI 스타일
# ==========================================
st.markdown("""
<style>
    .stApp { font-family: 'Pretendard', 'Malgun Gothic', sans-serif; }
    /* 캘린더 스타일 (기존 유지) */
    .cal-container { display: flex; flex-direction: column; border: 1px solid #ddd; background-color: #fff; border-radius: 8px; overflow: hidden; }
    .cal-header-row { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #f8f9fa; border-bottom: 1px solid #ddd; }
    .cal-header-item { text-align: center; font-weight: bold; padding: 8px 0; font-size: 0.9rem; color: #495057; }
    .cal-header-item:nth-child(6) { color: #1c7ed6; }
    .cal-header-item:nth-child(7) { color: #e03131; }
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #dee2e6; gap: 1px; }
    .cal-cell { background-color: #ffffff; min-height: 60px; height: auto; padding: 4px 2px; display: flex; flex-direction: column; gap: 2px; }
    .cal-cell.empty { background-color: #f8f9fa; min-height: 60px; }
    .date-num { font-size: 0.8rem; font-weight: bold; margin-bottom: 2px; padding-left: 4px; color: #333; }
    .cal-cell:nth-child(7n-1) .date-num { color: #1c7ed6; }
    .cal-cell:nth-child(7n) .date-num { color: #e03131; }
    .work-box { font-size: 0.75rem; padding: 3px 4px; border-radius: 4px; line-height: 1.3; color: #333; font-weight: 500; word-break: keep-all; white-space: normal; }
    .wb-a { background-color: #e7f5ff; border: 1px solid #d0ebff; color: #1864ab; }
    .wb-b { background-color: #fff4e6; border: 1px solid #ffe8cc; color: #d9480f; }
    .wb-rest { background-color: #ffe3e3; color: #c92a2a; text-align: center; }
    .badge { font-size: 0.7rem; padding: 3px 4px; border-radius: 4px; margin-top: 1px; color: white; display: block; white-space: normal; line-height: 1.2; }
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
    
    fb_config = {
        'databaseURL': FIREBASE_DB_URL,
        'storageBucket': STORAGE_BUCKET_URL
    }

    if "firebase_key" in st.secrets:
        try:
            val = st.secrets["firebase_key"]
            if isinstance(val, str): cred_info = json.loads(val)
            else: cred_info = dict(val)
            if "private_key" in cred_info: 
                cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, fb_config)
            return True
        except Exception as e: st.error(f"Cloud 인증 오류: {e}"); return False
    
    if os.path.exists(CRED_PATH):
        try:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred, fb_config)
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

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("☁️ DB 동기화")
    if st.button("🔄 최신 데이터 불러오기 (Load)", use_container_width=True):
        st.cache_resource.clear()
        st.toast("☁️ 클라우드에서 최신 데이터를 불러왔습니다.")
        st.rerun()
    st.info("**[자동 저장]**\n등록/삭제/수정 시 즉시 클라우드에 저장됩니다.")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

# --- 자동 근무자 계산 함수 ---
def get_auto_duty_members(curr_date, sch_data):
    records = normalize_data(sch_data.get("records", {}))
    teams = normalize_data(sch_data.get("teams", {}))
    month_rules = normalize_data(sch_data.get("month_rules", {}))
    
    t1_list = teams.get("1", [])
    t2_list = teams.get("2", [])
    if isinstance(t1_list, str): t1_list = [t1_list]
    if isinstance(t2_list, str): t2_list = [t2_list]

    year, month, day = curr_date.year, curr_date.month, curr_date.day
    date_str = curr_date.strftime("%Y-%m-%d")
    month_key = f"{year}-{month:02d}"
    rules = month_rules.get(month_key, {})
    
    off1 = rules.get("t1_off", [4, 5]) 
    off2 = rules.get("t2_off", [6, 0]) 

    prev_str = (curr_date - timedelta(days=1)).strftime("%Y-%m-%d")
    rest_members = []
    
    if prev_str in records:
        prev_recs = records[prev_str]
        if isinstance(prev_recs, dict): prev_recs = list(prev_recs.values())
        elif isinstance(prev_recs, list): prev_recs = [x for x in prev_recs if x]
        for r in prev_recs:
            if isinstance(r, dict) and r.get('type') == '당직': 
                rest_members.append(r.get('name'))
    
    if date_str in records:
        today_recs = records[date_str]
        if isinstance(today_recs, dict): today_recs = list(today_recs.values())
        elif isinstance(today_recs, list): today_recs = [x for x in today_recs if x]
        for r in today_recs:
            if r.get('type') in ['당직휴무', '휴무']:
                rest_members.append(r.get('name'))

    t1_today = [m for m in t1_list if m not in rest_members]
    t2_today = [m for m in t2_list if m not in rest_members]

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    week_idx = 0
    for idx, week in enumerate(month_days):
        if day in week:
            week_idx = idx
            break
            
    weekday = curr_date.weekday()
    is_t1_off = (weekday in off1)
    is_t2_off = (weekday in off2)
    
    duty_list = []
    if not is_t1_off and not is_t2_off:
        duty_list.extend(t1_today); duty_list.extend(t2_today)
    elif is_t1_off and not is_t2_off:
        duty_list.extend(t2_today)
    elif is_t2_off and not is_t1_off:
        duty_list.extend(t1_today)
        
    return duty_list

# --- 달력 그리기 함수 ---
def draw_calendar(year, month, sch_data, my_filter=None):
    records = normalize_data(sch_data.get("records", {}))
    teams = normalize_data(sch_data.get("teams", {}))
    month_rules = normalize_data(sch_data.get("month_rules", {}))
    
    t1_list = teams.get("1", [])
    t2_list = teams.get("2", [])
    if isinstance(t1_list, str): t1_list = [t1_list]
    if isinstance(t2_list, str): t2_list = [t2_list]

    month_key = f"{year}-{month:02d}"
    rules = month_rules.get(month_key, {})
    start_team = rules.get("start_team", "1")
    time_type = rules.get("time_type", "split")
    rotation_type = rules.get("rotation_type", "fixed")
    base_off1 = rules.get("t1_off", [])
    base_off2 = rules.get("t2_off", [])

    html = '<div class="cal-container"><div class="cal-header-row">'
    days = ['월', '화', '수', '목', '금', '토', '일']
    for d in days: html += f'<div class="cal-header-item">{d}</div>'
    html += '</div><div class="cal-grid">'
    
    cal = calendar.Calendar(firstweekday=0) 
    month_days = cal.monthdayscalendar(year, month)
    
    for r_idx, week in enumerate(month_days):
        if rotation_type == "biweekly" and (r_idx % 2 != 0): curr_off1, curr_off2 = base_off2, base_off1
        elif rotation_type == "two_weeks":
            rot_state = (r_idx // 2) % 2
            if rot_state == 1: curr_off1, curr_off2 = base_off2, base_off1
            else: curr_off1, curr_off2 = base_off1, base_off2
        else: curr_off1, curr_off2 = base_off1, base_off2

        is_even_week = (r_idx % 2 == 0)
        is_t1_first = (start_team == "1") if is_even_week else (start_team == "2")

        for c_idx, day in enumerate(week):
            if day == 0: html += '<div class="cal-cell empty"></div>'; continue
            
            date_str = f"{year}-{month:02d}-{day:02d}"
            today_recs_raw = records.get(date_str, [])
            if isinstance(today_recs_raw, dict): today_recs = list(today_recs.values())
            elif isinstance(today_recs_raw, list): today_recs = [x for x in today_recs_raw if x]
            else: today_recs = []

            off_names = set()
            special_names = set()
            for r in today_recs:
                if r.get('type') in ['당직휴무', '휴무', '팀휴무']: off_names.add(r.get('name'))
                elif r.get('type') == '특별근무': special_names.add(r.get('name'))

            is_t1_rule_work = (c_idx not in curr_off1)
            is_t2_rule_work = (c_idx not in curr_off2)

            t1_today = [m for m in t1_list if (is_t1_rule_work and m not in off_names) or (m in special_names)]
            t2_today = [m for m in t2_list if (is_t2_rule_work and m not in off_names) or (m in special_names)]

            work_html = ""
            team_a_list = t1_today if is_t1_first else t2_today
            team_a_is_rule = is_t1_rule_work if is_t1_first else is_t2_rule_work
            
            if team_a_list:
                if not team_a_is_rule: lbl = "[09-18]"
                elif time_type == "unified": lbl = "[09-18]"
                else: lbl = "[08-17]"
                work_html += f'<div class="work-box wb-a">{lbl} {", ".join(team_a_list)}</div>'

            team_b_list = t2_today if is_t1_first else t1_today
            team_b_is_rule = is_t2_rule_work if is_t1_first else is_t1_rule_work
            
            if team_b_list:
                if not team_b_is_rule: lbl = "[09-18]"
                elif time_type == "unified": lbl = "[09-18]"
                else: lbl = "[11-20]"
                work_html += f'<div class="work-box wb-b">{lbl} {", ".join(team_b_list)}</div>'

            if not team_a_list and not team_b_list: work_html += '<div class="work-box wb-rest">휴무</div>'

            indiv_html = ""
            for evt in today_recs:
                if not isinstance(evt, dict): continue
                if my_filter and my_filter != "전체 보기" and evt.get('name') != my_filter: continue
                e_type, e_name, e_val = evt.get('type',''), evt.get('name',''), evt.get('val','')
                if e_type in ["당직휴무", "휴무", "팀휴무", "특별근무"]: continue 

                bg_c, fg_c = "#eee", "black"
                display_txt = f"{e_name} {e_type}"
                if e_type == "당직": bg_c, fg_c, display_txt = "#D32F2F", "white", f"{e_name} 당직"
                elif e_type == "연차": bg_c, fg_c, display_txt = "#2E7D32", "white", f"{e_name} 연차 {e_val}h" if str(e_val).replace('.','').isdigit() else f"{e_name} 연차"
                elif e_type == "시간외": bg_c, fg_c, display_txt = "#1A237E", "white", f"{e_name} 시간외 {e_val}h" if str(e_val).replace('.','').isdigit() else f"{e_name} 시간외 {e_val}"
                
                indiv_html += f'<div class="badge" style="background-color:{bg_c}; color:{fg_c};">{display_txt}</div>'

            html += f'<div class="cal-cell"><div class="date-num">{day}</div>{work_html}{indiv_html}</div>'
    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)

# --- 메인 탭 구성 ---
st.title("🏕️ 율동공원 관리 시스템")

tab_cal, tab_my, tab_stay, tab_mon, tab_lost, tab_work = st.tabs(["📅 근무", "✍️ 수정", "⛺ 연박", "📊 현황", "🧢 분실", "📷 작업"])

# 1. 근무표 탭 (기존 유지)
with tab_cal:
    if 'curr_date' not in st.session_state: st.session_state.curr_date = datetime.now()
    def change_month(amount):
        curr = st.session_state.curr_date
        new_year = curr.year
        new_month = curr.month + amount
        if new_month > 12: new_month = 1; new_year += 1
        elif new_month < 1: new_month = 12; new_year -= 1
        st.session_state.curr_date = curr.replace(year=new_year, month=new_month, day=1)
    
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

    st.divider()
    with st.expander("🛠️ 날짜별 일정 관리 (삭제 및 휴무)", expanded=False):
        st.caption("🚨 삭제 버튼을 누르면 내용이 일치하는 항목을 찾아 삭제하고 **즉시 저장(Save)**합니다.")
        del_date = st.date_input("관리할 날짜 선택", value=cur)
        del_key = del_date.strftime("%Y-%m-%d")
        fresh_sch = get_data("schedule") or {}
        if "records" not in fresh_sch: fresh_sch["records"] = {}
        all_recs = normalize_data(fresh_sch["records"])
        target_list = all_recs.get(del_key, [])
        if isinstance(target_list, dict): target_list = list(target_list.values())
        elif isinstance(target_list, list): target_list = [x for x in target_list if x]

        st.subheader("1️⃣ 등록된 일정 (삭제)")
        manual_exists = False
        for i, rec in enumerate(target_list):
            if rec.get('type') in ['휴무', '팀휴무', '당직휴무']: continue 
            manual_exists = True
            with st.container(border=True):
                cols = st.columns([4, 1])
                icon = {"당직": "🌙", "연차": "🌴", "시간외": "⏰"}.get(rec['type'], "📝")
                with cols[0]: st.write(f"{icon} **{rec['name']}** {rec['type']} ({rec.get('val', '')})")
                with cols[1]:
                    btn_key = f"del_{del_key}_{rec['name']}_{rec['type']}_{rec.get('val','')}_{i}"
                    if st.button("삭제", key=btn_key, use_container_width=True):
                        latest_recs_raw = get_data(f"schedule/records/{del_key}") or []
                        if isinstance(latest_recs_raw, dict): latest_list = list(latest_recs_raw.values())
                        elif isinstance(latest_recs_raw, list): latest_list = [x for x in latest_recs_raw if x]
                        else: latest_list = []
                        found_idx = -1
                        for idx, item in enumerate(latest_list):
                            if (item.get('name') == rec['name'] and item.get('type') == rec['type'] and str(item.get('val')) == str(rec.get('val'))):
                                found_idx = idx; break
                        if found_idx != -1:
                            del latest_list[found_idx]
                            set_data(f"schedule/records/{del_key}", latest_list)
                            st.toast("삭제 후 저장되었습니다.")
                            st.rerun()
        if not manual_exists: st.caption("등록된 개인 일정이 없습니다.")

        st.divider()
        st.subheader("2️⃣ 자동 생성 근무자 (제외 처리)")
        auto_members = get_auto_duty_members(del_date, fresh_sch)
        if not auto_members: st.caption("이 날은 근무자가 없습니다.")
        else:
            for mem in auto_members:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1: st.write(f"👷 **{mem}** (자동 배정)")
                    with c2:
                        if st.button("제외", key=f"excl_{del_key}_{mem}", use_container_width=True):
                            latest_recs_raw = get_data(f"schedule/records/{del_key}") or []
                            if isinstance(latest_recs_raw, dict): latest_list = list(latest_recs_raw.values())
                            elif isinstance(latest_recs_raw, list): latest_list = [x for x in latest_recs_raw if x]
                            else: latest_list = []
                            latest_list.append({"type": "휴무", "name": mem, "val": "모바일제외"})
                            set_data(f"schedule/records/{del_key}", latest_list)
                            st.toast(f"{mem}님 제외 설정 저장됨."); st.rerun()
        
        excluded_list = [r for r in target_list if r.get('type') == '휴무']
        if excluded_list:
            st.divider(); st.caption("🚫 현재 제외된 근무자")
            for i, rec in enumerate(excluded_list):
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1: st.write(f"❌ **{rec['name']}** (제외됨)")
                    with c2:
                        if st.button("복구", key=f"rest_{del_key}_{i}", use_container_width=True):
                            latest_recs_raw = get_data(f"schedule/records/{del_key}") or []
                            if isinstance(latest_recs_raw, dict): latest_list = list(latest_recs_raw.values())
                            elif isinstance(latest_recs_raw, list): latest_list = [x for x in latest_recs_raw if x]
                            else: latest_list = []
                            found_idx = -1
                            for idx, item in enumerate(latest_list):
                                if item.get('type') == '휴무' and item.get('name') == rec['name']: found_idx = idx; break
                            if found_idx != -1:
                                del latest_list[found_idx]
                                set_data(f"schedule/records/{del_key}", latest_list)
                                st.toast("복구되어 저장되었습니다."); st.rerun()

# 2. 내 수정 탭
with tab_my:
    st.subheader("근무 기록 관리")
    sel_name = st.selectbox("직원 선택", [m for m in members if m != "전체 보기"])
    if sel_name:
        cur_y, cur_m = cur.year, cur.month
        month_prefix = f"{cur_y}-{cur_m:02d}"
        sch_data = get_data("schedule") or {}
        all_recs = normalize_data(sch_data.get("records", {}))
        sum_ot, sum_leave, cnt_night = 0.0, 0.0, 0
        for d_key, evts in all_recs.items():
            if not d_key.startswith(month_prefix): continue
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name:
                    etype = e.get('type')
                    eval_str = str(e.get('val', '0'))
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", eval_str)
                    val = float(nums[0]) if nums else 0.0
                    if etype == '시간외': sum_ot += val
                    elif etype == '연차': sum_leave += val
                    elif etype == '당직': cnt_night += 1
        st.markdown(f"##### 📊 {cur_y}년 {cur_m}월 {sel_name}님 합계")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div style='background:#E3F2FD;padding:10px;border-radius:5px;text-align:center;border:1px solid #90CAF9'><div style='font-size:0.8rem;color:#1565C0'>⏰ 시간외</div><div style='font-size:1.2rem;font-weight:bold;color:#0D47A1'>{sum_ot:g}H</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='background:#E8F5E9;padding:10px;border-radius:5px;text-align:center;border:1px solid #A5D6A7'><div style='font-size:0.8rem;color:#2E7D32'>🌴 연차</div><div style='font-size:1.2rem;font-weight:bold;color:#1B5E20'>{sum_leave:g}H</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='background:#FFEBEE;padding:10px;border-radius:5px;text-align:center;border:1px solid #FFCDD2'><div style='font-size:0.8rem;color:#C62828'>🌙 당직</div><div style='font-size:1.2rem;font-weight:bold;color:#B71C1C'>{cnt_night}회</div></div>", unsafe_allow_html=True)
        st.divider()
        st.write("📝 **새로운 기록 추가**")
        with st.form("new_schedule"):
            c_d, c_t = st.columns(2)
            in_date = c_d.date_input("날짜", value=datetime.now())
            in_type = c_t.selectbox("구분", ["시간외", "당직", "연차"])
            in_val = st.text_input("내용", placeholder="시간(4, 8) 또는 메모")
            if st.form_submit_button("저장하기", type="primary", use_container_width=True):
                d_key = in_date.strftime("%Y-%m-%d")
                day_data_raw = get_data(f"schedule/records/{d_key}") or []
                if isinstance(day_data_raw, dict): day_list = list(day_data_raw.values())
                elif isinstance(day_data_raw, list): day_list = [x for x in day_data_raw if x]
                else: day_list = []
                save_val = in_val
                if in_type == "당직" and not in_val: save_val = "22:00~"
                day_list.append({"name": sel_name, "type": in_type, "val": save_val})
                set_data(f"schedule/records/{d_key}", day_list)
                st.toast("클라우드에 저장되었습니다."); st.rerun()
        st.divider()
        st.write("🗑️ **최근 기록 삭제**")
        my_logs = []
        for d_key, evts in all_recs.items():
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name:
                    temp_e = e.copy(); temp_e['date'] = d_key; my_logs.append(temp_e)
        my_logs.sort(key=lambda x: x['date'], reverse=True)
        if not my_logs: st.info("기록이 없습니다.")
        for i, log in enumerate(my_logs[:10]):
            with st.container(border=True):
                col_info, col_btn = st.columns([4, 1])
                type_icon = {"시간외": "⏰", "당직": "🌙", "연차": "🌴"}.get(log['type'], "📝")
                with col_info: st.write(f"**{log['date']}**"); st.caption(f"{type_icon} {log['type']} | {log['val']}")
                with col_btn:
                    if st.button("삭제", key=f"del_{log['date']}_{i}", use_container_width=True):
                        latest_recs_raw = get_data(f"schedule/records/{log['date']}") or []
                        if isinstance(latest_recs_raw, dict): latest_list = list(latest_recs_raw.values())
                        elif isinstance(latest_recs_raw, list): latest_list = [x for x in latest_recs_raw if x]
                        else: latest_list = []
                        found_idx = -1
                        for idx, item in enumerate(latest_list):
                            if (item.get('name') == sel_name and item.get('type') == log['type'] and str(item.get('val')) == str(log['val'])): found_idx = idx; break
                        if found_idx != -1:
                            del latest_list[found_idx]
                            set_data(f"schedule/records/{log['date']}", latest_list)
                            st.toast("삭제 후 저장 완료."); st.rerun()

# 3. 연박자 보기 탭
with tab_stay:
    st.subheader("⛺ 연박 및 이동 현황")
    stay_data = get_data("stay_result")
    if stay_data:
        updated = stay_data.get("updated_at", "-")
        st.info(f"🕒 업데이트: {updated}")
        items = stay_data.get("list", [])
        if not items: st.success("연박/이동 내역이 없습니다.")
        else:
            for item in items:
                if "방이동" in item or "➡" in item: st.warning(item)
                else: st.info(item)
            st.caption("※ 데이터는 PC 프로그램에서 분석 후 자동 반영됩니다.")
    else: st.warning("데이터가 없습니다. PC 프로그램에서 분석을 실행해주세요.")

# 4. 입실 현황 탭
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
        for z_name in ["A", "B", "C", "D", "E", "F", "기타"]:
            if z_name not in zones: continue
            z_data = zones[z_name]
            blues = z_data.get("blue", [])
            greens = z_data.get("green", [])
            if not blues and not greens: continue
            with st.expander(f"📍 {z_name} 구역 ({len(blues)+len(greens)}건)", expanded=True):
                if blues:
                    for b in blues: st.markdown(f"<div class='stat-card stat-blue'>{b}</div>", unsafe_allow_html=True)
                if greens:
                    for g in greens: st.markdown(f"<div class='stat-card stat-green'>{g}</div>", unsafe_allow_html=True)
    else: st.warning("데이터가 없습니다. PC 프로그램에서 분석을 실행해주세요.")

# 5. 분실물 탭
with tab_lost:
    st.subheader("🧢 분실물 센터")
    raw_lost = get_data("lost_found")
    lost_items = []
    if isinstance(raw_lost, dict): lost_items = list(raw_lost.values())
    elif isinstance(raw_lost, list): lost_items = [x for x in raw_lost if x]
    
    with st.expander("➕ 분실물 등록 (즉시 저장)", expanded=False):
        c1, c2 = st.columns(2)
        l_loc = c1.text_input("장소")
        l_nm = c2.text_input("물건명")
        if st.button("등록", use_container_width=True):
            if l_loc and l_nm:
                latest_raw = get_data("lost_found")
                latest_items = []
                if isinstance(latest_raw, dict): latest_items = list(latest_raw.values())
                elif isinstance(latest_raw, list): latest_items = [x for x in latest_raw if x]
                new_l = {"date": datetime.now().strftime("%Y-%m-%d"), "item": l_nm, "location": l_loc, "status": "보관중", "return_date": "-"}
                latest_items.append(new_l)
                set_data("lost_found", latest_items)
                st.toast("클라우드 저장 완료"); st.rerun()

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
                        latest_raw = get_data("lost_found")
                        latest_items = []
                        if isinstance(latest_raw, dict): latest_items = list(latest_raw.values())
                        elif isinstance(latest_raw, list): latest_items = [x for x in latest_raw if x]
                        found_idx = -1
                        for idx, li in enumerate(latest_items):
                             if (li.get('item') == item['item'] and li.get('date') == item['date'] and li.get('location') == item['location']): found_idx = idx; break
                        if found_idx != -1:
                            latest_items[found_idx]['status'] = "수령완료"
                            latest_items[found_idx]['return_date'] = datetime.now().strftime("%Y-%m-%d")
                            set_data("lost_found", latest_items)
                            st.toast("수령 처리 저장됨"); st.rerun()
                else:
                    if st.button("삭제", key=f"del_{i}"):
                        latest_raw = get_data("lost_found")
                        latest_items = []
                        if isinstance(latest_raw, dict): latest_items = list(latest_raw.values())
                        elif isinstance(latest_raw, list): latest_items = [x for x in latest_raw if x]
                        found_idx = -1
                        for idx, li in enumerate(latest_items):
                             if (li.get('item') == item['item'] and li.get('date') == item['date'] and li.get('location') == item['location']): found_idx = idx; break
                        if found_idx != -1:
                            del latest_items[found_idx]
                            set_data("lost_found", latest_items)
                            st.toast("삭제 저장됨"); st.rerun()

# 6. 작업 일지 (사진 여러장 업로드 & ZIP 다운로드)
with tab_work:
    st.subheader("📸 작업 일지 관리")
    st.caption("사진을 여러 장 선택하면 자동으로 압축되어 저장됩니다.")
    
    # [1] 업로드 섹션
    with st.expander("➕ 사진 및 작업 등록하기", expanded=True):
        # [NEW] accept_multiple_files=True 로 여러 장 선택 가능
        uploaded_files = st.file_uploader("사진 선택 (여러 장 가능)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        work_desc = st.text_input("작업 내용", placeholder="예: A구역 제초작업 완료")
        
        if uploaded_files:
            st.markdown(f"**선택된 사진: {len(uploaded_files)}장**")
            # 미리보기 (작게 나열)
            cols = st.columns(len(uploaded_files))
            for idx, up_file in enumerate(uploaded_files):
                if idx < 5: # 너무 많으면 5개까지만 미리보기
                    cols[idx].image(up_file, width=100)
            
            if st.button("모두 업로드 및 저장", type="primary"):
                if not work_desc:
                    st.warning("작업 내용을 입력해주세요.")
                else:
                    with st.spinner(f"사진 {len(uploaded_files)}장 압축 및 전송 중..."):
                        try:
                            # 1. 스토리지 준비
                            bucket = storage.bucket()
                            uploaded_urls = []
                            today_str_short = datetime.now().strftime('%Y%m%d')
                            
                            # 2. 반복문으로 각 사진 처리
                            for up_file in uploaded_files:
                                # 이미지 압축
                                image = Image.open(up_file)
                                if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                                image.thumbnail((1024, 1024)) # 리사이징
                                
                                img_byte_arr = io.BytesIO()
                                image.save(img_byte_arr, format='JPEG', quality=70) # 용량 최적화
                                img_byte_arr = img_byte_arr.getvalue()
                                
                                # 업로드
                                fname = f"work_logs/{today_str_short}_{uuid.uuid4().hex[:8]}.jpg"
                                blob = bucket.blob(fname)
                                blob.upload_from_string(img_byte_arr, content_type="image/jpeg")
                                blob.make_public()
                                uploaded_urls.append(blob.public_url)
                            
                            # 3. DB 저장 (URL 리스트로 저장)
                            log_entry = {
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "desc": work_desc,
                                "photo_urls": uploaded_urls, # [수정] 리스트로 저장
                                "writer": "관리자"
                            }
                            db.reference('yuldong_data/work_logs').push(log_entry)
                            
                            st.success("✅ 모든 사진이 저장되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류: {e}")

    st.divider()
    
    # [2] 날짜별 조회 및 다운로드 섹션
    st.subheader("📅 날짜별 조회 & 다운로드")
    
    col_date, col_dummy = st.columns([1, 2])
    view_date = col_date.date_input("조회할 날짜", value=datetime.now())
    view_date_str = view_date.strftime("%Y-%m-%d")
    
    # DB에서 전체 로그 가져오기
    raw_logs = get_data("work_logs")
    if raw_logs:
        if isinstance(raw_logs, dict): logs = list(raw_logs.values())
        elif isinstance(raw_logs, list): logs = [x for x in raw_logs if x]
        
        # 선택한 날짜에 해당하는 로그만 필터링
        filtered_logs = [l for l in logs if l.get('date', '').startswith(view_date_str)]
        
        if not filtered_logs:
            st.info(f"{view_date_str}에는 작업 기록이 없습니다.")
        else:
            st.success(f"총 {len(filtered_logs)}건의 작업이 있습니다.")
            
            # [3] 일괄 ZIP 다운로드 버튼 생성
            # 해당 날짜의 모든 사진 URL 수집
            all_urls_for_date = []
            for l in filtered_logs:
                # 구버전(단일 url) 호환
                if 'photo_url' in l: all_urls_for_date.append(l['photo_url'])
                # 신버전(리스트 urls)
                if 'photo_urls' in l and isinstance(l['photo_urls'], list):
                    all_urls_for_date.extend(l['photo_urls'])
            
            if all_urls_for_date:
                if st.button(f"📥 이 날짜 사진 전체 다운로드 (ZIP) - {len(all_urls_for_date)}장", type="secondary"):
                    with st.spinner("사진을 다운로드하여 압축 중입니다..."):
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w") as zf:
                            for idx, url in enumerate(all_urls_for_date):
                                try:
                                    # URL에서 이미지 데이터 다운로드
                                    r = requests.get(url)
                                    if r.status_code == 200:
                                        # ZIP 파일 내 파일명 (date_번호.jpg)
                                        zf.writestr(f"{view_date_str}_{idx+1}.jpg", r.content)
                                except: pass
                        
                        st.download_button(
                            label="📦 압축 파일(ZIP) 저장하기",
                            data=zip_buffer.getvalue(),
                            file_name=f"work_photos_{view_date_str}.zip",
                            mime="application/zip",
                            key="dn_zip"
                        )

            # 로그 리스트 표시
            for log in filtered_logs:
                with st.container(border=True):
                    st.write(f"📝 **{log.get('desc')}**")
                    st.caption(f"{log.get('date')} | {log.get('writer')}")
                    
                    # 사진 표시 로직 (단일/다중 호환)
                    imgs_to_show = []
                    if 'photo_url' in log: imgs_to_show.append(log['photo_url'])
                    if 'photo_urls' in log and isinstance(log['photo_urls'], list):
                        imgs_to_show.extend(log['photo_urls'])
                    
                    if imgs_to_show:
                        # 갤러리 형태로 표시 (한 줄에 3개씩)
                        cols = st.columns(3)
                        for i, url in enumerate(imgs_to_show):
                            cols[i % 3].image(url, use_container_width=True)

    else:
        st.info("등록된 작업 내역이 없습니다.")

