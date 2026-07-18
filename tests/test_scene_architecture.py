import ast
import unittest
from collections.abc import Iterable, Mapping
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPOSITORY_ROOT / "engine"
SCENES_ROOT = ENGINE_ROOT / "scenes"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _attribute_chain(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (*_attribute_chain(node.value), node.attr)
    return ()


def _is_type_checking_guard(
    node: ast.AST,
    type_checking_names: set[str],
    typing_module_names: set[str],
) -> bool:
    chain = _attribute_chain(node)
    return (
        len(chain) == 1
        and chain[0] in type_checking_names
        or len(chain) == 2
        and chain[0] in typing_module_names
        and chain[1] == "TYPE_CHECKING"
    )


class _RuntimeImportVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.modules: list[str] = []
        self.qualified_names: list[str] = []
        self.type_checking_names = {"TYPE_CHECKING"}
        self.typing_module_names = {"typing"}

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_guard(
            node.test,
            self.type_checking_names,
            self.typing_module_names,
        ):
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "typing":
                self.typing_module_names.add(alias.asname or alias.name)
        self.modules.extend(alias.name for alias in node.names)
        self.qualified_names.extend(alias.name for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = _absolute_import_from_module(self.path, node)
        if module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    self.type_checking_names.add(alias.asname or alias.name)
        if module:
            self.modules.append(module)
        for alias in node.names:
            qualified = f"{module}.{alias.name}" if module else alias.name
            self.modules.append(qualified)
            self.qualified_names.append(qualified)


def _module_package(path: Path) -> str:
    try:
        relative = path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        relative = path
    parts = relative.with_suffix("").parts
    return ".".join(parts[:-1])


def _absolute_import_from_module(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = _module_package(path).split(".") if _module_package(path) else []
    parents = node.level - 1
    base = package[: max(0, len(package) - parents)]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _runtime_imports_from_tree(path: Path, tree: ast.Module) -> list[str]:
    visitor = _RuntimeImportVisitor(path)
    visitor.visit(tree)
    return list(dict.fromkeys(visitor.modules))


def _runtime_imported_names_from_tree(path: Path, tree: ast.Module) -> list[str]:
    visitor = _RuntimeImportVisitor(path)
    visitor.visit(tree)
    return list(dict.fromkeys(visitor.qualified_names))


def _runtime_imports(path: Path) -> list[str]:
    return _runtime_imports_from_tree(path, _parse(path))


def _runtime_imported_names(path: Path) -> list[str]:
    return _runtime_imported_names_from_tree(path, _parse(path))


def _runtime_scene_manager_imports(path: Path, tree: ast.Module) -> list[str]:
    return [
        imported
        for imported in _runtime_imported_names_from_tree(path, tree)
        if imported == "engine.scenes.SceneManager"
        or imported == "engine.scenes.scene_manager"
        or imported.startswith("engine.scenes.scene_manager.")
    ]


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"method {class_node.name}.{name} not found")


def _assigned_attributes(tree: ast.AST) -> Iterable[ast.Attribute]:
    def unpack(target: ast.AST) -> Iterable[ast.Attribute]:
        if isinstance(target, ast.Attribute):
            yield target
        elif isinstance(target, (ast.List, ast.Tuple)):
            for element in target.elts:
                yield from unpack(element)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield from unpack(target)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            yield from unpack(node.target)


_SCOPE_BOUNDARIES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _scope_nodes(scope: ast.AST) -> list[ast.AST]:
    nodes: list[ast.AST] = []
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        if isinstance(node, _SCOPE_BOUNDARIES):
            continue
        nodes.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return nodes


def _target_chains(target: ast.AST) -> Iterable[tuple[str, ...]]:
    if isinstance(target, (ast.Name, ast.Attribute)):
        chain = _attribute_chain(target)
        if chain:
            yield chain
    elif isinstance(target, (ast.List, ast.Tuple)):
        for element in target.elts:
            yield from _target_chains(element)


def _is_workspace_entry_annotation(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return "SceneWorkspaceEntry" in annotation.value
    return any(
        (isinstance(node, ast.Name) and node.id == "SceneWorkspaceEntry")
        or (isinstance(node, ast.Attribute) and node.attr == "SceneWorkspaceEntry")
        for node in ast.walk(annotation)
    )


def _annotation_type_names(annotation: ast.AST | None) -> set[str]:
    if annotation is None:
        return set()
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        annotation_text = annotation.value
        try:
            annotation = ast.parse(annotation_text, mode="eval").body
        except SyntaxError:
            return {annotation_text}
    return {
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(annotation)
        if isinstance(node, (ast.Name, ast.Attribute))
    }


def _is_workspace_owner_annotation(annotation: ast.AST | None) -> bool:
    return any(
        "SceneWorkspace" in name
        or "SceneManager" in name
        or name.endswith("WorkspacePort")
        for name in _annotation_type_names(annotation)
    )


_WORKSPACE_RECEIVER_NAMES = {
    "manager",
    "manager_port",
    "scene_manager",
    "scene_workspace",
    "workspace",
    "workspace_port",
}


def _looks_like_workspace_receiver(node: ast.AST) -> bool:
    chain = _attribute_chain(node)
    return bool(chain) and chain[-1].lstrip("_") in _WORKSPACE_RECEIVER_NAMES


def _is_workspace_entries_collection(node: ast.AST) -> bool:
    chain = _attribute_chain(node)
    if chain[-1:] == ("entries",):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in {"items", "values"} and _is_workspace_entries_collection(node.func.value)
    return False


def _is_workspace_entries_iterable(node: ast.AST) -> bool:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"items", "values"}
        and _is_workspace_entries_collection(node.func.value)
    ):
        return True
    return (
        isinstance(node, ast.Call)
        and _attribute_chain(node.func)[-1:] in {("enumerate",), ("iter",)}
        and any(_is_workspace_entries_iterable(argument) for argument in node.args)
    )


def _workspace_iteration_entry_targets(
    target: ast.AST,
    iterable: ast.AST,
) -> Iterable[tuple[str, ...]]:
    if isinstance(iterable, ast.Call):
        call_name = _attribute_chain(iterable.func)[-1:]
        if call_name == ("iter",) and iterable.args:
            yield from _workspace_iteration_entry_targets(target, iterable.args[0])
            return
        if call_name == ("enumerate",) and iterable.args:
            if isinstance(target, (ast.List, ast.Tuple)) and len(target.elts) >= 2:
                yield from _workspace_iteration_entry_targets(target.elts[1], iterable.args[0])
            return
        if isinstance(iterable.func, ast.Attribute) and _is_workspace_entries_collection(
            iterable.func.value
        ):
            if iterable.func.attr == "values":
                yield from _target_chains(target)
            elif (
                iterable.func.attr == "items"
                and isinstance(target, (ast.List, ast.Tuple))
                and len(target.elts) >= 2
            ):
                yield from _target_chains(target.elts[1])


def _workspace_entries_iterable_yields_entry(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    call_name = _attribute_chain(node.func)[-1:]
    if call_name == ("iter",) and node.args:
        return _workspace_entries_iterable_yields_entry(node.args[0])
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "values"
        and _is_workspace_entries_collection(node.func.value)
    )


def _workspace_owner_receivers(scope: ast.AST, nodes: list[ast.AST]) -> set[tuple[str, ...]]:
    receivers: set[tuple[str, ...]] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = [
            *scope.args.posonlyargs,
            *scope.args.args,
            *scope.args.kwonlyargs,
        ]
        for argument in arguments:
            if _is_workspace_owner_annotation(argument.annotation):
                receivers.add((argument.arg,))
    for node in nodes:
        if isinstance(node, ast.AnnAssign) and _is_workspace_owner_annotation(node.annotation):
            receivers.update(_target_chains(node.target))
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            value = node.value
            if value is None or not _is_workspace_owner_expression(value, receivers):
                continue
            for target in targets:
                for chain in _target_chains(target):
                    if chain not in receivers:
                        receivers.add(chain)
                        changed = True
    return receivers


def _is_workspace_owner_expression(
    node: ast.AST,
    workspace_receivers: set[tuple[str, ...]],
) -> bool:
    return _attribute_chain(node) in workspace_receivers or _looks_like_workspace_receiver(node)


def _is_workspace_entry_expression(
    node: ast.AST,
    receivers: set[tuple[str, ...]],
    workspace_receivers: set[tuple[str, ...]],
    entry_method_names: set[str],
) -> bool:
    if _attribute_chain(node) in receivers:
        return True
    if isinstance(node, ast.Call):
        call_name = _attribute_chain(node.func)[-1:]
        if isinstance(node.func, ast.Attribute):
            if (
                call_name in {("get_active_entry",), ("resolve_entry",), ("ensure_scene_open",)}
                and _is_workspace_owner_expression(node.func.value, workspace_receivers)
            ):
                return True
            if (
                node.func.attr in entry_method_names
                and _attribute_chain(node.func.value) == ("self",)
            ):
                return True
        if (
            call_name == ("get",)
            and isinstance(node.func, ast.Attribute)
            and _is_workspace_entries_collection(node.func.value)
        ):
            return True
        if call_name == ("next",) and any(
            _workspace_entries_iterable_yields_entry(argument) for argument in node.args
        ):
            return True
    if isinstance(node, ast.Subscript) and _is_workspace_entries_collection(node.value):
        return True
    if isinstance(node, ast.IfExp):
        return _is_workspace_entry_expression(
            node.body,
            receivers,
            workspace_receivers,
            entry_method_names,
        ) or _is_workspace_entry_expression(
            node.orelse,
            receivers,
            workspace_receivers,
            entry_method_names,
        )
    return False


def _workspace_entry_receivers(
    scope: ast.AST,
    nodes: list[ast.AST],
    inherited_receivers: set[tuple[str, ...]],
    workspace_receivers: set[tuple[str, ...]],
    entry_method_names: set[str],
) -> set[tuple[str, ...]]:
    receivers = set(inherited_receivers)
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = [
            *scope.args.posonlyargs,
            *scope.args.args,
            *scope.args.kwonlyargs,
        ]
        for argument in arguments:
            if _is_workspace_entry_annotation(argument.annotation):
                receivers.add((argument.arg,))

    for node in nodes:
        if isinstance(node, ast.AnnAssign) and _is_workspace_entry_annotation(node.annotation):
            receivers.update(_target_chains(node.target))

    changed = True
    while changed:
        changed = False
        for node in nodes:
            targets: Iterable[ast.AST] = ()
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = (node.target,)
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = (node.target,)
                value = node.value
            elif isinstance(node, (ast.For, ast.AsyncFor)) and _is_workspace_entries_iterable(node.iter):
                targets = ()
                value = node.iter
            if value is None:
                continue
            if isinstance(node, (ast.For, ast.AsyncFor)):
                chains = _workspace_iteration_entry_targets(node.target, value)
            elif _is_workspace_entry_expression(
                value,
                receivers,
                workspace_receivers,
                entry_method_names,
            ):
                chains = (
                    chain
                    for target in targets
                    for chain in _target_chains(target)
                )
            else:
                continue
            for chain in chains:
                if chain not in receivers:
                    receivers.add(chain)
                    changed = True
    return receivers


def _class_workspace_entry_receivers(class_node: ast.ClassDef) -> set[tuple[str, ...]]:
    receivers: set[tuple[str, ...]] = set()
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign) and _is_workspace_entry_annotation(node.annotation):
            for chain in _target_chains(node.target):
                receivers.add(("self", *chain) if len(chain) == 1 else chain)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for scoped_node in _scope_nodes(node):
                if not (
                    isinstance(scoped_node, ast.AnnAssign)
                    and _is_workspace_entry_annotation(scoped_node.annotation)
                ):
                    continue
                for chain in _target_chains(scoped_node.target):
                    if chain[:1] == ("self",):
                        receivers.add(chain)
    return receivers


def _class_workspace_entry_methods(class_node: ast.ClassDef) -> set[str]:
    return {
        node.name
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_workspace_entry_annotation(node.returns)
    }


def _workspace_entry_writer_violations(path: Path, tree: ast.Module) -> list[str]:
    if path == SCENES_ROOT / "workspace_lifecycle.py":
        return []
    entry_fields = {"dirty", "scene", "edit_world", "runtime_world"}
    violations: list[str] = []
    scopes = [tree, *(node for node in ast.walk(tree) if isinstance(node, _SCOPE_BOUNDARIES))]
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    class_receivers = {
        class_node: _class_workspace_entry_receivers(class_node)
        for class_node in ast.walk(tree)
        if isinstance(class_node, ast.ClassDef)
    }
    class_methods = {
        class_node: _class_workspace_entry_methods(class_node)
        for class_node in class_receivers
    }
    for scope in scopes:
        nodes = _scope_nodes(scope)
        parent = parents.get(scope)
        while parent is not None and not isinstance(parent, ast.ClassDef):
            parent = parents.get(parent)
        containing_class = parent if isinstance(parent, ast.ClassDef) else None
        inherited_receivers = (
            class_receivers.get(containing_class, set())
            if containing_class is not None
            else set()
        )
        entry_method_names = (
            class_methods.get(containing_class, set())
            if containing_class is not None
            else set()
        )
        workspace_receivers = _workspace_owner_receivers(scope, nodes)
        receivers = _workspace_entry_receivers(
            scope,
            nodes,
            inherited_receivers,
            workspace_receivers,
            entry_method_names,
        )
        for target in _assigned_attributes(scope):
            if target not in nodes:
                continue
            if target.attr in entry_fields and _is_workspace_entry_expression(
                target.value,
                receivers,
                workspace_receivers,
                entry_method_names,
            ):
                violations.append(
                    f"{path.relative_to(REPOSITORY_ROOT)}:{target.lineno}:{ast.unparse(target)}"
                )
    return violations


def _constructor_calls(tree: ast.AST, constructor: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _attribute_chain(node.func)[-1:] == (constructor,)
    ]


def _constructor_locations(
    production_trees: Mapping[str, ast.Module],
    constructor: str,
) -> list[str]:
    return [
        path
        for path, tree in production_trees.items()
        for _call in _constructor_calls(tree, constructor)
    ]


def _owner_dependency_edges(
    owner_modules: Mapping[str, set[str]],
    module_trees: Mapping[str, ast.Module] | None = None,
) -> dict[str, set[str]]:
    module_owner = {
        module: owner
        for owner, modules in owner_modules.items()
        for module in modules
    }
    edges: dict[str, set[str]] = {owner: set() for owner in owner_modules}
    for source_owner, modules in owner_modules.items():
        for module in modules:
            path = SCENES_ROOT / f"{module}.py"
            tree = module_trees[module] if module_trees is not None else _parse(path)
            for imported in _runtime_imports_from_tree(path, tree):
                prefix = "engine.scenes."
                if not imported.startswith(prefix):
                    continue
                target_module = imported.removeprefix(prefix).split(".", 1)[0]
                target_owner = module_owner.get(target_module)
                if target_owner is not None and target_owner != source_owner:
                    edges[source_owner].add(target_owner)
    return edges


class SceneServiceDependencyTests(unittest.TestCase):
    def test_services_do_not_import_scene_manager_at_runtime(self) -> None:
        violations: list[str] = []
        for path in sorted(SCENES_ROOT.rglob("*.py")):
            if path == SCENES_ROOT / "scene_manager.py":
                continue
            for imported in _runtime_scene_manager_imports(path, _parse(path)):
                violations.append(
                    f"{path.relative_to(SCENES_ROOT).as_posix()}: {imported}"
                )

        self.assertEqual(violations, [])

    def test_contract_and_lazy_export_boundaries_have_no_runtime_manager_import(self) -> None:
        contracts_imports = _runtime_imported_names(SCENES_ROOT / "contracts.py")
        package_imports = _runtime_imported_names(SCENES_ROOT / "__init__.py")

        self.assertFalse(any("scene_manager" in imported for imported in contracts_imports))
        self.assertFalse(any("scene_manager" in imported for imported in package_imports))

    def test_structural_serializable_history_workspace_projection_graph_is_acyclic(self) -> None:
        owner_modules = {
            "structural": {"structural_authoring"},
            "serializable": {
                "component_authoring",
                "entity_authoring",
                "serializable_authoring",
                "serializable_mutation",
                "serializable_pipeline",
            },
            "history": {"change_history"},
            "workspace": {"workspace_lifecycle"},
            "projection": {"scene_projection"},
        }
        edges = _owner_dependency_edges(owner_modules)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(owner: str, path: tuple[str, ...]) -> None:
            if owner in visiting:
                self.fail("owner dependency cycle: " + " -> ".join((*path, owner)))
            if owner in visited:
                return
            visiting.add(owner)
            for dependency in sorted(edges[owner]):
                visit(dependency, (*path, owner))
            visiting.remove(owner)
            visited.add(owner)

        for owner in sorted(edges):
            visit(owner, ())

    def test_runtime_import_helper_normalizes_absolute_and_relative_forms(self) -> None:
        path = SCENES_ROOT / "probe.py"
        tree = ast.parse(
            "\n".join(
                (
                    "from engine.scenes.scene_manager import SceneManager",
                    "from .scene_manager import SceneManager",
                    "from . import scene_manager",
                    "from .workspace_lifecycle import SceneWorkspace",
                )
            )
        )

        imports = set(_runtime_imports_from_tree(path, tree))
        imported_names = set(_runtime_imported_names_from_tree(path, tree))

        self.assertIn("engine.scenes.scene_manager", imports)
        self.assertIn("engine.scenes.workspace_lifecycle", imports)
        self.assertIn("engine.scenes.scene_manager.SceneManager", imported_names)
        self.assertIn("engine.scenes.scene_manager", imported_names)
        self.assertEqual(
            set(_runtime_scene_manager_imports(path, tree)),
            {
                "engine.scenes.scene_manager.SceneManager",
                "engine.scenes.scene_manager",
            },
        )

    def test_relative_import_creates_owner_graph_edge(self) -> None:
        edges = _owner_dependency_edges(
            {
                "structural": {"probe_structural"},
                "workspace": {"workspace_lifecycle"},
            },
            {
                "probe_structural": ast.parse(
                    "from .workspace_lifecycle import SceneWorkspace"
                ),
                "workspace_lifecycle": ast.parse(""),
            },
        )

        self.assertEqual(edges, {"structural": {"workspace"}, "workspace": set()})

    def test_nested_relative_manager_import_normalizes_to_repository_module(self) -> None:
        path = SCENES_ROOT / "nested" / "probe.py"
        tree = ast.parse("from ..scene_manager import SceneManager")

        self.assertEqual(
            _runtime_scene_manager_imports(path, tree),
            ["engine.scenes.scene_manager.SceneManager"],
        )

    def test_type_checking_imports_are_not_runtime_dependencies(self) -> None:
        path = SCENES_ROOT / "probe.py"
        tree = ast.parse(
            "\n".join(
                (
                    "from typing import TYPE_CHECKING",
                    "if TYPE_CHECKING:",
                    "    from .scene_manager import SceneManager",
                    "else:",
                    "    from .workspace_lifecycle import SceneWorkspace",
                )
            )
        )

        self.assertEqual(_runtime_scene_manager_imports(path, tree), [])
        self.assertIn(
            "engine.scenes.workspace_lifecycle",
            _runtime_imports_from_tree(path, tree),
        )

    def test_type_checking_aliases_are_not_runtime_dependencies(self) -> None:
        path = SCENES_ROOT / "probe.py"
        tree = ast.parse(
            "\n".join(
                (
                    "from typing import TYPE_CHECKING as TC",
                    "import typing as t",
                    "if TC:",
                    "    from .scene_manager import SceneManager as FirstManager",
                    "if t.TYPE_CHECKING:",
                    "    from .scene_manager import SceneManager as SecondManager",
                )
            )
        )

        self.assertEqual(_runtime_scene_manager_imports(path, tree), [])


class SceneOwnershipArchitectureTests(unittest.TestCase):
    def test_structural_has_exact_four_dependencies_and_no_manager_context(self) -> None:
        tree = _parse(SCENES_ROOT / "structural_authoring.py")
        structural = _class(tree, "SceneStructuralAuthoring")
        constructor = _method(structural, "__init__")
        parameters = [*constructor.args.posonlyargs, *constructor.args.args]
        self.assertEqual(
            [parameter.arg for parameter in parameters],
            ["self", "workspace", "pipeline", "serializable_entities", "prefab_overrides"],
        )
        annotations = [parameter.annotation for parameter in parameters[1:]]
        self.assertTrue(all(annotation is not None for annotation in annotations))
        self.assertEqual(
            [ast.unparse(annotation) for annotation in annotations if annotation is not None],
            [
                "SceneWorkspace",
                "SceneSerializableTransactionPort",
                "SceneSerializableEntityPort",
                "PrefabOverridePort",
            ],
        )
        self.assertEqual(constructor.args.kwonlyargs, [])
        self.assertIsNone(constructor.args.vararg)
        self.assertIsNone(constructor.args.kwarg)
        self.assertFalse(
            any(
                isinstance(node, ast.ClassDef) and node.name == "SceneStructuralAuthoringContext"
                for path in SCENES_ROOT.rglob("*.py")
                for node in ast.walk(_parse(path))
            )
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Attribute) and node.attr == "_manager"
                for node in ast.walk(structural)
            )
        )

    def test_scene_storage_and_workspace_entry_state_have_single_writers(self) -> None:
        scene_storage_fields = {"data", "entities_data", "_data", "_entities_data"}
        entry_violations: list[str] = []
        storage_violations: list[str] = []

        for path in sorted(ENGINE_ROOT.rglob("*.py")):
            tree = _parse(path)
            entry_violations.extend(_workspace_entry_writer_violations(path, tree))
            for target in _assigned_attributes(tree):
                receiver = _attribute_chain(target.value)
                if (
                    target.attr in scene_storage_fields
                    and path != SCENES_ROOT / "scene.py"
                    and (path.parent == SCENES_ROOT or receiver[-1:] in {("scene",), ("_scene",)})
                ):
                    storage_violations.append(
                        f"{path.relative_to(REPOSITORY_ROOT)}:{target.lineno}:{ast.unparse(target)}"
                    )

        self.assertEqual(entry_violations, [])
        self.assertEqual(storage_violations, [])

    def test_workspace_entry_writer_helper_detects_typed_and_resolved_receivers(self) -> None:
        probes = {
            ENGINE_ROOT / "api" / "typed_probe.py": """
def mutate(entry: SceneWorkspaceEntry) -> None:
    entry.dirty = True
""",
            ENGINE_ROOT / "api" / "resolved_probe.py": """
def mutate(workspace) -> None:
    entry = workspace.resolve_entry("scene")
    entry.scene = replacement
""",
            ENGINE_ROOT / "features" / "nested" / "active_probe.py": """
def mutate(workspace) -> None:
    active = workspace.get_active_entry()
    active.edit_world = replacement
""",
            ENGINE_ROOT / "features" / "nested" / "entries_probe.py": """
def mutate(workspace) -> None:
    for candidate in workspace.entries.values():
        candidate.runtime_world = replacement
""",
            ENGINE_ROOT / "features" / "nested" / "next_entry_probe.py": """
def mutate(workspace) -> None:
    candidate = next(iter(workspace.entries.values()))
    candidate.scene = replacement
""",
            ENGINE_ROOT / "features" / "nested" / "annotated_probe.py": """
def mutate(candidate: Optional[SceneWorkspaceEntry]) -> None:
    alias = candidate
    alias.dirty = False
""",
        }

        for path, source in probes.items():
            with self.subTest(path=path):
                violations = _workspace_entry_writer_violations(path, ast.parse(source))
                self.assertEqual(len(violations), 1)

    def test_workspace_entry_writer_helper_allows_authority_and_ignores_untyped_state(self) -> None:
        authority_source = """
def mutate(entry: SceneWorkspaceEntry) -> None:
    entry.dirty = True
    entry.scene = replacement
"""
        unrelated_source = """
class _MutationState:
    def __init__(self, scene, dirty):
        self.scene = scene
        self.dirty = dirty

class ThemeEditor:
    def mutate(self):
        self._state.dirty = True
"""

        self.assertEqual(
            _workspace_entry_writer_violations(
                SCENES_ROOT / "workspace_lifecycle.py",
                ast.parse(authority_source),
            ),
            [],
        )
        self.assertEqual(
            _workspace_entry_writer_violations(
                ENGINE_ROOT / "editor" / "theme" / "theme_editor.py",
                ast.parse(unrelated_source),
            ),
            [],
        )

    def test_workspace_entry_writer_helper_maps_enumerated_values_entry(self) -> None:
        enumerate_source = """
def mutate(workspace) -> None:
    for index, entry in enumerate(workspace.entries.values()):
        index.dirty = True
        entry.dirty = True
"""

        self.assertEqual(
            len(
                _workspace_entry_writer_violations(
                    ENGINE_ROOT / "api" / "enumerate_probe.py",
                    ast.parse(enumerate_source),
                )
            ),
            1,
        )

    def test_workspace_entry_writer_helper_propagates_annotated_instance_entry(self) -> None:
        cross_method_source = """
class Owner:
    def __init__(self, entry: SceneWorkspaceEntry) -> None:
        self.entry: SceneWorkspaceEntry = entry

    def mutate(self) -> None:
        self.entry.scene = replacement
"""

        self.assertEqual(
            len(
                _workspace_entry_writer_violations(
                    ENGINE_ROOT / "features" / "cross_method_probe.py",
                    ast.parse(cross_method_source),
                )
            ),
            1,
        )

    def test_workspace_entry_writer_helper_ignores_untyped_resolve_entry_receiver(self) -> None:
        unrelated_config_source = """
def mutate(config) -> None:
    result = config.resolve_entry("key")
    result.dirty = True
"""

        self.assertEqual(
            _workspace_entry_writer_violations(
                ENGINE_ROOT / "config" / "unrelated_probe.py",
                ast.parse(unrelated_config_source),
            ),
            [],
        )

    def test_workspace_entry_writer_helper_handles_items_subscript_port_and_private_wrapper(self) -> None:
        probes = {
            ENGINE_ROOT / "api" / "items_probe.py": """
def mutate(workspace) -> None:
    for key, entry in workspace.entries.items():
        key.dirty = True
        entry.runtime_world = replacement
""",
            ENGINE_ROOT / "api" / "subscript_probe.py": """
def mutate(workspace) -> None:
    entry = workspace.entries["scene"]
    entry.edit_world = replacement
""",
            ENGINE_ROOT / "api" / "typed_port_probe.py": """
def mutate(port: SceneWorkspacePort) -> None:
    entry = port.ensure_scene_open("scene")
    entry.dirty = True
""",
            ENGINE_ROOT / "features" / "private_wrapper_probe.py": """
class ManagerFacade:
    def _resolve_entry(self) -> SceneWorkspaceEntry:
        raise NotImplementedError

    def mutate(self) -> None:
        entry = self._resolve_entry()
        entry.scene = replacement
""",
        }

        for path, source in probes.items():
            with self.subTest(path=path):
                self.assertEqual(
                    len(_workspace_entry_writer_violations(path, ast.parse(source))),
                    1,
                )

    def test_rebuild_entity_index_is_private_to_scene(self) -> None:
        violations: list[str] = []
        for path in sorted(ENGINE_ROOT.rglob("*.py")):
            if path == SCENES_ROOT / "scene.py":
                continue
            for node in ast.walk(_parse(path)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_rebuild_entity_index"
                ):
                    violations.append(f"{path.relative_to(REPOSITORY_ROOT)}:{node.lineno}")

        self.assertEqual(violations, [])

    def test_authoring_owners_are_wired_once_and_share_narrow_owners(self) -> None:
        production_trees = {
            path.relative_to(SCENES_ROOT).as_posix(): _parse(path)
            for path in sorted(SCENES_ROOT.rglob("*.py"))
        }
        expected_singletons = {
            "SceneIncrementalAuthoring": "scene_manager.py",
            "SceneSerializableAuthoring": "scene_manager.py",
            "SceneStructuralAuthoring": "scene_manager.py",
            "PrefabOverrideService": "scene_manager.py",
            "SceneSerializableAuthoringPipeline": "serializable_authoring.py",
            "SceneEntityAuthoring": "serializable_authoring.py",
            "SceneComponentAuthoring": "serializable_authoring.py",
            "ScenePrefabAuthoring": "structural_authoring.py",
            "SceneHierarchyAuthoring": "structural_authoring.py",
        }
        for constructor, expected_path in expected_singletons.items():
            locations = _constructor_locations(production_trees, constructor)
            self.assertEqual(locations, [expected_path], constructor)

        manager = _class(production_trees["scene_manager.py"], "SceneManager")
        manager_init = _method(manager, "__init__")
        structural_call = _constructor_calls(manager_init, "SceneStructuralAuthoring")
        self.assertEqual(len(structural_call), 1)
        self.assertEqual(
            [ast.unparse(argument) for argument in structural_call[0].args],
            [
                "self._workspace",
                "self._serializable_authoring.transaction_pipeline",
                "self._serializable_authoring.entity_authoring",
                "self._prefab_overrides",
            ],
        )

    def test_constructor_location_helper_preserves_nested_relative_paths(self) -> None:
        trees = {
            "scene_manager.py": ast.parse("SceneStructuralAuthoring()"),
            "nested/duplicate.py": ast.parse("SceneStructuralAuthoring()"),
        }

        self.assertEqual(
            _constructor_locations(trees, "SceneStructuralAuthoring"),
            ["scene_manager.py", "nested/duplicate.py"],
        )


class SceneManagerFacadeArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = _parse(SCENES_ROOT / "scene_manager.py")
        self.manager = _class(self.tree, "SceneManager")

    def test_removed_private_aliases_are_absent(self) -> None:
        methods = {
            node.name
            for node in self.manager.body
            if isinstance(node, ast.FunctionDef)
        }

        self.assertTrue({"_entries", "_active_scene_key", "_entry_path_or_key"}.isdisjoint(methods))
        self.assertFalse(
            any(
                _attribute_chain(target) == ("self", "_workspace", "active_scene_key")
                for target in _assigned_attributes(self.manager)
            )
        )

    def test_retained_entry_wrappers_are_one_return_delegations_with_consumers(self) -> None:
        expected = {
            "_get_active_entry": "get_active_entry",
            "_resolve_entry": "resolve_entry",
        }
        for wrapper_name, workspace_method in expected.items():
            wrapper = _method(self.manager, wrapper_name)
            self.assertEqual(len(wrapper.body), 1)
            self.assertIsInstance(wrapper.body[0], ast.Return)
            statement = wrapper.body[0]
            assert isinstance(statement, ast.Return)
            returned = statement.value
            self.assertIsInstance(returned, ast.Call)
            assert isinstance(returned, ast.Call)
            self.assertEqual(
                _attribute_chain(returned.func),
                ("self", "_workspace", workspace_method),
            )
            consumers = [
                node
                for method in self.manager.body
                if isinstance(method, ast.FunctionDef) and method.name != wrapper_name
                for node in ast.walk(method)
                if isinstance(node, ast.Call)
                and _attribute_chain(node.func) == ("self", wrapper_name)
            ]
            self.assertGreater(len(consumers), 0, wrapper_name)

    def test_manager_keeps_coordination_without_extracted_algorithms(self) -> None:
        imports = _runtime_imports(SCENES_ROOT / "scene_manager.py")
        self.assertFalse(
            any(module == "engine.serialization.schema" or module.startswith("engine.serialization.schema.") for module in imports)
        )
        imported_names = {
            alias.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"Transform", "RectTransform", "SceneHierarchyAuthoring", "ScenePrefabAuthoring"}.isdisjoint(imported_names))

        forbidden_assignments = {
            "dirty",
            "pending_edit_world_sync_reason",
            "dirty_before_pending_edit_world_sync",
            "scene",
            "edit_world",
            "runtime_world",
            "data",
            "entities_data",
        }
        self.assertFalse(
            any(target.attr in forbidden_assignments for target in _assigned_attributes(self.manager))
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_rebuild_entity_index"
                for node in ast.walk(self.manager)
            )
        )

        scene_mutators = {
            "add_entity",
            "add_entity_from_data",
            "remove_entity",
            "remove_entity_subtree",
            "update_entity_property",
            "update_component_property",
            "replace_component_data",
            "remove_component",
        }
        direct_scene_mutations = [
            node
            for node in ast.walk(self.manager)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in scene_mutators
            and _attribute_chain(node.func.value)[-1:] == ("scene",)
        ]
        self.assertEqual(direct_scene_mutations, [])

        methods = {
            node.name
            for node in self.manager.body
            if isinstance(node, ast.FunctionDef)
        }
        self.assertTrue(
            {
                "_mtime_key",
                "_fire_on_scene_saved",
                "_compile_runtime_signals_for_entry",
                "refresh_active_scene_if_stale",
                "apply_change",
                "begin_transaction",
                "commit_transaction",
                "rollback_transaction",
            }.issubset(methods)
        )


if __name__ == "__main__":
    unittest.main()
