# Releases and the submodule

This repository versions three kinds of things differently:

- **code** (notebooks, docs) is committed normally;
- **third-party code** (SAM 3D Objects) is a pinned git submodule;
- **data** (input video and outputs) is published as GitHub Release assets, never committed.

## The `sam-3d-objects` submodule

`sam-3d-objects/` is [facebookresearch/sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects), pinned to the commit the notebooks were tested with:

| Pinned commit | Upstream date | Tested with |
|---|---|---|
| `f91db41` ("SA-3DAO Release - README Update (#190)") | 2026-06-02 | `.venv-sam3d` as in [SETUP.md](SETUP.md), RTX 4090 |

The submodule is used as is. Don't commit changes inside it: local fixes go in the notebook or the docs (see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).

### Common commands

```bash
git clone --recurse-submodules git@github.com:alessionovel/sam4d.git   # fresh clone
git submodule update --init                                            # after a plain clone
git submodule update                                                   # after a pull that moved the pin
git submodule status                                                   # show the pinned commit
```

`git pull` does not update the submodule's files by itself. Run `git submodule update` afterwards, or set `git config submodule.recurse true` once.

### Updating the pin to a newer upstream version

Only do this deliberately, after testing:

```bash
cd sam-3d-objects
git fetch origin
git checkout <new-commit>
# reinstall .venv-sam3d if upstream requirements changed (SETUP.md, section 2),
# then run sam3d.ipynb end to end and compare against the last release
cd ..
git add sam-3d-objects
git commit -m "Update sam-3d-objects to <short-sha>: <reason>"
```

Update the table above in the same commit.

## Data releases

**The latest release always contains all the data**: every input and every output published so far, not only what is new. `gh release download -R alessionovel/sam4d` (no tag) therefore always gets everything. A new release copies the assets of the previous one and adds or replaces what changed; older releases stay as history. Each release is tagged on the commit whose notebooks (and submodule pin) produced its newest outputs, so data and code stay linked.

### Naming

- Tags: `vMAJOR.MINOR.PATCH` (`v0.1.0`, `v0.2.0`, ...). Bump MINOR when an experiment is added (new video, sequence, prompt or settings), PATCH to fix assets. Results that are still running when a release is made are added to that same release when they finish.
- Assets, always with the same names so the download commands keep working:

| Asset | Contents |
|---|---|
| `input_video.mp4` | the example input video |
| `sam3_output.zip` | example `sam3_output/` folder (extracts to `sam3_output/`) |
| `sam3d_output.zip` | example `sam3d_output/` folder (extracts to `sam3d_output/`) |
| `<sequence>_sequence.zip` | an evaluation sequence (extracts to `sequences/<name>/`) |
| `<sequence>_sam3_output.zip` | `sam3.ipynb` output on it (extracts to `eval_output/sam3_<sequence>/`) |
| `<sequence>_eval_output.zip` | `evaluate.ipynb` runs on it (extract to `eval_output/<sequence>_*/`) |
| `<sequence>_*.mp4` | preview videos of those runs |
| `SHA256SUMS` | `sha256sum` of every other asset |

Each asset must be under GitHub's 2 GB per-file limit.

### Release notes

The release notes record what is needed to reproduce the run:
- **sam3.ipynb:** prompts, preset, number of frames, fps, resolution, number of tracked objects;
- **sam3d.ipynb:** frame used, `MAX_OBJECTS` and filters, seed, reconstructed object IDs;
- **hardware:** GPU and measured VRAM peaks.

See [v0.2.0](https://github.com/alessionovel/sam4d/releases/tag/v0.2.0) for an example.

### Creating a release

Run both notebooks to completion first; outputs from a crashed run are inconsistent. Then, from the repository root:

```bash
# 1. make sure the notebooks and the submodule pin that produced the outputs are committed and pushed
git status && git submodule status

# 2. start from everything in the current latest release
mkdir -p dist
(cd dist && gh release download -R alessionovel/sam4d && sha256sum -c SHA256SUMS && rm SHA256SUMS)

# 3. add or replace the new assets (zips keep the top-level folder, see the naming table), e.g.
zip -q -r dist/<sequence>_eval_output.zip eval_output/<sequence>_*
(cd dist && sha256sum * > SHA256SUMS)

# 4. tag and publish as the latest release
git tag -a vX.Y.Z -m "<short description>"
git push origin vX.Y.Z
gh release create vX.Y.Z --verify-tag --latest --title "vX.Y.Z: <short description>" --notes-file notes.md dist/*

# 5. verify the upload
(mkdir -p /tmp/check && cd /tmp/check && gh release download vX.Y.Z -R alessionovel/sam4d && sha256sum -c SHA256SUMS)
```

To add results that finished after the release was made, upload them to the same release (`gh release upload vX.Y.Z <files>`), then upload the regenerated `SHA256SUMS` with `--clobber` and update the notes (`gh release edit vX.Y.Z --notes-file notes.md`).

Delete `dist/` afterwards. The release notes keep one section per experiment, so they describe everything the release contains.

### Before publishing

The repository is public, and so are its releases. Check that:
- the video's license allows redistribution, with attribution in the release notes if it requires it;
- you're OK publishing what's visible in it: faces and license plates also appear in the frames, masks and textures of both output zips;
- `sam3_output/run_info.json` contains the absolute path of the video on the machine that produced it.
