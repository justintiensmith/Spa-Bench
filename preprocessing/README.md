# Dataset preprocessing

Spa-Bench uses full-length, two-camera, and motion-trimmed derivatives of the
same 1,200-episode semantic corpus. The trimming script locates sustained joint
motion, retains a short pre-motion prefix, rewrites episode/frame metadata, and
preserves prompts and provenance.

The exact input/output dataset revisions for each policy remain to be added to
`datasets/README.md`.

