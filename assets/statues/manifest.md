# Statue scan manifest

Last updated: 2026-11-21. Status: see "Download status" at the end for anything still pending or failed.

All files are under `assets/statues/raw/<short_name>/`. Nothing here needed a login
or credentials. Triangle counts and bounding boxes come from
`blender/inspect_mesh.py`; completeness notes come from 4-view Workbench renders made
with `blender/render_preview.py` (looked at by eye, not measured).

Rating scale (1-5): 5 = high-detail, complete, ancient type, ready for a hero or near shot; 4 = high detail with
missing limbs or minor issues; 3 = usable mid/background or good type but soft detail; 2 = distant background or
reference only; 1 = not recommended.

General caveats

- Scale and orientation are not normalised. SMK STLs are print-scaled (tallest side about 130-160 units, Z up);
  threedscans files are Y up (Mars and Minerva of Arezzo come in upside down or tilted); GLBs are in arbitrary
  photogrammetry units. Real heights are given where the source states them.
- No textures were kept on purpose (STL has none; the GLBs carry photo textures that can be ignored).
- Most SMK and threedscans meshes include the modern museum plinth.

## Sources and licences

**SMK** - Statens Museum for Kunst, Copenhagen, Royal Cast Collection: scans of 19th-century plaster casts of
the ancient originals (made with Scan the World). Found through the SMK Open API
(`https://api.smk.dk/api/v1/art/search/?keys=*&filters=[has_3d_file:true]`, 373 objects with 3D files). Each
record carries `public_domain: true` and `rights: https://creativecommons.org/publicdomain/mark/1.0/`; SMK's 2016
announcement says the 3D models are "released under Public Domain licences", and the same models are tagged
CC0 / public domain on Wikimedia Commons and SMK's Sketchfab account. Not verified: a licence statement on the
API that names the 3D files specifically (the `rights` field is per object record). Attribution is not required;
suggested credit: "SMK - Statens Museum for Kunst, Royal Cast Collection, <inv. no.>, public domain".
Source page pattern: `https://open.smk.dk/artwork/image/<inv. no.>`.

**threedscans.com** - Oliver Laric's scan archive. The site calls itself a "Free 3D scan archive"; Laric's
long-standing statement is that the scans can be "downloaded and used without copyright restrictions", and his
own Thingiverse uploads of the same scans (Mars, Minerva of Arezzo) are tagged CC0 1.0. There is NO formal
licence text on the current item pages, so for the 2023 Neptune uploads the licence rests on the site-wide
statement only. Suggested credit: "3D scan: Oliver Laric, threedscans.com".

**Zenodo "3dbigdataspace" community** - no-login mirror of CC-licensed Sketchfab models (via Objaverse 1.0), one
GLB per record. Licence checked twice for every file used: on the Zenodo record and on the public Sketchfab API
record of the original upload. All are CC BY 4.0 except Diana of Gabii (CC BY-SA 4.0 on Sketchfab; Zenodo shows
"cc-by-sa-2.5"). Attribution is required: "<title>" by <author> (Sketchfab), licence.

**Wikimedia Commons** - direct `upload.wikimedia.org` originals; licence taken from each file page (CC0 for the SMK uploads, CC BY-SA 4.0 for Scan the World's Juno Ludovisi, "Attribution" for the Musee Saint-Raymond scans).

**Internet Archive Thingiverse mirror** (`archive.org/details/thingiverse-<id>`) - used once, for Cosmo Wenman's
Athena of Velletri bust; the archive contains its own LICENSE.txt (CC BY 3.0).

## HERO: Zeus / Jupiter candidates

No high-detail, openly licensed, no-login scan of a canonical full-figure Jupiter (Smyrna, Verospi, Hermitage,
Marbury Hall, Dresden) was found. The Scan the World versions exist without login but are CC BY-NC-SA (see
Rejected). What was downloaded:

| short_name | what it is | source page | direct URL | licence / attribution | file (in raw/) | size | triangles | completeness | rating |
|---|---|---|---|---|---|---|---|---|---|
| zeus_jmch_sketchfab | Standing Jupiter, hip-mantle, sceptre in left hand, thunderbolt in lowered right, eagle at feet. Uploader's caption only says "Statue grecque by Mylon d'Eleutheres"; original statue and museum NOT identified | https://sketchfab.com/3d-models/zeus-782f99eadca041b8b52d9e0a2c6f4e3f (mirror: https://zenodo.org/records/10256419) | https://zenodo.org/api/records/10256419/files/782f99eadca041b8b52d9e0a2c6f4e3f.glb/content | CC BY 4.0 - "Zeus" by LZCreation (jmch), Sketchfab | zeus_jmch_sketchfab/zeus_jmch.glb | 10.5 MB | 308,436 (182,134 verts) | Complete: head, both arms, attributes, eagle, plinth plus a scrap of floor. Photogrammetry, soft detail, hole between legs/support | 3 |
| neptune_nimes (restored) | Roman marble Neptune, Musee de la Romanite, Nimes: bearded, long-haired, hip-mantle, trident, dolphin in right hand, left foot type with prow/dolphin support. Digitally restored by Iustinian Funie. Closest thing to a hero-quality bearded "father god"; needs attribute swap (trident head to sceptre, dolphin to thunderbolt/patera) to read as Jupiter | https://threedscans.com/uncategorized/neptune-restored-by-iustinian-funie/ | https://threedscans.com/wp-content/uploads/2023/04/Neptune_Iustinian_Funie.obj.zip | threedscans.com, "no copyright restrictions" (site statement, no formal licence on page) - Scan: Oliver Laric / threedscans.com; restoration: Iustinian Funie | neptune_nimes/Neptune_Iustinian_Funie.obj (+ .zip) | 111.9 MB OBJ | 2,687,755 (1,343,861 verts) | Complete after restoration: head, both arms, full trident. A museum mounting block is still attached behind the head/left hand; plinth present | 5 as Neptune, 4 as Jupiter stand-in |
| zeus_poseidon_artemision | Artemision Zeus or Poseidon (bronze, Athens NAM), SMK cast KAS2100. Severe-style striding nude, not a cult-statue type | https://open.smk.dk/artwork/image/KAS2100 | https://api.smk.dk/api/v1/download-3d/7m01br55g_smk-poseidon.stl | Public domain (SMK) | zeus_poseidon_artemision/KAS2100_poseidon_zeus_artemision_smk.stl | 10.5 MB | 209,494 | Complete nude figure with both outstretched arms; no plinth; low-resolution scan (a 2M-triangle CC0 version exists on Wikimedia Commons, see Download status) | 3 |
| zeus_poseidon_artemision (hi-res) | Same SMK cast KAS2100, full-resolution upload by SMK on Wikimedia Commons | https://commons.wikimedia.org/wiki/File:Poseidon_eller_Zeus_fra_Artemision_-_KAS2100.stl | https://upload.wikimedia.org/wikipedia/commons/c/cc/Poseidon_eller_Zeus_fra_Artemision_-_KAS2100.stl | CC0 (Commons file page; "Digitization: Statens Museum for Kunst") | zeus_poseidon_artemision/KAS2100_poseidon_zeus_artemision_commons_hires.stl | 104.7 MB | 2,094,906 | Complete, both arms, no plinth; real scale in mm (about 2.1 m), arbitrary orientation (not upright) | 4 |
| zeus_digitryart_sketchfab | Baroque/early-modern Jupiter with eagle on a cloud pedestal (not ancient; origin not stated by uploader) | https://sketchfab.com/3d-models/zeus-daa7f8cf5302497f886c5cbd59533098 (mirror: https://zenodo.org/records/10298816) | https://zenodo.org/api/records/10298816/files/daa7f8cf5302497f886c5cbd59533098.glb/content | CC BY 4.0 - "Zeus" by DigiTryArt, Sketchfab | zeus_digitryart_sketchfab/zeus_digitryart.glb | 18.4 MB | 499,996 (344,430 verts) | Complete figure; wrong period and style for 126 AD | 2 |
| jupiter_emperor_torso_ncma | "Torso of an Emperor in the Guise of Jupiter", Roman 1st c. marble, North Carolina Museum of Art | https://sketchfab.com/3d-models/torso-of-an-emperor-in-the-guise-of-jupiter-8bc03d09cdb44988be40d3ecf42c2c4c (mirror: https://zenodo.org/records/10243910) | https://zenodo.org/api/records/10243910/files/8bc03d09cdb44988be40d3ecf42c2c4c.glb/content | CC BY 4.0 - by debmayers24, Sketchfab | jupiter_emperor_torso_ncma/jupiter_emperor_torso_ncma.glb | 6.2 MB | 133,335 (82,369 verts) | Torso only: no head, no arms, cut off below the knees. Drapery reference | 2 |
| zeus_ammon_head | Zeus Ammon head/herm (SMK cast KAS1110), head reference only | https://open.smk.dk/artwork/image/KAS1110 | https://api.smk.dk/api/v1/download-3d/4q77fw75z_smk37-kas1110-zeus-ammon.stl | Public domain (SMK) | zeus_ammon_head/KAS1110_zeus_ammon.stl | 61.6 MB | 1,232,678 | Head only (ram horns), 54 cm | 2 |

## SUPPORTING statues

| short_name | deity | statue type / original | source page | direct URL | licence / attribution | file (in raw/) | size | triangles | real height | completeness | rating |
|---|---|---|---|---|---|---|---|---|---|---|---|
| athena_giustiniani | Minerva | Athena Giustiniani (Vatican), SMK cast KAS255 | https://open.smk.dk/artwork/image/KAS255 | https://api.smk.dk/api/v1/download-3d/g732df32k_smk52-kas255-athena-pallas-giustiniani.stl | Public domain (SMK) | athena_giustiniani/KAS255_athena_giustiniani.stl | 59.1 MB | 1,182,522 | 219 cm | Complete: helmet, spear, both arms, snake; thin oval plinth | 5 |
| athena_lemnia | Minerva | Athena Lemnia, Furtwaengler reconstruction (Dresden body, Bologna head), SMK cast KAS40 | https://open.smk.dk/artwork/image/KAS40 | https://api.smk.dk/api/v1/download-3d/cz30pz12n_20-smk-lemniam-athena-deci.stl | Public domain (SMK) | athena_lemnia/KAS40_athena_lemnia.stl | 124.1 MB | 2,482,840 | 208 cm | Both arms missing (stumps), bare head; plinth | 4 |
| athena_velletri | Minerva | (a) Athena of Velletri, Louvre original in its gallery niche; (b) Cosmo Wenman scan of the Skulpturhalle Basel cast, BUST only | (a) https://sketchfab.com/3d-models/athena-dite-pallas-de-velletri-674896a1e3cb4c5faafa7855bba033cd (mirror https://zenodo.org/records/10294906); (b) https://archive.org/details/thingiverse-196039 | (a) https://zenodo.org/api/records/10294906/files/674896a1e3cb4c5faafa7855bba033cd.glb/content; (b) https://archive.org/download/thingiverse-196039/Athena_of_Velletri_196039.zip | (a) CC BY 4.0 - by Minuit, Sketchfab; (b) CC BY 3.0 - "Athena of Velletri" by Cosmo Wenman (LICENSE.txt in archive) | (a) athena_velletri/athena_velletri_louvre_minuit.glb; (b) athena_velletri/Athena_of_Velletri_196039_wenman.zip, extracted OBJ in wenman_extracted/files/ | (a) 20.7 MB; (b) 197.9 MB zip, 65.6 MB OBJ | (a) 300,000 for statue plus whole niche; (b) 1,636,176 | 305 cm original | (a) Full figure, raised right arm, but the statue is a small part of a room scan: low detail, niche must be cut away. (b) Helmeted head and shoulders only, high detail | (a) 2; (b) 3 as head reference |
| minerva_arezzo | Minerva | Minerva of Arezzo, bronze, Museo Archeologico Nazionale Florence | https://threedscans.com/museo-archeologico-nazionale/athena/ | https://threedscans.com/wp-content/uploads/2016/02/Athena.obj.zip | CC0 on Laric's Thingiverse upload (thing 1544125) / threedscans "no copyright restrictions" - Scan: Oliver Laric, threedscans.com | minerva_arezzo/Athena.obj (+ .zip) | 114.9 MB OBJ | 2,608,341 (1,305,828 verts) | about 150 cm | High detail. Right arm absent (the modern restored arm is not on the statue), cut flat at the bottom with no feet/plinth; odd orientation | 3 |
| apollo_lykeios | Apollo | Apollo Lykeios type, SMK cast KAS1026 | https://open.smk.dk/artwork/image/KAS1026 | https://api.smk.dk/api/v1/download-3d/9593v081h_42-kas2016.stl | Public domain (SMK) | apollo_lykeios/KAS1026_apollo_lykeios.stl | 200.0 MB | 3,999,994 | 231.5 cm | Complete: right arm over head, tree-trunk support with snake; plinth | 5 |
| apollo_belvedere | Apollo | Apollo Belvedere (Vatican), SMK cast KAS353 | https://open.smk.dk/artwork/image/KAS353 | https://api.smk.dk/api/v1/download-3d/wm117v118_smk-apollo-belvedere.stl | Public domain (SMK) | apollo_belvedere/KAS353_apollo_belvedere_smk.stl | 14.5 MB | 290,254 | 232 cm | Complete: both arms (hands restored), cloak, sandals, tree-trunk support with snake; plinth. Low-resolution scan | 3 |
| apollo_belvedere (hi-res) | Apollo | Same SMK cast KAS353, full-resolution upload on Wikimedia Commons | https://commons.wikimedia.org/wiki/File:Apollo_Belvedere_-_KAS353.stl | https://upload.wikimedia.org/wikipedia/commons/6/61/Apollo_Belvedere_-_KAS353.stl | CC0 (Commons file page; "Digitization: Statens Museum for Kunst") | apollo_belvedere/KAS353_apollo_belvedere_commons_hires.stl | 145.3 MB | 2,905,356 | 232 cm | Same completeness as the small file; real scale in mm, arbitrary orientation (not previewed separately) | 5 |
| apollo_citharoedus_cyrene | Apollo | Apollo with kithara from Cyrene, 2nd c. AD marble, British Museum | https://sketchfab.com/3d-models/apollo-statue-a01dbaf0b7db4c308c9fcecade6d4283 (mirror https://zenodo.org/records/10283031) | https://zenodo.org/api/records/10283031/files/a01dbaf0b7db4c308c9fcecade6d4283.glb/content | CC BY 4.0 - "Apollo Statue" by artfletch, Sketchfab | apollo_citharoedus_cyrene/apollo_cyrene_bm_artfletch.glb | 32.0 MB | 804,558 (675,586 verts) | 229 cm | Right arm missing at shoulder, top of lyre broken, snake/trunk support; photogrammetry noise, back rough | 3 |
| diana_gabii | Diana | Diana of Gabii (Louvre type); scanned from a painted aluminium cast in Berlin | https://sketchfab.com/3d-models/diana-von-gabii-173b01a18a7b4a0dae067332ca4ee216 (mirror https://zenodo.org/records/10272988) | https://zenodo.org/api/records/10272988/files/173b01a18a7b4a0dae067332ca4ee216.glb/content | CC BY-SA 4.0 (Sketchfab; Zenodo record says cc-by-sa-2.5) - "Diana von Gabii" by VIMUNE, Sketchfab. Share-alike applies to derived meshes | diana_gabii/diana_von_gabii_vimune.glb | 135.1 MB | 3,998,994 (2,701,064 verts) | 165 cm original | Complete: head, both arms, trunk support, square plinth. Very clean | 5 |
| venus_capitoline | Venus | Capitoline Venus, SMK cast KAS493 | https://open.smk.dk/artwork/image/KAS493 | https://api.smk.dk/api/v1/download-3d/ff365988b_smk33-kas493-capitoline-venus-decimated.stl | Public domain (SMK) | venus_capitoline/KAS493_capitoline_venus.stl | 49.5 MB | 989,368 | 188.5 cm | Complete: both arms, vase with drapery support; plinth | 5 |
| venus_de_milo | Venus | Venus de Milo (Louvre), SMK cast KAS434 | https://open.smk.dk/artwork/image/KAS434 | https://api.smk.dk/api/v1/download-3d/w0892g669_smk-venus-de-milo.stl | Public domain (SMK) | venus_de_milo/KAS434_venus_de_milo.stl | 13.7 MB | 274,272 | 204 cm original | Arms missing as on the original; lower-resolution scan | 3 |
| mars_bacon_lincoln | Mars | Mars by John Bacon, 18th-century neoclassical marble, Usher Gallery Lincoln (NOT ancient) | https://threedscans.com/lincoln/mars/ | https://threedscans.com/wp-content/uploads/2016/02/Mars.stl.zip | CC0 on Laric's Thingiverse upload (thing 386984) / threedscans - Scan: Oliver Laric, threedscans.com | mars_bacon_lincoln/Mars.stl (+ .zip) | 31.0 MB STL | 620,142 | 200 cm | Complete nude Mars: helmet, sword, both arms, tree-trunk support, block plinth. File is upside down (Y axis) | 3 |
| ares_ludovisi | Mars | Ares Ludovisi (seated), SMK cast KAS250 | https://open.smk.dk/artwork/image/KAS250 | https://api.smk.dk/api/v1/download-3d/vh53x110x_43-ares-ludovisi-inv.stl | Public domain (SMK) | ares_ludovisi/KAS250_ares_ludovisi.stl | 100.0 MB | 2,000,062 | 158 cm | Complete seated group: both arms, sword, shield, Eros at the feet, rock seat; plinth | 5 (seated, so only for a seated niche) |
| hermes_belvedere | Mercury | Hermes ("Antinous") Belvedere, Vatican, SMK cast KAS1161 | https://open.smk.dk/artwork/image/KAS1161 | https://api.smk.dk/api/v1/download-3d/js956m23t_smk38-kas1161.stl | Public domain (SMK) | hermes_belvedere/KAS1161_hermes_belvedere.stl | 177.9 MB | 3,557,900 | 233.5 cm | Right arm missing below the shoulder and left hand missing (as original); palm-trunk support, plinth, no fig leaf | 4 |
| hermes_logios_germanicus | Mercury type | "Germanicus"/Marcellus as Hermes Logios (Louvre), SMK cast KAS644 | https://open.smk.dk/artwork/image/KAS644 | https://api.smk.dk/api/v1/download-3d/0p096c25s_smk41-kas644-germanicus.stl | Public domain (SMK) | hermes_logios_germanicus/KAS644_germanicus.stl | 75.3 MB | 1,505,550 | 192 cm | Complete: head, both arms (right hand raised), drapery over left arm with tortoise; plinth. Portrait head, not a god | 4 |
| neptune_nimes (raw) | Neptune | Same Nimes Neptune as in the hero table, unrestored raw scan | https://threedscans.com/uncategorized/neptune/ | https://threedscans.com/wp-content/uploads/2023/04/neptuneRaw.stl.zip | threedscans.com, "no copyright restrictions" (site statement only) - Scan: Oliver Laric, threedscans.com | neptune_nimes/neptuneRaw.stl (+ .zip) | 77.8 MB STL | 1,556,886 | not stated | Head and both arms present, trident shaft without head, right forearm damaged; rectangular museum-mount cut-out in the back of the mantle, support block behind head, broken prow support; Y up | 4 |
| dionysus_hadrians_villa | Bacchus | Dionysos with animal skin, from Hadrian's Villa (Museo Nazionale Romano), Roman 2nd c., SMK cast KAS196 | https://open.smk.dk/artwork/image/KAS196 | https://api.smk.dk/api/v1/download-3d/2227mv247_smk111-kas196.stl | Public domain (SMK) | dionysus_hadrians_villa/KAS196_dionysos.stl | 177.9 MB | 3,557,472 | 190 cm | Complete standing youth with nebris and long hair; fingers of left hand partly missing; trunk support, round plinth | 5 |
| demeter_knidos | Ceres | Demeter of Knidos (seated, British Museum), SMK cast KAS128 | https://open.smk.dk/artwork/image/KAS128 | https://api.smk.dk/api/v1/download-3d/cr56n5376_18-smk-demeter-from-knidos-cat-1300-bm-deci.stl | Public domain (SMK) | demeter_knidos/KAS128_demeter_knidos.stl | 132.6 MB | 2,652,908 | 150 cm | Seated on a throne block, veiled head present; both forearms and hands missing (as original); throne partly broken | 4 (seated) |
| livia_fortuna_ncg | Ceres / Juno stand-in | Empress Livia as Fortuna with cornucopia, from Pozzuoli, early 1st c. AD marble, Ny Carlsberg Glyptotek | https://sketchfab.com/3d-models/eff04040c8c944c5a5670d61f583abdb (mirror https://zenodo.org/records/10262891) | https://zenodo.org/api/records/10262891/files/eff04040c8c944c5a5670d61f583abdb.glb/content | CC BY 4.0 - "The Empress Livia as the Goddess Fortuna" by Geoffrey Marchal (geoffreymarchal), Sketchfab | livia_fortuna_ncg/livia_fortuna_ncg.glb | 12.9 MB | 385,361 (219,376 verts) | not stated | Draped standing goddess with cornucopia; right forearm missing; back of head/veil sliced flat by the scan; plinth. Soft detail | 3 |
| herakles_lansdowne | Hercules | Lansdowne Herakles (Getty; from Hadrian's Villa), SMK cast KAS224 | https://open.smk.dk/artwork/image/KAS224 | https://api.smk.dk/api/v1/download-3d/mg74qr49g_smk-110-kas224.stl | Public domain (SMK) | herakles_lansdowne/KAS224_herakles_lansdowne.stl | 200.0 MB | 4,000,048 | 208 cm | Complete: club over shoulder, lion skin, both arms, support, plinth | 5 |
| asklepios_hygieia_ncg | Aesculapius | Asklepios and Hygieia group, found near Porta S. Giovanni, Rome, 2nd c. AD marble, Ny Carlsberg Glyptotek | https://sketchfab.com/3d-models/3b5596c3efe14e78b1d970503098ace5 (mirror https://zenodo.org/records/10359269) | https://zenodo.org/api/records/10359269/files/3b5596c3efe14e78b1d970503098ace5.glb/content | CC BY 4.0 - "Asklepios, God of Healing" by Geoffrey Marchal (geoffreymarchal), Sketchfab | asklepios_hygieia_ncg/asklepios_hygieia_ncg.glb | 12.3 MB | 376,530 (217,567 verts) | not stated | Two-figure seated group with snake staff; heads and arms present; the back was not captured (smooth filled surface), so front view only | 2 |
| asklepios_munichia_torso | Aesculapius | Asklepios from Munichia (Athens NAM), SMK cast KAS1175, HEAD AND TORSO | https://open.smk.dk/artwork/image/KAS1175 | https://api.smk.dk/api/v1/download-3d/xk81jq714_145-smk-asklepios-kas1176.stl | Public domain (SMK) | asklepios_munichia_torso/KAS1175_asklepios_munichia.stl | 100.0 MB | 2,000,116 | 101.5 cm | Bearded Zeus-like head plus torso to the hips; both arms missing, left side broken away; on a museum mount. Excellent head/torso donor for a Jupiter | 3 |
| hera_barberini_head | Juno | Head of the Hera Barberini (Vatican), SMK cast KAS622, HEAD ONLY | https://open.smk.dk/artwork/image/KAS622 | https://api.smk.dk/api/v1/download-3d/cj82kc74k_smk25-orig1120-head-of-hera-barberini.stl | Public domain (SMK) | hera_barberini_head/KAS622_hera_barberini_head.stl | 53.4 MB | 1,067,546 | head | Head on a modern bust and socle, for grafting on a draped body | 2 |
| juno_ludovisi_head | Juno | Juno Ludovisi colossal head (Palazzo Altemps), Scan the World upload on Wikimedia Commons, HEAD ONLY | https://commons.wikimedia.org/wiki/File:Scan_the_World_-_Juno_Ludovisi.stl | https://upload.wikimedia.org/wikipedia/commons/4/4e/Scan_the_World_-_Juno_Ludovisi.stl | CC BY-SA 4.0 - Scan the World (Commons file page) | juno_ludovisi_head/juno_ludovisi_stw.stl | 32.1 MB | 642,984 | head, 116 cm original | Head and neck only, diadem and side locks; clean | 3 as head |
| juno_chiragan_msr | Juno | Head of Juno from the Chiragan villa, Musee Saint-Raymond Toulouse, HEAD ONLY | https://commons.wikimedia.org/wiki/File:Saint-raymond-juno-10.stl | https://upload.wikimedia.org/wikipedia/commons/e/e4/Saint-raymond-juno-10.stl | "Attribution" licence on the Commons file page, author Scan The World (exact CC version not checked) | juno_chiragan_msr/saint-raymond-juno-10.stl | 35.0 MB | 700,028 | head | Head only, nose and mouth broken, on a museum pin and base | 1 |
| vulcan_chiragan_msr | Vulcan | Head of Vulcan with pilos cap from the Chiragan villa, Musee Saint-Raymond Toulouse, HEAD ONLY | https://commons.wikimedia.org/wiki/File:Saint-raymond-vulcain-5.stl | https://upload.wikimedia.org/wikipedia/commons/d/df/Saint-raymond-vulcain-5.stl | "Attribution" licence on the Commons file page, author Scan The World (exact CC version not checked) | vulcan_chiragan_msr/saint-raymond-vulcain-5.stl | 35.0 MB | 700,080 | head | Bearded head only, on a museum pin and base; the only Vulcan found | 2 as head |
| aesculapius_chiragan_msr | Aesculapius | Draped Aesculapius figure from the Chiragan villa, Musee Saint-Raymond Toulouse | https://commons.wikimedia.org/wiki/File:29-msr-esculape-5-repaired.stl | https://upload.wikimedia.org/wikipedia/commons/f/f4/29-msr-esculape-5-repaired.stl | "Attribution" licence on the Commons file page, author Scan The World (exact CC version not checked) | aesculapius_chiragan_msr/29-msr-esculape-5-repaired.stl | 35.0 MB | 700,034 | small statue, size not stated | Headless, right arm missing, hip-mantle body on a broken base; body/drapery donor only | 2 |
| augustus_prima_porta | Augustus | Augustus of Prima Porta (Vatican), SMK cast KAS65 | https://open.smk.dk/artwork/image/KAS65 | https://api.smk.dk/api/v1/download-3d/6682x851h_smk-kas65-augustus-prima-porta.stl | Public domain (SMK) | augustus_prima_porta/KAS65_augustus_prima_porta.stl | 503.0 MB | 10,059,324 (decimate before use) | 219 cm | Complete: raised right arm, both hands, cuirass, Cupid on dolphin support; plinth. This file is at real scale in millimetres (2233 mm tall) | 5 |
| augustus_pontifex_labicana | Augustus | Augustus as Pontifex Maximus, capite velato togate statue (Via Labicana type, Palazzo Massimo) | https://sketchfab.com/3d-models/augusto-pontefice-massimo-augustus-88d06e2dff3f4d1daa7fd864fa0c5db1 (mirror https://zenodo.org/records/10363243) | https://zenodo.org/api/records/10363243/files/88d06e2dff3f4d1daa7fd864fa0c5db1.glb/content | CC BY 4.0 - by davide100, Sketchfab | augustus_pontifex_labicana/augustus_pontifex_davide100.glb | 22.3 MB | 583,911 (383,217 verts) | 207 cm original | Both hands missing (as original); back badly captured; a stray patch of ceiling floats above the head and must be deleted | 2 |
| caesar_fori_imperiali | Julius Caesar | Cuirassed Caesar, bronze replica on Via dei Fori Imperiali of the marble in Palazzo Senatorio, Rome | https://sketchfab.com/3d-models/statua-di-giulio-cesare-7fc6bfd0ea0643f6bd66baeaa8e3c2e3 (mirror https://zenodo.org/records/10319815) | https://zenodo.org/api/records/10319815/files/7fc6bfd0ea0643f6bd66baeaa8e3c2e3.glb/content | CC BY 4.0 - "Statua di Giulio Cesare" by massimo.riccioni, Sketchfab | caesar_fori_imperiali/caesar_fori_imperiali_riccioni.glb | 36.9 MB | 344,957 | not stated | Full figure with both arms on a tall modern pedestal; outdoor photogrammetry, blobby surface, lump on top of the head. Silhouette only | 2 |
| caesar_farnese_head | Julius Caesar | Caesar Farnese colossal head (Naples), SMK cast KAS101, HEAD ONLY | https://open.smk.dk/artwork/image/KAS101 | https://api.smk.dk/api/v1/download-3d/kh04dv45r_smk38-kas101-caesar-farnese19-01.stl | Public domain (SMK) | caesar_farnese_head/KAS101_caesar_farnese.stl | 41.4 MB | 828,960 | 125 cm | Head and neck only; could replace the head of caesar_fori_imperiali | 3 as head |

## Not found (no usable no-login, open-licence scan)

- Canonical full-figure Jupiter/Zeus (Smyrna, Verospi, Hermitage enthroned, Marbury Hall, Dresden): only NC-licensed versions.
- Juno / Hera full figure (Hera Barberini, Hera Campana): head only.
- Vulcan: head only (vulcan_chiragan_msr). Saturn: nothing at all.
- Farnese Hercules: only a remix whose upstream licence is non-commercial.
- Ares Borghese / Mars Ultor: not found; Mars is covered by the seated Ares Ludovisi and an 18th-century Mars.
- Diana of Versailles, Venus Genetrix, Aphrodite of Knidos (full), Hermes Ludovisi, Lateran Poseidon, Agrippa (statue): not found.
- Ceres standing: not found; covered by the seated Demeter of Knidos and Livia as Fortuna.
- Aesculapius standing: not found; only the seated group and a torso.

## Rejected

Non-commercial licences (downloadable without login, listed in case the project is non-commercial):

- Scan the World models mirrored on Zenodo/Europeana, all CC BY-NC-SA 4.0: Jupiter of Smyrna, Louvre (https://zenodo.org/records/21689479 and 21166852); Statue of Augustus as Jupiter, Hermitage, enthroned (21680490); Statue of Jupiter, Verona (21248739); Marble Statue of Zeus, Mougins (21415851, 21691570); Statue of Zeus Keraunios (21162720); Statue of Zeus-Serapis (21248339); Zeus with an eagle (21679724); Statue of Asklepios (20239385); Hercules, Royal Ontario Museum (21375812); Emperor Hadrian (21248467).
- Sketchfab www.noe-3d.at Zeus, Hera, Ceres, Diana, Asklepios, Ares Ludovisi: CC BY-NC.
- Sketchfab British Museum "Statue of Asclepius": CC BY-NC-SA. Sketchfab ancientworld3d "MSR Hercules Farnese": CC BY-NC-SA.
- Thingiverse 649822 "Zeus Sculpture (Statue 3D Scan)" by 3DWP: CC BY-NC-SA.

Unclear licence chain:

- Thingiverse 2668785 "Farnese Hercules" (https://archive.org/details/thingiverse-2668785, 140 MB, no login): tagged CC BY-SA 3.0 but it is a remix of the Scan the World Tuileries Hercules, which is distributed as non-commercial.
- Cults3D "Jupiter of Smyrna at The Louvre" (https://cults3d.com/en/3d-model/art/jupiter-of-smyrna-at-the-louvre-paris): a search snippet says CC BY-SA, the page returned HTTP 403 to curl and needs an account; conflicts with the NC licence on the same scan elsewhere.

Wrong or unusable content (downloaded, inspected, then deleted):

- Zenodo 10266648 "Caesar Statue Cultural Heritage using Scanner": turned out to be a Chinese robed figure.
- archive.org thingiverse-177375 "zeus": a flat relief plaque, not a statue.

Looked at but not downloaded: Zenodo 10353661 "Zeus Statue" by asphaltango (kit-bash of stock models, not a scan);
10287232 "Zeus" (a figure cut from Bernini's Four Rivers fountain); 10235503 Musee Saint-Raymond "Jupiter" (CC0, but a
16.8 cm bronze statuette); 10320110 "Poseidon of Milos" by jerryfisher (CC BY, built from 17 web photos, front only);
10322342 "Juno Regina from Chesters" (CC BY, headless provincial statue); Sketchfab "Empress Livia as the goddess
Ceres" (AI-generated, not a scan).

## Needs login (not attempted)

- Sketchfab, CC BY: "MODEL-07 Statue Of Augustus As Jupiter" by arvr3d, 132,632 faces, enthroned Hermitage type, described as made "for a museum project", may be a sculpt rather than a scan - https://sketchfab.com/3d-models/model-07-statue-of-augustus-as-jupiter-haris-b48882058e1a47979211d1516b65a4ef
- Sketchfab, CC BY: "Roman Asclepius Statue" by artfletch, 488,612 faces, British Museum - https://sketchfab.com/3d-models/roman-asclepius-statue-c1ac0762735e4bddb41a84982f37d67c
- Sketchfab, CC0: "Julius Caesar" (Julius Caesar statue) by www.noe-3d.at, 616,272 faces - https://sketchfab.com/3d-models/802edad501a94f9c99b84c4c33d376b7
- Sketchfab, CC BY: "Statue - Julius Caesar - Venice Museum" by gabriele.l, 217,042 faces - https://sketchfab.com/3d-models/bf55a15638694a8cb450f9f198f68f4d
- Sketchfab, CC0: SMK account (same casts as above, lower resolution) - https://sketchfab.com/smkmuseum
- MyMiniFactory, Scan the World (licence shown elsewhere as CC BY-NC-SA, so check before use): Jupiter of Smyrna https://www.myminifactory.com/object/3d-print-6629 ; Jupiter Enthroned, Naples https://www.myminifactory.com/object/3d-print-jupiter-enthroned-89464 ; Jupiter of Versailles https://www.myminifactory.com/object/3d-print-jupiter-of-versailles-at-the-louvre-paris-france-7069 ; Statue of Zeus, Baths of Diocletian https://www.myminifactory.com/object/3d-print-32127 ; Hercules Farnese, Tuileries https://www.myminifactory.com/object/hercules-fernese-at-the-jardin-des-tuileries-paris-7290
- Thingiverse live site: every request from curl is stopped by a Cloudflare challenge (HTTP 403); a browser is needed.

## Download status

All files listed above were downloaded completely (size checked against Content-Length; every STL checked against
its triangle-count header) and opened in Blender. Total on disk: about 3.3 GB. Nothing is pending.

Problems met on the way:

- api.smk.dk drops connections every few MB and stalls with more than about two parallel connections; every SMK
  file needed many resumed range requests. A first pass left truncated files, all since replaced.
- Wikimedia Commons answered HTTP 429 for about ten minutes after a burst of API queries; a later slow pass worked.
- Thingiverse and Cults3D block curl (HTTP 403).
- Not verified: the identity of the statue in zeus_jmch_sketchfab; the exact CC version of the Musee Saint-Raymond
  "Attribution" files; a formal licence for the 2023 threedscans Neptune files; real heights marked "not stated".
- Helper scripts written: blender/inspect_mesh.py and blender/render_preview.py. Zip archives were kept next to
  their extracted meshes.

## Hero statue (chosen 2026-11-21)

The user chose the Jupiter of Smyrna for the apse, accepting a non-commercial licence: the video is a non-commercial project.

| Field | Value |
|---|---|
| short_name | jupiter_smyrna_stw |
| deity | Jupiter |
| statue | Jupiter of Smyrna, Roman marble, Louvre (Ma 13); standing, hip-mantle, thunderbolt raised in the right hand |
| source page | https://zenodo.org/records/21689479 (Scan the World mirror; duplicate record 21166852) |
| direct download | https://zenodo.org/api/records/21689479/files/67a2fdd4cc10992323531181bc987556_normalized.glb/content |
| licence | CC BY-NC-SA 4.0: non-commercial only; adaptations must be shared under the same licence |
| attribution | "Jupiter of Smyrna at The Louvre, Paris" by Scan the World, CC BY-NC-SA 4.0 |
| local path | assets/statues/raw/jupiter_smyrna_stw/67a2fdd4cc10992323531181bc987556_normalized.glb (also the 4 MB .glb) |
| size | 25.5 MB |
| triangles | 306,688 |
| completeness | complete figure including head, both arms and thunderbolt; square museum plinth; tree-trunk support at the left leg. Mesh units are arbitrary (125 high), scale to be set in the scene |
| rating | 5 |
| preview | renders/previews/statue_jupiter_smyrna.png |

## Replacement candidates (2026-11-21)

Goal: undamaged full figures (no missing arms or heads) to replace demeter_knidos (no forearms), hermes_belvedere
(right arm missing) and the soft caesar_fori_imperiali. Licence policy now accepts CC BY-NC and CC BY-NC-SA (the video
is non-commercial), so Scan the World mirrors on Zenodo are used. Each new folder holds `record_<id>.json`, the Zenodo
API record at download time. 4-view checks: `renders/previews/statues_candidates/<short_name>.png` (Workbench, judged
by eye). Scan the World "_normalized" GLBs are scaled so the longest side is about 130 units and are unwelded
(vertex count about 3 x triangles); real heights are not stated in the records unless given below. "Complete" means
head, both arms and hands present; restorations made in the 17th-19th century count as present.

Attribution pattern for Scan the World: "<title>" by Scan the World (MyMiniFactory), CC BY-NC-SA 4.0. Share-alike
applies to edited meshes.

### Already downloaded, re-checked

| short_name | deity | triangles | completeness verdict | preview |
|---|---|---|---|---|
| mars_bacon_lincoln | Mars | 620,142 | COMPLETE (helmet, sword, both arms, support, plinth), but 18th-century neoclassical, not ancient; file upside down | renders/previews/statues_candidates/mars_bacon_lincoln.png |
| apollo_citharoedus_cyrene | Apollo | 804,558 | DAMAGED: right arm missing at the shoulder, top of the kithara broken | renders/previews/statues_candidates/apollo_citharoedus_cyrene.png |
| livia_fortuna_ncg | Fortuna / Ceres | 385,361 | DAMAGED: right forearm missing, back of head and veil sliced flat by the scan; soft | renders/previews/statues_candidates/livia_fortuna_ncg.png |
| minerva_arezzo | Minerva | 2,608,341 | DAMAGED: right arm missing, cut off flat below the knees (no feet, no plinth) | renders/previews/statues_candidates/minerva_arezzo.png |
| augustus_pontifex_labicana | Augustus | 583,911 | DAMAGED: both hands missing; back poorly captured; floating ceiling patch over the head | renders/previews/statues_candidates/augustus_pontifex_labicana.png |
| asklepios_hygieia_ncg | Aesculapius | 376,530 | Figures complete (both heads and arms, snake staff), but the back is not captured (smooth fill): front-facing niche use only | renders/previews/statues_candidates/asklepios_hygieia_ncg.png |

### New downloads

| short_name | deity | statue | source page | direct URL | licence / attribution | file (in raw/) | size | triangles | bbox (file units) | completeness verdict | rating | preview |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| juno_versailles_stw | Juno | Standing draped Juno (Versailles); right hand forward holding a patera-like object, left hand gathering the mantle. Date and whether ancient or a modern copy not stated in the record | https://zenodo.org/records/21290234 | https://zenodo.org/api/records/21290234/files/31bd6d6806b04eb3f3fa221ecd5fe7a0_normalized.glb/content | CC BY-NC-SA 4.0 - "Juno at The Palace of Versailles, France" by Scan the World | juno_versailles_stw/31bd6d6806b04eb3f3fa221ecd5fe7a0_normalized.glb | 32.3 MB | 392,214 | 37 x 55 x 130 | COMPLETE: head with diadem-like hair, both arms and hands, feet, thin plinth. Clean, crisp drapery | 5 | renders/previews/statues_candidates/juno_versailles_stw.png |
| demeter_seated_stw | Ceres (seated) | Seated Demeter on a high-backed throne, veiled and wreathed; Roman 2nd c. AD after a late-5th-c. BC Greek type; the outstretched arm is a restoration (record). Museum not named in the record | https://zenodo.org/records/21691619 | https://zenodo.org/api/records/21691619/files/6233f987ee29f122ae48f26cb280f44e_normalized.glb/content | CC BY-NC-SA 4.0 - "Statue of Demeter" by Scan the World | demeter_seated_stw/6233f987ee29f122ae48f26cb280f44e_normalized.glb | 58.1 MB | 699,996 | 71 x 80 x 130 | COMPLETE (with restored arm): head, veil, wreath, both arms, feet, throne with scroll arms; back of throne is a smooth fill; modern rectangular plinth. Direct seated replacement for demeter_knidos | 5 | renders/previews/statues_candidates/demeter_seated_stw.png |
| ceres_woman_stw | Ceres | Roman woman as Ceres, veiled "Pudicitia"-like mantle statue. Museum not named in the record | https://zenodo.org/records/21247857 | https://zenodo.org/api/records/21247857/files/c71208ef89337058082b4594ea832884_normalized.glb/content | CC BY-NC-SA 4.0 - "Statue of a woman as Ceres" by Scan the World | ceres_woman_stw/c71208ef89337058082b4594ea832884_normalized.glb | 58.3 MB | 699,998 | 40 x 31 x 113 | COMPLETE: veiled head, both arms (right under the mantle at the chest, left hand lowered at the hip holding a fold of the mantle or an attribute, not identifiable at preview size), feet, plinth. Surface slightly worn, small chips | 4 | renders/previews/statues_candidates/ceres_woman_stw.png |
| julia_ceres_louvre_stw | Ceres | "Julia as Ceres", Louvre (former royal collection): Roman princess of the imperial house as Ceres, "Pudicitia" type, wheat wreath | https://zenodo.org/records/21487644 | https://zenodo.org/api/records/21487644/files/3895e1fc275de79751756e1436bc80b1_normalized.glb/content | CC BY-NC-SA 4.0 - "Julie en Ceres at The Louvre, Paris" by Scan the World | julia_ceres_louvre_stw/3895e1fc275de79751756e1436bc80b1_normalized.glb | 57.9 MB | 695,610 | 43 x 30 x 130 | COMPLETE: head with wreath, right hand at the chin, left arm across the body, feet, round plinth. Very clean | 5 | renders/previews/statues_candidates/julia_ceres_louvre_stw.png |
| hermes_farnese_bm_stw | Mercury | Hermes Farnese, British Museum: nude youth, one hand on the hip, chlamys over the other shoulder and arm, winged sandals, tree-trunk support (Andros/Belvedere family) | https://zenodo.org/records/21679952 | https://zenodo.org/api/records/21679952/files/2c3a829b582d040ac66722b92958779c_normalized.glb/content | CC BY-NC-SA 4.0 - "Hermes Farnese at The British Museum, London" by Scan the World | hermes_farnese_bm_stw/2c3a829b582d040ac66722b92958779c_normalized.glb | 45.3 MB | 544,940 | 51 x 37 x 125 | COMPLETE: head, both arms and hands, winged sandals, trunk support, thin round plinth. Crisp | 5 | renders/previews/statues_candidates/hermes_farnese_bm_stw.png |
| hermes_pioclementino_versailles_stw | Mercury | Restored cast of the Hermes ("Antinous") Belvedere of the Museo Pio-Clementino (same type as hermes_belvedere), Gardens of Versailles | https://zenodo.org/records/21173227 | https://zenodo.org/api/records/21173227/files/87d7f1303ccbfbae61921890ce70fd07_normalized.glb/content | CC BY-NC-SA 4.0 - "Hermes of the Museo Pio-Clementino in The Palace of Versailles, France" by Scan the World | hermes_pioclementino_versailles_stw/87d7f1303ccbfbae61921890ce70fd07_normalized.glb | 43.7 MB | 526,282 | 59 x 50 x 130 | COMPLETE (restored): right hand on the hip, left forearm wrapped in the chlamys, head, feet. The palm-trunk support is scanned as stacked faceted blocks and should be remodelled or hidden. Same pose as the current hermes_belvedere, so a drop-in replacement | 4 | renders/previews/statues_candidates/hermes_pioclementino_versailles_stw.png |
| hermes_kew_stw | Mercury | "Kew Gardens Hermes", British Museum: same Andros-Farnese type, hand on hip, mantle over the left arm, tree-trunk support | https://zenodo.org/records/21678275 | https://zenodo.org/api/records/21678275/files/455ae5d9fc31950da1ec87220707803f_normalized.glb/content | CC BY-NC-SA 4.0 - "Kew Gardens Hermes at The British Museum, London" by Scan the World | hermes_kew_stw/455ae5d9fc31950da1ec87220707803f_normalized.glb | 26.5 MB | 318,104 | 55 x 39 x 125 | Complete in outline (head, both arms, feet, support) but weathered garden marble: pitted surface, worn hands and face | 3 | renders/previews/statues_candidates/hermes_kew_stw.png |
| hermes_loghios_stw | Mercury | "Hermes Loghios" (winged petasos), right arm restored by Alessandro Algardi in the 17th century in an orator's gesture; mantle over the left arm, trunk support | https://zenodo.org/records/21290104 | https://zenodo.org/api/records/21290104/files/389e81a8c180862b0fdf01cf84cd1515_normalized.glb/content | CC BY-NC-SA 4.0 - "Statue of Hermes Loghios" by Scan the World | hermes_loghios_stw/389e81a8c180862b0fdf01cf84cd1515_normalized.glb | 13.0 MB | 156,566 | 50 x 54 x 130 | COMPLETE (with restored right arm): petasos with wings identifies Mercury clearly. Low triangle count, soft but clean | 4 | renders/previews/statues_candidates/hermes_loghios_stw.png |
| nerva_jupiter_stw | Jupiter / deified emperor | Colossal seated Nerva as Jupiter, hip-mantle, right arm raised (Vatican, Sala Rotonda type; museum not named in the record) | https://zenodo.org/records/21647999 | https://zenodo.org/api/records/21647999/files/881649f3726d9aa68c2130fcfa59c0ee_normalized.glb/content | CC BY-NC-SA 4.0 - "Nerva as Jupiter" by Scan the World | nerva_jupiter_stw/881649f3726d9aa68c2130fcfa59c0ee_normalized.glb | 58.2 MB | 699,996 | 86 x 85 x 130 | COMPLETE from the front and sides: head, both arms, raised hand holding a short rod (sceptre stub?), feet, rocky seat. The back is not captured (smooth blob), so it needs a niche or wall behind it | 4 | renders/previews/statues_candidates/nerva_jupiter_stw.png |
| augustus_jupiter_hermitage_stw | Divus Augustus as Jupiter | Enthroned Augustus as Jupiter, Hermitage (made under one of his successors): hip-mantle, long sceptre in the left hand, orb/patera in the right | https://zenodo.org/records/21680490 | https://zenodo.org/api/records/21680490/files/f42cfb85fed7b26149043ec86e59d39f_normalized.glb/content | CC BY-NC-SA 4.0 - "Statue of Augustus as Jupiter" by Scan the World | augustus_jupiter_hermitage_stw/f42cfb85fed7b26149043ec86e59d39f_normalized.glb | 14.6 MB | 175,880 | 70 x 100 x 122 | COMPLETE: head, both arms and hands, sceptre, feet, throne block; back of the throne plain. Clean but low triangle count | 4 | renders/previews/statues_candidates/augustus_jupiter_hermitage_stw.png |
| emperor_seated_augustus_stw | Divus Augustus as Jupiter | Colossal seated emperor in the Jupiter type, from Herculaneum (found 1741), AD 41-54; head restored as Augustus with oak wreath and fillets; hip-mantle, right arm raised holding a sceptre stub, throne (Naples, MANN; museum inferred from the find-spot, not named in the record) | https://zenodo.org/records/21164633 | https://zenodo.org/api/records/21164633/files/2bda4307fcadc8dc90b9c76642090540_normalized.glb/content | CC BY-NC-SA 4.0 - "Emperor Seated On The Throne As Augustus" by Scan the World | emperor_seated_augustus_stw/2bda4307fcadc8dc90b9c76642090540_normalized.glb | 70.1 MB | 858,704 | 79 x 98 x 130 | COMPLETE (with restorations): head and wreath, both arms, raised hand with a short sceptre end, both feet, throne, plinth; back of the figure and throne scanned. Crisp. Best divine-emperor replacement for caesar_fori_imperiali | 5 | renders/previews/statues_candidates/emperor_seated_augustus_stw.png |
| caesar_borghese_stw | Divus Julius (heroic) | "Julius Caesar Borghese", Louvre: heroic nude with a Caesar-like portrait head (identity uncertain), chlamys over the left arm, cuirass on the support; body after the Diomedes of Kresilas | https://zenodo.org/records/21375700 | https://zenodo.org/api/records/21375700/files/df1c917fe9a4351257c056a0bfb841e6_normalized.glb/content | CC BY-NC-SA 4.0 - "Julius Caesar Borghese at The Louvre, Paris" by Scan the World | caesar_borghese_stw/df1c917fe9a4351257c056a0bfb841e6_normalized.glb | 70.8 MB | 858,670 | 61 x 45 x 130 | COMPLETE: portrait head, both arms and hands (right forearm forward, left wrapped in the mantle), feet, support with cuirass, plinth. Crisp. Standing alternative for the Caesar slot | 5 | renders/previews/statues_candidates/caesar_borghese_stw.png |
| asklepios_giustini_stw | Aesculapius | Standing Asklepios, Giustini type: bearded, fillet, himation, snake-entwined staff under the right hand | https://zenodo.org/records/21679742 | https://zenodo.org/api/records/21679742/files/5cbf4da0b186e0db28895b97b3e45c3f_normalized.glb/content | CC BY-NC-SA 4.0 - "Asklepios Giustini type" by Scan the World | asklepios_giustini_stw/5cbf4da0b186e0db28895b97b3e45c3f_normalized.glb | 57.9 MB | 700,016 | 59 x 130 x 46 (lies on its side: up axis is Y) | COMPLETE: head, both arms, staff with snake, feet, rounded plinth. Surface a little smooth (possibly a cast) | 4 | renders/previews/statues_candidates/asklepios_giustini_stw.png |
| asclepius_roman_stw | Aesculapius | "Roman Asclepius": bearded, hip-mantle, standing; mounted on a modern rod | https://zenodo.org/records/21164919 | https://zenodo.org/api/records/21164919/files/4e5ef6e33bdce33b2a9396dd0736a37a_normalized.glb/content | CC BY-NC-SA 4.0 - "Roman Asclepius" by Scan the World | asclepius_roman_stw/4e5ef6e33bdce33b2a9396dd0736a37a_normalized.glb | 57.1 MB | 694,644 | 46 x 37 x 125 | DAMAGED: staff and snake missing, lower legs partly missing (one foot only), no plinth, on a museum rod. Head and arms present | 2 | renders/previews/statues_candidates/asclepius_roman_stw.png |
| bacchus_statuette_stw | Bacchus | Marble statuette of Bacchus leaning on a vine trunk, wine cup in the right hand, panther at his feet (museum not named in the record) | https://zenodo.org/records/21243621 | https://zenodo.org/api/records/21243621/files/8f35f255b3568d14f16109ec9814f9f9_normalized.glb/content | CC BY-NC-SA 4.0 - "Statue of Bacchus" by Scan the World | bacchus_statuette_stw/8f35f255b3568d14f16109ec9814f9f9_normalized.glb | 42.1 MB | 505,342 | 69 x 46 x 122 | COMPLETE: head with wreath, both arms, cup, panther, trunk with grapes, plinth. A statuette, so carving is coarser than life-size work; can be scaled up | 4 | renders/previews/statues_candidates/bacchus_statuette_stw.png |
| vulcan_thorvaldsen | Vulcan | Vulcan, marble, 1861, by B. L. Bergslien after Thorvaldsen's 1838 model, Thorvaldsen Museum Copenhagen: pilos cap, exomis, hammer and tongs on an anvil, helmet and greaves at his feet | https://zenodo.org/records/10351688 (mirror of Sketchfab a9f8a85b4d6842cf9e10b7b5d4070dc2) | https://zenodo.org/api/records/10351688/files/a9f8a85b4d6842cf9e10b7b5d4070dc2.glb/content | CC BY-NC (Zenodo says cc-by-nc-1.0) - "Vulcan" by Geoffrey Marchal (geoffreymarchal), Sketchfab | vulcan_thorvaldsen/a9f8a85b4d6842cf9e10b7b5d4070dc2.glb | 17.4 MB | 552,170 | 20.7 x 19.4 x 36.9 | COMPLETE: head, both arms, tools, anvil, plinth; back rougher. 19th-century neoclassical, not ancient, but the only complete Vulcan found | 3 | renders/previews/statues_candidates/vulcan_thorvaldsen.png |
| fortuna_cinquantenaire | Fortuna | Fortuna with cornucopia, Roman marble, Musee du Cinquantenaire, Brussels | https://zenodo.org/records/10233382 (mirror of Sketchfab c3d426d1a1594ec6bbb5de989e3faa42) | https://zenodo.org/api/records/10233382/files/c3d426d1a1594ec6bbb5de989e3faa42.glb/content | CC BY-NC (Zenodo says cc-by-nc-1.0) - "Fortuna" by Geoffrey Marchal, Sketchfab | fortuna_cinquantenaire/c3d426d1a1594ec6bbb5de989e3faa42.glb | 18.0 MB | 587,534 | 14.9 x 9.0 x 33.9 | DAMAGED: head missing, right arm missing, top of the cornucopia broken; back flat. Rejected (kept only as a drapery donor) | 1 | renders/previews/statues_candidates/fortuna_cinquantenaire.png |

### Screened on Zenodo preview renders only (not downloaded)

- Rejected as damaged or wrong: 21692327 Statue of Hera (Borghese, headless); 21527309 / 21171618 "Goddess Hera (?)" (headless); 21248302 / 21678656 "Statue of The God Mercury" (legs and arms broken); 21215932 "Statue of Aesculapius" (headless); 21376901 "Statue of Dionysus" (right forearm missing); 21165702 Tyche, Lyon (head only); 21162480 Demeter (CC0, seated, headless); 21173052 "So-called Ceres" (seated, headless); 21244999 Livia as Ceres (bust).
- Not ancient: 21172980 Statue of Juno with peacocks (Florentine fountain); 21527316 Hera and 21567746 Ceres (18th-century garden statues, noe-3d, CC BY-NC); 21679494 Goddess in the Giusti Gardens.
- Complete but not downloaded (alternatives): 21162341 Demeter with torch, British Museum (small statue on a high pedestal); 21161530 Statue of Hermes, 21163716 youthful Hermes and 21375399 Hermes [2] (all look complete, same Andros-Farnese family as hermes_farnese_bm_stw); 21376112 Tyche "Fortuna Braccio Nuovo" type (head status unclear at preview size: check before use).
- No complete Vulcan, Fortuna or standing Juno-of-Rome type (Hera Campana/Barberini) was found; Vulcan exists only as the Thorvaldsen copy above.

### Recommendation

- demeter_knidos (seated Ceres, forearms missing) -> demeter_seated_stw: same seated pose and veil, complete (arm restored), 700k triangles, CC BY-NC-SA. Standing alternatives: julia_ceres_louvre_stw (cleanest) or juno_versailles_stw if a Juno is wanted.
- hermes_belvedere (right arm missing) -> hermes_farnese_bm_stw (complete, crisp, winged sandals identify Mercury) or hermes_pioclementino_versailles_stw (same Belvedere pose with the arms restored; its faceted palm support needs fixing).
- caesar_fori_imperiali (soft) -> emperor_seated_augustus_stw (Divus Augustus enthroned as Jupiter, crisp, complete) if a seated figure fits the slot; otherwise caesar_borghese_stw (standing, Caesar-type head, complete).

### Download status (replacement pass)

All 17 files above downloaded completely (size checked against the Zenodo API), about 0.8 GB in total. Not verified:
the museums of demeter_seated_stw, ceres_woman_stw, juno_versailles_stw, nerva_jupiter_stw and bacchus_statuette_stw
(not named in the records); whether juno_versailles_stw is ancient or a modern copy; real heights.
