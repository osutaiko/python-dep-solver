from collections import defaultdict, deque
from packaging.version import Version
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import utils

import json
import os

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False


class DependencyGraph:
    """
    directed graph로 변형시켜서 보기 편하게 하는 package
    
    module : node
    dependency : edge
    """

    def __init__(self, dep_space, visualize_initial=False, output_dir=None):

        self.dep_space = self._convert_dep_space_to_list(dep_space)
        self.graph = defaultdict(lambda: defaultdict(list))
        self.reverse_graph = defaultdict(lambda: defaultdict(list))
        self.resolved = {}

        self._build_graph()


        if visualize_initial and output_dir:
            import os
            os.makedirs(output_dir, exist_ok=True)
            initial_graph_path = os.path.join(output_dir, "dependency_graph_initial.png")
            self.visualize(output_path=initial_graph_path, show_versions=False)

    def _convert_dep_space_to_list(self, dep_space):
        """
        input 형식:  {pkg: {ver_str: {depends: {...}, constrains: {...}}}}
        output 형식: {pkg: [(ver_obj, ver_str, depends, constrains), ...]}
        """
        converted = {}

        for pkg, versions in dep_space.items():
            version_list = []
            for ver_str, metadata in versions.items():
                try:
                    ver_obj = Version(ver_str)
                    version_list.append({
                        'version_obj': ver_obj,
                        'version_str': ver_str,
                        'depends': metadata['depends'],
                        'constrains': metadata.get('constrains', {})
                    })
                except Exception:
                    continue

            version_list.sort(key=lambda x: x['version_obj'], reverse=True)
            converted[pkg] = version_list

        return converted

    def _build_graph(self):
        all_packages = set(self.dep_space.keys())

        queue = deque(all_packages)
        visited = set()

        while queue:
            pkg = queue.popleft()
            if pkg in visited or pkg not in self.dep_space:
                continue

            visited.add(pkg)

            for ver_info in self.dep_space[pkg]:
                depends = ver_info['depends']

                for dep_pkg, conditions in depends.items():
                    if dep_pkg == 'python':
                        continue

                    self.graph[pkg][dep_pkg].append({
                        'version': ver_info['version_str'],
                        'conditions': conditions
                    })

                    self.reverse_graph[dep_pkg][pkg].append({
                        'version': ver_info['version_str'],
                        'conditions': conditions
                    })

                    if dep_pkg not in visited and dep_pkg in self.dep_space:
                        queue.append(dep_pkg)

    def get_leaf_nodes(self):
        """
        모든 leaf node 찾기 
        """
        all_nodes = set(self.graph.keys()) | set(self.reverse_graph.keys())
        return {node for node in all_nodes if node not in self.graph or not self.graph[node]}

    def get_constraints_for_package(self, pkg):
        """
        package에 걸린 모든 제약 조건 수집
        """
        all_conditions = []

        if pkg in self.reverse_graph:
            for parent_pkg, dep_list in self.reverse_graph[pkg].items():
                for dep_info in dep_list:
                    all_conditions.extend(dep_info['conditions'])

        return all_conditions

    def find_version_intersection(self, pkg, conditions):
        """
        제약조건 교집합 찾기
        """
        if pkg not in self.dep_space:
            return []

        if not conditions:
            return [v['version_str'] for v in self.dep_space[pkg]]

        valid_versions = []

        for ver_info in self.dep_space[pkg]:
            ver_str = ver_info['version_str']

            satisfies_all = True
            for cond in conditions:
                if isinstance(cond.get('ver'), str) and cond['ver'].endswith('.*'):
                    continue

                try:
                    if not utils.cmp_v(ver_str, cond['op'], cond['ver']):
                        satisfies_all = False
                        break
                except Exception:
                    continue

            if satisfies_all:
                valid_versions.append(ver_str)

        return valid_versions

    def remove_node(self, pkg):
        """
        graph에서 제거 
        """
        if pkg in self.graph:
            del self.graph[pkg]

        if pkg in self.reverse_graph:
            del self.reverse_graph[pkg]

        for parent in list(self.graph.keys()):
            if pkg in self.graph[parent]:
                del self.graph[parent][pkg]

        for child in list(self.reverse_graph.keys()):
            if pkg in self.reverse_graph[child]:
                del self.reverse_graph[child][pkg]

    def simplify(self):
        iterations = 0
        max_iterations = 1000

        while iterations < max_iterations:
            iterations += 1
            leaf_nodes = self.get_leaf_nodes()

            if not leaf_nodes:
                break

            made_progress = False

            for pkg in leaf_nodes:
                if pkg in self.resolved:
                    continue
                
                conditions = self.get_constraints_for_package(pkg)
                
                valid_versions = self.find_version_intersection(pkg, conditions)

                if len(valid_versions) == 0:
                    in_dep_space = pkg in self.dep_space
                    self.resolved[pkg] = {
                        'status': 'constrained',
                        'conditions': conditions,
                        'valid_versions': [],
                        'in_dep_space': in_dep_space
                    }
                    self.remove_node(pkg)
                    made_progress = True
                elif len(valid_versions) == 1:
                    self.resolved[pkg] = {'status': 'fixed', 'version': valid_versions[0]}
                    self.remove_node(pkg)
                    made_progress = True
                else:
                    self.resolved[pkg] = {
                        'status': 'constrained',
                        'conditions': conditions,
                        'valid_versions': valid_versions
                    }
                    self.remove_node(pkg)
                    made_progress = True

            if not made_progress:
                break

        return self.resolved

    def get_remaining_packages(self):
        """
        해결되지 않은 package 가져오기
        """
        all_nodes = set(self.graph.keys()) | set(self.reverse_graph.keys())
        return all_nodes - set(self.resolved.keys())

    def visualize(self, output_path=None, show_versions=False):
        if not HAS_VISUALIZATION:
            print("[ERROR] networkx와 matplotlib이 필요합니다.")
            print("설치: pip install networkx matplotlib")
            return

        G = nx.DiGraph()

        all_nodes = set(self.graph.keys()) | set(self.reverse_graph.keys())
        for node in all_nodes:
            if node in self.resolved:
                status = self.resolved[node]['status']
                if status == 'fixed':
                    color = 'lightgreen'
                elif status == 'constrained':
                    color = 'lightblue'
                else:
                    color = 'lightcoral'
            else:
                color = 'lightgray'

            G.add_node(node, color=color)

        for parent, children in self.graph.items():
            for child, dep_list in children.items():
                if show_versions:
                    conditions = set()
                    for dep in dep_list:
                        for cond in dep['conditions']:
                            conditions.add(f"{cond['op']}{cond['ver']}")
                    label = ','.join(list(conditions)[:3])
                    if len(conditions) > 3:
                        label += '...'
                    G.add_edge(parent, child, label=label)
                else:
                    G.add_edge(parent, child)

        try:
            pos = nx.spring_layout(G, k=2, iterations=50)
        except:
            pos = nx.shell_layout(G)

        plt.figure(figsize=(16, 12))
        node_colors = [G.nodes[node].get('color', 'lightgray') for node in G.nodes()]
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=800, alpha=0.9)
        nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True,
                              arrowsize=20, arrowstyle='->', width=1.5)
        nx.draw_networkx_labels(G, pos, font_size=9, font_weight='bold')
        if show_versions:
            edge_labels = nx.get_edge_attributes(G, 'label')
            nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=6)

        plt.title("Dependency Graph\n" +
                 "Green: Fixed | Blue: Constrained | Red: Conflict | Gray: Unresolved",
                 fontsize=14)
        plt.axis('off')
        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()

        plt.close()


def build_dep_space_from_requirements(proj_constraints, dep_space):
    """
    proj_constraints 로 새로운 dep_space 만들기
    """
    dep_space_req = {}
    queue = deque(proj_constraints.keys())
    visited = set()

    while queue:
        pkg = queue.popleft()

        if pkg in visited:
            continue

        visited.add(pkg)

        if pkg not in dep_space:
            continue

        dep_space_req[pkg] = dep_space[pkg]

        for ver_str, metadata in dep_space[pkg].items():
            for dep_pkg in metadata.get('depends', {}).keys():
                if dep_pkg != 'python' and dep_pkg not in visited:
                    queue.append(dep_pkg)

            for const_pkg in metadata.get('constrains', {}).keys():
                if const_pkg != 'python' and const_pkg not in visited:
                    queue.append(const_pkg)

    return dep_space_req


def create_clean_dep_space(original_dep_space, resolved, remaining):
    dep_space_clean = {}
    fixed_versions = {}
    constrained_versions = {}
    precomputed_dep_space = {}

    for pkg, info in resolved.items():
        if info['status'] == 'fixed':
            fixed_versions[pkg] = info['version']
            if pkg in original_dep_space:
                precomputed_dep_space[pkg] = original_dep_space[pkg]

    for pkg, info in resolved.items():
        if info['status'] == 'constrained' and info.get('valid_versions'):
            constrained_versions[pkg] = {
                'valid_versions': info['valid_versions'],
                'conditions': info['conditions']
            }
            if pkg in original_dep_space:
                precomputed_dep_space[pkg] = original_dep_space[pkg]

    for pkg, info in resolved.items():
        if info['status'] == 'constrained' and not info.get('valid_versions'):
            if info.get('in_dep_space') and pkg in original_dep_space:
                dep_space_clean[pkg] = original_dep_space[pkg]

    for pkg in remaining:
        if pkg in original_dep_space:
            dep_space_clean[pkg] = original_dep_space[pkg]

    return dep_space_clean, fixed_versions, constrained_versions, precomputed_dep_space


def preprocess_dependencies(dep_space, proj_constraints=None, visualize=False, output_dir=None, save_clean=True):
    """
    main

    Args:
        dep_space: 전체 dependency space
        proj_constraints: optional, {pkg_name: [conditions]} 형태의 프로젝트 제약조건
        visualize: 시각화 여부
        output_dir: 출력 디렉토리
        save_clean: 파일 저장 여부
    """
    # proj_constraints가 있으면 필요한 패키지만 추출
    if proj_constraints:
        dep_space = build_dep_space_from_requirements(proj_constraints, dep_space)

    graph = DependencyGraph(dep_space,
                           visualize_initial=visualize,
                           output_dir=output_dir)

    resolved = graph.simplify()
    remaining = graph.get_remaining_packages()

    dep_space_clean, fixed_versions, constrained_versions, precomputed_dep_space = create_clean_dep_space(
        dep_space, resolved, remaining
    )

    if save_clean:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        data_dir = os.path.join(project_root, 'data')

        clean_path = os.path.join(data_dir, 'dep_space_clean.json')
        precomputed_path = os.path.join(data_dir, 'precomputed.json')

        with open(clean_path, 'w') as f:
            json.dump(dep_space_clean, f, indent=2)

        with open(precomputed_path, 'w') as f:
            json.dump(precomputed_dep_space, f, indent=2)

    if visualize and output_dir:
        final_graph_path = os.path.join(output_dir, "dependency_graph_final.png")
        graph.visualize(output_path=final_graph_path, show_versions=False)

    return {
        'resolved': resolved,
        'remaining': remaining,
        'dep_space_clean': dep_space_clean,
        'fixed_versions': fixed_versions,
        'constrained_versions': constrained_versions,
        'precomputed_dep_space': precomputed_dep_space,
        'graph': graph
    }
