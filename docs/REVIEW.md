# Reading golem-fleet

33 source files, 2,154 lines, counting the non-blank lines of every
`golem_fleet/**/*.py` except the `__init__.py` files. A reading order so
reviewing it is not alphabetical.

## The three files that carry the design — 255 lines

Read these and you know the system.

| file | lines | what it decides |
|---|---|---|
| `fleet/components.py` | 55 | what is placed on a machine: kind, name, answering. Nothing about how it runs — the Emet owns that |
| `fleet/placements.py` | 150 | `Placement`, `Fleet`, `Builder`, and the five rules a fleet must satisfy |
| `fleet/machines.py` | 50 | a machine is a name, plus OVH facts if it has any. Nothing else, because this library provisions nothing |

Plus `fault.py` — two lines, and every failure in the library subclasses it.

## Then what it writes — 121 lines

`outputs/` holds the two formats something else dictates and the mechanism
that puts them on disk: `outputs/inventory.py` (`fleet.toml`, one `ssh` key
per host, because golemctl reads it), `outputs/cloud_config.py` (cloud-init
and golemd read it), and `outputs/files.py`.

`outputs/files.py` is orchestration, not templating. An `Artifact` is a
filename and a renderer; a renderer takes one `ResolvedFleet` — the fleet
together with its resolved addresses — and returns text. `write_all` renders
the library's own artifacts first, then the program's declared ones, into the
output directory. `fleet.toml` is the library's, so a program neither declares
it nor can omit it.

## Then the edges

| package | lines | |
|---|---|---|
| `cli/` | 755 | a third of the source and the least interesting. Typer wiring. `machine_commands.py` is 15 subcommands behind three dispatch tables |
| `providers/ovh/` | 328 | ported near-verbatim from dulliac's `cli/ovhApi.ts` and `cli/installStatus.ts`. Read only if OVH is in question |
| `secrets/` | 231 | fleet key, secretspec re-exec, registry auth, refresh |
| `execution/` | 197 | `ports.py` is the `Runner` port, the single seam to a subprocess, which is why no test opens a socket |
| `addresses/` | 105 | where addresses come from, behind one Protocol. A fleet declares a tuple of sources and `resolve_all` merges them, so literal IPs and a pulumi stack output can sit side by side; one permissive reader accepts either exported form, and a machine declared twice is a fault |
| `operations/` | 113 | ssh, agent install, diagnostics, kexec. Four short files |

## No Emet shape of its own, and no primitives for one

`FleetProgram.artifacts` is a tuple of `files.Artifact`, empty by default. A
repository names the file it wants and the function that renders it; the
library writes it at the right moments and knows nothing about the format.
The spec records the earlier versions behind that and why each went.

## What a consuming repository declares

`cli/program.py` holds the single `FleetProgram` a consumer writes. Three of
its fields exist because a real port needed them and nothing else does:

- `entry_module` — the module `secretspec run` re-executes. A program with a
  secrets policy and no entry module raises rather than falling back to a
  guess.
- `help` — the top-level help line. `help_text` derives one from the program
  name when it is absent.
- `secret_entries` — pulumi output name to secretspec entry. An entry is a
  plain name, or a `refresh.TransformedEntry` pairing the name with a
  transform, which is how a stack output holding a whole docker config
  document becomes one registry auth string.

## `main.run` and `main.main`

`main.run(program, app)` settles the secretspec re-exec and then invokes the
app it was handed. `main.main(program, runner=…)` builds an app and hands it
to `run`. A repository adding commands of its own builds, extends, and calls
`run`; one that adds nothing calls `main`. Both invoke with
`prog_name=program.program_name`, because click's fallback reads `sys.argv[0]`
and prints `__main__.py`.

## The tests worth reading

`tests/test_outputs_files.py` drives the mechanism: a declared artifact
reaches disk under the name it was declared with, and `fleet.toml` is written
whether or not a program declares anything. A golden file belongs with
whoever owns the shape, so each consuming repository pins its own
`Placement.emet`.

`tests/test_no_comments.py` parses every file and fails on any comment or
docstring. `tests/fake.py` is the recording `Runner` every other test drives.

## Conventions

- **No English in source.** No comments, no docstrings, no explanatory prose
  in strings. Faults are bare `class X(Fault): pass`, raised with the
  offending values as args; the class name is the explanation.
- **Every package `__init__.py` is empty.** Imports name the module and use
  its members as attributes: `components.Component`, `inventory.render()`.
- **Module names are plural where the singular would collide** with the
  natural variable for that concept. `machines.Machine`, not `machine.Machine`
  shadowed by every `for machine in …`.

Two places keep a direct member import, both deliberate: `Fault`, because
`except Fault as fault` would otherwise rebind the module, and `FleetProgram`,
because `program` is a parameter in seven files. `fleet/components.py` and
`fleet/placements.py` also import sibling types directly — under PEP 649 a
property named `hostnames`, `machines` or `components` shadows the module of
that name for every annotation in its class.

## What is deliberately absent

See the spec's "Deliberately absent" section.
