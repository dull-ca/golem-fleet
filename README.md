# golem-fleet

Declare a fleet of machines and the components placed on them, then render what
`golemctl`, `pulumi` and provisioning consume.

golem-fleet is not an infrastructure-as-code library. It imports neither pulumi
nor any cloud SDK. It models a fleet, validates it, renders output files, and
shells out to the tools that do the provisioning.

```
                    your fleet.py  (typed builders)
                          |
                    +-----v-----+
                    |   Fleet   | -- validation --> named failures
                    +-----+-----+
       +------------------+-------------------------+
       v                  v                         v
  fleet.toml      artifacts you declare        cloud-config
  (golemctl)      (Placement.emet, ...)        (provisioning)
```

## Install

```
uv add golem-fleet
```

## Use

Declare a fleet, then build your own command around it:

```python
from golem_fleet.cli import application
from yourrepo.fleet import PROGRAM

app = application.build(PROGRAM)
```

```
yourcommand fleet plan
yourcommand fleet apply
yourcommand placement
```

Every package `__init__.py` is empty; imports name the defining submodule.

## Develop

```
devenv shell
check
```

`check` runs `ruff format --check`, `ruff check`, `ty check` and `pytest`.

The source tree carries no comments, no docstrings and no explanatory prose
in strings. Faults are bare `Fault` subclasses raised with the offending
values; the class name is the explanation. A test enforces it.

## Design

Start with [docs/REVIEW.md](https://github.com/dull-ca/golem-fleet/blob/main/docs/REVIEW.md), a reading order. Decisions and
their reasons are in [docs/superpowers/specs/2026-09-21-golem-fleet-design.md](https://github.com/dull-ca/golem-fleet/blob/main/docs/superpowers/specs/2026-09-21-golem-fleet-design.md).

## License

AGPL-3.0-only
