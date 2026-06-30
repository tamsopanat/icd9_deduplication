import streamlit as st
import pandas as pd
import json
import collections
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

st.set_page_config(page_title="Medical Coder Workspace", layout="wide")

# --- 1. DATA LOADING & CACHING ---
@st.cache_data
def load_data():
    with open('./data/icd9-cm-2015-code.json', 'r') as f:
        icd9_raw = json.load(f)
    
    title_map = {}
    for key, data in icd9_raw.items():
        if 'code' in data and 'title' in data:
            title_map[key] = data['title']
            
    valid_code = list(title_map.keys())
    
    includeMap = pd.read_excel('./result/icd9_inclusion_mapping_summary_TFIDF.xlsx', dtype='string')
    includeMap_dict = {row['Code'] : row['Code_include_expand'].split(', ') for i, row in includeMap.iterrows()}
    
    combineCode = pd.read_excel('./result/combine_code_summary.xlsx', dtype='string')
    combineCode_dict = {row['code_combine'] : [row['code_left'], row['code_right']] for i,row in combineCode.iterrows()}
    
    with open('./result/icd9_codeAlso.json', 'r') as f:
        code_also_dict = json.load(f)
        
    return valid_code, includeMap_dict, combineCode_dict, code_also_dict, title_map

try:
    valid_code, includeMap_dict, combineCode_dict, code_also_dict, title_map = load_data()
except Exception as e:
    st.error("Error loading data files. Please check paths.")
    st.stop()


# --- 2. SESSION STATE MANAGEMENT ---
if 'input_codes' not in st.session_state:
    st.session_state.input_codes = ["8331", "833",
                                    "3897", "8952",
                                    "1733", "1735",
                                    "0056", "0057", 
                                    "0044", "0045"]
if 'stage' not in st.session_state:
    st.session_state.stage = 'drafting'
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = {}


# --- 3. UI: HEADER ---
st.title("🗂️ Coder Workspace: ICD-9 Deduplication")
st.markdown("---")

# --- 4. STAGE 1: DRAFTING ---
if st.session_state.stage == 'drafting':
    st.subheader("1. Enter Diagnosis Codes")
    
    cols = st.columns(4)
    for i, code in enumerate(st.session_state.input_codes):
        with cols[i % 4]:
            st.session_state.input_codes[i] = st.text_input(
                f"Code {i+1}", value=code, key=f"input_{i}"
            )
            
    if st.button("➕ Add Another Code"):
        st.session_state.input_codes.append("")
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🔍 Analyze Codes", type="primary"):
        cleaned_codes = [c.strip() for c in st.session_state.input_codes if c.strip()]
        results = {}
        
        # Initialize default state
        for c in cleaned_codes:
            results[c] = {"title": title_map.get(c, "Title not found"), "status": "Keep", "reason": "Valid", "warning": None}
            
        # 1. Invalid Check
        for c in cleaned_codes:
            if c not in valid_code:
                results[c] = {"title": "Unknown Code", "status": "Remove", "reason": "Invalid code", "warning": None}
                
        # 2. Less Detailed Check
        sorted_codes = sorted(cleaned_codes, key=len, reverse=True)
        kept_so_far = []
        for c in sorted_codes:
            if results[c]["status"] == "Remove": continue
            matching_kept = next((k for k in kept_so_far if k.startswith(c)), None)
            if matching_kept:
                results[c].update({"status": "Remove", "reason": f"Less detailed version of '{matching_kept}'"})
            else:
                kept_so_far.append(c)
                
        # 3. Inclusion Check
        for parent_code in cleaned_codes:
            if parent_code in includeMap_dict and results[parent_code]["status"] != "Remove":
                for inc_code in includeMap_dict[parent_code]:
                    if inc_code in results:
                        results[inc_code].update({"status": "Remove", "reason": f"Inclusion code of '{parent_code}'"})

        # 4. COMBINATION CHECK
        for combined_code, [left, right] in combineCode_dict.items():
            # If both halves exist and haven't been removed yet
            if left in results and results[left]["status"] != "Remove" and \
               right in results and results[right]["status"] != "Remove":
                
                # Remove the two halves
                results[left].update({"status": "Remove", "reason": f"Combined with {right} -> {combined_code}"})
                results[right].update({"status": "Remove", "reason": f"Combined with {left} -> {combined_code}"})
                
                # Add the new combined code
                results[combined_code] = {
                    "title": title_map.get(combined_code, "Title not found"),
                    "status": "Add", # Special status for system-added codes
                    "reason": f"Generated from combining '{left}' and '{right}'",
                    "warning": None
                }

        # 5. ALERT / RECONSIDER CHECK
        active_codes = [c for c, d in results.items() if d["status"] in ["Keep", "Add"]]
        group_map = collections.defaultdict(list)
        
        for code in active_codes:
            base_group = code.split('.')[0][:3]
            group_map[base_group].append(code)
            
        for base, codes_in_group in group_map.items():
            if len(codes_in_group) >= 2:
                invalid_codes = []
                for code in codes_in_group:
                    has_exception = False
                    if code in code_also_dict:
                        if any(other in code_also_dict[code] for other in codes_in_group if other != code):
                            has_exception = True
                    if not has_exception:
                        invalid_codes.append(code)
                
                if len(invalid_codes) >= 2:
                    for c in invalid_codes:
                        if results[c]["status"] in ["Keep", "Add"]:
                            results[c]["warning"] = f"Conflict in base group '{base}'. Please reconsider."

        st.session_state.processed_results = results
        st.session_state.stage = 'review'
        st.rerun()


# --- 5. STAGE 2: REVIEW ---
elif st.session_state.stage == 'review':
    st.subheader("2. Review Analysis & Confirm")
    st.info("Review proposed changes. Red = Removing, Blue = Added (Combined), Yellow = Warning.")
    
    results = st.session_state.processed_results
    
    for code, details in results.items():
        if details["status"] == "Remove":
            st.markdown(f"""
            <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 15px; margin-bottom: 10px; color: #721c24;">
                <strong>❌ Code: {code}</strong> - {details['title']}<br>
                <em>Reason: {details['reason']}</em>
            </div>
            """, unsafe_allow_html=True)
            
        elif details["status"] == "Add":
            st.markdown(f"""
            <div style="background-color: #cce5ff; border: 1px solid #b8daff; border-radius: 5px; padding: 15px; margin-bottom: 10px; color: #004085;">
                <strong>✨ New Code (Combined): {code}</strong> - {details['title']}<br>
                <em>Action: {details['reason']}</em>
            </div>
            """, unsafe_allow_html=True)
            
        else: # "Keep"
            if details["warning"]:
                st.markdown(f"""
                <div style="background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 5px; padding: 15px; margin-bottom: 10px; color: #856404;">
                    <strong>⚠️ Code: {code}</strong> - {details['title']}<br>
                    <em>Warning: {details['warning']}</em>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; padding: 15px; margin-bottom: 10px; color: #155724;">
                    <strong>✅ Code: {code}</strong> - {details['title']}<br>
                    <em>Action: Keep</em>
                </div>
                """, unsafe_allow_html=True)
            
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("⬅️ Back to Edit"):
            st.session_state.stage = 'drafting'
            st.rerun()
    with col2:
        if st.button("✔️ Confirm & Finalize", type="primary"):
            st.session_state.stage = 'final'
            st.rerun()


# --- 6. STAGE 3: FINAL OUTPUT ---
elif st.session_state.stage == 'final':
    st.subheader("3. Final Billed Codes")
    st.success("Deduplication complete. These are your final codes ready for submission.")
    
    final_codes = [code for code, details in st.session_state.processed_results.items() if details["status"] != "Remove"]
    
    for code in final_codes:
        title = st.session_state.processed_results[code]["title"]
        st.markdown(f"""
        <div style="background-color: #e2e3e5; border: 1px solid #d6d8db; border-radius: 5px; padding: 15px; margin-bottom: 10px; color: #383d41;">
            <strong>📋 {code}</strong>: {title}
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Start New Patient"):
        st.session_state.input_codes = [""]
        st.session_state.stage = 'drafting'
        st.session_state.processed_results = {}
        st.rerun()