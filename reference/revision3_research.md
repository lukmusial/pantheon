# Revision 3 research (2026-11-22)

Research after draft 6 on three questions: the wall-versus-columns lighting imbalance, realistic
fire, and material/shader libraries for the code-generated architecture. Findings come from web
research by three subagents plus one path-traced reference render. Items marked "unverified" were
not confirmed for UE 5.9 on Mac.

## 1. Lighting imbalance (pale walls glow, columns/altars/paintings dark)

### Reference render

`MRQ_PathTraceTest` on draft 6 frames 3744 (Apollo hold) and 4320 (Venus hold), 512 samples.

- Frame 3744: usable. In the path tracer the exedra wall and the giallo antico columns are about
  equally bright and everything is warm (fire-lit). In Lumen the same wall is near-white with a cool
  cast, several times brighter than the columns. So Lumen puts far more cool light on the wall than
  physically traced transport does.
- The path-traced frame is not a clean ground truth: the whole image has an orange haze and the
  statue is washed out (the path tracer treats fog and the fire lights differently).
- Frame 4320: failed (smeared horizontal bands). Cause unknown. Unusable.

Conclusion: moderate evidence that the glow is at least partly a Lumen error, not only pale stone.
An earlier test with the sun switched off (`renders/stills_nosun`) did not remove the blowout at the
time, so sun bounce alone is unlikely to be the whole cause; conditions have changed since, so it
needs retesting.

### Candidate causes and fixes, in test order

1. **Hit lighting ignores lighting channels for GI.** Known limitation UE-357552 (reported on
   5.6.1; unverified for 5.9). Our sun is confined to the exterior by lighting channels, so it may
   still bounce into the interior. Hit-lighting GI reportedly also ignores per-light Indirect
   Lighting Intensity. Fix: `r.Lumen.HardwareRayTracing.LightingMode 2` (hit lighting for
   reflections only; GI from the surface cache).
   - https://forums.unrealengine.com/t/5-6-1-lumen-hardware-raytracing-hit-lighting-doesnt-respect-lighting-channels/2690802
   - https://forums.unrealengine.com/t/lumen-gi-and-reflections-feedback-thread/501108/1943
   - https://dev.epicgames.com/documentation/unreal-engine/hardware-ray-tracing-in-unreal-engine
2. **Albedo too high for an enclosed pale niche.** Wall ground colours are about 0.58-0.64 linear.
   Interreflection in a pale niche multiplies brightness by roughly 1/(1-albedo); dark surfaces get
   no such gain. Target about 0.45-0.52 linear (sRGB about 180-190). Epic's measured values: fresh
   concrete 0.51, fresh snow 0.81, charcoal 0.02. Pigment targets (estimates, not sourced): black
   ground no lower than 0.03-0.04, red ochre 0.10-0.15, porphyry 0.06-0.10, giallo antico 0.35-0.5.
   Giallo antico rendering near-black would indicate a material bug, not lighting.
   - https://dev.epicgames.com/documentation/en-us/unreal-engine/physically-based-materials-in-unreal-engine
   - https://haukethiessen.artstation.com/blog/7AwM/tutorial-adding-a-pbr-validation-view-mode-to-unreal
3. **Light the subjects, not the walls.** One soft, low rect light per shot as a "floor bounce
   card", on its own lighting channel shared only with statues, columns, paintings and altars;
   Indirect Lighting Intensity 0, Volumetric Scattering Intensity 0, shadows on. Only behaves as
   intended once item 1 is in place.
   - https://dev.epicgames.com/documentation/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine
4. **Lumen diagnostics.** Surface Cache view (pink = missing coverage, yellow = culled); raise Max
   Lumen Mesh Cards, Lumen Scene Detail 2-4, Final Gather Quality 2-4; test
   `r.Lumen.ScreenProbeGather.ReferenceMode 1`, `r.Lumen.ScreenProbeGather.MaxRayIntensity`
   (default 10) and `r.LumenScene.Radiosity.MaxRayIntensity` (default 40). Thin near-coplanar
   painted panels are a self-occlusion suspect. The surface cache folds specular into albedo for
   legacy Default Lit materials, which brightens marble bounce.
   - https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-technical-details-in-unreal-engine
5. **Local exposure.** Epic's guidance is Highlight and Shadow Contrast 0.6-1, Blurred Luminance
   Blend 0.4-0.6. Our 0.55 highlight is just outside it. Try highlight 0.6, shadow 0.55-0.6,
   blend 0.5, kernel about 50 %. Watch for halos at wall/column edges.
   - https://dev.epicgames.com/documentation/en-us/unreal-engine/auto-exposure-in-unreal-engine
6. **Grade last.** Highlights Gain about 0.9, shadows slightly up. Do not raise Lumen Diffuse Color
   Boost; keep Skylight Leaking 0. Fog at density 0.016 adds veiling light that greys the blacks.

Unverified: Epic's rendering-path table is ambiguous about hardware ray tracing and the path
tracer on Metal. The path-trace preset produced frames here on UE 5.9, so the path tracer runs;
confirm in the render log that Lumen is using hardware ray tracing.
- https://dev.epicgames.com/documentation/en-us/unreal-engine/supported-features-by-rendering-path-for-desktop-with-unreal-engine

## 2. Realistic fire

### Recommended: Niagara sprites with flipbooks from a real fluid simulation

Replace the crossed additive cards with 2-4 camera-facing Niagara sprites per fire (random start
frame, rotation, mirrored UV), fed by flipbooks rendered from a real simulation, blended with
motion vectors; add lit smoke, sparse embers and heat haze.

Flipbook sources, best first:
- **JangaFX free VDB animations (CC0)**: "Simple Fire" (101 frames, 65 MB), "Small Camp Fire"
  (200 frames, 59 MB). Render in Blender Cycles (Principled Volume, blackbody emission, EXR with
  alpha plus vector pass), pack into a sheet. Fully scriptable on this Mac.
  https://jangafx.com/software/embergen/download/free-vdb-animations
- **Niagara Fluids "3D Gas" baked with the Niagara Flipbook Baker.** 3D fluids rendered black on
  Mac in 5.3/5.4, reportedly fixed in 5.5; test on 5.9 first.
  https://dev.epicgames.com/documentation/unreal-engine/niagara-flipbook-baker-quick-start-guide-in-unreal-engine
- **Unity CC0 flipbooks** (Flame02, SmallFlame01): quick test only.
  https://unity.com/blog/engine-platform/free-vfx-image-sequences-flipbooks
- **Epic Niagara Examples Pack** (free on Fab): emitter-stack template.
  https://www.fab.com/listings/0e188eca-4e54-4fb2-a9ed-d8b8a565e600
- Paid (Fab Standard; Mac support not stated): "Cinematic Fire"
  https://www.fab.com/listings/b3e98248-dae7-4ca5-9e04-5026603d295f , Hivemind "Realistic Fire VFX"
  https://www.fab.com/listings/4b5f0d45-aaac-4a2e-a5b5-2d9d93523eff

Flipbook sizes: oil lamps 6x6 (36 frames, 256-512 px per frame); braziers 8x8 at 4K (64 frames,
512 px); altar 8x8 at 8K or two 4K sheets (48-64 frames, 1024 px), played at 24-30 fps with
motion-vector blending. Store temperature/density/smoke in channels and colour with the BlackBody
node. Cross-fade the loop seam.
- https://forums.unrealengine.com/t/community-tutorial-level-up-your-flipbooks-with-motion-vectors-and-subuv-blending-unreal-5-tutorial/2694470

### Not recommended on Mac: true volumetric fire

VDB import (Sparse Volume Textures) works only in Windows and Linux editors; Heterogeneous Volumes
are Experimental and path-tracer support needs DX12. Live Niagara Fluids for 27 fires is too heavy.
- https://dev.epicgames.com/documentation/en-us/unreal-engine/sparse-volume-textures-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/heterogeneous-volumes-in-unreal-engine

### Fire light

- Real lamp and candle flames oscillate at about 10 Hz but light output in still air changes only a
  few percent; gusts give dips at about 5 Hz. Pool fires puff at about 1.5/sqrt(D) Hz: about 2.4 Hz
  for 0.4 m bowls, about 1.5 Hz for a 1 m altar fire.
  https://arxiv.org/pdf/2207.02019
- So the current 45-115 % brightness swing is too strong to be realistic. Use about +-5-10 % for
  lamps with rare dips, +-20-30 % for braziers (slow puffing plus fast noise, never periodic).
  Liveliness should come from flame shape and from the light moving, not from brightness swings.
- Jitter the light position 2-5 cm with the same noise as the flame; source radius 10-20 cm for
  braziers, about 1 cm for lamps; two de-phased lights for the altar; a small shadowed light inside
  each bowl so the fire lights its own rim and tripod.
- Prefer animating intensity/position over a light function (light functions reach Lumen and fog
  only through the 5.5+ Light Function Atlas; check in 5.9).
- Keep 1800-1900 K; camera white balance about 3200-4000 K or flames go deep orange. Volumetric
  Scattering Intensity 0.3-1 for a subtle halo. Bloom down.

### Why the current fire looks fake

Crossed cards (visible intersection, uniform glow, no density variation); colour not driven by
temperature (no yellow-white core, no dark transparent base); no smoke; fire does not light its own
container; identical loops across 27 fires; flipbook frame steps under MRQ temporal sampling turn
into double exposures unless frames are interpolated (tie frame to particle age, deterministic
emitters, warm-up frames).
- https://forums.unrealengine.com/t/fire-system-niagara-render-to-movie-each-subsample-shows-different-fire-stage/249845
- https://dev.epicgames.com/documentation/unreal-engine/caching-and-reusing-your-system

## 3. Materials and shaders for the code-generated parts

### 3.1 Geometry first (Blender, scriptable): biggest gain

- Bevel every cornice, moulding, panel, pedestal, coffer step and plinth: 2-6 mm, 2-3 segments,
  weighted normals. Shader-only rounded corners do not change the silhouette.
- Split the revetment and the opus sectile floor into separate slabs with 1-2 mm recessed joints.
- Write a random per-slab value into vertex colour or a UV channel; the master material shifts
  hue/value/roughness and offsets or rotates the triplanar lookup per slab.
- Bake AO and curvature into vertex colours (Cycles bake to colour attribute) to drive dirt and wear.

### 3.2 Better source textures

- **ambientCG (CC0, API `ambientcg.com/api/v2/full_json`, 8K)**: pavonazzetto Marble012/Marble021;
  giallo antico Onyx007, Marble026, Travertine008/012; rosso antico Onyx010; africano Marble009,
  Marble013; granite and porphyry base Granite001A-007B; gold Metal048A/B/C, Foil002; bronze
  Metal008/013/015/017/018; Plaster001-007.
- **Poly Haven (CC0, API `api.polyhaven.com`)**: white_stucco, white_stucco_02, plastered_wall_04,
  worn_plaster_wall, grey_plaster for the dome and coffers.
- **Quixel Megascans on Fab**: reported free again from 12 Nov 2026 under the Fab Standard License
  (press reports; re-check). Needs an Epic account and a one-time add-to-library step, then assets
  sit in /Game/Fab and can be referenced by script. Most useful: Roman Marble Relief/Trim/Plinth
  scans, plaster and concrete surfaces, and decals (leaks, stains, grime).
  https://cgchannel.com/2026/11/epic-has-made-megascans-free-again-for-good-this-time
- No openly licensed scans of the named Roman marbles were found. The Oxford Corsi Collection
  (copyright, personal research only) can serve as colour/pattern reference for the recolouring.
  https://www.oum.ox.ac.uk/corsi/index.html
- Lower priority: ShareTextures (custom licence, read first), Textures.com (not scriptable),
  Substance 3D Assets (subscription), AMD GPUOpen MaterialX library (generic).

### 3.3 Master material additions (scriptable)

- Crevices (AO mask): darker, desaturated, rougher; DistanceToNearestSurface for contact grime.
- Edges (curvature mask): slightly lighter and rougher; red bole showing on worn gilding.
- Polished columns: Clear Coat shading model (base roughness about 0.3 under a 0.05 coat).
  Floor: honed 0.3-0.45 with a low-frequency "traffic" polish mask.
- Subsurface Profile only on pale marbles.
- Soot: world-Z gradient plus decals above lamps and altars; drip decals on the drum.
- Bronze: dark brown with green-grey patina only in crevices. Gold leaf: faint leaf-square seams,
  roughness 0.2-0.35.

### 3.4 Not recommended now

- **Substrate**: Epic's docs still say Mac "may not work entirely"; legacy Clear Coat and
  Subsurface Profile cover the needs.
  https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-substrate-materials-in-unreal-engine
- **Nanite tessellation/displacement**: Experimental; slow and flickering on Mac in forum reports.
  Use real modelled joints instead.
  https://forums.unrealengine.com/t/ue-5-4-macbook-m3-pro-max-nanite-displacement/1822742
- No Epic sample project with marble worth borrowing was found.
