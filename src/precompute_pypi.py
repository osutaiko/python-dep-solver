import json
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import utils
import parse

REQ_TXTS_DIR = utils.DATA_DIR / "requirements"
DEP_SPACE_PYPI_PATH = utils.DATA_DIR / "dep_space.json"
LOGS_DIR = utils.PROJECT_ROOT / "logs"


# class DualLogger:
#     """콘솔과 파일에 동시에 로그를 출력하는 클래스"""
#
#     def __init__(self, log_file):
#         self.terminal = sys.stdout
#         self.log = open(log_file, 'a', encoding='utf-8')
#
#     def write(self, message):
#         self.terminal.write(message)
#         self.log.write(message)
#         self.log.flush()
#
#     def flush(self):
#         self.terminal.flush()
#         self.log.flush()
#
#     def close(self):
#         self.log.close()


def load_all_packages(req_file=None):
    """
    requirements 파일(들)에서 모든 패키지 이름 추출
    """
    pkgs = set()
    files = [utils.DATA_DIR / "requirements" / req_file] if req_file else REQ_TXTS_DIR.glob("*.txt")
    for req_file in files:
        if not req_file.exists():
            continue
        for line in open(req_file, "r"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-e "):
                continue
            pkg_name = parse.extract_pkg_name(line)[0]
            pkgs.add(pkg_name)
    return sorted(pkgs)


def fetch_single_version_deps(package_name, version):
    """
    단일 버전의 의존성 정보를 가져오는 헬퍼 함수 (병렬 처리용)
    Runtime dependencies만 추출 (개발 의존성 제외)
    """
    try:
        requires_dist = utils.get_pypi_version_dependencies(package_name, version)

        if requires_dist is None:
            requires_dist = []

        depends_dict = {}
        deps_set = set()

        for req_str in requires_dist:
            if "extra ==" in req_str:
                continue

            if ";" in req_str:
                req_str = req_str.split(";")[0].strip()

            req_str = req_str.replace("(", "").replace(")", "").strip()

            if not req_str:
                continue

            pkg_name, constraint_str = parse.extract_pkg_name(req_str)

            if constraint_str:
                dep, conds = utils.parse_constraint_str(f"{pkg_name} {constraint_str}")
            else:
                dep, conds = pkg_name.lower(), []

            if dep:
                depends_dict[dep] = conds
                deps_set.add(dep)

        return (version, depends_dict, deps_set)

    except Exception as e:
        print(f"Failed to fetch {package_name}=={version}: {e}")
        return None


def fetch_pypi_package_metadata(package_name, max_workers=15):
    """
    PyPI에서 특정 패키지의 모든 버전과 의존성 정보 가져오기 (병렬 처리)
    """
    try:
        print(f"  Fetching versions for {package_name}...")
        all_versions = utils.get_pypi_all_versions(package_name)

        if not all_versions:
            print(f"  ---WARNING No versions found for {package_name}")
            return [], set()

        print(f"  Found {len(all_versions)} versions")
        print(f"  Fetching dependencies in parallel (max_workers={max_workers})...")

        extracted_data = []
        all_deps = set()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_single_version_deps, package_name, version): version
                for version in all_versions
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                version = futures[future]

                if completed % max(1, len(all_versions) // 10) == 0 or completed == len(all_versions):
                    progress = (completed / len(all_versions)) * 100
                    print(f"    Progress: {completed}/{len(all_versions)} ({progress:.1f}%)")

                try:
                    result = future.result()
                    if result:
                        ver, depends_dict, deps_set = result

                        extracted_data.append({
                            "version": ver,
                            "depends": depends_dict,
                            "constrains": {}
                        })
                        all_deps.update(deps_set)

                except Exception as e:
                    print(f"Failed to process {package_name}=={version}: {e}")
                    continue

        print(f"  Successfully fetched {len(extracted_data)}/{len(all_versions)} versions")
        return extracted_data, all_deps

    except Exception as e:
        print(f"Failed to fetch package {package_name}: {e}")
        return [], set()


def precompute_pypi(req_file=None, max_depth=None, enable_logging=True, max_workers=15):
    """
    PyPI를 사용하여 dependency space 생성 (병렬 처리 버전)
    Runtime dependencies만 포함 (개발 의존성 제외)
    """
    # logger = None
    # if enable_logging:
    #     LOGS_DIR.mkdir(exist_ok=True)
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     log_filename = f"precompute_pypi_{timestamp}.log"
    #     log_path = LOGS_DIR / log_filename
    #     logger = DualLogger(log_path)
    #     sys.stdout = logger
    #     print(f"[LOG] Logging to: {log_path}\n")

    try:
        if DEP_SPACE_PYPI_PATH.exists():
            with open(DEP_SPACE_PYPI_PATH, "r") as f:
                dep_space = json.load(f)
            print(f"Loaded existing dep_space with {len(dep_space)} packages")
        else:
            dep_space = {}

        if req_file:
            print(f"Loading packages from {req_file}...")
        else:
            print("Loading packages from data/requirements/*.txt...")

        packages = load_all_packages(req_file)
        print(f"Found {len(packages)} initial packages: {packages}\n")

        deps_done = set(dep_space.keys())

        if dep_space:
            print(f"Reconstructing queue from existing dep_space ({len(dep_space)} packages)...")

            temp_queue = list(packages)
            temp_done = set()
            temp_depth_map = {pkg: 0 for pkg in packages}

            final_queue = []
            final_depth_map = {}
            final_queue_set = set()
            found_unprocessed = False

            while temp_queue:
                pkg = temp_queue.pop(0)
                if pkg in temp_done:
                    continue
                temp_done.add(pkg)

                current_depth = temp_depth_map.get(pkg, 0)

                if pkg not in dep_space:
                    if not found_unprocessed:
                        print(f"  Found first unprocessed package: {pkg} (depth: {current_depth})")
                        found_unprocessed = True

                    if pkg not in final_queue_set:
                        final_queue.append(pkg)
                        final_depth_map[pkg] = current_depth
                        final_queue_set.add(pkg)

                    while temp_queue:
                        remaining = temp_queue.pop(0)
                        if remaining in temp_done:
                            continue
                        temp_done.add(remaining)

                        remaining_depth = temp_depth_map.get(remaining, 0)

                        if remaining in dep_space:
                            all_child_deps = set()
                            for ver, data in dep_space[remaining].items():
                                depends = data.get('depends', {})
                                all_child_deps.update(depends.keys())

                            for child in all_child_deps:
                                if child not in temp_done and child not in temp_queue:
                                    temp_queue.append(child)
                                    temp_depth_map[child] = remaining_depth + 1
                        else:
                            if remaining not in final_queue_set:
                                final_queue.append(remaining)
                                final_depth_map[remaining] = remaining_depth
                                final_queue_set.add(remaining)

                    break

                all_child_deps = set()
                for ver, data in dep_space[pkg].items():
                    depends = data.get('depends', {})
                    all_child_deps.update(depends.keys())

                for child in all_child_deps:
                    if child not in temp_done and child not in temp_queue:
                        temp_queue.append(child)
                        temp_depth_map[child] = current_depth + 1

            deps_queue = final_queue
            depth_map = final_depth_map

            print(f"  Queue reconstructed: {len(deps_queue)} packages to process")
            print(f"  Already processed: {len(deps_done)} packages")
            if deps_queue:
                print(f"  Next to process: {deps_queue[0]} (depth: {depth_map[deps_queue[0]]})")
        else:
            deps_queue = list(packages)
            depth_map = {pkg: 0 for pkg in packages}

        print(f"\n{'='*60}")
        print(f"Starting parallel processing with {max_workers} workers")
        print(f"FILTERING: Excluding dev dependencies (extra == ...)")
        print(f"{'='*60}\n")

        processed_count = 0
        skipped_count = 0
        start_time = time.time()

        while deps_queue:
            pkg = deps_queue.pop(0)

            if pkg in deps_done:
                skipped_count += 1
                continue

            current_depth = depth_map.get(pkg, 0)
            if max_depth is not None and current_depth > max_depth:
                print(f"[SKIP] {pkg} (depth {current_depth} > max {max_depth})")
                continue

            print(f"\n[{processed_count + 1}] Processing: {pkg} (depth: {current_depth})")
            deps_done.add(pkg)
            processed_count += 1

            metadata, child_deps = fetch_pypi_package_metadata(pkg, max_workers=max_workers)

            if not metadata:
                print(f"  [WARNING] {pkg}: no PyPI metadata, saving as empty")
                if pkg not in dep_space:
                    dep_space[pkg] = {}
                continue

            dep_space[pkg] = {}
            for m in metadata:
                ver = m["version"]
                dep_space[pkg][ver] = {
                    "depends": m["depends"],
                    "constrains": m["constrains"],
                }

            print(f"  Saved {len(metadata)} versions for {pkg}")

            new_deps = []
            for child in child_deps:
                if child not in deps_done and child not in deps_queue:
                    deps_queue.append(child)
                    depth_map[child] = current_depth + 1
                    new_deps.append(child)

            if new_deps:
                print(f"  Added {len(new_deps)} new dependencies to queue: {new_deps[:5]}{'...' if len(new_deps) > 5 else ''}")

            if processed_count % 100 == 0:
                with open(DEP_SPACE_PYPI_PATH, "w") as f:
                    json.dump(dep_space, f, indent=2)
                print(f"\n  --CHECKPOINT Saved progress: {len(dep_space)} packages")

            time.sleep(0.1)

        with open(DEP_SPACE_PYPI_PATH, "w") as f:
            json.dump(dep_space, f, indent=2)

        elapsed_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"  Precomputation completed!")
        print(f"  Total packages processed: {processed_count}")
        print(f"  Total packages in dep_space: {len(dep_space)}")
        print(f"  Elapsed time: {elapsed_time:.1f}s ({elapsed_time/60:.1f}m)")
        print(f"  Saved to: {DEP_SPACE_PYPI_PATH}")
        print(f"{'='*60}")

    finally:
        pass
        # if logger:
        #     sys.stdout = logger.terminal
        #     logger.close()
        #     print(f"\nLog saved to: {log_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PyPI를 사용하여 dependency space 생성 (Runtime deps only)")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="특정 requirements 파일명 (기본값: 모든 .txt 파일)"
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="최대 탐색 깊이 (기본값: 무제한)"
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="로그 파일 저장 안 함"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=15,
        help="병렬 worker 수 (기본값: 15)"
    )

    args = parser.parse_args()

    print("Starting PyPI dependency space precomputation (Runtime deps only)...")
    print(f"Configuration:")
    print(f"  Requirements file: {args.file if args.file else 'All .txt files'}")
    print(f"  Max depth: {args.max_depth if args.max_depth else 'Unlimited'}")
    print(f"  Workers: {args.workers}")
    print(f"  Logging: {'Disabled' if args.no_log else 'Enabled'}")
    print(f"  Filtering: Excluding dev dependencies (extra == ...)")
    print()

    precompute_pypi(
        req_file=args.file,
        max_depth=args.max_depth,
        enable_logging=not args.no_log,
        max_workers=args.workers
    )
