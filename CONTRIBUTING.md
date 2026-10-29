# Contributing to Caseback

Thanks for helping.

## Licences and sign-off

Contributions are licensed under the licence of the part they touch: hardware, firmware and the app under the
Functional Source License (FSL-1.1-ALv2, which turns into Apache-2.0 two years after each version is published);
the protocol, the algorithms, the tools and the website under Apache-2.0; Markdown documents under CC-BY-SA-4.0. `NOTICE`
lists the folders. You keep the copyright on what you write. Sign every commit with the Developer Certificate of
Origin (`git commit -s`); that is the only agreement required, there is no CLA.

## Checks before opening a pull request

- Protocol: `cd caseback-protocol/python && pip install -e ".[dev]" && pytest`, then `cd apps/ios/CasebackProtocol && swift test`
  and the C host test in `firmware/caseback-fw` (commands in `.github/workflows/ci.yml`). A change to the wire format must
  update the spec, all three implementations and the golden fixtures together.
- Algorithms: `pytest` in `algorithms/ppg` and `algorithms/wellness`.

## Evaluation discipline

Do not tune anything against a TEST split, and do not run a TEST evaluation again once it has been looked at. Report
results only on the datasets used, say when a number comes from training data, and never compare with commercial devices.

## Hardware and firmware

Say in the pull request what you built and on which NCS/Zephyr version. Use non-ferromagnetic parts near the watch movement.

## Coding agents

[AGENTS.md](AGENTS.md) has the rules for agents (Claude Code, Codex, Cursor and others) that work on this repository.

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), not in public issues.
