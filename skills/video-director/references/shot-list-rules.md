# Shot List Rules

## Purpose

The shot list converts approved blocking into a filmable and generatable observation plan. It may use cinematography language, but it is not a provider prompt.

## Shot design

Every shot must have one dominant purpose: establish geography, show an action, reveal information, register a reaction, bridge time, or complete a state change.

Here a shot is an independently generated clip. Do not create a new shot merely because a conventional edit could insert a close-up. First test whether adjacent beats can remain one readable causal chain with the same location, subjects, axis, and camera logic.

## Shot budget

Before enumerating shots, use a default generated-clip duration of 5–10 seconds and target an average of 6–8 seconds. Compute the initial shot-count range as:

- minimum count: `ceil(total duration / 10)`;
- maximum count: `floor(total duration / 5)`.

For example, a 102-second film has an initial budget of 11–20 independently generated shots. Prefer the lower half when actions can remain readable. Report the range, proposed count, average duration, every exception, and expected keyframe count before Director approval.

Merge when adjacent actions share location, subject state, axis, and one causal intention. Keep separate when there is a time or location jump, an indispensable viewpoint change, an unrelated insert, a high-risk multi-subject interaction, or a transformation that needs its own controlled clip.

Prefer a fixed camera when movement adds no information. Use movement only to:

- follow necessary subject motion;
- reveal a new subject or location relation;
- change emotional distance at a meaningful beat;
- preserve spatial comprehension during a transition.

## Action load

Default to one primary causal chain per shot. A setup, primary action, and immediate reaction may share a shot when they form one readable event. Split a shot when it asks the subject to perform several independent actions, changes body orientation repeatedly, transfers multiple objects, crosses a large space, or combines complex action with complex camera movement.

## Duration

Use the screenplay scene duration as a budget. Shot durations within a scene must sum exactly to that scene budget. Let action complexity determine shot length; do not force equal durations.

Do not make a separate generated shot shorter than 5 seconds merely for an insert or reaction; absorb that information into a neighboring shot. A shot outside 5–10 seconds is an exception and requires a named generation reason plus explicit user approval. Complex physical interactions usually need more time. If a scene cannot fit its required actions, report the conflict rather than silently changing the approved scene duration.

## Required fields

- `shot_id`, `scene_id`, and covered `action_ids`;
- narrative purpose and duration;
- shot size, height, angle, movement, composition, and focus;
- subject, location, and prop IDs;
- visible start state, primary action, and visible end state;
- axis side and continuity dependencies;
- motion complexity and generation risk;
- `end_state_significance`: `low`, `medium`, or `high` for later selective keyframe planning.

Lens values are optional. Use them only when a specific perspective characteristic is important; otherwise use a descriptive perspective such as `natural`, `compressed`, or `spacious`.

## Generation-aware risk

Mark risk as `low`, `medium`, or `high` based on combined demands:

- number of independently moving subjects;
- hand and object interaction;
- transformation or magic;
- crowd density;
- rapid travel or complex body mechanics;
- camera motion combined with subject motion;
- continuity-sensitive start and end states.

Reduce high risk by simplifying movement, splitting the shot, holding the camera, or moving nonessential information to another shot. Do not delete a required story event solely to reduce cost.

## End-keyframe signal

Set `end_state_significance` to `high` when the end composition or state is materially different and continuity-sensitive, such as a completed handoff, a changed pose or height, a revealed location, a transformed prop, or a state that must begin the following shot. This is only a signal for Storyboard QC, not an instruction to generate an end frame.
