---
title: 'A hundred Tor exits, kept alive and honest'
description: 'We route our agent traffic through a pool of a hundred Tor daemons so requests land on a spread of unique exit IPs. Keeping a hundred of them actually usable was the hard part. Six problems, what caused each one, and what we changed.'
pubDate: 'Sep 26 2026'
---

Every language model call our agents made left from the same IP address. A single address carrying all of our traffic is a pattern, and patterns get blocked, so we put a pool of a hundred Tor daemons behind the relay. Each request picks an exit round robin, which spreads traffic across a hundred unique exit IPs, and an exit that misbehaves gets rotated out.

That part is straightforward. The hard part turned out to be that a pool of a hundred daemons and a pool of a hundred working exits are different things, and the gap between them is where all our incidents lived.

## A hard country gate took the pool to zero

We wanted exit IPs in the United States, so every daemon ran with `--ExitNodes {us} --StrictNodes 1`. The flag tells Tor to build circuits only through that country's relays and to fail rather than use anything else.

On a healthy network this works perfectly and looks completely fine. The day before our incident, 194 of 194 daemons were up.

Then our own egress degraded. That is not something we control and not something we caused, but roughly 0.3% of Tor relay OR ports became reachable from where we were. With `--StrictNodes 1` and no reachable US exit, Tor builds no circuits at all, not slow ones, none, and it does not even complete bootstrap. The pool sat at 0 of 100 and stayed there.

What made this expensive was not the outage. It was that the failure mode was total while the setting looked permanent. We confirmed the cause with an A/B on the live box, same tor version, same egress, same hour, only the flag changed. The strict daemon built zero circuits. A clean tor with no strict gate reached 50% bootstrap and reported that it could build exit and internal paths.

We changed two things. The country is now a preference, with `TOR_EXIT_STRICT=1` available when you genuinely need the guarantee. And the health check stopped treating a daemon that was alive but still bootstrapping as broken, because on a degraded network bootstrap is slow, and our eviction logic was restarting daemons for being slow, which sent them back to the start of bootstrap and kept the pool at zero. That second change is the part worth keeping. A health check that cannot tell slow from dead will prevent recovery, because restarting the slow one is the worst possible response to slowness.

## The relay read its proxy list once and never looked again

A fresh Tor daemon cannot serve a request until it has built its first circuit, which takes 10 to 90 seconds depending on the network. A pool that just launched is 0 usable exits even though the pool size says 100, so any availability figure is wrong for the first minute and a half after every restart.

The worse version of this was in the relay itself. It built its list of usable proxies once at startup and then handed requests from that list. A daemon that finished bootstrapping was never added, because nothing went back and asked for a new list. The daemons were healthy. They had circuits. The relay never found out, so the pool stayed empty indefinitely while a hundred working daemons sat there idle. Rotation and failover were both implemented and correct, and neither could do anything, because the component responsible for handing a daemon a request did not know it existed.

The fix was a refresh loop that re-reads the source of proxies every health interval while a Tor profile is active, folding in anything newly healthy and leaving working entries untouched. It is idempotent, so running it every few seconds costs nothing.

Two related details came out of the same work. Round robin will hand you an exit that is functional and much slower than its neighbour, so we track a rolling average latency per exit and skip anything over 6 seconds when a faster one is free. And SOCKS connections are pooled and kept warm, because a request that opens a fresh connection pays that daemon's first-circuit cost again, which is the same 10 to 90 seconds arriving on every request. After a NEWNYM we also pre-warm deliberately: the rotation opens a throwaway connection to a `.invalid` domain, which makes Tor build the fresh circuit immediately, and the name resolution then fails, so no external traffic leaves the exit. Best effort with a 5 second timeout, never retried, because rotation must never block.

## Our health check was a load source that evicted healthy daemons

The health loop ran a full probe on every daemon every 60 seconds, 32 at a time. A full probe means opening a real SOCKS connection out through the exit to an external address to see where it came out.

That is invisible on a healthy network. On a degraded one, a lot of those probes time out transiently, a timeout counted as a failure, a failure evicted the daemon, and eviction restarted it. We were destroying daemons that were working correctly.

The numbers were not subtle: 139 health failures in 30 minutes, 150 evictions in 80 minutes, daemons pinned at 100% CPU each, and host load spiking to 170 on a 64 core machine. The pool was spending all of its capacity deciding which daemons were broken.

The fix was to split the check in two. Every cycle does a cheap liveness check against the daemon's control port, with no traffic leaving the machine, and only a genuinely unreachable control port counts as dead. The full egress probe still runs, but every fifth cycle, and it is the only thing allowed to mark a live daemon as failing. Failures also have to persist across at least 6 cycles before eviction, because a control connection under load can time out once and be fine on the very next attempt.

A health check that is expensive enough to be a load source will eventually evict healthy instances and log it as a rescue. That generalises well past this pool.

## The rotation feature designed to hide us was the most machine-shaped thing we built

Rotating an exit means getting a new IP. The obvious move is to rotate on a timer, so the pool never sits on one IP long enough to become a recognisable pattern. We had exactly that running on a schedule across every daemon, whether or not anything was wrong.

It made the traffic more obviously automated, not less. Our requests carry a session identity, and that identity is bound to the IP that created it, so a rotation does not only change where a request goes, it changes who the request looks like. Rotating all hundred on a timer produced a hundred brand new identities appearing at the same instant. Nobody resets themselves across a hundred identities simultaneously. That is the tell we were trying to avoid, and we had built it deliberately.

Scheduled rotation is off. Rotation on failure stays, because a misbehaving exit is exactly the case where a fresh identity is free.

If the goal is not to look automated, then coordinated on-timer changes to your own identity are evidence, not maintenance. Consistency reads as more human than variety.

## 9,000 threads from a library that looked reasonable

The relay grew past 9,000 threads and 2,600% CPU and stopped responding. The cause was `stem`, the standard library for talking to a Tor control port. It looks entirely reasonable: a `Controller` object that spawns two daemon threads per connection and gives you methods to call.

The problem is the peer that stops answering. Closing the controller joins a reader thread parked in `recv()` on a socket that never closes, so every rotation against a wedged daemon leaked two threads and blocked the calling thread. With a hundred daemons and a share of them wedged, that produced a process nobody could use.

We replaced it with a threadless control client that speaks the protocol directly over the socket. It is a larger change than it sounds, because the protocol has three reply shapes: a single line, a multi-line 250 block, and a data block terminated by a `.` line that requires `..` unescaping. We verified it byte for byte against a live tor 0.4.9.11 instead of trusting that it looked right. One implementation detail is worth knowing if you do this: to wake a reader parked in `recv()`, connect to that socket from yourself, which unblocks the read. Trying to close the thread out from under it does not work.

## Every daemon was sized like a relay, and there were a hundred of them

The pool worked, and then it ate the host. A hundred daemons, each configured with the defaults intended for a full relay, which is roughly a hundred times more than a client-only SOCKS exit needs.

The most expensive mistake was handing every daemon all 414 of our obfs4 bridge lines. Tor only needs two to four working bridges. Feeding it all 414 made each daemon process thousands of new bridge descriptors and run 65 threads, and on a 50 daemon pool that was about 800% CPU. We now give each daemon a random 24 bridge subset, which preserves coverage across the pool because every daemon draws a different subset.

Tor also sizes its worker pool to host CPU count, so on a 64 core box every daemon started 65 threads regardless of the fact that a client-only exit needs one or two. `NumCPUs 1` takes a daemon from 65 threads and 105MB RSS down to 3 threads and 45MB. We set `--CircuitBuildTimeout 10` and `--LearnCircuitBuildTimeout 0` so a dead relay gives up in 10 seconds instead of 60, roughly 6x less CPU burned per dead relay on a degraded network.

Three more defaults were wrong for this use and none of them ever complained. `MaxMemInQueues` defaults to 8GB per daemon on a large host, which a daemon holding one or two circuits will never approach, so it is capped at 256MB. Tor does not rotate its own log, so ours passed 8MB per daemon and 100 daemons is 800MB, so we truncate at startup. And when we scaled the pool down from 200 to 100, the retired `tor-<index>` data directories stayed on disk forever with their cached microdescriptors, about 55MB each, which is 11GB of nothing for a hundred retired daemons. Startup now sweeps any directory at or above the current count, which is safe because live daemons hold their own directory open.

That whole section is about defaults rather than our own code. A fleet of local daemons is a capacity problem multiplied by a hundred, and the per-daemon defaults are all sized for a single full relay. Nothing errors. Everything just gets quietly more expensive.

## Where it ended up

A hundred Tor daemons, round robin, with anything slow or broken pulled from rotation automatically. Requests land spread across a hundred unique exit IPs, and a request that fails tries another exit, so one bad daemon costs a retry instead of the call.

Most of this work was learning not to trust our own numbers. The pool knows how many daemons it launched. It does not know how many are serving, and those are different questions: is the control port open, is it bootstrapped, is it fast, did the last request through it work. One field called pool size was hiding all four of those, and every incident above was one of the four being wrong while the number stayed at 100.

## Closing

These all came from one assumption, that a thing existing means the thing works. A daemon process running means it can serve traffic. A pool holding a hundred entries means a hundred usable exits. A health check firing on schedule means it is reporting something true. A rotation timer running means the identities it hands out are good ones.

Existing and working were separated by 10 to 90 seconds, or by a single transient timeout, or by a network we do not control, and our code was on the wrong side of that gap every time. Make readiness observable separately from liveness, measure the thing instead of the report about the thing, and distrust any number in your system that cannot disagree with the world.
