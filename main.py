import streamlit as st
import pandas as pd
import json
import collections
import warnings


warnings.filterwarnings("ignore", category=FutureWarning)

# --- 1. PAGE SETUP & DATA LOADING ---
st.set_page_config(page_title="ICD-9 Deduplication Engine", layout="wide")
st.title("ICD-9 Deduplication")
st.markdown("Enter a list of ICD-9 codes. The engine will process them through the validation, inclusion, combination, and alert pipelines.")

# Cache the data loading so the dashboard remains fast
@st.cache_data
def load_data():
    icd9 = pd.read_json('./data/icd9-cm-2015-code.json').T
    icd9 = icd9.reset_index(names="Code")
    valid_code = icd9['Code'].tolist()
    
    includeMap = pd.read_excel('./result/icd9_inclusion_mapping_summary_TFIDF.xlsx', dtype='string')
    includeMap_dict = {row['Code'] : row['Code_include_expand'].split(', ') for i, row in includeMap.iterrows()}
    
    combineCode = pd.read_excel('./result/combine_code_summary.xlsx', dtype='string')
    combineCode_dict = {row['code_combine'] : [row['code_left'], row['code_right']] for i,row in combineCode.iterrows()}
    
    with open('./result/icd9_codeAlso.json', 'r') as f:
        code_also_dict = json.load(f)
        
    return valid_code, includeMap_dict, combineCode_dict, code_also_dict

try:
    valid_code, includeMap_dict, combineCode_dict, code_also_dict = load_data()
except Exception as e:
    st.error(f"Error loading files: {e}. Please ensure data/ and result/ folders are in the correct path.")
    st.stop()


# --- 2. PIPELINE FUNCTIONS (Adapted for UI Logging) ---
def remove_invalid_code(input_code: list[str]) -> tuple[list[str], list[str]]:
    valid = [code for code in input_code if code in valid_code]
    invalid = [code for code in input_code if code not in valid_code]
    logs = [f"Removed invalid code: '{c}'" for c in invalid]
    return valid, logs

def remove_less_detailed_code(input_code: list[str]) -> tuple[list[str], list[str]]:
    sorted_codes = sorted(input_code, key=len, reverse=True)
    result, logs = [], []
    for code in sorted_codes:
        matching_kept_code = next((kept_code for kept_code in result if kept_code.startswith(code)), None)
        if matching_kept_code:
            logs.append(f"Removed: '{code}' (Less detailed version of '{matching_kept_code}')")
        else:
            result.append(code)
    return result, logs

def remove_include_code(input_code: list[str]) -> tuple[list[str], list[str]]:
    removal_reasons = {}
    for code in input_code:
        if code in includeMap_dict:
            for inc_code in includeMap_dict[code]:
                removal_reasons[inc_code] = code
                
    result, logs = [], []
    for code in input_code:
        if code in removal_reasons:
            logs.append(f"Removed: '{code}' (Inclusion code of '{removal_reasons[code]}')")
        else:
            result.append(code)
    return result, logs

def collapse_combine_code(input_code: list[str]) -> tuple[list[str], list[str]]:
    result = list(input_code)
    logs = []
    for combined_code, [left, right] in combineCode_dict.items():
        if left in result and right in result:
            logs.append(f"Combined: '{left}' + '{right}' -> Collapsed into '{combined_code}'")
            result.remove(left)
            result.remove(right)
            result.append(combined_code)
    return result, logs

def alert_reconsider_code(input_code: list[str]) -> list[str]:
    group_map = collections.defaultdict(list)
    logs = []
    for code in input_code:
        base_group = code[:-1] if len(code) > 3 else code
        group_map[base_group].append(code)

    for base_group, codes_in_group in group_map.items():
        if len(codes_in_group) >= 2:
            invalid_codes = []
            for code in codes_in_group:
                has_exception = False
                if code in code_also_dict:
                    allowed_exceptions = code_also_dict[code]
                    if any(other_code in allowed_exceptions for other_code in codes_in_group if other_code != code):
                        has_exception = True
                if not has_exception:
                    invalid_codes.append(code)
            
            if len(invalid_codes) >= 2:
                logs.append(f"⚠️ Alert: Multiple codes found in base group '{base_group}': {invalid_codes}. Please reconsider.")
    return logs


# --- 3. UI DASHBOARD INTERFACE ---
showValue = ["8331", "833",
             "3897", "8952",
             "1733", "1735",
             "0056", "0057", 
             "0044", "0045"]
raw_input = st.text_input("Input ICD-9 Codes (comma or space separated)", value=' , '.join(showValue))

if st.button("Run Pipeline", type="primary"):
    
    # Clean input: remove dots, split by comma/space, and ignore empty strings
    cleaned_input = raw_input.replace('.', '').replace(',', ' ').split()
    current_codes = [c.strip() for c in cleaned_input if c.strip()]
    
    st.markdown("### Original Input")
    st.info(f"{current_codes}")

    # Step 1: Valid Codes
    current_codes, logs1 = remove_invalid_code(current_codes)
    with st.expander("Step 1: Invalid Code Filtering", expanded=True):
        if logs1:
            for log in logs1: st.error(log)
        else:
            st.success("All codes are valid.")
        st.write(f"**Remaining:** {current_codes}")

    # Step 2: Less Detailed Code
    current_codes, logs2 = remove_less_detailed_code(current_codes)
    with st.expander("Step 2: Less Detailed Code Removal", expanded=True):
        if logs2:
            for log in logs2: st.warning(log)
        else:
            st.success("No less-detailed codes found.")
        st.write(f"**Remaining:** {current_codes}")

    # Step 3: Inclusion Code
    current_codes, logs3 = remove_include_code(current_codes)
    with st.expander("Step 3: Inclusion Code Removal", expanded=True):
        if logs3:
            for log in logs3: st.warning(log)
        else:
            st.success("No inclusion rules triggered.")
        st.write(f"**Remaining:** {current_codes}")

    # Step 4: Combination Code
    current_codes, logs4 = collapse_combine_code(current_codes)
    with st.expander("Step 4: Code Combination", expanded=True):
        if logs4:
            for log in logs4: st.info(log)
        else:
            st.success("No combination rules triggered.")
        st.write(f"**Remaining:** {current_codes}")

    # Step 5: Alerts
    logs5 = alert_reconsider_code(current_codes)
    with st.expander("Step 5: Code Overlap Alerts", expanded=True):
        if logs5:
            for log in logs5: st.error(log)
        else:
            st.success("No conflicting code groups found!")

    # Final Output
    st.markdown("---")
    st.markdown("### ✅ Final Processed Codes")
    st.success(f"{current_codes}")