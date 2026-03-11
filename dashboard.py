import streamlit as st
import pandas as pd
import sqlite3
import os
import json
import plotly.express as px
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(
    page_title="NemoStore 프리미엄 부동산 분석 v2.0",
    page_icon="🏢",
    layout="wide"
)

# 커스텀 CSS (4열 갤러리 및 프리미엄 스타일)
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .gallery-card {
        background-color: white;
        padding: 5px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        transition: transform 0.2s;
        text-align: center;
    }
    .gallery-card:hover { transform: translateY(-3px); }
    .price-tag { color: #e44d26; font-weight: bold; font-size: 1.0em; display: block; margin: 5px 0; }
    .bench-tag { font-size: 0.8em; padding: 2px 5px; border-radius: 4px; display: inline-block; margin-bottom: 5px; }
    .bench-up { background-color: #ffebee; color: #c62828; }
    .bench-down { background-color: #e8f5e9; color: #2e7d32; }
    .card-title { font-size: 0.9em; font-weight: 600; color: #333; height: 40px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 경로 (배포 환경을 고려한 상대 경로 설정)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # nemostore 폴더
DB_PATH = os.path.join(BASE_DIR, "data", "nemo_stores.db")

@st.cache_data
def load_and_preprocess():
    if not os.path.exists(DB_PATH):
        st.error("데이터베이스를 찾을 수 없습니다.")
        return pd.DataFrame()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM store_list", conn)
    conn.close()
    
    # 1. 이미지 파싱
    df['photo_list'] = df['smallPhotoUrls'].apply(lambda x: json.loads(x) if x else [])
    
    # 2. 벤치마킹 지표 계산 (업종별 평균 임대료 대비)
    biz_avg = df.groupby('businessMiddleCodeName')['monthlyRent'].mean().to_dict()
    df['avg_rent_biz'] = df['businessMiddleCodeName'].map(biz_avg)
    df['bench_ratio'] = ((df['monthlyRent'] - df['avg_rent_biz']) / df['avg_rent_biz'] * 100).fillna(0)
    
    # 3. ㎡당 임대료
    df['rent_per_size'] = (df['monthlyRent'] / df['size']).fillna(0)
    
    return df

df_raw = load_and_preprocess()

# --- 사이드바: 필터 ---
st.sidebar.title("🏢 스마트 필터")
search_keyword = st.sidebar.text_input("🔍 매물명/키워드 검색", placeholder="예: '전주 1층 식당'")

all_biz = sorted(df_raw['businessMiddleCodeName'].unique())
sel_biz = st.sidebar.multiselect("🏷️ 업종(중분류)", all_biz)

st.sidebar.divider()
st.sidebar.subheader("💰 예산 및 면적")
r_rent = st.sidebar.slider("월세(만)", 0, int(df_raw['monthlyRent'].max()), (0, 500), step=10)
r_size = st.sidebar.slider("면적(㎡)", 0, int(df_raw['size'].max()), (0, 300))

# --- 필터링 로직 ---
df = df_raw.copy()
if search_keyword: df = df[df['title'].str.contains(search_keyword, na=False, case=False)]
if sel_biz: df = df[df['businessMiddleCodeName'].isin(sel_biz)]
df = df[(df['monthlyRent'].between(r_rent[0], r_rent[1])) & (df['size'].between(r_size[0], r_size[1]))]

# --- 메인 대시보드 ---
st.title("🚀 NemoStore Premium v2.0")
st.markdown(f"**{len(df):,}**개의 매물이 조건에 부합합니다. (전체 {len(df_raw):,}건)")

tabs = st.tabs(["🖼️ 프리미엄 갤러리", "📈 밀집도/분석", "📊 시장 트렌드", "📋 상세 리스트"])

# --- Tab 1: 4열 갤러리 탐색 ---
with tabs[0]:
    if df.empty:
        st.warning("조건에 맞는 매물이 없습니다.")
    else:
        # 데이터가 너무 많으면 성능을 위해 상위 100개만 렌더링
        rows_per_page = 100
        subset = df.head(rows_per_page)
        
        # 4열 그리드 구현
        cols = st.columns(4)
        for i, row in enumerate(subset.itertuples()):
            with cols[i % 4]:
                st.markdown(f'<div class="gallery-card">', unsafe_allow_html=True)
                img = row.photo_list[0] if row.photo_list else "https://via.placeholder.com/300x200?text=Nemo+Store"
                st.image(img, width='stretch')
                st.markdown(f'<div class="card-title">{row.title[:25]}</div>', unsafe_allow_html=True)
                st.markdown(f'<span class="price-tag">{row.monthlyRent:,}만 / {row.deposit:,}만</span>', unsafe_allow_html=True)
                
                # 벤치마킹 표시
                b_class = "bench-down" if row.bench_ratio < 0 else "bench-up"
                st.markdown(f'<span class="bench-tag {b_class}">업종평균대비 {row.bench_ratio:+.1f}%</span>', unsafe_allow_html=True)
                
                if st.button("상세 정보", key=f"btn_{row.Index}"):
                    st.session_state['sel_id'] = row.Index
                st.markdown('</div>', unsafe_allow_html=True)

    # 매물 상세 뷰어
    if 'sel_id' in st.session_state:
        st.divider()
        item = df_raw.loc[st.session_state['sel_id']]
        c1, c2 = st.columns([1, 1.5])
        with c1:
            if item['photo_list']:
                # 모든 사진 슬라이더 (여기서는 대표 사진들만 갤러리 형태로 표시 가능)
                st.image(item['photo_list'], width=150)
            else:
                st.info("이미지 없음")
        with c2:
            st.subheader(item['title'])
            st.info(f"📍 **{item['businessMiddleCodeName']}** | {item['floor']}층 | {item['size']}㎡")
            st.write(f"💰 **월세 {item['monthlyRent']:,} / 보증금 {item['deposit']:,} / 권리금 {item['premium']:,}**")
            st.markdown(f"**가성비 분석**: 이 매물은 동일 업종 평균 대비 월세가 **{item['bench_ratio']:+.1f}%** 차이납니다.")
            st.button("닫기", on_click=lambda: st.session_state.pop('sel_id'))

# --- Tab 2: 밀집도 및 분포 분석 (지도 대안) ---
with tabs[1]:
    st.subheader("📊 지역/업종 밀집도 분석 (Market Density)")
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**업종별 매물 비중 및 가격 (Treemap)**")
        fig_tree = px.treemap(df, path=['businessLargeCodeName', 'businessMiddleCodeName'], 
                             values='monthlyRent', color='monthlyRent',
                             color_continuous_scale='RdBu_r', template='plotly_white')
        st.plotly_chart(fig_tree, width='stretch')
        st.caption("💡 상자의 크기는 임대료 합계를, 색상은 가격 수준을 나타냅니다.")

    with col_b:
        st.write("**층수별 매물 분포 (Sunburst)**")
        fig_sun = px.sunburst(df, path=['floor', 'businessMiddleCodeName'], 
                             values='monthlyRent', color='monthlyRent',
                             color_continuous_scale='Viridis', template='plotly_white')
        st.plotly_chart(fig_sun, width='stretch')

# --- Tab 3: 시장 트렌드 ---
with tabs[2]:
    st.subheader("📈 가격 분석 지표")
    col_c, col_d = st.columns(2)
    with col_c:
        st.write("**면적 대비 임대료 상관관계 (Trendline)**")
        try:
            fig_trend = px.scatter(df, x='size', y='monthlyRent', trendline="ols",
                                   color='businessMiddleCodeName', hover_name='title',
                                   labels={'size':'면적(㎡)', 'monthlyRent':'월세(만)'},
                                   template='plotly_white')
            st.plotly_chart(fig_trend, width='stretch')
        except:
            st.info("데이터가 부족하여 트렌드 라인을 생성할 수 없습니다.")
            
    with col_d:
        st.write("**층별 평균 임대료 분석**")
        floor_avg = df.groupby('floor')['monthlyRent'].mean().reset_index().sort_values('floor')
        fig_floor = px.bar(floor_avg, x='floor', y='monthlyRent', color='monthlyRent',
                           labels={'floor':'층수', 'monthlyRent':'평균 월세(만)'},
                           template='plotly_white')
        st.plotly_chart(fig_floor, width='stretch')

# --- Tab 4: 상세 리스트 (한글 컬럼명) ---
with tabs[3]:
    st.subheader("📋 전체 매물 상세 내역")
    list_cols = ['title', 'businessMiddleCodeName', 'monthlyRent', 'deposit', 'premium', 'size', 'floor', 'bench_ratio']
    st.dataframe(
        df[list_cols].rename(columns={
            'title': '매물 명칭', 'businessMiddleCodeName': '업종', 'monthlyRent': '월세(만)',
            'deposit': '보증금(만)', 'premium': '권리금(만)', 'size': '면적(㎡)', 'floor': '층',
            'bench_ratio': '가성비(%)'
        }),
        width='stretch', hide_index=True
    )

st.sidebar.markdown("---")
st.sidebar.caption("NemoStore Premium v2.0 | Built with Streamlit")
