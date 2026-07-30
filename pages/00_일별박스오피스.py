import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

KOBIS_KEY = st.secrets["KOBIS_KEY"]
BOX_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
INFO_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfoResult.json"

today_kst = datetime.now(ZoneInfo("Asia/Seoul")).date()
default_date = today_kst - timedelta(days=1)

selected_date = st.date_input("조회할 날짜", value=default_date, max_value=default_date)
target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")


@st.cache_data(ttl=3600)
def fetch_boxoffice(target_dt: str):
    res = requests.get(BOX_URL, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)
    if res.status_code != 200:
        return None, f"요청이 실패했습니다 (상태코드: {res.status_code})"
    data = res.json()
    if "faultInfo" in data:
        return None, "인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요."
    box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    if not box_list:
        return None, "그날 자료가 없습니다. 날짜를 하루 더 앞으로 옮겨 보세요."
    return pd.DataFrame(box_list), None


@st.cache_data(ttl=86400)  # 영화 상세정보는 거의 안 바뀌므로 하루 캐싱
def fetch_movie_info(movie_cd: str):
    """영화 상세정보를 가져온다. 실패 시 원인을 담은 error 키를 함께 반환한다."""
    try:
        res = requests.get(INFO_URL, params={"key": KOBIS_KEY, "movieCd": movie_cd}, timeout=10)
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 오류: {e}"}

    if res.status_code != 200:
        return {"error": f"API 상태코드 오류: {res.status_code}"}

    data = res.json()
    if "faultInfo" in data:
        return {"error": f"KOBIS 오류: {data['faultInfo'].get('message', '알 수 없음')}"}

    info = data.get("movieInfoResult", {}).get("movieInfo", {})
    if not info:
        return {"error": "이 영화는 KOBIS 상세정보 DB에 등록되어 있지 않습니다."}

    directors = ", ".join(d.get("peopleNm", "") for d in info.get("directors", [])) or "-"
    actors = ", ".join(a.get("peopleNm", "") for a in info.get("actors", [])[:3]) or "-"
    genres = ", ".join(g.get("genreNm", "") for g in info.get("genres", [])) or "-"
    nation = ", ".join(n.get("nationNm", "") for n in info.get("nations", [])) or "-"
    audits = info.get("audits", [])
    grade = audits[0].get("watchGradeNm", "-") if audits else "-"

    return {
        "감독": directors,
        "주요배우": actors,
        "장르": genres,
        "국가": nation,
        "상영시간": f"{info.get('showTm', '-')}분",
        "관람등급": grade,
    }


df, err = fetch_boxoffice(target_dt)
if err:
    st.warning(err) if "자료" in err else st.error(err)
    st.stop()

for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]:
    df[col] = pd.to_numeric(df[col])

# 스크린당 관객수
df["스크린당관객"] = (df["audiCnt"] / df["scrnCnt"]).round(0)

# 영화 상세정보 병합 (국가/장르 구분 위해 필요)
with st.spinner("영화 상세정보 불러오는 중..."):
    info_list = [fetch_movie_info(code) for code in df["movieCd"]]
df["국가"] = [info.get("국가", "-") if "error" not in info else "-" for info in info_list]
df["장르"] = [info.get("장르", "-") if "error" not in info else "-" for info in info_list]

# 1위 영화 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("1위", top["movieNm"])
c2.metric("관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")


def format_rank_change(row):
    if row["rankOldAndNew"] == "NEW":
        return "🆕 NEW"
    inten = row["rankInten"]
    if inten > 0:
        return f"▲{inten}"
    elif inten < 0:
        return f"▼{abs(inten)}"
    return "-"


df["순위변동"] = df.apply(format_rank_change, axis=1)

table = df[["rank", "movieNm", "순위변동", "국가", "장르", "audiCnt", "스크린당관객", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "전일대비", "국가", "장르", "관객수", "스크린당관객", "누적관객", "스크린수"]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table, use_container_width=True)

# 한국영화 vs 외국영화 점유율
st.subheader("🌏 한국영화 vs 외국영화 관객 점유율")


def classify_nation(n):
    return "한국" if "한국" in n else ("기타/외국" if n != "-" else "정보없음")


df["국가구분"] = df["국가"].apply(classify_nation)
nation_share = df.groupby("국가구분")["audiCnt"].sum()

col_a, col_b = st.columns([1, 1])
with col_a:
    st.bar_chart(nation_share)
with col_b:
    total = nation_share.sum()
    for nation, cnt in nation_share.items():
        st.metric(nation, f"{cnt / total * 100:.1f}%", f"{cnt:,}명")

st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])

# 스크린당 관객수 랭킹 (효율 좋은 영화 찾기)
st.subheader("🎯 스크린당 관객수 TOP 5 (효율 순)")
efficiency = table.sort_values("스크린당관객", ascending=False).head(5)
st.bar_chart(efficiency.set_index("영화명")["스크린당관객"])
st.caption("스크린 수 대비 관객이 많을수록 '상영관은 적어도 알짜 흥행'하는 영화입니다.")

# 영화 선택 시 상세정보 카드
st.subheader("🎬 영화 상세정보")
selected_movie = st.selectbox("영화 선택", table["영화명"].tolist())
selected_code = df[df["movieNm"] == selected_movie]["movieCd"].iloc[0]
info = fetch_movie_info(selected_code)

if "error" not in info:
    d1, d2, d3 = st.columns(3)
    d1.write(f"**감독**\n\n{info['감독']}")
    d2.write(f"**주요 배우**\n\n{info['주요배우']}")
    d3.write(f"**관람등급**\n\n{info['관람등급']}")
    d4, d5 = st.columns(2)
    d4.write(f"**장르**\n\n{info['장르']}")
    d5.write(f"**상영시간**\n\n{info['상영시간']}")
else:
    st.info(f"상세정보를 불러오지 못했습니다. ({info['error']})")
