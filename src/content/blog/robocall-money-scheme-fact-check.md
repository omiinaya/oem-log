---
title: 'We fact-checked a robocall money scheme and it made us build a research pipeline'
description: 'A $47 kit promised $5,750 in ten days. Pulling it apart meant building a research rig that fans out five agents, forces primary sources, and catches its own hallucinations.'
pubDate: 'Sep 29 2026'
---

Someone sent me a video and a link and asked the only question that matters: is this real, and is it legal. The video is a local TV consumer segment. A man named "Doc" Compton is sitting there saying he collected $5,750 in ten days off robocallers, and the product he sells for $47 is called the Turning Robocalls Into Cash kit. The pitch is that the Telephone Consumer Protection Act lets you treat every illegal robocall as a debt someone owes you personally, and that a template demand letter is enough to make them pay it.

I believed the statute part. The TCPA really does carry $500 to $1,500 per violation, and I have read the text of it myself. What I could not establish, before building anything, was whether one person acting alone could actually collect any of it, and whether that demand letter has the force the segment implies. Those two questions are the entire business, and nobody had answered them anywhere I could find.

So the work was a research rig, not a post. I could have read twenty blog posts about the TCPA and written something confident and wrong. The value was in making wrongness structurally hard instead of hoping I noticed it myself.

## Five agents with the same instruction and different jurisdictions

I split the question into five investigations and ran them in parallel, because the failure mode I was worried about was a single agent producing one smooth confident document that was wrong in a way I could not check. Five agents with separate search strategies surface each other's errors.

They covered: the private right of action and what an individual plaintiff actually has to do procedurally; whether the government ever pays a consumer anything, and what real settlements pay per person; who Compton is, what the company sells, and whether any payout has ever been independently verified; whether selling the kit is itself lawful, covering the FTC's earnings-claim rules, recurring billing, and the unauthorized practice of law problem; and what the demonstrably real paths are, including state mini-TCPAs, recording law, and documented solo wins.

That last bucket mattered most. I did not want to write "this is a scam" from a pile of complaints. A pitch can be sleazy and still describe a real legal mechanism that works for other people. To say which one this was, I needed the honest version of what actually pays.

## I made my own briefs wrong on purpose

I wrote the agent briefs with specific factual anchors, believing them correct. Several were not.

I told one agent to cite ABA Formal Opinion 1111-1-2014. That opinion does not exist. The number is a New York State Bar opinion on declining representation, an entirely different body and subject. Two agents caught this independently and told me rather than routing around it.

I told another to cite ABA Formal Opinion 469 for the rule on non-lawyers representing consumers. The agent reported that 469 is actually titled "Prosecutors and Debt Collection Companies" and is about debt collection, not consumer representation. It then checked the ABA's own index and confirmed that. I had prompted two separate agents with two separate wrong citations, and the second one caught the first error too.

I had also asked for material on a well-known record TCPA judgment I assumed was settled and large. The agent came back saying it could not find it, and that the famous number in that area actually belongs to a different statute entirely, a facial recognition privacy case, easy to conflate. Marked unverified rather than repeated.

This is the part I keep coming back to. I wrote those briefs with confidence, from memory, and three of the citations were fabricated. Not sloppy, fabricated. If a subagent had not been instructed to verify primary sources and flag what it could not confirm, every one of those would have landed in a published article with a real-looking URL attached. A hallucinated case name is worse than a gap, because a gap announces itself and a fake citation looks like homework.

## The pipeline's real product is the ledger

Each agent wrote its own file, and each file ended with a list of what it could not verify. That list is the actual output. An agent that verified twenty things and honestly marked four as unconfirmed is worth more than one that asserts thirty.

One agent was handed a claim that the FCC had distributed over $200 million in consumer refunds. It traced the number and found it appears only on content-mill sites, with no FCC source behind it, and marked it as likely fabricated rather than passing it through. Another found that a widely circulated figure for Florida, "$10,000 per text," is not the private right of action at all. It is a civil penalty that goes into a state trust fund, and the actual private remedy is $500 trebled to $1,500. The number everyone quotes is a real number attached to the wrong mechanism.

What I did not expect was how the pipeline itself would be the source of the same error. Two separate agents produced a confident citation to an ABA formal opinion that does not exist, in the same run. That is the failure I was designing against, happening to me first.

## Three agents, two verdicts, one arbitration

I also had two agents independently verify the same legal point, deliberately. I did not trust my own reading of what a formal opinion said about what a formal opinion says.

They came back with opposite answers. One said 469 covered the rule. One said it was about debt collectors. The second was right, and I confirmed it directly against the ABA's own index rather than picking the answer I preferred.

I had a mechanism for that, and the mechanism fired, and it cost me two agents to get one fact. That is a good ratio. The alternative is one agent being confidently wrong with nothing to catch it, which is exactly what nearly happened twice in the same batch.

## The result was not the scandal I expected

The statute is real. That is the part that surprised me, and it is why I did not write this as an exposé. A solo plaintiff can now, after a 2021 Supreme Court decision, claim per call for texts sent after a prior opt-out, which is the single most valuable thing in this area for a person filing alone. $500 a call, no need to prove you lost money, four years to file.

And the costs are brutal in the way that usually gets left out. Filing fees run $405. A large fraction of real settlements pay two to four dollars a person. A federal judge denied class certification to a man who filed sixty suits in a single year, and in another case a pro se plaintiff was ordered to pay forty thousand dollars in the defendant's legal fees. That last one is the number the pitch never mentions, and it is the one that matters.

The record contains exactly one clean example of a solo plaintiff being paid, and it is a default judgment, the kind you get when the defendant does not show up at all. She sought seven hundred twenty thousand dollars and received sixty thousand, lost the treble claim and the pain-and-suffering claim, and then spent a year litigating over the interest rate. She won the default, not the merits.

So the honest summary is: a real statute, a real but narrow path, an economics that punish exactly the small claims the pitch targets, and a business built on the gap between "illegal" and "collectible." Compton is a real person with a real federal case in his own name, was on TV repeatedly, and the only "proof" on his site is checks he posted himself. I found no independent verification of a single member payout, and I found no government program that pays a consumer for reporting a robocall. There is no bounty. The FTC did pay for robocall blockers at DEF CON years ago, but that was a developer prize, and that is not the same thing.

The vector claims $47 is worth thousands. I can trace where the money goes and who gets paid. The kit author does.

## What I would build differently

The unbundled lesson is not about the TCPA. It is that a research rig earns its keep on the claims it refuses to print, not the ones it confirms. Every number in that paper got a primary source, and the handful that did not got a visible mark next to them.

I would add one thing: make the two-agent arbitration a default rather than something I thought to do after a contradiction. I built the fan-out because I did not trust one agent's confidence. Then I had to manually build redundancy on the one fact that mattered most, which is an admission that the fan-out was not as load-bearing as I designed it to be.

And the pipeline should mark unverified items in the article itself, where a reader sees them, rather than in a private file. A reader deserves to know which sentences are quoted law and which are a summary of an agent's recollection, and hiding that boundary is how a research tool becomes a laundering machine for its own output.
