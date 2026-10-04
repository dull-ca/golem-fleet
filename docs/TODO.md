# Follow-ups

Candidates for separate PRs. None is in v1, each is small, and each is here
because leaving it out was a judgement call rather than an oversight.

## Worth doing

**`--all` failure detail restates the summary.** A failed machine prints
`dev-01  failed (3)` and then `('dev-01', 3)` beneath it. `strabs.doit`
captures `str(exception)`, not the class, so a bare fault's args are all that
reach the output. For a real operation failure the captured command output is
there and useful; only the synthetic `MachineActionFailed` line is noise.
Either stop raising it (signal failure by exit code alone) or filter a detail
line that only repeats the summary.

**`secrets rotate` and `secrets list`.** dulliac has both
(`cli/secrets.ts`). Nothing in the shape blocks them.

**`registry_auth.transform_for(host)`.** `refresh.MintedSecretTransform` is
`Callable[[object], str]`, and `registry_auth.pull_auth` takes `registry_host`
keyword-only, so every consumer declaring a registry auth entry writes
`functools.partial(registry_auth.pull_auth, registry_host=HOST)`. A
`transform_for(host)` returning the bound transform would remove the
`functools` import from each consumer and keep the keyword at the one call
site that needs it.

**Parallel `golemctl fleet apply`.** `plan`/`apply`/`status` are one
inherit-stdio call that owns the terminal. The `--all` machine operations
already fan out through `strabs.doit`; the golemctl verbs could too, if
golemctl grows a per-host selector.

**`droplet_ipv6` is a separate stack output.** strabs-iac exports
`droplet_ipv4` and `droplet_ipv6` as two maps keyed by machine name. The
permissive reader takes one value per machine, so a machine needing both
families has to come from the nested form or be declared twice — and declaring
it twice now raises `MachineAddressDeclaredTwice`. Not a defect today (that
repo's one droplet has IPv6 disabled), but the first machine with both will hit
it. A source that joins two outputs by key would fix it.

**A redirect hostname published by two machines passes validation.**
`reject_router_name_claimed_twice_on_a_machine` looks within one machine, and
`CanonicalHostnameClaimedTwice` covers canonical names only.
`published_hostnames` then yields both, and a consumer deriving DNS from it
emits two conflicting records. No current fleet does this.

**A declared artifact named `fleet.toml` overwrites the library's.**
`write_all` writes the library's artifacts first and the declared ones after,
to the same directory, without comparing names.

**`Source.resolve` takes no `None` runner.** A consumer rendering with no
provider calls `resolve(runner=None)` on a `source.Declared`, which ignores
the runner, and its `ty` reports it. Widening the Protocol to
`ports.Runner | None` breaks `pulumi_stack.Output`, which needs a runner, so
it needs a new branch and fault there.

## Worth doing if something asks

**`Artifact.render` takes one `ResolvedFleet`.** Both real renderers need only
the `Fleet`, so each consumer writes a one-line adapter. The single bundle was
chosen over a `(fleet, addresses)` pair, so those consumers are not forced to
accept a parameter they do not use.

**dulliac carries two names per component.** Its `Service` has a `name`
(`golem-docs`) and a `scroll` (`GolemDocs`, the Emet constructor), and
`placement/resolve.ts` requires each scroll to start with `[A-Z]` and to be
unique. `components.Component` has one name, which strabs-iac uses as the
constructor and checks against `[A-Z][A-Za-z0-9]*` with `fullmatch`, stricter
than dulliac's in the tail. Porting dulliac needs a second field or a stated
convention.

**Optional `fleet.toml` keys.** golemctl reads `ssh_port`, `ssh_args`,
`token_file` and `remote_port`. Neither source repository writes a key other
than `ssh`. Four lines each when a host needs one.

**A generic command address source.** A `source.Source` running any argv and
reading JSON. Twenty lines, and `pulumi_stack.Output` is the only one either
repository ever needed.

## Naming left as it is

**`keys.ENVIRONMENT_VARIABLE` / `keys.FILE_MODE`** in `secrets/keys.py`.
Two agents flagged that stripping the `FLEET_KEY_` prefix lost information.
Every fix is worse — renaming `FleetKey` breaks the name consumers construct,
and re-prefixing restores the stutter. Revisit if it bites.

**`hostnames.Empty`** is thinner than `EmptyHostname` at the raise site, and
the fault is raised and caught entirely inside the fleet package, so the
qualified form that would restore the meaning never appears.

## Smaller cleanups

**The ssh account is declared twice.** `outputs/inventory.py` has
`SSH_ACCOUNT` and inlines the `root@address` f-string; `operations/ssh.py`
has the same value as `ACCOUNT` and a `destination()` helper. Deduping would
make `outputs` (pure) import from `operations` (I/O), inverting the dependency
the library is organised around. Six lines is a fair price; a shared home that does not
invert it would be better.

**`check_exit_code` and `store_secrets` are presentation** living in
`secrets/`. Moving them to `cli/secrets_commands.py` improves the layering and
changes the total by nothing.

## Known size

`cli/` is 755 lines — a third of the source — and `machine_commands.py` is 317
of that for 15 subcommands behind three dispatch tables. The lever there is
which commands are wanted, not golfing the wiring.
