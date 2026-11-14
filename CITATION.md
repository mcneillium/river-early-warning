# Data citation and licence

This repository contains code only. The data is downloaded by
`python -m rew.download` and is never committed.

## Dataset

Coxon, G., Zheng, Y., Barbedo, R., Cooper, H., Fileni, F., Fowler, H., Fry, M.,
Green, A., Gribbin, T., Harfoot, H., Lewis, E., Qiu, X., Salwey, S.,
Wendt, D.E., Ribeiro Neto, G. (2025). *Catchment boundaries, daily and
sub-daily hydrometeorological time series, groundwater level time series and
attributes for 671 catchments in Great Britain (CAMELS-GB v2).* NERC EDS
Environmental Information Data Centre.
https://doi.org/10.5285/9a46d428-958f-4ac1-86eb-94eee70c0955

## Data paper

Coxon, G., et al. (2026). CAMELS-GB v2: hydrometeorological time series and
landscape attributes for 671 catchments in Great Britain. *Earth System
Science Data*, 18(6), 4345-4371.

## Licence

Checked on 14 November 2026. The dataset record at the NERC EDS Environmental
Information Data Centre states that the resource is available under the terms
of the Open Government Licence. The data paper's data access statement says
the same. The record also carries attribution statements for the bodies whose
data it contains (among them Natural Resources Wales, the British Geological
Survey, the UK Centre for Ecology & Hydrology and the University of Bristol).

No data is redistributed in this repository, so the licence applies to anyone
who runs the download step.

TODO (Paul): before any paper or data release, open the dataset record, copy
the full list of attribution statements it asks for into the
acknowledgements, and paste them here.

## Parts used

| Part | Files | Used for |
| --- | --- | --- |
| `Catchment_Timeseries/hydro-meteorological/daily/` | 671 | Flow, precipitation, temperature, PET |
| `Catchment_Attributes/` | 9 | Catchment descriptors (used from week 2) |

Checksums of every downloaded file are written to `data/MANIFEST.json`.
