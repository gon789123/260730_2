import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]
URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
default_date = today_kst - timedelta(days=1)

# 1. 날짜 선택 기능
selected_date = st.date_input(
    "조회할 날짜",
    value=default_date,
    max_value=default_date,  # 오늘/미래 자료는 KOBIS에 없으니 어제까지만 허용
)
target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")


@st.cache_data(ttl=3600)
def fetch_boxoffice(target_dt: str):
    res = requests.get(URL, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)
    if res.status_code != 200:
        return None, f"요청이 실패했습니다 (상태코드: {res.status_code})"
    data = res.json()
    if "faultInfo" in data:
        return None, "인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요."
    box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    if not box_list:
        return None, "그날 자료가 없습니다. 날짜를 하루 더 앞으로 옮겨 보세요."
    return pd.DataFrame(box_list), None


df, err = fetch_boxoffice(target_dt)
if err:
    st.warning(err) if "자료" in err else st.error(err)
    st.stop()

for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]:
    df[col] = pd.to_numeric(df[col])

# 1위 영화 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("1위", top["movieNm"])
c2.metric("관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")


# 2. 순위 변동 표시 (rankOldAndNew: NEW/OLD, rankInten: 증감폭)
def format_rank_change(row):
    if row["rankOldAndNew"] == "NEW":
        return "🆕 NEW"
    inten = row["rankInten"]
    if inten > 0:
        return f"▲{inten}"
    elif inten < 0:
        return f"▼{abs(inten)}"
    else:
        return "-"


df["순위변동"] = df.apply(format_rank_change, axis=1)

table = df[["rank", "movieNm", "순위변동", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "전일대비", "개봉일", "관객수", "누적관객", "스크린수"]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table, use_container_width=True)

st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])


# 4. 최근 7일 트렌드 (선택한 영화 기준)
st.subheader("🗓️ 최근 7일 관객수 추이")

movie_options = table["영화명"].tolist()
selected_movie = st.selectbox("영화 선택", movie_options)

trend_rows = []
for i in range(6, -1, -1):  # 6일 전 ~ 오늘(선택일) 순서
    d = selected_date - timedelta(days=i)
    d_str = d.strftime("%Y%m%d")
    day_df, day_err = fetch_boxoffice(d_str)
    if day_err:
        continue
    day_df["audiCnt"] = pd.to_numeric(day_df["audiCnt"])
    row = day_df[day_df["movieNm"] == selected_movie]
    if not row.empty:
        trend_rows.append({"날짜": d.strftime("%m-%d"), "관객수": int(row.iloc[0]["audiCnt"])})

if trend_rows:
    trend_df = pd.DataFrame(trend_rows).set_index("날짜")
    st.line_chart(trend_df["관객수"])
else:
    st.info("최근 7일간 이 영화의 박스오피스 데이터가 없습니다 (TOP 10 밖이었을 수 있어요).")
