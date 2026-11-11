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

Each release is one experiment: an input video and the outputs both notebooks produced from it. It is tagged on the commit whose notebooks (and submodule pin) produced them, so data and code stay linked.

### Naming

- Tags: `vMAJOR.MINOR.PATCH` (`v0.1.0`, `v0.2.0`, ...). Bump MINOR for a new experiment (new video, prompt or settings), PATCH to fix assets of an existing one.
- Assets, always with the same names so the download commands keep working:

| Asset | Contents |
|---|---|
| `input_video.mp4` | the input video |
| `sam3_output.zip` | `sam3_output/` folder (extracts to `sam3_output/`) |
| `sam3d_output.zip` | `sam3d_output/` folder (extracts to `sam3d_output/`) |
| `SHA256SUMS` | `sha256sum` of the three files above |

Each asset must be under GitHub's 2 GB per-file limit.

### Release notes

The release notes record what is needed to reproduce the run:
- **sam3.ipynb:** prompts, preset, number of frames, fps, resolution, number of tracked objects;
- **sam3d.ipynb:** frame used, `MAX_OBJECTS` and filters, seed, reconstructed object IDs;
- **hardware:** GPU and measured VRAM peaks.

See [v0.1.0](https://github.com/alessionovel/sam4d/releases/tag/v0.1.0) for an example.

### Creating a release

Run both notebooks to completion first; outputs from a crashed run are inconsistent. Then, from the repository root:

```bash
# 1. make sure the notebooks and the submodule pin that produced the outputs are committed and pushed
git status && git submodule status

# 2. package (zips keep the top-level folder)
mkdir -p dist
zip -q -r dist/sam3_output.zip sam3_output
zip -q -r dist/sam3d_output.zip sam3d_output
cp input_video.mp4 dist/
(cd dist && sha256sum input_video.mp4 sam3_output.zip sam3d_output.zip > SHA256SUMS)

# 3. tag and publish
git tag -a vX.Y.Z -m "Example data: <short description>"
git push origin vX.Y.Z
gh release create vX.Y.Z --verify-tag --title "vX.Y.Z: <short description>" \
    --notes-file notes.md dist/input_video.mp4 dist/sam3_output.zip dist/sam3d_output.zip dist/SHA256SUMS

# 4. verify the upload
(mkdir -p /tmp/check && cd /tmp/check && gh release download vX.Y.Z -R alessionovel/sam4d && sha256sum -c SHA256SUMS)
```

Delete `dist/` afterwards. Then update the "Example data" section of the README if the new release should become the default example.

### Before publishing

The repository is public, and so are its releases. Check that:
- the video's license allows redistribution, with attribution in the release notes if it requires it;
- you're OK publishing what's visible in it: faces and license plates also appear in the frames, masks and textures of both output zips;
- `sam3_output/run_info.json` contains the absolute path of the video on the machine that produced it.
