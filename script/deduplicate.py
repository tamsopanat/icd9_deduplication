import pandas as pd
import warnings
import json
import collections

warnings.filterwarnings("ignore", category=FutureWarning)
icd9 = pd.read_json('../data/icd9-cm-2015-code.json').T
icd9 = icd9.reset_index(names="Code")
includeMap = pd.read_excel('../result/icd9_inclusion_mapping_summary_TFIDF.xlsx', dtype='string')
combineCode = pd.read_excel('../result/combine_code_summary.xlsx', dtype='string')
with open('../result/icd9_codeAlso.json', 'r') as f:
    code_also_dict = json.load(f)

valid_code = icd9['Code'].tolist()
def remove_invalid_code(input_code : list[str]) -> list[str]:
    return [code for code in input_code if code in valid_code]

def remove_less_detailed_code(input_code : list[str]) -> list[str]:
    sorted_codes = sorted(input_code, key=len, reverse=True)
    result = []
    for code in sorted_codes:
        matching_kept_code = next((kept_code for kept_code in result if kept_code.startswith(code)), None)
        if matching_kept_code:
            print(f"Removed: '{code}' (Reason: Less detailed version of '{matching_kept_code}')")
        else:
            result.append(code)
    return result

includeMap_dict = {row['Code'] : row['Code_include_expand'].split(', ') for i, row in includeMap.iterrows()}
def remove_include_code(input_code : list[str]) -> list[str]:
    removal_reasons = {}
    for code in input_code:
        if code in includeMap_dict:
            included_codes = includeMap_dict[code]
            for inc_code in included_codes:
                removal_reasons[inc_code] = code
                
    result = []
    for code in input_code:
        if code in removal_reasons:
            parent_code = removal_reasons[code]
            print(f"Removed: '{code}' (Reason: It is an inclusion code of '{parent_code}')")
        else:
            result.append(code)
    return result

combineCode_dict = {row['code_combine'] : [row['code_left'], row['code_right']] for i,row in combineCode.iterrows()}
def collapse_combine_code(input_code : list[str]) -> list[str]:
    result = input_code
    for combined_code, [left, right] in combineCode_dict.items():
        if left in result and right in result:
            print(f"Combining: '{left}' + '{right}' -> Collapsing into '{combined_code}'")
            result.remove(left)
            result.remove(right)
            result.append(combined_code)
    return result

def alert_reconsider_code(input_code : list[str]) -> list[str]:
    group_map = collections.defaultdict(list)
    for code in input_code:
        base_group = code[:-1]
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
            
            # 3. Raise an alert if multiple codes remain without exceptions
            if len(invalid_codes) >= 2:
                print(f"Alert: Multiple codes found in base group '{base_group}': {invalid_codes}. Please reconsider.")