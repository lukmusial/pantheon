# Architectural ornament scan manifest

Last updated: 2026-11-21. Complete: 10 scans downloaded (about 205 MB), all checked.

All files are under `assets/architecture/scans/<short_name>/`. Each folder also holds
`record_<id>.json`, the Zenodo API record at download time (title, licence, creators, description). Nothing needed a
login. Triangle counts and bounding boxes come from `blender/inspect_mesh.py`; completeness notes come from 4-view
Workbench renders made with `blender/render_preview.py` into `renders/previews/scans/<short_name>.png` (judged by eye).
Bounding boxes are in file units (GLB metres for most; Zenodo "_normalized" files are rescaled to about 1-2 units, so
real size must come from the source description).

Licence policy for this project (user decision, non-commercial video): CC0, PD, CC BY, CC BY-SA, CC BY-NC and
CC BY-NC-SA are acceptable. Attribution is recorded for each file.

Rating scale (1-5): 5 = complete, crisp, right period, use as is; 4 = good with minor repair; 3 = usable at
mid-distance or as a sculpting base; 2 = reference only; 1 = not recommended.

## Downloaded

| short_name | what | source page | direct URL | licence | attribution | local path | triangles | bbox (file units) | completeness | rating | preview |
|---|---|---|---|---|---|---|---|---|---|---|---|
| capital_tarraco_theatre | Roman Corinthian column capital with top of fluted shaft, from the Augustan theatre of Tarraco (31 BC-AD 14), MNAT 7593, Tarragona. Photogrammetry from 1549 photos | https://zenodo.org/records/21529215 (Objaverse/Sketchfab mirror) | https://zenodo.org/api/records/21529215/files/03f18fa9b86b4383aba5df9cd6af4324_normalized.glb/content | CC BY-NC (Zenodo record says cc-by-nc-1.0; exact version on Sketchfab not checked) | "Capital from Tarraco (Tarragona, Spain)" by Global Digital Heritage, with the Museu Nacional Arqueologic de Tarragona, Sketchfab | capital_tarraco_theatre/03f18fa9b86b4383aba5df9cd6af4324_normalized.glb | 1,114,143 | 0.90 x 0.97 x 0.90 (normalised) | Complete capital: two leaf rings, caulicoli, all four corner volutes, inner helices, abacus with abacus flowers; one abacus corner and some leaf tips chipped, small modern fixing block on one abacus face; shaft stub included (cut it off). Crisp | 5 | renders/previews/scans/capital_tarraco_theatre.png |
| capital_terracina | Roman Corinthian capital from the forum area of Terracina, Italy | https://zenodo.org/records/10363684 (mirror of Sketchfab d2dd11a6e38b422e86e9fc992b000077) | https://zenodo.org/api/records/10363684/files/d2dd11a6e38b422e86e9fc992b000077.glb/content | CC BY 4.0 | "Corinthian capital of a public Roman building" by tdr125, Sketchfab | capital_terracina/d2dd11a6e38b422e86e9fc992b000077.glb | 544,907 | 817 x 651 x 1000 | Fragment: lower leaf rings and caulicoli only, heavily weathered; volutes and abacus broken away, top rough | 2 | renders/previews/scans/capital_terracina.png |
| capital_beja_composite | Roman Composite capital from Pax Iulia (Beja, Portugal), Museu Regional de Beja; two marble blocks, about 1.0 m high, 1.7 x 1.6 m | https://zenodo.org/records/10388929 (mirror of Sketchfab b914d13592ec4b6693488d23fd28c442) | https://zenodo.org/api/records/10388929/files/b914d13592ec4b6693488d23fd28c442.glb/content | CC BY 4.0 | "Roman Capitel from Beja, Portugal" by valoncar, Sketchfab | capital_beja_composite/b914d13592ec4b6693488d23fd28c442.glb | 1,954,680 | 7.34 x 6.64 x 5.24 | Partial: the capital is set into later masonry; one face (leaf rings, egg-and-dart echinus, volutes, rosettes) and parts of a second are carved and well preserved, the rest is rough wall blocks. Composite, not Corinthian. Good source to cut one face and mirror/array | 3 | renders/previews/scans/capital_beja_composite.png |
| capital_montdore | Antique Roman Corinthian capital from the baths at Le Mont-Dore, France, on a modern block | https://zenodo.org/records/10354900 (mirror of Sketchfab ec2c272e4e4d4ca48226add7c6a7ae3c) | https://zenodo.org/api/records/10354900/files/ec2c272e4e4d4ca48226add7c6a7ae3c.glb/content | CC BY 4.0 | "Chapiteau antique therme Mont Dore" by DominiqueAllios, Sketchfab | capital_montdore/ec2c272e4e4d4ca48226add7c6a7ae3c.glb | 137,760 | 1.86 x 2.56 x 2.44 | Complete in outline (two leaf rings, corner volutes, abacus) but weathered, volutes worn to stumps, top surface noisy; low triangle count. Provincial, not Rome | 3 | renders/previews/scans/capital_montdore.png |
| capital_krakow | Corinthian capital, Archaeological Museum in Krakow, MAK/AS/2435 (date not stated) | https://zenodo.org/records/21527711 (Objaverse/Sketchfab mirror; museum page https://muzea.malopolska.pl/en/objects-list/1177) | https://zenodo.org/api/records/21527711/files/1b61fd199e744afa9bdb8f46cf843e31_normalized.glb/content | CC0 1.0 | Wirtualne Muzea Malopolski / Archaeological Museum in Krakow (credit optional) | capital_krakow/1b61fd199e744afa9bdb8f46cf843e31_normalized.glb | 44,594 | 531 x 535 x 492 | Complete small capital but a decimated, blobby mesh (44k triangles); detail lives in the texture only | 2 | renders/previews/scans/capital_krakow.png |
| pilaster_capital_ephesus_stw | Corinthian pilaster capital from the (Hellenistic) Temple of Artemis at Ephesus, British Museum | https://zenodo.org/records/21243215 | https://zenodo.org/api/records/21243215/files/1704f1f35f97ee06e5263aed11f84b31_normalized.glb/content | CC BY-NC-SA 4.0 | "Corinthian pilaster-capital The Ephesus temple at The British Museum, London" by Scan the World | pilaster_capital_ephesus_stw/1704f1f35f97ee06e5263aed11f84b31_normalized.glb | 312,464 | 106 x 78.5 x 27.4 (lies flat; render with up axis Y, then it is upside down) | Front face complete in outline (corner volutes, helices, central flower, leaf ring) but soft, blobby photogrammetry; back is a flat cut. Greek, not Roman Imperial. Not an olive-leaf type | 2 | renders/previews/scans/pilaster_capital_ephesus_stw.png |
| cornice_merida_theatre | Roman cornice block from the theatre of Augusta Emerita (1st c. AD), Museo Nacional de Arte Romano, Merida, displayed on a brick wall: modillions with acanthus, coffers between, dentils, egg-and-dart, bead-and-reel | https://zenodo.org/records/10368028 (mirror of Sketchfab 946037ab8ba94263bec81811f6b17532) | https://zenodo.org/api/records/10368028/files/946037ab8ba94263bec81811f6b17532.glb/content | CC BY 4.0 | "Cornisa / Cornice" by egiptologo91, Sketchfab | cornice_merida_theatre/946037ab8ba94263bec81811f6b17532.glb | 1,268,614 | 35372 x 21937 x 14125 (arbitrary units) | Good fragment: about three modillion bays with soffit coffers, dentil course and mouldings, crisp; left/right ends broken; scanned together with a large flat museum wall that must be cut away (the cornice is perhaps 1/3 of the triangles). Best cornice found: cut one bay and array it | 4 | renders/previews/scans/cornice_merida_theatre.png |
| cornice_vespasian_temple | Fallen entablature/cornice block of the Temple of Vespasian, Forum Romanum, Rome, lying among other blocks | https://zenodo.org/records/10243671 (mirror of Sketchfab 9f6efafca0b446d08c0678f9936519bf) | https://zenodo.org/api/records/10243671/files/9f6efafca0b446d08c0678f9936519bf.glb/content | CC BY 4.0 | "Temple of Vespasianus" by hervislab, Sketchfab | cornice_vespasian_temple/9f6efafca0b446d08c0678f9936519bf.glb | 322,932 | 1369 x 1157 x 888 | Fragmentary outdoor scan: one face shows a soffit coffer with a rosette and a modillion end, the rest is rubble and ground; open shell, low detail. Reference only, the only Rome-made piece found | 2 | renders/previews/scans/cornice_vespasian_temple.png |
| base_taormina_stw | Marble column base, Attic type (torus-scotia-torus on square plinth), reused at the ex-church of Sant'Agostino, Taormina; date not stated (probably reused antique or Renaissance) | https://zenodo.org/records/20216046 | https://zenodo.org/api/records/20216046/files/9581a2f908a06f6cbbd314414e620868.glb/content | CC0 1.0 (Zenodo record) | "Base of a Column" by Scan the World (credit optional) | base_taormina_stw/9581a2f908a06f6cbbd314414e620868.glb | 300,176 | 127 x 130 x 65 | Complete profile but weathered: lower torus and plinth chipped, scotia shallow; top cut flat. Usable as a texture/wear reference; a clean modelled base will look better | 3 | renders/previews/scans/base_taormina_stw.png |
| rosette_alexandria | White marble panel from a tombstone, Alexandria: basket of flowers in a beaded medallion inside a moulded frame | https://zenodo.org/records/10291659 (mirror of Sketchfab 6b3d8bbf33a344de9ceb9470ef848af4) | https://zenodo.org/api/records/10291659/files/6b3d8bbf33a344de9ceb9470ef848af4.glb/content | CC BY 4.0 | "White Marble Rosette" by hobamohahebo, Sketchfab | rosette_alexandria/6b3d8bbf33a344de9ceb9470ef848af4.glb | 211,741 | 5.32 x 0.52 x 4.95 | Complete relief panel, crisp, but it is a flower basket, not a coffer rosette; date not stated. Reference only | 2 | renders/previews/scans/rosette_alexandria.png |

## Recommendation

- Column capitals: use **capital_tarraco_theatre** (Augustan Corinthian, complete, 1.1M triangles, CC BY-NC). It is
  the only complete, crisp Roman Imperial Corinthian capital found; style is close to the Pantheon's (Augustan-
  Hadrianic Roman Corinthian with olive-type leaflets is not available). Cut off the shaft stub and the modern block on
  the abacus, mirror a good quarter to repair the chipped abacus corner, then instance. Second choice:
  capital_montdore (complete but worn). capital_beja_composite can supply a crisp Composite face for pilaster
  capitals (cut one face, use as a relief on a flat pilaster block).
- Cornice: **cornice_merida_theatre** (CC BY): cut one modillion bay with its dentils and mouldings and array it.
- Attic base: no clean scan; model it (base_taormina_stw is only a wear reference).
- Coffer rosettes: no Roman coffer rosette scan found; model them (cornice_vespasian_temple shows a soffit rosette as
  reference).

## Searched, not found or not used

- Pantheon itself: no ornament scan. Zenodo 21397172 "Pantheon, Rome, Italy" (CMBC, CC BY, 162 MB) is a whole-
  building exterior photogrammetry model, too coarse for capitals; not downloaded.
- Hadrianic/Trajanic Rome capitals (Forum of Trajan, Temple of Venus and Roma, Hadrian's Villa): none found on Zenodo
  or Europeana.
- Olive-leaf or acanthus pilaster capital from Rome: not found. Only pilaster_capital_ephesus_stw (Greek, blobby).
- Europeana: five CC0 Corinthian capitals from the Milan civic archaeological collection digitised by Politecnico di
  Milano (e.g. A 0.9.1433, 38 x 53 x 38 cm, two leaf rings; A 0.9.7074 and A 0.9.7076 pilaster capitals), served by
  www.kaemart.it/3dicons/POLIMI/download.php?id=... as 3D-PDF only. Blender cannot import 3D-PDF (U3D/PRC), so they
  were not downloaded; worth converting if another tool is available.
- Scan the World capitals on Zenodo screened from their preview renders and rejected as eroded, medieval or non-Roman:
  21680482 (very eroded), 21162214 (ciborium), 21290343 and 21377504 (pillar fragments), 21243912 (Asian type, damaged),
  21215642 / 20235866 (Romanesque), 21163487 (Renaissance console), 21648093 (Cypriot), 21680578 (Catalan church).
- Other screened: 10289890 Corinthian-Nabataean capital (Petra style), 10217024 Trimontium (a sculpted model, not a
  scan), 10264262 (low-resolution Cordoba capital), 10328944 (modelled column), 10343182 "Italian chapiter" (date and
  origin not stated, CC BY-NC), 21167613 / 21411122 StW "Fragment of an Entablature" (satyr-head frieze slab, 131 MB,
  thin, provenance unknown), 21172069 StW "Cornice Block" (Egyptian, Philae), 10285184 Beja entablature (small
  architrave piece), 10348305 / 10367589 / 10282864 / 21489470 column bases (painted, eroded, or Romanesque).
