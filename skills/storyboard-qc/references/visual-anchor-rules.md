# Visual Anchor Rules

## Goal

Anchors are visual identity evidence, not illustrations of every shot. The Image Asset Prompts package fixes the minimal anchor list for new projects; legacy Director v1 manifests also remain valid. Storyboard QC validates and executes the fixed list but does not silently change membership.

## Character anchors

For each primary identity or confirmed age state, define:

- anchor ID and linked Director asset/state IDs;
- exact visual choices that are locked;
- full or three-quarter body view sufficient to establish silhouette and costume;
- neutral readable posture and expression unless a state requires otherwise;
- visible recurring props or travel gear only when they belong to that state;
- plain or low-information background that does not compete with identity;
- prohibited changes inherited from the Asset Bible.

Do not create a separate anchor for every expression or pose. Add a second view only when the first cannot show important costume, silhouette, age, or carried-gear information.

## User-supplied references

Treat user-supplied turnarounds, three-view sheets, model sheets, portraits, environment concepts, and prop sheets as first-class anchor sources.

- `use_existing_reference` when the supplied material already covers the identity, silhouette, costume or layout, and required state well enough for downstream frames;
- `generate_from_reference` when identity is established but normalized views, age states, costumes, poses, expressions, damage states, or lighting-neutral variants are missing;
- `generate_new` only when there is no adequate approved reference.

Register each source with a stable `REF_*` ID, original path, asset ID, covered states, visible views, and human review status. Never convert a turnaround into text and discard the visual source. Derived images must retain a reference lineage back to every source used.

## Location anchors

Prioritize reusable geometry:

- entrances and exits;
- fixed landmarks;
- functional zones;
- travel directions and important axes;
- base materials and architecture after user confirmation;
- occupancy, damage, weather, and time state.

When one location has several time states, keep the base layout identical and describe only controlled changes. A state-variation anchor is justified when the change is too large to preserve reliably through text alone.

## Prop anchors

Generate a separate prop anchor only if it is recurring, visually distinctive, state-changing, handed between subjects, or central to continuity. Ordinary bowls, generic fabric, or common tools should usually be locked inside a character or location reference instead.

## Background groups

Use one compact group-style reference only when crowd clothing, demographic mix, density, or condition must stay consistent. Do not create individual identities for background figures who do not perform story actions.

## Individual human review

Review one anchor candidate at a time against its manifest item. Display the exact image ID, attempt version, `must_show`, and `must_not_show`. Record only an explicit human `approved`, `retry_requested`, or `rejected` decision before advancing. A retry preserves the failed file and changes only the named defect.

## Contact Sheet review

Review all anchors together for:

- same-identity age relationship;
- face, hair, body proportion, costume, and silhouette;
- location layout and landmark persistence;
- repeated prop design;
- palette and material consistency;
- forbidden additions;
- state differences appearing only where authorized.

The Contact Sheet is an overview after individual decisions, not an approval mechanism. Every included anchor must retain its own decision record. If an overview exposes a new conflict, reopen only the affected item with user confirmation.
