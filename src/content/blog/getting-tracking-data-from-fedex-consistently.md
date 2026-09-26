---
title: 'Getting tracking data from FedEx consistently, but the hard way'
description: 'We wanted tracking numbers to just work from our agents, and they do now. Getting there meant learning why FedEx sits behind Akamai, why its cookie stops working the moment the network exit changes, and why copying the browser was never enough.'
pubDate: 'Sep 25 2026'
---

Where is this package, has it moved, is it sitting somewhere. I wanted our agents to be able to answer those from FedEx without a human opening a browser tab. The data is public, and FedEx's tracking page gets it by calling one JSON endpoint with the package number in it. One request, clean response. Reach that endpoint and the rest of the work is parsing.

Everything hard about this was the door in front of the endpoint.

The first version that worked drove a real browser: send it through a residential network, wait for the page to render, read the status out of the DOM, close it. It worked, and it was still the wrong shape. A human watching a browser do this would call it fine. An agent asking where a package is should be able to ask as often as it likes, without every question dragging a browser along with it.

So the goal was never a faster scraper. It was the direct call, with no browser in the request path at all.

Getting there took five wrong turns, and every one of them got closed by a measurement instead of an opinion. Here is the whole story: the sensor payloads that did nothing, the cookie marker I read backwards, and the session model that finally held.

## Mistake one: treating a successful sensor post as a solved challenge

The FedEx tracking page is a JavaScript app. When it loads, the page and its scripts collect browser information and hand it to Akamai, the anti-bot vendor FedEx sits behind. Akamai decides how much it trusts the session and writes its verdict into an `_abck` cookie. The app then calls FedEx's JSON endpoint with that cookie attached.

My first plan was simple: capture the browser's sensor payload, replay it from a lightweight HTTP client, and skip the browser. The sensor endpoint returned `201` with a success body. That looked like a solved challenge.

It was not.

How we got there: I treated an HTTP success as a statement about the session. It was only a statement that the endpoint received the request. The endpoint returned the same `201` for an empty body, a garbage body, and a request that was not valid JSON at all. Replaying the browser's real payload changed nothing about the cookie the API trusted either. The cookie grew once from 511 to 527 characters, stopped there, and the API kept answering `403`. We had been reading an acknowledgement as a decision.

The genuinely useful lesson: a challenge endpoint acknowledging your request is not the same as the server trusting the client. A successful response can mean the packet arrived, the parser was happy, or the request was stored. None of those prove the identity behind it was accepted. Read what the server changed, not what it replied.

## Mistake two: trusting the marker inside the cookie

The Akamai cookie has a marker in the middle that looked like it told us whether the session had passed. I read `~-1~` as untrusted and `~0~` as accepted, then built decisions on top of that assumption.

The working browser cookie used the same marker I had been calling untrusted. Every conclusion I had drawn from it was backwards.

How we got there: I picked the easiest visible value in the cookie and treated it as the answer. I had not compared the full shape of a cookie that worked with one that failed. Once I did, the difference was obvious. The working cookie had four segments, including a roughly 900-character server-written session record and a separate 127-character tail. The lightweight client's cookie stayed a two-part stub, even when replaying sensor traffic pushed it past a thousand characters.

We also ran the sensor under Node with a DOM shim. It produced a valid signed payload, which proved we could reproduce the output. The cookie still did not become the shape the API trusted. Sensor generation was not the missing piece.

Length was not the gate either. A long cookie can still be the wrong shape. The useful comparison was structural: count the segments, inspect the long record, and compare a known-good cookie with the one the request actually produced.

Lesson: when a system gives you a convenient status-looking value, verify it against a known-good example before you build your entire theory on it. Shape often tells you more than a marker or a length threshold.

## Mistake three: thinking a Chrome TLS fingerprint was a Chrome engine

The lightweight client could impersonate Chrome's TLS handshake. That seemed like the missing piece. If the request looked like Chrome at the network layer, the rest of the browser should be unnecessary.

It was not enough.

How we got there: I kept treating TLS fingerprinting as if it reproduced the browser. It reproduces the handshake. It does not run the page's JavaScript, lay out the DOM, query canvas or WebGL, or produce the timing patterns those scripts inspect. A ClientHello can look exactly right and still be attached to a client that never executes a real browser engine.

We tried Chrome impersonation profiles in `curl_cffi`, another TLS library with its own Chrome profiles, and a small Go program using `utls` to reproduce a recent Chrome ClientHello directly. All three produced the same 507-character stub. The real browser over the same network exit produced a 1,105-character cookie that the API accepted. The handshake profiles changed, the egress stayed the same, and the stub stayed the same. The missing signal was not another header or another cipher order.

This is the part I would keep: fingerprinting one layer does not impersonate the system above it. Before you conclude that a browser is required, list what the browser actually does that your client does not. In this case, the answer was the JavaScript runtime and everything the page's sensor could observe through it.

## Mistake four: treating cookies like portable credentials

By this point we had a working combination: a real browser on a residential exit, followed by a direct API request replaying that browser's cookies through the same exit. The obvious next move was to send those cookies anywhere and expect them to work.

It worked sometimes. That was worse.

How we got there: I thought of the cookie as a ticket. Once we had it, I assumed the important part was possession. The actual rule was coherence. A complete browser-generated cookie set replayed from the same network exit returned the tracking data. The same cookie sent on a different exit started returning `403`. The important cookie sent by itself produced `200`, `200`, `403`, `403` as the residential exit rotated underneath us.

The other error code taught us something too. A `400` response from the endpoint meant the anti-bot layer had passed the request, but the application layer rejected it because the authorization header was missing. The failures were not one wall measured in degrees. A `403` meant the session or its network context was wrong. A `400` meant we had reached the application and skipped part of its request contract.

The fix was to keep the browser warm-up and the API call bound to the same exit. Fresh cookies from one path, followed by a request from another, were never a coherent client. They were two different clients wearing pieces of the same session.

Lesson: a cookie from a protected site is usually part of a session, not a standalone credential. Preserve the context that earned it: the same client identity, the same supporting cookies, and the same network exit.

## Mistake five: paying for the warm-up on every request

The direct request worked, but only by first starting a browser to earn a session the API would accept. Every lookup paid for that startup: a stock browser, a residential exit, the page settling, cookies harvested, the API call, the browser closed. The API call itself was quick. The setup around it was the whole cost.

That was acceptable for one command and terrible inside a larger application. A page that checked twenty shipments would spend most of its time starting browsers.

How we got there: I had optimized the API call while treating the browser warm-up as setup that naturally belonged to every request. The warm-up was not part of each shipment lookup. It was the thing that made the session trustworthy, and that result could be reused until the session aged out.

The first fix was straightforward. The tracker warmed once, then held on to that cookie set along with the exact network exit it had been created on, and reused both across many lookups. A `403` cleared the cached session, warmed a new one, and retried once. After the first request, each additional shipment took a few seconds instead of around forty.

The next fix moved the warm-up out of the request path. We built a small local pool of persistent browser sessions. Each session had a fixed network exit, kept its own cookie jar warm, and refreshed that jar shortly before the four-minute session window closed. A tracking request borrowed a ready session, used the matching exit, and returned the result. If the pool was unavailable, the tracker could still warm its own browser as a fallback.

That made the browser reusable instead of per-request. The normal lookup dropped to under three seconds, but the number is the side effect. The real change is that an agent can now ask about a package as a matter of course, and the machinery for it runs whether or not anyone is asking.

The lesson is not just to cache more. It is to identify which part of your request is state preparation and which part is the actual work. If preparation is expensive, stateful, and valid for more than one operation, give it a lifecycle of its own.

## Where it ended up

The command now returns structured tracking data through a direct API call without launching a browser for the normal case. The browser pool prepares and refreshes sessions in advance. Each request borrows one of those sessions and must replay it through the same network exit that created it. If a session is rejected, the tracker warms a fresh one and retries once before giving up.

The direct client mirrors the public client credential and application headers that the tracking page sends from its own frontend. The important part was making the request match the application contract, not inventing a private API around it.

Most importantly, the tool now fails in ways we can act on. A rejected session means the cookies are stale or the exit changed. A missing authorization header means the request reached the application but not the endpoint correctly. A browser that never produced the cookie means the warm-up failed. We stopped seeing one generic failure and started seeing which layer rejected us.

None of this came from one clever request. It came from testing one variable at a time, keeping the bad results, and letting each closed path narrow the next experiment. The direct request path is what works now, which is the thing I wanted to be able to do at all. A fully browser-free path is still open. We proved the direct call can work, but we have not earned the right to remove the browser yet.

## Closing

Look back at the five mistakes and notice that each one came from treating part of the browser session as if it worked alone. A sensor acknowledgement was not a trust decision. A marker was not the cookie's structure. A TLS fingerprint was not a browser engine. A cookie was not portable outside its network exit. A reusable warm-up was being paid for again on every request.

The common thread was session coherence. FedEx did not care that we had copied one interesting piece from the browser. It cared that the browser-generated session, the client making the request, the supporting cookies, the application headers, and the network exit all agreed that they belonged to the same visit.

That changed how I approached the problem. Instead of asking how to make one request look legitimate, I started asking which relationships had to remain intact for the server to see one continuous client. Once those relationships were explicit, the way in became understandable, the parts worth keeping became safe to reuse, and the failures became specific enough to debug.
