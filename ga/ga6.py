

import random
import math
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


# -------------------------
#  Version 비교 유틸리티
# -------------------------

def normalize_version(v: str) -> Tuple[int, ...]:
    """
    "3.10.0a0" -> (3, 10, 0)
    "3.9"      -> (3, 9)
    """
    cleaned = ""
    for ch in v:
        if ch.isdigit() or ch == ".":
            cleaned += ch
        else:
            break
    if not cleaned:
        return (0,)
    parts = [int(p) for p in cleaned.split(".") if p != ""]
    if not parts:
        return (0,)
    return tuple(parts)


def cmp_version(a: str, b: str) -> int:
    """
    a < b  -> -1
    a == b ->  0
    a > b  -> +1
    """
    ta = normalize_version(a)
    tb = normalize_version(b)
    L = max(len(ta), len(tb))
    ta = ta + (0,) * (L - len(ta))
    tb = tb + (0,) * (L - len(tb))
    if ta < tb:
        return -1
    elif ta > tb:
        return 1
    else:
        return 0


def check_one_constraint(ver: str, op: str, target: str) -> bool:
    """
    ver <op> target 이 성립하는지 체크
    op: "<", "<=", ">", ">=", "==", "!=", "=" 지원
    """
    c = cmp_version(ver, target)
    if op == ">=":
        return c >= 0
    elif op == ">":
        return c > 0
    elif op == "<=":
        return c <= 0
    elif op == "<":
        return c < 0
    elif op in ("==", "="):
        return c == 0
    elif op == "!=":
        return c != 0
    else:
        raise ValueError(f"Unknown op: {op}")


def check_constraint_list(ver: str, constraints: List[Dict[str, str]]) -> bool:
    """
    constraints = [{ "op": ">=", "ver": "3.9" }, { "op": "<", "ver": "3.10.0a0" }]
    처럼 들어올 때,
    모든 조건을 AND 로 만족하는지 검사
    """
    return all(check_one_constraint(ver, c["op"], c["ver"]) for c in constraints)


def version_distance(v1: str, v2: str) -> float:
    """두 버전 간의 거리 계산"""
    t1 = normalize_version(v1)
    t2 = normalize_version(v2)
    max_len = max(len(t1), len(t2))
    t1 = t1 + (0,) * (max_len - len(t1))
    t2 = t2 + (0,) * (max_len - len(t2))
    return float(sum(abs(a - b) for a, b in zip(t1, t2)))


# -------------------------
#  인코딩 (염색체 구조)
# -------------------------

def build_encoding(repo: Dict[str, Any], python_candidates: Optional[List[str]] = None):
    """
    repo: 네가 준 JSON dict (패키지 -> 버전 -> {depends, constrains})
    python_candidates: GA가 탐색할 파이썬 버전 후보들
    """
    if python_candidates is None:
        # 필요하면 여기 후보를 더 늘려도 됨
        python_candidates = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.14"]

    package_names = sorted(repo.keys())  # 예: ["Pillow", "accelerate", "azure-storage-blob", "black"]

    # gene_choices[i] = i번째 유전자에서 선택 가능한 값 리스트
    # gene 0: 파이썬 버전 후보
    # gene 1..N: 각 패키지의 [None(미설치), version1, version2, ...]
    gene_choices: List[List[Optional[str]]] = []
    gene_choices.append(python_candidates)

    for pkg in package_names:
        versions = repo[pkg]   # 예: {"12.9.0": {...}, "12.19.0": {...}, ...} 또는 {}
        if versions:
            vs = sorted(versions.keys(), key=normalize_version)
            gene_choices.append([None] + vs)
        else:
            # 아직 버전 정보가 없다면 "설치 안 함"만 선택 가능
            gene_choices.append([None])

    return package_names, gene_choices


def decode_individual(
    individual: List[int],
    package_names: List[str],
    gene_choices: List[List[Optional[str]]],
):
    """
    GA 염색체(정수 리스트)를 실제 (python_ver, {pkg: version or None}) 로 디코딩
    """
    python_ver = gene_choices[0][individual[0]]
    pkg_versions: Dict[str, Optional[str]] = {}

    for i, pkg in enumerate(package_names, start=1):
        allele = individual[i]
        choice_list = gene_choices[i]
        pkg_versions[pkg] = choice_list[allele]

    return python_ver, pkg_versions


# -------------------------
#  Fitness 함수
# -------------------------

def fitness(
    individual: List[int],
    repo: Dict[str, Any],
    package_names: List[str],
    gene_choices: List[List[Optional[str]]],
    hard_constraints: Optional[Dict[str, List[Dict[str, str]]]] = None,
) -> float:
    """
    목적:
      - 의존성 위반 최소화
      - hard_constraints 만족도 최대화 (버전 거리 기반)
    """
    python_ver, pkg_versions = decode_individual(individual, package_names, gene_choices)

    MISSING_DEP_PENALTY = 0.5
    CONFLICT_PENALTY = 3.0
    CONSTRAIN_PENALTY = 3.0
    INSTALLED_REWARD = 1.0
    REQUIRED_MISSING_PENALTY = 500.0

    missing_dep = 0
    conflicts = 0
    constrain_conflicts = 0
    installed = sum(1 for v in pkg_versions.values() if v is not None)

    required_pkgs = [pkg for pkg, versions in repo.items() if versions]

    for pkg, ver in pkg_versions.items():
        if ver is None:
            continue

        meta = repo.get(pkg, {}).get(ver)
        if not meta:
            continue

        depends = meta.get("depends", {})
        for dep_pkg, cons_list in depends.items():
            if dep_pkg in ("python", "python_abi"):
                dep_ver = python_ver
            else:
                if dep_pkg not in pkg_versions:
                    missing_dep += 1
                    continue
                dep_ver = pkg_versions.get(dep_pkg)

            if dep_ver is None:
                missing_dep += 1
            else:
                if not check_constraint_list(dep_ver, cons_list):
                    conflicts += 1

        constrains = meta.get("constrains", {})
        for target_pkg, cons_list in constrains.items():
            if target_pkg in ("python", "python_abi"):
                target_ver = python_ver
            else:
                if target_pkg not in pkg_versions:
                    continue
                target_ver = pkg_versions.get(target_pkg)

            if target_ver is None:
                continue

            if not check_constraint_list(target_ver, cons_list):
                constrain_conflicts += 1
        
    missing_required = sum(
        1 for pkg in required_pkgs
        if pkg_versions.get(pkg) is None
    )

    score = (
        INSTALLED_REWARD * installed
        - MISSING_DEP_PENALTY * missing_dep
        - CONFLICT_PENALTY * conflicts
        - CONSTRAIN_PENALTY * constrain_conflicts
        - REQUIRED_MISSING_PENALTY * missing_required
    )

    # Hard constraints 패널티 (강화된 버전)
    # hard_constraints는 반드시 만족해야 하는 조건이므로 매우 높은 페널티 부여
    hard_constraint_penalty = 0
    hard_constraint_satisfied = 0
    
    if hard_constraints:
        for constraint_pkg, cons_list in hard_constraints.items():
            if constraint_pkg not in pkg_versions:
                continue
            
            pkg_ver = pkg_versions.get(constraint_pkg)
            
            # Target 버전 추출 (== 조건)
            target_ver = None
            for c in cons_list:
                if c.get("op") in ("==", "="):
                    target_ver = c.get("ver")
                    break
            
            if pkg_ver is None:
                # 미설치: 극심한 페널티
                hard_constraint_penalty += 1e7
            elif check_constraint_list(pkg_ver, cons_list):
                # 조건 완벽히 만족: 보상
                hard_constraint_satisfied += 1
                score += 1e4
            elif target_ver:
                # 조건 미충족: 거리에 따른 매우 높은 페널티
                dist = version_distance(pkg_ver, target_ver)
                # 거리 0에 가까울수록 페널티 감소, 멀어질수록 증가
                hard_constraint_penalty += 1e6 + dist * 1e5
            else:
                # 범위 조건 미충족 (>= 등)
                hard_constraint_penalty += 1e6

    score -= hard_constraint_penalty
    return score


# -------------------------
#  GA 연산 (선택 / 교차 / 변이)
# -------------------------

def random_individual(gene_choices: List[List[Optional[str]]]) -> List[int]:
    return [random.randrange(len(choices)) for choices in gene_choices]


def random_individual_respecting_constraints(
    gene_choices: List[List[Optional[str]]],
    package_names: List[str],
    hard_constraints: Optional[Dict[str, List[Dict[str, str]]]] = None,
) -> List[int]:
    """
    Create a random individual that respects hard constraints if provided.
    If a required version is not available, find the best match.
    """
    individual = [random.randrange(len(choices)) for choices in gene_choices]
    
    if hard_constraints:
        # For each hard-constrained package, pick a version that satisfies it
        for constraint_pkg, cons_list in hard_constraints.items():
            if constraint_pkg in package_names:
                pkg_idx = package_names.index(constraint_pkg) + 1  # +1 for python gene
                if pkg_idx < len(gene_choices):
                    choices = gene_choices[pkg_idx]
                    
                    # First, try to find an exact match or satisfying version
                    found = False
                    for i, ver in enumerate(choices):
                        if ver is None:
                            continue
                        if check_constraint_list(ver, cons_list):
                            individual[pkg_idx] = i
                            found = True
                            break
                    
                    # If no exact match, pick the highest available version
                    if not found:
                        best_idx = 0
                        best_ver = None
                        for i, ver in enumerate(choices):
                            if ver is None:
                                continue
                            if best_ver is None:
                                best_idx = i
                                best_ver = ver
                            elif cmp_version(ver, best_ver) > 0:
                                best_idx = i
                                best_ver = ver
                        individual[pkg_idx] = best_idx
    
    return individual


def tournament_selection(
    population: List[List[int]],
    fitnesses: List[float],
    k: int = 3,
) -> List[int]:
    """
    k-토너먼트 선택
    """
    best_idx = None
    for _ in range(k):
        i = random.randrange(len(population))
        if best_idx is None or fitnesses[i] > fitnesses[best_idx]:
            best_idx = i
    return population[best_idx][:]


def crossover(
    parent1: List[int],
    parent2: List[int],
    pc: float = 0.9,
):
    """
    1-point crossover
    """
    if random.random() > pc:
        return parent1[:], parent2[:]
    point = random.randrange(1, len(parent1))  # 0과 끝은 피함
    c1 = parent1[:point] + parent2[point:]
    c2 = parent2[:point] + parent1[point:]
    return c1, c2


def mutate(
    individual: List[int],
    gene_choices: List[List[Optional[str]]],
    pm: float = 0.05,
):
    """
    각 유전자마다 확률 pm으로 다른 값으로 랜덤하게 변경
    """
    for i in range(len(individual)):
        if random.random() < pm:
            individual[i] = random.randrange(len(gene_choices[i]))


# -------------------------
#  GA 메인 루프
# -------------------------

def run_ga(
    repo: Dict[str, Any],
    python_candidates: Optional[List[str]] = None,
    pop_size: int = 50,
    n_generations: int = 80,
    pc: float = 0.9,
    pm: float = 0.05,
    tournament_k: int = 3,
    seed: Optional[int] = None,
    hard_constraints: Optional[Dict[str, List[Dict[str, str]]]] = None,
):
    """
    repo: JSON dict
    hard_constraints: {package: [{"op": "==", "ver": "1.0"}]} (must be satisfied)
    return: (best_fitness, best_python_ver, best_pkg_versions 딕셔너리)
    """
    if seed is not None:
        random.seed(seed)

    package_names, gene_choices = build_encoding(repo, python_candidates)

    # 초기 개체군 (hard constraint 고려)
    population = []
    for _ in range(pop_size):
        if hard_constraints:
            ind = random_individual_respecting_constraints(gene_choices, package_names, hard_constraints)
        else:
            ind = random_individual(gene_choices)
        population.append(ind)
    
    best_individual = None
    best_fitness = -math.inf

    for gen in range(n_generations):
        fitnesses = []
        for ind in population:
            f = fitness(ind, repo, package_names, gene_choices, hard_constraints)
            fitnesses.append(f)

        # 베스트 갱신
        for ind, f in zip(population, fitnesses):
            if f > best_fitness:
                best_fitness = f
                best_individual = ind[:]

        # 10대마다만 출력 (또는 마지막 세대)
        if gen % 10 == 0 or gen == n_generations - 1:
            print(f"[gen {gen:03d}] best fitness = {best_fitness:.3f}")

        # 다음 세대 생성
        new_population: List[List[int]] = []
        while len(new_population) < pop_size:
            p1 = tournament_selection(population, fitnesses, k=tournament_k)
            p2 = tournament_selection(population, fitnesses, k=tournament_k)
            c1, c2 = crossover(p1, p2, pc=pc)
            mutate(c1, gene_choices, pm=pm)
            mutate(c2, gene_choices, pm=pm)
            new_population.append(c1)
            if len(new_population) < pop_size:
                new_population.append(c2)
        population = new_population

    assert best_individual is not None
    best_python_ver, best_pkg_versions = decode_individual(best_individual, package_names, gene_choices)
    return best_fitness, best_python_ver, best_pkg_versions


# -------------------------
#  사용 예시
# -------------------------
if __name__ == "__main__":
    # 여기에 JSON dict를 그대로 넣으면 됨.
    
    repo = {
        "Pillow": {},
        "accelerate": {},
        "azure-storage-blob": {
            "12.9.0": {
                "depends": {
                    "azure-core": [
                        {"op": "<", "ver": "2.0.0"},
                        {"op": ">=", "ver": "1.9.0"},
                    ],
                    "cryptography": [{"op": ">=", "ver": "2.1.4"}],
                    "msrest": [{"op": ">=", "ver": "0.6.10"}],
                    "python": [{"op": ">=", "ver": "2.7"}],
                },
                "constrains": {},
            },
            "12.19.0": {
                "depends": {
                    "azure-core": [
                        {"op": "<", "ver": "2.0.0"},
                        {"op": ">=", "ver": "1.28.0"},
                    ],
                    "cryptography": [{"op": ">=", "ver": "2.1.4"}],
                    "isodate": [{"op": ">=", "ver": "0.6.1"}],
                    "python": [
                        {"op": ">=", "ver": "3.9"},
                        {"op": "<", "ver": "3.10.0a0"},
                    ],
                    "typing-extensions": [{"op": ">=", "ver": "4.3.0"}],
                },
                "constrains": {},
            },
        },
        "black": {
            "22.6.0": {
                "depends": {
                    "click": [{"op": ">=", "ver": "8.0.0"}],
                    "mypy_extensions": [{"op": ">=", "ver": "0.4.3"}],
                    "pathspec": [{"op": ">=", "ver": "0.9.0"}],
                    "platformdirs": [{"op": ">=", "ver": "2"}],
                    "python": [
                        {"op": ">=", "ver": "3.9"},
                        {"op": "<", "ver": "3.10.0a0"},
                    ],
                    "tomli": [{"op": ">=", "ver": "1.1.0"}],
                    "typing_extensions": [{"op": ">=", "ver": "3.10.0.0"}],
                },
                "constrains": {},
            }
        },
    }

    best_f, best_py, best_pkgs = run_ga(
        repo,
        python_candidates=["3.8", "3.9", "3.10", "3.14"],
        pop_size=40,
        n_generations=60,
        seed=42,
    )

    print("\n=== GA Result ===")
    print("Best fitness:", best_f)
    print("Python:", best_py)
    print("Packages:")
    for name, ver in best_pkgs.items():
        print(f"  {name}: {ver}")


# -------------------------
#  CLI 인터페이스
# -------------------------

def load_json(path: str) -> Dict:
    """JSON 파일 로드"""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] JSON 로드 실패: {path}")
        print(f"[ERROR] {e}")
        exit(1)


def save_json(data: Dict, path: str):
    """JSON 파일 저장"""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[INFO] 결과 저장 완료: {path}")
    except Exception as e:
        print(f"[ERROR] JSON 저장 실패: {path}")
        print(f"[ERROR] {e}")


def run_cli():
    """CLI 모드로 실행"""
    parser = argparse.ArgumentParser(
        description="GA를 이용한 Python 패키지 의존성 해결"
    )
    parser.add_argument(
        "--dep-space",
        type=str,
        required=True,
        help="의존성 공간 JSON 파일 경로",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ga_solution.json",
        help="결과 저장 경로 (기본값: ga_solution.json)",
    )
    parser.add_argument(
        "--python-versions",
        type=str,
        default="3.8,3.9,3.10,3.11,3.12",
        help="탐색할 Python 버전 (쉼표로 구분, 기본값: 3.8,3.9,3.10,3.11,3.12)",
    )
    parser.add_argument(
        "--population-size",
        type=int,
        default=100,
        help="개체군 크기 (기본값: 100)",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=50,
        help="진화 세대 수 (기본값: 100)",
    )
    parser.add_argument(
        "--crossover-rate",
        type=float,
        default=0.9,
        help="교차 확률 (기본값: 0.9)",
    )
    parser.add_argument(
        "--mutation-rate",
        type=float,
        default=0.05,
        help="변이 확률 (기본값: 0.05)",
    )
    parser.add_argument(
        "--tournament-size",
        type=int,
        default=3,
        help="토너먼트 크기 (기본값: 3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="난수 시드 (기본값: None)",
    )
    parser.add_argument(
        "--hard-constraints",
        type=str,
        default=None,
        help="Hard constraint 파일 경로 (JSON 형식, {package: [{op: '==', ver: '1.0'}]})",
    )

    args = parser.parse_args()

    # 의존성 공간 로드
    print("[*] 의존성 공간 로드 중...")
    dep_space = load_json(args.dep_space)
    print(f"[*] {len(dep_space)}개 패키지 로드 완료")

    # Hard constraint 로드
    hard_constraints = None
    if args.hard_constraints:
        hard_constraints = load_json(args.hard_constraints)
        print(f"[*] Hard constraint 로드 완료: {list(hard_constraints.keys())}")

    # Python 버전 파싱
    python_versions = args.python_versions.split(',')
    python_versions = [v.strip() for v in python_versions]

    print(f"[*] GA 실행 중...")
    print(f"    - 개체군 크기: {args.population_size}")
    print(f"    - 세대 수: {args.generations}")
    print(f"    - 교차 확률: {args.crossover_rate}")
    print(f"    - 변이 확률: {args.mutation_rate}")
    print(f"    - Python 버전: {python_versions}")

    # GA 실행
    best_fitness, best_python_ver, best_pkg_versions = run_ga(
        dep_space,
        python_candidates=python_versions,
        pop_size=args.population_size,
        n_generations=args.generations,
        pc=args.crossover_rate,
        pm=args.mutation_rate,
        tournament_k=args.tournament_size,
        seed=args.seed,
        hard_constraints=hard_constraints,
    )

    print(f"\n[*] GA 실행 완료!")
    print(f"[*] 최고 적합도: {best_fitness:.3f}")
    print(f"[*] Python 버전: {best_python_ver}")

    # 설치된 패키지 출력
    installed_packages = {
        pkg: ver
        for pkg, ver in best_pkg_versions.items()
        if ver is not None
    }

    print(f"[*] 설치된 패키지 ({len(installed_packages)}개):")
    for pkg, ver in sorted(installed_packages.items()):
        print(f"    {pkg} == {ver}")

    # 결과 저장
    result = {
        "python_version": best_python_ver,
        "packages": installed_packages,
        "fitness": best_fitness,
    }

    save_json(result, args.output)

    # 상세 결과도 저장
    detailed_output = args.output.replace(".json", "_detailed.json")
    detailed_result = {
        "python_version": best_python_ver,
        "all_packages": best_pkg_versions,
        "installed_packages": installed_packages,
        "fitness": best_fitness,
    }
    save_json(detailed_result, detailed_output)


if __name__ == "__main__":
    run_cli()












