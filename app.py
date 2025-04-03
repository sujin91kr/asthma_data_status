import streamlit as st
import pandas as pd
import numpy as np
import datetime
import os
import io
import base64
from PIL import Image
import hashlib
import json
import re
from datetime import datetime

# 설정 및 상수
CONFIG_FILE = "config.json"
DATA_FILE = "data/clinical_data.xlsx"
USER_FILE = "data/users.json"

VALID_VISITS = ["V1", "V2", "V3", "V4", "V5"]
VALID_OMICS = ["Bulk Exome RNA-seq", "Bulk Total RNA-seq", "Metabolites", "SNP", "Methylation", "miRNA", "Protein", "scNRA-seq"]
VALID_TISSUES = ["PAXgene", "PBMC", "Bronchial biopsy", "Nasal cell", "Sputum", "Plasma", "Urine", "Whole blood", "Serum", "Bronchial BAL"]
VALID_PROJECTS = ["COREA", "PRISM", "PRISMUK"]
VALID_OMICS_TISSUE = {
    "Bulk Exome RNA-seq": ["PAXgene", "PBMC"],
    "Bulk Total RNA-seq": ["Bronchial biopsy", "Nasal cell", "Sputum"],
    "Metabolites": ["Plasma", "Urine"],
    "Methylation": ["Whole blood"],
    "miRNA": ["Serum"],
    "Protein": ["Plasma", "Serum"],
    "scRNA-seq": ["Whole blood", "Bronchial biopsy", "Bronchial BAL"],
    "SNP": ["Whole blood"]
}

# 디렉토리 생성
os.makedirs("data", exist_ok=True)

# 페이지 설정
st.set_page_config(
    page_title="COREA | PRISM Omics Data Status",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 정의
st.markdown("""
<style>
    .main-header {
        font-size: 25px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 20px;
        border-bottom: 2px solid #1E3A8A;
        padding-bottom: 10px;
    }
    .sub-header {
        font-size: 20px;
        font-weight: bold;
        color: #2563EB;
        margin: 15px 0;
    }
    .success-box {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .error-box {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .info-box {
        background-color: #EFF6FF;
        border-left: 5px solid #3B82F6;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .warning-box {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #EFF6FF;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3B82F6 !important;
        color: white !important;
    }
    .footer {
        margin-top: 50px;
        text-align: center;
        color: #6B7280;
        font-size: 14px;
        border-top: 1px solid #E5E7EB;
        padding-top: 20px;
    }
    .metric-card {
        background-color: #F9FAFB;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
        margin-bottom: 16px;
    }
    .file-path {
        background-color: #F3F4F6;
        padding: 8px 12px;
        border-radius: 4px;
        font-family: monospace;
        margin: 5px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .file-path-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .copy-button {
        background-color: transparent;
        border: none;
        color: #3B82F6;
        cursor: pointer;
        padding: 2px 8px;
        font-size: 14px;
    }
    .copy-button:hover {
        background-color: #EFF6FF;
        border-radius: 4px;
    }
</style>
<script>
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        alert("경로가 클립보드에 복사되었습니다!");
    }, function() {
        alert("복사에 실패했습니다!");
    });
}
</script>
""", unsafe_allow_html=True)

#############################################
# 사용자 관리 함수
#############################################
def init_users():
    if not os.path.exists(USER_FILE):
        default_users = {
            "admin": {
                "password": hashlib.sha256("admin123".encode()).hexdigest(),
                "is_admin": True
            },
            "user": {
                "password": hashlib.sha256("user123".encode()).hexdigest(),
                "is_admin": False
            }
        }
        with open(USER_FILE, 'w') as f:
            json.dump(default_users, f)

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)

def authenticate(username, password):
    users = load_users()
    if username in users:
        stored_password = users[username]["password"]
        if stored_password == hashlib.sha256(password.encode()).hexdigest():
            return True, users[username]["is_admin"]
    return False, False

#############################################
# 데이터 로딩 및 처리 함수
#############################################
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_excel(DATA_FILE)
            # 필수 컬럼 확인
            required_cols = ["Project", "PatientID", "Visit", "Omics", "Tissue", "SampleID", "Date"]
            if not all(col in df.columns for col in required_cols):
                st.error(f"데이터 파일에 필수 컬럼이 누락되었습니다. 필요한 컬럼: {', '.join(required_cols)}")
                return None
            
            # 날짜 형식 변환
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce', utc=False)
            
            return df
        except Exception as e:
            st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
            return None
    return None

def get_invalid_data(df):
    # 유효하지 않은 Visit 체크
    invalid_visit = df[~df['Visit'].isin(VALID_VISITS)].copy()
    
    # 유효하지 않은 Omics-Tissue 조합 체크
    invalid_omics_tissue_rows = []
    for index, row in df.iterrows():
        omics = row['Omics']
        tissue = row['Tissue']
        if omics not in VALID_OMICS or tissue not in VALID_TISSUES:
            invalid_omics_tissue_rows.append(row)
        elif tissue not in VALID_OMICS_TISSUE.get(omics, []):
            invalid_omics_tissue_rows.append(row)
    invalid_omics_tissue = pd.DataFrame(invalid_omics_tissue_rows)
    
    # 유효하지 않은, 존재하지 않는 Project 체크
    invalid_project = df[~df['Project'].isin(VALID_PROJECTS)].copy()
    
    # 중복 데이터 체크 (PatientID, Visit, Omics, Tissue 기준)
    duplicate_keys = df.duplicated(subset=['PatientID', 'Visit', 'Omics', 'Tissue'], keep=False)
    duplicate_data = df[duplicate_keys].sort_values(by=['PatientID', 'Visit', 'Omics', 'Tissue']).copy()
    
    return invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data

def get_valid_data(df):
    # 유효한 데이터만 필터링
    valid_df = df[(df['Visit'].isin(VALID_VISITS)) &
                  (df['Project'].isin(VALID_PROJECTS))].copy()
    
    # Omics-Tissue 유효성 검사
    valid_rows = []
    for index, row in valid_df.iterrows():
        omics = row['Omics']
        tissue = row['Tissue']
        if omics in VALID_OMICS and tissue in VALID_TISSUES:
            if tissue in VALID_OMICS_TISSUE.get(omics, []):
                valid_rows.append(row)
    
    valid_df = pd.DataFrame(valid_rows)
    
    # 중복 제거 (첫 번째 항목 유지)
    valid_df = valid_df.drop_duplicates(subset=['PatientID', 'Visit', 'Omics', 'Tissue'], keep='first')
    
    return valid_df

def save_uploaded_file(uploaded_file):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # 설정 파일 업데이트
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    
    config['last_update'] = datetime.now(datetime.timezone.kst).strftime("%Y-%m-%d %H:%M:%S")
    config['last_updated_by'] = st.session_state.username
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def get_sample_paths(df):
    """
    실제 환경에서는 각 조직의 파일이 저장된 위치(서버 경로 등)를 
    구성 규칙에 맞춰서 반환하도록 구현합니다.
    여기서는 예시로 /data/Project/PatientID/Visit/Omics/Tissue/SampleID 구조로 생성
    """
    sample_paths = {}
    for _, row in df.iterrows():
        path = f"/data/{row['Project']}/{row['PatientID']}/{row['Visit']}/{row['Omics']}/{row['Tissue']}/{row['SampleID']}"
        key = f"{row['PatientID']}_{row['Visit']}_{row['Omics']}_{row['Tissue']}"
        sample_paths[key] = path
    return sample_paths

def get_file_download_link(df, filename, link_text):
    """데이터프레임을 다운로드 가능한 엑셀 링크로 변환"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

#############################################
# 페이지 레이아웃
#############################################
def login_page():
    st.markdown('<div class="main-header">COREA | PRISM Omics Data Status</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="background-color: #F9FAFB; padding: 20px; border-radius: 10px; 
                        box-shadow: 0 1px 3px rgba(0,0,0,0.12);">
                <h3 style="text-align: center; color: #1E3A8A;">로그인</h3>
            """, 
            unsafe_allow_html=True
        )
        
        username = st.text_input("사용자 이름")
        password = st.text_input("비밀번호", type="password")
        
        if st.button("로그인", key="login_button"):
            if username and password:
                success, is_admin = authenticate(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.is_admin = is_admin
                    st.session_state.username = username
                    st.experimental_rerun()
                else:
                    st.error("로그인 실패: 사용자 이름 또는 비밀번호가 잘못되었습니다.")
            else:
                st.warning("사용자 이름과 비밀번호를 모두 입력해주세요.")
        
        st.markdown("</div>", unsafe_allow_html=True)

def main_page():
    st.markdown('<div class="main-header">COREA | PRISM Omics Data Status</div>', unsafe_allow_html=True)
    
    # 상단 네비게이션
    col1, col2, col3 = st.columns([5, 3, 2])
    with col1:
        st.markdown(f"환영합니다, **{st.session_state.username}**님")
    with col2:
        # 마지막 업데이트 정보 표시
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if 'last_update' in config:
                    st.markdown(f"마지막 업데이트: {config['last_update']}")
    with col3:
        if st.button("로그아웃"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()

    # 메뉴 구성
    menu_options = {
        '오믹스 개별 현황': "data_ind_dashboard",
        '오믹스 조합 현황': "data_comb_dashboard",
        '샘플 ID 리스트': "data_id_list"
    }

    if st.session_state.is_admin:
        menu_options.update({"관리자 설정": "data_management"})

    for menu_title, page_name in menu_options.items():
        if st.sidebar.button(menu_title, key=f"menu_{page_name}"):
            st.session_state.page = page_name
            st.experimental_rerun()
    
    # 푸터
    st.markdown(
        """
        <div class="footer">
            © 2025 COREA PRISM Omics Data Status | 개발: WonLab
        </div>
        """, 
        unsafe_allow_html=True
    )


#############################################
# 오믹스 개별 현황 페이지
#############################################
def view_data_ind_dashboard():
    st.markdown('<div class="sub-header">오믹스 데이터 현황</div>', unsafe_allow_html=True)
    
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    # 데이터 요약 정보
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("프로젝트 수", df['Project'].nunique())
    with col2:
        st.metric("총 환자 수", df['PatientID'].nunique())
    with col3:
        st.metric("총 샘플 수", len(df))
    
    # 탭 구성
    dashboard_tabs = st.tabs([
        "코호트별 환자수", 
        "오믹스별 환자수"
    ])
    
    # 탭 1: 코호트별(프로젝트별) 환자수
    with dashboard_tabs[0]:
        st.markdown('<div class="sub-header">코호트 - 오믹스 - Visit 환자수</div>', unsafe_allow_html=True)
        
        projects = sorted(df['Project'].unique())
        project_tabs = st.tabs(projects)
        
        for i, project in enumerate(projects):
            with project_tabs[i]:
                project_df = df[df['Project'] == project]
                
                # 오믹스별 Visit별 환자수 계산
                omics_list = sorted(project_df['Omics'].unique())
                visit_list = sorted(project_df['Visit'].unique())
                
                # 데이터 준비
                result_data = []
                for omics in omics_list:
                    row_data = {'Omics': omics}
                    for visit in visit_list:
                        patient_count = project_df[
                            (project_df['Omics'] == omics) & 
                            (project_df['Visit'] == visit)
                        ]['PatientID'].nunique()
                        row_data[visit] = patient_count
                    # 전체 Visit에 대한 환자수 (중복 제거)
                    row_data['Total'] = project_df[project_df['Omics'] == omics]['PatientID'].nunique()
                    result_data.append(row_data)
                
                # 전체 오믹스에 대한 행 추가
                total_row = {'Omics': 'Total'}
                for visit in visit_list:
                    total_row[visit] = project_df[project_df['Visit'] == visit]['PatientID'].nunique()
                total_row['Total'] = project_df['PatientID'].nunique()
                result_data.append(total_row)
                
                result_df = pd.DataFrame(result_data)
                
                # 데이터 표시
                st.dataframe(result_df, use_container_width=True)
                
                # 다운로드 버튼
                st.markdown(
                    get_file_download_link(
                        result_df,
                        f"cohort_{project}_patient_counts.xlsx",
                        "📊 환자수 데이터 다운로드"
                    ),
                    unsafe_allow_html=True
                )
    
    # 탭 2: 오믹스별 환자수
    with dashboard_tabs[1]:
        st.markdown('<div class="sub-header">오믹스 - 코호트 - Visit 환자수</div>', unsafe_allow_html=True)
        
        omics_list = sorted(df['Omics'].unique())
        omics_tabs = st.tabs(omics_list)
        
        for i, omics in enumerate(omics_list):
            with omics_tabs[i]:
                omics_df = df[df['Omics'] == omics]
                
                # 코호트별(프로젝트별) Visit별 환자수 계산
                projects = sorted(omics_df['Project'].unique())
                visit_list = sorted(omics_df['Visit'].unique())
                
                # 데이터 준비
                result_data = []
                for project in projects:
                    row_data = {'Project': project}
                    for visit in visit_list:
                        patient_count = omics_df[
                            (omics_df['Project'] == project) & 
                            (omics_df['Visit'] == visit)
                        ]['PatientID'].nunique()
                        row_data[visit] = patient_count
                    # 전체 Visit에 대한 환자수
                    row_data['Total'] = omics_df[omics_df['Project'] == project]['PatientID'].nunique()
                    result_data.append(row_data)
                
                # 전체 코호트에 대한 행 추가
                total_row = {'Project': 'Total'}
                for visit in visit_list:
                    total_row[visit] = omics_df[omics_df['Visit'] == visit]['PatientID'].nunique()
                total_row['Total'] = omics_df['PatientID'].nunique()
                result_data.append(total_row)
                
                result_df = pd.DataFrame(result_data)
                
                # 데이터 표시
                st.dataframe(result_df, use_container_width=True)
                
                # 다운로드 버튼
                st.markdown(
                    get_file_download_link(
                        result_df,
                        f"omics_{omics}_patient_counts.xlsx",
                        "📊 환자수 데이터 다운로드"
                    ),
                    unsafe_allow_html=True
                )


#############################################
# 오믹스 조합 현황 페이지
#############################################
def view_data_comb_dashboard():

    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    # 데이터 요약 정보
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("프로젝트 수", df['Project'].nunique())
    with col2:
        st.metric("총 환자 수", df['PatientID'].nunique())
    with col3:
        st.metric("총 샘플 수", len(df))

    projects = sorted(df['Project'].unique())
    project_tabs = st.tabs(projects)
    
    for i, project in enumerate(projects):
        with project_tabs[i]:
            project_df = df[df['Project'] == project]
            
            # 1. 오믹스 조합별 환자수 요약
            st.markdown('<div class="sub-header">오믹스 조합별 환자 수</div>', unsafe_allow_html=True)
            
            # 각 환자별로 가진 오믹스 종류 파악
            patient_omics = {}
            for patient_id in project_df['PatientID'].unique():
                patient_data = project_df[project_df['PatientID'] == patient_id]
                patient_omics[patient_id] = sorted(patient_data['Omics'].unique())
            
            # 오믹스 조합별 환자수 계산
            omics_combinations = {}
            for patient_id, omics_list in patient_omics.items():
                combination = " + ".join(omics_list)
                if combination in omics_combinations:
                    omics_combinations[combination] += 1
                else:
                    omics_combinations[combination] = 1
            
            # 결과 데이터프레임 변환
            combinations_df = pd.DataFrame([
                {"오믹스 조합": combo, "환자 수": count}
                for combo, count in omics_combinations.items()
            ]).sort_values(by="환자 수", ascending=False)
            
            st.dataframe(combinations_df, use_container_width=True)
            
            # 2. 오믹스 및 조직 선택 UI
            st.markdown('<div class="sub-header">선택된 오믹스 조합 현황</div>', unsafe_allow_html=True)

            selected_omics = st.multiselect(
                label="오믹스 선택 (하단에 해당 조직 자동 생성됨)",
                options=sorted(project_df['Omics'].unique()),
                default=sorted(project_df['Omics'].unique()),
                key=f"omics_select_{project}"
            )

            selected_tissues_dict = {}
            for omics in selected_omics:
                with st.expander(f"[조직 선택] {omics}", expanded=True):
                    tissue_options = sorted(project_df[project_df['Omics'] == omics]['Tissue'].unique())
                    selected = st.multiselect(
                        label=f"{omics}의 조직 선택",
                        options=tissue_options,
                        default=tissue_options,
                        key=f"tissue_select_{project}_{omics}"
                    )
                    selected_tissues_dict[omics] = selected
                    
             # 필터링된 환자 및 샘플 정보
            filtered_df = pd.DataFrame()
            for omics, tissues in selected_tissues_dict.items():
                sub_df = project_df[(project_df['Omics'] == omics) & (project_df['Tissue'].isin(tissues))]
                filtered_df = pd.concat([filtered_df, sub_df], ignore_index=True)

            if not filtered_df.empty:
                st.markdown(f"**선택된 조건에 맞는 환자 수:** {filtered_df['PatientID'].nunique()}명")

                pivot_df = pd.pivot_table(
                    filtered_df,
                    values='PatientID',
                    index=['Visit'],
                    columns=['Omics', 'Tissue'],
                    aggfunc=lambda x: len(set(x)),
                    fill_value=0
                )
                st.dataframe(pivot_df, use_container_width=True)

                st.markdown('<div class="sub-header">환자별 샘플 ID</div>', unsafe_allow_html=True)
                sample_data = []
                for pid in sorted(filtered_df['PatientID'].unique()):
                    patient_df = filtered_df[filtered_df['PatientID'] == pid]
                    for visit in sorted(patient_df['Visit'].unique()):
                        visit_df = patient_df[patient_df['Visit'] == visit]
                        row = {'PatientID': pid, 'Visit': visit, 'Date': visit_df['Date'].min()}
                        for omics in selected_omics:
                            for tissue in selected_tissues_dict.get(omics, []):
                                sample_id = visit_df[
                                    (visit_df['Omics'] == omics) & (visit_df['Tissue'] == tissue)
                                ]['SampleID']
                                row[f"{omics}_{tissue}_SampleID"] = sample_id.values[0] if not sample_id.empty else None
                        sample_data.append(row)

                sample_df = pd.DataFrame(sample_data)
                st.dataframe(sample_df, use_container_width=True)

                st.markdown(
                    get_file_download_link(
                        sample_df,
                        f"project_{project}_selected_samples.xlsx",
                        "\U0001F4E5 선택된 샘플 데이터 다운로드"
                    ),
                    unsafe_allow_html=True
                )
            else:
                st.warning("선택된 조건에 해당하는 데이터가 없습니다.")         

#############################################
# 데이터 관리 페이지
#############################################
def view_data_management():
    st.markdown('<div class="sub-header">데이터 관리</div>', unsafe_allow_html=True)
    
    # 전체 데이터 다운로드 버튼
    df = load_data()
    if df is not None:
        st.markdown(
            get_file_download_link(
                df,
                "clinical_data_full.xlsx",
                "📥 전체 데이터 엑셀 다운로드"
            ),
            unsafe_allow_html=True
        )
    
    # 데이터 유효성 검사 결과
    data_validation()

def data_validation():
    st.markdown('<div class="sub-header">데이터 유효성 검사</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    # 유효성 검사 실행
    invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data = get_invalid_data(df)
    valid_df = get_valid_data(df)
    
    # 유효성 검사 결과 요약
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
        if invalid_omics_tissue is not None and not invalid_omics_tissue.empty:
            is_valid_omics_tissue = False
        else:
            is_valid_omics_tissue = True
        
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
    
    # 추가 유효성 통계
    col5, col6 = st.columns(2)
    with col5:
        total_records = len(df)
        valid_records = len(valid_df) if valid_df is not None else 0
        st.metric("유효한 레코드 / 전체 레코드", f"{valid_records} / {total_records}")
    with col6:
        valid_percent = (valid_records / total_records * 100) if total_records > 0 else 0
        st.metric("데이터 유효성 비율", f"{valid_percent:.1f}%")
    
    # 상세 검사 결과 탭
    st.markdown("### 상세 검사 결과")
    tab1, tab2, tab3, tab4 = st.tabs(["Visit 체크", "Omics-Tissue 체크", "Project 체크", "중복 체크"])
    
    with tab1:
        st.info(f"유효한 Visit 값: {', '.join(VALID_VISITS)}")
        if len(invalid_visit) > 0:
            st.dataframe(invalid_visit, use_container_width=True)
        else:
            st.success("모든 Visit 값이 유효합니다.")
    
    with tab2:
        st.info("유효한 Omics-Tissue 조합 예시:")
        valid_combinations = []
        for omics, tissues in VALID_OMICS_TISSUE.items():
            for tissue in tissues:
                valid_combinations.append({"Omics": omics, "Tissue": tissue})
        st.dataframe(pd.DataFrame(valid_combinations), use_container_width=True)
        
        if invalid_omics_tissue is not None and not invalid_omics_tissue.empty:
            st.error("유효하지 않은 Omics-Tissue 조합:")
            st.dataframe(invalid_omics_tissue, use_container_width=True)
        else:
            st.success("모든 Omics-Tissue 조합이 유효합니다.")
    
    with tab3:
        st.info(f"유효한 Project 값: {', '.join(VALID_PROJECTS)}")
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

#############################################
# 관리자 설정 페이지
#############################################
def admin_settings():
    st.markdown('<div class="sub-header">관리자 설정</div>', unsafe_allow_html=True)
    
    admin_tabs = st.tabs(["데이터 업로드", "사용자 관리", "시스템 설정"])
    
    # 데이터 업로드 탭
    with admin_tabs[0]:
        st.markdown("### 데이터 업로드")
        st.markdown("최신 임상 데이터를 업로드하세요. 업로드 후 자동으로 유효성 검사가 수행됩니다.")
        
        uploaded_file = st.file_uploader("Excel 파일 선택", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            if st.button("파일 업로드"):
                # 파일 저장
                save_uploaded_file(uploaded_file)
                st.success(f"파일이 성공적으로 업로드되었습니다: {uploaded_file.name}")
                
                # 데이터 유효성 검사
                st.markdown("### 업로드된 데이터 유효성 검사")
                data_validation()
    
    # 사용자 관리 탭
    with admin_tabs[1]:
        st.markdown("### 사용자 관리")
        
        users = load_users()
        
        # 사용자 목록 표시
        user_data = []
        for username, user_info in users.items():
            user_data.append({
                "사용자명": username,
                "권한": "관리자" if user_info["is_admin"] else "일반 사용자"
            })
        user_df = pd.DataFrame(user_data)
        st.dataframe(user_df, use_container_width=True)
        
        # 새 사용자 추가
        st.markdown("### 새 사용자 추가")
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("사용자명")
        with col2:
            new_password = st.text_input("비밀번호", type="password")
        
        is_admin = st.checkbox("관리자 권한 부여")
        
        if st.button("사용자 추가"):
            if new_username and new_password:
                if new_username in users:
                    st.error(f"'{new_username}' 사용자가 이미 존재합니다.")
                else:
                    users[new_username] = {
                        "password": hashlib.sha256(new_password.encode()).hexdigest(),
                        "is_admin": is_admin
                    }
                    save_users(users)
                    st.success(f"사용자 '{new_username}'가 추가되었습니다.")
                    st.experimental_rerun()
            else:
                st.warning("사용자명과 비밀번호를 모두 입력해주세요.")
        
        # 사용자 삭제
        st.markdown("### 사용자 삭제")
        
        deletable_users = [u for u in users.keys() if u != st.session_state.username]
        if len(deletable_users) == 0:
            st.warning("삭제할 수 있는 다른 사용자가 없습니다.")
        else:
            user_to_delete = st.selectbox("삭제할 사용자 선택", options=deletable_users)
            
            if st.button("사용자 삭제"):
                if user_to_delete:
                    del users[user_to_delete]
                    save_users(users)
                    st.success(f"사용자 '{user_to_delete}'가 삭제되었습니다.")
                    st.experimental_rerun()
    
    # 시스템 설정 탭
    with admin_tabs[2]:
        st.markdown("### 시스템 설정")
        
        # 유효한 값 설정
        st.markdown("#### 유효한 값 설정")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Visit 설정**")
            valid_visits_str = ", ".join(VALID_VISITS)
            new_valid_visits = st.text_area("유효한 Visit 값 (쉼표로 구분)", value=valid_visits_str)
        with col2:
            st.markdown("**Project 설정**")
            valid_projects_str = ", ".join(VALID_PROJECTS)
            new_valid_projects = st.text_area("유효한 Project 값 (쉼표로 구분)", value=valid_projects_str)
        
        st.markdown("#### Omics-Tissue 조합 설정")
        st.info("Omics-Tissue 조합 설정은 현재 코드 상의 VALID_OMICS_TISSUE 사전을 직접 수정하여 변경할 수 있습니다.")
        
        if st.button("설정 저장"):
            """
            실제 구현에서는 입력된 new_valid_visits, new_valid_projects 등을
            VALID_VISITS, VALID_PROJECTS에 반영하고, config.json에 저장하는 로직을 넣을 수 있습니다.
            """
            st.success("설정이 저장되었습니다. (실제 코드에서는 수정 사항을 config에 반영하는 로직 추가 필요)")

#############################################
# 메인 실행 부분
#############################################
def main():
    # 사용자 초기화
    init_users()
    
    # 로그인 상태 체크
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.is_admin = False
        st.session_state.page = "login"

    if not st.session_state.authenticated:
        login_page()
    else:
        page = st.session_state.get("page", "data_ind_dashboard")
        if page == "data_ind_dashboard":
            view_data_ind_dashboard()
        elif page == "data_comb_dashboard":
            view_data_comb_dashboard()
        elif page == "data_id_list":
            st.info("샘플 ID 리스트 페이지 준비 중입니다.")
        elif page == "data_management":
            view_data_management()
        else:
            st.error("페이지를 찾을 수 없습니다.")

if __name__ == "__main__":
    main()
        
