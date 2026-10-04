# golem-fleet

Declare a fleet of machines and the components placed on them; render what
`golemctl`, `pulumi` and provisioning read.

This document records decisions and their reasons. It does not restate the
API — the code is the API, and describing it twice guarantees one copy is
wrong.

## Purpose

`dulliac` (TypeScript) and `strabs-iac` (Python) each grew a fleet concept:
machines, components placed on them, a generated `fleet.toml`, a generated
`Placement.emet`, and a CLI driving `golemctl fleet`. The two diverged.
golem-fleet is the shared library.

It is **not** an infrastructure-as-code library. It imports no cloud SDK. It
models a fleet, validates it, renders files, and shells out.

## Conflicts between the two repositories, and how each was settled

**The Emet shape is the consuming repository's choice, and no default
ships.** A repository declares the file it wants and the function that
renders it, and the library offers nothing below that. An earlier
version also shipped a default shape, where a component's kind, image, port,
environment and mounts travelled as data. Nothing called it: strabs-iac had
deleted that container model as a lossy copy of what its Emet `Quadlet`
says — a `Mount` here cannot express `Access` or `Relabel` — and passes its
own renderer. With no single right shape, a default is a flagship output
nobody uses, and its byte-for-byte golden file is what let a missing `${`
escape survive the port. Dropping it makes a repository's own renderer the
intended way to use this. The text primitives that survived the first cut
went next, for the reason recorded below.

The version before that provided the substitution through a value AST, a
recursive renderer with indent propagation and a `Projection` Protocol — 493
lines. None of the AST's distinguishing features were used: the
inline-vs-block choice is fixed per field rather than dynamic, and
nested-application parenthesisation was exercised by nothing but its own
test. A function returning a string is the whole requirement.

**A component carries no container payload.** When the default shape went, the
`image`, `port`, `environment` and `mounts` it had rendered stayed on
`Component`, read by nothing — this library had copied them from strabs-iac's
model after strabs-iac deleted it, for the reason above. They say how a
component runs, and that is the Emet's to say. Both consuming repositories
declare a name and the hostnames it answers at, and reach the image and the
port from the Emet module that configures the app. A component is a kind, a
name and an answering.

**A hostname is canonical or it redirects to the canonical one.** dulliac
models redirects; strabs-iac does not. A flat list is the zero-redirect case.

**Ingress is derived, not declared.** The Emet side already infers it from the
presence of a `Service`. dulliac declared it explicitly; that stops.

**A component may be placed on two machines.** dulliac refused this, because
there a service *was* an Emet constructor, so one constructor on two hosts was
genuinely ambiguous. Here nothing in the library maps a component to an Emet
constructor, so two machines each running a `metrics` workload is ordinary.
A renderer needing uniqueness enforces it itself.

**`fleet status` sends no manifest.** golemctl takes none for that verb.
dulliac passes one; that is a latent fault, not a feature.

**The fleet key file is removed on SIGINT and SIGTERM**, not only on return.
strabs-iac's plain context manager leaks the key on Ctrl-C.

## Decisions not visible in the code

**A `Fleet` holds no address source.** Addresses arrive at render time. The
domain stays pure, so a fleet can be declared and validated with no tool
installed and no network.

**The library renders only the formats something else dictates.** Each
consuming repository defines its own Emet, and the shape, the parameters and
the elements differ between them, so a helper for writing one is a helper for
writing somebody else's language. The dividing line is who fixes the format:
golemctl fixes `fleet.toml` and cloud-init and golemd fix the cloud-config, so
this library renders both; a repository fixes its `Placement.emet`, so this
library only writes what the repository renders. `fleet.toml` is the
library's own artifact, so no program declares it and none can omit it. The
Emet text primitives went with the same reasoning: 26 lines of string
joining, including the `${` escape, which strabs-iac had right before this
library did.

**The `Runner` port carries `str | bytes` on stdin.** Sending a compiled
`golemd` to a host is an ordinary operation, and text-only stdin forced a
base64 round trip costing a third of the bytes plus GNU `base64` on every
host.

**Child output is decoded UTF-8 with replacement, on both stdin paths.**
`subprocess` otherwise decodes with the machine's locale and raises, so one
stray byte on a remote tool's stderr would kill the command that ran it.

**One `Fault` base; every fault is a bare two-line subclass** raised with
the offending values as args. An earlier version gave each of 85 faults a
hand-written three-clause sentence — 884 lines, 19% of the source. That is the
precise failure the no-prose rule exists to prevent: English in source burns
context and is rarely right. The class name is the explanation. If a name does
not explain itself, rename it.

**Every package `__init__.py` is empty.** Imports name the defining submodule.
Re-export lists froze internals into the contract and buried the few names
that matter.

**No discovery mechanism.** A consuming repository builds its own app from
its own program. An earlier version read `[tool.golem-fleet]` from
`pyproject.toml` — 146 lines and 7 fault classes to replace what both source
repositories do with a devenv script.

**The entry point runs an app; it does not insist on building one.** An
earlier `main` built the app itself, so the first repository that added
commands of its own after `application.build` could not call it — doing so
would have silently dropped them — and re-implemented the secretspec re-exec
by hand. `main.run` takes the app; `main.main` builds one and hands it over.
Both pass the program's own name to click, because click's fallback reads
`sys.argv[0]` and a module entry point prints `__main__.py`.

**`RecordingRunner` lives in `tests/`, not the library.** A mock framework
shipped inside a published package is not a feature.

## Deliberately absent

Recorded so nobody restores one believing it was an oversight.

- **A container payload on a component** — `ImageReference`, a registry
  helper, `Mount`, environment variables and a port. Unread, and a lossy copy
  of the Emet's `Quadlet`.
- **A DigitalOcean provider and `doctl` wrappers.** Nothing called them. A
  DigitalOcean host arrives as an ordinary machine with an address.
- **`StaticMachine(ipv4)`.** Worse than unused: addresses come from an
  address source, so an address declared on a machine was silently ignored by
  every renderer.
- **`TemplateInstall` and a 14-entry operating-system list**, copied from
  dulliac where they were also unused.
- **A generic command address source.** Invented; neither repository had one.
- **Optional `fleet.toml` keys** (`ssh_port`, `ssh_args`, `token_file`,
  `remote_port`). golemctl reads them, but neither repository writes a key
  other than `ssh`, and no consumer could reach the options that set them.
- **`secrets rotate` and `secrets list`.** dulliac has both; not asked for
  here.
- **`dns.json`.** Nothing read it. strabs-iac derives its records from
  `Fleet.published_hostnames` in process.
- **The exception-reflection catch list.** The CLI built its catch list by
  reflecting over package namespaces. It existed only because there were 85
  fault classes and because each package re-exported them — circular, and the
  reason the re-exports became load-bearing. `except Fault` replaces all
  of it.

## Testing

The `Runner` port is the single seam to a subprocess, and the OVH client has
a `Transport` Protocol, so no test opens a socket or starts a real process
beyond a few deliberate `sys.executable` children.

`fleet.toml` and the cloud-config are each pinned whole, so changing either
renderer by a character has to be meant. No Emet module is pinned here,
because none is rendered here: a stand-in renderer proves a declared artifact
reaches disk, and the golden file lives with the repository that owns the
shape.

## Tooling

Python 3.14 pinned by `devenv.nix`, not inherited. `uv` for dependencies.
`ruff` for formatting and linting. `ty` for types. `pytest`. The flake builds
from `uv.lock` through uv2nix, because one dependency (`strabs-doit`) is not
in nixpkgs.

`ruff` selects every rule and ignores thirteen codes. A local `# noqa` is
never available — it is a comment — so every lint conflict is settled in
configuration or by a rename.
