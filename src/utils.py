from packaging.version import Version

INEQ_OPS = ['==', '!=', '>=', '<=', '>', '<']

def startswith_list(s, op_list):
    for op in op_list:
        if s.startswith(op):
            return op, s[len(op):]
    return None, []

def normalize_ver(v):
    if v.endswith(".*"):
        v = v[:-2] + ".0"

    return v

def parse_constraint_str(s):
    toks = s.split(' ', 1)
    toks = [t for t in toks if not t.startswith("*")]
    dep = toks[0]

    if len(toks) == 1:
        conds = []

    elif len(toks) == 2:
        raw_conds = toks[1].split(',')

        conds = []
        for raw_cond in raw_conds:
            op, ver = startswith_list(raw_cond, INEQ_OPS)
            if (not op):
                print(f"[ERROR] Unrecognized operator in {raw_cond}")
                continue

            conds.append({ 'op': op, 'ver': ver })
            

    return { 'dep': dep, 'conds': conds }

def cmp_v(v1, op, v2):
    if op not in INEQ_OPS:
        print(f"[ERROR] op {op} not in INEQ_OPS")
        return False

    v1 = Version(normalize_ver(v1))
    v2 = Version(normalize_ver(v2))

    match op:
        case '==':
            return v1 == v2
        case '!=':
            return v1 != v2
        case '>=':
            return v1 >= v2
        case '<=':
            return v1 <= v2
        case '>': 
            return v1 > v2
        case '<':
            return v1 < v2

    return False
