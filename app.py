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
    page_icon="📅", 
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
        system_pass = "1234"
    
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
    .cal-container { display: flex; flex-direction: column; border: 1px solid #ddd; background-color: #fff; }
    
    /* 요일 헤더 */
    .cal-header-row { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #f1f3f5; border-bottom: 1px solid #ddd; }
    .cal-header-item { text-align: center; font-weight: bold; padding: 5px 0; font-size: 0.9rem; color: #333; }
    /* 월요일 시작 기준 색상 (6번째=토, 7번째=일) */
    .cal-header-item:nth-child(6) { color: #1c7ed6; } 
    .cal-header-item:nth-child(7) { color: #e03131; }

    /* 날짜 그리드 */
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); background-color: #e9ecef; gap: 1px; }
    .cal-cell { background-color: #ffffff; min-height: 90px; padding: 2px; display: flex; flex-direction: column; overflow: hidden; }
    .cal-cell.empty { background-color: #f8f9fa; }
    .date-num { font-size: 0.8rem; font-weight: bold; margin-bottom: 2px; padding-left: 2px; color: #333; }
    
    /* 날짜 숫자 색상 */
    .cal-cell:nth-child(7n-1) .date-num { color: #1c7ed6; } /* 토 */
    .cal-cell:nth-child(7n) .date-num { color: #e03131; }   /* 일 */

    .work-box { font-size: 0.65rem; padding: 2px 4px; margin-bottom: 2px; border-radius: 4px; line-height: 1.2; color: #333; font-weight: 500; word-break: keep-all; }
    .wb-a { background-color: #e7f5ff; border: 1px solid #d0ebff; color: #1864ab; }
    .wb-b { background-color: #fff4e6; border: 1px solid #ffe8cc; color: #d9480f; }
    .wb-rest { background-color: #ffe3e3; color: #c92a2a; text-align: center; }
    .badge { font-size: 0.7rem; padding: 2px 4px; border-radius: 3px; margin-top: 1px; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
    .bg-night { background-color: #1E3A8A; } .bg-leave { background-color: #10B981; } .bg-ot { background-color: #EF4444; } .bg-gray { background-color: #868e96; }
    @media (max-width: 600px) { .cal-header-item { font-size: 0.75rem; padding: 3px 0; } .cal-cell { min-height: 70px; padding: 1px; } .date-num { font-size: 0.7rem; } .work-box { font-size: 0.6rem; padding: 1px 2px; border-radius: 2px; } .badge { font-size: 0.6rem; padding: 1px 2px; border-radius: 2px; } }
</style>
""", unsafe_allow_html=True)

# --- Firebase 초기화 (오류 수정됨) ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(CURRENT_DIR, CRED_FILENAME)

@st.cache_resource
def init_firebase():
    if firebase_admin._apps: return True
    
    # 1. Cloud Secrets
    if "firebase_key" in st.secrets:
        try:
            # AttrDict 오류 방지를 위해 dict()로 강제 변환
            cred_info = dict(st.secrets["firebase_key"])
            
            # 줄바꿈 문자 보정
            if "private_key" in cred_info:
                cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")

            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
            return True
        except Exception as e:
            st.error(f"Cloud 인증 오류: {e}")
            return False

    # 2. Local File
    if os.path.exists(CRED_PATH):
        try:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
            return True
        except Exception as e:
            st.error(f"로컬 인증 오류: {e}")
            return False
            
    st.warning("⚠️ 인증 파일을 찾을 수 없습니다.")
    uploaded = st.file_uploader("키 파일 업로드", type="json")
    if uploaded:
        cred = credentials.Certificate(json.load(uploaded))
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
        st.rerun()
        return True
    return False

if not init_firebase(): st.stop()

# --- DB 헬퍼 ---
def get_data(path): return db.reference(f'yuldong_data/{path}').get()
def set_data(path, data): db.reference(f'yuldong_data/{path}').set(data)

# --- [핵심] 데이터 안전 추출 함수 (List/Dict 오류 해결) ---
def get_safe_list(data, key_index):
    """
    Firebase에서 데이터가 List로 오든 Dict로 오든
    안전하게 특정 조(1조, 2조)의 명단을 리스트로 반환
    key_index: 문자열 "1" 또는 정수 1
    """
    if not data:
        return []
        
    # 1. 리스트로 온 경우 (Firebase가 숫자를 인덱스로 인식)
    if isinstance(data, list):
        try:
            idx = int(key_index)
            if idx < len(data) and data[idx] is not None:
                return data[idx]
        except:
            return []
            
    # 2. 딕셔너리로 온 경우
    elif isinstance(data, dict):
        return data.get(str(key_index), [])
        
    return []

def normalize_records(data):
    """Records 데이터도 리스트/딕셔너리 안전 변환"""
    if isinstance(data, list):
        # 리스트라면 인덱스는 무시하고 값들만 모아서 날짜별로 매핑이 어려우므로
        # 보통 records는 날짜(string) 키라서 dict로 오지만, 방어코드 작성
        return {} # 리스트로 오면 날짜 매핑이 깨진 것
    return data if data else {}

# --- 달력 그리기 ---
def draw_calendar(year, month, sch_data, my_filter=None):
    records = normalize_records(sch_data.get("records", {}))
    teams_raw = sch_data.get("teams", {})
    
    # [수정] 안전하게 팀원 명단 가져오기
    t1_list = get_safe_list(teams_raw, 1)
    t2_list = get_safe_list(teams_raw, 2)
    
    # 혹시 문자열 하나로 되어있으면 리스트로 변환
    if isinstance(t1_list, str): t1_list = [t1_list]
    if isinstance(t2_list, str): t2_list = [t2_list]

    # 근무 규칙
    month_rules = sch_data.get("month_rules", {})
    if isinstance(month_rules, list): month_rules = {} # 방어코드
    
    month_key = f"{year}-{month:02d}"
    rules = month_rules.get(month_key, {})
    start_team = rules.get("start_team", "1")
    off1 = rules.get("t1_off", [4, 5]) 
    off2 = rules.get("t2_off", [6, 0]) 
    
    # 1. 요일 헤더 (월요일 시작)
    html = '<div class="cal-container"><div class="cal-header-row">'
    days = ['월', '화', '수', '목', '금', '토', '일']
    for d in days:
        html += f'<div class="cal-header-item">{d}</div>'
    html += '</div><div class="cal-grid">'
    
    # 2. 달력 데이터 (0=월요일 시작)
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    for r_idx, week in enumerate(month_days):
        for c_idx, day in enumerate(week):
            if day == 0:
                html += '<div class="cal-cell empty"></div>'
                continue
            
            curr_date = datetime(year, month, day)
            prev_str = (curr_date - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 전날 당직자 확인
            rest_members = []
            if prev_str in records:
                prev_recs = records[prev_str]
                if isinstance(prev_recs, dict): prev_recs = list(prev_recs.values())
                elif isinstance(prev_recs, list): prev_recs = [x for x in prev_recs if x]
                
                for r in prev_recs:
                    if isinstance(r, dict) and r.get('type') == '당직': 
                        rest_members.append(r.get('name'))
            
            # 근무 제외 처리
            t1_today = [m for m in t1_list if m not in rest_members]
            t2_today = [m for m in t2_list if m not in rest_members]
            t1_str, t2_str = ", ".join(t1_today), ", ".join(t2_today)
            
            work_html = ""
            # calendar 모듈: 월=0 ~ 일=6
            weekday = c_idx 
            is_t1_off, is_t2_off = (weekday in off1), (weekday in off2)
            
            if not is_t1_off and not is_t2_off:
                is_even_week = (r_idx % 2 == 0)
                if start_team == "1": duty_a, duty_b = (t1_str, t2_str) if is_even_week else (t2_str, t1_str)
                else: duty_a, duty_b = (t2_str, t1_str) if is_even_week else (t1_str, t2_str)
                
                if duty_a: work_html += f'<div class="work-box wb-a"><b>08-17</b><br>{duty_a}</div>'
                if duty_b: work_html += f'<div class="work-box wb-b"><b>11-20</b><br>{duty_b}</div>'
            elif is_t1_off and not is_t2_off:
                if t2_str: work_html += f'<div class="work-box wb-b"><b>09-18</b><br>{t2_str}</div>'
            elif is_t2_off and not is_t1_off:
                if t1_str: work_html += f'<div class="work-box wb-a"><b>09-18</b><br>{t1_str}</div>'
            else:
                work_html += '<div class="work-box wb-rest">전체 휴무</div>'

            # 개인 일정
            d_str = f"{year}-{month:02d}-{day:02d}"
            indiv_html = ""
            if d_str in records:
                day_recs = records[d_str]
                if isinstance(day_recs, dict): day_recs = list(day_recs.values())
                elif isinstance(day_recs, list): day_recs = [x for x in day_recs if x]
                
                for evt in day_recs:
                    if not isinstance(evt, dict): continue
                    if my_filter and my_filter != "전체 보기" and evt.get('name') != my_filter: continue
                    
                    e_type, e_name, e_val = evt.get('type',''), evt.get('name',''), evt.get('val','')
                    cls, txt = "bg-gray", ""
                    if e_type == "당직": cls, txt = "bg-night", f"{e_name} 당직"
                    elif e_type == "연차": cls, txt = "bg-leave", f"{e_name} 연차"
                    elif e_type == "시간외": cls, txt = "bg-ot", (f"{e_name} {e_val} 시간외" if e_val else f"{e_name} 시간외")
                    else: txt = f"{e_name} {e_type}"
                    indiv_html += f'<div class="badge {cls}">{txt}</div>'

            html += f'<div class="cal-cell"><div class="date-num">{day}</div>{work_html}{indiv_html}</div>'
            
    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)

# --- 메인 화면 ---
st.title("🏕️ 율동공원 모바일")
if st.sidebar.button("로그아웃"):
    st.session_state.logged_in = False
    st.rerun()

tab_cal, tab_my, tab_lost = st.tabs(["📅 근무표", "✍️ 내 수정", "🧢 분실물"])

# 1. 달력 탭
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
    teams_raw = sch_data.get("teams", {})
    
    # 안전하게 명단 가져오기
    t1 = get_safe_list(teams_raw, 1)
    t2 = get_safe_list(teams_raw, 2)
    
    members = ["전체 보기"] + t1 + t2
    my_filter = st.selectbox("표시 대상", members)
    
    draw_calendar(cur.year, cur.month, sch_data, my_filter)
    st.caption("※ 전날 당직자는 근무 명단에서 자동 제외됩니다.")

# 2. 내 수정 탭
with tab_my:
    st.subheader("내 근무 기록 관리")
    sel_name = st.selectbox("이름 선택", [m for m in members if m != "전체 보기"])
    if sel_name:
        with st.form("new_schedule"):
            c_d, c_t = st.columns(2)
            in_date = c_d.date_input("날짜")
            in_type = c_t.selectbox("구분", ["시간외", "당직", "연차"])
            in_val = st.text_input("내용", placeholder="시간(4, 8) 또는 메모")
            if st.form_submit_button("저장", type="primary", use_container_width=True):
                d_key = in_date.strftime("%Y-%m-%d")
                fresh_sch = get_data("schedule") or {}
                if "records" not in fresh_sch: fresh_sch["records"] = {}
                records = normalize_records(fresh_sch["records"])
                
                day_list = records.get(d_key, [])
                if isinstance(day_list, dict): day_list = list(day_list.values())
                elif isinstance(day_list, list): day_list = [x for x in day_list if x]
                
                save_val = in_val
                if in_type == "당직" and not in_val: save_val = "22:00~"
                day_list.append({"name": sel_name, "type": in_type, "val": save_val})
                records[d_key] = day_list
                fresh_sch["records"] = records
                set_data("schedule", fresh_sch)
                st.success("저장 완료!")
                st.rerun()
        st.divider()
        st.write("🗑️ **최근 기록 삭제**")
        my_logs = []
        records = normalize_records(sch_data.get("records", {}))
        for d, evts in records.items():
            if isinstance(evts, dict): evts = list(evts.values())
            elif isinstance(evts, list): evts = [x for x in evts if x]
            for e in evts:
                if isinstance(e, dict) and e.get('name') == sel_name:
                    e['date'] = d
                    my_logs.append(e)
        my_logs.sort(key=lambda x: x['date'], reverse=True)
        if not my_logs: st.info("기록이 없습니다.")
        for log in my_logs[:5]:
            with st.container(border=True):
                col_info, col_btn = st.columns([4, 1])
                d_txt = ""
                if log['type'] == "시간외": d_txt = f"{log['name']} {log['val']} 시간외"
                else: d_txt = f"{log['name']} {log['type']}"
                col_info.text(f"{log['date']} | {d_txt}")
                if col_btn.button("삭제", key=f"del_{log['date']}_{log['type']}_{log['val']}"):
                    f_data = get_data("schedule")
                    recs = normalize_records(f_data.get("records", {}))
                    tgt_list = recs.get(log['date'], [])
                    if isinstance(tgt_list, dict): tgt_list = list(tgt_list.values())
                    elif isinstance(tgt_list, list): tgt_list = [x for x in tgt_list if x]
                    new_list = [r for r in tgt_list if not (r.get('name')==sel_name and r.get('type')==log['type'] and str(r.get('val'))==str(log['val']))]
                    recs[log['date']] = new_list
                    f_data["records"] = recs
                    set_data("schedule", f_data)
                    st.rerun()

# 3. 분실물 탭
with tab_lost:
    st.subheader("🧢 분실물 센터")
    raw_lost = get_data("lost_found")
    lost_items = []
    if isinstance(raw_lost, dict): lost_items = list(raw_lost.values())
    elif isinstance(raw_lost, list): lost_items = [x for x in raw_lost if x]
    
    with st.expander("➕ 분실물 등록하기", expanded=False):
        l_loc = st.text_input("장소")
        l_nm = st.text_input("물건명")
        if st.button("등록하기", type="primary", use_container_width=True):
            if l_loc and l_nm:
                new_l = {"date": datetime.now().strftime("%Y-%m-%d"), "item": l_nm, "location": l_loc, "status": "보관중", "return_date": "-"}
                lost_items.append(new_l)
                set_data("lost_found", lost_items)
                st.rerun()
    st.markdown(f"**보관중인 물품: {len([x for x in lost_items if x.get('status')=='보관중'])}개**")
    for i, item in reversed(list(enumerate(lost_items))):
        is_kept = (item.get('status') == "보관중")
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                icon = "🟢" if is_kept else "⚪"
                st.write(f"**{icon} {item.get('item')}**")
                st.caption(f"📍{item.get('location')} | 📅{item.get('date')}")
                if not is_kept: st.caption(f"수령일: {item.get('return_date')}")
            with c2:
                if is_kept:
                    if st.button("수령", key=f"r_{i}"):
                        lost_items[i]['status'] = "수령완료"
                        lost_items[i]['return_date'] = datetime.now().strftime("%Y-%m-%d")
                        set_data("lost_found", lost_items)
                        st.rerun()
                if st.button("삭제", key=f"d_{i}"):
                    del lost_items[i]
                    set_data("lost_found", lost_items)
                    st.rerun()
