import streamlit as st
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# 페이지 설정 - 아이콘과 제목 설정
st.set_page_config(
    page_title="과정중심평가 입력기",  # 브라우저 탭에 표시될 제목
    page_icon="📝",  # 브라우저 탭에 표시될 아이콘 (이모지 또는 이미지 파일 경로)
)

# Streamlit의 기본 메뉴와 푸터 숨기기
hide_menu_style = """
    <style>
    #MainMenu {visibility: hidden; }
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_menu_style, unsafe_allow_html=True)

# OpenAI API 클라이언트 초기화
client = openai.OpenAI(api_key=st.secrets["api"]["keys"][0])

# Google Sheets 인증 설정
credentials_dict = json.loads(st.secrets["gcp"]["credentials"])
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
])
gc = gspread.authorize(credentials)

# 스프레드시트 열기
spreadsheet = gc.open(st.secrets["google"]["spreadsheet_name"])
worksheet = spreadsheet.sheet1

# 성취기준 데이터 로드
try:
    with open("achievement_standards_all.json", "r", encoding="utf-8") as f:
        achievement_standards = json.load(f)
except FileNotFoundError:
    st.error("성취기준 데이터 파일을 찾을 수 없습니다.")
except json.JSONDecodeError:
    st.error("성취기준 데이터 파일을 읽는 중 오류가 발생했습니다.")

# 페이지에 제목 표시
st.title("평가 문제 입력기")

# 세션 상태 초기화
if "step" not in st.session_state:
    st.session_state.step = 0
if "questions" not in st.session_state:
    st.session_state.questions = ["", "", ""]
if "activity_code" not in st.session_state:
    st.session_state.activity_code = ""
if "ai_generated_question" not in st.session_state:
    st.session_state.ai_generated_question = ""
if "ai_used" not in st.session_state:
    st.session_state.ai_used = False
if "selections" not in st.session_state:
    st.session_state.selections = {"grade": "", "subject": "", "category": "", "standard": ""}

# 에러 메시지 출력 함수
def display_error(message):
    st.error(f"⚠️ {message}")

# 단계 이동 함수
def go_to_next_step(current_step, selected_option, option_key, next_step):
    if selected_option:
        st.session_state.selections[option_key] = selected_option
        st.session_state.step = next_step
        st.rerun()

def go_to_previous_step(previous_step, option_key):
    st.session_state.selections[option_key] = ""
    st.session_state.step = previous_step
    st.rerun()

# 문제 입력 방법 선택
input_method = st.radio(
    "문제 입력 방법을 선택하세요:",
    ("직접 입력", "인공지능 도움 받기")
)

# 선택된 입력 방법에 따른 UI 표시
if input_method == "직접 입력":
    st.subheader("📄 직접 문제 입력")
    for i in range(1, 4):
        st.session_state.questions[i-1] = st.text_area(f"문제 {i} 입력", value=st.session_state.questions[i-1], height=100)
        st.session_state[f"image{i}_url"] = st.text_input(f"문제 {i} 관련 이미지 URL (선택사항)", "")

elif input_method == "인공지능 도움 받기":
    st.subheader("📄 인공지능으로 문제 생성")

    # 현재 선택 상태를 네비게이션처럼 표시
    st.write("### 현재 선택 사항")
    st.write(f"**학년**: {st.session_state.selections['grade']}")
    st.write(f"**과목**: {st.session_state.selections['subject']}")
    st.write(f"**카테고리**: {st.session_state.selections['category']}")
    st.write(f"**성취기준**: {st.session_state.selections['standard']}")

    if st.session_state.step == 0:
        grade = st.selectbox("학년 선택", list(achievement_standards.keys()))
        if st.button("다음 단계", key="next_step_0"):
            go_to_next_step(st.session_state.step, grade, 'grade', 1)

    if st.session_state.step == 1:
        subject = st.selectbox("과목 선택", list(achievement_standards[st.session_state.selections['grade']].keys()))
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("이전 단계", key="prev_step_1"):
                go_to_previous_step(0, 'grade')
        with col2:
            if st.button("다음 단계", key="next_step_1"):
                go_to_next_step(st.session_state.step, subject, 'subject', 2)

    if st.session_state.step == 2:
        category = st.selectbox("카테고리 선택", list(achievement_standards[st.session_state.selections['grade']][st.session_state.selections['subject']].keys()))
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("이전 단계", key="prev_step_2"):
                go_to_previous_step(1, 'subject')
        with col2:
            if st.button("다음 단계", key="next_step_2"):
                go_to_next_step(st.session_state.step, category, 'category', 3)

    if st.session_state.step == 3:
        standard = st.selectbox("성취기준 선택", achievement_standards[st.session_state.selections['grade']][st.session_state.selections['subject']][st.session_state.selections['category']])
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("이전 단계", key="prev_step_3"):
                go_to_previous_step(2, 'category')
        with col2:
            if st.button("문제 생성", key="generate_question"):
                if standard:
                    st.session_state.selections['standard'] = standard
                    st.session_state.step = 4  # 문제 생성 완료 단계로 이동
                    with st.spinner("인공지능이 문제를 생성 중입니다..."):
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",  # 적절한 GPT 모델을 선택
                                messages=[
                                    {"role": "system", "content": "당신은 교육용 문제를 생성하는 AI입니다."},
                                    {"role": "user", "content": f"성취기준: {standard}. 이 성취기준에 맞는 문제를 딱 1개만 생성해 주세요."}
                                ]
                            )

                            if response.choices and response.choices[0].message.content:
                                st.session_state.ai_generated_question = response.choices[0].message.content.strip()
                                st.session_state.ai_used = False
                            else:
                                display_error("문제 생성에 실패했습니다. 다시 시도해 주세요.")
                                st.session_state.ai_generated_question = ""

                        except Exception as e:
                            display_error(f"문제 생성 중 오류가 발생했습니다: {e}")
                            st.session_state.ai_generated_question = ""

    if st.session_state.step == 4 and st.session_state.ai_generated_question:
        st.write("### 생성된 문제:")
        st.write(st.session_state.ai_generated_question)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("이 문제를 1번 문제로 사용", key="use_in_1"):
                st.session_state.questions[0] = st.session_state.ai_generated_question
                st.session_state.ai_used = True
        with col2:
            if st.button("이 문제를 2번 문제로 사용", key="use_in_2"):
                st.session_state.questions[1] = st.session_state.ai_generated_question
                st.session_state.ai_used = True
        with col3:
            if st.button("이 문제를 3번 문제로 사용", key="use_in_3"):
                st.session_state.questions[2] = st.session_state.ai_generated_question
                st.session_state.ai_used = True

        if st.session_state.ai_used:
            st.session_state.step = 3  # 다시 문제 생성 단계로 이동
            st.session_state.ai_generated_question = ""  # 새로운 문제 생성을 위해 초기화
            st.rerun()  # 새로 고침하여 문제가 사라지지 않도록 함

    # 문제 및 이미지 URL 입력 - 항상 표시되도록 유지
    st.subheader("📄 문제 입력")
    for i in range(1, 4):
        st.text_area(f"문제 {i} 입력", value=st.session_state.questions[i-1], height=100)
        st.text_input(f"문제 {i} 관련 이미지 URL (선택사항)", st.session_state.get(f"image{i}_url", ""))

# 활동 코드 입력 및 문제 저장
if input_method:
    st.subheader("🔑 활동 코드 설정 및 저장")
    st.session_state.activity_code = st.text_input("활동 코드를 입력하세요", value=st.session_state.activity_code).strip()
    teacher_email = st.text_input("교사 이메일 입력", help="학생이 답변을 제출하면 이 이메일로 결과가 전송됩니다.")

    if st.button("💾 문제 저장"):
        if not all(st.session_state.questions) or not st.session_state.activity_code:
            display_error("모든 필수 항목을 입력해주세요.")
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [
                current_time,
                st.session_state.activity_code,
                st.session_state.questions[0], st.session_state.get("image1_url", ""),
                st.session_state.questions[1], st.session_state.get("image2_url", ""),
                st.session_state.questions[2], st.session_state.get("image3_url", ""),
                teacher_email
            ]
            try:
                worksheet.append_row(row)
                st.success("✅ 문제가 성공적으로 저장되었습니다.")
            except Exception as e:
                display_error(f"문제 저장 중 오류가 발생했습니다: {e}")
