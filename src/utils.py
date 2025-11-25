from packaging.version import Version

INEQ_OPS = ['==', '!=', '>=', '<=', '>', '<']

def is_conda_pkg(req):
    return "@" not in req and "://" not in req and not req.startswith("git+")

def startswith_list(s, op_list):
    for op in op_list:
        if s.startswith(op):
            return op, s[len(op):]
    return None, []

def expand_wildcard(ver):
    if not ver.endswith(".*"):
        return None
    
    base = ver[:-2]
    parts = base.split(".")
    while len(parts) < 2:
        parts.append("0")
    
    major = int(parts[0])
    minor = int(parts[1])

    lower = f"{major}.{minor}.0"
    upper = f"{major}.{minor+1}.0"

    return [
        { 'op': '>=', 'ver': lower },
        { 'op': '<',  'ver': upper }
    ]

def parse_constraint_str(s):
    toks = s.split(' ', 1)
    toks = [t for t in toks if not t.startswith("*")]
    dep = toks[0]

    if len(toks) == 1:
        return { 'dep': dep, 'conds': [] }

    raw_conds = toks[1].split(',')
    conds = []
    
    for raw_cond in raw_conds:
        raw_cond = raw_cond.strip().split(' ')[0]

        op, ver = startswith_list(raw_cond, INEQ_OPS)
        if not op:
            op = "=="
            ver = raw_cond
        
        wc = expand_wildcard(ver)
        if wc:
            conds.extend(wc)      
        else:
            conds.append({ 'op': op, 'ver': ver })
            
    return { 'dep': dep, 'conds': conds }

def cmp_v(v1, op, v2):
    if op not in INEQ_OPS:
        print(f"[ERROR] op {op} not in INEQ_OPS")
        return False

    v1 = Version(v1)
    v2 = Version(v2)

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
