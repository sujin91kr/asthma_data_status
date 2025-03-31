import streamlit as st
import pandas as pd
import numpy as np
import base64
import io
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import pickle
import re

# --------------------------------------------------------------------------------
# 1) 기본 설정 및 세션 상태 초기화
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="천식 데이터 분석",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 추가
st.markdown("""
<style>
    .main-header {
        font-weight: bold;
        font-size: 25px;
        padding: 10px;
        text-align: center;
        background-color: #f0f2f6;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .error-box {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .info-box {
        background-color: #cce5ff;
        color: #004085;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .user-info {
        text-align: right;
        padding: 10px;
    }
    .stButton button {
        width: 100%;
    }
    .hierarchy-item {
        padding-left: 20px;
        border-left: 1px solid #ddd;
        margin-bottom: 5px;
    }
    .selected-item {
        font-weight: bold;
        color: #1E88E5;
    }
    .logout-btn {
        color: white;
        background-color: #dc3545;
        border-radius: 5px;
        padding: 5px 10px;
    }
    div[data-testid="stSidebarNav"] {
        background-color: #f8f9fa;
        padding: 10px;
    }
    div[data-testid="stSidebarNav"] li {
        margin-bottom: 10px;
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 15px;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'permissions' not in st.session_state:
    st.session_state.permissions = None
if 'shared_data' not in st.session_state:
    st.session_state.shared_data = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'
if 'selected_omics_combo_corea' not in st.session_state:
    st.session_state.selected_omics_combo_corea = None
if 'selected_omics_combo_prism' not in st.session_state:
    st.session_state.selected_omics_combo_prism = None
if 'selected_omics_combo_prismuk' not in st.session_state:
    st.session_state.selected_omics_combo_prismuk = None

# --------------------------------------------------------------------------------
# 2) 사용자/프로젝트/Omics 정보 정의
# --------------------------------------------------------------------------------
users = {
    'admin': {
        'password': 'admin123',
        'permissions': {
            'can_upload': True,
            'is_admin': True
        }
    },
    'viewer': {
        'password': 'viewer123',
        'permissions': {
            'can_upload': False,
            'is_admin': False
        }
    }
}

valid_visits = ['V1', 'V2', 'V3', 'V4', 'V5']
valid_omics_tissue = [
    ('Bulk Exome RNA-seq', 'PAXgene'),
    ('Bulk Exome RNA-seq', 'PBMC'),
    ('Bulk Total RNA-seq', 'Bronchial biopsy'),
    ('Bulk Total RNA-seq', 'Nasal cell'),
    ('Bulk Total RNA-seq', 'Sputum'),
    ('Metabolites', 'Plasma'),
    ('Metabolites', 'Urine'),
    ('Methylation', 'Whole blood'),
    ('miRNA', 'Serum'),
    ('Protein', 'Plasma'),
    ('Protein', 'Serum'),
    ('scRNA-seq', 'Bronchial BAL'),
    ('scRNA-seq', 'Bronchial biopsy'),
    ('scRNA-seq', 'Whole blood'),
    ('SNP', 'Whole blood')
]
valid_projects = ['COREA', 'PRISM', 'PRISMUK']
valid_omics_tissue_str = [f"{o}___{t}" for o, t in valid_omics_tissue]

# --------------------------------------------------------------------------------
# 3) 유틸/헬퍼 함수
# --------------------------------------------------------------------------------
def get_excel_download_link(df, filename, link_text):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def load_data():
    data_storage_file = "asthma_data_storage.pkl"
    if st.session_state.shared_data is not None:
        return st.session_state.shared_data
    
    if os.path.exists(data_storage_file):
        try:
            with open(data_storage_file, 'rb') as f:
                data = pickle.load(f)
                st.session_state.shared_data = data
                return data
        except Exception as e:
            st.error(f"저장된 데이터를 로드하는 중 오류가 발생했습니다: {e}")
    return None

def get_valid_data(df):
    if df is None:
        return None
    
    df['Omics_Tissue'] = df['Omics'] + "___" + df['Tissue']
    mask_visit = df['Visit'].isin(valid_visits)
    mask_omics_tissue = df['Omics_Tissue'].isin(valid_omics_tissue_str)
    mask_project = df['Project'].isin(valid_projects)
    
    valid_df = df[mask_visit & mask_omics_tissue & mask_project].copy()
    valid_df = valid_df.drop_duplicates(subset=['PatientID', 'Visit', 'Omics', 'Tissue'])
    valid_df['Visit'] = pd.Categorical(valid_df['Visit'], categories=valid_visits, ordered=True)
    
    return valid_df

def get_invalid_data(df):
    if df is None:
        return None, None, None, None
    
    invalid_visit = df[~df['Visit'].isin(valid_visits)]
    df['Omics_Tissue'] = df['Omics'] + "___" + df['Tissue']
    invalid_omics_tissue = df[~df['Omics_Tissue'].isin(valid_omics_tissue_str)]
    invalid_project = df[~df['Project'].isin(valid_projects)]
    df_duplicate = df[df.duplicated(subset=['PatientID', 'Visit', 'Omics', 'Tissue'], keep=False)]
    return invalid_visit, invalid_omics_tissue, invalid_project, df_duplicate

def create_pivot_table(df, project):
    """
    - (PatientID, Omics_Tissue)를 피벗하여 SampleID 목록을 표시
    - fillna('') 시도 시 Categorical에서 오류가 생기면 astype(str)로 우선 변환
    """
    if df is None:
        return None
    
    project_df = df[df['Project'] == project].copy()
    
    # (PatientID, Visit, Omics_Tissue) 기준으로 SampleID 문자열 병합
    pivot_df = project_df.groupby(['PatientID', 'Visit', 'Omics_Tissue']).agg(
        {'SampleID': lambda x: ', '.join(x)}
    ).reset_index()

    # pivot
    pivot_table = pivot_df.pivot_table(
        index=['PatientID', 'Visit'],
        columns='Omics_Tissue',
        values='SampleID',
        aggfunc='first'
    )
    
    # 피벗 결과에서 fillna('')로 변환하기 전에 문자열 형식으로 변경
    pivot_table = pivot_table.astype(str).fillna('')  # 모든 셀을 문자열로
    pivot_table = pivot_table.reset_index()           # index(=PatientID, Visit) 열 복귀
    
    return pivot_table

def create_omics_summary(df, project):
    if df is None:
        return None
    project_df = df[df['Project'] == project].copy()
    summary_df = project_df.groupby(['Omics', 'Tissue', 'Visit']).agg({'SampleID': 'nunique'}).reset_index()
    summary_df.rename(columns={'SampleID': 'SampleCount'}, inplace=True)
    
    pivot_summary = summary_df.pivot_table(
        index=['Omics', 'Tissue'],
        columns='Visit',
        values='SampleCount',
        aggfunc='sum'
    ).reset_index().fillna(0)
    
    visit_cols = [col for col in pivot_summary.columns if col in valid_visits]
    pivot_summary['Total'] = pivot_summary[visit_cols].sum(axis=1)
    
    return pivot_summary

def create_omics_combo(df):
    if df is None:
        return None
    omics_combo = df.groupby(['Project', 'PatientID']).apply(
        lambda x: ' + '.join(sorted(x['Omics'].unique()))
    ).reset_index().rename(columns={0: 'OmicsCombo'})
    
    combo_count = omics_combo.groupby(['Project', 'OmicsCombo']).size().reset_index(name='PatientCount')
    combo_count = combo_count.sort_values(['Project', 'PatientCount'], ascending=[True, False])
    return combo_count

def filter_patients_by_hierarchy(df, project, hierarchy_values):
    """
    - hierarchy_values 구조를 기반으로 Omics->Tissue 체크 상태를 해석해서
      해당 Omics *모두*를 갖는 환자만 필터
    - Tissue 체크가 없으면 해당 Omics의 전체 Tissue
    """
    project_key = project.lower()
    selected_omics = hierarchy_values[f"{project_key}_omics"]  # Omics 리스트
    selected_otkeys = hierarchy_values[f"{project_key}_tissues"]  # "Omics___Tissue"
    
    # Omics 하나도 없으면 결과 없음
    if not selected_omics:
        return pd.DataFrame()
    
    sub = df[df['Project'] == project].copy()
    if len(sub) == 0:
        return pd.DataFrame()
    
    # 환자를 Omics별로 필터링하되, Tissue 체크는 Omics별로 "Omics___Tissue" key가 있으면 그 Tissue만
    # => 환자가 전부(AND) 만족해야 하므로 Omics별 환자집합을 순차적으로 교집합
    final_patients = None
    
    for omics in selected_omics:
        # 이 Omics에 대해 체크된 Tissue 목록
        tlist = []
        for ot in selected_otkeys:
            if ot.startswith(f"{omics}___"):
                tlist.append(ot.split("___", 1)[1])  # Tissue만
        # Tissue가 하나도 체크 안됐다면 => 해당 Omics 전체 Tissue 허용
        if not tlist:
            df_omics = sub[sub['Omics'] == omics].copy()
        else:
            df_omics = sub[(sub['Omics'] == omics) & (sub['Tissue'].isin(tlist))].copy()
        
        # 이 Omics를 가진 환자집합
        patients_omics = set(df_omics['PatientID'].unique())
        
        if final_patients is None:
            # 첫 Omics
            final_patients = patients_omics
        else:
            # 교집합
            final_patients = final_patients.intersection(patients_omics)
    
    # 교집합 결과가 없다면 빈 DF
    if not final_patients:
        return pd.DataFrame()
    
    # 최종 환자들
    return sub[sub['PatientID'].isin(final_patients)].copy()
    
def get_patients_that_have_all_selected_omics(df, project, selected_omics, selected_tissues):
    """
    - project 내 데이터에서 Tissue가 selected_tissues(중 하나)인 것만 추출(만약 tissue 선택이 비어있으면 전체 Tissue)
    - 각 환자가 보유한 Omics를 확인하여, selected_omics가 전부(subset) 포함되는지 확인
      (즉, 선택한 Omics 목록을 '모두' 만족하는 사람만 필터)
    """
    sub = df[df['Project'] == project].copy()
    if len(sub) == 0:
        return pd.DataFrame()
    
    # Tissue 선택이 비어있지 않다면, 해당 Tissue만 필터
    if selected_tissues:
        sub = sub[sub['Tissue'].isin(selected_tissues)]
    
    # Omics가 1개도 선택 안 되었으면 결과 없음(혹은 '전체'로 볼 수도 있지만, 요구사항대로 비움)
    if not selected_omics:
        return pd.DataFrame()  # 빈 DF 리턴
    
    # 환자별로 실제 보유 Omics set
    g = sub.groupby('PatientID')['Omics'].unique()
    passing_patients = []
    for pid, omics_arr in g.iteritems():
        omics_set = set(omics_arr)
        # "selected_omics"가 omics_set의 부분집합인지(교집합 로직)
        # => "모든 선택 Omics를 환자가 가지고 있는지"
        if set(selected_omics).issubset(omics_set):
            passing_patients.append(pid)
    
    # 최종 해당 환자들의 (Omics, Tissue, SampleID 등) raw 데이터
    final_df = sub[sub['PatientID'].isin(passing_patients)].copy()
    return final_df

# --------------------------------------------------------------------------------
# 4) 페이지 함수들
# --------------------------------------------------------------------------------
def login_page():
    st.markdown('<div class="main-header">천식 데이터 분석 - 로그인</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("### 로그인")
        st.write("계정 정보가 없으면 관리자에게 문의하세요.")
        st.markdown("---")
        
        username = st.text_input("사용자 이름:")
        password = st.text_input("비밀번호:", type="password")
        
        if st.button("로그인", key="login_button"):
            if username in users and users[username]['password'] == password:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.permissions = users[username]['permissions']
                st.session_state.page = 'original_data'
                st.stop()
            else:
                st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

def original_data_page():
    st.markdown('<div class="main-header">원본 데이터</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    with tab1:
        st.markdown("### COREA 데이터")
        df_corea = df[df['Project'] == 'COREA'].drop(columns=['Project'])
        st.dataframe(df_corea, use_container_width=True)
    with tab2:
        st.markdown("### PRISM 데이터")
        df_prism = df[df['Project'] == 'PRISM'].drop(columns=['Project'])
        st.dataframe(df_prism, use_container_width=True)
    with tab3:
        st.markdown("### PRISMUK 데이터")
        df_prismuk = df[df['Project'] == 'PRISMUK'].drop(columns=['Project'])
        st.dataframe(df_prismuk, use_container_width=True)

def validation_check_page():
    st.markdown('<div class="main-header">데이터 유효성 검사</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data = get_invalid_data(df)
    valid_df = get_valid_data(df)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        is_valid_visit = (len(invalid_visit) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_visit else 'error-box'}">
                <h4>Visit 체크</h4>
                <p>{'정상' if is_valid_visit else f'오류 발견 ({len(invalid_visit)}건)'}</p>
                <p>{'모든 Visit 값이 V1-V5 범위 내에 있습니다' if is_valid_visit else f'{len(invalid_visit)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    with col2:
        is_valid_omics_tissue = (len(invalid_omics_tissue) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_omics_tissue else 'error-box'}">
                <h4>Omics-Tissue 체크</h4>
                <p>{'정상' if is_valid_omics_tissue else f'오류 발견 ({len(invalid_omics_tissue)}건)'}</p>
                <p>{'모든 Omics-Tissue 조합이 유효합니다' if is_valid_omics_tissue else f'{len(invalid_omics_tissue)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    with col3:
        is_valid_project = (len(invalid_project) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_project else 'error-box'}">
                <h4>Project 체크</h4>
                <p>{'정상' if is_valid_project else f'오류 발견 ({len(invalid_project)}건)'}</p>
                <p>{'모든 Project 값이 유효합니다' if is_valid_project else f'{len(invalid_project)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    with col4:
        is_valid_duplicate = (len(duplicate_data) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_duplicate else 'error-box'}">
                <h4>중복 체크</h4>
                <p>{'정상' if is_valid_duplicate else f'오류 발견 ({len(duplicate_data)}건)'}</p>
                <p>{'중복 레코드가 없습니다' if is_valid_duplicate else f'{len(duplicate_data)}개 레코드가 중복되었습니다.'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    
    col5, col6 = st.columns(2)
    with col5:
        total_records = len(df)
        valid_records = len(valid_df) if valid_df is not None else 0
        st.metric("유효한 레코드 / 전체 레코드", f"{valid_records} / {total_records}")
    with col6:
        valid_percent = (valid_records / total_records * 100) if total_records > 0 else 0
        st.metric("데이터 유효성 비율", f"{valid_percent:.1f}%")
    
    st.markdown("### 상세 검사 결과")
    tab1, tab2, tab3, tab4 = st.tabs(["Visit 체크", "Omics-Tissue 체크", "Project 체크", "중복 체크"])
    with tab1:
        st.info(f"유효한 Visit 값: {', '.join(valid_visits)}")
        if len(invalid_visit) > 0:
            st.dataframe(invalid_visit, use_container_width=True)
        else:
            st.success("모든 Visit 값이 유효합니다.")
    with tab2:
        st.info(f"유효한 Omics-Tissue 조합은 총 {len(valid_omics_tissue)}개입니다.")
        if len(invalid_omics_tissue) > 0:
            st.dataframe(invalid_omics_tissue, use_container_width=True)
        else:
            st.success("모든 Omics-Tissue 조합이 유효합니다.")
    with tab3:
        st.info(f"유효한 Project 값: {', '.join(valid_projects)}")
        if len(invalid_project) > 0:
            st.dataframe(invalid_project, use_container_width=True)
        else:
            st.success("모든 Project 값이 유효합니다.")
    with tab4:
        st.info("동일한 (PatientID, Visit, Omics, Tissue) 조합은 중복입니다.")
        if len(duplicate_data) > 0:
            st.dataframe(duplicate_data, use_container_width=True)
        else:
            st.success("중복 레코드가 없습니다.")

def pivot_tables_page():
    st.markdown('<div class="main-header">Pivot 테이블</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    valid_df = get_valid_data(df)
    if valid_df is None or len(valid_df) == 0:
        st.warning("유효한 데이터가 없습니다. 데이터 유효성을 확인해주세요.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    with tab1:
        st.markdown("### Project: COREA - (PatientID, Visit) x (Omics, Tissue)")
        pivot_corea = create_pivot_table(valid_df, 'COREA')
        if pivot_corea is not None and len(pivot_corea) > 0:
            st.dataframe(pivot_corea, use_container_width=True)
            excel_filename = f"COREA_Pivot_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(pivot_corea, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
        else:
            st.info("COREA 프로젝트에 대한 유효한 데이터가 없습니다.")
    with tab2:
        st.markdown("### Project: PRISM - (PatientID, Visit) x (Omics, Tissue)")
        pivot_prism = create_pivot_table(valid_df, 'PRISM')
        if pivot_prism is not None and len(pivot_prism) > 0:
            st.dataframe(pivot_prism, use_container_width=True)
            excel_filename = f"PRISM_Pivot_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(pivot_prism, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
        else:
            st.info("PRISM 프로젝트에 대한 유효한 데이터가 없습니다.")
    with tab3:
        st.markdown("### Project: PRISMUK - (PatientID, Visit) x (Omics, Tissue)")
        pivot_prismuk = create_pivot_table(valid_df, 'PRISMUK')
        if pivot_prismuk is not None and len(pivot_prismuk) > 0:
            st.dataframe(pivot_prismuk, use_container_width=True)
            excel_filename = f"PRISMUK_Pivot_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(pivot_prismuk, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
        else:
            st.info("PRISMUK 프로젝트에 대한 유효한 데이터가 없습니다.")

def omics_summary_page():
    st.markdown('<div class="main-header">Project별 Omics별 현황</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    valid_df = get_valid_data(df)
    if valid_df is None or len(valid_df) == 0:
        st.warning("유효한 데이터가 없습니다. 데이터 유효성을 확인해주세요.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    # -- COREA
    with tab1:
        st.markdown("### Project: COREA - Omics별 Sample Count")
        summary_corea = create_omics_summary(valid_df, 'COREA')
        if summary_corea is not None and len(summary_corea) > 0:
            st.dataframe(summary_corea, use_container_width=True)
            excel_filename = f"COREA_Summary_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(summary_corea, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            st.markdown("#### 시각화")
            plot_data = summary_corea.melt(
                id_vars=['Omics', 'Tissue'],
                value_vars=valid_visits + ['Total'],
                var_name='Visit',
                value_name='SampleCount'
            )
            fig = px.bar(
                plot_data,
                x='Omics',
                y='SampleCount',
                color='Visit',
                barmode='group',
                facet_row='Tissue',
                hover_data=['Omics', 'Tissue', 'Visit', 'SampleCount'],
                title='COREA - Omics별, Tissue별, Visit별 샘플 수'
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("COREA 프로젝트에 대한 유효한 데이터가 없습니다.")
    
    # -- PRISM
    with tab2:
        st.markdown("### Project: PRISM - Omics별 Sample Count")
        summary_prism = create_omics_summary(valid_df, 'PRISM')
        if summary_prism is not None and len(summary_prism) > 0:
            st.dataframe(summary_prism, use_container_width=True)
            excel_filename = f"PRISM_Summary_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(summary_prism, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            st.markdown("#### 시각화")
            plot_data = summary_prism.melt(
                id_vars=['Omics', 'Tissue'],
                value_vars=valid_visits + ['Total'],
                var_name='Visit',
                value_name='SampleCount'
            )
            fig = px.bar(
                plot_data,
                x='Omics',
                y='SampleCount',
                color='Visit',
                barmode='group',
                facet_row='Tissue',
                hover_data=['Omics', 'Tissue', 'Visit', 'SampleCount'],
                title='PRISM - Omics별, Tissue별, Visit별 샘플 수'
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("PRISM 프로젝트에 대한 유효한 데이터가 없습니다.")
    
    # -- PRISMUK
    with tab3:
        st.markdown("### Project: PRISMUK - Omics별 Sample Count")
        summary_prismuk = create_omics_summary(valid_df, 'PRISMUK')
        if summary_prismuk is not None and len(summary_prismuk) > 0:
            st.dataframe(summary_prismuk, use_container_width=True)
            excel_filename = f"PRISMUK_Summary_{datetime.now().strftime('%Y%m%d')}.xlsx"
            excel_link = get_excel_download_link(summary_prismuk, excel_filename, "엑셀 다운로드")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            st.markdown("#### 시각화")
            plot_data = summary_prismuk.melt(
                id_vars=['Omics', 'Tissue'],
                value_vars=valid_visits + ['Total'],
                var_name='Visit',
                value_name='SampleCount'
            )
            fig = px.bar(
                plot_data,
                x='Omics',
                y='SampleCount',
                color='Visit',
                barmode='group',
                facet_row='Tissue',
                hover_data=['Omics', 'Tissue', 'Visit', 'SampleCount'],
                title='PRISMUK - Omics별, Tissue별, Visit별 샘플 수'
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("PRISMUK 프로젝트에 대한 유효한 데이터가 없습니다.")

# ---- [중요] 새로 개선된 Omics 조합 페이지 ----
def omics_combination_page():
    """
    Omics + Tissue를 계층적 체크박스로 선택 (방문은 없음),
    선택된 모든 Omics를 가지고 있는 환자만 필터(AND 교집합).
    """
    st.markdown('<div class="main-header">Project별 Omics 및 Tissue 계층별 선택</div>', unsafe_allow_html=True)
    df = load_data()
    
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    valid_df = get_valid_data(df)
    if valid_df is None or len(valid_df) == 0:
        st.warning("유효한 데이터가 없습니다. 데이터 유효성을 확인해주세요.")
        return
    
    # 탭1: 계층적 선택 / 탭2: 기존 Omics 조합
    tab1, tab2 = st.tabs(["계층적 Omics 선택", "기존 Omics 조합"])
    
    # -----------------------------
    # (1) 계층적 Omics 선택(체크박스)
    # -----------------------------
    with tab1:
        st.write("아래에서 Omics와 Tissue를 계층적으로 체크하여, **모두**(Omics 기준) 만족하는 환자를 필터링합니다.")
        
        # 서브 탭 3개 (COREA / PRISM / PRISMUK)
        hierarchy_tab1, hierarchy_tab2, hierarchy_tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
        
        # ------ [COREA] ------
        with hierarchy_tab1:
            st.subheader("COREA - Omics→Tissue 선택")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("#### Omics 선택")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("모두 선택", key="select_all_corea"):
                        all_omics = sorted(valid_df[valid_df['Project'] == 'COREA']['Omics'].unique().tolist())
                        st.session_state.hierarchy_values['corea_omics'] = all_omics
                        
                        # 해당 Omics에 속한 Tissue 전부 선택
                        all_tissues = []
                        for omics in all_omics:
                            sub_tissues = valid_df[
                                (valid_df['Project'] == 'COREA') & (valid_df['Omics'] == omics)
                            ]['Tissue'].unique().tolist()
                            for tissue in sub_tissues:
                                all_tissues.append(f"{omics}___{tissue}")
                        
                        st.session_state.hierarchy_values['corea_tissues'] = all_tissues
                
                with col_btn2:
                    if st.button("모두 해제", key="clear_all_corea"):
                        st.session_state.hierarchy_values['corea_omics'] = []
                        st.session_state.hierarchy_values['corea_tissues'] = []
                
                st.write("---")
                
                # Omics 목록
                omics_list = sorted(valid_df[valid_df['Project'] == 'COREA']['Omics'].unique().tolist())
                for omics in omics_list:
                    is_omics_selected = (omics in st.session_state.hierarchy_values['corea_omics'])
                    if st.checkbox(omics, value=is_omics_selected, key=f"corea_omics_{omics}"):
                        # 체크됨 → Omics 목록에 없으면 추가
                        if omics not in st.session_state.hierarchy_values['corea_omics']:
                            st.session_state.hierarchy_values['corea_omics'].append(omics)
                    else:
                        # 체크 해제
                        if omics in st.session_state.hierarchy_values['corea_omics']:
                            st.session_state.hierarchy_values['corea_omics'].remove(omics)
                            
                            # Tissue에서도 제거
                            updated_tissues = []
                            for ot in st.session_state.hierarchy_values['corea_tissues']:
                                if not ot.startswith(f"{omics}___"):
                                    updated_tissues.append(ot)
                            st.session_state.hierarchy_values['corea_tissues'] = updated_tissues
                    
                    # Omics가 체크되었으면 아래 Tissue들 체크박스
                    if omics in st.session_state.hierarchy_values['corea_omics']:
                        sub_tissues = sorted(valid_df[
                            (valid_df['Project'] == 'COREA') & (valid_df['Omics'] == omics)
                        ]['Tissue'].unique().tolist())
                        
                        st.markdown(f"##### {omics}에 대한 Tissue:")
                        st.markdown("<div class='hierarchy-item'>", unsafe_allow_html=True)
                        for tissue in sub_tissues:
                            ot_key = f"{omics}___{tissue}"
                            is_tissue_selected = (ot_key in st.session_state.hierarchy_values['corea_tissues'])
                            if st.checkbox(tissue, value=is_tissue_selected, key=f"corea_tissue_{omics}_{tissue}"):
                                if ot_key not in st.session_state.hierarchy_values['corea_tissues']:
                                    st.session_state.hierarchy_values['corea_tissues'].append(ot_key)
                            else:
                                if ot_key in st.session_state.hierarchy_values['corea_tissues']:
                                    st.session_state.hierarchy_values['corea_tissues'].remove(ot_key)
                        st.markdown("</div>", unsafe_allow_html=True)
            
            # 오른쪽(결과는 아래에 표시하므로 비워두거나 안내문)
            with col2:
                st.info("Omics와 Tissue를 선택하세요. 아래에 결과가 표시됩니다.")
            
            st.write("---")
            # 최종 필터 결과 아래쪽에 표시
            filtered_data = filter_patients_by_hierarchy(valid_df, 'COREA', st.session_state.hierarchy_values)
            st.markdown("### 선택 조건에 부합하는 COREA 환자/샘플")
            if len(filtered_data) > 0:
                st.dataframe(filtered_data, use_container_width=True)
            else:
                st.info("해당 조건에 맞는 COREA 환자가 없습니다.")
        
        # ------ [PRISM] ------
        with hierarchy_tab2:
            st.subheader("PRISM - Omics→Tissue 선택")
            col1, col2 = st.columns([1,1])
            with col1:
                st.markdown("#### Omics 선택")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("모두 선택", key="select_all_prism"):
                        all_omics = sorted(valid_df[valid_df['Project'] == 'PRISM']['Omics'].unique().tolist())
                        st.session_state.hierarchy_values['prism_omics'] = all_omics
                        
                        all_tissues = []
                        for omics in all_omics:
                            sub_tissues = valid_df[
                                (valid_df['Project'] == 'PRISM') & (valid_df['Omics'] == omics)
                            ]['Tissue'].unique().tolist()
                            for tissue in sub_tissues:
                                all_tissues.append(f"{omics}___{tissue}")
                        st.session_state.hierarchy_values['prism_tissues'] = all_tissues
                
                with col_btn2:
                    if st.button("모두 해제", key="clear_all_prism"):
                        st.session_state.hierarchy_values['prism_omics'] = []
                        st.session_state.hierarchy_values['prism_tissues'] = []
                
                st.write("---")
                
                omics_list = sorted(valid_df[valid_df['Project'] == 'PRISM']['Omics'].unique().tolist())
                for omics in omics_list:
                    is_omics_selected = (omics in st.session_state.hierarchy_values['prism_omics'])
                    if st.checkbox(omics, value=is_omics_selected, key=f"prism_omics_{omics}"):
                        if omics not in st.session_state.hierarchy_values['prism_omics']:
                            st.session_state.hierarchy_values['prism_omics'].append(omics)
                    else:
                        if omics in st.session_state.hierarchy_values['prism_omics']:
                            st.session_state.hierarchy_values['prism_omics'].remove(omics)
                            updated_tissues = []
                            for ot in st.session_state.hierarchy_values['prism_tissues']:
                                if not ot.startswith(f"{omics}___"):
                                    updated_tissues.append(ot)
                            st.session_state.hierarchy_values['prism_tissues'] = updated_tissues
                    
                    if omics in st.session_state.hierarchy_values['prism_omics']:
                        sub_tissues = sorted(valid_df[
                            (valid_df['Project'] == 'PRISM') & (valid_df['Omics'] == omics)
                        ]['Tissue'].unique().tolist())
                        
                        st.markdown(f"##### {omics}에 대한 Tissue:")
                        st.markdown("<div class='hierarchy-item'>", unsafe_allow_html=True)
                        for tissue in sub_tissues:
                            ot_key = f"{omics}___{tissue}"
                            is_tissue_selected = (ot_key in st.session_state.hierarchy_values['prism_tissues'])
                            if st.checkbox(tissue, value=is_tissue_selected, key=f"prism_tissue_{omics}_{tissue}"):
                                if ot_key not in st.session_state.hierarchy_values['prism_tissues']:
                                    st.session_state.hierarchy_values['prism_tissues'].append(ot_key)
                            else:
                                if ot_key in st.session_state.hierarchy_values['prism_tissues']:
                                    st.session_state.hierarchy_values['prism_tissues'].remove(ot_key)
                        st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.info("Omics와 Tissue를 선택하세요. 아래에 결과가 표시됩니다.")
            
            st.write("---")
            filtered_data = filter_patients_by_hierarchy(valid_df, 'PRISM', st.session_state.hierarchy_values)
            st.markdown("### 선택 조건에 부합하는 PRISM 환자/샘플")
            if len(filtered_data) > 0:
                st.dataframe(filtered_data, use_container_width=True)
            else:
                st.info("해당 조건에 맞는 PRISM 환자가 없습니다.")
        
        # ------ [PRISMUK] ------
        with hierarchy_tab3:
            st.subheader("PRISMUK - Omics→Tissue 선택")
            col1, col2 = st.columns([1,1])
            with col1:
                st.markdown("#### Omics 선택")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("모두 선택", key="select_all_prismuk"):
                        all_omics = sorted(valid_df[valid_df['Project'] == 'PRISMUK']['Omics'].unique().tolist())
                        st.session_state.hierarchy_values['prismuk_omics'] = all_omics
                        
                        all_tissues = []
                        for omics in all_omics:
                            sub_tissues = valid_df[
                                (valid_df['Project'] == 'PRISMUK') & (valid_df['Omics'] == omics)
                            ]['Tissue'].unique().tolist()
                            for tissue in sub_tissues:
                                all_tissues.append(f"{omics}___{tissue}")
                        st.session_state.hierarchy_values['prismuk_tissues'] = all_tissues
                
                with col_btn2:
                    if st.button("모두 해제", key="clear_all_prismuk"):
                        st.session_state.hierarchy_values['prismuk_omics'] = []
                        st.session_state.hierarchy_values['prismuk_tissues'] = []
                
                st.write("---")
                
                omics_list = sorted(valid_df[valid_df['Project'] == 'PRISMUK']['Omics'].unique().tolist())
                for omics in omics_list:
                    is_omics_selected = (omics in st.session_state.hierarchy_values['prismuk_omics'])
                    if st.checkbox(omics, value=is_omics_selected, key=f"prismuk_omics_{omics}"):
                        if omics not in st.session_state.hierarchy_values['prismuk_omics']:
                            st.session_state.hierarchy_values['prismuk_omics'].append(omics)
                    else:
                        if omics in st.session_state.hierarchy_values['prismuk_omics']:
                            st.session_state.hierarchy_values['prismuk_omics'].remove(omics)
                            updated_tissues = []
                            for ot in st.session_state.hierarchy_values['prismuk_tissues']:
                                if not ot.startswith(f"{omics}___"):
                                    updated_tissues.append(ot)
                            st.session_state.hierarchy_values['prismuk_tissues'] = updated_tissues
                    
                    if omics in st.session_state.hierarchy_values['prismuk_omics']:
                        sub_tissues = sorted(valid_df[
                            (valid_df['Project'] == 'PRISMUK') & (valid_df['Omics'] == omics)
                        ]['Tissue'].unique().tolist())
                        
                        st.markdown(f"##### {omics}에 대한 Tissue:")
                        st.markdown("<div class='hierarchy-item'>", unsafe_allow_html=True)
                        for tissue in sub_tissues:
                            ot_key = f"{omics}___{tissue}"
                            is_tissue_selected = (ot_key in st.session_state.hierarchy_values['prismuk_tissues'])
                            if st.checkbox(tissue, value=is_tissue_selected, key=f"prismuk_tissue_{omics}_{tissue}"):
                                if ot_key not in st.session_state.hierarchy_values['prismuk_tissues']:
                                    st.session_state.hierarchy_values['prismuk_tissues'].append(ot_key)
                            else:
                                if ot_key in st.session_state.hierarchy_values['prismuk_tissues']:
                                    st.session_state.hierarchy_values['prismuk_tissues'].remove(ot_key)
                        st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.info("Omics와 Tissue를 선택하세요. 아래에 결과가 표시됩니다.")
            
            st.write("---")
            filtered_data = filter_patients_by_hierarchy(valid_df, 'PRISMUK', st.session_state.hierarchy_values)
            st.markdown("### 선택 조건에 부합하는 PRISMUK 환자/샘플")
            if len(filtered_data) > 0:
                st.dataframe(filtered_data, use_container_width=True)
            else:
                st.info("해당 조건에 맞는 PRISMUK 환자가 없습니다.")
    
    # ------------------------
    # (2) 기존 Omics 조합
    # ------------------------
    with tab2:
        st.markdown("### 기존 Omics 조합")
        
        existing_tab1, existing_tab2, existing_tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
        
        # -- COREA
        with existing_tab1:
            omics_combo = create_omics_combo(valid_df)
            if omics_combo is not None:
                corea_combo = omics_combo[omics_combo['Project'] == 'COREA'][['OmicsCombo','PatientCount']]
                if len(corea_combo) > 0:
                    st.dataframe(corea_combo, use_container_width=True)
                    selected_combo = st.selectbox(
                        "OmicsCombo 선택:",
                        options=corea_combo['OmicsCombo'].tolist(),
                        key="corea_combo_selectbox"
                    )
                    
                    if selected_combo:
                        st.session_state.selected_omics_combo_corea = selected_combo
                        # 어떤 환자들이 이 OmicsCombo를 갖는지
                        patients_with_combo = valid_df.groupby(['Project','PatientID']).apply(
                            lambda x: ' + '.join(sorted(x['Omics'].unique()))
                        ).reset_index().rename(columns={0:'OmicsCombo'})
                        
                        relevant_patients = patients_with_combo[
                            (patients_with_combo['Project'] == 'COREA') &
                            (patients_with_combo['OmicsCombo'] == selected_combo)
                        ]['PatientID'].tolist()
                        
                        if relevant_patients:
                            patient_data = valid_df[
                                (valid_df['Project'] == 'COREA') &
                                (valid_df['PatientID'].isin(relevant_patients))
                            ].sort_values(['PatientID','Omics','Tissue','Visit'])
                            
                            sample_count = patient_data.groupby(['Omics','Tissue','Visit']).agg({
                                'SampleID':'nunique'
                            }).reset_index().rename(columns={'SampleID':'SampleCount'})
                            pivot_sample_count = sample_count.pivot_table(
                                index=['Omics','Tissue'],
                                columns='Visit',
                                values='SampleCount',
                                aggfunc='sum'
                            ).reset_index().fillna(0)
                            
                            st.markdown("---")
                            st.markdown(f"### 선택된 OmicsCombo({selected_combo}) 환자의 (Omics, Visit별) 샘플수")
                            st.dataframe(pivot_sample_count, use_container_width=True)
                            
                            if st.button("해당 OmicsCombo 데이터 (엑셀) 다운로드", key="download_corea_excel"):
                                output = BytesIO()
                                df_save = patient_data[['PatientID','Omics','Tissue','Visit','SampleID']].copy()
                                df_save['Omics_Tissue'] = df_save['Omics'] + "__" + df_save['Tissue']
                                df_save = df_save[['PatientID','Visit','Omics_Tissue','SampleID']]
                                pivot_save = df_save.pivot_table(
                                    index=['PatientID','Visit'],
                                    columns='Omics_Tissue',
                                    values='SampleID',
                                    aggfunc='first'
                                ).reset_index().fillna('')
                                
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    pivot_save.to_excel(writer, index=False)
                                
                                output.seek(0)
                                b64 = base64.b64encode(output.read()).decode()
                                filename = f"COREA_{re.sub(' ', '_', selected_combo)}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">엑셀 파일 다운로드 (클릭)</a>'
                                st.markdown(href, unsafe_allow_html=True)
                        else:
                            st.info("해당 OmicsCombo를 가진 환자가 없습니다.")
                else:
                    st.info("COREA 프로젝트에 대한 Omics 조합이 없습니다.")
            else:
                st.info("Omics 조합을 생성할 수 없습니다. 유효한 데이터가 부족합니다.")
        
        # -- PRISM
        with existing_tab2:
            omics_combo = create_omics_combo(valid_df)
            if omics_combo is not None:
                prism_combo = omics_combo[omics_combo['Project'] == 'PRISM'][['OmicsCombo','PatientCount']]
                if len(prism_combo) > 0:
                    st.dataframe(prism_combo, use_container_width=True)
                    selected_combo = st.selectbox(
                        "OmicsCombo 선택:",
                        options=prism_combo['OmicsCombo'].tolist(),
                        key="prism_combo_selectbox"
                    )
                    
                    if selected_combo:
                        st.session_state.selected_omics_combo_prism = selected_combo
                        patients_with_combo = valid_df.groupby(['Project','PatientID']).apply(
                            lambda x: ' + '.join(sorted(x['Omics'].unique()))
                        ).reset_index().rename(columns={0:'OmicsCombo'})
                        
                        relevant_patients = patients_with_combo[
                            (patients_with_combo['Project'] == 'PRISM') &
                            (patients_with_combo['OmicsCombo'] == selected_combo)
                        ]['PatientID'].tolist()
                        
                        if relevant_patients:
                            patient_data = valid_df[
                                (valid_df['Project'] == 'PRISM') &
                                (valid_df['PatientID'].isin(relevant_patients))
                            ].sort_values(['PatientID','Omics','Tissue','Visit'])
                            
                            sample_count = patient_data.groupby(['Omics','Tissue','Visit']).agg({
                                'SampleID':'nunique'
                            }).reset_index().rename(columns={'SampleID':'SampleCount'})
                            pivot_sample_count = sample_count.pivot_table(
                                index=['Omics','Tissue'],
                                columns='Visit',
                                values='SampleCount',
                                aggfunc='sum'
                            ).reset_index().fillna(0)
                            
                            st.markdown("---")
                            st.markdown(f"### 선택된 OmicsCombo({selected_combo}) 환자의 (Omics, Visit별) 샘플수")
                            st.dataframe(pivot_sample_count, use_container_width=True)
                            
                            if st.button("해당 OmicsCombo 데이터 (엑셀) 다운로드", key="download_prism_excel"):
                                output = BytesIO()
                                df_save = patient_data[['PatientID','Omics','Tissue','Visit','SampleID']].copy()
                                df_save['Omics_Tissue'] = df_save['Omics'] + "__" + df_save['Tissue']
                                df_save = df_save[['PatientID','Visit','Omics_Tissue','SampleID']]
                                pivot_save = df_save.pivot_table(
                                    index=['PatientID','Visit'],
                                    columns='Omics_Tissue',
                                    values='SampleID',
                                    aggfunc='first'
                                ).reset_index().fillna('')
                                
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    pivot_save.to_excel(writer, index=False)
                                
                                output.seek(0)
                                b64 = base64.b64encode(output.read()).decode()
                                filename = f"PRISM_{re.sub(' ', '_', selected_combo)}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">엑셀 파일 다운로드 (클릭)</a>'
                                st.markdown(href, unsafe_allow_html=True)
                        else:
                            st.info("해당 OmicsCombo를 가진 환자가 없습니다.")
                else:
                    st.info("PRISM 프로젝트에 대한 Omics 조합이 없습니다.")
            else:
                st.info("Omics 조합을 생성할 수 없습니다. 유효한 데이터가 부족합니다.")
        
        # -- PRISMUK
        with existing_tab3:
            omics_combo = create_omics_combo(valid_df)
            if omics_combo is not None:
                prismuk_combo = omics_combo[omics_combo['Project'] == 'PRISMUK'][['OmicsCombo','PatientCount']]
                if len(prismuk_combo) > 0:
                    st.dataframe(prismuk_combo, use_container_width=True)
                    selected_combo = st.selectbox(
                        "OmicsCombo 선택:",
                        options=prismuk_combo['OmicsCombo'].tolist(),
                        key="prismuk_combo_selectbox"
                    )
                    
                    if selected_combo:
                        st.session_state.selected_omics_combo_prismuk = selected_combo
                        
                        patients_with_combo = valid_df.groupby(['Project','PatientID']).apply(
                            lambda x: ' + '.join(sorted(x['Omics'].unique()))
                        ).reset_index().rename(columns={0:'OmicsCombo'})
                        
                        relevant_patients = patients_with_combo[
                            (patients_with_combo['Project'] == 'PRISMUK') &
                            (patients_with_combo['OmicsCombo'] == selected_combo)
                        ]['PatientID'].tolist()
                        
                        if relevant_patients:
                            patient_data = valid_df[
                                (valid_df['Project'] == 'PRISMUK') &
                                (valid_df['PatientID'].isin(relevant_patients))
                            ].sort_values(['PatientID','Omics','Tissue','Visit'])
                            
                            sample_count = patient_data.groupby(['Omics','Tissue','Visit']).agg({
                                'SampleID':'nunique'
                            }).reset_index().rename(columns={'SampleID':'SampleCount'})
                            pivot_sample_count = sample_count.pivot_table(
                                index=['Omics','Tissue'],
                                columns='Visit',
                                values='SampleCount',
                                aggfunc='sum'
                            ).reset_index().fillna(0)
                            
                            st.markdown("---")
                            st.markdown(f"### 선택된 OmicsCombo({selected_combo}) 환자의 (Omics, Visit별) 샘플수")
                            st.dataframe(pivot_sample_count, use_container_width=True)
                            
                            if st.button("해당 OmicsCombo 데이터 (엑셀) 다운로드", key="download_prismuk_excel"):
                                output = BytesIO()
                                df_save = patient_data[['PatientID','Omics','Tissue','Visit','SampleID']].copy()
                                df_save['Omics_Tissue'] = df_save['Omics'] + "__" + df_save['Tissue']
                                df_save = df_save[['PatientID','Visit','Omics_Tissue','SampleID']]
                                pivot_save = df_save.pivot_table(
                                    index=['PatientID','Visit'],
                                    columns='Omics_Tissue',
                                    values='SampleID',
                                    aggfunc='first'
                                ).reset_index().fillna('')
                                
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    pivot_save.to_excel(writer, index=False)
                                
                                output.seek(0)
                                b64 = base64.b64encode(output.read()).decode()
                                filename = f"PRISMUK_{re.sub(' ', '_', selected_combo)}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                                href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">엑셀 파일 다운로드 (클릭)</a>'
                                st.markdown(href, unsafe_allow_html=True)
                        else:
                            st.info("해당 OmicsCombo를 가진 환자가 없습니다.")
                else:
                    st.info("PRISMUK 프로젝트에 대한 Omics 조합이 없습니다.")
            else:
                st.info("Omics 조합을 생성할 수 없습니다. 유효한 데이터가 부족합니다.")


# --------------------------------------------------------------------------------
# 5) 사이드바 메뉴 및 전체 흐름
# --------------------------------------------------------------------------------
def sidebar_menu():
    st.sidebar.markdown(f"<div class='user-info'>사용자: {st.session_state.user}</div>", unsafe_allow_html=True)
    
    if st.sidebar.button("로그아웃", key="logout_btn", type="primary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.stop()
    
    st.sidebar.markdown("---")
    
    if st.session_state.permissions and st.session_state.permissions.get('can_upload', False):
        uploaded_file = st.sidebar.file_uploader("Excel 파일 업로드", type=['xlsx'], key="file_uploader")
        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                st.session_state.shared_data = df
                if st.session_state.permissions.get('is_admin', False):
                    with open("asthma_data_storage.pkl", 'wb') as f:
                        pickle.dump(df, f)
                    st.sidebar.success("데이터가 저장되었습니다.")
            except Exception as e:
                st.sidebar.error(f"파일 업로드 중 오류가 발생했습니다: {e}")
    
    st.sidebar.markdown("---")
    
    menu_options = {
        "원본 데이터": "original_data",
        "데이터 유효성 검사": "validation_check",
        "Pivot 테이블": "pivot_tables",
        "Omics 현황": "omics_summary",
        "Omics 조합": "omics_combination"
    }
    for menu_title, page_name in menu_options.items():
        if st.sidebar.button(menu_title, key=f"menu_{page_name}"):
            st.session_state.page = page_name

def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        sidebar_menu()
        if st.session_state.page == 'original_data':
            original_data_page()
        elif st.session_state.page == 'validation_check':
            validation_check_page()
        elif st.session_state.page == 'pivot_tables':
            pivot_tables_page()
        elif st.session_state.page == 'omics_summary':
            omics_summary_page()
        elif st.session_state.page == 'omics_combination':
            omics_combination_page()
        else:
            original_data_page()

if __name__ == "__main__":
    main()
