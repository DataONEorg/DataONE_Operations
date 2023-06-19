# d1nodeprops

Get and set extended properties for nodes in a DataONE environment.

`d1nodeprops` works directly with the CN LDAP service, and so the script must be run on a CN or with assistance from an SSH tunnel. 

## Examples

With an ssh tunnel open, like:

```
ssh -L3980:localhost:389 cn-stage-ucsb-1.test.dataone.org
```

List the nodes with some basic properties:

```
$ d1nodeprops -o list
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ NodeId                    ┃ URL                                                    ┃ Approv ┃ State ┃ Sync  ┃ Repl  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ urn:node:mnStageUCSB3     │ https://mn-stage-ucsb-3.test.dataone.org/metacat/d1/mn │ TRUE   │ up    │ FALSE │ TRUE  │
│ urn:node:mnStageUNM1      │ https://mn-stage-unm-1.test.dataone.org/mn             │ TRUE   │ down  │ FALSE │ TRUE  │
│ urn:node:mnStageORC1      │ https://mn-stage-orc-1.test.dataone.org/mn             │ FALSE  │ up    │ FALSE │ TRUE  │
│ urn:node:mnStageUCSB2     │ https://mn-stage-ucsb-2.test.dataone.org/metacat/d1/mn │ TRUE   │ up    │ TRUE  │ TRUE  │
│ urn:node:mnStagePISCO     │ http://test.piscoweb.org/catalog/d1/mn                 │ TRUE   │ down  │ FALSE │ TRUE  │
│ urn:node:mnStageLTER      │ https://mn-stage-ucsb-3.test.dataone.org/knb/d1/mn/    │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnStageCDL       │ https://d1-merritt-stage.cdlib.org:8084/knb/d1/mn      │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:USGSCSAS         │ http://mercury-ops2.ornl.gov/clearinghouse/mn          │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:ORNLDAAC         │ http://mercury-ops2.ornl.gov/ornldaac/mn               │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestTFRI       │ https://metacat3.tfri.gov.tw/tfri/d1/mn                │ FALSE  │ down  │ TRUE  │ TRUE  │
│ urn:node:mnTestSEAD       │ http://d2i-dev.d2i.indiana.edu:8081/sead/rest/mn       │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestUSANPN     │ https://mynpn-dev.usanpn.org/metacat/d1/mn             │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:TestKUBI         │ https://bidataone.nhm.ku.edu/mn                        │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:EDACGSTORE       │ https://gstore.unm.edu/dataone                         │ FALSE  │ down  │ FALSE │ FALSE │
│ urn:node:mnTestDRYAD      │ https://so.test.dataone.org/mnTestDRYAD                │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:DRYAD            │ https://datadryad.org/mn                               │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestGLEON      │ https://poseidon.limnology.wisc.edu/metacat/d1/mn      │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnDemo11         │ https://mn-demo-11.test.dataone.org/knb/d1/mn          │ FALSE  │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestEDORA      │ http://mercury-ops2.ornl.gov/EDORA_MN_TEST/mn          │ FALSE  │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestRGD        │ http://mercury-ops2.ornl.gov/RGD_MN_TEST/mn            │ FALSE  │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestIOE        │ https://data.rcg.montana.edu/catalog/d1/mn             │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestLTER       │ https://gmn-s.lternet.edu/mn                           │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestMPC        │ https://dataone-test.pop.umn.edu/mn                    │ TRUE   │ down  │ TRUE  │ TRUE  │
│ urn:node:mnTestAEKOS      │ https://dataone-dev.tern.org.au/mn                     │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestNRDC       │ https://sensor.nevada.edu/DataONE/mn                   │ FALSE  │ down  │ TRUE  │ TRUE  │
│ urn:node:mnTestNRDC1      │ https://sensor.nevada.edu/DataONETest/mn               │ FALSE  │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestPPBIO      │ https://ppbiodata.inpa.gov.br/metacat/d1/mn            │ FALSE  │ down  │ FALSE │ FALSE │
│ urn:node:mnTestGRIIDC     │ https://dataonetest.tamucc.edu/mn                      │ TRUE   │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestNEON       │ http://dataone.neonscience.org/metacat/d1/mn           │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestOTS        │ https://metacat.ots.ac.cr/metacat/d1/mn                │ TRUE   │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestARCTIC     │ https://test.arcticdata.io/metacat/d1/mn               │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestCLOEBIRD   │ http://dataone.ornith.cornell.edu/metacat/d1/mn        │ TRUE   │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestRW         │ https://dataone-test.researchworkspace.com/mn          │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestR2R        │ https://r2r-node.test.dataone.org/mn                   │ TRUE   │ down  │ TRUE  │ FALSE │
│ urn:node:mnTestUIC        │ https://dataone.lib.uic.edu/metacat/d1/mn              │ FALSE  │ up    │ TRUE  │ TRUE  │
│ urn:node:mnTestEDI        │ https://gmn-s.edirepository.org/mn                     │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestNCEI       │ https://ncei.nceas.ucsb.edu/mn                         │ TRUE   │ up    │ TRUE  │ TRUE  │
│ urn:node:mnTestPANGAEA    │ https://pangaea-dev-orc-1.test.dataone.org/mn          │ TRUE   │ down  │ FALSE │ FALSE │
│ urn:node:mnTestFEMC       │ https://dataone.uvm.edu/mn                             │ FALSE  │ up    │ FALSE │ FALSE │
│ urn:node:mnTestESS_DIVE   │ https://data-dev.ess-dive.lbl.gov/catalog/d1/mn        │ TRUE   │ up    │ FALSE │ FALSE │
│ urn:node:mnTestCyVerse    │ https://de-2.cyverse.org/dataone-node/rest/mn          │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnStageUCSB4     │ https://mn-stage-ucsb-4.test.dataone.org/metacat/d1/mn │ TRUE   │ up    │ FALSE │ TRUE  │
│ urn:node:mnTestIEDA       │ https://gmn.test.dataone.org/mn                        │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestCAS_CERN   │ https://data-en.cern.ac.cn/metacat/d1/mn               │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestCARY       │ https://figshare-orc-1.test.dataone.org/mn             │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:IEDA_EARTHCHEM   │ https://gmn.test.dataone.org/ieda/earthchem            │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:IEDA_USAP        │ https://gmn.test.dataone.org/ieda/usap                 │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:IEDA_MGDL        │ https://gmn.test.dataone.org/ieda/mgdl                 │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestGMN1       │ https://gmn.test.dataone.org/gmn/1                     │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestGMNLocal   │ https://dahlsys.com/gmn                                │ TRUE   │ up    │ FALSE │ FALSE │
│ urn:node:mnTestARM        │ https://gmn.test.dataone.org/arm                       │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestKILTHUB    │ https://gmn.test.dataone.org/kilthub                   │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestPNDB       │ https://test.pndb.fr/metacat/d1/mn                     │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestHYDROSHARE │ https://so.test.dataone.org/mnTestHYDROSHARE/          │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestKNB        │ https://dev.nceas.ucsb.edu/knb/d1/mn                   │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestHAKAI_IYS  │ https://so.test.dataone.org/mnTestHAKAI_IYS/           │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestDRYAD2     │ https://so.test.dataone.org/mnTestDRYAD2               │ TRUE   │ up    │ TRUE  │ FALSE │
│ urn:node:mnTestDRYAD3     │ https://so.test.dataone.org/mnTestDRYAD                │ TRUE   │ up    │ TRUE  │ FALSE │
└───────────────────────────┴────────────────────────────────────────────────────────┴────────┴───────┴───────┴───────┘
20230619T114709.863990 main WARNING: Duplicate Base URL: https://so.test.dataone.org/mnTestDRYAD

```
Get all the node properties listed in LDAP for `urn:node:mnTestARM`:
```
$ d1nodeprops -I urn:node:mnTestARM
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property                  ┃ Value                                                                                                ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ CN_node_name              │ ARM - Atmospheric Radiation Measurement Research Facility                                            │
│ CN_operational_status     │ operational                                                                                          │
│ CN_date_operational       │                                                                                                      │
│ CN_date_upcoming          │                                                                                                      │
│ CN_date_deprecated        │                                                                                                      │
│ CN_logo_url               │ https://raw.githubusercontent.com/DataONEorg/member-node-info/master/production/graphics/web/ARM.png │
│ CN_info_url               │ https://www.archive.arm.gov/                                                                         │
│ CN_location_lonlat        │                                                                                                      │
│ d1NodeSynchronize         │ TRUE                                                                                                 │
│ d1NodeSynSchdHour         │ *                                                                                                    │
│ subject                   │ CN=urn:node:mnTestARM,DC=dataone,DC=org                                                              │
│ cn                        │ urn:node:mnTestARM                                                                                   │
│ d1NodeReplicate           │ FALSE                                                                                                │
│ d1NodeSynSchdYear         │ *                                                                                                    │
│ d1NodeSynSchdWday         │ ?                                                                                                    │
│ d1NodeLastCompleteHarvest │ 1900-01-01T00:00:00Z                                                                                 │
│ d1NodeSynSchdMin          │ 0/3                                                                                                  │
│ d1NodeSynSchdMon          │ *                                                                                                    │
│ d1NodeId                  │ urn:node:mnTestARM                                                                                   │
│ d1NodeContactSubject      │ http://orcid.org/0000-0001-8849-7530                                                                 │
│ d1NodeBaseURL             │ https://gmn.test.dataone.org/arm                                                                     │
│ d1NodeName                │ ARM Stage                                                                                            │
│ d1NodeState               │ up                                                                                                   │
│ d1NodeSynSchdSec          │ 0                                                                                                    │
│ d1NodeDescription         │ ARM Stage                                                                                            │
│ d1NodeType                │ mn                                                                                                   │
│ d1NodeSynSchdMday         │ *                                                                                                    │
│ d1NodeApproved            │ TRUE                                                                                                 │
│ d1NodeLastHarvested       │ 2019-11-22T19:58:43.157+00:00                                                                        │
│ d1NodeLogLastAggregated   │ 2021-03-11T22:10:47.652+00:00                                                                        │
│ d1NodeAggregateLogs       │ FALSE                                                                                                │
└───────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Same as above but with JSON output:
```
$ d1nodeprops  -I urn:node:mnTestARM -f json
{
  "CN_node_name": "ARM - Atmospheric Radiation Measurement Research Facility",
  "CN_operational_status": "operational",
  "CN_date_operational": null,
  "CN_date_upcoming": null,
  "CN_date_deprecated": null,
  "CN_logo_url": "https://raw.githubusercontent.com/DataONEorg/member-node-info/master/production/graphics/web/ARM.png",
  "CN_info_url": "https://www.archive.arm.gov/",
  "CN_location_lonlat": null,
  "d1NodeSynchronize": "TRUE",
  "d1NodeSynSchdHour": "*",
  "subject": "CN=urn:node:mnTestARM,DC=dataone,DC=org",
  "cn": "urn:node:mnTestARM",
  "d1NodeReplicate": "FALSE",
  "d1NodeSynSchdYear": "*",
  "d1NodeSynSchdWday": "?",
  "d1NodeLastCompleteHarvest": "1900-01-01T00:00:00Z",
  "d1NodeSynSchdMin": "0/3",
  "d1NodeSynSchdMon": "*",
  "d1NodeId": "urn:node:mnTestARM",
  "d1NodeContactSubject": "http://orcid.org/0000-0001-8849-7530",
  "d1NodeBaseURL": "https://gmn.test.dataone.org/arm",
  "d1NodeName": "ARM Stage",
  "d1NodeState": "up",
  "d1NodeSynSchdSec": "0",
  "d1NodeDescription": "ARM Stage",
  "d1NodeType": "mn",
  "d1NodeSynSchdMday": "*",
  "d1NodeApproved": "TRUE",
  "d1NodeLastHarvested": "2019-11-22T19:58:43.157+00:00",
  "d1NodeLogLastAggregated": "2021-03-11T22:10:47.652+00:00",
  "d1NodeAggregateLogs": "FALSE"
}
```

Set `CN_node_name` for the node `urn:node:mnTestGMN1`:

```
d1nodeprops -I urn:node:mnTestGMN1 -o update -p ****** -k CN_node_name "MN Test GMN1"
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property                  ┃ Value                                    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ CN_node_name              │ MN Test GMN1                             │
│ CN_operational_status     │                                          │
│ CN_date_operational       │                                          │
│ CN_date_upcoming          │                                          │
│ CN_date_deprecated        │                                          │
│ CN_logo_url               │                                          │
│ CN_info_url               │                                          │
│ CN_location_lonlat        │                                          │
│ d1NodeSynchronize         │ TRUE                                     │
│ d1NodeSynSchdHour         │ *                                        │
│ subject                   │ CN=urn:node:mnTestGMN1,DC=dataone,DC=org │
│ cn                        │ urn:node:mnTestGMN1                      │
│ d1NodeReplicate           │ FALSE                                    │
│ d1NodeSynSchdYear         │ *                                        │
│ d1NodeSynSchdWday         │ ?                                        │
│ d1NodeLastCompleteHarvest │ 1900-01-01T00:00:00Z                     │
│ d1NodeSynSchdMin          │ 0/3                                      │
│ d1NodeSynSchdMon          │ *                                        │
│ d1NodeId                  │ urn:node:mnTestGMN1                      │
│ d1NodeContactSubject      │ http://orcid.org/0000-0001-8849-7530     │
│ d1NodeBaseURL             │ https://gmn.test.dataone.org/gmn/1       │
│ d1NodeName                │ GMN Test 1                               │
│ d1NodeState               │ up                                       │
│ d1NodeSynSchdSec          │ 0                                        │
│ d1NodeDescription         │ GMN Test 1                               │
│ d1NodeType                │ mn                                       │
│ d1NodeSynSchdMday         │ *                                        │
│ d1NodeApproved            │ TRUE                                     │
│ d1NodeLastHarvested       │ 2019-07-02T07:42:13.429+00:00            │
│ d1NodeLogLastAggregated   │ 2021-05-18T23:45:55.455+00:00            │
│ d1NodeAggregateLogs       │ FALSE                                    │
└───────────────────────────┴──────────────────────────────────────────┘
```
