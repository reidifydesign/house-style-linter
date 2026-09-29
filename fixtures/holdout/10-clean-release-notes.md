# Release notes 0.4

This release adds a `--strict` flag. Warnings now fail the run when it is set.

Run time dropped 35% on large folders (numbers in https://example.com/notes/0.4-timing).

The old `moreover` check is gone. Upgrading may require a config change if you set `disable` by hand.
