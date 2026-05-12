---
name: pyside6-model-view-data
description: Use this skill when scaling PySide6 trees, tables, project browsers, hierarchy views, asset lists, filters, sorting, or large editor datasets using Qt model/view architecture.
---

# PySide6 model/view data skill

## Mission

Use Qt's model/view architecture when editor data grows beyond toy size.

`QTreeWidget` and `QTableWidget` are fine for early panels. For larger,
frequently changing or filterable data, use model/view. Yes, it is more ceremony.
So is building a bridge instead of throwing planks over a river.

## When item widgets are acceptable

Use `QTreeWidget` / `QTableWidget` when:

- data is small
- edits are simple
- no heavy filtering/sorting is needed
- the panel is experimental
- speed of implementation matters

## When to move to model/view

Use model/view when:

- hierarchy/project/assets can grow large
- filtering/search is needed
- sorting is needed
- multiple views share the same data
- selection state must survive refreshes
- drag/drop rules are non-trivial
- the UI updates frequently

## Recommended classes

- Flat list: `QAbstractListModel`
- Table: `QAbstractTableModel`
- Tree: `QAbstractItemModel`
- Filtering/sorting: `QSortFilterProxyModel`
- Views:
  - `QListView`
  - `QTableView`
  - `QTreeView`

## Model principles

Models expose data. They do not call engine mutation methods from `data()`.

Required model methods commonly include:

```python
rowCount(...)
columnCount(...)
data(...)
index(...)
parent(...)
flags(...)
```

For flat list/table models, subclass the simpler model types where possible.

## Data update rules

Use model signals properly:

- `beginResetModel()` / `endResetModel()` for full replacement
- `dataChanged.emit(...)` for edited items
- `beginInsertRows()` / `endInsertRows()`
- `beginRemoveRows()` / `endRemoveRows()`
- layout change signals when reordering

Do not mutate the backing list and hope the view guesses. Views are not psychic,
which is rude but understandable.

## Filtering

Use `QSortFilterProxyModel` for search fields.

Pattern:

```python
self.proxy = QSortFilterProxyModel(self)
self.proxy.setSourceModel(self.model)
self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
self.view.setModel(self.proxy)
```

When search changes:

```python
self.proxy.setFilterFixedString(text)
```

## Selection preservation

When refreshing data:

- preserve stable ids or paths
- restore selection by id after reset
- avoid using row number as identity
- use entity name/path/key if stable enough

## Drag/drop

For hierarchy or asset panel drag/drop:

- implement flags intentionally
- provide MIME data with explicit type
- validate drop target
- emit panel signal for requested operation
- let MainWindow/facade execute the mutation

Do not mutate engine data from model `dropMimeData()` unless the architecture
explicitly allows it. In this repo, it does not.

## Delegates

Use delegates for polished rendering/editing:

- thumbnail cards
- colored badges
- component property editors
- progress/status cells

Avoid creating thousands of child widgets in list rows. That is how performance
goes to a farm upstate.

## Testing model/view

Test:

- row/column counts
- display data
- filter behavior
- selection restoration logic
- drag/drop MIME payloads
- emitted signals for user intent
