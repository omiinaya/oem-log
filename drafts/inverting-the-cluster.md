---
title: 'Inverting the cluster: one agent, many thin clients'
description: 'We traded a cluster of full agents for one agent driving a fleet of thin clients, so a change to the fleet stopped being a change to every machine. Making that topology trustworthy took six days with the whole fleet dark, a client that reported itself healthy while nothing owned it, and a version number that was not the running version.'
pubDate: 'Sep 26 2026'
---

Most agent fleets are built as a cluster. Every node is a full agent with its own config, its own copy of the runtime, and its own moment of updating. That shape is easy to reason about and expensive to keep. A change to any node is a change to every node, and nothing in the system can tell you which ones actually took it.

We ran that shape and got tired of it. Not because it kept breaking, but because every change was N changes, and we had no honest answer to the question we cared most about: which machines are running the code we just shipped.

So we inverted it. One agent, a set of thin clients, and a control plane in the middle. The agent dials out to a hub, the hub exposes each client, and the clients do the work. Configuration lives in one place. The runtime is one binary, signed once, published once, and the clients pull it when they are ready.

That is what we run today. Getting to a point where we trusted it took real work, and almost none of it was the networking. Here is the five mistakes version.

## Mistake one: letting a client say who it is

The hub needs to know which machine is talking to it. The obvious way to answer that is to let the client name itself, so we gave every client an environment variable carrying its node id and the hub believed it.

Then a security-minded pass on the transport gave every node its own client certificate, signed by a fleet certificate authority, and the hub verified it during the handshake. We had identity from two sources at once, and we kept trusting the weaker one. A client could present a valid certificate and then claim to be a different machine.

How we got there: we added authentication and never went back to look at what the authentication was actually replacing. The certificate proved something now, and the variable was just left in place doing the same job.

The fix was to delete the trust, not merge it. The hub reads the node's identity from the certificate's common name and refuses a connection where the name the client claims does not match the name on its certificate. The environment variable stayed in the code, but as a label for logging only. Nothing that matters reads it.

The genuinely useful lesson: when you add a real proof to a system, check whether you also left a claim behind doing the same job. Two answers to one question means one of them is optional, and the one you are still reading is probably the one you introduced first.

## Mistake two: believing a node that only knew it had connected

The hub keeps a registry of the clients that are currently connected. The node list in our tooling reads from that registry, and for a long time we treated a node appearing there as proof that the node was working.

One client was in that list, healthy, answering health checks, and nothing was keeping it alive. The agent process was running. The thing that was supposed to restart it on a crash or a reboot was stopped, and had been for a while. The agent was an orphan: alive, reachable, and one power cycle away from gone.

How we got there: we built a liveness signal out of a connection, and a connection is a weaker thing than a running process. It says the client is present right now. It says nothing about whether anything will bring it back after it stops.

The fix was to stop asking the registry and start asking who owns the process. Our control tool grew a command that reports the supervising mechanism for each node: the service manager on one platform, the user service manager on Linux, the launch daemon on macOS. It answers a different question than the node list does, and when the two disagree, that disagreement is the finding. A node can be connected and unowned, and the connected part will hide the unowned part for as long as nobody restarts it.

We also made the supervisor itself fail loudly. On Windows the service shim now counts consecutive crashes and, past a threshold, gives up and stops cleanly instead of relaunching forever. A node that has given up shows up as a stopped service, which is a state our monitoring can see and tell a human about. A node crash-looping in the background is a state that looks like activity.

The genuinely useful lesson: a fleet needs two questions answered separately. Is it talking to me right now, and will something bring it back when it stops. One signal cannot answer both, and using the one you have for both is how a dead thing stays on a dashboard.

## Mistake three: a version number that was not the version

We publish signed releases, and each client checks whether it is current and pulls if it is not. The reporting side had a bug. The version a client reported came from an environment variable set by whatever launched it, not from the binary itself. We had installed a fixed value into a launch script once, and every client installed from that script reported a version that was correct on the day we wrote the script and wrong forever after.

A client on a new binary would report an old version. A client on an old binary would report the right one, if the right one happened to be what its launcher claimed. The number and the thing it described had come apart, and we were reading the number.

How we got there: the version was stamped at packaging time into a script, and the agent trusted its environment. Nothing in the system compared the two.

The fix was to stop the script claiming a version and start the packer stamping the real one. The version is read out of the published artifact and written into the installer at build time, so the number comes from the thing being installed instead of from a constant someone has to remember to update. The control tool reports the version each client claims, so a node that is behind is visible without running anything on it.

There was a second failure hiding in the same area. An update that downloads a new binary and stages it, then exits so something restarts it, does nothing at all if the thing that restarts it never moves the staged file into place. The client exits cleanly, the launcher starts the old binary, and the next check finds it is still out of date. The system looks like it is updating, because it is downloading, verifying, and staging. It is only the last step that is missing. We had a client sit on an old version for a long stretch for exactly this reason.

The genuinely useful lesson: a self-reported value is a claim. When a number stands for a thing on disk, compare the number to the thing. And when an update pipeline is a chain of steps, the last step is the one that decides whether the chain did anything, so verify the end of it rather than the busy middle.

## Mistake four: three fixes in a row, and a test that only worked in one direction

This one took the whole fleet offline for six days, and the reason it lasted six days is the most useful thing here.

We had a hub that was leaking threads. A client that disconnected left a handler thread spinning at full CPU, roughly fourteen thousand reads a second on a socket that was already closed. A single one of those is a wasted core. We had about a hundred and ninety of them, and the host's load average was around a hundred and eighty on a machine with sixty-four cores.

The cause was in how we read from the TLS connection. The library's convenient read path returns a clean close as zero bytes, and the loop we had written kept asking, because zero bytes at the socket layer did not reliably surface as end of stream to the caller. So on the fifteenth we wrote a proper reader that detects the closed socket and returns end of stream explicitly, and wired it in, and the build was green.

It was still spinning. The reader was correct, and the agent path was still reading the old way, byte at a time. We had added the fix without replacing the code that was broken. A regression test we added at the same time caught it, which is the only reason this stayed a short bug instead of a long one. But catching it took a second pass, and the first pass was a green build on a broken hub.

Then the same reader took the fleet offline. It drove the read side of the connection manually, and it never flushed the write side. The hub was not sending its half of the TLS handshake, so every client connected, waited forever for a server hello, and died. Zero nodes registered. The hub filled its log with hundreds of thousands of session errors while looking healthy on every metric we had. That was the real outage, and it lasted six days.

The reason it lasted six days is worth being precise about. The regression test that caught the first bug sent a bare socket close. It never performed a handshake. So it proved the read side of our reader was correct, and it passed happily while the write side was never called in the live path. The test was green for six days on a hub that could not complete a single handshake. When we finally wrote a test that performed an actual handshake, it failed immediately.

There was one more layer after that. With the handshake fixed, nodes could register, and then every routed request still timed out, because the read parked indefinitely and the loop only drained its outbound queue when a line came in. A queued request sat there until it timed out. The fix was a read timeout on the socket, and it was chosen deliberately as a real timeout rather than a non-blocking socket, because a non-blocking read returns immediately and spins the loop at full CPU, which is the exact failure we started with.

The genuinely useful lesson: a regression test that skips the step you are actually failing at will pass on a system that is completely broken. Ours never did a handshake, so it could not see a broken handshake. When you write a test to prove a fix, make it perform the whole operation end to end, and treat a test that passes on the first run with suspicion.

## Mistake five: one timeout for every kind of work

The hub waited a fixed amount of time for a client to answer, and applied it to everything. Command execution, file reads, file writes, updates, and quick status checks all shared one deadline.

The clients were fine. The deadline was not. Some of the work we ask a client to do takes longer than the deadline by a wide margin, because it is a real query against a real machine with real hardware enumeration. When one of those overran, the hub gave up while the client was still working, and reported a timeout for an answer that arrived minutes later, correct, to nobody.

How we got there: a timeout is a claim about how long something takes, and we made the claim once, at the beginning, for a workload that did not exist yet. Then we grew the workload and never revisited the claim. The constant was comfortable, and a comfortable constant is the hardest kind of wrong to notice.

The fix was to give each kind of operation its own deadline, set from what that operation actually does. Long commands get room for long work. File transfers get room for large files. Updates get room for a download, a verification, and a swap. Quick status checks keep a short one. And when a wait does expire, the error names the deadline it hit, so the next person looking at it can tell the difference between a client that is broken and a client that is slow.

The genuinely useful lesson: a single timeout applied to a growing set of work quietly converts real results into false failures. The failures look like flakiness in the thing being measured, so you go debug the client. Size each deadline to the operation, and make the timeout say which operation it was.

## Where it ended up

One agent driving a fleet of thin clients. The clients are thin in a literal sense, a few megabytes each, doing real work over a connection they dial out, so nothing needs an inbound port opened anywhere.

Every platform now has one durable mechanism, and every machine on a platform uses the same one: a service on Windows, a user service on Linux, a launch daemon on macOS. When a machine joins, one installer takes it from a raw box to registered with that mechanism in place, and every later update is a signed release the client pulls for itself. The uniformity was not a style preference. Two machines with different persistence mechanisms means every future problem is two problems, and we had that for long enough to know it.

Failures are legible now. A client that dies gets restarted and the reason shows up. A client that gives up stays stopped and says so. A version that is not the one that shipped is visible from the hub without touching the node. A slow command gets a deadline sized for slow commands.

The fleet is small. Four machines across three operating systems, and it is the rare week that one of them needs us at all.

## Closing

Every one of these was the same mistake in a different place. We had a report and we believed it instead of the thing the report was about. A client said its name and we took the name. A registry said a node was connected and we called that health. A number said which version was running and it came from a launch script instead of the binary. A test said the fix was correct and we never checked that the fix was in the path. A constant said how long to wait and we never measured.

Centralising the fleet gave us one config surface, one binary, and one place to be right. It also handed us one place to be wrong, and being wrong in one place is cheaper to find and more expensive to miss than being wrong in five. The hub is the only thing that knows the truth about every machine now, which means the whole system is only as honest as the questions that hub asks and the checks it actually performs. When every answer flows through one component, the work is making sure each answer is a measurement rather than a report.
