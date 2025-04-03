import streamlit as st
import pandas as pd
import io
import openpyxl
from datetime import datetime

##############################
# 유효성 검사 관련 함수들 예시
##############################
def load_data_from_file(file):
    """업로드된 엑셀 파일을 Pandas DataFrame으로 로드"""
    if file is not None:
        df = pd.read_excel(file)
        return df
    return None

def get_invalid_data(df):
    """유효성 검사를 위한 예시 함수
       - invalid_visit: Visit 범위(V1~V5 등) 밖인 레코드
       - invalid_omics_tissue: 사전에 정의된 omics-tissue 조합에서 벗어나는 레코드
       - invalid_project: Project 값이 유효한지 검사 (예: 내부 사전 정의)
       - duplicate_data: (PatientID, Visit, Omics, Tissue) 중복 레코드
    """
    valid_visits = ["V1","V2","V3","V4","V5"]
    # 예시 valid omics-tissue 조합. 실제로는 DB나 config 파일 등에서 관리 가능
    valid_omics_tissue = [
        ("SNP","Blood"),
        ("SNP","Tissue"),
        ("Methylation","Blood"),
        ("Methylation","Tissue"),
        ("RNAseq","Blood"),
        ("RNAseq","Tissue"),
    ]
    valid_projects = ["ProjectA", "ProjectB"]  # 예시

    # (1) invalid_visit
    invalid_visit = df[~df["Visit"].isin(valid_visits)]
    
    # (2) invalid_omics_tissue
    df_omics_tissue = df[["Omics","Tissue"]].apply(tuple, axis=1)
    valid_combo = df_omics_tissue.isin(valid_omics_tissue)
    invalid_omics_tissue = df[~valid_combo]
    
    # (3) invalid_project
    # 만약 Project 열이 df에 있다고 가정
    if "Project" in df.columns:
        invalid_project = df[~df["Project"].isin(valid_projects)]
    else:
        # Project 열이 없다면 empty DataFrame
        invalid_project = pd.DataFrame()
    
    # (4) duplicate_data
    # (PatientID, Visit, Omics, Tissue)가 동일한 중복 레코드를 찾는다
    duplicate_mask = df.duplicated(subset=["PatientID","Visit","Omics","Tissue"], keep=False)
    duplicate_data = df[duplicate_mask].sort_values(by=["PatientID","Visit","Omics","Tissue"])
    
    return invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data

def get_valid_data(df):
    """유효 레코드만 추출하는 예시 함수"""
    if df is None or df.empty:
        return df
    
    # 위의 get_invalid_data() 로직 활용해서,
    # invalid 레코드를 제외한 데이터만 valid_data로 만든다
    invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data = get_invalid_data(df)
    
    invalid_indices = set(invalid_visit.index) \
                     | set(invalid_omics_tissue.index) \
                     | set(invalid_project.index) \
                     | set(duplicate_data.index)
    valid_df = df[~df.index.isin(invalid_indices)]
    return valid_df

##############################
# 환자 수/샘플 수 계산 예시 함수
##############################
def count_patients_samples(df):
    """
    df에서 환자 수와 샘플 수를 구분해서 리턴하는 예시 함수.
    환자 수는 unique patientID 기준,
    샘플 수는 SampleID 개수 기준이라고 가정.
    """
    num_patients = df["PatientID"].nunique()
    num_samples = df["SampleID"].nunique()
    return num_patients, num_samples

def create_pivot_cohort_omics_visit(df):
    """페이지 1, 2에서 사용할 피벗 테이블"""
    # 예시: (Cohort, Omics, Visit) 별 unique PatientID 수
    # 실제로는 Cohort 컬럼이 있다고 가정
    pivot_df = df.groupby(["Cohort","Omics","Visit"])["PatientID"].nunique().reset_index()
    pivot_df.rename(columns={"PatientID":"PatientCount"}, inplace=True)
    return pivot_df

################################
# 메인 Streamlit 앱 시작
################################
def main():
    st.set_page_config(page_title="임상 데이터 현황", layout="wide")
    st.title("임상 데이터 현황 관리 웹페이지")

    # 간단한 로그인 시뮬레이션
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.is_admin = False

    if not st.session_state.logged_in:
        login()
        return
    else:
        # 로그인 되었다면, 역할에 따라 화면 표시
        if st.session_state.is_admin:
            admin_page()
        else:
            user_page()

def login():
    st.subheader("로그인")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        # 예시 관리자 계정
        if username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.is_admin = True
            st.success("관리자로 로그인되었습니다.")
        # 예시 일반 사용자 계정
        elif username == "user" and password == "user123":
            st.session_state.logged_in = True
            st.session_state.is_admin = False
            st.success("일반 사용자로 로그인되었습니다.")
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

def admin_page():
    st.sidebar.title("관리자 메뉴")
    st.sidebar.write("**업로드/데이터 검증/현황 관리**")

    # 엑셀 파일 업로드
    uploaded_file = st.sidebar.file_uploader("새로운 엑셀 데이터 업로드", type=["xlsx","xls"])
    if uploaded_file is not None:
        df = load_data_from_file(uploaded_file)
        if df is not None:
            st.session_state["raw_data"] = df
            st.session_state["uploaded_file_name"] = uploaded_file.name  # 파일명
            st.success(f"파일 업로드 성공: {uploaded_file.name}")
            
            # 1) 유효성 검사 진행
            st.markdown('<div class="main-header">데이터 유효성 검사</div>', unsafe_allow_html=True)
            invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data = get_invalid_data(df)
            valid_df = get_valid_data(df)

            # 2) 검사 결과 요약 표시
            display_validation_summary(df, invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data, valid_df)

            # 3) 유효한 데이터만 세션에 저장
            st.session_state["valid_data"] = valid_df
        else:
            st.warning("업로드된 파일을 불러오지 못했습니다.")
    
    # 관리자 화면에서도 데이터 현황 페이지(1,2,3 등)를 볼 수 있도록 탭 구성
    show_data_overview()

    # 전체 raw 파일 다운로드 버튼
    if "raw_data" in st.session_state:
        st.download_button(
            label="전체 Raw 파일 다운로드",
            data=convert_df_to_excel_bytes(st.session_state["raw_data"]),
            file_name=f"raw_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # 로그아웃
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.session_state.is_admin = False

def user_page():
    st.sidebar.title("사용자 메뉴")
    st.sidebar.write("**현황 보기** (데이터 업로드 권한 없음)")
    
    show_data_overview()

    # 전체 raw 파일 다운로드 버튼 (가장 최근 업로드된 파일 기준)
    if "raw_data" in st.session_state:
        st.download_button(
            label="전체 Raw 파일 다운로드",
            data=convert_df_to_excel_bytes(st.session_state["raw_data"]),
            file_name=f"raw_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.session_state.is_admin = False

def show_data_overview():
    """페이지 1,2,3에 해당하는 탭 구성 후, 데이터 현황을 표시"""
    if "valid_data" not in st.session_state or st.session_state["valid_data"] is None:
        st.warning("유효한 데이터가 없습니다. 관리자에게 문의하세요.")
        return
    
    df = st.session_state["valid_data"]
    tabs = st.tabs(["페이지1: 코호트별 - 오믹스별 방문자수", 
                    "페이지2: 오믹스별 - 코호트별 방문자수", 
                    "페이지3: 오믹스 조합/다운로드"])

    ############################
    # [페이지 1] 코호트별 탭
    ############################
    with tabs[0]:
        st.subheader("페이지 1: 코호트별 - 오믹스별 Visit별 환자 수")
        # 코호트 목록
        cohorts = df["Cohort"].unique()
        # 각 코호트별 탭
        for c in cohorts:
            sub_df = df[df["Cohort"] == c]
            st.markdown(f"### 코호트: {c}")
            pivot_df = sub_df.groupby(["Omics","Visit"])["PatientID"].nunique().reset_index()
            pivot_df.rename(columns={"PatientID":"환자 수"}, inplace=True)
            st.dataframe(pivot_df, use_container_width=True)
            
            # 전체 환자/샘플 수 표시
            total_patients, total_samples = count_patients_samples(sub_df)
            st.write(f"**{c} 코호트 전체 환자 수**: {total_patients}, **샘플 수**: {total_samples}")
            st.markdown("---")

    ############################
    # [페이지 2] 오믹스별 탭
    ############################
    with tabs[1]:
        st.subheader("페이지 2: 오믹스별 - 코호트별 Visit별 환자 수")
        omics_list = df["Omics"].unique()
        for o in omics_list:
            sub_df = df[df["Omics"] == o]
            st.markdown(f"### 오믹스: {o}")
            pivot_df = sub_df.groupby(["Cohort","Visit"])["PatientID"].nunique().reset_index()
            pivot_df.rename(columns={"PatientID":"환자 수"}, inplace=True)
            st.dataframe(pivot_df, use_container_width=True)
            
            # 전체 환자/샘플 수
            total_patients, total_samples = count_patients_samples(sub_df)
            st.write(f"**{o} 오믹스 전체 환자 수**: {total_patients}, **샘플 수**: {total_samples}")
            st.markdown("---")

    ############################
    # [페이지 3] 코호트별 탭 구성 + 오믹스 조합 요약 + 체크박스 필터 + 다운로드
    ############################
    with tabs[2]:
        st.subheader("페이지 3: 코호트별 오믹스 조합 요약 및 엑셀 다운로드")
        cohorts = df["Cohort"].unique()

        for c in cohorts:
            st.markdown(f"## 코호트: {c}")
            sub_df = df[df["Cohort"] == c]

            # (1) 오믹스 조합별 환자수 요약 (예시: SNP + Methylation 등)
            # 실제 구현에서는 가능한 모든 조합을 만들어서 환자수를 구하거나,
            # 사용자에게 다중 선택받아 확인 가능
            omics_combinations = sub_df.groupby("PatientID")["Omics"].unique()
            # omics_combinations는 각 환자별 어떤 omics 세트를 가지고 있는지 array 형태
            # 이를 간단히 set -> tuple 로 변환하여 groupby
            combo_series = omics_combinations.apply(lambda x: tuple(sorted(set(x))))
            combo_counts = combo_series.value_counts().reset_index()
            combo_counts.columns = ["Omics조합", "환자수"]
            st.dataframe(combo_counts)

            # (2) 오믹스/티슈 체크박스 선택 -> 필터링
            unique_omics = sorted(sub_df["Omics"].unique())
            unique_tissue = sorted(sub_df["Tissue"].unique())
            selected_omics = st.multiselect(f"[{c} 코호트] 오믹스 선택", unique_omics)
            selected_tissue = st.multiselect(f"[{c} 코호트] Tissue 선택", unique_tissue)

            if selected_omics and selected_tissue:
                filtered_df = sub_df[sub_df["Omics"].isin(selected_omics) & sub_df["Tissue"].isin(selected_tissue)]
                # visit별 환자 수
                pivot_df = filtered_df.groupby(["Omics","Tissue","Visit"])["PatientID"].nunique().reset_index()
                pivot_df.rename(columns={"PatientID":"환자 수"}, inplace=True)
                st.dataframe(pivot_df, use_container_width=True)
                
                # (3) 선택된 항목에 대한 [환자ID, Visit, Date, Omics1_Tissue1_SampleID, ...] 형태 엑셀 다운로드
                # 이를 구현하기 위해서는 "wide" 형태의 피벗 작업이 필요
                # 간단 예시:
                wide_df = create_wide_sample_table(filtered_df)
                st.dataframe(wide_df.head(), use_container_width=True)

                # 엑셀 다운로드 버튼
                download_xlsx = convert_df_to_excel_bytes(wide_df)
                st.download_button(
                    label=f"체크 항목 엑셀 다운로드 ({c} 코호트)",
                    data=download_xlsx,
                    file_name=f"checked_samples_{c}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            st.markdown("---")

######################
# 유효성 검사 결과 요약
######################
def display_validation_summary(df, invalid_visit, invalid_omics_tissue, invalid_project, duplicate_data, valid_df):
    if df is None:
        st.warning("데이터가 없습니다. 먼저 Excel 파일을 업로드해주세요.")
        return
    total_records = len(df)
    valid_records = len(valid_df) if valid_df is not None else 0

    is_valid_visit = (len(invalid_visit) == 0)
    is_valid_omics_tissue = (len(invalid_omics_tissue) == 0)
    is_valid_project = (len(invalid_project) == 0)
    is_valid_duplicate = (len(duplicate_data) == 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_visit else 'error-box'}">
                <h4>Visit 체크</h4>
                <p>{'정상' if is_valid_visit else f'오류 발견 ({len(invalid_visit)}건)'}</p>
                <p>{'모든 Visit 값이 V1-V5 범위 내에 있습니다' if is_valid_visit else f'{len(invalid_visit)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_omics_tissue else 'error-box'}">
                <h4>Omics-Tissue 체크</h4>
                <p>{'정상' if is_valid_omics_tissue else f'오류 발견 ({len(invalid_omics_tissue)}건)'}</p>
                <p>{'모든 Omics-Tissue 조합이 유효합니다' if is_valid_omics_tissue else f'{len(invalid_omics_tissue)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_project else 'error-box'}">
                <h4>Project 체크</h4>
                <p>{'정상' if is_valid_project else f'오류 발견 ({len(invalid_project)}건)'}</p>
                <p>{'모든 Project 값이 유효합니다' if is_valid_project else f'{len(invalid_project)}개 레코드에 문제가 있습니다.'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f"""
            <div class="{'success-box' if is_valid_duplicate else 'error-box'}">
                <h4>중복 체크</h4>
                <p>{'정상' if is_valid_duplicate else f'오류 발견 ({len(duplicate_data)}건)'}</p>
                <p>{'중복 레코드가 없습니다' if is_valid_duplicate else f'{len(duplicate_data)}개 레코드가 중복되었습니다.'}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    col5, col6 = st.columns(2)
    with col5:
        st.metric("유효한 레코드 / 전체 레코드", f"{valid_records} / {total_records}")
    with col6:
        valid_percent = (valid_records / total_records * 100) if total_records > 0 else 0
        st.metric("데이터 유효성 비율", f"{valid_percent:.1f}%")

    st.markdown("### 상세 검사 결과")
    tab1, tab2, tab3, tab4 = st.tabs(["Visit 체크", "Omics-Tissue 체크", "Project 체크", "중복 체크"])
    # 유효 Visit 목록(예시)
    valid_visits = ["V1","V2","V3","V4","V5"]
    # 유효 Omics-Tissue 목록(예시)
    valid_omics_tissue = [
        ("SNP","Blood"),
        ("SNP","Tissue"),
        ("Methylation","Blood"),
        ("Methylation","Tissue"),
        ("RNAseq","Blood"),
        ("RNAseq","Tissue"),
    ]
    # 유효 Project 값(예시)
    valid_projects = ["ProjectA", "ProjectB"]

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

#############################################
# Wide 형태 변환 예시 (Omics_Tissue별 SampleID 펼치기)
#############################################
def create_wide_sample_table(df):
    """
    [환자ID, Visit, Date, Omics1_Tissue1_SampleID, Omics1_Tissue2_SampleID, ...]
    형태로 피벗하는 예시 함수.
    """
    # 우선 (PatientID, Visit, Omics, Tissue)별 SampleID를 pivot
    # pivot_table로 Omics_Tissue를 컬럼으로 두고, 값으로 SampleID를 가져온다고 가정
    df["Omics_Tissue"] = df["Omics"] + "_" + df["Tissue"]
    wide_df = df.pivot_table(
        index=["PatientID","Visit","Date"], 
        columns="Omics_Tissue",
        values="SampleID",
        aggfunc=lambda x: ",".join(x)  # 같은 셀에 여러 SampleID가 있을 수 있어 쉼표로 연결
    ).reset_index()
    return wide_df

#############################################
# DataFrame -> Excel 변환용 헬퍼 함수
#############################################
def convert_df_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    processed_data = output.getvalue()
    return processed_data

#############################################
# Streamlit 앱 실행 엔트리 포인트
#############################################
if __name__ == "__main__":
    main()
