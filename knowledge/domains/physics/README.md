---
title: "Physics — domain knowledge"
type: reference
domain: physics
status: seed
concepts: [physics, doctrine-anchor, replication, derived-column, distance-scale, regression-dilution]
related: [../README.md, ../../research-discipline.md]
---

# Physics

Seeded by study 10 (Hubble 1929 replication). Doctrine anchor: a replication reports target by target and never says "replicated" for the whole unless every target reproduced within its tolerance; a prospective lock is disclosed as a lock, never called blindness.

## What study 10 learned about this field

- **A historical paper's headline number often needs inputs the paper never
  printed.** Reproducing Hubble's K = 465 requires a four-parameter joint fit for
  the constant and the Sun's motion, which needs each object's equatorial
  coordinates; the article prints none, and it never lists the membership of the
  nine groups behind its second solution. Both targets ended as documented method
  gaps rather than failed fits. Budget a replication for missing INPUTS, not only
  for methods to re-implement, and register an `inconclusive_if` on input
  availability before the first cell.
  *(supports 10-hubble-1929-replication#C2)*

- **In a table of astronomical measurements, ask what each column was computed
  from.** Hubble's Table 2 carries a distance column that looks like independent
  evidence and is not: it is the velocity divided by his own adopted constant.
  Using it to check a constant returns the ratio of two constants. A column is
  evidence about a quantity only if it was measured independently of it.
  *(supports 10-hubble-1929-replication#C13)*

- **The 1929-to-today factor of about six is a distance-SCALE story, not a
  velocity story.** One common multiplicative factor applied to every distance
  carries both two-parameter fits of Hubble's own table to within a few km/s/Mpc
  of the modern value. Velocities from spectra were good then and are good now;
  the ladder was what moved.
  *(supports 10-hubble-1929-replication#C5)*

- **On a distance–velocity relation the ordinary least-squares slope is a lower
  bound.** Distances carry far more error than velocities, so regressing velocity
  on distance is diluted toward zero; on Hubble's 24 objects the inverse fit
  returns a constant larger by a factor of about 1.6, and his own published value
  sits between the two. Report both fits, or an errors-in-variables fit when the
  error ratio is known.
  *(supports 10-hubble-1929-replication#C9)* *(supports 10-hubble-1929-replication#C11)*

- **A cluster given one assigned distance behaves as one leveraged point, not as
  many.** Hubble assigned the whole Virgo cluster a single distance from its mean
  luminosity; those four rows are the largest distances in the table and dropping
  them together moves the constant by more than its own standard error — which
  reproduces, from his numbers, his own attribution of the gap between his two
  solutions to those nebulae.
  *(supports 10-hubble-1929-replication#C9)*

- **Small-sample intervals in this regime under-cover, and it is measurable.**
  At n = 24 with the residual scatter of Hubble's own fit, a 95 % percentile
  bootstrap interval for the slope covers a known truth about 0.925 of the time,
  and the analytic interval about 0.938: both short of nominal, the bootstrap by
  more. Measured in a known-truth lab under a declared linear-plus-Gaussian
  process at Hubble's design points; it describes the interval machinery, not the
  universe.
  *(supports 10-hubble-1929-replication#C4)*
