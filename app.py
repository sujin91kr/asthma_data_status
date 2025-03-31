import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import base64
from io import BytesIO
import hashlib
import pickle
import time
from datetime import date

# 페이지 설정
st.set_page_config(
    page_title="천식 데이터 분석",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 유효성 체크 기준
valid_visits = ["V1", "V2", "V3", "V4", "V5"]
valid_omics_tissue = [
    ["Bulk Exome RNA-seq", "PAXgene"],
    ["Bulk Exome RNA-seq", "PBMC"],
    ["Bulk Total RNA-seq", "Bronchial biopsy"],
    ["Bulk Total RNA-seq", "Nasal cell"],
    ["Bulk Total RNA-seq", "Sputum"],
    ["Metabolites", "Plasma"],
    ["Metabolites", "Urine"],
    ["Methylation", "Whole blood"],
    ["miRNA", "Serum"],
    ["Protein", "Plasma"],
    ["Protein", "Serum"],
    ["scRNA-seq", "Bronchial BAL"],
    ["scRNA-seq", "Bronchial biopsy"],
    ["scRNA-seq", "Whole blood"],
    ["SNP", "Whole blood"]
]
valid_projects = ["COREA", "PRISM", "PRISMUK"]

# 유효한 Omics-Tissue 조합 문자열로 변환
valid_omics_tissue_str = ["___".join(combo) for combo in valid_omics_tissue]

# 사용자 인증 함수
def authenticate(username, password):
    # 사용자 정보 (실제 사용 시 보안을 강화해야 함)
    users = {
        "admin": {
            "password": hashlib.sha256("admin123".encode()).hexdigest(),
            "permissions": {"can_upload": True, "is_admin": True}
        },
        "viewer": {
            "password": hashlib.sha256("viewer123".encode()).hexdigest(),
            "permissions": {"can_upload": False, "is_admin": False}
        }
    }
    
    # 비밀번호 해시화
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    # 사용자 검증
    if username in users and users[username]["password"] == hashed_password:
        return True, users[username]["permissions"]
    else:
        return False, None

# 엑셀 파일 다운로드 함수
def download_excel(df, filename):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    b64 = base64.b64encode(processed_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">엑셀 파일 다운로드</a>'
    return href

# 데이터 저장/로드 함수
def save_data(data):
    with open("asthma_data.pkl", "wb") as f:
        pickle.dump(data, f)

def load_data():
    if os.path.exists("asthma_data.pkl"):
        with open("asthma_data.pkl", "rb") as f:
            return pickle.load(f)
    return None

# 로그인 화면
def show_login_page():
    st.title("천식 데이터 분석 - 로그인")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write("계정 정보가 필요하시면 관리자에게 문의하세요.")
        st.markdown("---")
        
        username = st.text_input("사용자 이름:")
        password = st.text_input("비밀번호:", type="password")
        
        if st.button("로그인", type="primary"):
            is_authenticated, permissions = authenticate(username, password)
            
            if is_authenticated:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.permissions = permissions
                st.experimental_rerun()
            else:
                st.error("사용자 이름 또는 비밀번호가 올바르지 않습니다.")

# 원본 데이터 필터링 및 유효성 체크 함수
def filter_valid_data(df_raw):
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    
    # Omics_Tissue 컬럼 추가
    df_with_combo = df_raw.copy()
    df_with_combo['Omics_Tissue'] = df_with_combo['Omics'] + "___" + df_with_combo['Tissue']
    
    # 유효한 데이터만 필터링
    df_valid = df_with_combo[
        (df_with_combo['Visit'].isin(valid_visits)) &
        (df_with_combo['Omics_Tissue'].isin(valid_omics_tissue_str)) &
        (df_with_combo['Project'].isin(valid_projects))
    ].copy()
    
    # 중복 제거 (PatientID, Visit, Omics, Tissue 기준)
    df_valid = df_valid.drop_duplicates(subset=['PatientID', 'Visit', 'Omics', 'Tissue'])
    
    return df_valid

# 유효성 체크 함수
def check_invalid_visits(df):
    return df[~df['Visit'].isin(valid_visits)]

def check_invalid_omics_tissue(df):
    df_with_combo = df.copy()
    df_with_combo['Omics_Tissue'] = df_with_combo['Omics'] + "___" + df_with_combo['Tissue']
    return df_with_combo[~df_with_combo['Omics_Tissue'].isin(valid_omics_tissue_str)]

def check_invalid_projects(df):
    return df[~df['Project'].isin(valid_projects)]

def check_duplicates(df):
    duplicates = df.groupby(['PatientID', 'Visit', 'Omics', 'Tissue']).filter(lambda x: len(x) > 1)
    return duplicates

# 원본 데이터 표시 함수
def show_original_data(df, project):
    if df is None or df.empty:
        st.info("데이터가 없습니다. 파일을 업로드해주세요.")
        return
    
    df_filtered = df[df['Project'] == project].drop(columns=['Project'])
    st.dataframe(df_filtered, use_container_width=True)

# Pivot 테이블 생성 함수
def create_pivot_table(df_valid, project):
    if df_valid is None or df_valid.empty:
        st.info("유효한 데이터가 없습니다.")
        return
    
    # 프로젝트 필터링
    df_project = df_valid[df_valid['Project'] == project].copy()
    
    # Pivot 데이터 생성
    pivot_df = df_project.groupby(['PatientID', 'Visit', 'Omics_Tissue'])['SampleID'].apply(', '.join).reset_index()
    pivot_table = pivot_df.pivot_table(
        index=['PatientID', 'Visit'],
        columns='Omics_Tissue',
        values='SampleID',
        fill_value=''
    ).reset_index()
    
    return pivot_table

# Omics 현황 요약 함수
def create_omics_summary(df_valid, project):
    if df_valid is None or df_valid.empty:
        st.info("유효한 데이터가 없습니다.")
        return
    
    # 프로젝트 필터링
    df_project = df_valid[df_valid['Project'] == project].copy()
    
    # Omics, Tissue, Visit별 샘플 수 집계
    summary_df = df_project.groupby(['Omics', 'Tissue', 'Visit']).agg(
        SampleCount=('SampleID', 'nunique')
    ).reset_index()
    
    # Pivot 형태로 변환
    summary_pivot = summary_df.pivot_table(
        index=['Omics', 'Tissue'],
        columns='Visit',
        values='SampleCount',
        fill_value=0
    ).reset_index()
    
    # Total 열 추가
    summary_pivot['Total'] = summary_pivot.select_dtypes(include=[np.number]).sum(axis=1)
    
    return summary_pivot

# 프로젝트별 Omics 조합 생성 함수
def create_omics_combo(df_valid, project):
    if df_valid is None or df_valid.empty:
        st.info("유효한 데이터가 없습니다.")
        return
    
    # 프로젝트별 환자의 Omics 조합 계산
    df_project = df_valid[df_valid['Project'] == project].copy()
    
    # 환자별 Omics 조합 생성
    patient_omics = df_project.groupby('PatientID')['Omics'].apply(
        lambda x: ' + '.join(sorted(set(x)))
    ).reset_index()
    
    # Omics 조합별 환자 수 집계
    omics_combo_counts = patient_omics.groupby('Omics').agg(
        PatientCount=('PatientID', 'nunique')
    ).reset_index().sort_values('PatientCount', ascending=False)
    
    return omics_combo_counts, patient_omics

# Omics 조합별 환자 데이터 조회 함수
def get_patients_by_combo(df_valid, project, omics_combo):
    # 프로젝트 내 모든 환자의 Omics 조합 확인
    _, patient_omics = create_omics_combo(df_valid, project)
    
    # 선택된 Omics 조합을 가진 환자 ID 추출
    selected_patients = patient_omics[patient_omics['Omics'] == omics_combo]['PatientID'].tolist()
    
    # 해당 환자들의 데이터 필터링
    patient_data = df_valid[
        (df_valid['Project'] == project) & 
        (df_valid['PatientID'].isin(selected_patients))
    ].copy()
    
    return patient_data

# Omics 조합 샘플 요약 함수
def summarize_combo_samples(patient_data):
    if patient_data is None or patient_data.empty:
        return pd.DataFrame({'Message': ['해당 OmicsCombo를 가진 환자가 없습니다.']})
    
    # Omics, Tissue, Visit별 샘플 수 집계
    summary = patient_data.groupby(['Omics', 'Tissue', 'Visit']).agg(
        SampleCount=('SampleID', 'nunique')
    ).reset_index()
    
    # Pivot 형태로 변환
    summary_pivot = summary.pivot_table(
        index=['Omics', 'Tissue'],
        columns='Visit',
        values='SampleCount',
        fill_value=0
    ).reset_index()
    
    return summary_pivot

# 계층적 Omics 선택을 위한 데이터 준비 함수
def prepare_omics_selection_data(df_valid, project):
    if df_valid is None or df_valid.empty:
        return {}
    
    # 프로젝트별 유효한 Omics-Tissue 조합 추출
    df_project = df_valid[df_valid['Project'] == project].copy()
    
    # Omics 그룹화
    omics_groups = {}
    
    for omics in df_project['Omics'].unique():
        tissues = df_project[df_project['Omics'] == omics]['Tissue'].unique().tolist()
        omics_groups[omics] = tissues
    
    return omics_groups

# 선택된 Omics-Tissue 조합에 해당하는 환자 필터링
def filter_patients_by_omics_selection(df_valid, project, selected_combinations):
    """
    선택된 모든 Omics-Tissue 조합을 만족하는 환자만 필터링
    """
    if df_valid is None or df_valid.empty or not selected_combinations:
        return pd.DataFrame()
    
    # 프로젝트 데이터 필터링
    df_project = df_valid[df_valid['Project'] == project].copy()
    
    # 각 조합별로 해당하는 환자 목록 생성
    patients_by_combo = {}
    
    for omics, tissues in selected_combinations.items():
        for tissue in tissues:
            combo_key = f"{omics}___{tissue}"
            
            # 해당 Omics-Tissue 조합을 가진 환자 필터링
            combo_patients = df_project[
                (df_project['Omics'] == omics) & 
                (df_project['Tissue'] == tissue)
            ]['PatientID'].unique()
            
            patients_by_combo[combo_key] = set(combo_patients)
    
    # 모든 조합의 교집합 계산 (모든 조합을 만족하는 환자)
    if patients_by_combo:
        common_patients = set.intersection(*patients_by_combo.values())
        
        # 공통 환자 데이터 필터링
        filtered_data = df_project[df_project['PatientID'].isin(common_patients)].copy()
        return filtered_data
    
    return pd.DataFrame()

# 계층적 선택 결과 요약 함수
def summarize_hierarchical_results(filtered_data):
    if filtered_data is None or filtered_data.empty:
        return pd.DataFrame()
    
    # Visit별 환자 수 요약
    summary = filtered_data.groupby(['Omics', 'Tissue', 'Visit']).agg(
        PatientCount=('PatientID', 'nunique'),
        SampleCount=('SampleID', 'nunique')
    ).reset_index()
    
    # Pivot 테이블 형태로 변환 (Visit별 PatientCount와 SampleCount)
    visits = filtered_data['Visit'].unique()
    
    # 기본 인덱스 열
    result_df = summary[['Omics', 'Tissue']].drop_duplicates().copy()
    
    # 각 Visit에 대한 PatientCount와 SampleCount 열 추가
    for visit in visits:
        visit_data = summary[summary['Visit'] == visit]
        
        # Join을 위한 임시 DataFrame
        temp_df = visit_data[['Omics', 'Tissue', 'PatientCount', 'SampleCount']].copy()
        temp_df.columns = ['Omics', 'Tissue', f'{visit}_PatientCount', f'{visit}_SampleCount']
        
        # Left Join
        result_df = pd.merge(
            result_df, 
            temp_df, 
            on=['Omics', 'Tissue'], 
            how='left'
        )
    
    # NA를 0으로 대체
    result_df = result_df.fillna(0)
    
    # Total 열 추가
    patient_cols = [col for col in result_df.columns if 'PatientCount' in col]
    sample_cols = [col for col in result_df.columns if 'SampleCount' in col]
    
    result_df['Total_PatientCount'] = result_df[patient_cols].sum(axis=1)
    result_df['Total_SampleCount'] = result_df[sample_cols].sum(axis=1)
    
    return result_df

# 엑셀 다운로드 함수 (계층적 선택 결과)
def prepare_hierarchical_download(filtered_data, project):
    """
    계층적 선택 결과 데이터를 엑셀 다운로드용으로 준비
    """
    if filtered_data is None or filtered_data.empty:
        return None
    
    # BytesIO 객체 생성
    output = BytesIO()
    
    # ExcelWriter 생성
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 시트1: 조합별 요약
        summary_data = filtered_data.groupby(['Omics', 'Tissue', 'Visit']).agg(
            PatientCount=('PatientID', 'nunique'),
            SampleCount=('SampleID', 'nunique')
        ).reset_index()
        summary_data.to_excel(writer, sheet_name='조합별 요약', index=False)
        
        # 시트2: 환자별 샘플
        patient_samples = filtered_data[['PatientID', 'Visit', 'Omics', 'Tissue', 'SampleID']].sort_values(
            by=['PatientID', 'Visit', 'Omics', 'Tissue']
        )
        patient_samples.to_excel(writer, sheet_name='환자별 샘플', index=False)
        
        # 시트3: 환자별 방문별 샘플 수
        patient_visit_summary = filtered_data.groupby(['PatientID', 'Visit']).agg(
            OmicsCount=('Omics', 'nunique'),
            TissueCount=('Tissue', 'nunique'),
            SampleCount=('SampleID', 'nunique')
        ).reset_index()
        patient_visit_summary.to_excel(writer, sheet_name='환자별 방문별 샘플 수', index=False)
        
        # 시트4: 전체 데이터
        filtered_data.to_excel(writer, sheet_name='전체 데이터', index=False)
    
    # 직렬화된 엑셀 파일을 Base64로 인코딩
    bytes_data = output.getvalue()
    b64 = base64.b64encode(bytes_data).decode()
    
    # 다운로드 링크 생성
    current_date = date.today().strftime("%Y%m%d")
    filename = f"{project}_Selected_Omics_{current_date}.xlsx"
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">선택된 Omics 샘플 엑셀 다운로드</a>'
    
    return href

# 메인 앱 UI
def main_app():
    # 사이드바 메뉴
    st.sidebar.title("천식 데이터 분석")
    st.sidebar.write(f"사용자: {st.session_state.username}")
    
    if st.sidebar.button("로그아웃"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()
    
    # 메뉴 선택
    menu = st.sidebar.radio(
        "메뉴 선택",
        ["원본 데이터", "데이터 유효성 검사", "Pivot 테이블", "Omics 현황", "Omics 조합"]
    )
    
    # 파일 업로드 옵션 (관리자만)
    if st.session_state.permissions["can_upload"]:
        with st.sidebar.expander("파일 업로드"):
            uploaded_file = st.file_uploader("Excel 파일 업로드", type=["xlsx"])
            
            if uploaded_file is not None:
                df = pd.read_excel(uploaded_file)
                st.session_state.data = df
                save_data(df)
                st.sidebar.success("파일이 업로드되었습니다.")
    
    # 데이터 로드
    if 'data' not in st.session_state:
        st.session_state.data = load_data()
    
    # 유효 데이터 필터링
    if st.session_state.data is not None:
        st.session_state.valid_data = filter_valid_data(st.session_state.data)
    
    # 선택된 메뉴에 따른 화면 표시
    if menu == "원본 데이터":
        show_original_data_page()
    elif menu == "데이터 유효성 검사":
        show_validation_page()
    elif menu == "Pivot 테이블":
        show_pivot_page()
    elif menu == "Omics 현황":
        show_omics_summary_page()
    elif menu == "Omics 조합":
        show_omics_combo_page()

# 원본 데이터 페이지
def show_original_data_page():
    st.title("원본 데이터")
    
    if st.session_state.data is None or st.session_state.data.empty:
        st.info("데이터가 없습니다. 파일을 업로드해주세요.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    
    with tab1:
        st.subheader("COREA 데이터")
        show_original_data(st.session_state.data, "COREA")
    
    with tab2:
        st.subheader("PRISM 데이터")
        show_original_data(st.session_state.data, "PRISM")
    
    with tab3:
        st.subheader("PRISMUK 데이터")
        show_original_data(st.session_state.data, "PRISMUK")

# 데이터 유효성 검사 페이지
def show_validation_page():
    st.title("데이터 유효성 검사")
    
    if st.session_state.data is None or st.session_state.data.empty:
        st.info("데이터가 없습니다. 파일을 업로드해주세요.")
        return
    
    # 유효성 체크 수행
    invalid_visits_df = check_invalid_visits(st.session_state.data)
    invalid_omics_tissue_df = check_invalid_omics_tissue(st.session_state.data)
    invalid_projects_df = check_invalid_projects(st.session_state.data)
    duplicate_df = check_duplicates(st.session_state.data)
    
    # 체크 결과 상태
    visit_valid = len(invalid_visits_df) == 0
    omics_tissue_valid = len(invalid_omics_tissue_df) == 0
    project_valid = len(invalid_projects_df) == 0
    duplicate_valid = len(duplicate_df) == 0
    
    # 전체 데이터 수
    total_records = len(st.session_state.data)
    valid_records = len(st.session_state.valid_data) if st.session_state.valid_data is not None else 0
    
    # 상태 표시 (4개의 박스로 표시)
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    with col1:
        st.metric(
            label="Visit 체크",
            value="정상" if visit_valid else f"오류 {len(invalid_visits_df)}건",
            delta="통과" if visit_valid else None,
            delta_color="normal" if visit_valid else "inverse"
        )
        st.write("유효한 Visit 값: ", ", ".join(valid_visits))
    
    with col2:
        st.metric(
            label="Omics-Tissue 체크",
            value="정상" if omics_tissue_valid else f"오류 {len(invalid_omics_tissue_df)}건",
            delta="통과" if omics_tissue_valid else None,
            delta_color="normal" if omics_tissue_valid else "inverse"
        )
        st.write(f"유효한 Omics-Tissue 조합이 {len(valid_omics_tissue)}개 있습니다.")
    
    with col3:
        st.metric(
            label="Project 체크",
            value="정상" if project_valid else f"오류 {len(invalid_projects_df)}건",
            delta="통과" if project_valid else None,
            delta_color="normal" if project_valid else "inverse"
        )
        st.write("유효한 Project 값: ", ", ".join(valid_projects))
    
    with col4:
        st.metric(
            label="중복 체크",
            value="정상" if duplicate_valid else f"오류 {len(duplicate_df)}건",
            delta="통과" if duplicate_valid else None,
            delta_color="normal" if duplicate_valid else "inverse"
        )
        st.write("동일한 (PatientID, Visit, Omics, Tissue) 조합은 중복으로 간주됩니다.")
    
    # 요약 정보
    col5, col6 = st.columns(2)
    
    with col5:
        st.metric(
            label="유효한 레코드 / 전체 레코드",
            value=f"{valid_records} / {total_records}",
            delta=None
        )
    
    with col6:
        validity_ratio = round(valid_records/total_records*100, 1) if total_records > 0 else 0
        st.metric(
            label="데이터 유효성 비율",
            value=f"{validity_ratio}%",
            delta=None
        )
    
    # 상세 검사 결과 탭
    tab1, tab2, tab3, tab4 = st.tabs(["Visit 체크", "Omics-Tissue 체크", "Project 체크", "중복 체크"])
    
    with tab1:
        if not visit_valid:
            st.dataframe(invalid_visits_df, use_container_width=True)
        else:
            st.success("모든 Visit 값이 유효합니다.")
    
    with tab2:
        if not omics_tissue_valid:
            st.dataframe(invalid_omics_tissue_df, use_container_width=True)
        else:
            st.success("모든 Omics-Tissue 조합이 유효합니다.")
    
    with tab3:
        if not project_valid:
            st.dataframe(invalid_projects_df, use_container_width=True)
        else:
            st.success("모든 Project 값이 유효합니다.")
    
    with tab4:
        if not duplicate_valid:
            st.dataframe(duplicate_df, use_container_width=True)
        else:
            st.success("중복 레코드가 없습니다.")

# Pivot 테이블 페이지
def show_pivot_page():
    st.title("Pivot 테이블")
    
    if st.session_state.valid_data is None or st.session_state.valid_data.empty:
        st.info("유효한 데이터가 없습니다. 파일을 업로드하고 유효성 검사를 통과한 데이터가 필요합니다.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    
    with tab1:
        st.write("Project: COREA, Omics별 Sample Count")
        summary_corea = create_omics_summary(st.session_state.valid_data, "COREA")
        if summary_corea is not None and not summary_corea.empty:
            st.dataframe(summary_corea, use_container_width=True)
    
    with tab2:
        st.write("Project: PRISM, Omics별 Sample Count")
        summary_prism = create_omics_summary(st.session_state.valid_data, "PRISM")
        if summary_prism is not None and not summary_prism.empty:
            st.dataframe(summary_prism, use_container_width=True)
    
    with tab3:
        st.write("Project: PRISMUK, Omics별 Sample Count")
        summary_prismuk = create_omics_summary(st.session_state.valid_data, "PRISMUK")
        if summary_prismuk is not None and not summary_prismuk.empty:
            st.dataframe(summary_prismuk, use_container_width=True)

# Omics 조합 페이지
def show_omics_combo_page():
    st.title("Omics 조합")
    
    if st.session_state.valid_data is None or st.session_state.valid_data.empty:
        st.info("유효한 데이터가 없습니다. 파일을 업로드하고 유효성 검사를 통과한 데이터가 필요합니다.")
        return
    
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    
    with tab1:
        st.subheader("COREA 프로젝트 Omics 조합")
        show_omics_combo_tab("COREA")
    
    with tab2:
        st.subheader("PRISM 프로젝트 Omics 조합")
        show_omics_combo_tab("PRISM")
    
    with tab3:
        st.subheader("PRISMUK 프로젝트 Omics 조합")
        show_omics_combo_tab("PRISMUK")

# Omics 조합 탭 내용
def show_omics_combo_tab(project):
    # 계층적 선택 UI와 기존 조합 목록을 탭으로 구분
    subtab1, subtab2 = st.tabs(["계층적 Omics 선택", "기존 Omics 조합"])
    
    with subtab1:
        # 세션 상태 키
        selection_key = f"{project.lower()}_selected_omics"
        
        # 선택 가능한 Omics 목록 가져오기
        omics_groups = prepare_omics_selection_data(st.session_state.valid_data, project)
        
        # Omics 그룹이 없으면 정보 표시
        if not omics_groups:
            st.info(f"{project} 프로젝트에 데이터가 없습니다.")
            return
        
        # 선택 UI 컨테이너
        with st.container():
            st.write("Omics 선택")
            
            # 모두 선택/해제 버튼
            col1, col2 = st.columns([1, 6])
            with col1:
                if st.button("모두 선택", key=f"select_all_{project}"):
                    # 모든 Omics와 Tissue 선택
                    if selection_key not in st.session_state:
                        st.session_state[selection_key] = {}
                    
                    for omics, tissues in omics_groups.items():
                        st.session_state[selection_key][omics] = tissues
            
            with col2:
                if st.button("모두 해제", key=f"clear_all_{project}"):
                    # 선택 초기화
                    if selection_key in st.session_state:
                        st.session_state[selection_key] = {}
            
            # Omics 그룹 표시 (가로로 배열)
            omics_list = list(omics_groups.keys())
            cols = st.columns(len(omics_list))
            
            # 세션 상태 초기화
            if selection_key not in st.session_state:
                st.session_state[selection_key] = {}
            
            # 각 Omics에 대한 체크박스 그룹 생성
            for i, omics in enumerate(omics_list):
                with cols[i]:
                    st.write(f"**{omics}**")
                    
                    # 해당 Omics에 대한 Tissue 목록
                    tissues = omics_groups[omics]
                    
                    # 현재 선택 상태 
                    current_selection = st.session_state[selection_key].get(omics, [])
                    
                    # Tissue 체크박스 생성
                    selected_tissues = []
                    for tissue in tissues:
                        if st.checkbox(
                            tissue, 
                            value=tissue in current_selection,
                            key=f"{project}_{omics}_{tissue}"
                        ):
                            selected_tissues.append(tissue)
                    
                    # 선택 상태 업데이트
                    if selected_tissues:
                        st.session_state[selection_key][omics] = selected_tissues
                    elif omics in st.session_state[selection_key]:
                        del st.session_state[selection_key][omics]
        
        # 선택된 조합으로 환자 필터링
        filtered_data = filter_patients_by_omics_selection(
            st.session_state.valid_data, 
            project, 
            st.session_state.get(selection_key, {})
        )
        
        # 결과 표시
        st.subheader("선택된 Omics 조합 결과")
        
        if filtered_data.empty:
            st.info("선택된 항목이 없거나 조건에 맞는 데이터가 없습니다.")
        else:
            # 결과 요약
            result_summary = summarize_hierarchical_results(filtered_data)
            st.dataframe(result_summary, use_container_width=True)
            
            # 다운로드 링크
            download_link = prepare_hierarchical_download(filtered_data, project)
            st.markdown(download_link, unsafe_allow_html=True)
            
            # 상태 정보
            selected_count = sum(len(tissues) for tissues in st.session_state.get(selection_key, {}).values())
            patient_count = filtered_data['PatientID'].nunique()
            sample_count = filtered_data['SampleID'].nunique()
            
            st.info(f"선택된 조합 수: {selected_count}, 모든 조합을 만족하는 환자 수: {patient_count}, 샘플 수: {sample_count}")
    
    with subtab2:
        # 기존 Omics 조합 목록 표시
        omics_combo_df, _ = create_omics_combo(st.session_state.valid_data, project)
        
        if omics_combo_df is None or omics_combo_df.empty:
            st.info("해당 프로젝트에 데이터가 없습니다.")
            return
        
        # 목록 표시
        st.dataframe(omics_combo_df, use_container_width=True)
        
        # 선택 UI
        selected_combo = st.selectbox(
            "OmicsCombo 선택:", 
            omics_combo_df['Omics'].tolist(), 
            key=f"combo_select_{project}"
        )
        
        if selected_combo:
            # 선택된 Omics 조합을 가진 환자 데이터 조회
            patient_data = get_patients_by_combo(st.session_state.valid_data, project, selected_combo)
            
            # 환자 데이터 요약
            if patient_data is not None and not patient_data.empty:
                # 다운로드 버튼
                excel_name = f"{project}_{selected_combo.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.xlsx"
                
                col1, col2 = st.columns([1, 5])
                with col1:
                    # 엑셀 다운로드 버튼
                    patient_data_excel = patient_data.copy()
                    patient_data_excel['Omics_Tissue'] = patient_data_excel['Omics'] + "__" + patient_data_excel['Tissue']
                    excel_bytes = BytesIO()
                    with pd.ExcelWriter(excel_bytes, engine='openpyxl') as writer:
                        patient_data_excel.to_excel(writer, index=False)
                    
                    excel_data = excel_bytes.getvalue()
                    b64 = base64.b64encode(excel_data).decode()
                    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{excel_name}">해당 OmicsCombo 데이터 (엑셀) 다운로드</a>'
                    st.markdown(href, unsafe_allow_html=True)
                
                # 샘플 요약 표시
                st.write("선택된 OmicsCombo에 속한 Patient들의 (Omics, Visit별) 샘플수")
                combo_summary = summarize_combo_samples(patient_data)
                st.dataframe(combo_summary, use_container_width=True)

# 애플리케이션 시작
def main():
    # 앱 제목과 설명
    st.set_page_config(
        page_title="천식 데이터 분석",
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 세션 상태 초기화
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # 로그인 상태에 따라 화면 표시
    if not st.session_state.logged_in:
        show_login_page()
    else:
        main_app()

   if st.session_state.valid_data is None or st.session_state.valid_data.empty:
        st.info("유효한 데이터가 없습니다. 파일을 업로드하고 유효성 검사를 통과한 데이터가 필요합니다.")
        return
       
    tab1, tab2, tab3 = st.tabs(["COREA", "PRISM", "PRISMUK"])
    
    with tab1:
        st.write("Project: COREA, PatientID, Visit x (Omics, Tissue)")
        pivot_corea = create_pivot_table(st.session_state.valid_data, "COREA")
        if pivot_corea is not None and not pivot_corea.empty:
            st.dataframe(pivot_corea, use_container_width=True)
    
    with tab2:
        st.write("Project: PRISM, PatientID, Visit x (Omics, Tissue)")
        pivot_prism = create_pivot_table(st.session_state.valid_data, "PRISM")
        if pivot_prism is not None and not pivot_prism.empty:
            st.dataframe(pivot_prism, use_container_width=True)
    
    with tab3:
        st.write("Project: PRISMUK, PatientID, Visit x (Omics, Tissue)")
        pivot_prismuk = create_pivot_table(st.session_state.valid_data, "PRISMUK")
        if pivot_prismuk is not None and not pivot_prismuk.empty:
            st.dataframe(pivot_prismuk, use_container_width=True)

# Omics 현황 페이지
def show_omics_summary_page():
    st.title("Project별 Omics별 현황")
    
    if st.session_state.valid_data is None or st.session_state.valid_data.empty:
        st.info("유효한 데이터가 없습니다. 파일을 업로드하고 유효성 검사
