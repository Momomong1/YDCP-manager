import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import calendar
import os
import json
import re

# --- 기본 설정 ---
CRED_FILENAME = "service.json"
FIREBASE_DB_URL = 'https://ydcpmanager-default-rtdb.firebaseio.com/'

st.set_page_config(
    page_title="율동공원 관리", 
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
    
    /* 캘린더 컨테이너 */
    .cal-container { 
        display: flex; 
        flex-direction: column; 
        border: 1px solid #ddd; 
        background-color: #fff; 
        border-radius: 8px; /* 둥근 모서리 추가 */
        overflow: hidden; 
    }
    
    /* 요일 헤더 */
    .cal-header-row { 
        display: grid; 
        grid-template-columns: repeat(7, 1fr); 
        background-color: #f8f9fa; 
        border-bottom: 1px solid #ddd; 
    }
    .cal-header-item { 
        text-align: center; 
        font-weight: bold; 
        padding: 8px 0; 
        font-size: 0.9rem; 
        color: #495057; 
    }
    .cal-header-item:nth-child(6) { color: #1c7ed6; }
    .cal-header-item:nth-child(7) { color: #e03131; }
    
    /* 날짜 그리드 */
    .cal-grid { 
        display: grid; 
        grid-template-columns: repeat(7, 1fr); 
        background-color: #dee2e6; /* 그리드 선 색상 */
        gap: 1px; 
    }
    
    /* 개별 날짜 셀 (핵심 수정) */
    .cal-cell { 
        background-color: #ffffff; 
        min-height: 60px; /* 기본 높이 줄임 */
        height: auto;     /* 내용에 따라 늘어남 */
        padding: 4px 2px; 
        display: flex; 
        flex-direction: column; 
        gap: 2px;         /* 항목 간 간격 */
    }
    .cal-cell.empty { background-color: #f8f9fa; min-height: 60px; }
    
    /* 날짜 숫자 */
    .date-num { 
        font-size: 0.8rem; 
        font-weight: bold; 
        margin-bottom: 2px; 
        padding-left: 4px; 
        color: #333; 
    }
    .cal-cell:nth-child(7n-1) .date-num { color: #1c7ed6; }
    .cal-cell:nth-child(7n) .date-num { color: #e03131; }

    /* 근무 조 박스 */
    .work-box { 
        font-size: 0.75rem; 
        padding: 3px 4px; 
        border-radius: 4px; 
        line-height: 1.3; 
        color: #333; 
        font-weight: 500; 
        word-break: keep-all; /* 단어 단위 줄바꿈 */
        white-space: normal;  /* 줄바꿈 허용 */
    }
    .wb-a { background-color: #e7f5ff; border: 1px solid #d0ebff; color: #1864ab; }
    .wb-b { background-color: #fff4e6; border: 1px solid #ffe8cc; color: #d9480f; }
    .wb-rest { background-color: #ffe3e3; color: #c92a2a; text-align: center; }
    
    /* 개인 일정 뱃지 */
    .badge { 
        font-size: 0.7rem; 
        padding: 3px 4px; 
        border-radius: 4px; 
        margin-top: 1px; 
        color: white; 
        display: block; 
        white-space: normal; /* 줄바꿈 허용 */
        line-height: 1.2;
    }
    .bg-night { background-color: #D32F2F; } 
    .bg-leave { background-color: #2E7D32; } 
    .bg-ot { background-color: #1A237E; }    
    .bg-gray { background-color: #868e96; }
    
    /* 모바일 반응형 (더 작게 최적화) */
    @media (max-width: 600px) { 
        .cal-header-item { font-size: 0.7rem; padding: 4px 0; } 
        .cal-cell { min-height: 50px; padding: 2px; } 
        .date-num { font-size: 0.7rem; margin-bottom: 1px; } 
        .work-box { font-size: 0.65rem; padding: 2px 3px; letter-spacing: -0.5px; } 
        .badge { font-size: 0.65rem; padding: 2px 3px; letter-spacing: -0.5px; } 
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
    rules = month_rules.get(month_key, {})
    start_team = rules.get("start_team", "1")
    off1 = rules.get("t1_off", [4, 5]) 
    off2 = rules.get("t2_off", [6, 0]) 
    
    html = '<div class="cal-container"><div class="cal-header-row">'
    days = ['월', '화', '수', '목', '금', '토', '일']
    for d in days: html += f'<div class="cal-header-item">{d}</div>'
    html += '</div><div class="cal-grid">'
    
    cal = calendar.Calendar(firstweekday=0) 
    month_days = cal.monthdayscalendar(year, month)
    
    for r_idx, week in enumerate(month_days):
        for c_idx, day in enumerate(week):
            if day == 0:
                html += '<div class="cal-cell empty"></div>'
                continue
            
            curr_date = datetime(year, month, day)
            date_str = f"{year}-{month:02d}-{day:02d}"
            
            # --- 휴무자 제외 로직 ---
            # 1. 어제 당직자
            prev_str = (curr_date - timedelta(days=1)).strftime("%Y-%m-%d")
            rest_members = []
            
            if prev_str in records:
                prev_recs = records[prev_str]
                if isinstance(prev_recs, dict): prev_recs = list(prev_recs.values())
                elif isinstance(prev_recs, list): prev_recs = [x for x in prev_recs if x]
                for r in prev_recs:
                    if isinstance(r, dict) and r.get('type') == '당직': 
                        rest_members.append(r.get('name'))
            
            # 2. 오늘 '당직휴무' 또는 '휴무' 기록자
            if date_str in records:
                today_recs = records[date_str]
                if isinstance(today_recs, dict): today_recs = list(today_recs.values())
                elif isinstance(today_recs, list): today_recs = [x for x in today_recs if x]
                for r in today_recs:
                    if r.get('type') in ['당직휴무', '휴무']:
                        rest_members.append(r.get('name'))

            t1_today = [m for m in t1_list if m not in rest_members]
            t2_today = [m for m in t2_list if m not in rest_members]
            t1_str, t2_str = ", ".join(t1_today), ", ".join(t2_today)
            
            # --- 근무 박스 ---
            work_html = ""
            weekday = curr_date.weekday() 
            is_t1_off, is_t2_off = (weekday in off1), (weekday in off2)
            
            if not is_t1_off and not is_t2_off:
                is_even_week = (r_idx % 2 == 0)
                if start_team == "1": duty_a, duty_b = (t1_str, t2_str) if is_even_week else (t2_str, t1_str)
                else: duty_a, duty_b = (t2_str, t1_str) if is_even_week else (t1_str, t2_str)
                if duty_a: work_html += f'<div class="work-box wb-a">A {duty_a}</div>'
                if duty_b: work_html += f'<div class="work-box wb-b">B {duty_b}</div>'
            elif is_t1_off and not is_t2_off:
                if t2_str: work_html += f'<div class="work-box wb-b">통합 {t2_str}</div>'
            elif is_t2_off and not is_t1_off:
                if t1_str: work_html += f'<div class="work-box wb-a">통합 {t1_str}</div>'
            else:
                work_html += '<div class="work-box wb-rest">휴무</div>'

            # --- 개인 일정 뱃지 ---
            indiv_html = ""
            if date_str in records:
                day_recs = records[date_str]
                if isinstance(day_recs, dict): day_recs = list(day_recs.values())
                elif isinstance(day_recs, list): day_recs = [x for x in day_recs if x]
                for evt in day_recs:
                    if not isinstance(evt, dict): continue
                    if my_filter and my_filter != "전체 보기" and evt.get('name') != my_filter: continue
                    e_type, e_name, e_val = evt.get('type',''), evt.get('name',''), evt.get('val','')
                    
                    if e_type in ["당직휴무", "휴무", "팀휴무"]: continue # 표시 안 함

                    cls, txt = "bg-gray", ""
                    if e_type == "당직": cls, txt = "bg-night", f"🌙{e_name}"
                    elif e_type == "연차": cls, txt = "bg-leave", f"🌴{e_name}"
                    elif e_type == "시간외": cls, txt = "bg-ot", f"{e_name} {e_val if e_val else ''}"
                    else: txt = f"{e_name} {e_type}"
                    
                    indiv_html += f'<div class="badge {cls}">{txt}</div>'

            html += f'<div class="cal-cell"><div class="date-num">{day}</div>{work_html}{indiv_html}</div>'
    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)

# --- 메인 탭 구성 ---
st.title("🏕️ 율동공원 관리 시스템")
if st.sidebar.button("로그아웃"):
    st.session_state.logged_in = False
    st.rerun()

# 탭 5개
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

    # -------------------------------------------------------------
    # [추가된 기능] 날짜별 일정 삭제 기능
    # -------------------------------------------------------------
    st.divider()
    with st.expander("🛠️ 날짜별 일정 관리 (삭제)", expanded=False):
        st.caption("달력에서 날짜를 확인하고, 삭제할 날짜를 선택하세요.")
        
        # 날짜 선택
        del_date = st.date_input("관리할 날짜 선택", value=cur)
        del_key = del_date.strftime("%Y-%m-%d")
        
        # 해당 날짜 데이터 가져오기
        all_recs = normalize_data(sch_data.get("records", {}))
        target_list = all_recs.get(del_key, [])
        if isinstance(target_list, dict): target_list = list(target_list.values())
        elif isinstance(target_list, list): target_list = [x for x in target_list if x]
        
        if not target_list:
            st.info(f"{del_key}에는 등록된 일정이 없습니다.")
        else:
            st.write(f"**{del_key} 등록된 일정**")
            for i, rec in enumerate(target_list):
                with st.container(border=True):
                    cols = st.columns([4, 1])
                    # 아이콘
                    icon = "📝"
                    if rec['type'] == '당직': icon = "🌙"
                    elif rec['type'] == '연차': icon = "🌴"
                    elif rec['type'] == '시간외': icon = "⏰"
                    
                    with cols[0]:
                        st.write(f"{icon} **{rec['name']}** - {rec['type']} ({rec.get('val', '')})")
                    
                    with cols[1]:
                        # 삭제 버튼 (고유 키 사용)
                        if st.button("삭제", key=f"del_cal_{del_key}_{i}", use_container_width=True):
                            # 삭제 로직
                            del target_list[i]
                            all_recs[del_key] = target_list
                            sch_data["records"] = all_recs
                            set_data("schedule", sch_data)
                            st.success("삭제되었습니다!")
                            st.rerun()

# 2. 내 수정 탭
with tab_my:
    st.subheader("근무 기록 관리")
    
    # 1. 대상자 선택
    sel_name = st.selectbox("직원 선택", [m for m in members if m != "전체 보기"])
    
    if sel_name:
        # --- [NEW] 이번 달 합계 통계 표시 ---
        cur_y, cur_m = cur.year, cur.month # 현재 보고 있는 달력 기준
        month_prefix = f"{cur_y}-{cur_m:02d}"
        
        # 전체 데이터 가져오기
        sch_data = get_data("schedule") or {}
        all_recs = normalize_data(sch_data.get("records", {}))
        
        # 합계 계산
        sum_ot = 0.0   # 시간외
        sum_leave = 0.0 # 연차
        cnt_night = 0   # 당직 횟수
        
        for d_key, evts in all_recs.items():
            # 해당 월의 데이터만 필터링
            if not d_key.startswith(month_prefix): continue
            
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name:
                    etype = e.get('type')
                    eval_str = str(e.get('val', '0'))
                    
                    # 숫자 추출 (정규식)
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", eval_str)
                    val = float(nums[0]) if nums else 0.0
                    
                    if etype == '시간외': sum_ot += val
                    elif etype == '연차': sum_leave += val
                    elif etype == '당직': cnt_night += 1

        # 통계 카드 출력 (색상 박스)
        st.markdown(f"##### 📊 {cur_y}년 {cur_m}월 {sel_name}님 합계")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div style='background:#E3F2FD;padding:10px;border-radius:5px;text-align:center;border:1px solid #90CAF9'>"
                    f"<div style='font-size:0.8rem;color:#1565C0'>⏰ 시간외</div>"
                    f"<div style='font-size:1.2rem;font-weight:bold;color:#0D47A1'>{sum_ot:g}H</div></div>", unsafe_allow_html=True)
        
        c2.markdown(f"<div style='background:#E8F5E9;padding:10px;border-radius:5px;text-align:center;border:1px solid #A5D6A7'>"
                    f"<div style='font-size:0.8rem;color:#2E7D32'>🌴 연차</div>"
                    f"<div style='font-size:1.2rem;font-weight:bold;color:#1B5E20'>{sum_leave:g}H</div></div>", unsafe_allow_html=True)
        
        c3.markdown(f"<div style='background:#FFEBEE;padding:10px;border-radius:5px;text-align:center;border:1px solid #FFCDD2'>"
                    f"<div style='font-size:0.8rem;color:#C62828'>🌙 당직</div>"
                    f"<div style='font-size:1.2rem;font-weight:bold;color:#B71C1C'>{cnt_night}회</div></div>", unsafe_allow_html=True)
        
        st.divider()

        # --- [기존] 기록 추가 폼 ---
        st.write("📝 **새로운 기록 추가**")
        with st.form("new_schedule"):
            c_d, c_t = st.columns(2)
            in_date = c_d.date_input("날짜", value=datetime.now())
            in_type = c_t.selectbox("구분", ["시간외", "당직", "연차"])
            in_val = st.text_input("내용", placeholder="시간(4, 8) 또는 메모")
            
            if st.form_submit_button("저장하기", type="primary", use_container_width=True):
                d_key = in_date.strftime("%Y-%m-%d")
                
                # 데이터 갱신을 위해 다시 로드 (동시성)
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
                st.success("저장되었습니다.")
                st.rerun()

        # --- [기존] 기록 삭제 리스트 ---
        st.divider()
        st.write("🗑️ **최근 기록 삭제**")
        
        # 내 기록 필터링
        my_logs = []
        for d_key, evts in all_recs.items():
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
                        # 삭제를 위해 최신 데이터 다시 로드
                        fresh_sch = get_data("schedule") or {}
                        fresh_recs = normalize_data(fresh_sch.get("records", {}))
                        target_day_list = fresh_recs.get(log['date'], [])
                        
                        if isinstance(target_day_list, dict): target_day_list = list(target_day_list.values())
                        elif isinstance(target_day_list, list): target_day_list = [x for x in target_day_list if x]
                        
                        new_day_list = []
                        deleted = False
                        for item in target_day_list:
                            # 동일한 항목 하나만 삭제
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

# 3. 연박자 보기 탭
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
                if "방이동" in item or "➡" in item:
                    st.warning(item)
                else:
                    st.info(item)
            st.caption("※ 데이터는 PC 프로그램에서 분석 후 자동 반영됩니다.")
    else:
        st.warning("데이터가 없습니다. PC 프로그램에서 분석을 실행해주세요.")

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
                    for b in blues:
                        st.markdown(f"<div class='stat-card stat-blue'>{b}</div>", unsafe_allow_html=True)
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





