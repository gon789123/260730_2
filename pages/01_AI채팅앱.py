import streamlit as st
from openai import OpenAI

# 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")
st.title("🤖 AI 정보 선생님")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)

# AI의 성격 (화면에는 띄우지 않고 요청에만 함께 보낸다)
SYSTEM_PROMPT = (
    "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
    "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
)

# 학생들이 처음 질문하기 쉽도록 준비한 예시 질문 목록
EXAMPLE_QUESTIONS = [
    "AI는 어떻게 사람처럼 대답할 수 있어?",
    "코딩을 왜 배워야 해?",
    "인터넷은 어떻게 전 세계에 연결되어 있어?",
    "파이썬이랑 다른 언어는 뭐가 달라?",
    "컴퓨터는 어떻게 0과 1만으로 작동해?",
]

# 대화 기록이 없으면 처음 한 번만 만들어 둔다
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# 버튼으로 눌린 질문을 임시로 담아 둘 자리
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# 지금까지의 대화를 말풍선으로 다시 그리기 (성격 문장은 숨김)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 대화가 아직 시작되지 않았을 때만 예시 질문 버튼 보여주기
if len(st.session_state.messages) == 1:
    st.markdown("**💡 무엇을 물어봐야 할지 모르겠다면, 아래 질문을 눌러보세요!**")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, question in zip(cols, EXAMPLE_QUESTIONS):
        with col:
            if st.button(question, use_container_width=True):
                st.session_state.pending_question = question

# 채팅 입력창
user_input = st.chat_input("궁금한 것을 물어보세요!")

# 버튼 클릭이 있었다면 그 질문을, 없다면 직접 입력한 질문을 사용
final_input = st.session_state.pending_question or user_input
st.session_state.pending_question = None  # 한 번 쓰고 나면 초기화

if final_input:
    # 보낸 말을 기록에 넣고 화면에도 그리기
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # AI 답 받아오기 (실패하면 빨간 오류 화면 대신 안내 문구)
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="solar-open2",                 # 모델 이름은 그대로 유지
                messages=st.session_state.messages,  # 대화 전체를 함께 보내 기억 유지
                reasoning_effort="none",             # 추론 끄기 -> 바로 답변 시작
                stream=True,                         # 글자가 실시간으로 흐르게
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            # AI 답도 기록에 저장 (다음 질문에 이어서 사용)
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception:
            st.error("응답을 받지 못했습니다. 잠시 후 다시 보내 주세요.")
