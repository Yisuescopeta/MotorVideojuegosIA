---
name: pyside6-threading-processes
description: Use this skill when adding background work, subprocesses, terminal commands, asset scanning, long-running operations, indexing, agent calls, tests, or external commands to the PySide6 editor.
---

# PySide6 threading and process skill

## Mission

Keep the editor responsive while doing real work.

The GUI thread should handle GUI events. It should not scan the world, run
commands, talk to agents, load huge assets, or contemplate mortality.

## GUI thread rule

Only create and mutate widgets on the main GUI thread.

Background workers may emit signals with results. MainWindow/panels receive
those signals and update UI.

## Use QProcess for commands

For external commands, prefer `QProcess`:

- terminal panel commands
- CLI commands
- tests
- tool execution
- scripts with stdout/stderr

Why:

- async output
- stdout/stderr channels
- finished/error signals
- better integration with Qt event loop

Pattern:

```python
process = QProcess(self)
process.setProgram("py")
process.setArguments(["-m", "motor", "doctor", "--project", ".", "--json"])
process.readyReadStandardOutput.connect(self._read_stdout)
process.readyReadStandardError.connect(self._read_stderr)
process.finished.connect(self._on_finished)
process.errorOccurred.connect(self._on_error)
process.start()
```

Avoid blocking `subprocess.run(...)` inside button handlers.

## Use QThread worker objects for blocking Python work

Preferred worker-object pattern:

```python
class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            result = do_expensive_work()
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
```

Then move it to a `QThread`:

```python
thread = QThread(self)
worker = Worker()
worker.moveToThread(thread)

thread.started.connect(worker.run)
worker.finished.connect(self._on_result)
worker.failed.connect(self._on_error)
worker.finished.connect(thread.quit)
worker.failed.connect(thread.quit)
thread.finished.connect(worker.deleteLater)
thread.finished.connect(thread.deleteLater)

thread.start()
```

## Avoid common QThread mistakes

- Do not update widgets from worker thread.
- Do not implement random slots in a `QThread` subclass and expect them to run in the worker thread.
- Keep references to active threads/workers so they are not garbage-collected.
- Provide cancellation where operations can be long.
- Always clean up threads.
- Prefer signals over shared mutable state.

## Cancellation

For cancellable work:

- expose `request_cancel()`
- check cancellation between chunks
- emit `cancelled`
- leave project state unchanged on cancel where possible

## Progress

Workers should emit progress:

```python
progress_changed = Signal(int, str)  # percent, message
```

UI should show:

- progress bar for long tasks
- cancel button if possible
- console log for details
- status bar for short summary

## Asset scanning/indexing

For asset refresh:

- scan in background
- parse metadata off the GUI thread
- build result list
- apply final result on GUI thread
- throttle UI updates for massive lists

## Agent/network calls

For agent calls:

- never block UI
- display pending state
- stream updates via signals if supported
- keep approval UI responsive
- time out or allow cancellation

## Error handling

Background errors should:

- emit structured error
- log technical detail to console
- show dialog only if user action is required
- not crash the event loop
