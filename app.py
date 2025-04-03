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

#############################################
# 설정 및 상수
#############################################
CONFIG_FILE = "config.json"
DATA_FILE = "data/clinical_data.xlsx"
USER_FILE = "data/users.json"

VALID_VISITS = ["V1", "V2", "V3", "V4", "V5"]
VALID_OMICS = ["SNP", "Methylation", "RNA", "Proteomics", "Metabolomics"]
VALID_TISSUES = ["Blood", "Urine", "Tissue", "Stool"]
VALID_PROJECTS = ["Project A", "Project B", "Project C"]

# 오믹스별 허용 Tissue(계층적 선택에 활용)
VALID_OMICS_TISSUE = {
    "SNP": ["Blood"],
    "Methylation": ["Blood", "Tissue"],
    "RNA": ["Blood", "Tissue"],
    "Proteomics": ["Blood", "Urine"],
    "Metabolomics": ["Blood", "Urine", "Stool"]
}

# 디렉토리 생성
os.makedirs("data", exist_ok=True)

#############################################
# 페이지 설정 (Streamlit)
#############################################
st.set_page_config(
    page_title="임상 데이터 관리 시스템",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

#############################################
# CSS 스타일 정의
#############################################
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
    .footer {
        margin-top: 50px;
        text-align: center;
        color: #6B7280;
        font-size: 14px;
        border-top: 1px solid #E5E7EB;
        padding-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

#############################################
# 사용자 관리 함수
#############################################
def init_users():
    """기본 users.json이 없을 경우 생성"""
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
# 데이터 로딩 & 저장 함수
#############################################
def load_data():
    """Excel 파일을 불러와 DataFrame으로 반환"""
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_excel(DATA_FILE)
            # 필수 컬럼 확인
            required_cols = ["PatientID", "Visit", "Omics", "Tissue", "SampleID", "Date", "Project"]
            if not all(col in df.columns for col in required_cols):
                st.error(f"데이터 파일에 필수 컬럼이 누락되었습니다. 필요한 컬럼: {', '.join(required_cols)}")
                return None
            
            # 날짜 형식 변환
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            return df
        except Exception as e:
            st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
            return None
    return None

def save_uploaded_file(uploaded_file):
    """새 엑셀 파일 업로드 시 파일을 저장하고 config 갱신"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # 설정 파일 업데이트
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    
    config['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    config['last_updated_by'] = st.session_state.username
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

#############################################
# 데이터 유효성 검사
#############################################
def get_invalid_data(df):
    """유효성 검사에 필요한 invalid 리스트 반환"""
    # (1) Visit 체크
    invalid_visit = df[~df['Visit'].isin(VALID_VISITS)].copy()
    
    # (2) Omics-Tissue 조합 체크
    invalid_omics_tissue_rows = []
    for _, row in df.iterrows():
        omics = row['Omics']
        tissue = row['Tissue']
        if omics not in VALID_OMICS or tissue not in VALID_TISSUES:
            invalid_omics_tissue_rows.append(row)
        else:
            # 오믹스와 티슈가 VALID_OMICS_TISSUE에 맞는지
            valid_tissues = VALID_OMICS_TISSUE.get(omics, [])
            if tissue not in valid_tissues:
                invalid_omics_tissue_rows.append(row)
    invalid_omics_tissue = pd.DataFrame(invalid_omics_tissue_rows)
    
    # (3) Project 체크
    invalid_project = df[~df['Project'].isin(VALID_PROJECTS)].copy()
    
    # (4) 중복 체크 (PatientID, Visit, Omics, Tissue)
    duplicate_keys = df.duplicated(subset=['PatientID', 'Visit', 'Omics', 'Tissue'], keep=False)
    duplicate_data = df[duplicate_keys].sort_values(by=['PatientID','Visit','Omics','Tissue']).copy()
    
    return invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data

def get_valid_data(df):
    """유효한 레코드만 추출"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 유효 Visit & Project 필터
    valid_df = df[(df['Visit'].isin(VALID_VISITS)) &
                  (df['Project'].isin(VALID_PROJECTS))].copy()
    
    # Omics-Tissue 검사 통과하는 행만
    valid_rows = []
    for _, row in valid_df.iterrows():
        omics = row['Omics']
        tissue = row['Tissue']
        if omics in VALID_OMICS:
            if tissue in VALID_OMICS_TISSUE.get(omics, []):
                valid_rows.append(row)
    valid_df = pd.DataFrame(valid_rows)
    
    # 중복 제거 (최초 레코드만 유효)
    valid_df = valid_df.drop_duplicates(subset=['PatientID','Visit','Omics','Tissue'], keep='first')
    return valid_df

#############################################
# 엑셀 다운로드 링크 생성
#############################################
def get_file_download_link(df, filename, link_text):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

#############################################
# 샘플 파일 경로 예시
#############################################
def get_sample_paths(df):
    """
    (Omics, Tissue)별 파일 위치를 가정하여 /data/프로젝트/환자ID/Visit/Omics/Tissue/SampleID 로 만듦
    """
    sample_paths = {}
    for _, row in df.iterrows():
        path = f"/data/{row['Project']}/{row['PatientID']}/{row['Visit']}/{row['Omics']}/{row['Tissue']}/{row['SampleID']}"
        key = (row['PatientID'], row['Visit'], row['Omics'], row['Tissue'])
        sample_paths[key] = path
    return sample_paths

#############################################
# 페이지 1: "코호트별 환자 Pivot" 페이지
#############################################
def view_cohort_pivot_page():
    st.markdown('<div class="sub-header">코호트별 환자 Pivot</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None or df.empty:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    st.info("코호트(Project), PatientID, Visit을 행으로 두고, (Omics, Tissue)를 열로 하여 SampleID를 피벗한 표입니다.")
    
    # 유효 데이터만 사용
    valid_df = get_valid_data(df)
    if valid_df.empty:
        st.warning("유효한 데이터가 없습니다.")
        return
    
    # pivot: index=[Project, PatientID, Visit], columns=[Omics, Tissue], values=SampleID
    pivot_df = valid_df.pivot_table(
        index=["Project", "PatientID", "Visit"],
        columns=["Omics", "Tissue"],
        values="SampleID",
        aggfunc=lambda x: ", ".join(sorted(set(x)))  # 여러 샘플ID면 쉼표로 연결
    )
    pivot_df = pivot_df.reset_index()  # MultiIndex -> 컬럼화
    
    st.dataframe(pivot_df, use_container_width=True)
    
    # 엑셀 다운로드
    download_link = get_file_download_link(pivot_df, "cohort_patient_pivot.xlsx", "📥 Pivot 데이터 다운로드")
    st.markdown(download_link, unsafe_allow_html=True)

#############################################
# 페이지 2: "데이터 현황" (대시보드-like)
#############################################
def view_data_dashboard():
    st.markdown('<div class="sub-header">데이터 현황</div>', unsafe_allow_html=True)
    df = load_data()
    if df is None or df.empty:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    
    # 상단 요약 정보
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("총 환자 수", df['PatientID'].nunique())
    with c2:
        st.metric("총 샘플 수", len(df))
    with c3:
        st.metric("프로젝트 수", df['Project'].nunique())
    with c4:
        max_date = df['Date'].max()
        date_str = max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else "N/A"
        st.metric("가장 최근 샘플 일자", date_str)
    
    # 아래에 세부 섹션 구성
    st.markdown("---")
    st.markdown("### (1) 코호트별(프로젝트) - 오믹스별 - Tissue - Visit별 환자 수")
    st.info("**[요청사항]** Tissue를 추가하고, Total 행 없이, Total 열은 유지합니다.")

    projects = sorted(df['Project'].unique())
    for project in projects:
        st.markdown(f"#### 프로젝트: {project}")
        proj_df = df[df['Project'] == project]
        omics_list = sorted(proj_df['Omics'].unique())
        visit_list = sorted(proj_df['Visit'].unique())
        tissue_list = sorted(proj_df['Tissue'].unique())
        
        # 결과를 만들어 담을 리스트
        rows_data = []
        for omics in omics_list:
            for tissue in tissue_list:
                row_data = {
                    "Omics": omics,
                    "Tissue": tissue
                }
                # visit별 환자 수
                sub_df = proj_df[(proj_df['Omics'] == omics) & (proj_df['Tissue'] == tissue)]
                for visit in visit_list:
                    count_patients = sub_df[sub_df['Visit'] == visit]['PatientID'].nunique()
                    row_data[visit] = count_patients
                # total 열(이 Omics+Tissue 전체 Visit에서 환자 수)
                row_data["Total"] = sub_df['PatientID'].nunique()
                
                # 만약 전부 0이라면(해당 tissue에 sample 없음), 굳이 표시 안할 수도 있으나
                # 여기서는 그대로 표시한다고 가정
                rows_data.append(row_data)
        
        result_df = pd.DataFrame(rows_data)
        # visit_list 순서대로 컬럼 정렬
        col_order = ["Omics", "Tissue"] + visit_list + ["Total"]
        result_df = result_df[col_order]
        
        st.dataframe(result_df, use_container_width=True)
        
        # 다운로드
        link = get_file_download_link(result_df, f"project_{project}_patient_counts.xlsx", "📥 다운로드")
        st.markdown(link, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### (2) 오믹스별 - 코호트(Project) - Tissue - Visit별 환자 수")
    omics_list_all = sorted(df['Omics'].unique())
    for omics in omics_list_all:
        st.markdown(f"#### 오믹스: {omics}")
        omics_df = df[df['Omics'] == omics]
        projects = sorted(omics_df['Project'].unique())
        visit_list = sorted(omics_df['Visit'].unique())
        tissue_list = sorted(omics_df['Tissue'].unique())
        
        rows_data = []
        for project in projects:
            for tissue in tissue_list:
                row_data = {
                    "Project": project,
                    "Tissue": tissue
                }
                # visit별 환자 수
                sub_df = omics_df[(omics_df['Project'] == project) & (omics_df['Tissue'] == tissue)]
                for visit in visit_list:
                    count_patients = sub_df[sub_df['Visit'] == visit]['PatientID'].nunique()
                    row_data[visit] = count_patients
                # total 열
                row_data["Total"] = sub_df['PatientID'].nunique()
                rows_data.append(row_data)
        
        result_df = pd.DataFrame(rows_data)
        col_order = ["Project", "Tissue"] + visit_list + ["Total"]
        result_df = result_df[col_order]
        
        st.dataframe(result_df, use_container_width=True)
        
        link = get_file_download_link(result_df, f"omics_{omics}_patient_counts.xlsx", "📥 다운로드")
        st.markdown(link, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### (3) 오믹스 조합별 환자 수")
    st.info("오믹스별로 다른 Tissue를 계층적으로 선택할 수 있도록 구성하고, 선택한 (Omics, Tissue) 조합에 대한 Visit별 환자수를 [행=Omics, 열=Visit] 으로 표시합니다.")
    
    # (3-a) 환자별 오믹스 조합 개요
    valid_df = get_valid_data(df)
    if valid_df.empty:
        st.warning("유효한 데이터가 없습니다.")
        return
    
    # 환자별로 어떤 오믹스 세트를 가지고 있는지
    patient_omics_map = {}
    for pid in valid_df['PatientID'].unique():
        sub = valid_df[valid_df['PatientID'] == pid]
        omics_set = sorted(sub['Omics'].unique())
        combo_key = " + ".join(omics_set)
        patient_omics_map[pid] = combo_key
    
    # 오믹스 조합 별 환자수
    combo_counts = {}
    for pid, combo in patient_omics_map.items():
        combo_counts[combo] = combo_counts.get(combo, 0) + 1
    
    combos_df = pd.DataFrame([
        {"오믹스 조합": c, "환자수": n}
        for c, n in combo_counts.items()
    ]).sort_values("환자수", ascending=False)
    st.dataframe(combos_df, use_container_width=True)
    
    # (3-b) 계층적 선택 (오믹스 -> Tissue) + Visit별 환자수
    st.markdown("#### 오믹스 및 조직 계층적 선택")
    
    # 1) 오믹스 멀티셀렉트
    selected_omics = st.multiselect("오믹스 선택", VALID_OMICS, [])
    
    # 2) 오믹스별 Tissue 선택
    omics_tissue_dict = {}
    if selected_omics:
        for om in selected_omics:
            valid_tissues = VALID_OMICS_TISSUE.get(om, [])
            chosen_tissues = st.multiselect(f"[{om}] 선택할 Tissue", valid_tissues, default=valid_tissues)
            omics_tissue_dict[om] = chosen_tissues
    
    # 필터링용 (Omics, Tissue) 세트 만들기
    selected_pairs = []
    for om in omics_tissue_dict:
        for t in omics_tissue_dict[om]:
            selected_pairs.append((om, t))
    
    if selected_pairs:
        # 해당 (Omics, Tissue) 중 하나라도 해당되면 포함하도록 필터
        filtered_list = []
        for (om, t) in selected_pairs:
            sub = valid_df[(valid_df['Omics'] == om) & (valid_df['Tissue'] == t)]
            filtered_list.append(sub)
        final_filtered = pd.concat(filtered_list).drop_duplicates()
        
        st.markdown(f"**선택된 (Omics, Tissue) 조합 개수:** {len(selected_pairs)}")
        st.markdown(f"**필터링된 환자 수:** {final_filtered['PatientID'].nunique()}")
        
        if not final_filtered.empty:
            # (3-c) Visit별 환자수 (행=Omics, 열=Visit)
            visit_values = sorted(final_filtered['Visit'].unique())
            row_data = []
            # Omics 별로 행
            for om in sorted(omics_tissue_dict.keys()):
                # 해당 omics로 필터
                sub_omics_df = final_filtered[final_filtered['Omics'] == om]
                # Tissue는 여러 개일 수 있음
                # (Omics, Tissue)마다 한 번에 합산해서 환자수를 구해도 되고,
                # Omics 단일 레벨로만 볼 수도 있음(문제에서 '행=Omics, 열=Visit'이라고 했으므로 Tissue 구분 없이 합산)
                row = {"Omics": om}
                for v in visit_values:
                    row[v] = sub_omics_df[sub_omics_df['Visit'] == v]['PatientID'].nunique()
                row_data.append(row)
            
            pivot_df = pd.DataFrame(row_data)
            st.markdown("#### 선택된 (Omics, Tissue)에 대한 Visit별 환자수")
            st.dataframe(pivot_df, use_container_width=True)
            
            # (3-d) 샘플 ID 및 파일 경로는 웹페이지에서 안 보여주고, "엑셀 다운로드"만
            # 이를 위해 final_filtered를 환자ID/Visit 별로 정리한 엑셀을 생성
            sample_data = []
            for pid in sorted(final_filtered['PatientID'].unique()):
                sub_pid = final_filtered[final_filtered['PatientID'] == pid]
                for v in sorted(sub_pid['Visit'].unique()):
                    sub_visit = sub_pid[sub_pid['Visit'] == v]
                    row_info = {
                        "PatientID": pid,
                        "Visit": v,
                        "Date": sub_visit['Date'].min()
                    }
                    # Omics_Tissue별 SampleID
                    # (선택된 pairs만 대상)
                    for (om, t) in selected_pairs:
                        sub_samp = sub_visit[(sub_visit['Omics'] == om) & (sub_visit['Tissue'] == t)]
                        if not sub_samp.empty:
                            row_info[f"{om}_{t}_SampleID"] = ", ".join(sub_samp['SampleID'].unique())
                        
                    sample_data.append(row_info)
            
            sample_df = pd.DataFrame(sample_data)
            
            # 파일 경로도 엑셀에 포함하고 싶다면, 예: "FilePath" 컬럼 추가
            # 여기서는 SampleID 1개당 1 경로라고 가정하기 어렵지만,
            # 예시로 첫 번째 SampleID만 path를 넣는 식:
            paths = get_sample_paths(final_filtered)
            
            # paths의 key=(PatientID,Visit,Omics,Tissue)
            # sample_df에는 여러 (Omics,Tissue)별 SampleID가 들어갈 수 있으므로
            # 간단히 "대표 경로"만 넣거나, 별도 로직이 필요합니다.
            # 여기서는 생략하거나, 혹은 row별로 "대표 오믹스"만 넣는 등 원하는 방식으로 구성 가능.

            # 엑셀 다운로드 링크(샘플 ID & 경로)
            download_link = get_file_download_link(
                sample_df,
                "selected_omics_tissues_samples.xlsx",
                "📥 샘플 데이터(엑셀) 다운로드"
            )
            st.markdown(download_link, unsafe_allow_html=True)
        else:
            st.warning("선택한 (Omics, Tissue)에 해당하는 데이터가 없습니다.")

#############################################
# 페이지 3: "데이터 관리" (업로드 & 유효성 검사)
#############################################
def view_data_management():
    st.markdown('<div class="sub-header">데이터 관리</div>', unsafe_allow_html=True)
    
    df = load_data()
    if df is not None and not df.empty:
        # 전체 데이터 다운로드
        link = get_file_download_link(df, "clinical_data_full.xlsx", "📥 전체 데이터 다운로드")
        st.markdown(link, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 데이터 유효성 검사")
    data_validation_panel()

def data_validation_panel():
    df = load_data()
    if df is None or df.empty:
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
                <p>{'정상' if is_valid_visit else f'오류 ({len(invalid_visit)}건)'}</p>
                <p>{'모든 Visit 값이 V1-V5 범위입니다' if is_valid_visit else f'{len(invalid_visit)}개 레코드에서 유효하지 않은 Visit'}</p>
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
                <p>{'정상' if is_valid_omics_tissue else f'오류 ({len(invalid_omics_tissue)}건)'}</p>
                <p>{'모든 Omics-Tissue가 유효합니다' if is_valid_omics_tissue else f'{len(invalid_omics_tissue)}개 레코드가 유효하지 않은 조합'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    with col3:
        is_valid_project = (len(invalid_project) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_project else 'error-box'}">
                <h4>Project 체크</h4>
                <p>{'정상' if is_valid_project else f'오류 ({len(invalid_project)}건)'}</p>
                <p>{'모든 Project 값이 유효합니다' if is_valid_project else f'{len(invalid_project)}개 레코드에서 잘못된 Project'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    with col4:
        is_valid_duplicate = (len(duplicate_data) == 0)
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_duplicate else 'error-box'}">
                <h4>중복 체크</h4>
                <p>{'정상' if is_valid_duplicate else f'오류 ({len(duplicate_data)}건)'}</p>
                <p>{'중복 레코드가 없습니다' if is_valid_duplicate else f'{len(duplicate_data)}개 레코드가 중복되었습니다.'}</p>
            </div>
            """, unsafe_allow_html=True
        )
    
    total_records = len(df)
    valid_records = len(valid_df)
    st.metric("유효 레코드 / 전체 레코드", f"{valid_records} / {total_records}")
    ratio = (valid_records / total_records)*100 if total_records>0 else 0
    st.metric("데이터 유효성 비율", f"{ratio:.1f}%")
    
    st.markdown("#### 상세 결과")
    tab1, tab2, tab3, tab4 = st.tabs(["Visit", "Omics-Tissue", "Project", "중복"])
    
    with tab1:
        st.info(f"유효한 Visit: {', '.join(VALID_VISITS)}")
        if not invalid_visit.empty:
            st.dataframe(invalid_visit, use_container_width=True)
        else:
            st.success("문제 없음")
    
    with tab2:
        st.info("VALID_OMICS_TISSUE:")
        combos = []
        for om, tis_list in VALID_OMICS_TISSUE.items():
            for t in tis_list:
                combos.append({"Omics": om, "Tissue": t})
        st.dataframe(pd.DataFrame(combos), use_container_width=True)
        
        if invalid_omics_tissue is not None and not invalid_omics_tissue.empty:
            st.error("유효하지 않은 조합 레코드")
            st.dataframe(invalid_omics_tissue, use_container_width=True)
        else:
            st.success("문제 없음")
    
    with tab3:
        st.info(f"유효한 Project: {', '.join(VALID_PROJECTS)}")
        if not invalid_project.empty:
            st.dataframe(invalid_project, use_container_width=True)
        else:
            st.success("문제 없음")
    
    with tab4:
        st.info("중복 기준: (PatientID, Visit, Omics, Tissue)가 동일")
        if not duplicate_data.empty:
            st.dataframe(duplicate_data, use_container_width=True)
        else:
            st.success("중복 레코드 없음")

#############################################
# 페이지 4: "관리자 설정"
#############################################
def admin_settings():
    st.markdown('<div class="sub-header">관리자 설정</div>', unsafe_allow_html=True)
    
    st.markdown("### 1) 데이터 업로드")
    uploaded_file = st.file_uploader("Excel 파일 선택", type=["xlsx","xls"])
    if uploaded_file is not None:
        if st.button("업로드 실행"):
            save_uploaded_file(uploaded_file)
            st.success(f"파일 '{uploaded_file.name}'이 업로드 되었습니다.")
            st.markdown("#### 업로드 후 유효성 검사")
            data_validation_panel()

    st.markdown("---")
    st.markdown("### 2) 사용자 관리")
    users = load_users()
    
    # 사용자 목록 표시
    st.subheader("사용자 목록")
    user_data = []
    for uname, info in users.items():
        user_data.append({
            "사용자명": uname,
            "권한": "관리자" if info["is_admin"] else "일반"
        })
    if user_data:
        user_df = pd.DataFrame(user_data)
        st.dataframe(user_df, use_container_width=True)
    else:
        st.write("등록된 사용자가 없습니다.")
    
    # 새 사용자 추가
    st.subheader("새 사용자 추가")
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("사용자명")
    with col2:
        new_password = st.text_input("비밀번호", type="password")
    
    is_admin = st.checkbox("관리자 권한")
    
    if st.button("사용자 추가"):
        if new_username and new_password:
            if new_username in users:
                st.error(f"이미 존재하는 사용자명입니다: {new_username}")
            else:
                users[new_username] = {
                    "password": hashlib.sha256(new_password.encode()).hexdigest(),
                    "is_admin": is_admin
                }
                save_users(users)
                st.success(f"사용자 '{new_username}' 추가 완료.")
                st.experimental_rerun()
        else:
            st.warning("사용자명과 비밀번호를 입력해주세요.")
    
    # 사용자 삭제
    st.subheader("사용자 삭제")
    deletable_users = [u for u in users.keys() if u != st.session_state.username]
    if deletable_users:
        user_to_delete = st.selectbox("삭제할 사용자 선택", options=deletable_users)
        if st.button("삭제 실행"):
            del users[user_to_delete]
            save_users(users)
            st.success(f"사용자 '{user_to_delete}' 삭제 완료.")
            st.experimental_rerun()
    else:
        st.info("삭제 가능한 다른 사용자가 없습니다 (현재 로그인 계정 제외).")
    
    st.markdown("---")
    st.markdown("### 3) 시스템 설정 (예시)")
    st.info("코드 상단의 VALID_OMICS_TISSUE 등 상수를 수정하거나, config.json과 users.json을 수정해 시스템을 조정할 수 있습니다.")

#############################################
# 메인 실행 (페이지 라우팅)
#############################################
def main():
    # 1) 사용자 초기화
    init_users()
    
    # 2) 로그인 상태 체크
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.is_admin = False
    
    if not st.session_state.authenticated:
        login_page()
    else:
        main_page()

def login_page():
    st.markdown('<div class="main-header">임상 데이터 관리 시스템 로그인</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style="background-color:#F9FAFB; padding:20px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <h4 style="text-align:center;">로그인</h4>
        """, unsafe_allow_html=True)
        
        username = st.text_input("사용자 이름")
        password = st.text_input("비밀번호", type="password")
        
        if st.button("로그인"):
            success, is_admin = authenticate(username, password)
            if success:
                st.session_state.authenticated = True
                st.session_state.is_admin = is_admin
                st.session_state.username = username
                st.experimental_rerun()
            else:
                st.error("로그인 실패: 사용자 이름 또는 비밀번호가 잘못되었습니다.")
        
        st.markdown("</div>", unsafe_allow_html=True)

def main_page():
    st.markdown('<div class="main-header">임상 데이터 관리 시스템</div>', unsafe_allow_html=True)
    
    # 상단 로그아웃 / 마지막 업데이트 정보
    with st.container():
        c1, c2, c3 = st.columns([4,4,2])
        with c1:
            st.write(f"**환영합니다**, {st.session_state.username} 님")
        with c2:
            # config.json에서 마지막 업데이트 정보
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                last_update = config.get("last_update", "N/A")
                st.write(f"마지막 업데이트: {last_update}")
        with c3:
            if st.button("로그아웃"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.experimental_rerun()
    
    # 사이드바 메뉴
    menu_options = [
        "데이터 현황",
        "코호트별 환자 Pivot",
        "데이터 관리"
    ]
    if st.session_state.is_admin:
        menu_options.append("관리자 설정")
    
    choice = st.sidebar.radio("페이지 선택", menu_options)
    
    if choice == "데이터 현황":
        view_data_dashboard()
    elif choice == "코호트별 환자 Pivot":
        view_cohort_pivot_page()
    elif choice == "데이터 관리":
        view_data_management()
    elif choice == "관리자 설정":
        admin_settings()

#############################################
# 엔트리 포인트
#############################################
if __name__ == "__main__":
    main()
