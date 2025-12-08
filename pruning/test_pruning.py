#!/usr/bin/env python3
"""
pruning.py 테스트 스크립트 - dep_space.json의 의존성 그래프 분석 및 단순화
"""

import json
import sys
from pathlib import Path

# 현재 디렉토리와 src 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pruning


def load_json(path):
    """JSON 파일 로드"""
    with open(path) as f:
        return json.load(f)


def main():
    print("=" * 80)
    print("PRUNING TEST - Dependency Graph Preprocessing")
    print("=" * 80)

    # dep_space.json 로드 (프로젝트 루트의 data 디렉토리)
    dep_space_path = Path(__file__).parent.parent / "data" / "dep_space.json"

    if not dep_space_path.exists():
        print(f"\n[ERROR] {dep_space_path} not found")
        print("Please run precompute.py first to generate dep_space.json")
        return

    print(f"\n[1] Loading dependency space...")
    print(f"    Path: {dep_space_path}")

    dep_space = load_json(dep_space_path)

    total_packages = len(dep_space)
    total_versions = sum(len(versions) for versions in dep_space.values())
    avg_versions = total_versions / total_packages if total_packages > 0 else 0

    print(f"    ✓ Loaded {total_packages} packages")
    print(f"    ✓ Total versions: {total_versions}")
    print(f"    ✓ Average versions per package: {avg_versions:.1f}")

    # 샘플 패키지 출력
    print(f"\n[2] Sample packages in dep_space:")
    sample_count = 0
    for pkg, versions in dep_space.items():
        if sample_count >= 10:
            break
        print(f"    - {pkg}: {len(versions)} versions")
        sample_count += 1

    # 시각화 설정
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    print(f"\n[3] Running preprocessing...")
    print(f"    Output directory: {output_dir}")
    print("    Visualizing: Yes")
    print("-" * 80)

    # pruning.py 전처리 실행
    result = pruning.preprocess_dependencies(
        dep_space,
        visualize=True,
        output_dir=str(output_dir),
        save_clean=True
    )

    print("-" * 80)

    # 결과 분석
    print(f"\n{'=' * 80}")
    print("PREPROCESSING RESULTS")
    print("=" * 80)

    resolved = result['resolved']
    remaining = result['remaining']
    fixed_versions = result['fixed_versions']
    constrained_versions = result['constrained_versions']
    dep_space_clean = result['dep_space_clean']
    precomputed_dep_space = result['precomputed_dep_space']

    # 통계 출력
    fixed_count = sum(1 for info in resolved.values() if info['status'] == 'fixed')
    constrained_with_versions = sum(1 for info in resolved.values()
                                    if info['status'] == 'constrained' and info.get('valid_versions'))
    constrained_no_versions = sum(1 for info in resolved.values()
                                  if info['status'] == 'constrained' and not info.get('valid_versions'))

    print(f"\n[SUMMARY]")
    print(f"  Total resolved: {len(resolved)}")
    print(f"    - Fixed (single version): {fixed_count}")
    print(f"    - Constrained (multiple versions): {constrained_with_versions}")
    print(f"    - Constrained (no versions in dep_space): {constrained_no_versions}")
    print(f"  Remaining for solver: {len(remaining)}")
    print(f"  Packages in dep_space_clean: {len(dep_space_clean)}")
    print(f"  Packages in precomputed.json (Fixed + Constrained): {len(precomputed_dep_space)}")

    # Fixed 버전 출력
    if fixed_count > 0:
        print(f"\n[FIXED VERSIONS] ({fixed_count} packages)")
        print("  These packages have been resolved to a single version:")
        count = 0
        for pkg, info in resolved.items():
            if info['status'] == 'fixed':
                print(f"    {count+1}. {pkg} = {info['version']}")
                count += 1
                if count >= 20:
                    remaining_fixed = fixed_count - 20
                    if remaining_fixed > 0:
                        print(f"    ... and {remaining_fixed} more")
                    break

    # Constrained 버전 출력
    if constrained_with_versions > 0:
        print(f"\n[CONSTRAINED VERSIONS] ({constrained_with_versions} packages)")
        print("  These packages have multiple valid versions:")
        count = 0
        for pkg, info in resolved.items():
            if info['status'] == 'constrained' and info.get('valid_versions'):
                valid_count = len(info['valid_versions'])
                print(f"    {count+1}. {pkg}: {valid_count} valid versions")
                if valid_count <= 5:
                    print(f"        Options: {', '.join(info['valid_versions'])}")
                else:
                    print(f"        Sample: {', '.join(info['valid_versions'][:5])}...")
                count += 1
                if count >= 10:
                    remaining_constrained = constrained_with_versions - 10
                    if remaining_constrained > 0:
                        print(f"    ... and {remaining_constrained} more")
                    break

    # Constrained (no versions) 출력
    if constrained_no_versions > 0:
        print(f"\n[CONSTRAINED - NO VERSIONS] ({constrained_no_versions} packages)")
        print("  These packages are not in dep_space or have unsatisfiable constraints:")
        count = 0
        for pkg, info in resolved.items():
            if info['status'] == 'constrained' and not info.get('valid_versions'):
                in_dep_space = info.get('in_dep_space', False)
                status_str = "UNSATISFIABLE" if in_dep_space else "EXTERNAL"
                print(f"    {count+1}. {pkg} [{status_str}]")
                count += 1
                if count >= 10:
                    remaining_no_ver = constrained_no_versions - 10
                    if remaining_no_ver > 0:
                        print(f"    ... and {remaining_no_ver} more")
                    break

    # Remaining 패키지 출력
    if remaining:
        print(f"\n[REMAINING FOR SOLVER] ({len(remaining)} packages)")
        print("  These packages still need to be resolved by the solver:")
        remaining_list = sorted(remaining)
        for i, pkg in enumerate(remaining_list[:15]):
            print(f"    {i+1}. {pkg}")
        if len(remaining_list) > 15:
            print(f"    ... and {len(remaining_list) - 15} more")

    # 파일 출력 정보
    print(f"\n{'=' * 80}")
    print("OUTPUT FILES")
    print("=" * 80)

    data_dir = Path(__file__).parent.parent / "data"

    files_info = [
        ("dep_space_clean.json", "Cleaned dependency space for solver (Remaining + Unsatisfiable packages)"),
        ("precomputed.json", "Fixed + Constrained packages dep_space (Full version info)"),
    ]

    print(f"\n[DATA FILES] Saved to {data_dir}/")
    for filename, description in files_info:
        filepath = data_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / (1024*1024):.2f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.2f} KB"
            else:
                size_str = f"{size} bytes"
            print(f"  ✓ {filename} ({size_str})")
            print(f"    {description}")
        else:
            print(f"  ✗ {filename} (not found)")

    graph_files = [
        ("dependency_graph_initial.png", "Initial dependency graph"),
        ("dependency_graph_final.png", "Simplified dependency graph"),
    ]

    print(f"\n[VISUALIZATION FILES] Saved to {output_dir}/")
    for filename, description in graph_files:
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            size_str = f"{size / 1024:.2f} KB"
            print(f"  ✓ {filename} ({size_str})")
            print(f"    {description}")
        else:
            print(f"  ✗ {filename} (not found)")

    # 최종 요약
    print(f"\n{'=' * 80}")
    print("PREPROCESSING COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    reduction_rate = (1 - len(remaining) / total_packages) * 100 if total_packages > 0 else 0
    print(f"\n  Problem space reduction: {reduction_rate:.1f}%")
    print(f"  ({total_packages} packages → {len(remaining)} packages remaining)")
    print(f"\n  Next step: Use dep_space_clean.json with GA solver")
    print()


if __name__ == "__main__":
    main()
