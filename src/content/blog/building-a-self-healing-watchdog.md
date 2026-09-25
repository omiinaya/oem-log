---
title: 'Building a watchdog that finally stopped lying to us'
description: 'The real story of our self-healing watchdog: what we wired wrong, the incidents that exposed it, and how a long run of fixes took it from chaos to quietly stable.'
pubDate: 'Sep 24 2026'
---

We run several services we don't want to babysit, so I built a watchdog on top of them. It probes each service, notices when one is sick, auto-fixes the safe problems, and pages me for the rest. That is the pitch. The reality is it took a long time and a pile of real incidents to get there, and most of what made it good was recovering from the ways I made it bad first.

Here is the whole story. The wiring mistakes, the incidents that surfaced them, and the fixes that eventually stuck.

## Mistake one: a check that fired during warmup and restarted in a loop

One of the services it watches is a small proxy relay: a process that holds an outgoing connection pool and forwards traffic through it. Our first check against that relay was blunt. If the pool looked degraded, restart the relay. Straightforward, and wrong.

The relay needs a few minutes to warm up and build its pool after any start. The check ran on a two minute cadence. The sequence was: pool looks thin during warmup, the check flags it, we restart the relay, the restart resets warmup, two minutes later the same thin pool appears, restart again. One routine deploy became two and a half hours and dozens of restarts, all with the pool at zero the whole time. Nothing was ever actually broken. The check's response to a normal startup state was the defect.

How we got there: I wrote the check against "pool is below minimum" as a pure threshold, and I had never measured how long a healthy start took. The check had no idea a warmup window existed, so it couldn't tell a starting service from a dying one.

The fix had two parts. The check now reads the service's uptime from its own health endpoint and refuses to treat a below-minimum pool as a failure while the process is still inside its warmup window (a few minutes). And every restart-type action got a cooldown that survives daemon restarts, so even a genuinely repeated failure can't hammer the service on every check cycle.

The genuinely useful lesson: if a condition is the normal transient of a fresh start, restarting in response to it just keeps resetting the clock. Measure startup time before you write a single check against a running service.

## Mistake two: alerts that were louder than the incident

When things looked broken, the watchdog would flood us. One real incident produced a burst of messages in a few seconds plus a pile of parallel restart attempts, and the service manager, rate limited, rejected all of them. Our note from that day is still accurate: the alerting was worse than the issue it was spamming about.

How we got there: our registration logic could run several times over a short window, and each registration spun up its own watcher and its own alert loop. Nothing serialized them. Every watcher saw the same condition, and every watcher independently decided it should send and act.

The fix was a concurrency lock around the whole read-decide-send window, shared across every watcher, so no matter how many of them notice the same thing in the same instant, exactly one alert goes out and the losers block and stay quiet. Fixes got the same treatment: a cooldown lock per action so a hundred watchers cannot fire a hundred parallel restarts. That was the single biggest quality jump. The watchdog stopped being a noise source and became something we could actually rely on.

The reusable lesson: with multiple watchers, the danger is not missing a condition, it is everyone reacting to it at once. Serialize the send and the act, and count on one actor even when many detect.

## Mistake three: the watcher that watched itself

Detection reads service logs looking for failure signatures. Early on the pattern was far too loose; it matched words like "restart" and "crash". Those words appear in totally routine log lines. Including the lines the watchdog's own alerts produce. So the watchdog alerted, the send logged a line, the line matched the pattern again, and it alerted on itself. An infinite mirror, on a loop.

How we got there: I wrote the match against generic keywords instead of the real death signatures, and I never checked whether the pattern might also match text our own system produces.

Two fixes, both worth stealing. Match precise death signatures only, the specific lines that actually mean a service died, never generic words that show up in routine output. And as defense in depth, have every watcher explicitly skip any line containing our own alert marker, so even a signature that slips the regex can never trigger on itself. We also stopped turning every unique log line into its own incident; a burst became one incident with a counter for how many times it came back, instead of a pile of near-identical rows.

Lesson: if your detector reads logs, sample what a real run of your own system writes, including the detector's own output, before you trust the match. Generic patterns are how watchers eat themselves.

## Mistake four: the watchdog that looked healthy but saw nothing

This was the worst kind. For a stretch the watchdog reported everything green, nothing firing, all calm. It turned out the log watchers were reading from the wrong place entirely. Our services run under a user session, but the log collection was reading the system journal, which has none of our service lines. It was seeing zero events and reporting healthy. Blind, and content about it.

How we got there: I assumed journal reads would find user-scoped units, and never verified the collector actually pulled our lines. The checks passed because they were checking nothing.

The fix was to detect the session scope and read the right journal. And the durable change was a rule I now apply everywhere: verify the probe actually reads data, do not trust that a check ran. A check that returns "all good" while reading nothing is a hole, not a win. We made the watchdog confirm it is getting fresh feed lines, not just that the loop is ticking.

Lesson: a silent check is indistinguishable from a healthy one until you prove it saw something. Test the collector against real lines, not just that the collector executed.

## Mistake five: a fix that was correct on disk and did nothing live

I fixed a bug, tested it, and the live system was still wrong. The explanation was the most frustrating one there is: the running process was executing an old copy of the code. The fix was fine in the repo and in the installed copy, but the live process had loaded its modules before the fix and never reloaded. The process was up, so status looked fine. It was running stale logic.

How we got there: I treated "deploy the files" as "make it live." But there are three separate layers: the repo, the installed copy the process imports, and the code already in memory in the running process. Syncing the first two does nothing for the third.

The fix was a reload path that re-imports the modules into the running daemon without a full restart, so a code change can be applied in place. And the rule that got us out of this trap for good: verify behavior, not process state. "Up" is not "running the thing I just fixed." After any change I check for the actual new behavior, never just a heartbeat.

This is the one our team repeats constantly and it has a name now: restarted is not the same as new code. Sync what runs, then prove what runs it.

## Where it ended up

After all the fixes, the thing is genuinely stable, and not by accident.

The set of things it watches is grown by decoration, so adding a watch is adding one function, not rewiring a list. Every auto-heal is proven before it is claimed: the check re-runs after the fix and only reports success if the condition is actually gone, and it re-opens the incident if the condition came back. It has a coverage tab so I can see what is and is not being watched, an incidents ledger that only holds real problems (a recurring root cause shows as one row with a count, not a flood), pending approvals for changes I don't want done automatically, and after-action notes attached to every resolved incident so there is a record of what happened and how it was handled. It sends a digest that ranks the recurring problems, so I fix the roots instead of the symptoms. It even watches itself: a self-check flags if it has gone deaf, so a failed alert shows up instead of hiding.

The test suite grew from a handful to a few hundred tests through all of this, and it now locks these behaviors in so they can't come back. Our own audit's headline number is telling: no open incidents, every check green, and the watch proving delivery of its own alerts so it can't silently lose one.

None of that was one clever idea. It was dozens of boring fixes stacked on top of each other, each one a reaction to a real incident, which is exactly why they held. A watchdog that works is not a feature you build once. It is a thing you keep repairing until it stops lying to you.

## Closing

Look back at the five mistakes and notice what they actually have in common. None of them were about the services the watchdog watches. The relay was fine during the restart storm. Nothing was broken when the alerts flooded. The services were healthy the whole time the watcher saw nothing. The common thread is that the failure was always in the monitor lying about its own health, never in the thing it monitored. That is the part nobody warns you about.

Building a monitor, the real difficulty is that it can be completely wrong about whether it is doing its job, and look entirely normal while doing it. It can be reading nothing, running stale code, reacting to its own output, or hammering a warmup state, and every one of those looks like a healthy, busy watchdog. The bugs that took real time to find were the ones where the monitor reported success about something it never actually did.

So the piece of this I would actually hand anyone starting out is this: treat the monitor's self-doubt as a first-class feature. Before you trust any green state, ask what the monitor did to deserve it. Prove the collector read a real line. Prove the running process is the code you just wrote. Prove a fix actually removed the condition before you celebrate it. All of that is boring, and it is exactly where the value is.